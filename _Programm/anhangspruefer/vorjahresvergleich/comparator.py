"""
Vergleicher für die Vorjahreszahlen zwischen zwei Anhang-PDFs.

Eingabe:
  - aktueller Anhang (z.B. 2025): "Vorjahr"-Spalte/-Zeile enthält 2024-Werte
  - vorjähriger Anhang (z.B. 2024): Berichtsjahr-Werte sind die 2024-Werte

Ziel:
  Prüfen, ob die im 2025er Anhang ausgewiesenen 2024-Werte mit den im
  2024er Anhang ausgewiesenen 2024-Werten übereinstimmen.

Vorgehen (rein lokal, keine externen Aufrufe):
  1. Beide PDFs durch den extractor jagen → Listen von AnhangItem
  2. Labels normalisieren, exakter Schlüsselmatch + Fuzzy-Fallback
  3. Pro Label spaltenweise vergleichen:
        cur.prior_values[i]   vs   match.current_values[i]
  4. Status pro (Label, Spalte): OK / ABWEICHUNG / FEHLENDER_WERT
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from .extractor import (
    AnhangItem,
    anhang_page_range,
    compact_key,
    extract_items,
    normalize_label,
)
from .text_compare import TextRow, align_texts


# Schwelle für Fuzzy-Matching der Labels (0..1). Hoch angesetzt, damit nur
# praktisch identische Bezeichnungen matchen – verhindert Fehlmatches wie
# "Zuweisung Rückstellung …" ↔ "Rückstellung …".
FUZZY_THRESHOLD = 0.95


# Zeilen, die KEINE vergleichbaren Einzelposten sind und daher übersprungen
# werden: Summen/Zwischensummen sowie generische "davon …"-Aufgliederungen
# (nicht eindeutig ohne Oberposten -> würden falsch cross-matchen).
_SKIP_LABEL_RE = re.compile(
    r"^\s*(summe|zwischensumme|gesamtsumme|gesamt|davon\b)",
    re.I,
)

# Beteiligungslisten (Tochtergesellschaften): Firmennamen mit Rechtsform.
# Diese sind KEINE Kontinuitätspositionen — Eigenkapital/Ergebnis der Tochter
# ändern sich von Jahr zu Jahr legitim. Daher aus dem Zahlenvergleich nehmen.
_LEGAL_FORM_RE = re.compile(
    r"\b(gmbh|gesmbh|ges\.m\.b\.h|ag|kgaa|kg|og|se|s\.?r\.?l|s\.?r\.?o|"
    r"s\.?p\.?a|b\.?v|n\.?v|ltd|llc|inc|plc)\b",
    re.I,
)
# echte Positionen, die zwar einen Firmennamen enthalten, aber Bilanzposten
# sind (z.B. "Darlehen Muster Group GmbH") -> NICHT ausschließen
_POSITION_PREFIX_RE = re.compile(
    r"^\s*(darlehen|forderung|verbindlichkeit|r[uü]ckstellung|verrechnung|"
    r"ausleihung|anteile|beteiligung|guthaben|kredit)",
    re.I,
)


def _is_skippable(item: AnhangItem) -> bool:
    lab = item.label.strip()
    if _SKIP_LABEL_RE.match(lab):
        return True
    # reine Aufzählungs-Unterpunkte wie "a) übrige" / "b. übrige" sind
    # Aufgliederungen ohne eindeutige Bezeichnung
    if re.match(r"^[a-zA-Z][\.\)]\s+\S", lab) and len(item.label_key) <= 8:
        return True
    # Beteiligungs-/Firmennamen (aber keine echten Positionen wie "Darlehen …")
    if _LEGAL_FORM_RE.search(lab) and not _POSITION_PREFIX_RE.match(lab):
        return True
    return False

# Toleranz für Wertvergleich (absolut, EUR)
VALUE_TOLERANCE = 0.005


@dataclass
class ComparisonRow:
    """Eine Zeile im Vergleichsergebnis: ein Label, eine Spalte."""
    label: str
    column_index: int                       # 1..N
    value_in_current_anhang: Optional[float]   # Vorjahreswert aus 2025er PDF
    value_in_prior_anhang: Optional[float]     # Berichtsjahreswert aus 2024er PDF
    page_current: int
    page_prior: Optional[int]
    match_score: float                      # 1.0 = exakter Labelmatch
    status: str                             # OK / ABWEICHUNG / NUR_AKTUELL / NUR_VORJAHR / FEHLENDER_WERT
    label_prior_doc: Optional[str] = None   # tatsächliches Label im 2024er PDF (bei Fuzzy)

    # Aliase für Rückwärtskompatibilität mit dem alten Excel-Report
    @property
    def label_current_doc(self) -> str:
        return self.label

    @property
    def difference(self) -> Optional[float]:
        if self.value_in_current_anhang is None or self.value_in_prior_anhang is None:
            return None
        return self.value_in_current_anhang - self.value_in_prior_anhang


@dataclass
class CompareResult:
    """Gesamtergebnis eines Vorjahresvergleichs."""
    current_pdf: Path
    prior_pdf: Path
    rows: list[ComparisonRow] = field(default_factory=list)
    # Eigener Bereich: Text-Gegenüberstellung aktuell ↔ Vorjahr (Vollständigkeit)
    text_rows: list[TextRow] = field(default_factory=list)

    @property
    def stats(self) -> dict:
        counts = {
            "OK": 0, "ABWEICHUNG": 0,
            "NUR_AKTUELL": 0, "NUR_VORJAHR": 0,
            "FEHLENDER_WERT": 0,
        }
        labels: set[str] = set()
        for r in self.rows:
            counts[r.status] = counts.get(r.status, 0) + 1
            labels.add(normalize_label(r.label))
        counts["GESAMT"] = len(self.rows)
        counts["LABELS"] = len(labels)
        return counts


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def _values_match(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= VALUE_TOLERANCE


def _label_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# Mindestlänge eines Schlüssels, ab der die Volltext-Gegenprobe beweiskräftig
# ist. Kurze Schlüssel ("summe", "davon") kommen zufällig überall vor.
_GEGENPROBE_MIN_LEN = 10


def _anhang_compact_text(pdf_path: Path) -> str:
    """Anhang-Volltext des Dokuments als leerzeichenfreier Suchschlüssel.

    Dient als von der Posten-Extraktion UNABHÄNGIGE Gegenprobe: kommt eine
    Bezeichnung hier vor, ist der Posten im Dokument vorhanden – auch wenn der
    Extraktor ihn (z.B. mangels Wertespalte) nicht als Posten erfasst hat.
    """
    try:
        from ..parsers.document_text import load_page_texts

        pages = load_page_texts(pdf_path)
        start, end = anhang_page_range(pages)
        return compact_key(" ".join(pages[start:end]))
    except Exception:
        return ""


def _vorhanden_laut_volltext(label_key: str, other_text: str) -> bool:
    """True, wenn die Bezeichnung im Volltext der Gegenseite auftaucht."""
    if not other_text or len(label_key) < _GEGENPROBE_MIN_LEN:
        return False
    return label_key in other_text


def _index_by_normalized(items: list[AnhangItem]) -> dict[str, list[AnhangItem]]:
    out: dict[str, list[AnhangItem]] = {}
    for it in items:
        key = it.label_key_compact  # leerzeichen-unabhängig (verklebte Wörter)
        if not key:
            continue
        out.setdefault(key, []).append(it)
    return out


def _find_match(
    cur_key: str,
    prior_index: dict[str, list[AnhangItem]],
    target_value: Optional[float] = None,
) -> tuple[Optional[AnhangItem], float]:
    """Sucht im Index nach exaktem oder fuzzy Match.

    Kommen im Vorjahres-Anhang MEHRERE gleichnamige Posten vor (z.B. steht
    dieselbe 'Investitionsprämie …' unter mehreren Oberposten des Anlagen-
    spiegels), wird derjenige bevorzugt, dessen SCHLUSSwert dem gesuchten
    Eröffnungswert am nächsten liegt – das ist der echte Kontinuitätspartner.
    Ohne diese Präferenz würde stur der erste Treffer genommen und ein
    wertgleicher Posten fälschlich als Abweichung ausgewiesen.
    """
    if cur_key in prior_index:
        candidates = prior_index[cur_key]
        if len(candidates) > 1 and target_value is not None:
            def _value_distance(cand: AnhangItem) -> float:
                cv = closing_value(cand)
                return abs(cv - target_value) if cv is not None else float("inf")

            return min(candidates, key=_value_distance), 1.0
        return candidates[0], 1.0
    best: Optional[AnhangItem] = None
    best_score = 0.0
    for k, candidates in prior_index.items():
        s = _label_similarity(cur_key, k)
        if s > best_score:
            best_score = s
            best = candidates[0]
    if best is not None and best_score >= FUZZY_THRESHOLD:
        return best, best_score
    return None, 0.0


# ---------------------------------------------------------------------------
# Eröffnungs-/Schlusswert je Posten
# ---------------------------------------------------------------------------
# Fachregel (vom Prüfer vorgegeben):
#   In allen Spiegel-/Entwicklungstabellen muss der ERÖFFNUNGSwert im NEUEN
#   Bericht mit dem SCHLUSSwert im VORJAHRES-Bericht übereinstimmen
#   (Bilanzkontinuität). Je nach Tabellentyp ist das:
#     - Anlagenspiegel (Doppelzeile): BUCHWERT (letzte Spalte) –
#         Eröffnung = obere Zeile, Schluss = untere Zeile
#     - Rückstellungs-/Verbindlichkeitenspiegel (einzeilig, >=3 Spalten):
#         Eröffnung = "Stand" erste Spalte, Schluss = "Stand" letzte Spalte
#     - einfache Tabelle (Bezeichnung + Vorjahr): Eröffnung = Vorjahresspalte,
#         Schluss = Berichtsjahresspalte
def _is_single_row_spiegel(item: AnhangItem) -> bool:
    return (not item.double_row) and (not item.prior_values) and len(item.current_values) >= 3


def opening_value(item: AnhangItem) -> Optional[float]:
    """Wert am Periodenbeginn (muss = Vorjahres-Schlusswert sein)."""
    if item.double_row:                       # Anlagenspiegel: obere Zeile, Buchwert
        return item.prior_values[-1] if item.prior_values else None
    if _is_single_row_spiegel(item):          # Stand-Spiegel: erste Spalte
        return item.current_values[0]
    return item.prior_values[0] if item.prior_values else None   # einfach: Vorjahresspalte


def closing_value(item: AnhangItem) -> Optional[float]:
    """Wert am Periodenende."""
    if item.double_row:                       # Anlagenspiegel: untere Zeile, Buchwert
        return item.current_values[-1] if item.current_values else None
    if _is_single_row_spiegel(item):          # Stand-Spiegel: letzte Spalte
        return item.current_values[-1]
    return item.current_values[0] if item.current_values else None  # einfach: Berichtsjahr


# ---------------------------------------------------------------------------
# Hauptfunktion
# ---------------------------------------------------------------------------
def compare_anhaenge(current_pdf: Path, prior_pdf: Path, pipeline=None) -> CompareResult:
    """
    Vergleicht die Vorjahreszahlen zwischen zwei Anhang-PDFs.

    Args:
        current_pdf: Anhang des aktuellen Berichtsjahrs (z.B. Anhang 2025)
        prior_pdf:   Anhang des Vorjahrs (z.B. Anhang 2024)
        pipeline:    Dokumenten-Pipeline (mandantenspezifisch). None -> Standard.

    Returns:
        CompareResult mit einer Zeile pro (Label, Spalte). Labels die nur
        im Vorjahres-PDF vorkamen werden als zusätzliche Zeilen mit Status
        NUR_VORJAHR angehängt.
    """
    from ..pipelines import Pipeline
    pipeline = pipeline or Pipeline()

    current_pdf = Path(current_pdf)
    prior_pdf = Path(prior_pdf)

    cur_items = [it for it in pipeline.extract_anhang_items(current_pdf) if not _is_skippable(it)]
    prior_items = [it for it in pipeline.extract_anhang_items(prior_pdf) if not _is_skippable(it)]

    prior_index = _index_by_normalized(prior_items)
    matched_prior_keys: set[str] = set()
    rows: list[ComparisonRow] = []

    # Volltexte für die Gegenprobe (Präzision vor Vollständigkeit): eine
    # einseitige Meldung wird nur ausgegeben, wenn die Bezeichnung auf der
    # Gegenseite NACHWEISLICH fehlt.
    cur_text = _anhang_compact_text(current_pdf)
    pri_text = _anhang_compact_text(prior_pdf)

    for cur in cur_items:
        # Eröffnungswert im neuen Anhang = der Wert, der mit dem SCHLUSSwert
        # des Vorjahresberichts übereinstimmen muss (Bilanzkontinuität).
        new_open = opening_value(cur)
        if new_open is None:
            # Kein vergleichbarer Eröffnungswert -> keine Vergleichszeile.
            # ABER: Der Posten IST im aktuellen Anhang vorhanden. Sein
            # Vorjahres-Gegenstück darf deshalb NICHT als NUR_VORJAHR
            # ("fehlt heuer") gemeldet werden – das wäre eine Fehlmeldung.
            vorhanden, _s = _find_match(cur.label_key_compact, prior_index)
            if vorhanden is not None:
                matched_prior_keys.add(vorhanden.label_key_compact)
            continue

        match, score = _find_match(cur.label_key_compact, prior_index, new_open)

        if match is None:
            # Gegenprobe: steht die Bezeichnung im Vorjahres-Anhang doch im
            # Volltext, ist der Posten nicht "neu" – nur nicht gepaart.
            if _vorhanden_laut_volltext(cur.label_key_compact, pri_text):
                continue
            rows.append(
                ComparisonRow(
                    label=cur.label,
                    column_index=1,
                    value_in_current_anhang=new_open,
                    value_in_prior_anhang=None,
                    page_current=cur.page,
                    page_prior=None,
                    match_score=0.0,
                    status="NUR_AKTUELL",
                )
            )
            continue

        matched_prior_keys.add(match.label_key_compact)

        old_close = closing_value(match)
        if old_close is None:
            status = "FEHLENDER_WERT"
        elif _values_match(new_open, old_close):
            status = "OK"
        else:
            status = "ABWEICHUNG"

        rows.append(
            ComparisonRow(
                label=cur.label,
                column_index=1,
                value_in_current_anhang=new_open,   # Eröffnung neu (= Vorjahres-Schluss)
                value_in_prior_anhang=old_close,     # Schluss alt
                page_current=cur.page,
                page_prior=match.page,
                match_score=score,
                status=status,
                label_prior_doc=match.label if match.label != cur.label else None,
            )
        )

    # Zusatz-Zeilen für Posten, die nur im Vorjahres-PDF vorkommen.
    for it in prior_items:
        if it.label_key_compact in matched_prior_keys:
            continue
        old_close = closing_value(it)
        if old_close is None:
            continue
        # Gegenprobe: kommt die Bezeichnung im aktuellen Anhang im Volltext vor,
        # fehlt der Posten NICHT – er wurde nur nicht als Posten erfasst/gepaart.
        if _vorhanden_laut_volltext(it.label_key_compact, cur_text):
            continue
        rows.append(
            ComparisonRow(
                label=it.label,
                column_index=1,
                value_in_current_anhang=None,
                value_in_prior_anhang=old_close,
                page_current=0,
                page_prior=it.page,
                match_score=0.0,
                status="NUR_VORJAHR",
                label_prior_doc=it.label,
            )
        )

    # Duplikat-Unterdrückung: Ein Posten kann in mehreren Tabellen auftauchen
    # (z.B. Anlagenspiegel = Buchwert UND Anlagenverzeichnis = Anschaffungs-
    # kosten). Wenn dieselbe Bezeichnung an einer Stelle bereits OK ist, ist die
    # Kontinuität belegt -> eine widersprüchliche Abweichung desselben Labels
    # aus einer anderen Tabelle ist ein Artefakt und wird entfernt.
    ok_labels = {compact_key(r.label) for r in rows if r.status == "OK"}
    rows = [
        r for r in rows
        if not (r.status == "ABWEICHUNG" and compact_key(r.label) in ok_labels)
    ]

    # Textbereich: Gegenüberstellung aktuell ↔ Vorjahr (Vollständigkeit).
    # Optional – ein Fehler hier darf den Zahlenvergleich nicht kippen.
    try:
        text_rows = align_texts(current_pdf, prior_pdf)
    except Exception:
        text_rows = []

    return CompareResult(
        current_pdf=current_pdf,
        prior_pdf=prior_pdf,
        rows=rows,
        text_rows=text_rows,
    )
