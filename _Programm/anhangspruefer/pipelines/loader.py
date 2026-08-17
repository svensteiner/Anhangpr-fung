"""
Mandanten-Plugins von aussen an das Hirn anstöpseln.

Warum ausserhalb des Repositories
=================================
Eine Mandanten-Pipeline verrät zwangsläufig, WEN man prüft, und meist auch, wie
die Unterlagen dieses Mandanten aufgebaut sind (Briefkopf, Blattnamen,
Aktenzeichen). Das fällt unter die Verschwiegenheitspflicht und darf deshalb
nicht ins Repository. Das Hirn (Prüf- und Vergleichslogik) bleibt versioniert
und mandantenneutral; die Plugins liegen daneben im Klientenordner, der per
``.gitignore`` ausgeschlossen ist.

Ablage
======
    Klienten/
      <Mandant>/pipeline.py     <- Plugin dieses Mandanten
      _Standard/pipeline.py     <- optional: ergänzt das Standardprofil für
                                   ALLE Mandanten ohne eigenes Plugin
      _LIESMICH.txt             <- Unterstrich = kein Mandant

Ordner, die mit ``_`` beginnen, gelten nicht als Mandant. Der Sonderordner
``_Standard`` ersetzt die Standard-Pipeline, die greift, wenn kein Plugin auf
den eingetragenen Mandanten passt.

Vertrag eines Plugins
=====================
``pipeline.py`` definiert genau eine Unterklasse von
:class:`anhangspruefer.pipelines.base.Pipeline`. Alles andere ist optional:

    from anhangspruefer.pipelines.base import Pipeline

    class MeinMandantPipeline(Pipeline):
        name = "mandant-xy"                     # erscheint im Ergebnis
        mandant_keys = ("xy gmbh", "xy")        # Teilstrings des Mandantenfelds
        extra_noise_patterns = (r"Briefkopf XY",)
        hr_entity_codes = ("XY", "100")

Fehlt ``mandant_keys``, wird der Ordnername als Schlüssel verwendet. Weil das
Plugin per Dateipfad geladen wird, sind RELATIVE Importe (``from ..x import y``)
nicht möglich – immer absolut importieren (``from anhangspruefer.x import y``).

Fehlerverhalten
===============
Ein defektes Plugin darf das Werkzeug nicht lahmlegen, aber auch nicht
stillschweigend übergangen werden: Ladefehler werden gesammelt und
zurückgegeben, damit die App sie dem Anwender zeigen kann. Sonst prüft er
ahnungslos mit dem Standardprofil weiter.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .base import Pipeline

#: Dateiname, unter dem ein Plugin je Mandantenordner erwartet wird.
PLUGIN_DATEINAME = "pipeline.py"

#: Ordner, dessen Plugin das Standardprofil für alle Mandanten ohne eigenes
#: Plugin ersetzt.
STANDARD_ORDNER = "_Standard"


@dataclass
class PluginBefund:
    """Ergebnis eines Ladevorgangs."""

    #: Schlüssel (klein) -> Pipeline-Klasse
    registry: dict = field(default_factory=dict)
    #: Standard-Pipeline-Klasse (aus ``_Standard``), sonst None
    standard: Optional[type] = None
    #: Klartext-Meldungen zu Plugins, die NICHT geladen werden konnten
    fehler: list = field(default_factory=list)
    #: Durchsuchtes Verzeichnis (für Diagnose), None wenn nicht vorhanden
    verzeichnis: Optional[str] = None

    @property
    def anzahl(self) -> int:
        return len(self.registry)


def _pipeline_klasse(modul, quelle: str) -> type:
    """Findet die Pipeline-Unterklasse in einem geladenen Plugin-Modul."""
    kandidaten = [
        obj for _, obj in inspect.getmembers(modul, inspect.isclass)
        if issubclass(obj, Pipeline) and obj is not Pipeline
        # Nur im Plugin selbst definierte Klassen – importierte Basisklassen
        # anderer Plugins zählen nicht mit.
        and obj.__module__ == modul.__name__
    ]
    if not kandidaten:
        raise ValueError(
            f"{quelle}: keine Pipeline-Unterklasse gefunden. Erwartet wird "
            f"'class XyzPipeline(Pipeline):' mit "
            f"'from anhangspruefer.pipelines.base import Pipeline'."
        )
    if len(kandidaten) > 1:
        namen = ", ".join(sorted(k.__name__ for k in kandidaten))
        raise ValueError(
            f"{quelle}: mehrere Pipeline-Klassen gefunden ({namen}). "
            f"Pro Plugin ist genau eine zulässig."
        )
    return kandidaten[0]


def _lade_modul(pfad: Path, modulname: str):
    """Lädt eine Python-Datei als Modul – ohne sie im Paket zu haben."""
    spec = importlib.util.spec_from_file_location(modulname, str(pfad))
    if spec is None or spec.loader is None:
        raise ImportError(f"Modul konnte nicht vorbereitet werden: {pfad}")
    modul = importlib.util.module_from_spec(spec)
    # Vor dem Ausführen registrieren, damit dataclasses/Typauflösung im Plugin
    # das eigene Modul finden.
    sys.modules[modulname] = modul
    try:
        spec.loader.exec_module(modul)
    except BaseException:
        sys.modules.pop(modulname, None)
        raise
    return modul


def lade_plugins(basis_verzeichnis) -> PluginBefund:
    """Durchsucht ``basis_verzeichnis`` nach Mandanten-Plugins.

    Args:
        basis_verzeichnis: der Klientenordner (``Klienten/``).

    Returns:
        :class:`PluginBefund`. Existiert das Verzeichnis nicht, ist der Befund
        leer – das ist kein Fehler, sondern der Normalfall einer frischen
        Installation ohne Mandantenprofile.
    """
    befund = PluginBefund()
    if basis_verzeichnis is None:
        return befund

    basis = Path(basis_verzeichnis)
    if not basis.is_dir():
        return befund
    befund.verzeichnis = str(basis)

    for ordner in sorted(basis.iterdir(), key=lambda p: p.name.lower()):
        if not ordner.is_dir():
            continue
        plugin = ordner / PLUGIN_DATEINAME
        if not plugin.is_file():
            continue

        ist_standard = ordner.name == STANDARD_ORDNER
        if ordner.name.startswith("_") and not ist_standard:
            continue                      # Unterstrich = kein Mandant

        quelle = f"{ordner.name}/{PLUGIN_DATEINAME}"
        try:
            modul = _lade_modul(plugin, f"_mandantenplugin_{ordner.name.lower()}")
            cls = _pipeline_klasse(modul, quelle)
        except BaseException as e:
            # Bewusst BaseException: ein Plugin mit SyntaxError oder einem
            # fehlgeschlagenen Import darf das Werkzeug nicht mitreissen.
            befund.fehler.append(f"{quelle}: {type(e).__name__}: {e}")
            continue

        if ist_standard:
            befund.standard = cls
            continue

        schluessel = tuple(k.strip().lower() for k in (cls.mandant_keys or ()) if k.strip())
        if not schluessel:
            schluessel = (ordner.name.strip().lower(),)
        for k in schluessel:
            vorher = befund.registry.get(k)
            if vorher is not None and vorher is not cls:
                befund.fehler.append(
                    f"{quelle}: Schlüssel '{k}' ist bereits von "
                    f"{vorher.__name__} belegt – das zuletzt geladene Plugin gilt."
                )
            befund.registry[k] = cls

    return befund
