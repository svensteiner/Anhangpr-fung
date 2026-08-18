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

    # METHODEN/VERFAHREN: Hier entscheidet der EINE Begriff allein. Fragt die
    # Checkliste nach dem Umsatzkostenverfahren und ist der Abschluss nach dem
    # Gesamtkostenverfahren aufgestellt, ist der Punkt nicht anwendbar – auch
    # wenn Begleitbegriffe wie "Personalaufwand" im Abschluss vorkommen.
    (r"umsatzkostenverfahren", ["umsatzkostenverfahren"]),
    (r"pauschalwertberichtigung", ["pauschalwertberichtigung", "pauschale wertberichtigung"]),
    (r"equity-?methode", ["equity"]),
    (r"vollkonsolidier|quotenkonsolidier", ["vollkonsolidier", "quotenkonsolidier"]),
    (r"teilwertabschreibung", ["teilwertabschreibung"]),
    (r"zuschreibung", ["zuschreibung"]),

    # ---------------------------------------------------------------------
    # BILANZPOSITIONEN: Fragt der Prüfpunkt nach einer konkreten Position und
    # ist diese im Abschluss nicht bilanziert, ist die Angabe NICHT ANWENDBAR
    # (nicht "offen"). Beispiel: ohne Firmenwert entfallen alle Firmenwert-
    # Angaben. Geprüft wird der GESAMTE Abschluss (Bilanz UND Anhang).
    # ---------------------------------------------------------------------
    (r"firmenwert|gesch(ä|ae)fts-?\s*\(?firmen", ["firmenwert", "firmen-)wert", "goodwill"]),
    (r"entwicklungskosten|forschung", ["entwicklungskosten", "forschung"]),
    (r"vorr(ä|ae)t|unfertige|fertige erzeugnis|roh-,? hilfs",
     ["vorrat", "vorräte", "vorraet", "unfertige", "fertige erzeugnis", "handelswaren", "hilfsstoffe"]),
    (r"beteiligung", ["beteiligung"]),
    (r"ausleihung", ["ausleihung"]),
    (r"eigene anteile|eigene aktien", ["eigene anteile", "eigene aktien"]),
    (r"pensionsr(ü|ue)ckstellung|pensionsverpflichtung", ["pension"]),
    (r"abfertigung", ["abfertigung"]),
    (r"jubil(ä|ae)um", ["jubiläum", "jubilaeum", "jubiläums", "jubilaeums"]),
    (r"disagio|damnum", ["disagio", "damnum"]),
    (r"fremdw(ä|ae)hrung|devisen", ["fremdwährung", "fremdwaehrung", "devisen"]),
    (r"grundst(ü|ue)ck|geb(ä|ae)ude|bauten", ["grundstück", "grundstueck", "gebäude", "gebaeude", "bauten"]),
    (r"anzahlung", ["anzahlung"]),
    (r"r(ü|ue)cklage", ["rücklage", "ruecklage"]),
    (r"gewinnvortrag|verlustvortrag|bilanzverlust|bilanzgewinn",
     ["gewinnvortrag", "verlustvortrag", "bilanzverlust", "bilanzgewinn"]),
]


# Allgemeines Prüf-/Rechnungslegungsvokabular. Diese Begriffe beschreiben die
# ANGABE selbst, nicht einen Sachverhalt des Mandanten – ihr Fehlen bedeutet
# "Angabe fehlt", NICHT "nicht anwendbar". Sie dürfen den generischen
# Positionsfilter daher nie auslösen.
_GENERISCHE_BEGRIFFE = {
    "angabe", "angaben", "erlaeuterung", "erläuterung", "erlaeuterungen", "erläuterungen",
    "aufgliederung", "beschreibung", "begruendung", "begründung", "darstellung",
    "gesellschaft", "gesellschaften", "unternehmen", "mutterunternehmen",
    "geschaeftsjahr", "geschäftsjahr", "berichtsjahr", "wirtschaftsjahr", "vorjahr",
    "bilanzstichtag", "jahresabschluss", "abschlussstichtag", "konzernabschluss",
    "gesamtbetrag", "betrages", "betraege", "beträge", "hoehe", "höhe",
    "bilanzierung", "bilanzierungs", "bewertung", "bewertungs", "bewertungsmethoden",
    "grundsaetze", "grundsätze", "vorschriften", "voraussetzungen", "verhaeltnisse",
    "auswirkungen", "zusammensetzung", "restlaufzeit", "geschaeftsfelder",
    "wesentliche", "wesentlichen", "sonstige", "sonstigen", "einzelnen",
    "buchwertes", "buchwert", "posten", "bilanzposten", "position", "positionen",
}

#: Ab dieser Länge gilt ein Wort als spezifischer Fachbegriff.
_POSITIONS_MIN_LEN = 12


def _positions_begriffe(item: ChecklistItem) -> list[str]:
    """Spezifische Sachverhalts-/Positionsbegriffe der Prüffrage.

    Nur lange, nicht-generische Wörter – also solche, die eine konkrete Bilanz-
    oder GuV-Position bzw. einen Sachverhalt benennen ("Pauschalwertberichtigung",
    "Firmenwert", "Genussrecht"), nicht das Prüfvokabular ("Angabe").
    """
    text = (item.description or "") + " " + " ".join(item.search_keywords)
    woerter = re.findall(r"[a-zäöüßA-ZÄÖÜ]{%d,}" % _POSITIONS_MIN_LEN, text)
    out: list[str] = []
    for w in woerter:
        wl = w.lower()
        # Beugungsfest vergleichen: "Restlaufzeiten" ist so generisch wie
        # "Restlaufzeit" und darf den Filter nicht auslösen.
        if any(wl.startswith(g) or g.startswith(wl) for g in _GENERISCHE_BEGRIFFE):
            continue
        out.append(wl)
    return out


def _begriff_im_abschluss(begriff: str, document_text_low: str) -> bool:
    """Kommt der Begriff (auch als Wortstamm) im Abschluss vor?"""
    if begriff in document_text_low:
        return True
    # Wortstamm: Komposita/Beugung ("Pauschalwertberichtigungen" -> "...berichtigung")
    return len(begriff) >= 12 and begriff[:10] in document_text_low


def _position_vorhanden(item: ChecklistItem, document_text_low: str) -> bool:
    """False, wenn KEIN spezifischer Begriff der Prüffrage im Abschluss vorkommt.

    Fachregel des Prüfers: Findet sich z.B. das Wort "Pauschalwertberichtigung"
    nirgends im Abschluss, ist die zugehörige Anhangangabe nicht anwendbar –
    nicht "offen".
    """
    begriffe = _positions_begriffe(item)
    if not begriffe:
        return True                     # keine Positionsbindung -> immer prüfen
    return any(_begriff_im_abschluss(b, document_text_low) for b in begriffe)


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


#: Größenklasse-Bezeichnungen der KPMG-Spalte -> normierter Schlüssel.
_SIZE_LABEL = {"groß": "gross", "gross": "gross", "mittel": "mittel", "klein": "klein"}
_SIZE_ENTRY_RE = re.compile(r"\b(gmbh|ag)\b\s+(groß|gross|mittel|klein)", re.IGNORECASE)

#: Anzeigetexte für Meldungen (nicht für den internen Vergleich).
_SIZE_DISPLAY = {"gross": "groß", "mittel": "mittel", "klein": "klein"}
_FORM_DISPLAY = {"gmbh": "GmbH", "ag": "AG"}


def _parse_size_classes(entries: list[str]) -> set[tuple[str, str]]:
    """Zerlegt Einträge wie 'AG groß; GmbH mittel' in {(rechtsform, größe)}."""
    out: set[tuple[str, str]] = set()
    for entry in entries:
        for m in _SIZE_ENTRY_RE.finditer(entry.lower()):
            out.add((m.group(1), _SIZE_LABEL.get(m.group(2), m.group(2))))
    return out


def _size_class_applicable(
    item: ChecklistItem, legal_form: str | None, size_class: str | None
) -> bool:
    """True = Punkt ist anwendbar (nicht filtern).

    legal_form ('gmbh'/'ag') UND size_class ('klein'/'mittel'/'gross') müssen
    beide bekannt sein, sonst wird konservativ NICHT gefiltert (unbekannt =>
    immer anwendbar). Ebenso, wenn die Spalte keine auswertbaren Einträge hat.
    """
    if not item.size_classes or legal_form is None or size_class is None:
        return True
    parsed = _parse_size_classes(item.size_classes)
    if not parsed:
        return True
    return (legal_form, size_class) in parsed


def _item_applicable_ex(
    item: ChecklistItem, document_text_low: str
) -> tuple[bool, list[str] | None]:
    """Wie _item_applicable, gibt zusätzlich die geprüften Auslöse-Begriffe
    zurück (für eine sprechende n.-a.-Begründung)."""
    dl = (item.description or "").lower()
    for pattern, triggers in ITEM_TRIGGERS:
        if re.search(pattern, dl):
            return any(kw in document_text_low for kw in triggers), triggers
    return True, None


def _item_applicable(item: ChecklistItem, document_text_low: str) -> bool:
    """Prüffragen-Ebene: Sachverhalt der Frage im Abschluss vorhanden?"""
    return _item_applicable_ex(item, document_text_low)[0]


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


#: Präfix für n.a.-Gründe, die NUR aus Stichwort-/Positions-Heuristik stammen
#: (Klasse "maschinell") – im Gegensatz zu Gründen mit klarem Rechtsgrund
#: (Größenklasse, Prüfer-Vorgabe Blatt "Start").
MASCHINELL_PRAEFIX = "Maschinell n. a. – bitte stichprobenweise prüfen: "


def apply_relevance(
    result: ReviewResult,
    checklist: Checklist,
    document_text: str,
    legal_form: str | None = None,
    size_class: str | None = None,
) -> dict:
    """Setzt Findings nicht anwendbarer Kategorien/Punkte auf NOT_APPLICABLE.

    legal_form ('gmbh'/'ag'/None) und size_class ('klein'/'mittel'/'gross'/None)
    kommen bevorzugt aus der UI-Auswahl des Prüfers; ist legal_form nicht
    gesetzt, wird die Rechtsform-Autoerkennung aus dem Abschlusstext als
    Fallback verwendet (size_class kann nicht automatisch erkannt werden).

    n.-a.-Gründe werden in zwei Klassen unterschieden:
      - RECHTSGRUND: Größenklasse (§ 221 UGB) oder Prüfer-Vorgabe (Blatt
        "Start") – eindeutig, keine Stichwortsuche beteiligt.
      - MASCHINELL: Kategorie-/Positions-Trigger bzw. Stichwortabwesenheit –
        nur ein Hinweis, der Grund trägt den Präfix MASCHINELL_PRAEFIX und
        bekommt keinen eigenen Status (bleibt NICHT ANWENDBAR).

    Gibt eine Übersicht zurück:
      { "anwendbar": [Kategorien], "nicht_anwendbar": [Kategorien],
        "umgestellt": Anzahl der auf NICHT ANWENDBAR gesetzten Findings,
        "rechtsform": effektive Rechtsform, "groessenklasse": size_class,
        "rechtsgrund": Anzahl n.a. mit Rechtsgrund,
        "maschinell": Anzahl n.a. maschinell }
    """
    low = (document_text or "").lower()
    detected_form = _detect_legal_form(low)
    effective_form = legal_form or detected_form
    item_of = {it.item_id: it for it in checklist.items}
    applicable_cache: dict[str, bool] = {}

    umgestellt = 0
    rechtsgrund_n = 0
    maschinell_n = 0
    for f in result.findings:
        item = item_of.get(f.checklist_item_id)
        cat = item.category if item else ""
        if cat not in applicable_cache:
            applicable_cache[cat] = category_applicable(cat, low)

        grund: str | None = None
        klasse: str | None = None

        if item is not None and not item.pruefer_relevant:
            grund = "Im Prüfprogramm (Blatt Start) als nicht relevant markiert."
            klasse = "rechtsgrund"
        elif item is not None and not _size_class_applicable(item, effective_form, size_class):
            form_txt = _FORM_DISPLAY.get(effective_form, effective_form)
            size_txt = _SIZE_DISPLAY.get(size_class, size_class)
            grund = (f"Nicht erforderlich für {form_txt} {size_txt} "
                     "(Größenklasse laut Prüfprogramm).")
            klasse = "rechtsgrund"
        elif not applicable_cache[cat]:
            begriffe = _triggers_for(cat) or []
            hinweis = ", ".join(begriffe[:3]) or "kein Positions-/Themenbegriff im Abschluss"
            grund = f"{MASCHINELL_PRAEFIX}Position nicht vorhanden ({hinweis})."
            klasse = "maschinell"
        elif item is not None and not _item_applicable(item, low):
            _ok, triggers = _item_applicable_ex(item, low)
            hinweis = ", ".join((triggers or [])[:3]) or "Sachverhalt"
            grund = f"{MASCHINELL_PRAEFIX}Sachverhalt nicht vorhanden ({hinweis})."
            klasse = "maschinell"
        elif item is not None and not _position_vorhanden(item, low):
            begriffe = _positions_begriffe(item)
            hinweis = ", ".join(begriffe[:3]) or "Fachbegriff"
            grund = f"{MASCHINELL_PRAEFIX}Position/Sachverhalt kommt im Abschluss nicht vor ({hinweis})."
            klasse = "maschinell"

        if grund and f.status != ComplianceStatus.NOT_APPLICABLE:
            f.status = ComplianceStatus.NOT_APPLICABLE
            f.technical_reasoning = grund
            f.evidence = []
            umgestellt += 1
            if klasse == "rechtsgrund":
                rechtsgrund_n += 1
            elif klasse == "maschinell":
                maschinell_n += 1

    anwendbar = sorted({c for c, ok in applicable_cache.items() if ok})
    nicht = sorted({c for c, ok in applicable_cache.items() if not ok})
    result._update_statistics()
    return {
        "anwendbar": anwendbar, "nicht_anwendbar": nicht, "umgestellt": umgestellt,
        "rechtsform": effective_form, "groessenklasse": size_class,
        "rechtsgrund": rechtsgrund_n, "maschinell": maschinell_n,
    }
