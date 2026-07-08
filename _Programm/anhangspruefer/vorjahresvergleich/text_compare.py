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
from typing import Optional

import pdfplumber

from .extractor import anhang_page_range


# Ähnlichkeitsschwelle: bestes Match < Schwelle  =>  Segment gilt als NEU
NEW_THRESHOLD = 0.80

# Ähnlichkeit, ab der zwei Absätze als "derselbe" Absatz gelten (sonst NEU/FEHLT).
# Die Paarung erfolgt nach bester Ähnlichkeit statt strikt nach Reihenfolge, damit
# umgestellte/anders aufgeteilte Absätze korrekt zugeordnet werden.
PARA_MATCH_THRESHOLD = 0.55

# Deckungsgrad, ab dem ein unpaariger Absatz als "in der Gegenseite enthalten"
# gilt (nur anders aufgeteilt) und daher NICHT als NEU/FEHLT ausgewiesen wird.
PARA_CONTAIN_THRESHOLD = 0.75

# Mindestlänge eines erzählenden Segments (Zeichen), um Rauschen zu vermeiden
MIN_SEGMENT_CHARS = 30
MIN_SEGMENT_WORDS = 5


@dataclass
class TextRow:
    """Eine Zeile der Text-Gegenüberstellung aktuell ↔ Vorjahr."""
    current: str               # Textteil im aktuellen Anhang ("" = fehlt)
    prior: str                 # Textteil im Vorjahres-Anhang ("" = neu)
    status: str                # IDENT / GEÄNDERT / NEU / FEHLT
    page_current: Optional[int]
    page_prior: Optional[int]


# Rückwärtskompatibilität (früherer Datentyp)
@dataclass
class NewTextBlock:
    text: str
    page: int
    best_score: float


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
    words = s.split()
    if len(words) < MIN_SEGMENT_WORDS:
        return False
    # Tabellen-/Kopfzeilen-Fragmente ausschließen:
    low = [w.lower() for w in words]
    # (a) zu wenige verschiedene Wörter -> Wiederholungen wie "EUR EUR EUR" /
    #     "davon davon davon" / "Gesamtbetrag davon davon …"
    if len(set(low)) / len(low) < 0.5:
        return False
    # (b) typische Tabellen-Kopfbegriffe
    if re.search(r"anschaffungs-?/?herstellungskosten|kumulierte abschreibung|"
                 r"gesamtbetrag davon|per \d", s, re.I):
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


# ---------------------------------------------------------------------------
# Absatz-Extraktion (Textteile = Absätze)
# ---------------------------------------------------------------------------
_HEADING_RE = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s")


def _is_heading(line: str) -> bool:
    s = line.strip()
    if _HEADING_RE.match(s):
        return True
    letters = re.sub(r"[^A-Za-zÄÖÜäöüß]", "", s)
    if len(letters) >= 4 and letters == letters.upper() and len(s.split()) <= 6:
        return True
    return False


def _is_number_row(line: str) -> bool:
    """Zahlen-/Tabellenzeile (trennt Absätze, gehört nicht zum Fließtext)."""
    letters = sum(c.isalpha() for c in line)
    digits = sum(c.isdigit() for c in line)
    return digits > 0 and digits > letters


def _extract_paragraphs(pdf_path: Path) -> list[tuple[str, int]]:
    """Liefert (Absatztext, Seite) für alle erzählenden Absätze."""
    out: list[tuple[str, int]] = []
    pdf_path = Path(pdf_path)
    with pdfplumber.open(str(pdf_path)) as pdf:
        page_texts = [p.extract_text(x_tolerance=2) or "" for p in pdf.pages]
        start, end = anhang_page_range(page_texts)
        for page_num in range(start + 1, end + 1):    # nur Anhang-Seiten
            text = page_texts[page_num - 1]
            buf: list[str] = []

            def flush() -> None:
                if buf:
                    para = re.sub(r"\s+", " ", " ".join(buf)).strip()
                    if _is_narrative(para):
                        out.append((para, page_num))
                    buf.clear()

            for raw in text.split("\n"):
                ln = raw.strip()
                if not ln or _is_heading(ln) or _is_number_row(ln):
                    flush()
                    continue
                buf.append(ln)
            flush()
    return out


# ---------------------------------------------------------------------------
# Tabellen-Erkennung (für die Vollständigkeit reicht "vorhanden")
# ---------------------------------------------------------------------------
# Wir prüfen den ANHANG: Tabellen werden NICHT Text-für-Text verglichen
# (die Zahlen prüft der Zahlenvergleich), sondern nur als "vorhanden" vermerkt.
_TABLE_SIGNATURES: list[tuple[str, "re.Pattern[str]"]] = [
    ("Anlagenspiegel", re.compile(r"anschaff.*buchwert|buchwert.*anschaff", re.S)),
    ("Rückstellungsspiegel", re.compile(r"r[uü]ckstellung.*(zuweisung|aufl[oö]sung|verwendung)", re.S)),
    ("Verbindlichkeitenspiegel", re.compile(r"verbindlichkeit.*restlaufzeit", re.S)),
    ("Forderungenspiegel", re.compile(r"forderung.*restlaufzeit", re.S)),
]


def _detect_tables(pdf_path: Path) -> list[str]:
    """Erkennt vorhandene Standard-Tabellen — nur im Anhang-Abschnitt."""
    with pdfplumber.open(str(Path(pdf_path))) as pdf:
        page_texts = [p.extract_text(x_tolerance=2) or "" for p in pdf.pages]
    start, end = anhang_page_range(page_texts)
    full = " ".join(page_texts[start:end]).lower()
    return [name for name, pat in _TABLE_SIGNATURES if pat.search(full)]


# ---------------------------------------------------------------------------
# Gegenüberstellung aktuell ↔ Vorjahr (Absätze + Tabellen-Anmerkungen)
# ---------------------------------------------------------------------------
def _coverage(frag: str, pool: list[str]) -> float:
    """Höchster Deckungsgrad von 'frag' in einem der Absätze aus 'pool' (0..1).

    Deckungsgrad = übereinstimmende Zeichen / Länge von 'frag'. Erfasst den
    Fall, dass ein Absatz auf der Gegenseite nur ANDERS AUFGETEILT ist (er
    steckt vollständig in einem längeren Absatz).
    """
    if not frag:
        return 1.0
    best = 0.0
    for other in pool:
        if not other:
            continue
        sm = SequenceMatcher(None, frag, other, autojunk=False)
        cov = sum(bl.size for bl in sm.get_matching_blocks()) / len(frag)
        if cov > best:
            best = cov
            if best >= PARA_CONTAIN_THRESHOLD:
                break
    return best


def _pair_paragraphs(cur: list[tuple[str, int]], pri: list[tuple[str, int]]) -> list[TextRow]:
    """Paart Absätze nach BESTER Ähnlichkeit (reihenfolge-unabhängig).

    Jeder Vorjahres-Absatz wird höchstens einmal verwendet (greedy, stärkste
    Paare zuerst). Umgestellte oder anders aufgeteilte Absätze werden dadurch
    korrekt zugeordnet. Ein unpaariger Absatz gilt nur dann als NEU/FEHLT, wenn
    sein Inhalt nicht ohnehin (anders aufgeteilt) in einem Absatz der Gegenseite
    enthalten ist. IDENT = Wortlaut gleich (Zahlen ausgeblendet), sonst GEÄNDERT.
    """
    a = [_normalize_for_match(t) for t, _ in cur]
    b = [_normalize_for_match(t) for t, _ in pri]

    pairs: list[tuple[float, int, int]] = []
    for i in range(len(a)):
        if not a[i]:
            continue
        for j in range(len(b)):
            if not b[j]:
                continue
            r = SequenceMatcher(None, a[i], b[j], autojunk=False).ratio()
            if r >= PARA_MATCH_THRESHOLD:
                pairs.append((r, i, j))
    pairs.sort(key=lambda x: x[0], reverse=True)

    match_of: dict[int, int] = {}
    used_prior: set[int] = set()
    for _r, i, j in pairs:
        if i in match_of or j in used_prior:
            continue
        match_of[i] = j
        used_prior.add(j)

    rows: list[TextRow] = []
    for i, (ct, cp) in enumerate(cur):           # in Reihenfolge des aktuellen Anhangs
        j = match_of.get(i)
        if j is not None:
            pt, pp = pri[j]
            status = "IDENT" if a[i] == b[j] else "GEÄNDERT"
            rows.append(TextRow(ct, pt, status, cp, pp))
        elif _coverage(a[i], b) < PARA_CONTAIN_THRESHOLD:
            rows.append(TextRow(ct, "", "NEU", cp, None))   # wirklich neuer Text
    for j, (pt, pp) in enumerate(pri):           # nicht gepaarte Vorjahres-Absätze
        if j not in used_prior and _coverage(b[j], a) < PARA_CONTAIN_THRESHOLD:
            rows.append(TextRow("", pt, "FEHLT", None, pp))  # echte Vollständigkeitslücke
    return rows


def align_texts(current_pdf: Path, prior_pdf: Path) -> list[TextRow]:
    """Stellt Absätze beider Anhänge gegenüber.

    Gleiche Absätze (Wortlaut identisch, Zahlen ausgeblendet) sind IDENT.
    Umgestellte Absätze werden über die Ähnlichkeit korrekt gepaart; echte
    Lücken zeigen NEU (nur aktuell) bzw. FEHLT (nur Vorjahr → Vollständigkeits-
    lücke). Tabellen erscheinen als Anmerkungszeile "<Tabelle> vorhanden".
    """
    rows: list[TextRow] = []

    # 1) Tabellen-Anmerkungen
    cur_tables = _detect_tables(current_pdf)
    pri_tables = _detect_tables(prior_pdf)
    order = list(dict.fromkeys(cur_tables + pri_tables))
    for name in order:
        inc, inp = name in cur_tables, name in pri_tables
        label = f"{name} vorhanden"
        if inc and inp:
            rows.append(TextRow(label, label, "IDENT", None, None))
        elif inc:
            rows.append(TextRow(label, "", "NEU", None, None))
        else:
            rows.append(TextRow("", label, "FEHLT", None, None))

    # 2) Absatz-Gegenüberstellung nach bester Ähnlichkeit (reihenfolge-unabhängig)
    rows += _pair_paragraphs(_extract_paragraphs(current_pdf),
                             _extract_paragraphs(prior_pdf))
    return rows


def diff_excerpt(current: str, prior: str, max_len: int = 400) -> str:
    """Kompakter Auszug der Wortunterschiede zwischen zwei Textteilen.

    Für die Spalte "Unterschied (Auszug)" im Textvergleich:
      * leer, wenn identisch,
      * Kurzhinweis bei nur-aktuell/nur-Vorjahr,
      * sonst die abweichenden Wortgruppen, getrennt nach Seite.
    Reine Satzzeichen-Fragmente (z.B. ein verirrter ".") werden ausgeblendet.
    """
    current = current or ""
    prior = prior or ""
    if current == prior:
        return ""
    if not prior:
        return "nur aktuell (neuer Textteil)"
    if not current:
        return "nur im Vorjahr (fehlt aktuell)"

    aw, bw = current.split(), prior.split()
    sm = SequenceMatcher(None, aw, bw, autojunk=False)
    only_cur: list[str] = []
    only_pri: list[str] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            frag = " ".join(aw[i1:i2]).strip()
            if frag and any(ch.isalnum() for ch in frag):
                only_cur.append(frag)
        if tag in ("replace", "insert"):
            frag = " ".join(bw[j1:j2]).strip()
            if frag and any(ch.isalnum() for ch in frag):
                only_pri.append(frag)

    parts: list[str] = []
    if only_cur:
        parts.append("aktuell: " + " / ".join(only_cur))
    if only_pri:
        parts.append("Vorjahr: " + " / ".join(only_pri))
    if not parts:
        return "nur geänderte Zahlen/Zeichen"
    return (" || ".join(parts))[:max_len]


def find_new_text_blocks(current_pdf: Path, prior_pdf: Path) -> list[NewTextBlock]:
    """Rückwärtskompatibel: nur die neu hinzugekommenen Absätze."""
    return [
        NewTextBlock(text=r.current, page=r.page_current or 0, best_score=0.0)
        for r in align_texts(current_pdf, prior_pdf)
        if r.status == "NEU"
    ]
