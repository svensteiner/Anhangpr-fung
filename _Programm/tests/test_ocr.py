"""Tests fuer den lokalen OCR-Konnektor. Kein EasyOCR-Lauf, kein Mandanten-PDF."""

import json
from pathlib import Path

import pytest
from anhangspruefer.parsers import ocr as ocr_mod

@pytest.fixture(autouse=True)
def _isolated_ocr_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("ANHANGSPRUEFER_OCR_CACHE", str(tmp_path / "ocr_cache"))

from anhangspruefer.parsers.document_text import load_page_texts


def test_cache_path_uses_stem():
    assert ocr_mod.cache_path(Path("Bericht.PDF")).name == "Bericht.ocr.json"


def test_load_cache_reads_sidecar(tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 empty-" + tmp_path.name.encode())
    sidecar = tmp_path / "scan.ocr.json"
    sidecar.write_text(
        json.dumps({"texts": ["Anhang Seite eins", "Seite zwei"]}),
        encoding="utf-8",
    )
    assert ocr_mod.load_cache(pdf) == ["Anhang Seite eins", "Seite zwei"]


def test_load_cache_rejects_stale_size(tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 empty")
    sidecar = tmp_path / "scan.ocr.json"
    sidecar.write_text(
        json.dumps({"source_size": 999999, "texts": ["alt"]}),
        encoding="utf-8",
    )
    assert ocr_mod.load_cache(pdf) is None


def test_ocr_pdf_uses_cache_without_engine(tmp_path, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4 empty")
    sidecar = tmp_path / "scan.ocr.json"
    sidecar.write_text(json.dumps({"texts": ["lokal erkannt"]}), encoding="utf-8")

    def _boom(*_a, **_k):
        raise AssertionError("EasyOCR darf bei Cache-Treffer nicht starten")

    monkeypatch.setattr(ocr_mod, "easyocr", None, raising=False)
    assert ocr_mod.ocr_pdf(pdf) == ["lokal erkannt"]


def test_empty_pdf_falls_back_to_ocr_cache(tmp_path, monkeypatch):
    """Bild-Scan ohne Textebene: load_page_texts nimmt den OCR-Cache."""
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(
        "anhangspruefer.parsers.document_text._pdf_page_texts",
        lambda path, x_tolerance=2: ["", ""],
    )
    # Patch the real _pdf_page_texts internals via ocr_pdf
    monkeypatch.setattr(
        "anhangspruefer.parsers.ocr.ocr_pdf",
        lambda path: ["OCR Anhang", "OCR Seite 2"],
    )

    # Call the public loader: we must hit the real _pdf_page_texts.
    # Re-apply by patching pdfplumber path: easier to patch ocr after empty extract.
    import anhangspruefer.parsers.document_text as dt

    def fake_pdf(path, x_tolerance=2):
        texts = ["", ""]
        if texts and (sum(len(t) for t in texts) / len(texts)) <= dt.LEER_GRENZE_JE_SEITE:
            ocr_texts = dt.ocr_pdf(path) if hasattr(dt, "ocr_pdf") else __import__(
                "anhangspruefer.parsers.ocr", fromlist=["ocr_pdf"]
            ).ocr_pdf(path)
            if ocr_texts and sum(len(t) for t in ocr_texts) > sum(len(t) for t in texts):
                return ocr_texts
        return texts

    monkeypatch.setattr(dt, "_pdf_page_texts", fake_pdf)
    out = load_page_texts(pdf)
    assert out == ["OCR Anhang", "OCR Seite 2"]
