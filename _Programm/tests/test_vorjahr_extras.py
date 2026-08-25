# -*- coding: utf-8 -*-
"""Hirn-Erweiterungen: AAB-Ende, 12-Spalten-Anlagenspiegel, Inline-Vorjahr, Text-Sortierung."""
from anhangspruefer.vorjahresvergleich.extractor import (
    AnhangItem,
    _extract_inline_vorjahr,
    _is_anhang_end,
    anhang_page_range,
)
from anhangspruefer.vorjahresvergleich.text_compare import TextRow, sort_text_rows


def test_aab_endet_den_anhang():
    assert _is_anhang_end("Allgemeine Auftragsbedingungen")
    assert _is_anhang_end("Allgemeine Auftragsbedingungen fuer Wirtschaftstreuhandberufe")
    pages = ["Deckblatt", "Anhang", "Bewertung", "Allgemeine Auftragsbedingungen fuer WT"]
    assert anhang_page_range(pages) == (1, 3)


def test_inline_vorjahr_paar():
    text = "Im Geschaeftsjahr waren im Durchschnitt 4 Arbeitnehmer (Vorjahr: 3 Arbeitnehmer) beschaeftigt."
    items = _extract_inline_vorjahr(text, 2)
    assert len(items) == 1
    assert items[0].current_values == [4.0]
    assert items[0].prior_values == [3.0]


def test_text_rows_aenderungen_zuerst():
    rows = [
        TextRow("a", "a", "IDENT", 1, 1),
        TextRow("neu", "", "NEU", 2, None),
        TextRow("x", "y", "GEÄNDERT", 3, 3),
        TextRow("", "alt", "FEHLT", None, 4),
    ]
    ordered = [r.status for r in sort_text_rows(rows)]
    assert ordered == ["FEHLT", "GEÄNDERT", "NEU", "IDENT"]
