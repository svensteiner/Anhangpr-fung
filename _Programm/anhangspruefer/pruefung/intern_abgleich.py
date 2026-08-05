"""
Interner Abgleich: Detailzahlen VORNE (Bilanz/GuV) ↔ Anhang HINTEN.

Fachlicher Hintergrund
======================
Im Jahresabschluss-Entwurf stehen die Detailzahlen im vorderen Teil (Bilanz und
Gewinn- und Verlustrechnung), die erläuternden Angaben im Anhang dahinter. Beide
müssen zueinander passen – eine Position darf im Anhang nicht mit einem anderen
Betrag erläutert werden als sie in der Bilanz ausgewiesen ist.

Dieser Abgleich braucht KEINE externen Belege: er prüft das Dokument gegen sich
selbst und ist damit sofort einsetzbar (Teil der Belegprüfung, Modus 2).

Vorgehen (rein lokal)
=====================
1. Seitenbereich des Anhangs bestimmen (bestehende Erkennung).
2. Posten aus dem VORDEREN Teil (vor dem Anhang) und aus dem ANHANG getrennt
   extrahieren – mit demselben, erprobten Extraktor.
3. Posten über den normalisierten Bezeichnungs-Schlüssel paaren und die
   Berichtsjahreswerte vergleichen.

Präzision vor Vollständigkeit: Gemeldet wird nur, was eindeutig zuordenbar ist.
Kommt eine Bezeichnung mehrfach mit unterschiedlichen Werten vor (z.B. Brutto-
und Nettodarstellung), gilt der Posten als übereinstimmend, sobald IRGENDEIN
Wertepaar zusammenpasst – sonst entstünden Scheinabweichungen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ..parsers.document_text import load_page_texts
from ..vorjahresvergleich.extractor import (
    X_TOLERANCE,
    AnhangItem,
    anhang_page_range,
    extract_items,
)

#: Rundungstoleranz in EUR (Anhang rundet häufig auf ganze Euro).
TOLERANZ = 0.5

#: Kürzere Bezeichnungen sind nicht eindeutig genug für einen Abgleich.
#: (Kurze Schlüssel paaren quer und erzeugen Scheinabweichungen.)
MIN_KEY_LEN = 12

#: Ab dieser Größenordnung gilt ein Wert als Betrag; darunter ist es eher eine
#: Stückzahl (Arbeitnehmer, Anteile) – Betrag gegen Stückzahl darf nicht als
#: Abweichung gemeldet werden.
BETRAG_GRENZE = 1000.0
STUECKZAHL_GRENZE = 100.0


def _ist_jahreszahl(wert: float) -> bool:
    """1900–2100 als ganze Zahl ist fast immer eine Jahresangabe, kein Betrag."""
    return float(wert).is_integer() and 1900 <= abs(wert) <= 2100


def _semantisch_unvergleichbar(a: float, b: float) -> bool:
    """Stückzahl gegen Betrag – die Paarung ist inhaltlich falsch."""
    kleiner, groesser = min(abs(a), abs(b)), max(abs(a), abs(b))
    return kleiner < STUECKZAHL_GRENZE and groesser >= BETRAG_GRENZE

STATUS_OK = "OK"
STATUS_ABWEICHUNG = "ABWEICHUNG"


@dataclass
class AbgleichZeile:
    """Eine Position, die vorne UND im Anhang vorkommt."""
    label: str
    wert_vorne: float
    wert_anhang: float
    seite_vorne: int
    seite_anhang: int
    status: str

    @property
    def differenz(self) -> float:
        return self.wert_vorne - self.wert_anhang


@dataclass
class AbgleichErgebnis:
    dokument: str
    zeilen: list[AbgleichZeile] = field(default_factory=list)
    posten_vorne: int = 0
    posten_anhang: int = 0
    anhang_ab_seite: Optional[int] = None

    @property
    def anzahl_ok(self) -> int:
        return sum(1 for z in self.zeilen if z.status == STATUS_OK)

    @property
    def anzahl_abweichung(self) -> int:
        return sum(1 for z in self.zeilen if z.status == STATUS_ABWEICHUNG)


def _berichtswert(item: AnhangItem) -> Optional[float]:
    """Der Wert, der gegen die Bilanz abzustimmen ist.

    Fachregel: In Spiegel-Darstellungen (Anlagenspiegel:
    Anschaffungskosten | Zugänge | Abgänge | Abschreibungen | BUCHWERT) ist
    NICHT die erste Spalte (Anschaffungskosten) mit der Bilanz vergleichbar,
    sondern die letzte (Buchwert). Nur der Buchwert steht in der Bilanz.
    """
    v = item.current_values
    if not v:
        return None
    if len(v) >= 3:            # Spiegel-Zeile -> Buchwert
        return v[-1]
    return v[0]


def _alle_werte(item: AnhangItem) -> list[float]:
    """Alle Wertspalten – für die tolerante Übereinstimmungsprüfung."""
    return list(item.current_values)


def _sammle(items: list[AnhangItem]) -> dict[str, list[tuple[float, int]]]:
    """Schlüssel -> Liste von (Wert, Seite). Mehrfachnennungen bleiben erhalten."""
    out: dict[str, list[tuple[float, int]]] = {}
    for it in items:
        key = it.label_key_compact
        wert = _berichtswert(it)
        if not key or len(key) < MIN_KEY_LEN or wert is None:
            continue
        out.setdefault(key, []).append((wert, it.page))
    return out


def abgleich_intern(pdf_path: Path, toleranz: float = TOLERANZ) -> AbgleichErgebnis:
    """Prüft die Detailzahlen des vorderen Teils gegen die Anhangangaben."""
    pdf_path = Path(pdf_path)
    ergebnis = AbgleichErgebnis(dokument=pdf_path.name)

    page_texts = load_page_texts(pdf_path, x_tolerance=X_TOLERANCE)
    start, end = anhang_page_range(page_texts)
    if start <= 0:
        # Kein vorderer Teil vorhanden (reines Anhang-Dokument) -> nichts zu tun.
        return ergebnis
    ergebnis.anhang_ab_seite = start + 1

    vorne = extract_items(pdf_path, page_range=(0, start))
    hinten = extract_items(pdf_path, page_range=(start, end))
    ergebnis.posten_vorne = len(vorne)
    ergebnis.posten_anhang = len(hinten)

    # Der Anhang ist die zu prüfende Angabe; im vorderen Teil steht das Detail.
    # Bezeichnungen dort tragen oft Zusätze (z.B. Kontonummern), deshalb wird
    # per Teilstring zugeordnet, nicht per Gleichheit.
    for h_item in hinten:
        h_key = h_item.label_key_compact
        h_wert = _berichtswert(h_item)
        if h_wert is None or len(h_key) < MIN_KEY_LEN:
            continue

        partner = [
            it for it in vorne
            if it.current_values and len(it.label_key_compact) >= MIN_KEY_LEN
            and (h_key in it.label_key_compact or it.label_key_compact in h_key)
        ]
        if not partner:
            continue                      # keine Entsprechung vorne -> kein Fall

        # (a) Stimmt IRGENDEINE Wertspalte des Anhang-Postens mit einer
        #     Wertspalte vorne überein? Der Anhang zeigt bei Spiegeln mehrere
        #     Spalten (Anschaffungskosten … Buchwert); in der Bilanz steht der
        #     Buchwert. Ein Treffer in irgendeiner Spalte belegt die Abstimmung.
        h_werte = _alle_werte(h_item)
        treffer = next(
            ((it, w) for it in partner for w in it.current_values
             for hw in h_werte if abs(w - hw) <= toleranz),
            None,
        )
        if treffer:
            it, w = treffer
            ergebnis.zeilen.append(AbgleichZeile(
                h_item.label, w, w, it.page, h_item.page, STATUS_OK))
            continue

        # (b) Summe der Detailposten ergibt die Anhangangabe?
        summe = sum(it.current_values[0] for it in partner)
        if len(partner) > 1 and abs(summe - h_wert) <= toleranz:
            ergebnis.zeilen.append(AbgleichZeile(
                h_item.label, summe, h_wert, partner[0].page, h_item.page, STATUS_OK))
            continue

        # (c) Abweichung – aber nur, wenn die Paarung fachlich tragfähig ist.
        v_wert = partner[0].current_values[0]
        if (_ist_jahreszahl(v_wert) or _ist_jahreszahl(h_wert)
                or _semantisch_unvergleichbar(v_wert, h_wert)):
            continue                      # Fehlpaarung -> nicht melden
        # Zwei kleine ganze Zahlen sind Stückzahlen (Arbeitnehmer, Anteile) –
        # ohne Betragsbezug ist die Zuordnung über die Bezeichnung zu schwach,
        # um daraus eine Abweichung abzuleiten.
        if (abs(v_wert) < STUECKZAHL_GRENZE and abs(h_wert) < STUECKZAHL_GRENZE):
            continue
        ergebnis.zeilen.append(AbgleichZeile(
            h_item.label, v_wert, h_wert,
            partner[0].page, h_item.page, STATUS_ABWEICHUNG))

    ergebnis.zeilen.sort(key=lambda z: (z.status != STATUS_ABWEICHUNG, z.label))
    return ergebnis
