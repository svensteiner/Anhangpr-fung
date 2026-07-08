"""Tests für die Dokumenten-Pipelines (ein Hirn, austauschbare Pipeline).

Nutzt ausschließlich SYNTHETISCHE Daten – keine Mandantenunterlagen im Repo.
"""

import openpyxl

from anhangspruefer.pipelines import get_pipeline, Pipeline, HankookPipeline
from anhangspruefer.pipelines.hankook import (
    _extract_hankook_eventualverbindlichkeiten,
    _detect_hankook_type,
    _parse_lst_anhang,
    _parse_lst_beleg,
    _is_hankook_vjv_item,
    TYPE_LEASING,
    TYPE_MIETE,
    TYPE_EVENTUALV,
)
from anhangspruefer.vorjahresvergleich.extractor import AnhangItem


# ---------------------------------------------------------------------------
# Auswahl der Pipeline über den Mandanten (explizit)
# ---------------------------------------------------------------------------
def test_get_pipeline_hankook():
    assert isinstance(get_pipeline("Hankook Tire Austria GmbH"), HankookPipeline)
    assert isinstance(get_pipeline("hankook"), HankookPipeline)


def test_get_pipeline_default_is_standard():
    # Fremder / leerer Mandant -> Standard-Pipeline (nicht die Hankook-Unterklasse)
    assert type(get_pipeline("Accilium")) is Pipeline
    assert type(get_pipeline("")) is Pipeline


# ---------------------------------------------------------------------------
# Rundungstoleranz: Standard 2 Cent, Hankook 0,5 EUR bei ganzzahligem Anhang
# ---------------------------------------------------------------------------
def test_standard_tolerance_is_two_cents():
    assert Pipeline().match_tolerance(100.0) == 0.02


def test_hankook_tolerance_whole_euro():
    hp = HankookPipeline()
    assert hp.match_tolerance(64440.0) == 0.5      # ganze EUR -> Rundung erlaubt
    assert hp.match_tolerance(64440.31) == 0.02    # cent-genau -> streng


# ---------------------------------------------------------------------------
# Hankook-Eventualverbindlichkeiten: Extraktion aus dem Summenblatt
# ---------------------------------------------------------------------------
def _make_zusammenfassung(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Zusammenfassung Test"
    ws.append(["", "", "EVENTUALVERBINDLICHKEITEN"])
    ws.append(["", "", "Hankook", "", "Folgendes Geschäftsjahr", "folgende 5 Geschäftsjahre"])
    ws.append(["", "", "Leasing Warehouse", "", 1007124, 4240500])
    ws.append(["", "", "Rent Office", "", 78927.59, 404727.62])
    ws.append(["", "", "Car lease", "", 64440.31, 191859.13])
    ws.append(["", "", "Total", "", 1150491.9, 4837086.75])
    wb.save(path)


def test_detect_hankook_eventualverbindlichkeiten(tmp_path):
    p = tmp_path / "eventualv.xlsx"
    _make_zusammenfassung(p)
    assert _detect_hankook_type(p) == TYPE_EVENTUALV


def test_extract_hankook_eventualverbindlichkeiten(tmp_path):
    p = tmp_path / "eventualv.xlsx"
    _make_zusammenfassung(p)
    facts = _extract_hankook_eventualverbindlichkeiten(p)

    leasing = [f for f in facts if f.source_type == TYPE_LEASING]
    miete = [f for f in facts if f.source_type == TYPE_MIETE]

    # Car lease -> Leasing (Spalte 'folgendes Geschäftsjahr')
    assert len(leasing) == 1
    assert leasing[0].value == 64440.31

    # Warehouse + Office -> Miete (zwei Fakten, werden vom Hirn summiert)
    assert len(miete) == 2
    assert round(sum(f.value for f in miete), 2) == 1086051.59

    # Total-Zeile wird NICHT als Fakt geführt (nur Komponenten)
    assert all("total" not in f.label.lower() for f in facts)


# ---------------------------------------------------------------------------
# Latente Steuern: Fließtext (Anhang) und Detail-Tabelle (Beleg)
# Synthetische Beträge – keine echten Mandantenzahlen.
# ---------------------------------------------------------------------------
def test_parse_lst_anhang_three_components():
    text = (
        "Zwischen den Wertansätzen bestehen Unterschiedsbeträge bzw. "
        "Steuerlatenzen für den Aktivposten Leasing KFZ in Höhe von EUR 1.000,00, "
        "des Geschäfts-(Firmen-)wertes in Höhe von EUR 2.000,00 und der "
        "Rückstellung für Jubiläumsgelder in Höhe von EUR 300,00. "
        "Rückstellungen ... Jubiläumsgeld 9.999,00 8.888,00"  # Tabelle danach -> darf nicht stören
    )
    by_section = {p.section: p.current_value for p in _parse_lst_anhang(text)}
    assert by_section["LatSteuer_Leasing_KFZ"] == 1000.0
    assert by_section["LatSteuer_Firmenwert"] == 2000.0
    assert by_section["LatSteuer_Jubilaeum"] == 300.0


def test_parse_lst_beleg_takes_fourth_column():
    # Spalten: UGB | StR | Differenz | latente Steuer  -> die 4. Zahl zählt
    text = (
        "Aktivposten Leasing KFZ 0,00 4.000,00 4.000,00 920,00 "
        "Abschreibung Geschäfts-(Firmen-)wert 1.000,00 2.000,00 1.000,00 230,00 "
        "RST für Jubiläumsgeld -100,00 -50,00 50,00 11,50"
    )
    by_type = {f.source_type: f.value for f in _parse_lst_beleg(text, "detail.pdf")}
    assert by_type["hankook_lst_leasing_kfz"] == 920.0
    assert by_type["hankook_lst_firmenwert"] == 230.0
    assert by_type["hankook_lst_jubilaeum"] == 11.5


def test_hankook_section_to_type_has_latente_steuern():
    hp = HankookPipeline()
    assert hp.section_to_type["LatSteuer_Leasing_KFZ"] == "hankook_lst_leasing_kfz"
    assert hp.section_to_type["LatSteuer_Firmenwert"] == "hankook_lst_firmenwert"
    assert hp.section_to_type["LatSteuer_Jubilaeum"] == "hankook_lst_jubilaeum"


# ---------------------------------------------------------------------------
# Modus 1: Filter für echte Kontinuitätsposten (Vorjahresvergleich)
# ---------------------------------------------------------------------------
def _item(label, current, prior, double_row=False):
    return AnhangItem(label=label, page=1, current_values=current,
                      prior_values=prior, double_row=double_row)


def test_vjv_keeps_anlagenspiegel_and_items_with_vorjahr():
    # Anlagenspiegel-Doppelzeile
    assert _is_hankook_vjv_item(_item(
        "Geschäfts-(Firmen-)wert",
        [3251298, 0, 2004968, 0, 1246330],
        [3251298, 0, 1679838, 325130, 1571460],
        double_row=True,
    )) is True
    # Angestellte (Wert mit Vorjahr) – echter Kontinuitätsvergleich
    assert _is_hankook_vjv_item(_item("Angestellte", [23.0], [21.0])) is True
    # einzeiliger Spiegel (>=3 Spalten, kein Vorjahr)
    assert _is_hankook_vjv_item(_item("Rückstellungsspiegel Stand", [100.0, 20.0, 120.0], [])) is True


def test_vjv_drops_nutzungsdauer_and_noise():
    # Nutzungsdauer in JAHREN (kollidiert mit Anlagenspiegel-Label)
    assert _is_hankook_vjv_item(_item("Geschäfts-(Firmen-)wert", [10.0], [])) is False
    assert _is_hankook_vjv_item(_item("Betriebs- und Geschäftsausstattung", [5.0], [])) is False
    # Seitenzahl / Prosa-Zahl
    assert _is_hankook_vjv_item(_item("Geschäftsführer Suk Namkung Seite", [7.0], [])) is False
    assert _is_hankook_vjv_item(_item("konzernweiten Safe Harbour Test", [2025.0], [])) is False


def test_vjv_drops_forward_commitments():
    # Verpflichtungen (folgendes Jahr / 5 Jahre) -> Modus 2, nicht Kontinuität
    assert _is_hankook_vjv_item(_item("Verpflichtungen aus Leasingverträgen", [64440.0], [191859.0])) is False
    assert _is_hankook_vjv_item(_item("Verpflichtungen aus Mietverträgen", [1086052.0], [4645228.0])) is False
