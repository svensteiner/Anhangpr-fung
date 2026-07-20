"""
Dokumenten-Pipelines je Mandant.

Ein gemeinsames "Hirn", austauschbare Pipeline: Die Auswahl erfolgt EXPLIZIT
über den in der App eingetragenen Mandanten (`get_pipeline(mandant)`).
Unbekannter/leerer Mandant -> Standard-Pipeline (bisheriges Verhalten).

Neuen Mandanten ergänzen:
    1. Datei `<mandant>.py` mit einer `Pipeline`-Unterklasse anlegen.
    2. Hier in `_REGISTRY` unter einem Namensschlüssel eintragen.
"""

from __future__ import annotations

from .base import Pipeline
from .hankook import HankookPipeline
from .syngroup import SyngroupPipeline

# Schlüssel = Teilstring (klein) des Mandantennamens -> Pipeline-Klasse.
_REGISTRY: dict[str, type[Pipeline]] = {
    "hankook": HankookPipeline,
    "syngroup": SyngroupPipeline,
}


def get_pipeline(mandant: str) -> Pipeline:
    """Wählt die Pipeline anhand des Mandantennamens (Teilstring-Match)."""
    key = (mandant or "").strip().lower()
    if key:
        for name, cls in _REGISTRY.items():
            if name in key:
                return cls()
    return Pipeline()


def available_pipelines() -> list[str]:
    return ["standard"] + list(_REGISTRY.keys())


__all__ = [
    "Pipeline",
    "HankookPipeline",
    "SyngroupPipeline",
    "get_pipeline",
    "available_pipelines",
]
