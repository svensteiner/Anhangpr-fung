"""
Extraktor für Anhang-Posten (Label + Berichtsjahr-/Vorjahreswerte).

Strategie v3 — zeilenbasiert mit pdfplumber
===========================================
Anhänge zum Jahresabschluss folgen in Österreich/Deutschland fast immer dem
gleichen Tabellenmuster:

   Bezeichnung                       Wert(e) Berichtsjahr
   Vorjahr                           Wert(e) Vorjahr

oder mit expliziten Spaltenköpfen:

                                     31.12.2025      31.12.2024
   Bezeichnung                       Wert 2025       Wert 2024

Diese Heuristik nutzt pdfplumber.extract_text() — also den korrekt
linearisierten Seiteninhalt — und zerlegt jede Zeile in (Labelteil,
Liste trailing Zahlen). Mehrzeilige Labels (das Label steht auf einer
oder mehreren Textzeilen oberhalb der Wertezeile) werden zusammengefasst.

Modi pro Zeile:
  A) "Vorjahr"-Zeile direkt darunter   →  current_values aus Item-Zeile,
                                          prior_values aus Vorjahr-Zeile
  B) Header "31.12.YYYY 31.12.YYYY"    →  Item-Zeile hat current+prior nebeneinander
                                          (zwei Zahlen, [0]=current, [1]=prior)
  C) Sonst                              →  current_values nur, prior leer

Komplett lokal. Kein Netzwerk, kein LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pdfplumber


# Wort-Trennschärfe für pdfplumber. Standard (3) verklebt bei manchen PDFs
# (z.B. Prüfungsberichten ohne echte Space-Zeichen) die Wörter. 2 rekonstruiert
# die Wortgrenzen über die Zeichenabstände zuverlässig.
X_TOLERANCE = 2


# ---------------------------------------------------------------------------
# Zahlenerkennung (deutsches Format, optional Klammern für Negativwerte)
# ---------------------------------------------------------------------------
NUMBER_RE = re.compile(
    r"""
    (?<![\w.,-])                             # Wortgrenze links (inkl. Bindestrich → kein COVID-19)
    \(?-?                                    # ggf. ( oder -
    (?:
        \d{1,3}(?:\.\d{3})+(?:,\d+)?         # 1.234 / 1.234.567,89
        |
        \d+(?:,\d+)?                         # 12345 / 12345,67
    )
    \)?
    (?![\w.])                                # Wortgrenze rechts (kein weiterer Buchstabe/Punkt)
    """,
    re.VERBOSE,
)

# Header der typischerweise Wertspalten ankündigen
YEAR_PAIR_RE = re.compile(r"\b(20\d{2}|19\d{2})\b.*\b(20\d{2}|19\d{2})\b")
DATE_PAIR_RE = re.compile(r"31\.12\.(20\d{2}).*31\.12\.(20\d{2})")

# Zeilen die wir komplett ignorieren (Kopf-/Fußzeilen, Spaltenköpfe ohne Daten)
NOISE_PATTERNS = [
    re.compile(r"^\s*$"),
    re.compile(r"^\s*Anhang\s*$", re.I),
    re.compile(r"^\s*Beilage\b", re.I),
    re.compile(r"^\s*HAAI\b", re.I),
    re.compile(r"^\s*LANG\s*&\s*OBERMANN", re.I),
    re.compile(r"^\s*Steuerberatungsgesellschaft", re.I),
    re.compile(r"^\s*(EUR\s*)+$", re.I),
    re.compile(r"^\s*(TEUR\s*)+$", re.I),
    re.compile(r"^[\s\-_=•·\.]+$"),
]


def _is_noise(line: str) -> bool:
    return any(p.match(line) for p in NOISE_PATTERNS)


# ---------------------------------------------------------------------------
# Kernparser: Zeile -> (Label, Liste trailing Zahlen)
# ---------------------------------------------------------------------------
def parse_german_number(token: str) -> Optional[float]:
    """Wandelt '1.234.567,89' / '(1.234,00)' / '-42' in float um."""
    s = token.strip()
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    if s.startswith("-"):
        neg = True
        s = s[1:]
    s = s.replace(".", "").replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def split_label_and_trailing_numbers(line: str) -> tuple[str, list[float]]:
    """
    Zerlegt eine Zeile in Labeltext und alle Zahlen, die am Zeilenende
    durch reine Whitespace voneinander/vom Label getrennt stehen.

    Beispiele:
        'Software 2.634.705,31 664.581,01 2.006.736,92'
        -> ('Software', [2634705.31, 664581.01, 2006736.92])

        'Vorjahr 17.441,97 0,00 0,00 1.946,56 19.388,53'
        -> ('Vorjahr', [17441.97, 0.00, 0.00, 1946.56, 19388.53])

        'Erläuterungen zu einzelnen Posten von Bilanz und GuV'
        -> ('Erläuterungen zu einzelnen Posten von Bilanz und GuV', [])
    """
    matches = list(NUMBER_RE.finditer(line))
    if not matches:
        return line.strip(), []

    nums: list[float] = []
    label_end = len(line)
    # rückwärts: nur kontinuierliche Zahlen am Ende einsammeln
    for m in reversed(matches):
        between = line[m.end():label_end]
        if between.strip() != "":
            break
        v = parse_german_number(m.group())
        if v is None:
            break
        nums.insert(0, v)
        label_end = m.start()

    label = line[:label_end].rstrip(" \t.,;:")
    return label, nums


# ---------------------------------------------------------------------------
# Datenklasse für ein extrahiertes Anhang-Item
# ---------------------------------------------------------------------------
@dataclass
class AnhangItem:
    label: str
    page: int
    current_values: list[float]   # Berichtsjahres-Werte (Item-Zeile)
    prior_values: list[float]     # Vorjahreswerte (aus 'Vorjahr'-Zeile oder zweiter Spalte)
    source_lines: list[str] = field(default_factory=list, repr=False)
    double_row: bool = False      # True = Anlagespiegel-Doppelzeile (Modus 2)

    @property
    def label_key(self) -> str:
        return normalize_label(self.label)

    @property
    def label_key_compact(self) -> str:
        """Match-Schlüssel OHNE Leerzeichen.

        Manche PDFs (z.B. Prüfungsberichte) extrahieren Text mit verklebten
        Wörtern ('Rückstellungenfürsonstiges'), andere mit Leerzeichen
        ('Rückstellungen für sonstiges'). Durch Entfernen aller Leerzeichen
        matchen beide Schreibweisen zuverlässig.
        """
        return compact_key(self.label)


def compact_key(label: str) -> str:
    """Normalisierter Match-Schlüssel ohne jegliche Leerzeichen."""
    return normalize_label(label).replace(" ", "")


def normalize_label(label: str) -> str:
    """Normalisiert ein Label für robustes Matching zwischen zwei PDFs."""
    s = label.lower().strip()
    s = (
        s.replace("ä", "ae")
         .replace("ö", "oe")
         .replace("ü", "ue")
         .replace("ß", "ss")
    )
    # Aufzählungszeichen/Nummerierungen am Anfang weg
    s = re.sub(r"^[\divxlcm]+[\.\)]\s*", "", s)
    s = re.sub(r"^[a-z][\.\)]\s*", "", s)
    s = re.sub(r"^[•·\-–—\*]\s*", "", s)
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ---------------------------------------------------------------------------
# Filter für unbrauchbare Labels
# ---------------------------------------------------------------------------
LABEL_BLACKLIST = {
    "vorjahr", "summe", "eur", "teur", "anhang", "seite",
}

# Erkennt erzählerische Sätze (volle Sätze in Fließtext mit Zahlen am Ende)
NARRATIVE_HINTS = re.compile(
    r"\b(wurden|werden|wird|ist|sind|setzen sich|berücksichtigt|"
    r"betrug|betragen|erhalten|gemäß|entsprechen|enthält|enthalten|"
    r"umfassen|umfasst|laut|hat die Pflicht|tätig)\b",
    re.I,
)


# Sektionsüberschriften, die als Labelteil unbrauchbar sind
SECTION_HEADER_WORDS = {
    "anlagevermoegen", "umlaufvermoegen", "aktiva", "passiva",
    "rueckstellungen", "verbindlichkeiten", "eigenkapital",
    "immaterielle vermoegensgegenstaende", "sachanlagen", "finanzanlagen",
    "vermoegensgegenstaende", "bilanz", "gewinn und verlustrechnung",
    "guv", "anhang", "erlaeuterungen zur bilanz",
    "sonstige angaben", "haftungsverhaeltnisse",
    "steuerrueckstellungen", "sonstige rueckstellungen",
}


def _is_section_header(line: str) -> bool:
    """Erkennt typische Sektionsüberschriften (für die Item-Extraktion zu ignorieren)."""
    s = line.strip()
    if not s:
        return True
    norm = normalize_label(s)
    if norm in SECTION_HEADER_WORDS:
        return True
    # ALL CAPS mit mindestens 4 Buchstaben (z.B. ANLAGEVERMÖGEN, SUMME RÜCKSTELLUNGEN)
    letters = re.sub(r"[^A-Za-zÄÖÜäöüß]", "", s)
    if len(letters) >= 4 and letters == letters.upper():
        return True
    # Römische Nummerierung allein (z.B. "I.", "II.")
    if re.fullmatch(r"[IVXLC]+\.\s*", s):
        return True
    return False


def _is_meaningful_label(label: str) -> bool:
    if not label:
        return False
    norm = normalize_label(label)
    if not norm:
        return False
    if norm in LABEL_BLACKLIST:
        return False
    if not re.search(r"[a-zäöüß]", label, re.I):
        return False
    # Zu lange Labels deuten auf Fließtext hin
    if len(label.split()) > 12:
        return False
    if NARRATIVE_HINTS.search(label):
        return False
    return True


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------
def extract_items(pdf_path: Path) -> list[AnhangItem]:
    """
    Extrahiert alle Anhang-Posten aus einer PDF.

    Returns:
        Liste von AnhangItem in Lesereihenfolge. Jeder Eintrag enthält
        ein Label sowie die zugehörigen Berichtsjahres- und (sofern
        vorhanden) Vorjahreswerte.
    """
    items: list[AnhangItem] = []
    pdf_path = Path(pdf_path)

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=X_TOLERANCE) or ""
            raw_lines = [ln.rstrip() for ln in text.split("\n")]

            # Nur der ANLAGENSPIEGEL hat echte Doppelzeilen-Posten (Stand 1.1.
            # über Stand 31.12., je 6 Spalten). Andere Spiegel (Rückstellungen,
            # Verbindlichkeiten) sind EINZEILIG. Die Doppelzeilen-Logik darf
            # daher nur auf Anlagenspiegel-Seiten feuern – erkennbar am Kopf
            # "Anschaffungs-/Herstellungskosten … Buchwert".
            _tl = text.lower()
            page_is_anlagenspiegel = ("buchwert" in _tl) and ("anschaff" in _tl)

            # Modus: zwei Zahlen pro Item-Zeile = (current, prior)?
            two_column_mode = False

            pending_label_parts: list[str] = []
            i = 0
            while i < len(raw_lines):
                line = raw_lines[i]

                if _is_noise(line):
                    pending_label_parts.clear()
                    i += 1
                    continue

                # Spaltenkopf-Erkennung: Jahrespaar in der Zeile
                if DATE_PAIR_RE.search(line) or (
                    YEAR_PAIR_RE.search(line) and not NUMBER_RE.search(line.replace(YEAR_PAIR_RE.search(line).group(0), ""))
                ):
                    two_column_mode = True
                    pending_label_parts.clear()
                    i += 1
                    continue

                label_part, nums = split_label_and_trailing_numbers(line)

                if not nums:
                    # reine Textzeile -> als (Teil-)Label vormerken
                    if label_part:
                        if _is_section_header(label_part):
                            # Sektionsüberschrift: pending zurücksetzen, NICHT mitnehmen
                            pending_label_parts.clear()
                        else:
                            pending_label_parts.append(label_part)
                            # nur die letzten beiden Textzeilen behalten
                            pending_label_parts = pending_label_parts[-2:]
                    i += 1
                    continue

                # Wir haben Zahlen in der Zeile.
                # Regel: wenn die Item-Zeile selbst einen MEHRTEILIGEN Labeltext enthält
                # (>= 2 Wörter mit Buchstaben), nimm nur diesen — es ist ein eigenständiges Label.
                # Einzelne Wörter dagegen sind oft Fortführungen der vorherigen Zeile
                # (z.B. "...an verbundenen\nUnternehmen 60.000,...") → mit pending zusammenfassen.
                label_words = [w for w in label_part.split() if re.search(r"[a-zA-ZäöüÄÖÜß]", w)] if label_part else []
                if len(label_words) >= 2:
                    full_label = label_part.strip()
                else:
                    full_label = " ".join(
                        pending_label_parts + ([label_part] if label_part else [])
                    ).strip()
                pending_label_parts.clear()

                if not _is_meaningful_label(full_label):
                    i += 1
                    continue

                # Modus 1: explizite "Vorjahr"-Zeile darunter?
                prior_values: list[float] = []
                is_double_row: bool = False
                if i + 1 < len(raw_lines):
                    nxt = raw_lines[i + 1].strip()
                    if re.match(r"^vorjahr\b", nxt, re.I):
                        rest = re.sub(r"^vorjahr[\s\.:]*", "", nxt, flags=re.I)
                        _, prior_nums = split_label_and_trailing_numbers(rest)
                        if prior_nums:
                            prior_values = prior_nums
                            i += 1  # Vorjahr-Zeile konsumieren

                current_values = nums

                # Modus 2: Anlagespiegel-Doppelzeile.
                #   Direkt unter der Item-Zeile steht eine zweite reine
                #   Zahlenzeile (kein Label, kein "Vorjahr"-Keyword).
                #   Konvention im Anlagespiegel:
                #     Zeile 1 = 1.1.<Berichtsjahr>  (= Stand 31.12.Vorjahr)
                #     Zeile 2 = 31.12.<Berichtsjahr>
                #   Wir mappen auf prior/current, damit der Vergleich
                #   2025.prior  ==  2024.current  konsistent funktioniert.
                #
                #   WICHTIG: Wenn two_column_mode aktiv ist UND die Item-Zeile
                #   genau 2 Zahlen hat, handelt es sich um eine einfache
                #   Datum-Spalten-Tabelle (z.B. Investitionszuschüsse). In diesem
                #   Fall darf Modus 2 NICHT feuern, weil die nächste reine
                #   Zahlenzeile eine Summenzeile (keine zweite Datenzeile) ist.
                #   Anlagespiegel-Zeilen haben typischerweise >= 3 Zahlen.
                _two_col_table = two_column_mode and len(nums) == 2
                if not prior_values and not _two_col_table and page_is_anlagenspiegel and i + 1 < len(raw_lines):
                    nxt_line = raw_lines[i + 1]
                    nxt_label, nxt_nums = split_label_and_trailing_numbers(nxt_line)
                    only_numeric = bool(nxt_nums) and (
                        not nxt_label
                        or not re.search(r"[a-zA-ZäöüÄÖÜß]", nxt_label)
                    )
                    if only_numeric and len(nxt_nums) >= max(1, len(nums) - 2):
                        prior_values = nums          # 1.1. -> Stand Ende Vorjahr
                        current_values = nxt_nums    # 31.12. -> Stand Ende Berichtsjahr
                        is_double_row = True
                        i += 1  # zweite Zeile konsumieren

                # Modus 3: Spaltenkopf "31.12.YYYY 31.12.YYYY" gesehen,
                #          keine Vorjahr-Zeile, genau 2 Zahlen -> [current, prior]
                if (
                    not prior_values
                    and two_column_mode
                    and len(nums) == 2
                ):
                    current_values = [nums[0]]
                    prior_values = [nums[1]]

                items.append(
                    AnhangItem(
                        label=full_label[:200],
                        page=page_index,
                        current_values=current_values,
                        prior_values=prior_values,
                        source_lines=[line],
                        double_row=is_double_row,
                    )
                )
                i += 1

    return _deduplicate(items)


def _deduplicate(items: list[AnhangItem]) -> list[AnhangItem]:
    """Entfernt offensichtliche Doppelungen (gleiches Label + gleiche Werte)."""
    seen: set[tuple] = set()
    out: list[AnhangItem] = []
    for it in items:
        key = (
            it.label_key,
            tuple(round(v, 2) for v in it.current_values),
            tuple(round(v, 2) for v in it.prior_values),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


# ---------------------------------------------------------------------------
# Rückwärtskompatibilität: alter Funktionsname / Datentyp
# ---------------------------------------------------------------------------
@dataclass
class LabelValuePair:
    """Legacy-Datentyp – wird nur noch für Importe alter Aufrufer behalten."""
    label: str
    current: Optional[float]
    prior: Optional[float]
    page: int
    raw_line: str = ""

    @property
    def label_key(self) -> str:
        return normalize_label(self.label)


def extract_label_value_pairs(pdf_path: Path) -> list[LabelValuePair]:
    """Legacy-Wrapper: liefert die ersten Werte als (current, prior) Paare."""
    pairs: list[LabelValuePair] = []
    for it in extract_items(Path(pdf_path)):
        cur = it.current_values[0] if it.current_values else None
        pri = it.prior_values[0] if it.prior_values else None
        pairs.append(
            LabelValuePair(
                label=it.label, current=cur, prior=pri,
                page=it.page, raw_line=" / ".join(it.source_lines),
            )
        )
    return pairs
