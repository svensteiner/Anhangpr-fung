"""Tests für die Standard-Pipeline und die Auswahl über den Mandanten.

Mandantenspezifische Profile sind PLUGINS und liegen ausserhalb des
Repositories (``Klienten/<Mandant>/pipeline.py``); ihre Tests liegen dort
daneben. Hier wird deshalb ausschliesslich das mandantenneutrale Verhalten
geprüft – mit synthetischen Namen.
"""

import re

from anhangspruefer.pipelines import (
    Pipeline,
    available_pipelines,
    get_pipeline,
    register_plugins,
)


# ---------------------------------------------------------------------------
# Auswahl der Pipeline über den Mandanten (explizit)
# ---------------------------------------------------------------------------
def test_ohne_plugins_immer_standard():
    """Frische Installation ohne Mandantenprofile -> immer Standard."""
    register_plugins(None)
    assert type(get_pipeline("")) is Pipeline
    assert type(get_pipeline("Irgendeine GmbH")) is Pipeline
    assert available_pipelines() == ["standard"]


def test_fehlendes_verzeichnis_ist_kein_fehler(tmp_path):
    befund = register_plugins(tmp_path / "gibt_es_nicht")
    assert befund.anzahl == 0
    assert befund.fehler == []
    assert type(get_pipeline("x")) is Pipeline


# ---------------------------------------------------------------------------
# Standard-Pipeline: Verhalten wie bisher
# ---------------------------------------------------------------------------
def test_standard_tolerance_is_two_cents():
    assert Pipeline().match_tolerance(100.0) == 0.02


def test_standard_hat_keine_mandantenspezifika():
    """Das Hirn selbst darf keine mandantenidentifizierenden Angaben tragen."""
    p = Pipeline()
    assert p.extra_noise_patterns == ()
    assert p.hr_entity_codes == ()
    assert p.mandant_keys == ()
    assert p.compiled_noise() == ()


def test_standard_section_to_type_unveraendert():
    assert Pipeline().section_to_type == {
        "Haftungsverhaeltnisse": "bank_guarantees",
        "Arbeitnehmer": "hr_employees",
    }


# ---------------------------------------------------------------------------
# Der Hook für Dokument-Möblierung (Briefkopf, Kanzleiname, Aktenzeichen)
# ---------------------------------------------------------------------------
def test_compiled_noise_ist_case_insensitive():
    class Profil(Pipeline):
        extra_noise_patterns = (r"^\s*MUSTER\s*&\s*PARTNER",)

    muster = Profil().compiled_noise()
    assert len(muster) == 1
    assert muster[0].search("  muster & partner steuerberatung")


def test_extra_noise_filtert_briefkopfzeile():
    """Ein Briefkopf darf nicht als Bilanzposten durchgehen."""
    from anhangspruefer.vorjahresvergleich.extractor import _is_noise

    briefkopf = "MUSTER & PARTNER 100,00"
    assert _is_noise(briefkopf) is False          # ohne Profil: kein Rauschen
    assert _is_noise(briefkopf, (re.compile(r"MUSTER\s*&\s*PARTNER", re.I),)) is True


def test_gemeinsame_noise_liste_bleibt_wirksam():
    """Die neutralen Muster (Leerzeile, 'Anhang', 'EUR EUR') bleiben im Hirn."""
    from anhangspruefer.vorjahresvergleich.extractor import _is_noise

    assert _is_noise("   ") is True
    assert _is_noise("Anhang") is True
    assert _is_noise("EUR EUR") is True
    assert _is_noise("Sonstige Rueckstellungen 34.634,94") is False
