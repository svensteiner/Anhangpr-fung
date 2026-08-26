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

from ..parsers.document_text import load_page_texts


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
# Währungs-Spaltenkopf: MINDESTENS zwei Einheiten nebeneinander ("EUR EUR",
# "TEUR TEUR", "EUR TEUR") = zwei Wertspalten (Berichtsjahr | Vorjahr).
# Ein einzelnes "EUR" ist KEIN Spaltenkopf und darf nicht so gewertet werden.
CURRENCY_PAIR_RE = re.compile(r"^\s*(?:(?:T?EUR|€)\s+){1,}(?:T?EUR|€)\s*$", re.I)
# Wort-Spaltenkopf ohne Jahreszahlen ("Geschäftsjahr Vorjahr", "Berichtsjahr
# Vorjahr"). Nur gültig, wenn die Zeile KEINE Zahl enthält – sonst wäre es ein
# Fließtext, der zufällig "Vorjahr" erwähnt.
HEADER_WORD_PAIR_RE = re.compile(
    r"^\s*(gesch(ä|ae)ftsjahr|berichtsjahr|laufendes\s+jahr|aktuelles\s+jahr)"
    r"[\s|]+vorjahr\s*$",
    re.I,
)
# Nachlaufende Einheiten-/Fußnotenmarker am Zeilenende (siehe unten).
_TRAILING_UNIT_RE = re.compile(r"(?:\s+(?:T?EUR|€|TSD|Mio\.?|Mrd\.?)|\s*\*+)+\s*$", re.I)

# Zeilen die wir komplett ignorieren (Kopf-/Fußzeilen, Spaltenköpfe ohne Daten)
NOISE_PATTERNS = [
    re.compile(r"^\s*$"),
    re.compile(r"^\s*Anhang\s*$", re.I),
    re.compile(r"^\s*Beilage\b", re.I),
    re.compile(r"^\s*(EUR\s*)+$", re.I),
    re.compile(r"^\s*(TEUR\s*)+$", re.I),
    re.compile(r"^\s*[A-Za-zÄÖÜäöüß]\s*$"),
    re.compile(r"^[\s\-_=•·\.]+$"),
]


def _is_noise(line: str, extra_noise=()) -> bool:
    """Rauschzeile? ``extra_noise`` liefert die Mandanten-Pipeline nach.

    Briefköpfe, Kanzleinamen und Aktenzeichen sind mandantenspezifisch und
    gehören deshalb NICHT in diese gemeinsame Liste, sondern in das jeweilige
    Mandanten-Plugin (``Pipeline.extra_noise_patterns``).
    """
    if any(p.match(line) for p in NOISE_PATTERNS):
        return True
    return any(p.search(line) for p in extra_noise)


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

        '2100 Grundanteil Whg Färbermühlgasse 13 6.708,65 6.708,65'
        -> ('2100 Grundanteil Whg Färbermühlgasse 13', [6708.65, 6708.65])
        (die Hausnummer "13" ist KEIN Betrag, siehe Regel unten)
    """
    # Nachlaufende Währungseinheiten/Fußnotenmarker abschneiden, sonst bricht
    # die Rückwärtssuche sofort ab und die Zeile liefert GAR KEINE Zahlen
    # ("Sonstige Rückstellungen 1.234,00 EUR" -> bisher 0 Werte).
    # BEWUSST NICHT getrimmt: nachgestelltes Minus (Nutzungsdauer-Erkennung der
    # Mandanten-Pipelines hängen daran) und "%" (Prozentsätze sind keine Beträge).
    line = _TRAILING_UNIT_RE.sub("", line)

    matches = list(NUMBER_RE.finditer(line))
    if not matches:
        return line.strip(), []

    nums: list[float] = []
    label_end = len(line)
    # Beträge in diesen Abschlüssen haben IMMER ein Dezimalkomma. Sobald wir
    # rückwärts eine Zahl MIT Komma eingesammelt haben, darf eine weitere
    # ganzzahlige Zahl OHNE Komma nicht mehr als Betrag gelten – das ist eine
    # im Bezeichnungstext stehende Zahl (Hausnummer, Kontonummer im Namen wie
    # "ERSTE BANK 8880 6201"), kein Wert. Zeilen OHNE jedes Komma (Nutzungsdauer
    # "3", Arbeitnehmerzahl "18") sind davon nicht betroffen, weil dort nie ein
    # Komma-Wert gesehen wurde.
    seen_decimal = False
    # rückwärts: nur kontinuierliche Zahlen am Ende einsammeln
    for m in reversed(matches):
        between = line[m.end():label_end]
        if between.strip() != "":
            break
        token = m.group()
        has_decimal = "," in token
        if not has_decimal and seen_decimal:
            break
        v = parse_german_number(token)
        if v is None:
            break
        if has_decimal:
            seen_decimal = True
        nums.insert(0, v)
        label_end = m.start()

    label = line[:label_end].rstrip(" \t.,;:")
    return label, nums


# ---------------------------------------------------------------------------
# OCR-Zahlartefakte reparieren (Fehler D)
# ---------------------------------------------------------------------------
# Der Bild-Scan-OCR des Vorjahres-Abschlusses liest Beträge gelegentlich
# falsch: Punkt statt Komma als Dezimaltrennzeichen ('7715.93'), Komma statt
# Punkt als Tausendertrennzeichen ('48,882,57'), doppelte/verrutschte
# Trennzeichen ('636,.72', '47.243,.80'), Leerzeichen nach dem Komma
# ('174.282, 24'). Wir reparieren NUR eindeutig erkennbare Muster.
#
# BEWUSST NICHT repariert: Fälle, in denen die OCR ein Minuszeichen als
# Ziffer gelesen hat (z.B. '2314.953,82' statt '-314.953,82', '4320.095,21'
# statt '-320.095,21'). Der erste Ziffernblock ist dort 4-stellig statt der
# sonst überall 1-3-stelligen Tausendergruppe – jede Korrektur wäre eine
# Vermutung ins Blaue. Solche Zahlen matchen keines der Muster unten, bleiben
# für NUMBER_RE unsichtbar und landen unverändert (unangetastet) im
# Labeltext – sie werden dadurch nie als falscher Betrag gemeldet
# (Präzision vor Vollständigkeit).
_OCR_DOUBLE_SEP_RE = re.compile(r"(?<=[.,])[.,]")
_OCR_SPACE_AFTER_COMMA_RE = re.compile(r",\s+(?=\d{2}\b)")
_OCR_COMMA_THOUSANDS_RE = re.compile(r"\b(\d{1,3}(?:,\d{3})+),(\d{2})\b")
_OCR_DOT_DECIMAL_RE = re.compile(r"\b(\d{3,})\.(\d{1,2})\b(?!,)")
# Leerzeichen statt Komma ("119.749 46" statt "119.749,46"). NUR wenn davor
# eine VOLLE Tausender-Dreiergruppe steht (fixe Lookbehind-Breite \d{3}) –
# das grenzt zuverlässig gegen Faelle wie "69 00 69 00" ab (dort stehen vor
# jedem Leerzeichen nie 3 zusammenhaengende Ziffern), wo Komma vs. eigen-
# staendige Ganzzahl nicht unterscheidbar waere und wir NICHT raten wollen.
# UND nur, wenn die zwei Nachkommastellen dort auch wirklich ENDEN (nicht
# selbst der Anfang einer laengeren, eigenstaendigen Zahl sind wie in
# "RAIBA 12018081 14.903,11" – dort waere "14" der Beginn von "14.903,11",
# keine Cent-Gruppe, sonst entsteht "12018081,14.903,11").
_OCR_SPACE_AS_COMMA_RE = re.compile(r"(?<=\d{3})\s(?=\d{2}(?![.,\d]))")
# Einzelner Großbuchstabe DIREKT (ohne Leerzeichen) vor einer Zahl geklebt
# ('F7.313,43' statt '7.313,43') – ein Extraktions-Artefakt, das auch im
# digitalen Berichtsjahres-PDF vorkommt (vermutlich eine überlagerte
# Korrektur-/Fußnotenmarkierung), nicht nur im OCR-Scan. NUMBER_RE lehnt
# 'F7.313,43' sonst komplett ab (Wortgrenze links verletzt), der Betrag geht
# spurlos verloren. Nur EIN isolierter Buchstabe direkt vor der Ziffer –
# echte Wortanfänge wie 'Anlage 5' bleiben unberührt (Leerzeichen davor).
_STRAY_LETTER_BEFORE_NUMBER_RE = re.compile(r"(?<!\S)[A-Z](?=\d)")


def _fix_ocr_number_artifacts(line: str) -> str:
    """Repariert erkennbare OCR-Zahlfehler VOR der eigentlichen Extraktion.

    Reihenfolge ist wichtig: erst doppelte/verrutschte Trennzeichen
    zusammenfassen und Leerraum nach dem Komma entfernen, danach die beiden
    Vertauschungsfälle auflösen (Komma als Tausender-, Punkt als
    Dezimaltrennzeichen). Wirkt auf ECHTEN Text (z.B. den digitalen
    Berichtsjahres-PDF) nicht, weil dort keines der Muster vorkommt – korrekt
    formatierte deutsche Beträge nutzen nie mehrere Kommas oder einen Punkt
    mit nur 1-2 Nachkommastellen.
    """
    s = line
    s = _STRAY_LETTER_BEFORE_NUMBER_RE.sub("", s)
    s = _OCR_DOUBLE_SEP_RE.sub("", s)
    s = _OCR_SPACE_AFTER_COMMA_RE.sub(",", s)
    s = _OCR_SPACE_AS_COMMA_RE.sub(",", s)
    s = _OCR_COMMA_THOUSANDS_RE.sub(
        lambda m: m.group(1).replace(",", ".") + "," + m.group(2), s
    )
    s = _OCR_DOT_DECIMAL_RE.sub(lambda m: m.group(1) + "," + m.group(2), s)
    return s


# ---------------------------------------------------------------------------
# Verklebte OCR-Zeilen auftrennen (Fehler C)
# ---------------------------------------------------------------------------
# Der Bild-Scan-OCR liefert manchmal zwei Bilanzzeilen ohne Zeilenumbruch
# hintereinander: '<Text> <Betrag> <Betrag> <Text> <Betrag> <Betrag>'. Wir
# suchen die Nahtstelle "zwei Beträge, dann ein großgeschriebenes Wort" und
# trennen dort NUR, wenn beide entstehenden Teile für sich genommen wie ein
# eigenständiger Posten aussehen (Label + eigene(r) Betrag/Beträge) –
# Präzision vor Vollständigkeit, sonst bleibt die Zeile unverändert.
_GLUE_BOUNDARY_RE = re.compile(
    r"""
    \d[\d.,]*\d                  # Betrag 1 (heuristisch, Feindetails übernimmt
    (?:\s+\d[\d.,]*\d)?          # split_label_and_trailing_numbers) optional Betrag 2
    \s+
    (?=[A-ZÄÖÜ][\wÄÖÜäöüß.\-]*(?:\s|$))   # Nahtstelle: neues, großgeschriebenes Wort
    """,
    re.VERBOSE,
)


def _split_glued_lines(line: str) -> list[str]:
    """Zerlegt eine verklebte OCR-Doppelzeile in ihre logischen Teilzeilen.

    Greift nur, wenn NACH der Trennstelle nachweislich wieder Text mit
    eigenem Betrag folgt und VOR der Trennstelle noch ein eigenes Label mit
    eigenem Betrag steht – sonst ist es kein Verklebungsfall, sondern
    normaler Text, der zufällig mit einem Großbuchstaben weitergeht (z.B.
    ein Firmenname), und die Zeile bleibt unangetastet.
    """
    m = _GLUE_BOUNDARY_RE.search(line)
    if not m:
        return [line]
    left, right = line[:m.end()], line[m.end():]
    if not left.strip() or not right.strip():
        return [line]
    left_label, left_nums = split_label_and_trailing_numbers(left)
    if not left_label.strip() or not left_nums:
        return [line]
    right_label, right_nums = split_label_and_trailing_numbers(right)
    if not right_label.strip() or not right_nums:
        return [line]
    return [left] + _split_glued_lines(right)


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


# Sachkonto-Nummer (4-5 Ziffern), der KEIN weiteres Zeichen vorausgeht (Wort-
# grenze links) und der Whitespace + entweder ein Buchstabe ODER eine weitere
# Gliederungsnummer mit Punkt ("3.", "12.") folgt (Wortanfang rechts). Der
# Gliederungsnummer-Fall greift, wenn die Kontonummer beim Label-Zusammenbau
# vor eine Gliederungsüberschrift gestellt wurde ("62000 3. Personalaufwand
# ... Gehälter" statt "3. Personalaufwand ... 62000 Gehälter"), siehe
# extract_items(). Wird in normalize_label() entfernt (siehe dort für die
# Begründung).
_KONTONUMMER_RE = re.compile(r"(?<!\S)\d{4,5}(?=\s+(?:[a-zäöüß]|\d+\.))")


def normalize_label(label: str) -> str:
    """Normalisiert ein Label für robustes Matching zwischen zwei PDFs."""
    s = label.lower().strip()
    s = (
        s.replace("ä", "ae")
         .replace("ö", "oe")
         .replace("ü", "ue")
         .replace("ß", "ss")
    )
    # Sachkonto-Nummer entfernen (4-5-stellig, gefolgt von einem Wortanfang).
    # Der aktuelle Abschluss enthält Kontonummern ('20500 Abgrenzungen
    # Forderungen'), der gescannte Vorjahres-Abschluss nicht ('Abgrenzungen
    # Forderungen') – ohne Entfernung matcht das nie. GILT AN BELIEBIGER
    # STELLE im Label, nicht nur am Anfang: Gliederungs-Zwischenzeilen wie
    # '1. Wertpapiere (Wertrechte) des Anlagevermögens 8310 Wertpapiere'
    # tragen die Kontonummer mitten im zusammengesetzten Label. Bewusst NICHT
    # 1-3-stellige Zahlen ("3 Monate", "18 Arbeitnehmer") und NICHT Zahlen
    # ohne folgenden Buchstaben ("2025 2024" – Jahreszahlen-Paare, da dort
    # keine Wortgrenze mit Buchstaben folgt).
    s = _KONTONUMMER_RE.sub("", s)
    # Aufzählungszeichen/Nummerierungen am Anfang weg – ITERATIV, damit auch
    # mehrstufige Gliederungen ("A.II.1. Sachanlagen", "1.2.3 Anlagevermögen")
    # vollständig entfernt werden. Ohne die Schleife bliebe ein Rest stehen und
    # kostete bei FUZZY_THRESHOLD=0.95 den Match.
    for _ in range(6):
        vorher = s
        # mehrstufige Nummer ohne abschließenden Punkt ("1.2.3 Anlagevermögen").
        # Verlangt mindestens eine Unterstufe, damit ein Label wie "3 Monate"
        # NICHT seine führende Zahl verliert.
        s = re.sub(r"^\d+(?:\.\d+)+[\.\)]?\s+", "", s)
        s = re.sub(r"^[\divxlcm]+[\.\)]\s*", "", s)
        s = re.sub(r"^[a-z][\.\)]\s*", "", s)
        s = re.sub(r"^[•·\-–—\*]\s*", "", s)
        if s == vorher:
            break
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Isolierte Einzelbuchstaben entfernen: der digitale Berichtsjahres-PDF
    # hat ein diagonales Wasserzeichen, dessen Buchstaben ("ENTWURF") beim
    # Textextrahieren einzeln zwischen echte Wörter rutschen ("Vorsorge für
    # Abfertigungen W", "Nachrichtenaufwand W Portogebühren"). Ohne Entfernung
    # verhindert dieser Zufallsbuchstabe den Match gegen das saubere
    # Vorjahres-Label. Ein einzelner Buchstabe ist in diesen Kontenbezeich-
    # nungen nie inhaltstragend.
    s = re.sub(r"\b[a-z]\b", " ", s)
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
# Anhang-Abschnitt eingrenzen
# ---------------------------------------------------------------------------
# Wir prüfen NUR den Anhang. In Prüfungsberichten steht davor/danach viel
# anderer Text (Prüfungsvertrag, Bestätigungsvermerk, Lagebericht, eine
# zweite Bilanz/GuV, Beilagen). Diese Bereiche werden anhand der Überschriften
# ausgeschlossen, damit Zahlen- und Textvergleich nur den Anhang erfassen.
def _is_anhang_start(line: str) -> bool:
    s = line.strip().lower()
    if s == "anhang":
        return True
    if re.match(r"^\d+\.\s*anhang$", s):
        return True
    if re.match(r"^anhang\s+(zum|f[üu]r|gem|nach|i\.\s*s)", s):
        return True
    return False


def _is_anhang_end(line: str) -> bool:
    s = line.strip().lower()
    if re.search(
        r"allgemeine\s+auftragsbedingungen|"
        r"auftragsbedingungen\s+f[uü]r\s+wirtschaftstreuhand",
        s,
    ):
        return True
    if len(s) > 45:
        return False
    return bool(re.match(
        r"^(lagebericht\b|bilanz\b|gewinn-?\s*und\s*verlust|best[äa]tigungsvermerk\b|"
        r"beilage\b|anlagenverzeichnis\b|entwicklung des anlageverm|anlage\s+\d)",
        s,
    ))


def anhang_page_range(page_texts: list[str]) -> tuple[int, int]:
    """(start, end) Seitenindizes des Anhang-Abschnitts; end exklusiv.

    Wird kein Anhang-Kopf erkannt, wird das ganze Dokument zurückgegeben.
    """
    start = None
    for i, t in enumerate(page_texts):
        if any(_is_anhang_start(ln) for ln in t.split("\n")):
            start = i
            break
    if start is None:
        return (0, len(page_texts))
    end = len(page_texts)
    for j in range(start + 1, len(page_texts)):
        if any(_is_anhang_end(ln) for ln in page_texts[j].split("\n")):
            end = j
            break
    return (start, end)


# ---------------------------------------------------------------------------
# Jahresabschluss-Kern (Bilanz + GuV + Anhang) für den Zahlenvergleich
# ---------------------------------------------------------------------------
# Modus 1 prüft die Vorjahreszahlen des ganzen Abschlusses, nicht nur des
# Anhangs. AAB gehören nicht dazu. Der Textvergleich bleibt bei
# ``anhang_page_range``.
_AAB_RE = re.compile(r"allgemeine\s+auftragsbedingungen", re.I)
_AAB_SHORT_RE = re.compile(r"(?m)^\s*AAB\b")
# Inhaltsverzeichnis-Zeilen sind kurz; der echte AAB-Text ist eine lange Seite.
_AAB_MIN_CHARS = 4000
_BILANZ_GUV_RE = re.compile(
    r"\baktiva\b|\bpassiva\b|gewinn-?\s*und\s*verlustrechnung",
    re.I,
)


def aab_page_index(page_texts: list[str]) -> int:
    """Erste Seite des AAB-Blocks (0-basiert); sonst Dokumentende.

    ``_is_anhang_end`` darf hier nicht verwendet werden: dort gilt schon
    ``Bilanz`` als Ende. Kurze Inhaltsverzeichnis-Zeilen zählen nicht.
    """
    for i, t in enumerate(page_texts):
        if len(t) < _AAB_MIN_CHARS:
            continue
        if (
            _AAB_RE.search(t)
            or _AAB_SHORT_RE.search(t)
            or re.search(r"auftragsbedingungen", t, re.I)
        ):
            return i
    return len(page_texts)


def ja_page_range(page_texts: list[str]) -> tuple[int, int]:
    """Seiten von Bilanz, GuV und Anhang bis vor die AAB.

    Startet am Dokumentanfang: Deckblatt/Inhaltsverzeichnis erzeugen kaum
    Posten (Rauschfilter), eine Bilanz-Suche würde TOC-Treffer riskieren.
    """
    return (0, aab_page_index(page_texts))


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------
_INLINE_VORJAHR_RE = re.compile(
    r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)"
    r"(?:\s+[A-Za-zÄÖÜäöüß%]+){0,4}\s*"
    r"\(\s*Vorjahr\s*:?\s*"
    r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)",
    re.I,
)


def _extract_inline_vorjahr(page_text: str, page: int) -> list:
    """Fliesstext-Paare 'X (Vorjahr: Y)' als Kontinuitaetsposten."""
    items = []
    flat = page_text.replace("\n", " ")
    for m in _INLINE_VORJAHR_RE.finditer(flat):
        cur = parse_german_number(m.group(1))
        pri = parse_german_number(m.group(2))
        if cur is None or pri is None:
            continue
        words = re.findall(r"[A-Za-zÄÖÜäöüß\-]{2,}", flat[:m.start()])
        label = " ".join(words[-6:]) or "Angabe (Vorjahr)"
        items.append(AnhangItem(
            label=label[:200],
            page=page,
            current_values=[cur],
            prior_values=[pri],
            source_lines=[m.group(0)],
        ))
    return items


def extract_items(pdf_path: Path,
                  page_range: Optional[tuple[int, Optional[int]]] = None,
                  extra_noise=(),
                  scope: str = "anhang") -> list[AnhangItem]:
    """
    Extrahiert vergleichbare Posten (Label + Werte) aus einem Abschluss.

    Args:
        pdf_path:   Dokument (PDF oder DOCX – über den Konnektor).
        page_range: Optionaler Seitenbereich (start, end) als 0-basierte
                    Indizes, end exklusiv. Ohne Angabe entscheidet ``scope``.
                    ``end=None`` liest bis zum Dokumentende – das ganze
                    Dokument ist also ``(0, None)``.
        extra_noise: Zusätzliche kompilierte Regexe für mandantenspezifische
                    Möblierung (Briefkopf, Kanzleiname, Aktenzeichen). Kommt
                    aus dem Mandanten-Plugin, nicht aus diesem Modul.
        scope:      Nur relevant ohne ``page_range``.
                    ``"anhang"`` = nur der Anhang-Abschnitt (Textvergleich,
                    interner Abgleich hinten).
                    ``"ja"`` = Bilanz, GuV und Anhang bis vor die AAB
                    (Vorjahres-Zahlenvergleich).

    Returns:
        Liste von AnhangItem in Lesereihenfolge. Jeder Eintrag enthält
        ein Label sowie die zugehörigen Berichtsjahres- und (sofern
        vorhanden) Vorjahreswerte.
    """
    items: list[AnhangItem] = []
    pdf_path = Path(pdf_path)

    page_texts = load_page_texts(pdf_path, x_tolerance=X_TOLERANCE)
    if page_range is not None:
        start, end = page_range
        # Der Bereich kommt vom Aufrufer und darf das Dokument überragen
        # (``end=None`` = bis zum Ende). Ohne diese Begrenzung greift die
        # Seitenschleife unten an ``page_texts`` vorbei -> IndexError, und der
        # Aufrufer verliert das Dokument stillschweigend.
        start = max(0, start)
        end = len(page_texts) if end is None else min(end, len(page_texts))
    elif scope == "ja":
        start, end = ja_page_range(page_texts)
    else:
        start, end = anhang_page_range(page_texts)
    # Spaltenkopf "GJ | VJ" gilt oft für Folgeseiten (Bilanz/GuV über mehrere
    # Blätter). Darum dokumentweit merken, nicht je Seite zurücksetzen.
    two_column_mode = False
    for page_index in range(start + 1, end + 1):   # 1-basierte Seitennummer
        text = page_texts[page_index - 1]
        raw_lines = [ln.rstrip() for ln in text.split("\n")]
        # Fehler D zuerst (OCR-Zahlartefakte reparieren), DANACH Fehler C
        # (verklebte Zeilen trennen) – die Trennstellen-Erkennung braucht
        # bereits reparierte Beträge, sonst bleiben z.B. Punkt-Dezimalzahlen
        # ('7715.93') für die Betragserkennung unsichtbar.
        raw_lines = [_fix_ocr_number_artifacts(ln) for ln in raw_lines]
        expanded_lines: list[str] = []
        for ln in raw_lines:
            expanded_lines.extend(_split_glued_lines(ln))
        raw_lines = expanded_lines

        # Nur der ANLAGENSPIEGEL hat echte Doppelzeilen-Posten (Stand 1.1.
        # über Stand 31.12., je 6 Spalten). Andere Spiegel (Rückstellungen,
        # Verbindlichkeiten) sind EINZEILIG. Die Doppelzeilen-Logik darf
        # daher nur auf Anlagenspiegel-Seiten feuern – erkennbar am Kopf
        # "Anschaffungs-/Herstellungskosten … Buchwert".
        _tl = text.lower()
        page_is_anlagenspiegel = ("buchwert" in _tl) and ("anschaff" in _tl)
        # Rueckstellungs-/Verbindlichkeitenspiegel: Stand | Bewegung | Stand.
        # Die Jahreszahlen in den Stand-Koepfen duerfen NICHT als
        # Zwei-Spalten-Modus (GJ|VJ) gelten – sonst zerlegt Modus 3b die
        # vier Bewegungsspalten in ein falsches Wertepaar.
        page_is_bewegungsspiegel = ("stand" in _tl) and any(
            w in _tl for w in (
                "zuweisung", "verwendung", "verbrauch",
                "aufloesung", "auflösung",
            )
        )
        if (
            not page_is_anlagenspiegel
            and not page_is_bewegungsspiegel
            and _BILANZ_GUV_RE.search(text)
        ):
            two_column_mode = True

        pending_label_parts: list[str] = []
        i = 0
        while i < len(raw_lines):
            line = raw_lines[i]

            # Währungs-Spaltenkopf ("EUR EUR" / "TEUR TEUR") ZUERST prüfen:
            # Er steht auch in NOISE_PATTERNS und würde sonst als Rauschen
            # verworfen – dann bliebe die Vorjahresspalte unerkannt und alle
            # Posten der Tabelle hätten keinen Eröffnungswert.
            if CURRENCY_PAIR_RE.match(line) or (
                HEADER_WORD_PAIR_RE.match(line) and not NUMBER_RE.search(line)
            ):
                two_column_mode = True
                pending_label_parts.clear()
                i += 1
                continue

            if _is_noise(line, extra_noise):
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
                # Führt label_part mit einer Kontonummer ein ('8310
                # Wertpapiere'), zieht die Kontonummer beim Zusammenbau ganz
                # nach vorne ('8310 1. Wertpapiere ... Wertpapiere') statt sie
                # mitten im kombinierten Label zu vergraben ('1. Wertpapiere
                # ... 8310 Wertpapiere'). Rein kosmetisch für Berichte/Debug –
                # normalize_label() entfernt die Kontonummer ohnehin an
                # beliebiger Stelle, das Match-Verhalten ändert sich nicht.
                _konto_m = re.match(r"^(\d{4,5})\s+(?=[A-Za-zÄÖÜäöüß])", label_part) if label_part else None
                if _konto_m:
                    konto = _konto_m.group(1)
                    rest = label_part[_konto_m.end():]
                    full_label = (
                        konto + " " + " ".join(pending_label_parts + ([rest] if rest else []))
                    ).strip()
                else:
                    full_label = " ".join(
                        pending_label_parts + ([label_part] if label_part else [])
                    ).strip()
            pending_label_parts.clear()

            if page_is_anlagenspiegel:
                full_label = re.sub(r"^\d{1,4}[\.\)]?\s+", "", full_label).strip()
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
            _wide_anlagenspiegel = page_is_anlagenspiegel and len(nums) >= 11
            if (not prior_values and not _two_col_table and page_is_anlagenspiegel
                    and not _wide_anlagenspiegel and i + 1 < len(raw_lines)):
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

            # Modus 3: Spaltenkopf "31.12.YYYY 31.12.YYYY" gesehen
            #          (oder Bilanz/GuV-Seite), keine Vorjahr-Zeile,
            #          genau 2 Zahlen -> [current, prior]
            if (
                not prior_values
                and two_column_mode
                and len(nums) == 2
                and not page_is_anlagenspiegel
                and not page_is_bewegungsspiegel
            ):
                current_values = [nums[0]]
                prior_values = [nums[1]]

            # Modus 3b: wie Modus 3, aber MEHR als 2 Zahlen (OCR-Verklebung
            # ohne trennenden Labeltext). Typischer Fall im Bild-Scan: der
            # letzte Posten einer Gruppe zieht die direkt anschließende
            # Zwischen-/Endsumme auf dieselbe Zeile ("... 152.508,49
            # 152.508,49 3.380.486,22 3.695.440,04" – die letzten beiden
            # Zahlen sind die Summenzeile, kein eigener Posten). Nur die
            # ERSTEN beiden Zahlen gehören zum Posten selbst; der Rest wird
            # verworfen statt geraten. Nicht im Anlagenspiegel (dort ist die
            # Wide-Zeile ein eigenes, bereits behandeltes Muster).
            elif (
                not prior_values
                and two_column_mode
                and len(nums) > 2
                and not page_is_anlagenspiegel
                and not page_is_bewegungsspiegel
            ):
                current_values = [nums[0]]
                prior_values = [nums[1]]

            if not prior_values and _wide_anlagenspiegel:
                # Die letzten beiden Spalten sind "Buchwert Stand 01.01." (=
                # Eröffnung, Vorjahr) und "Buchwert Stand 31.12." (= Schluss,
                # Berichtsjahr) – siehe Kopfzeile "... Buchwerte / Stand
                # 01.01.JJJJ / Stand 31.12.JJJJ". Reihenfolge daher [-2]=prior,
                # [-1]=current (NICHT vertauscht, siehe Regression unten).
                current_values = [nums[-1]]
                prior_values = [nums[-2]]

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

        items.extend(_extract_inline_vorjahr(text, page_index))

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
