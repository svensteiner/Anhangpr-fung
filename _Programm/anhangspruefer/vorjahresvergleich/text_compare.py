"""
Textvergleich für den Vorjahresvergleich.

Ziel (ergänzend zum Zahlenvergleich):
  Erkennen, welche TEXTTEILE im aktuellen Anhang NEU hinzugekommen sind,
  d.h. im Vorjahres-Anhang inhaltlich nicht vorhanden waren. Diese werden
  als eigener Bereich ("Neue Textteile") ausgewiesen.

Vorgehen (rein lokal, keine externen Aufrufe):
  1. Beide PDFs seitenweise als Text einlesen (pdfplumber).
  2. In Sätze/Textsegmente zerlegen und auf erzählenden Text filtern
     (Tabellen-/Zahlenzeilen werden ausgeschlossen – die behandelt der
     Zahlenvergleich).
  3. Für den Vergleich werden Zahlen ausgeblendet, damit NICHT bloß
     geänderte Beträge als "neuer Text" erscheinen, sondern wirklich neue
     Formulierungen/Aussagen.
  4. Jedes Segment des aktuellen Anhangs, das im Vorjahres-Anhang keine
     ausreichend ähnliche Entsprechung hat, gilt als NEU.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import pdfplumber


# Ähnlichkeitsschwelle: bestes Match < Schwelle  =>  Segment gilt als NEU
NEW_THRESHOLD = 0.80

# Mindestlänge eines erzählenden Segments (Zeichen), um Rauschen zu vermeiden
MIN_SEGMENT_CHARS = 30
MIN_SEGMENT_WORDS = 5


@dataclass
class NewTextBlock:
    """Ein im aktuellen Anhang neu hinzugekommener Textteil."""
    text: str            # Originaltext des Segments
    page: int            # Seite im aktuellen Anhang
    best_score: float    # beste Ähnlichkeit zu einem Vorjahres-Segment (0..1)


def _normalize_for_match(text: str) -> str:
    """Normalisiert für den Ähnlichkeitsvergleich: Zahlen raus, klein, getrimmt.

    Zahlen/Beträge werden entfernt, damit eine inhaltlich gleiche Aussage mit
    nur geändertem Wert NICHT als neuer Text gilt.
    """
    t = text.lower()
    t = re.sub(r"[0-9]+(?:[.,][0-9]+)*", " ", t)      # Zahlen/Beträge entfernen
    t = re.sub(r"[^a-zäöüß ]+", " ", t)                # Satzzeichen etc. raus
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _is_narrative(segment: str) -> bool:
    """True, wenn das Segment erzählender Text ist (keine Tabellen-/Zahlenzeile)."""
    s = segment.strip()
    if len(s) < MIN_SEGMENT_CHARS:
        return False
    letters = sum(c.isalpha() for c in s)
    digits = sum(c.isdigit() for c in s)
    if letters == 0:
        return False
    # zu zahlenlastig -> Tabellenzeile
    if digits > 0 and digits / max(letters, 1) > 0.35:
        return False
    # Buchstabenanteil insgesamt ausreichend
    if letters / len(s) < 0.5:
        return False
    if len(s.split()) < MIN_SEGMENT_WORDS:
        return False
    return True


_SENT_SPLIT = re.compile(r"(?<=[.!?:;])\s+(?=[A-ZÄÖÜ0-9])")


def _segments_from_text(text: str) -> list[str]:
    """Zerlegt einen Seitentext in Satz-/Textsegmente."""
    # Zeilenumbrüche zu Leerzeichen, dann an Satzgrenzen trennen
    flat = re.sub(r"\s*\n\s*", " ", text)
    flat = re.sub(r"\s+", " ", flat).strip()
    if not flat:
        return []
    parts = _SENT_SPLIT.split(flat)
    return [p.strip() for p in parts if p.strip()]


def _extract_segments(pdf_path: Path) -> list[tuple[str, int]]:
    """Liefert (Segmenttext, Seitenzahl) für alle erzählenden Segmente."""
    out: list[tuple[str, int]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=2) or ""
            for seg in _segments_from_text(text):
                if _is_narrative(seg):
                    out.append((seg, page_num))
    return out


def find_new_text_blocks(current_pdf: Path, prior_pdf: Path) -> list[NewTextBlock]:
    """Findet Textteile, die im aktuellen Anhang neu gegenüber dem Vorjahr sind."""
    current_pdf = Path(current_pdf)
    prior_pdf = Path(prior_pdf)

    cur_segments = _extract_segments(current_pdf)
    prior_segments = _extract_segments(prior_pdf)

    # Normalisierte Vorjahres-Segmente vorbereiten
    prior_norm = [_normalize_for_match(s) for s, _ in prior_segments]
    prior_norm_set = set(prior_norm)

    new_blocks: list[NewTextBlock] = []
    seen_norm: set[str] = set()

    for seg, page in cur_segments:
        norm = _normalize_for_match(seg)
        if not norm or len(norm) < 12:
            continue
        if norm in seen_norm:
            continue  # Duplikate innerhalb des aktuellen Anhangs nur einmal
        # exakte Entsprechung im Vorjahr?
        if norm in prior_norm_set:
            continue
        # Fuzzy gegen alle Vorjahres-Segmente
        best = 0.0
        for pn in prior_norm:
            if not pn:
                continue
            # schneller Vorfilter: Längen grob ähnlich
            if abs(len(pn) - len(norm)) > max(len(norm), 1) * 0.6:
                continue
            score = SequenceMatcher(None, norm, pn).ratio()
            if score > best:
                best = score
                if best >= NEW_THRESHOLD:
                    break
        if best < NEW_THRESHOLD:
            seen_norm.add(norm)
            new_blocks.append(NewTextBlock(text=seg, page=page, best_score=round(best, 2)))

    return new_blocks
