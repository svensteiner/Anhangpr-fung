"""Tests für Modus 3: Loader-Blattwahl + Relevanz-Filter (bedingte Angaben).

Nur synthetische Daten – keine Mandanten-/KPMG-Unterlagen.
"""

from datetime import datetime

import openpyxl

from anhangspruefer.models.checklist import Checklist, ChecklistItem
from anhangspruefer.models.finding import Finding, ReviewResult, EvidenceItem
from anhangspruefer.models.enums import ComplianceStatus
from anhangspruefer.compliance.knowledge.checklist_loader import ChecklistLoader
from anhangspruefer.compliance.knowledge.relevance import (
    _detect_legal_form,
    _item_applicable,
    _size_class_applicable,
    apply_relevance,
    category_applicable,
)


# --- Loader: das richtige Blatt wählen (nicht das "Start"-Übersichtsblatt) ---
def test_load_from_xlsx_picks_master_sheet(tmp_path):
    wb = openpyxl.Workbook()
    start = wb.active
    start.title = "Start"
    start.append(["#", "Kategorie", "Prüfpunkte", "relevant?"])   # KEIN ID/Prüffrage
    start.append(["1", "Allgemein", "7", "Ja"])
    master = wb.create_sheet("UGB-Prüfprogramm")
    master.append(["ID", "Kategorie", "Prüffrage", "UGB-§", "Stichwörter", "Pflicht", "Anwendbar auf"])
    master.append(["K001", "Vorräte", "Angabe des Unterschiedsbetrags", "§ 238", "Vorräte", "Ja", "alle"])
    master.append(["K002", "Forderungen", "Erläuterung der Forderungen", "§ 225", "Forderung", "Ja", "alle"])
    p = tmp_path / "pp.xlsx"
    wb.save(p)

    cl = ChecklistLoader().load_from_xlsx(p)
    assert len(cl.items) == 2                       # nicht 0 (Bug: las 'Start')
    assert cl.get_item("K001").category == "Vorräte"


# --- Relevanz: allgemeine Kategorien immer, positionsabhängige nur bei Vorkommen ---
def test_category_applicable_general_is_always_true():
    assert category_applicable("Allgemein", "") is True
    assert category_applicable("Allgemeine Angaben", "beliebig") is True


def test_category_applicable_conditional():
    assert category_applicable("Vorräte", "Die Vorräte werden bewertet.".lower()) is True
    assert category_applicable("Vorräte", "hier steht nichts dazu") is False
    assert category_applicable("Anteilsbasierte Vergütungen", "keine") is False
    assert category_applicable("Umgründung Allgemein", "im Zuge der Verschmelzung".lower()) is True


def _finding(iid):
    return Finding(checklist_item_id=iid, status=ComplianceStatus.PARTIALLY_COMPLIANT, ugb_references=[])


def test_apply_relevance_marks_absent_positions_not_applicable():
    cl = Checklist(name="t", version="")
    cl.add_item(ChecklistItem(item_id="A1", category="Vorräte", description="x"))
    cl.add_item(ChecklistItem(item_id="B1", category="Anteilsbasierte Vergütungen", description="y"))
    cl.add_item(ChecklistItem(item_id="C1", category="Allgemein", description="z"))
    res = ReviewResult(document_name="d", checklist_name="t", review_timestamp=datetime(2026, 1, 1))
    for iid in ("A1", "B1", "C1"):
        res.add_finding(_finding(iid))

    summary = apply_relevance(res, cl, "Die Vorräte werden zu Anschaffungskosten bewertet.")
    st = {f.checklist_item_id: f.status for f in res.findings}

    assert st["A1"] == ComplianceStatus.PARTIALLY_COMPLIANT   # Vorräte vorhanden -> bleibt
    assert st["B1"] == ComplianceStatus.NOT_APPLICABLE        # anteilsbasiert fehlt -> N/A
    assert st["C1"] == ComplianceStatus.PARTIALLY_COMPLIANT   # allgemein immer relevant
    assert "Anteilsbasierte Vergütungen" in summary["nicht_anwendbar"]
    assert summary["umgestellt"] == 1


# --- Rechtsform & Größenklasse (KPMG-Spalte) ---------------------------------
def test_detect_legal_form():
    assert _detect_legal_form("die musterfirma handels gmbh mit stammkapital") == "gmbh"
    assert _detect_legal_form("die muster aktiengesellschaft mit grundkapital") == "ag"
    assert _detect_legal_form("unklarer text ohne rechtsform") is None


def test_size_class_excludes_ag_only_items_for_gmbh():
    ag_only = ChecklistItem(item_id="K044", category="Allgemein", description="Aktiengattungen",
                            size_classes=["AG groß", "AG mittel"])
    mixed = ChecklistItem(item_id="K048", category="Allgemein", description="x",
                          size_classes=["AG groß", "GmbH groß"])
    unrestricted = ChecklistItem(item_id="K001", category="Allgemein", description="y")
    assert _size_class_applicable(ag_only, "gmbh") is False
    assert _size_class_applicable(mixed, "gmbh") is True
    assert _size_class_applicable(unrestricted, "gmbh") is True
    assert _size_class_applicable(ag_only, None) is True      # Rechtsform unklar -> nicht filtern


def test_item_trigger_verbrauchsfolge_hat_vorrang_vor_wertpapier():
    # K022-Fall: Frage nennt Verbrauchsfolgeverfahren UND (beiläufig) Wertpapiere.
    item = ChecklistItem(
        item_id="K022", category="Allgemein",
        description=("Angabe des Unterschiedsbetrages zu Börsenkursen bei Anwendung "
                     "eines Verbrauchsfolgeverfahrens gem. § 209 (2) UGB, auch bei Wertpapieren"))
    # Mandant OHNE Verbrauchsfolgeverfahren -> nicht anwendbar
    assert _item_applicable(item, "die waren werden zu anschaffungskosten bewertet") is False
    # Mandant MIT FIFO -> anwendbar (auch wenn 'wertpapier' im Abschluss fehlt)
    assert _item_applicable(item, "die vorräte werden nach dem fifo-verfahren bewertet") is True


def test_item_trigger_hybridinstrumente():
    item = ChecklistItem(item_id="K060", category="Allgemein",
                         description="Angabe des Bestehens von Genussscheinen, Wandelschuldverschreibungen oder vergleichbaren Wertpapieren")
    assert _item_applicable(item, "text ohne solche instrumente") is False
    assert _item_applicable(item, "es bestehen genussrechte aus dem jahr 2020") is True


def test_item_trigger_festverzinsliche_wertpapiere():
    item = ChecklistItem(item_id="K014", category="Allgemein",
                         description="Beschreibung der Methoden bei festverzinslichen Wertpapieren")
    assert _item_applicable(item, "kein einschlägiger text") is False
    assert _item_applicable(item, "die wertpapiere des anlagevermögens ...") is True
    # 'derivativer Firmenwert' ist KEIN Derivat -> der Derivate-Trigger darf
    # nicht greifen; maßgeblich ist, ob ein FIRMENWERT bilanziert ist.
    fw = ChecklistItem(item_id="K018", category="Allgemein",
                       description="Zuordnung eines derivativen Geschäfts-(Firmen-)werts")
    assert _item_applicable(fw, "der firmenwert wird linear abgeschrieben") is True
    # Ohne Firmenwert im Abschluss ist die Angabe nicht anwendbar (Prüfervorgabe)
    assert _item_applicable(fw, "text ohne solche position") is False


def test_loader_reads_size_classes(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "UGB-Prüfprogramm"
    ws.append(["ID", "Kategorie", "Prüffrage", "UGB-§", "Stichwörter", "Pflicht",
               "Anwendbar auf", "Größenklasse (KPMG)"])
    ws.append(["K044", "Allgemein", "Aktienangaben", "§ 241", "Aktien", "Ja",
               "alle", "AG groß; AG mittel"])
    p = tmp_path / "pp.xlsx"
    wb.save(p)
    cl = ChecklistLoader().load_from_xlsx(p)
    assert cl.get_item("K044").size_classes == ["AG groß", "AG mittel"]
    assert cl.get_item("K044").applicable_to == ["alle"]


# --- Ausgefüllte KPMG-Checkliste als Excel ---
def test_generate_checklist_xlsx(tmp_path):
    import openpyxl
    from anhangspruefer.compliance.reporting.checklist_excel import generate_checklist_xlsx

    cl = Checklist(name="t", version="")
    cl.add_item(ChecklistItem(item_id="K1", category="Vorräte", description="Angabe X", ugb_references=["§ 238"]))
    cl.add_item(ChecklistItem(item_id="K2", category="Anteilsbasierte Vergütungen", description="Angabe Y"))
    cl.add_item(ChecklistItem(item_id="K3", category="Verbindlichkeiten",
                              description="Angabe der Restlaufzeit über 5 Jahre"))
    res = ReviewResult(document_name="Anhang.pdf", checklist_name="t", review_timestamp=datetime(2026, 1, 1))
    res.add_finding(Finding(checklist_item_id="K1", status=ComplianceStatus.COMPLIANT, ugb_references=["§ 238"]))
    f2 = Finding(checklist_item_id="K2", status=ComplianceStatus.NOT_APPLICABLE, ugb_references=[])
    f2.add_evidence(EvidenceItem(section_id="s", section_title="Anhang", quote="schwacher treffer", page_number=5))
    res.add_finding(f2)
    f3 = Finding(checklist_item_id="K3", status=ComplianceStatus.NOT_COMPLIANT, ugb_references=[])
    f3.missing_elements = ["Gesamtbetrag Restlaufzeit über 5 Jahre nicht angegeben"]
    res.add_finding(f3)

    out = tmp_path / "cl.xlsx"
    generate_checklist_xlsx(cl, res, out)

    wb = openpyxl.load_workbook(out)
    assert "KPMG-Checkliste (ausgefüllt)" in wb.sheetnames
    ws = wb["KPMG-Checkliste (ausgefüllt)"]
    assert ws.max_row == 4                          # Kopf + 3 Punkte
    row2 = [c.value for c in ws[2]]
    row3 = [c.value for c in ws[3]]
    row4 = [c.value for c in ws[4]]
    assert row2[1] == "K1" and row2[5] == "Ja"      # klares Verdikt, kein "Teilweise"
    assert row3[1] == "K2" and row3[5] == "n. a."
    assert (row3[6] or "") == ""                    # bei n. a. kein Nachweis
    # Bei "Fehlt": klare, KONKRETE Aussage was fehlt
    assert row4[5] == "Fehlt"
    assert row4[7] == "Fehlt: Gesamtbetrag Restlaufzeit über 5 Jahre nicht angegeben"


def test_checklist_xlsx_has_pruefer_override(tmp_path):
    """Prüfer kann übersteuern: Dropdown 'Prüfer-Urteil', 'Final' = Prüfer schlägt Tool."""
    import openpyxl
    from anhangspruefer.compliance.reporting.checklist_excel import generate_checklist_xlsx

    cl = Checklist(name="t", version="")
    cl.add_item(ChecklistItem(item_id="K1", category="Vorräte", description="Angabe X"))
    res = ReviewResult(document_name="d", checklist_name="t", review_timestamp=datetime(2026, 1, 1))
    res.add_finding(Finding(checklist_item_id="K1",
                            status=ComplianceStatus.NOT_ASSESSABLE, ugb_references=[]))  # Tool: Offen
    out = tmp_path / "cl.xlsx"
    generate_checklist_xlsx(cl, res, out)

    wb = openpyxl.load_workbook(out)                 # ohne data_only -> Formeln sichtbar
    ws = wb["KPMG-Checkliste (ausgefüllt)"]
    header = [c.value for c in ws[1]]
    assert header[9] == "Prüfer-Urteil" and header[10] == "Final" and header[11] == "Prüfer-Kommentar"
    # Final-Formel: Prüfer-Urteil (J) übersteuert Tool-Ergebnis (F)
    assert ws.cell(row=2, column=11).value == '=IF(J2<>"",J2,F2)'
    # Dropdown mit den vier Verdikten vorhanden
    dvs = list(ws.data_validations.dataValidation)
    assert any(d.formula1 == '"Ja,Fehlt,n. a.,Offen"' for d in dvs)
