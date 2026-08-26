"""Präzision des Vorjahresvergleichs: keine Fehlmeldungen NUR_VORJAHR/NUR_AKTUELL.

Fachregel des Prüfers: Der Anhang ändert sich real kaum — ein hoher Anteil
einseitiger Meldungen ist fast immer ein Artefakt. Präzision vor Vollständigkeit.
Nur synthetische Daten, keine Mandantenunterlagen.
"""

from pathlib import Path

from anhangspruefer.vorjahresvergleich.extractor import AnhangItem, CURRENCY_PAIR_RE
from anhangspruefer.vorjahresvergleich.comparator import (
    _vorhanden_laut_volltext,
    compare_anhaenge,
)


class _FakePipeline:
    """Liefert vorgegebene Posten statt echter PDF-Extraktion."""

    name = "fake"

    def __init__(self, current, prior):
        self._map = {"current.pdf": current, "prior.pdf": prior}

    def extract_anhang_items(self, path):
        return self._map[Path(path).name]


def _item(label, current, prior=(), page=1, double_row=False):
    return AnhangItem(label=label, page=page, current_values=list(current),
                      prior_values=list(prior), double_row=double_row)


def _compare(current, prior):
    return compare_anhaenge(Path("current.pdf"), Path("prior.pdf"),
                            pipeline=_FakePipeline(current, prior))


# --- Währungs-Spaltenkopf ----------------------------------------------------
def test_currency_pair_header_detected():
    assert CURRENCY_PAIR_RE.match("  EUR   EUR ")
    assert CURRENCY_PAIR_RE.match("TEUR TEUR")
    assert CURRENCY_PAIR_RE.match("EUR TEUR")


def test_single_currency_is_no_header():
    # Ein einzelnes EUR ist KEIN Zwei-Spalten-Kopf -> darf keinen Modus setzen
    assert not CURRENCY_PAIR_RE.match("EUR")
    assert not CURRENCY_PAIR_RE.match("EUR 1.234,00")


# --- Symmetrie: Posten ohne Eröffnungswert markiert seinen Partner ----------
def test_posten_ohne_eroeffnungswert_erzeugt_kein_nur_vorjahr():
    """Der Posten steht im aktuellen Anhang (nur ohne Vergleichswert).
    Sein Vorjahres-Gegenstück darf NICHT als 'fehlt heuer' gemeldet werden."""
    current = [_item("Sonstige Rueckstellungen", [5000.0])]          # nur 1 Wert
    prior = [_item("Sonstige Rueckstellungen", [5000.0], [4000.0])]
    rows = _compare(current, prior).rows
    assert not [r for r in rows if r.status == "NUR_VORJAHR"]


def test_echter_wegfall_wird_weiterhin_gemeldet():
    """Ein Posten, der wirklich nur im Vorjahr existiert, MUSS gemeldet werden."""
    current = [_item("Sonstige Rueckstellungen", [5000.0], [4000.0])]
    prior = [_item("Sonstige Rueckstellungen", [4000.0], [3000.0]),
             _item("Rueckstellung fuer Rechtsstreit", [1234.0], [1000.0])]
    rows = _compare(current, prior).rows
    nur_vj = [r for r in rows if r.status == "NUR_VORJAHR"]
    assert len(nur_vj) == 1
    assert "Rechtsstreit" in nur_vj[0].label


# --- Volltext-Gegenprobe -----------------------------------------------------
def test_gegenprobe_erkennt_vorhandensein():
    volltext = "diegesellschaftweistsonstigerueckstellungenaus"
    assert _vorhanden_laut_volltext("sonstigerueckstellungen", volltext) is True


def test_gegenprobe_kurze_schluessel_beweisen_nichts():
    # "summe" käme zufällig überall vor -> darf nichts unterdrücken
    assert _vorhanden_laut_volltext("summe", "irgendeinsummetext") is False


def test_gegenprobe_ohne_volltext_unterdrueckt_nichts():
    assert _vorhanden_laut_volltext("sonstigerueckstellungen", "") is False


def test_eindeutiger_wert_matcht_trotz_anderem_label():
    """OCR verstellt den Namen, der Betrag ist eindeutig → trotzdem OK."""
    current = [_item("20500 Abgrenzungen Forderungen", [100.0], [27473.55])]
    prior = [_item("Abgrenzungen Ford.", [27473.55], [25000.0])]
    rows = _compare(current, prior).rows
    ok = [r for r in rows if r.status == "OK"]
    assert len(ok) == 1
    assert abs(ok[0].value_in_current_anhang - 27473.55) < 0.01


def test_mehrdeutiger_wert_wird_nicht_geraten():
    current = [_item("Posten A", [100.0], [50.0])]
    prior = [_item("X", [50.0]), _item("Y", [50.0])]
    rows = _compare(current, prior).rows
    assert not [r for r in rows if r.status == "OK"]


def test_null_betrag_kein_wertmatch():
    current = [_item("Neu mit Null", [1.0], [0.0])]
    prior = [_item("Ganz anderer Posten", [0.0])]
    rows = _compare(current, prior).rows
    assert not [r for r in rows if r.status == "OK"]
