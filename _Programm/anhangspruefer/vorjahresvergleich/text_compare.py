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
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from ..parsers.document_text import load_page_texts
from .extractor import anhang_page_range


# Ähnlichkeitsschwelle: bestes Match < Schwelle  =>  Segment gilt als NEU
NEW_THRESHOLD = 0.80

# Ähnlichkeit, ab der zwei Absätze als "derselbe" Absatz gelten (sonst NEU/FEHLT).
# Die Paarung erfolgt nach bester Ähnlichkeit statt strikt nach Reihenfolge, damit
# umgestellte/anders aufgeteilte Absätze korrekt zugeordnet werden.
PARA_MATCH_THRESHOLD = 0.60

# Ähnlichkeit, ab der ein gepaarter Absatz trotz OCR-Rauschen (verwürfelte
# Wortreihenfolge, Satzzeichen-Fehllesungen, vereinzelte Zeichenfehler) noch
# als IDENT gilt statt als GEÄNDERT. Ein reiner Wortlaut-Vergleich (exakte
# Gleichheit) würde bei einem Scan-Vorjahr praktisch nie zutreffen.
IDENT_THRESHOLD = 0.90

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
    t = re.sub(r"([a-zäöüß])\s*-\s+([a-zäöüß])", r"\1\2", t)
    t = t.replace(";", " ")
    t = re.sub(r"[^a-zäöüß ]+", " ", t)                # Satzzeichen etc. raus
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _is_narrative(segment: str) -> bool:
    """True, wenn das Segment erzählender Text ist (keine Tabellen-/Zahlenzeile)."""
    s = segment.strip()
    if len(s) < MIN_SEGMENT_CHARS:
        return False
    # Tabellen-Restzeilen aus dem PDF sicher aussortieren: ein Währungszeichen
    # '€' oder mehrere formatierte Beträge (x.xxx,xx) sind Tabelleninhalt, kein
    # Fließtext. Diese Zahlen prüft der Zahlenvergleich – im Textvergleich
    # würden sie sonst als "neue/fehlende Textteile" erscheinen.
    if "€" in s:
        return False
    if len(re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", s)) >= 3:
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


def _similarity(x: str, y: str) -> float:
    """Ähnlichkeit zweier normalisierter Absatztexte (0..1).

    Kombiniert zwei Maße und verwendet jeweils das bessere:
      * Zeichen-Ähnlichkeit (SequenceMatcher) – erkennt Tippfehler und
        einzelne OCR-Zeichenfehler bei sonst gleicher Wortreihenfolge.
      * Wortmengen-Ähnlichkeit (Sørensen-Dice über Wort-Vielfachmengen) –
        bleibt hoch, wenn OCR die Wortreihenfolge durch Spaltenfehler
        verwürfelt hat (dieselben Wörter, andere Reihenfolge), obwohl die
        Zeichenkette dadurch stark von der Vorlage abweicht.
    Ein wirklich neuer/fehlender Absatz hat in beiden Maßen einen niedrigen
    Wert, da weder die Zeichenfolge noch die Wörter übereinstimmen.
    """
    if not x or not y:
        return 0.0
    char_ratio = SequenceMatcher(None, x, y, autojunk=False).ratio()
    wx, wy = Counter(x.split()), Counter(y.split())
    total = sum(wx.values()) + sum(wy.values())
    if total == 0:
        return char_ratio
    overlap = sum((wx & wy).values())
    word_ratio = 2 * overlap / total
    return max(char_ratio, word_ratio)


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
    for page_num, text in enumerate(load_page_texts(pdf_path, include_tables=False), start=1):
        for seg in _segments_from_text(text):
            if _is_narrative(seg):
                out.append((seg, page_num))
    return out


# ---------------------------------------------------------------------------
# Absatz-Extraktion (Textteile = Absätze)
# ---------------------------------------------------------------------------
_HEADING_RE = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+(?P<rest>\S.*)$")

# Häufige finite Verbformen (Hilfs-/Modalverben in Passiv-/Aktivsätzen).
# Eine kurze Zeile MIT einem dieser Wörter ist Teil eines Satzes (Fließtext),
# keine Absatz-Überschrift. Bewusst allgemein gehalten (Grammatik, nicht
# mandantenspezifischer Wortschatz), damit die Erkennung für jeden Anhang
# funktioniert.
_FINITE_VERB_WORDS = frozenset({
    "wurde", "wurden", "wird", "werden", "ist", "sind", "war", "waren",
    "hat", "haben", "hatte", "hatten", "kann", "können", "konnte", "konnten",
    "muss", "müssen", "musste", "mussten", "soll", "sollen", "sollte",
    "sollten", "darf", "dürfen", "durfte", "durften", "gilt", "gelten",
    "galt", "enthält", "enthalten", "erfolgt", "erfolgen", "betrifft",
    "besteht", "bestehen", "bestand", "unterliegt", "unterliegen",
})


def _looks_like_title_line(s: str) -> bool:
    """Strukturelle Erkennung einer Absatz-Überschrift ohne Wortlaut-Liste.

    Eine Überschrift wie "Sachanlagen", "Sonstige Angaben" oder
    "Rückstellungen für Jubiläumsgelder" ist eine kurze, in sich
    abgeschlossene Zeile OHNE Satzendezeichen, OHNE Ziffern und OHNE finites
    Verb – im Unterschied zu einer (ggf. umgebrochenen) Fließtextzeile.
    """
    if not s or s[-1] in ".,;:!?":
        return False
    if re.search(r"\d", s):
        return False
    words = s.split()
    if not (1 <= len(words) <= 8):
        return False
    # Einzelne verirrte Großbuchstaben (z.B. Wasserzeichen-Reste, die als
    # eigene Zeile extrahiert werden) sind KEINE Überschrift – eine echte
    # Überschrift hat immer mehrere Buchstaben.
    letters = re.sub(r"[^A-Za-zÄÖÜäöüß]", "", s)
    if len(letters) < 4:
        return False
    if not s[0].isupper():
        return False
    low_words = {w.strip("-,.:;()").lower() for w in words}
    if low_words & _FINITE_VERB_WORDS:
        return False
    return True


def _is_heading(line: str) -> bool:
    s = line.strip()
    m = _HEADING_RE.match(s)
    if m:
        # "1. Allgemeines" ist eine Überschrift, "222 bis 234, 236 bis 240,
        # ..." (Fortsetzung einer Paragraphen-Aufzählung im Fließtext) NICHT
        # – entscheidend ist, ob der Rest der Zeile selbst wie ein Titel
        # aussieht (kurz, kein weiteres Satzzeichen/Ziffer, kein Verb).
        if _looks_like_title_line(m.group("rest")):
            return True
    letters = re.sub(r"[^A-Za-zÄÖÜäöüß]", "", s)
    if len(letters) >= 4 and letters == letters.upper() and len(s.split()) <= 6:
        return True
    return _looks_like_title_line(s)


def _is_noise_line(line: str) -> bool:
    """Reines Extraktions-Rauschen: gehört nicht zum Anhangtext, unterbricht
    aber (anders als eine Überschrift) NICHT den laufenden Absatz – die
    Zeile wird einfach übersprungen.

    Zwei generische Fälle:
      * ein einzelner Großbuchstabe auf eigener Zeile – typisch für ein
        diagonales Wasserzeichen, dessen Buchstaben pdfplumber je nach
        Kreuzungspunkt mit einer Textzeile als eigenes Segment ausliest;
        eine echte Textzeile besteht nie aus nur einem Buchstaben.
      * eine Unterschriften-Punktlinie ("....... ......."), wie sie am Ende
        von Anhängen üblich ist – kein inhaltlicher Text.
    """
    s = line.strip()
    if not s:
        return False
    if len(s) == 1 and s.isalpha() and s.isupper():
        return True
    compact = s.replace(" ", "")
    if len(compact) >= 10 and compact.count(".") / len(compact) > 0.8:
        return True
    return False


def _is_number_row(line: str) -> bool:
    """Zahlen-/Tabellenzeile (trennt Absätze, gehört nicht zum Fließtext)."""
    letters = sum(c.isalpha() for c in line)
    digits = sum(c.isdigit() for c in line)
    return digits > 0 and digits > letters


# Tabellen-Kopf-/Spaltenzeilen (Text ohne Satzcharakter). Sie brechen einen
# Absatz und werden NICHT in den Fließtext übernommen, damit Tabellenköpfe aus
# dem PDF nicht an echte Absätze "ankleben" und dadurch Scheinänderungen
# (GEÄNDERT/FEHLT) gegen den Word-Anhang erzeugen (dessen Tabellen bereits
# ausgeschlossen sind).
_TABLE_HEADER_RE = re.compile(
    r"^\s*(stand\b|aktiv\b|passiv\b|bewegung\b|nutzungsdauer\b|verwendung\b|"
    r"aufl[öo]sung\b|zuweisung\b|verbrauch\b|abgang\b|zugang\b|restlaufzeit\b|"
    r"betrag des\b|st[üu]ckzahl\b|nennbetr|aktiengattung\b|buchwert\b|"
    r"anschaffungs|31\.12\.\d|01\.01\.\d|€|eur\s+eur\b)",
    re.I,
)


def _is_table_header_line(line: str) -> bool:
    """True für reine Tabellen-Kopf-/Spaltenzeilen (kein Fließtext)."""
    return bool(_TABLE_HEADER_RE.match(line.strip()))


def _is_table_only_page(text: str) -> bool:
    """True, wenn eine Seite überwiegend aus Tabellenzeilen besteht.

    Die grobe Anhang-Seitenerkennung (anhang_page_range) markiert bei
    manchen Layouts eine angehängte Beilage (z.B. Anlagenspiegel direkt nach
    dem Anhangtext) noch als Anhang-Seite. Eine solche Seite ist aber KEIN
    erzählender Absatztext, sondern eine Zahlentabelle (die prüft der
    Zahlenvergleich) – und bei unterschiedlicher OCR-Lesbarkeit zwischen den
    Jahren würde sie sonst als Scheinunterschied ("Tabelle nur heuer
    lesbar") im Textvergleich auftauchen. Erkennung rein strukturell über
    den Anteil an Zahlen-/Tabellenkopfzeilen – keine Layout-Annahme über ein
    bestimmtes Dokument.
    """
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if len(lines) < 4:
        return False
    table_like = sum(
        1 for ln in lines if _is_number_row(ln) or _is_table_header_line(ln)
    )
    return table_like / len(lines) > 0.5


def _extract_paragraphs(pdf_path: Path) -> list[tuple[str, int]]:
    """Liefert (Absatztext, Seite) für alle erzählenden Absätze."""
    out: list[tuple[str, int]] = []
    pdf_path = Path(pdf_path)
    page_texts = load_page_texts(pdf_path, include_tables=False)
    start, end = anhang_page_range(page_texts)
    for page_num in range(start + 1, end + 1):    # nur Anhang-Seiten
        text = page_texts[page_num - 1]
        if _is_table_only_page(text):
            continue                              # angehängte Zahlentabelle
        buf: list[str] = []

        def flush() -> None:
            if buf:
                para = re.sub(r"\s+", " ", " ".join(buf)).strip()
                if _is_narrative(para):
                    out.append((para, page_num))
                buf.clear()

        for raw in text.split("\n"):
            ln = raw.strip()
            if not ln:
                flush()
                continue
            if _is_noise_line(ln):
                continue                          # Rauschen: Absatz läuft weiter
            if _is_heading(ln) or _is_number_row(ln) or _is_table_header_line(ln):
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
    page_texts = load_page_texts(pdf_path)
    start, end = anhang_page_range(page_texts)
    full = " ".join(page_texts[start:end]).lower()
    return [name for name, pat in _TABLE_SIGNATURES if pat.search(full)]


# ---------------------------------------------------------------------------
# Gegenüberstellung aktuell ↔ Vorjahr (Absätze + Tabellen-Anmerkungen)
# ---------------------------------------------------------------------------
def _coverage(frag: str, pool: list[str]) -> float:
    """Höchster Deckungsgrad von 'frag' in einem der Absätze aus 'pool' (0..1).

    Deckungsgrad = übereinstimmende Zeichen ODER Wörter / Umfang von 'frag'
    (das jeweils bessere Maß zählt – siehe _similarity). Erfasst den Fall,
    dass ein Absatz auf der Gegenseite nur ANDERS AUFGETEILT oder durch
    OCR-Spaltenfehler umsortiert ist (er steckt inhaltlich vollständig in
    einem längeren/anders geordneten Absatz).
    """
    if not frag:
        return 1.0
    frag_words = Counter(frag.split())
    frag_word_total = sum(frag_words.values())
    best = 0.0
    for other in pool:
        if not other:
            continue
        sm = SequenceMatcher(None, frag, other, autojunk=False)
        char_cov = sum(bl.size for bl in sm.get_matching_blocks()) / len(frag)
        word_cov = 0.0
        if frag_word_total:
            other_words = Counter(other.split())
            word_cov = sum((frag_words & other_words).values()) / frag_word_total
        cov = max(char_cov, word_cov)
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
            r = _similarity(a[i], b[j])
            if r >= PARA_MATCH_THRESHOLD:
                pairs.append((r, i, j))
    pairs.sort(key=lambda x: x[0], reverse=True)

    match_of: dict[int, tuple[int, float]] = {}
    used_prior: set[int] = set()
    for r, i, j in pairs:
        if i in match_of or j in used_prior:
            continue
        match_of[i] = (j, r)
        used_prior.add(j)

    rows: list[TextRow] = []
    for i, (ct, cp) in enumerate(cur):           # in Reihenfolge des aktuellen Anhangs
        m = match_of.get(i)
        if m is not None:
            j, r = m
            pt, pp = pri[j]
            # OCR-Rauschen (verwürfelte Wortreihenfolge, Satzzeichen-
            # Fehllesungen) soll NICHT als Wortlautänderung erscheinen –
            # daher Ähnlichkeitsschwelle statt exakter Gleichheit.
            status = "IDENT" if r >= IDENT_THRESHOLD else "GEÄNDERT"
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
    return sort_text_rows(rows)


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


_TEXT_STATUS_ORDER = {"FEHLT": 0, "GEÄNDERT": 1, "NEU": 2, "IDENT": 3}


def sort_text_rows(rows: list[TextRow]) -> list[TextRow]:
    """Änderungen und Lücken zuerst, identische Absätze zuletzt."""
    return sorted(rows, key=lambda r: (_TEXT_STATUS_ORDER.get(r.status, 9), r.page_current or 99))


def find_new_text_blocks(current_pdf: Path, prior_pdf: Path) -> list[NewTextBlock]:
    """Rückwärtskompatibel: nur die neu hinzugekommenen Absätze."""
    return [
        NewTextBlock(text=r.current, page=r.page_current or 0, best_score=0.0)
        for r in align_texts(current_pdf, prior_pdf)
        if r.status == "NEU"
    ]
