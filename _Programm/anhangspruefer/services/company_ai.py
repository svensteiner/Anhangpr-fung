"""Kompatibilitätsimport zum zentralen LLP-Foundry-Layer.

Der Zugang liegt in ``K:\\LLP Wirtschaftsprüfung\\AI Tools\\_Gemeinsam\\llp_ai``.
Dieses Modul enthält weder Schlüssel noch eigene Netzlogik. Ist der Layer
nicht erreichbar, bleibt die Prüfung bei der Heuristik.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_SHARED_ROOT = Path(r"K:\LLP Wirtschaftsprüfung\AI Tools\_Gemeinsam")
_shared = Path(os.environ.get("LLP_SHARED_AI_ROOT", DEFAULT_SHARED_ROOT))
if _shared.is_dir() and str(_shared) not in sys.path:
    sys.path.insert(0, str(_shared))


class CompanyAIError(Exception):
    """KI-Layer nicht nutzbar (aus, falsch konfiguriert oder nicht erreichbar)."""


def _load():
    try:
        from llp_ai.company_ai import (  # type: ignore
            active_provider,
            ask_ai,
            ask_json,
            get_config,
            is_ai_enabled,
            is_ai_ready,
        )
    except Exception:
        return None
    return {
        "ask_ai": ask_ai,
        "ask_json": ask_json,
        "get_config": get_config,
        "is_ai_enabled": is_ai_enabled,
        "is_ai_ready": is_ai_ready,
        "active_provider": active_provider,
    }


_LAYER = _load()


def is_ai_ready() -> bool:
    if _LAYER is None:
        return False
    try:
        return bool(_LAYER["is_ai_ready"]())
    except Exception:
        return False


def is_ai_enabled() -> bool:
    if _LAYER is None:
        return False
    try:
        return bool(_LAYER["is_ai_enabled"]())
    except Exception:
        return False


def ask_json(*args, **kwargs):
    if _LAYER is None:
        raise CompanyAIError("Der zentrale Foundry-Layer ist nicht erreichbar.")
    try:
        return _LAYER["ask_json"](*args, **kwargs)
    except Exception as exc:
        raise CompanyAIError("Foundry-Anfrage fehlgeschlagen.") from exc


def ask_ai(*args, **kwargs):
    if _LAYER is None:
        raise CompanyAIError("Der zentrale Foundry-Layer ist nicht erreichbar.")
    try:
        return _LAYER["ask_ai"](*args, **kwargs)
    except Exception as exc:
        raise CompanyAIError("Foundry-Anfrage fehlgeschlagen.") from exc


def get_config():
    if _LAYER is None:
        raise CompanyAIError("Der zentrale Foundry-Layer ist nicht erreichbar.")
    return _LAYER["get_config"]()


def active_provider():
    if _LAYER is None:
        return type("P", (), {"name": "", "label": ""})()
    try:
        return _LAYER["active_provider"]()
    except Exception:
        return type("P", (), {"name": "", "label": ""})()


__all__ = [
    "CompanyAIError",
    "active_provider",
    "ask_ai",
    "ask_json",
    "get_config",
    "is_ai_enabled",
    "is_ai_ready",
]
