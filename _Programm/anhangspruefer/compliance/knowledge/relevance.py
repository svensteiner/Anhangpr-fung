"""
Relevanz-Filter für die UGB-Inhaltsprüfung (Modus 3).

Fachregel (vom Prüfer vorgegeben):
    Eine Anhangangabe ist nur NÖTIG, wenn die zugehörige Bilanz-/GuV-Position
    (bzw. der Sachverhalt) überhaupt vorliegt. Angaben zu nicht vorhandenen
    Positionen (z.B. Umgründung, Derivate, anteilsbasierte Vergütungen) sind
    "NICHT ANWENDBAR" und dürfen nicht als Lücke erscheinen.

Umsetzung:
    Je Prüfprogramm-Kategorie werden Auslöse-Stichwörter (Positions-/Themen-
    indikatoren) hinterlegt. Kommt keines davon im geprüften Dokumenttext vor,
    gilt die Kategorie als nicht anwendbar. Kategorien ohne Auslöser sind IMMER
    relevant (allgemeine Angaben, Bewertungsmethoden, GuV, Arbeitnehmer,
    Ereignisse nach Stichtag, abschließende Würdigung, Vorjahreszahlen).

Der Dokumenttext sollte Anhang UND – falls vorhanden – die Bilanz umfassen,
damit eine bilanzierte, aber im Anhang gar nicht erwähnte Position erkannt wird.
"""

from __future__ import annotations

import re

from ...models.checklist import Checklist, ChecklistItem
from ...models.finding import ReviewResult
from ...models.enums import ComplianceStatus


# Kategorie-Teilstring (klein)  ->  Positions-/Themen-Stichwörter (klein).
# Keine Auslöser => Kategorie ist immer relevant.
CATEGORY_TRIGGERS: dict[str, list[str]] = {
    "anlagevermögen":       ["anlagevermögen", "anlagenspiegel", "sachanlage", "immaterielle", "geschäfts-(firmen"],
    "finanzanlage":         ["finanzanlage", "wertpapier", "ausleihung", "beteiligung", "anteile an"],
    "finanzumlauf":         ["wertpapier", "finanzumlauf"],
    "vorräte":              ["vorräte", "vorratsvermögen", "fertige erzeugnis", "unfertige", "roh-", "hilfsstoffe", "handelswaren"],
    "forderungen":          ["forderung"],
    "hybride finanzinstrumente": ["genussrecht", "hybride", "partizipationskapital", "nachrangkapital", "besserungskapital"],
    "gmbh & co":            ["gmbh & co", "gmbh und co", "& co. kg", "& co kg"],
    "personalrückstell":    ["rückstellung", "abfertigung", "pension", "jubiläum"],
    "rückstellungen":       ["rückstellung"],
    "investitionszuschüsse": ["investitionszuschuss", "zuschuss"],
    "verbindlichkeiten":    ["verbindlichkeit"],
    "latente steuern":      ["latente steuer", "steuerlatenz", "steuerabgrenzung"],
    "eventualverbindlichkeiten": ["eventualverbindlichkeit", "haftungsverhältnis", "haftungsverhaeltnis", "sonstige finanzielle verpflichtung", "bürgschaft", "garantie"],
    "außerbilanzielle":     ["außerbilanziell", "ausserbilanziell", "off-balance", "nicht in der bilanz"],
    "derivative":           ["derivat", "termingeschäft", "swap", "option", "future", "sicherungsinstrument"],
    "sicherungsbez":        ["sicherungsbeziehung", "hedge", "bewertungseinheit", "derivat"],
    "gruppenbesteuerung":   ["gruppenbesteuerung", "steuergruppe", "gruppenträger", "gruppenmitglied", "steuerumlage"],
    "anteilsbasierte":      ["anteilsbasiert", "aktienbasiert", "aktienoption", "stock option", "aktienoptionsprogramm"],
    "konzernverhältnisse":  ["konzern", "mutterunternehmen", "verbundene unternehmen", "beteiligung", "vollkonsolidier"],
    "beteiligun":           ["konzern", "mutterunternehmen", "verbundene unternehmen", "beteiligung"],
    # Umgründungen – nur bei tatsächlicher Umgründung
    "umgründung":           ["umgründung", "verschmelzung", "spaltung", "abspaltung", "einbringung", "umwandlung", "zuwendung"],
    "abspaltung":           ["abspaltung", "spaltung"],
    "einlage":              ["einbringung", "einlage"],
    "zuwendung":            ["zuwendung"],
    "übernehmende":         ["verschmelzung", "umgründung", "einbringung"],
    "übertragende":         ["verschmelzung", "umgründung", "spaltung", "abspaltung"],
    "gesellschafter der übernehmenden": ["verschmelzung", "umgründung"],
    "hauptgesellschafter":  ["umwandlung", "verschmelzung"],
}


# Themen-Trigger auf PRÜFFRAGEN-Ebene: manche Prüfpunkte hängen an einem
# Sachverhalt, obwohl ihre Kategorie "Allgemein" ist (z.B. festverzinsliche
# Wertpapiere). Bewusst minimal halten — "derivativer Firmenwert" ist z.B.
# KEIN Derivat, sondern abgeleiteter Firmenwert!
ITEM_TRIGGERS: list[tuple[str, list[str]]] = [
    # Reihenfolge = Priorität, der ERSTE passende Eintrag entscheidet.
    # § 209 (2): Angabe hängt an der ANWENDUNG eines Verbrauchsfolgeverfahrens
    # (betrifft v.a. Vorräte) — nicht am zufällig erwähnten Wort "Wertpapier".
    (r"verbrauchsfolge",
     ["verbrauchsfolge", "fifo", "lifo", "durchschnittspreis", "gleitende durchschnitt", "identitätspreis"]),
    # Hybrid-/Sonderinstrumente: nur relevant, wenn solche Instrumente existieren.
    (r"genussschein|genussrecht|wandelschuldverschreibung|optionsschein|besserungsschein",
     ["genussschein", "genussrecht", "wandelschuldverschreibung", "optionsschein", "besserungsschein"]),
    (r"festverzinslich|wertpapier", ["wertpapier", "festverzinslich"]),
    (r"\baktien\b|aktiengattung|bezugsrecht", ["aktie", "grundkapital"]),
]


def _detect_legal_form(document_text_low: str) -> str | None:
    """Rechtsform aus dem Abschlusstext ableiten ('gmbh' | 'ag' | None)."""
    is_gmbh = bool(re.search(r"\bgmbh\b|gesellschaft mit beschränkter haftung|stammkapital|gmbhg",
                             document_text_low))
    is_ag = bool(re.search(r"aktiengesellschaft|grundkapital|\bvorstand\b.*\baufsichtsrat\b",
                           document_text_low))
    if is_gmbh and not is_ag:
        return "gmbh"
    if is_ag and not is_gmbh:
        return "ag"
    return None   # unklar/beides -> konservativ nicht filtern


def _size_class_applicable(item: ChecklistItem, legal_form: str | None) -> bool:
    """False nur, wenn die KPMG-Größenklasse die Rechtsform KLAR ausschließt
    (z.B. reine 'AG …'-Einträge bei einer GmbH)."""
    if not item.size_classes or legal_form is None:
        return True
    for entry in item.size_classes:
        el = entry.lower()
        if legal_form == "gmbh" and "gmbh" in el:
            return True
        if legal_form == "ag" and re.search(r"\bag\b", el):
            return True
    return False


def _item_applicable(item: ChecklistItem, document_text_low: str) -> bool:
    """Prüffragen-Ebene: Sachverhalt der Frage im Abschluss vorhanden?"""
    dl = (item.description or "").lower()
    for pattern, triggers in ITEM_TRIGGERS:
        if re.search(pattern, dl):
            return any(kw in document_text_low for kw in triggers)
    return True


def _triggers_for(category: str) -> list[str] | None:
    """Auslöse-Stichwörter der Kategorie; None => immer relevant."""
    cl = (category or "").lower()
    hits: list[str] = []
    for key, kws in CATEGORY_TRIGGERS.items():
        if key in cl:
            hits.extend(kws)
    return hits or None


def category_applicable(category: str, document_text_low: str) -> bool:
    """True, wenn die Kategorie (Position/Thema) im Dokument vorkommt bzw.
    generell immer gilt."""
    triggers = _triggers_for(category)
    if triggers is None:
        return True
    return any(kw in document_text_low for kw in triggers)


def relevant_categories(categories, document_text: str) -> dict[str, bool]:
    low = (document_text or "").lower()
    return {cat: category_applicable(cat, low) for cat in categories}


def apply_relevance(result: ReviewResult, checklist: Checklist, document_text: str) -> dict:
    """Setzt Findings nicht anwendbarer Kategorien auf NOT_APPLICABLE.

    Gibt eine Übersicht zurück:
      { "anwendbar": [Kategorien], "nicht_anwendbar": [Kategorien],
        "umgestellt": Anzahl der auf NICHT ANWENDBAR gesetzten Findings }
    """
    low = (document_text or "").lower()
    legal_form = _detect_legal_form(low)
    item_of = {it.item_id: it for it in checklist.items}
    applicable_cache: dict[str, bool] = {}

    umgestellt = 0
    for f in result.findings:
        item = item_of.get(f.checklist_item_id)
        cat = item.category if item else ""
        if cat not in applicable_cache:
            applicable_cache[cat] = category_applicable(cat, low)

        # kurzer, klarer n.-a.-Grund (ersetzt das Stichwort-Geschwafel)
        grund = None
        if not applicable_cache[cat]:
            grund = "Position nicht vorhanden."
        elif item is not None and not _size_class_applicable(item, legal_form):
            grund = f"Gilt nicht für {legal_form.upper()} (KPMG-Größenklasse)."
        elif item is not None and not _item_applicable(item, low):
            grund = "Sachverhalt nicht vorhanden."

        if grund and f.status != ComplianceStatus.NOT_APPLICABLE:
            f.status = ComplianceStatus.NOT_APPLICABLE
            f.technical_reasoning = grund
            f.evidence = []
            umgestellt += 1

    anwendbar = sorted({c for c, ok in applicable_cache.items() if ok})
    nicht = sorted({c for c, ok in applicable_cache.items() if not ok})
    result._update_statistics()
    return {"anwendbar": anwendbar, "nicht_anwendbar": nicht, "umgestellt": umgestellt,
            "rechtsform": legal_form}
