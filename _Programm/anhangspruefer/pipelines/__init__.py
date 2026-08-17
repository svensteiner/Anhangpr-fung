"""
Dokumenten-Pipelines je Mandant.

Ein gemeinsames "Hirn", austauschbare Pipeline: Die Auswahl erfolgt EXPLIZIT
über den in der App eingetragenen Mandanten (`get_pipeline(mandant)`).
Unbekannter/leerer Mandant -> Standard-Pipeline (bisheriges Verhalten).

Mandantenprofile sind PLUGINS und liegen NICHT in diesem Repository, sondern
neben dem Programm unter ``Klienten/<Mandant>/pipeline.py``. Grund: Ein
Mandantenprofil verrät, wen man prüft, und wie dessen Unterlagen aufgebaut
sind – beides fällt unter die Verschwiegenheitspflicht. Der Klientenordner ist
per ``.gitignore`` ausgeschlossen.

Neuen Mandanten anstöpseln:
    1. Ordner ``Klienten/<Mandant>/`` anlegen (Name = Eintrag im Feld "Mandant").
    2. Darin ``pipeline.py`` mit einer ``Pipeline``-Unterklasse ablegen.
    3. Werkzeug neu starten – das Plugin wird beim Start geladen.

Der Vertrag eines Plugins steht in :mod:`anhangspruefer.pipelines.loader`.
"""

from __future__ import annotations

from .base import Pipeline
from .loader import PluginBefund, lade_plugins

# Zur Laufzeit gefüllt durch `register_plugins()` (ruft die App beim Start).
# Schlüssel = Teilstring (klein) des Mandantennamens -> Pipeline-Klasse.
_REGISTRY: dict[str, type[Pipeline]] = {}

# Standard-Pipeline: entweder die neutrale Basisklasse oder eine lokale
# Ergänzung aus ``Klienten/_Standard/pipeline.py``.
_STANDARD: type[Pipeline] = Pipeline

# Ladefehler des letzten `register_plugins()`-Aufrufs (Klartext, für die App).
_FEHLER: list[str] = []

# Durchsuchtes Verzeichnis, für Diagnose in /healthz.
_VERZEICHNIS: str | None = None


def register_plugins(basis_verzeichnis) -> PluginBefund:
    """Lädt die Mandanten-Plugins aus dem Klientenordner und ersetzt die Registry.

    Idempotent: ein erneuter Aufruf liest neu ein (z.B. nach dem Ablegen eines
    neuen Profils). Liefert den Befund zurück, damit die App Anzahl und Fehler
    anzeigen kann.
    """
    global _REGISTRY, _STANDARD, _FEHLER, _VERZEICHNIS
    befund = lade_plugins(basis_verzeichnis)
    _REGISTRY = befund.registry
    _STANDARD = befund.standard or Pipeline
    _FEHLER = list(befund.fehler)
    _VERZEICHNIS = befund.verzeichnis
    return befund


def get_pipeline(mandant: str) -> Pipeline:
    """Wählt die Pipeline anhand des Mandantennamens (Teilstring-Match).

    Passt kein Plugin, greift die Standard-Pipeline – wie bisher. Der Name der
    tatsächlich verwendeten Pipeline steht in ``pipeline.name`` und wird im
    Ergebnis ausgewiesen, damit ein Tippfehler im Mandantenfeld auffällt.
    """
    key = (mandant or "").strip().lower()
    if key:
        # Längster Schlüssel zuerst: "xy holding" schlägt "xy", sonst
        # entscheidet die Einlesereihenfolge und das Ergebnis wäre zufällig.
        for name in sorted(_REGISTRY, key=len, reverse=True):
            if name in key:
                return _REGISTRY[name]()
    return _STANDARD()


def available_pipelines() -> list[str]:
    """Namen der verfügbaren Profile – ohne Mandantenschlüssel offenzulegen."""
    namen = {cls.name for cls in _REGISTRY.values()}
    return [_STANDARD.name] + sorted(namen - {_STANDARD.name})


def plugin_errors() -> list[str]:
    """Ladefehler des letzten `register_plugins()`-Aufrufs."""
    return list(_FEHLER)


def plugin_directory() -> str | None:
    return _VERZEICHNIS


__all__ = [
    "Pipeline",
    "PluginBefund",
    "get_pipeline",
    "available_pipelines",
    "register_plugins",
    "plugin_errors",
    "plugin_directory",
]
