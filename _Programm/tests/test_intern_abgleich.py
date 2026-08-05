"""Interner Abgleich: Detailzahlen vorne (Bilanz/GuV) ↔ Anhang hinten.

Nur synthetische Daten – keine Mandantenunterlagen.
"""

from anhangspruefer.pruefung.intern_abgleich import (
    BETRAG_GRENZE,
    STUECKZAHL_GRENZE,
    _ist_jahreszahl,
    _semantisch_unvergleichbar,
)


# --- Schutz vor Fehlpaarungen ------------------------------------------------
def test_jahreszahl_wird_erkannt():
    # "2.025" im Text ist die Jahreszahl 2025, kein Betrag
    assert _ist_jahreszahl(2025) is True
    assert _ist_jahreszahl(1998) is True
    assert _ist_jahreszahl(2025.50) is False      # mit Nachkommastellen = Betrag
    assert _ist_jahreszahl(34634.94) is False


def test_stueckzahl_gegen_betrag_ist_unvergleichbar():
    # 6 Arbeitnehmer vs. 5.000,00 EUR darf keine Abweichung erzeugen
    assert _semantisch_unvergleichbar(5000.0, 6.0) is True
    assert _semantisch_unvergleichbar(2.0, 0.0) is False      # beide klein
    assert _semantisch_unvergleichbar(34634.94, 34634.94) is False
    assert _semantisch_unvergleichbar(94145.34, 73964.11) is False   # beide Beträge


def test_grenzen_sind_plausibel():
    assert STUECKZAHL_GRENZE < BETRAG_GRENZE


# --- Abgleichslogik ----------------------------------------------------------
def test_abgleich_ohne_vorderen_teil_liefert_leeres_ergebnis(tmp_path, monkeypatch):
    """Reines Anhang-Dokument (Anhang beginnt auf Seite 1) -> nichts abzugleichen."""
    import anhangspruefer.pruefung.intern_abgleich as mod

    monkeypatch.setattr(mod, "load_page_texts", lambda p, **k: ["Anhang Text"])
    monkeypatch.setattr(mod, "anhang_page_range", lambda pages: (0, 1))
    r = mod.abgleich_intern(tmp_path / "x.pdf")
    assert r.zeilen == [] and r.anhang_ab_seite is None


def test_abgleich_meldet_nur_echte_abweichung(tmp_path, monkeypatch):
    """Gleiche Bezeichnung vorne und im Anhang: gleicher Wert -> OK,
    abweichender Wert -> ABWEICHUNG."""
    import anhangspruefer.pruefung.intern_abgleich as mod
    from anhangspruefer.vorjahresvergleich.extractor import AnhangItem

    vorne = [
        AnhangItem(label="1000 Sonstige Rueckstellungen", page=3,
                   current_values=[34634.94], prior_values=[]),
        AnhangItem(label="1100 Verbindlichkeiten aus L+L", page=3,
                   current_values=[10000.00], prior_values=[]),
    ]
    hinten = [
        AnhangItem(label="Sonstige Rueckstellungen", page=9,
                   current_values=[34634.94], prior_values=[]),
        AnhangItem(label="Verbindlichkeiten aus L+L", page=9,
                   current_values=[12500.00], prior_values=[]),
    ]
    monkeypatch.setattr(mod, "load_page_texts", lambda p, **k: [""] * 10)
    monkeypatch.setattr(mod, "anhang_page_range", lambda pages: (5, 10))
    monkeypatch.setattr(mod, "extract_items",
                        lambda p, page_range=None: vorne if page_range == (0, 5) else hinten)

    r = mod.abgleich_intern(tmp_path / "x.pdf")
    assert r.anzahl_ok == 1
    assert r.anzahl_abweichung == 1
    abw = [z for z in r.zeilen if z.status == "ABWEICHUNG"][0]
    assert abw.differenz == -2500.00
