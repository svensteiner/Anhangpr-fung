"""Smoke-Tests für Textverarbeitungs-Hilfsfunktionen."""

from anhangspruefer.utils.text_processing import (
    normalize_text,
    fuzzy_match,
    extract_paragraphs,
    extract_ugb_reference,
    extract_amounts,
    clean_extracted_text,
)


def test_normalize_text_collapses_whitespace():
    raw = "Anhang   zum\r\nJahresabschluss\r\n\r\n  Vorjahr "
    out = normalize_text(raw)
    assert "\r" not in out
    assert "Anhang zum" in out
    assert "Vorjahr" in out


def test_fuzzy_match_exact_substring():
    is_match, score = fuzzy_match("Angaben zum Anlagevermögen", "anlagevermögen")
    assert is_match is True
    assert score == 1.0


def test_fuzzy_match_no_overlap():
    is_match, score = fuzzy_match("Bilanz", "Geschäftsführerbezüge", threshold=0.8)
    assert is_match is False
    assert score < 0.8


def test_extract_ugb_reference_finds_paragraphs():
    text = "Gemäß § 236 Abs 1 und § 237 sowie §§ 238 ff sind Angaben zu machen."
    refs = extract_ugb_reference(text)
    assert any("236" in r for r in refs)
    assert any("237" in r for r in refs)
    assert any("238" in r for r in refs)


def test_extract_amounts_german_format():
    text = "Der Betrag beläuft sich auf 1.234.567,89 EUR im Berichtsjahr."
    amounts = extract_amounts(text)
    values = [v for _, v in amounts if v is not None]
    assert 1234567.89 in values


def test_extract_paragraphs_skips_short_fragments():
    text = "Hi\n\nDies ist ein längerer Absatz mit Inhalt.\n\nx"
    paras = extract_paragraphs(text)
    assert len(paras) == 1
    assert "längerer Absatz" in paras[0]


def test_clean_extracted_text_removes_page_markers():
    text = "Inhalt eins\nSeite 5 von 10\nInhalt zwei"
    out = clean_extracted_text(text)
    assert "Seite 5" not in out
