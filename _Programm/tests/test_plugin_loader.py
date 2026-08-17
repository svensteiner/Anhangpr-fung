"""Mandanten-Plugins anstöpseln: Laden, Auswahl, Fehlerverhalten.

Alle Plugins in diesen Tests werden zur Laufzeit synthetisch erzeugt – es
werden keine echten Mandantenprofile gelesen.
"""

import openpyxl
import pytest

from anhangspruefer.pipelines import (
    Pipeline,
    available_pipelines,
    get_pipeline,
    plugin_directory,
    plugin_errors,
    register_plugins,
)
from anhangspruefer.pipelines.loader import lade_plugins


@pytest.fixture(autouse=True)
def _registry_zuruecksetzen():
    """Kein Test darf die Registry für den nächsten stehen lassen."""
    yield
    register_plugins(None)


def _plugin(basis, ordner: str, inhalt: str):
    d = basis / ordner
    d.mkdir(parents=True, exist_ok=True)
    (d / "pipeline.py").write_text(inhalt, encoding="utf-8")
    return d


_EINFACH = '''
from anhangspruefer.pipelines.base import Pipeline

class MusterPipeline(Pipeline):
    name = "muster"
    mandant_keys = ("muster gmbh", "muster")
    extra_noise_patterns = (r"^\\s*MUSTERKOPF",)
    hr_entity_codes = ("MU", "700")

    def match_tolerance(self, anhang_value):
        return 0.5
'''


# ---------------------------------------------------------------------------
# Laden und Auswahl
# ---------------------------------------------------------------------------
def test_plugin_wird_geladen_und_ausgewaehlt(tmp_path):
    _plugin(tmp_path, "Muster", _EINFACH)
    befund = register_plugins(tmp_path)

    assert befund.anzahl == 2                      # zwei Schlüssel, ein Profil
    assert befund.fehler == []
    assert plugin_directory() == str(tmp_path)

    p = get_pipeline("Muster GmbH")
    assert p.name == "muster"
    assert p.match_tolerance(100.0) == 0.5
    assert p.hr_entity_codes == ("MU", "700")
    assert available_pipelines() == ["standard", "muster"]


def test_unbekannter_mandant_bleibt_standard(tmp_path):
    _plugin(tmp_path, "Muster", _EINFACH)
    register_plugins(tmp_path)
    assert type(get_pipeline("Ganz Andere AG")) is Pipeline
    assert type(get_pipeline("")) is Pipeline


def test_ordnername_als_schluessel_wenn_keine_keys(tmp_path):
    _plugin(tmp_path, "Beispielmandant", '''
from anhangspruefer.pipelines.base import Pipeline

class OhneKeys(Pipeline):
    name = "beispiel"
''')
    register_plugins(tmp_path)
    assert get_pipeline("Beispielmandant").name == "beispiel"
    assert get_pipeline("beispielmandant AG").name == "beispiel"


def test_laengster_schluessel_gewinnt(tmp_path):
    """'muster holding' muss 'muster' schlagen – sonst entscheidet der Zufall."""
    _plugin(tmp_path, "A_Muster", '''
from anhangspruefer.pipelines.base import Pipeline

class Kurz(Pipeline):
    name = "kurz"
    mandant_keys = ("muster",)
''')
    _plugin(tmp_path, "B_MusterHolding", '''
from anhangspruefer.pipelines.base import Pipeline

class Lang(Pipeline):
    name = "lang"
    mandant_keys = ("muster holding",)
''')
    register_plugins(tmp_path)
    assert get_pipeline("Muster Holding GmbH").name == "lang"
    assert get_pipeline("Muster GmbH").name == "kurz"


def test_unterstrich_ordner_ist_kein_mandant(tmp_path):
    _plugin(tmp_path, "_Notizen", _EINFACH)
    befund = register_plugins(tmp_path)
    assert befund.anzahl == 0
    assert type(get_pipeline("Muster GmbH")) is Pipeline


def test_ordner_ohne_pipeline_datei_wird_uebergangen(tmp_path):
    (tmp_path / "NurUnterlagen").mkdir()
    (tmp_path / "NurUnterlagen" / "anhang.pdf").write_bytes(b"%PDF-1.4")
    befund = register_plugins(tmp_path)
    assert befund.anzahl == 0 and befund.fehler == []


# ---------------------------------------------------------------------------
# _Standard: ergänzt das Profil für alle Mandanten ohne eigenes Plugin
# ---------------------------------------------------------------------------
def test_standard_ordner_ersetzt_die_standardpipeline(tmp_path):
    _plugin(tmp_path, "_Standard", '''
from anhangspruefer.pipelines.base import Pipeline

class StandardProfil(Pipeline):
    name = "standard"
    extra_noise_patterns = (r"^\\s*KANZLEIKOPF",)
    hr_entity_codes = ("AB",)
''')
    register_plugins(tmp_path)

    p = get_pipeline("Beliebiger Mandant")
    assert p.name == "standard"
    assert p.hr_entity_codes == ("AB",)
    assert p.compiled_noise()[0].search("  kanzleikopf gmbh")


def test_eigenes_plugin_schlaegt_standardordner(tmp_path):
    _plugin(tmp_path, "_Standard", '''
from anhangspruefer.pipelines.base import Pipeline

class StandardProfil(Pipeline):
    name = "standard"
    hr_entity_codes = ("AB",)
''')
    _plugin(tmp_path, "Muster", _EINFACH)
    register_plugins(tmp_path)

    assert get_pipeline("Muster GmbH").hr_entity_codes == ("MU", "700")
    assert get_pipeline("Andere AG").hr_entity_codes == ("AB",)


# ---------------------------------------------------------------------------
# Fehlerverhalten: nicht lahmlegen, aber auch nicht verschweigen
# ---------------------------------------------------------------------------
def test_syntaxfehler_legt_das_werkzeug_nicht_lahm(tmp_path):
    _plugin(tmp_path, "Kaputt", "class Pipeline(:\n    pass\n")
    _plugin(tmp_path, "Muster", _EINFACH)
    befund = register_plugins(tmp_path)

    # Das intakte Plugin laeuft weiter ...
    assert get_pipeline("Muster GmbH").name == "muster"
    # ... aber der Ausfall wird gemeldet, nicht verschluckt.
    assert len(befund.fehler) == 1
    assert "Kaputt/pipeline.py" in befund.fehler[0]
    assert "SyntaxError" in befund.fehler[0]
    assert befund.fehler == plugin_errors()


def test_fehlender_import_wird_gemeldet(tmp_path):
    _plugin(tmp_path, "Kaputt", "import gibt_es_ganz_sicher_nicht\n")
    befund = register_plugins(tmp_path)
    assert len(befund.fehler) == 1
    assert "ModuleNotFoundError" in befund.fehler[0]


def test_plugin_ohne_pipeline_klasse_wird_gemeldet(tmp_path):
    _plugin(tmp_path, "Leer", "WERT = 42\n")
    befund = register_plugins(tmp_path)
    assert len(befund.fehler) == 1
    assert "keine Pipeline-Unterklasse" in befund.fehler[0]


def test_plugin_mit_zwei_klassen_wird_gemeldet(tmp_path):
    _plugin(tmp_path, "Zwei", '''
from anhangspruefer.pipelines.base import Pipeline

class EinsPipeline(Pipeline):
    name = "eins"

class ZweiPipeline(Pipeline):
    name = "zwei"
''')
    befund = register_plugins(tmp_path)
    assert len(befund.fehler) == 1
    assert "mehrere Pipeline-Klassen" in befund.fehler[0]


def test_doppelt_belegter_schluessel_wird_gemeldet(tmp_path):
    for ordner, name in (("A", "a"), ("B", "b")):
        _plugin(tmp_path, ordner, f'''
from anhangspruefer.pipelines.base import Pipeline

class P{name.upper()}(Pipeline):
    name = "{name}"
    mandant_keys = ("gleicher schluessel",)
''')
    befund = register_plugins(tmp_path)
    assert any("bereits von" in f for f in befund.fehler)


def test_lade_plugins_ohne_seiteneffekt(tmp_path):
    """lade_plugins() liest nur – erst register_plugins() schaltet um."""
    _plugin(tmp_path, "Muster", _EINFACH)
    register_plugins(None)
    befund = lade_plugins(tmp_path)
    assert befund.anzahl == 2
    assert type(get_pipeline("Muster GmbH")) is Pipeline   # noch nicht aktiv


# ---------------------------------------------------------------------------
# Der Hook wirkt wirklich bis in die Extraktion
# ---------------------------------------------------------------------------
def test_hr_entity_codes_wirken_in_der_belegextraktion(tmp_path):
    """Die Zeile der geprüften Gesellschaft schlägt die Gesamtzeile."""
    xlsx = tmp_path / "personalstand.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Zusammenfassung"
    ws.append(["Gesellschaft", "Köpfe"])
    ws.append(["MU", 12])
    ws.append(["Gesamtergebnis", 99])
    wb.save(xlsx)

    _plugin(tmp_path, "Muster", _EINFACH)
    register_plugins(tmp_path)

    eigen = get_pipeline("Muster GmbH").extract_beleg_facts(xlsx, "hr_employees")
    assert len(eigen) == 1 and eigen[0].value == 12.0

    # Ohne Kennung bleibt nur die Gesamtzeile.
    standard = Pipeline().extract_beleg_facts(xlsx, "hr_employees")
    assert len(standard) == 1 and standard[0].value == 99.0
