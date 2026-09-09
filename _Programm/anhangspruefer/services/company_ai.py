"""Kompatibilitätsimport zum zentralen LLP-Foundry-Layer.

Suche (in dieser Reihenfolge):
  1. Umgebung ``LLP_SHARED_AI_ROOT`` (wenn gesetzt: nur dieser Ordner)
  2. ``K:\\LLP Wirtschaftsprüfung\\AI Tools\\_Gemeinsam``
  3. ``_Gemeinsam`` neben dem Tool und eine Ebene darüber

Dieses Modul enthält keine Schlüssel. Ist der Layer nicht erreichbar,
bleibt die Prüfung bei der Heuristik.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_SHARED_ROOT = Path(r"K:\LLP Wirtschaftsprüfung\AI Tools\_Gemeinsam")
_TOOL_ROOT = Path(__file__).resolve().parents[3]


def _candidate_roots() -> list[Path]:
    env = os.environ.get("LLP_SHARED_AI_ROOT")
    if env:
        return [Path(env)]
    return [
        DEFAULT_SHARED_ROOT,
        _TOOL_ROOT / "_Gemeinsam",
        _TOOL_ROOT.parent / "_Gemeinsam",
    ]


def _prepare_path() -> None:
    for root in _candidate_roots():
        if root.is_dir() and str(root) not in sys.path:
            sys.path.insert(0, str(root))


class CompanyAIError(Exception):
    """KI-Layer nicht nutzbar (aus, falsch konfiguriert oder nicht erreichbar)."""


def _load():
    _prepare_path()
    try:
        from llp_ai.company_ai import (  # type: ignore
            active_provider,
            ask_ai,
            ask_json,
            describe_status,
            get_config,
            is_ai_enabled,
            is_ai_ready,
        )
    except Exception:
        return None
    return {
        "ask_ai": ask_ai,
        "ask_json": ask_json,
        "describe_status": describe_status,
        "get_config": get_config,
        "is_ai_enabled": is_ai_enabled,
        "is_ai_ready": is_ai_ready,
        "active_provider": active_provider,
    }


_LAYER = _load()


def _reload() -> None:
    global _LAYER
    _LAYER = _load()


def describe_status() -> dict:
    if _LAYER is None:
        return {
            "enabled": False,
            "provider_ok": False,
            "endpoint_gesetzt": False,
            "deployment_gesetzt": False,
            "schluessel_gesetzt": False,
            "bereit": False,
            "hinweis": "Der zentrale Foundry-Layer ist nicht erreichbar. Prüfung ohne Modell.",
        }
    try:
        data = _LAYER["describe_status"]()
    except Exception:
        return {
            "enabled": False,
            "provider_ok": False,
            "endpoint_gesetzt": False,
            "deployment_gesetzt": False,
            "schluessel_gesetzt": False,
            "bereit": False,
            "hinweis": "Foundry-Status konnte nicht gelesen werden. Prüfung ohne Modell.",
        }
    if not isinstance(data, dict):
        return {
            "enabled": False,
            "provider_ok": False,
            "endpoint_gesetzt": False,
            "deployment_gesetzt": False,
            "schluessel_gesetzt": False,
            "bereit": False,
            "hinweis": "Foundry-Status war ungültig. Prüfung ohne Modell.",
        }
    return data


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
    "describe_status",
    "get_config",
    "is_ai_enabled",
    "is_ai_ready",
]
