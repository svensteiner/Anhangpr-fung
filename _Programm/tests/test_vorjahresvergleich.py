"""Tests für Hilfsfunktionen des Vorjahresvergleichs (ohne PDF-IO)."""

from anhangspruefer.vorjahresvergleich.extractor import (
    parse_german_number,
    split_label_and_trailing_numbers,
    normalize_label,
)


def test_parse_german_number_thousand_and_decimal():
    assert parse_german_number("1.234.567,89") == 1234567.89
    assert parse_german_number("0,00") == 0.0
    assert parse_german_number("42") == 42.0


def test_parse_german_number_negative_and_brackets():
    assert parse_german_number("-1.000,50") == -1000.50
    assert parse_german_number("(2.500,00)") == -2500.0


def test_parse_german_number_invalid_returns_none():
    assert parse_german_number("foo") is None


def test_split_label_pure_label():
    label, nums = split_label_and_trailing_numbers(
        "Erläuterungen zu einzelnen Posten von Bilanz und GuV"
    )
    assert nums == []
    assert "Erläuterungen" in label


def test_split_label_with_trailing_numbers():
    label, nums = split_label_and_trailing_numbers(
        "Software 2.634.705,31 664.581,01 2.006.736,92"
    )
    assert label == "Software"
    assert nums == [2634705.31, 664581.01, 2006736.92]


def test_split_label_vorjahr_row():
    label, nums = split_label_and_trailing_numbers(
        "Vorjahr 17.441,97 0,00 0,00 1.946,56 19.388,53"
    )
    assert label == "Vorjahr"
    assert len(nums) == 5
    assert nums[0] == 17441.97


def test_normalize_label_umlauts_and_punctuation():
    a = normalize_label("1. Anlagevermögen (brutto)")
    b = normalize_label("Anlagevermoegen brutto")
    assert a == b
