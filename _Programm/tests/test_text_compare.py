"""Tests für die robuste Absatz-Paarung im Textvergleich (Vorjahresvergleich).

Reihenfolge-unabhängige Paarung nach bester Ähnlichkeit + Enthaltensein-Prüfung,
damit umgestellte/anders aufgeteilte Absätze NICHT als NEU/FEHLT erscheinen.
Nur synthetische Texte – keine Mandantendaten.
"""

from anhangspruefer.vorjahresvergleich.text_compare import _pair_paragraphs, diff_excerpt


def _p(text, page=1):
    return (text, page)


def test_reordered_paragraphs_have_no_false_gaps():
    a = "Die Gesellschaft wendet das Gesamtkostenverfahren an und bilanziert vorsichtig."
    b = "Rueckstellungen werden mit dem voraussichtlichen Erfuellungsbetrag angesetzt."
    rows = _pair_paragraphs([_p(a), _p(b)], [_p(b), _p(a)])  # umgekehrte Reihenfolge
    assert len(rows) == 2
    assert {r.status for r in rows} == {"IDENT"}


def test_merged_paragraph_is_not_a_gap():
    p1 = "Die latenten Steuern werden mit dem Steuersatz von dreiundzwanzig Prozent bewertet."
    p2 = "Eine Abzinsung der latenten Steuern erfolgt ausdruecklich nicht."
    # Vorjahr getrennt, aktuell verschmolzen -> keine FEHLT/NEU
    rows = _pair_paragraphs([_p(p1 + " " + p2)], [_p(p1), _p(p2)])
    assert all(r.status not in ("FEHLT", "NEU") for r in rows)


def test_genuinely_missing_paragraph_is_fehlt():
    common = "Die Gewinn- und Verlustrechnung wurde nach dem Gesamtkostenverfahren erstellt."
    only_prior = "Zusaetzlich bestand eine wesentliche Haftung aus einem laufenden Gerichtsverfahren."
    rows = _pair_paragraphs([_p(common)], [_p(common), _p(only_prior)])
    fehlt = [r for r in rows if r.status == "FEHLT"]
    assert len(fehlt) == 1
    assert "Haftung" in fehlt[0].prior


def test_genuinely_new_paragraph_is_neu():
    common = "Die Gewinn- und Verlustrechnung wurde nach dem Gesamtkostenverfahren erstellt."
    only_current = "Neu wurde eine Patronatserklaerung der Muttergesellschaft im Berichtsjahr abgegeben."
    rows = _pair_paragraphs([_p(common), _p(only_current)], [_p(common)])
    neu = [r for r in rows if r.status == "NEU"]
    assert len(neu) == 1
    assert "Patronatserkl" in neu[0].current


def test_changed_paragraph_is_geaendert_not_gap():
    cur = "Der durchschnittliche Personalstand betrug im Berichtsjahr x  Angestellte im Vertrieb."
    pri = "Der durchschnittliche Personalstand betrug im Vorjahr y  Angestellte in der Verwaltung."
    rows = _pair_paragraphs([_p(cur)], [_p(pri)])
    assert len(rows) == 1
    assert rows[0].status == "GEÄNDERT"


# --- Unterschied-Auszug (neue Excel-Spalte) ---------------------------------
def test_diff_excerpt_identical_is_empty():
    assert diff_excerpt("Gleicher Text hier.", "Gleicher Text hier.") == ""


def test_diff_excerpt_shows_both_sides():
    d = diff_excerpt("Betrag von EUR 13.198,00 angesetzt.", "Betrag von EUR 6.886,00 angesetzt.")
    assert "aktuell:" in d and "13.198,00" in d
    assert "Vorjahr:" in d and "6.886,00" in d


def test_diff_excerpt_ignores_lone_punctuation():
    # führendes "." (Extraktionsartefakt) ist kein inhaltlicher Unterschied
    assert diff_excerpt("MUSTERFIRMA Anhang Text.", ". MUSTERFIRMA Anhang Text.") == "nur geänderte Zahlen/Zeichen"


def test_diff_excerpt_new_and_missing():
    assert "nur aktuell" in diff_excerpt("Neuer Absatz.", "")
    assert "nur im Vorjahr" in diff_excerpt("", "Alter Absatz.")
