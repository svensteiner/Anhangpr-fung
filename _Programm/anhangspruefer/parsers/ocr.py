"""
Lokale Texterkennung (OCR) fuer gescannte PDFs.

Datensicherheit: laeuft nur auf diesem Rechner, kein Netz, kein Cloud.
Cache: Sidecar ``*.ocr.json`` neben der Datei UND ein Hash-Cache unter
``Klienten/_ocr_cache/`` (gitignored). Dadurch greift die Erkennung auch
wenn dieselbe Datei per Upload in ein Temp-Verzeichnis kopiert wird —
der Demo-Klick in der App bleibt schnell.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional


CACHE_SUFFIX = ".ocr.json"
RENDER_ZOOM = 2.2


def cache_path(pdf_path) -> Path:
    p = Path(pdf_path)
    return p.with_name(p.stem + CACHE_SUFFIX)


def hash_cache_dir() -> Path:
    env = os.environ.get("ANHANGSPRUEFER_OCR_CACHE")
    p = Path(env) if env else (Path.cwd() / "Klienten" / "_ocr_cache")
    p.mkdir(parents=True, exist_ok=True)
    return p


def file_fingerprint(pdf_path) -> str:
    pdf_path = Path(pdf_path)
    h = hashlib.sha256()
    with pdf_path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return f"{pdf_path.stat().st_size}_{h.hexdigest()[:20]}"


def _read_payload(sidecar: Path, expected_size: Optional[int] = None) -> Optional[list[str]]:
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    texts = data.get("texts")
    if not isinstance(texts, list) or not texts:
        return None
    if not all(isinstance(t, str) for t in texts):
        return None
    size = data.get("source_size")
    if expected_size is not None and isinstance(size, int) and size > 0:
        if expected_size != size:
            return None
    return texts


def load_cache(pdf_path) -> Optional[list[str]]:
    pdf_path = Path(pdf_path)
    sidecar = cache_path(pdf_path)
    if sidecar.is_file():
        texts = _read_payload(sidecar, pdf_path.stat().st_size)
        if texts:
            _save_hash_cache(pdf_path, texts, "sidecar")
            return texts
    try:
        hashed = hash_cache_dir() / (file_fingerprint(pdf_path) + CACHE_SUFFIX)
    except OSError:
        return None
    if hashed.is_file():
        return _read_payload(hashed)
    return None


def _save_hash_cache(pdf_path: Path, texts: list[str], engine: str) -> None:
    try:
        dest = hash_cache_dir() / (file_fingerprint(pdf_path) + CACHE_SUFFIX)
        payload = {
            "source": pdf_path.name,
            "source_size": pdf_path.stat().st_size,
            "engine": engine,
            "pages": len(texts),
            "chars": sum(len(t) for t in texts),
            "texts": texts,
        }
        dest.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def save_cache(pdf_path, texts: list[str], engine: str) -> Path:
    pdf_path = Path(pdf_path)
    sidecar = cache_path(pdf_path)
    payload = {
        "source": pdf_path.name,
        "source_size": pdf_path.stat().st_size,
        "engine": engine,
        "pages": len(texts),
        "chars": sum(len(t) for t in texts),
        "texts": texts,
    }
    try:
        sidecar.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        sidecar = hash_cache_dir() / (file_fingerprint(pdf_path) + CACHE_SUFFIX)
        sidecar.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    _save_hash_cache(pdf_path, texts, engine)
    return sidecar


def _boxes_to_lines(raw) -> str:
    items = []
    for bbox, text, _conf in raw:
        if not text or not str(text).strip():
            continue
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        items.append((sum(ys) / len(ys), min(xs), str(text).strip()))
    if not items:
        return ""
    items.sort(key=lambda x: (round(x[0] / 18) * 18, x[1]))
    lines: list[str] = []
    cur_y = None
    buf: list[tuple[float, str]] = []
    for y, x, text in items:
        band = round(y / 18) * 18
        if cur_y is None or abs(band - cur_y) > 18:
            if buf:
                lines.append(" ".join(t for _, t in buf))
            buf = [(x, text)]
            cur_y = band
        else:
            buf.append((x, text))
    if buf:
        lines.append(" ".join(t for _, t in buf))
    return "\n".join(lines)


def ocr_pdf(pdf_path) -> list[str]:
    """Erkennt den Text eines Bild-PDFs lokal. Cache zuerst."""
    pdf_path = Path(pdf_path)
    cached = load_cache(pdf_path)
    if cached is not None:
        return cached

    try:
        import easyocr
        import fitz
        import numpy as np
    except ImportError:
        return []

    try:
        reader = easyocr.Reader(["de", "en"], gpu=False, verbose=False)
        doc = fitz.open(str(pdf_path))
        pages: list[str] = []
        matrix = fitz.Matrix(RENDER_ZOOM, RENDER_ZOOM)
        for i in range(doc.page_count):
            pix = doc[i].get_pixmap(matrix=matrix, alpha=False)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            raw = reader.readtext(img, detail=1, paragraph=False)
            pages.append(_boxes_to_lines(raw))
        doc.close()
    except Exception:
        return []

    if any(p.strip() for p in pages):
        try:
            save_cache(pdf_path, pages, "easyocr-de-en")
        except OSError:
            pass
    return pages
