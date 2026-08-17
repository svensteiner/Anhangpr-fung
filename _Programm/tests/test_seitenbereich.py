"""Seitenbereich in ``extract_items`` und die Mindesttextprüfung.

Nur synthetische Daten – keine Mandantenunterlagen.

Hintergrund
===========
``abgleich_intern`` las separate Bilanz-/GuV-Dateien mit einem Seitenbereich,
dessen Ende weit über das Dokument hinausreichte ("ganzes Dokument"). Die
Seitenschleife in ``extract_items`` griff dadurch an der Seitenliste vorbei,
warf ``IndexError`` – und der Aufrufer verwarf die Datei in einem
``except Exception: continue`` lautlos. Jede getrennt hochgeladene Bilanz war
damit wirkungslos, OHNE dass es jemand bemerkte.

Diese Tests fahren deshalb bewusst das ECHTE ``extract_items`` (nur der
Datei-Zugriff ist ersetzt). Das Mocken von ``extract_items`` war genau der
Grund, warum der bestehende Test den Fehler nicht gesehen hat.
"""

from pathlib import Path

import pytest

import anhangspruefer.vorjahresvergleich.extractor as extr
from anhangspruefer.parsers.document_text import (
    LEER_GRENZE_JE_SEITE,
    LESBARE_SUFFIXE,
    TEXTARM_GRENZE_JE_SEITE,
    Textausbeute,
    kann_lesen,
    textausbeute,
)


# Eine Bilanzseite in der Form, die der Extraktor erwartet: "Label  Zahl".
_BILANZ_SEITE = (
    "Bilanz zum 31.12.2025\n"
    "Sonstige Rueckstellungen 34.634,94\n"
    "Verbindlichkeiten aus Lieferungen 128.400,10\n"
)


def _seiten(monkeypatch, seiten: list):
    """Ersetzt nur den Datei-Zugriff – die Extraktionslogik bleibt echt."""
    monkeypatch.setattr(extr, "load_page_texts", lambda p, **k: seiten)


# --- Seitenbereich -----------------------------------------------------------
def test_seitenbereich_ueber_dokumentende_wirft_nicht(tmp_path, monkeypatch):
    """Ein zu grosses ``end`` darf den Extraktor nicht aus der Bahn werfen.

    Das ist der Regressionstest zum stillen Verlust separater Bilanzdateien.
    """
    _seiten(monkeypatch, [_BILANZ_SEITE, "Seite 2"])

    items = extr.extract_items(tmp_path / "bilanz.pdf", page_range=(0, 10_000))

    assert items, "Posten muessen gefunden werden, statt in einem IndexError zu enden"
    assert any("Rueckstellungen" in it.label for it in items)


def test_ganzes_dokument_ueber_end_none(tmp_path, monkeypatch):
    """``(0, None)`` ist die ausdrueckliche Schreibweise fuer "ganzes Dokument".

    Geprueft wird an unterschiedlichen Seiteninhalten – gleiche Label mit
    gleichem Wert werden vom Extraktor bewusst dedupliziert und taugen daher
    nicht als Nachweis, dass die zweite Seite gelesen wurde.
    """
    guv_seite = "Gewinn- und Verlustrechnung\nUmsatzerloese Inland 987.654,32\n"
    _seiten(monkeypatch, [_BILANZ_SEITE, guv_seite])

    alle = extr.extract_items(tmp_path / "abschluss.pdf", page_range=(0, None))
    nur_erste = extr.extract_items(tmp_path / "abschluss.pdf", page_range=(0, 1))

    assert any(it.page == 2 for it in alle), "zweite Seite muss gelesen werden"
    assert any("Umsatzerloese" in it.label for it in alle)
    assert all(it.page == 1 for it in nur_erste)
    assert len(alle) > len(nur_erste)


def test_negativer_start_wird_begrenzt(tmp_path, monkeypatch):
    _seiten(monkeypatch, [_BILANZ_SEITE])
    assert extr.extract_items(tmp_path / "b.pdf", page_range=(-5, 10_000))


def test_leeres_dokument_liefert_leere_liste(tmp_path, monkeypatch):
    _seiten(monkeypatch, [])
    assert extr.extract_items(tmp_path / "b.pdf", page_range=(0, None)) == []


# --- Zusammenspiel mit dem internen Abgleich ---------------------------------
def test_separate_bilanzdatei_wird_wirklich_gelesen(tmp_path, monkeypatch):
    """Ende zu Ende mit echtem Extraktor: die Bilanz muss den Abgleich erzeugen.

    Der bestehende Test in ``test_intern_abgleich.py`` mockt ``extract_items``
    und haette den Fehler nie gesehen.
    """
    import anhangspruefer.pruefung.intern_abgleich as mod

    anhang_seite = "Anhang\nSonstige Rueckstellungen 34.634,94\n"

    # Anhang beginnt auf Seite 1 -> kein vorderer Teil in derselben Datei;
    # die Detailzahlen koennen nur aus der separaten Bilanzdatei kommen.
    monkeypatch.setattr(mod, "load_page_texts", lambda p, **k: [anhang_seite])
    monkeypatch.setattr(mod, "anhang_page_range", lambda pages: (0, 1))

    def seiten_je_datei(p, **k):
        return [_BILANZ_SEITE] if Path(p).name == "bilanz.pdf" else [anhang_seite]
    monkeypatch.setattr(extr, "load_page_texts", seiten_je_datei)

    r = mod.abgleich_intern(tmp_path / "anhang.pdf",
                            detail_dokumente=[tmp_path / "bilanz.pdf"])

    assert r.uebersprungene_dateien == []
    assert r.anzahl_ok == 1 and r.anzahl_abweichung == 0


def test_beschaedigte_pdf_beilage_wird_vermerkt_statt_verschwiegen(tmp_path, monkeypatch):
    """Ein lesbares Format, das sich nicht oeffnen laesst, MUSS auftauchen.

    Genau dieses Verschweigen hat den Seitenbereichs-Fehler jahrelang gedeckt.
    """
    import anhangspruefer.pruefung.intern_abgleich as mod

    monkeypatch.setattr(mod, "load_page_texts", lambda p, **k: ["Anhang"])
    monkeypatch.setattr(mod, "anhang_page_range", lambda pages: (0, 1))

    def kaputt(p, page_range=None):
        raise RuntimeError("PDF ist beschaedigt")
    monkeypatch.setattr(mod, "extract_items", kaputt)

    r = mod.abgleich_intern(tmp_path / "anhang.pdf",
                            detail_dokumente=[tmp_path / "bilanz.pdf"])

    assert len(r.uebersprungene_dateien) == 1
    assert "bilanz.pdf" in r.uebersprungene_dateien[0]
    assert "beschaedigt" in r.uebersprungene_dateien[0]


def test_excel_beleg_erzeugt_keinen_fehlalarm(tmp_path, monkeypatch):
    """Ein Excel-Beleg ist Beleg fuer die BELEGpruefung, keine Bilanzquelle.

    Er darf hier still uebergangen werden – sonst warnt jeder normale Lauf mit
    Personalstand-Excel, und die Warnung verliert ihre Bedeutung.
    """
    import anhangspruefer.pruefung.intern_abgleich as mod

    monkeypatch.setattr(mod, "load_page_texts", lambda p, **k: ["Anhang"])
    monkeypatch.setattr(mod, "anhang_page_range", lambda pages: (0, 1))

    def darf_nicht_aufgerufen_werden(p, page_range=None):
        raise AssertionError(f"Excel darf nicht als Textquelle gelesen werden: {p}")
    monkeypatch.setattr(mod, "extract_items", darf_nicht_aufgerufen_werden)

    r = mod.abgleich_intern(tmp_path / "anhang.pdf",
                            detail_dokumente=[tmp_path / "personalstand.xlsx"])

    assert r.uebersprungene_dateien == []
    assert r.zeilen == []


# --- Mindesttextprüfung ------------------------------------------------------
def test_scan_ohne_textebene_gilt_als_leer():
    """Ein Scan liefert leere Seitentexte – das muss erkannt werden."""
    b = textausbeute([""] * 30, "Abschluss_2025_gescannt.pdf")
    assert b.ist_leer is True
    assert b.ist_textarm is False          # leer schliesst textarm aus
    assert "Scan ohne Texterkennung" in b.meldung
    assert "Abschluss_2025_gescannt.pdf" in b.meldung


def test_dokument_ohne_seiten():
    b = textausbeute([], "leer.pdf")
    assert b.ist_leer is True
    assert b.zeichen_je_seite == 0.0
    assert "keine lesbaren Seiten" in b.meldung


def test_normaler_abschluss_ist_unauffaellig():
    """Ein gesetzter Abschluss liegt weit ueber den Schwellen."""
    b = textausbeute(["x" * 2000] * 40, "Abschluss_2025.pdf")
    assert b.ist_leer is False and b.ist_textarm is False
    assert b.meldung == ""


def test_textarmes_dokument_warnt_ohne_abbruch():
    zeichen = (LEER_GRENZE_JE_SEITE + TEXTARM_GRENZE_JE_SEITE) // 2
    b = textausbeute(["x" * zeichen] * 10, "teil_gescannt.pdf")
    assert b.ist_leer is False
    assert b.ist_textarm is True
    assert "auffällig wenig Text" in b.meldung


@pytest.mark.parametrize("grenze_fall, erwartet_leer", [
    (LEER_GRENZE_JE_SEITE, True),          # genau auf der Grenze = noch leer
    (LEER_GRENZE_JE_SEITE + 1, False),
])
def test_leer_grenze_ist_inklusiv(grenze_fall, erwartet_leer):
    b = textausbeute(["x" * grenze_fall], "x.pdf")
    assert b.ist_leer is erwartet_leer


def test_schwellen_sind_plausibel():
    assert 0 < LEER_GRENZE_JE_SEITE < TEXTARM_GRENZE_JE_SEITE


def test_kann_lesen_deckt_sich_mit_dem_konnektor():
    """``kann_lesen`` und die Format-Weiche in ``load_page_texts`` duerfen nicht
    auseinanderlaufen."""
    from anhangspruefer.parsers.document_text import load_page_texts

    for suffix in LESBARE_SUFFIXE:
        assert kann_lesen(f"x{suffix}") and kann_lesen(f"X{suffix.upper()}")
    for suffix in (".xlsx", ".rtf", ".txt", ".msg", ""):
        assert not kann_lesen(f"x{suffix}")
        with pytest.raises(ValueError):
            load_page_texts(f"nicht_vorhanden{suffix}")


def test_none_seiten_zaehlen_als_kein_text():
    """pdfplumber liefert bei textlosen Seiten ``None`` -> darf nicht crashen."""
    b = Textausbeute(datei="x.pdf", seiten=3, zeichen=0)
    assert b.ist_leer is True
    assert textausbeute([None, None], "x.pdf").ist_leer is True
