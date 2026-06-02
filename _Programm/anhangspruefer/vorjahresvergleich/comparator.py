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

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from .extractor import AnhangItem, extract_items, normalize_label


# Schwelle für Fuzzy-Matching der Labels (0..1)
FUZZY_THRESHOLD = 0.88

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


def _index_by_normalized(items: list[AnhangItem]) -> dict[str, list[AnhangItem]]:
    out: dict[str, list[AnhangItem]] = {}
    for it in items:
        key = it.label_key
        if not key:
            continue
        out.setdefault(key, []).append(it)
    return out


def _find_match(
    cur_key: str,
    prior_index: dict[str, list[AnhangItem]],
) -> tuple[Optional[AnhangItem], float]:
    """Sucht im Index nach exaktem oder fuzzy Match."""
    if cur_key in prior_index:
        return prior_index[cur_key][0], 1.0
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
# Hauptfunktion
# ---------------------------------------------------------------------------
def compare_anhaenge(current_pdf: Path, prior_pdf: Path) -> CompareResult:
    """
    Vergleicht die Vorjahreszahlen zwischen zwei Anhang-PDFs.

    Args:
        current_pdf: Anhang des aktuellen Berichtsjahrs (z.B. Anhang 2025)
        prior_pdf:   Anhang des Vorjahrs (z.B. Anhang 2024)

    Returns:
        CompareResult mit einer Zeile pro (Label, Spalte). Labels die nur
        im Vorjahres-PDF vorkamen werden als zusätzliche Zeilen mit Status
        NUR_VORJAHR angehängt.
    """
    current_pdf = Path(current_pdf)
    prior_pdf = Path(prior_pdf)

    cur_items = extract_items(current_pdf)
    prior_items = extract_items(prior_pdf)

    prior_index = _index_by_normalized(prior_items)
    matched_prior_keys: set[str] = set()
    rows: list[ComparisonRow] = []

    for cur in cur_items:
        # Wir vergleichen nur Items, die im aktuellen Anhang überhaupt
        # einen Vorjahreswert ausweisen — sonst gibt es nichts zu prüfen.
        if not cur.prior_values:
            continue

        match, score = _find_match(cur.label_key, prior_index)

        if match is None:
            for ci, v in enumerate(cur.prior_values, start=1):
                rows.append(
                    ComparisonRow(
                        label=cur.label,
                        column_index=ci,
                        value_in_current_anhang=v,
                        value_in_prior_anhang=None,
                        page_current=cur.page,
                        page_prior=None,
                        match_score=0.0,
                        status="NUR_AKTUELL",
                    )
                )
            continue

        matched_prior_keys.add(match.label_key)

        n = max(len(cur.prior_values), len(match.current_values))

        # Anlagespiegel-Doppelzeilen: Zeile 1 und Zeile 2 haben unterschiedliche
        # Spalten-Semantik. Nur die Bilanzspalten (AHK, KumAfa, Buchwert) sind
        # direkt vergleichbar; Bewegungsspalten (Zugänge, AfA, Abgänge) werden
        # übersprungen.
        # Standard-Layout 6 Spalten:  [AHK | Zug | KumAfa | AfA | Abg | BW]
        #   Bilanzspalten bei n=6: {0, 2, 5}
        #   Bilanzspalten bei n=5: {0, 2, 4}
        #   Bilanzspalten bei n=4: {0, 2, 3}
        #   Bilanzspalten bei n<=3: alle
        if cur.double_row or match.double_row:
            if n == 6:
                compare_cols: set[int] = {0, 2, 5}
            elif n == 5:
                compare_cols = {0, 2, 4}
            elif n == 4:
                compare_cols = {0, 2, 3}
            else:
                compare_cols = set(range(n))
        else:
            compare_cols = set(range(n))

        for ci in range(n):
            if ci not in compare_cols:
                continue  # Bewegungsspalte überspringen

            v_cur = cur.prior_values[ci] if ci < len(cur.prior_values) else None
            v_pri = match.current_values[ci] if ci < len(match.current_values) else None

            if v_cur is None or v_pri is None:
                status = "FEHLENDER_WERT"
            elif _values_match(v_cur, v_pri):
                status = "OK"
            else:
                status = "ABWEICHUNG"

            rows.append(
                ComparisonRow(
                    label=cur.label,
                    column_index=ci + 1,
                    value_in_current_anhang=v_cur,
                    value_in_prior_anhang=v_pri,
                    page_current=cur.page,
                    page_prior=match.page,
                    match_score=score,
                    status=status,
                    label_prior_doc=match.label if match.label != cur.label else None,
                )
            )

    # Zusatz-Zeilen für Posten, die nur im Vorjahres-PDF vorkommen.
    for it in prior_items:
        if it.label_key in matched_prior_keys:
            continue
        if not it.current_values:
            continue
        for ci, v in enumerate(it.current_values, start=1):
            rows.append(
                ComparisonRow(
                    label=it.label,
                    column_index=ci,
                    value_in_current_anhang=None,
                    value_in_prior_anhang=v,
                    page_current=0,
                    page_prior=it.page,
                    match_score=0.0,
                    status="NUR_VORJAHR",
                    label_prior_doc=it.label,
                )
            )

    return CompareResult(
        current_pdf=current_pdf,
        prior_pdf=prior_pdf,
        rows=rows,
    )
