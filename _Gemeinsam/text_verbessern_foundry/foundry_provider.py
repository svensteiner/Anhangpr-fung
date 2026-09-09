"""Thorough rewrite via the central LLP Foundry layer (llp_ai)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from app.models import SemanticConstraints, TransformOptions
from app.providers.base import EditorialProvider, ProviderError
from app.providers.local import LocalRuleProvider


def _shared_roots() -> list[Path]:
    env = os.environ.get("LLP_SHARED_AI_ROOT")
    if env:
        return [Path(env)]
    here = Path(__file__).resolve()
    return [
        Path(r"K:\LLP Wirtschaftsprüfung\AI Tools\_Gemeinsam"),
        here.parents[2] / "_Gemeinsam",
        here.parents[3] / "_Gemeinsam" if len(here.parents) > 3 else Path(),
    ]


def _load_layer():
    for root in _shared_roots():
        if root.is_dir() and str(root) not in sys.path:
            sys.path.insert(0, str(root))
    try:
        from llp_ai.company_ai import ask_ai, is_ai_ready  # type: ignore
    except Exception:
        return None
    return {"ask_ai": ask_ai, "is_ai_ready": is_ai_ready}


_LAYER = _load_layer()


def foundry_ready() -> bool:
    if _LAYER is None:
        return False
    try:
        return bool(_LAYER["is_ai_ready"]())
    except Exception:
        return False


class FoundryEditorialProvider(EditorialProvider):
    """Microsoft Foundry only. No silent switch to Ollama or another vendor."""

    name = "foundry"
    is_remote = True

    def rewrite(self, text: str, constraints: SemanticConstraints, options: TransformOptions) -> str:
        if _LAYER is None or not foundry_ready():
            raise ProviderError(
                "Foundry ist nicht eingerichtet. Die sichere lokale Fassung bleibt verfügbar.",
                code="provider_unavailable",
            )
        mandatory = list(dict.fromkeys(
            list(constraints.names) + list(constraints.protected_terms)
        ))
        prompt = (
            "Act as a careful professional editor. Return only the rewritten text. "
            f"Tone: {options.tone.value}; strength: {options.rewrite_strength.value}; "
            f"language: {options.language.value}. Preserve names and facts. "
            f"Mandatory exact strings: {mandatory}\n\n<TEXT>\n{text}\n</TEXT>"
        )
        try:
            rewritten = _LAYER["ask_ai"](prompt)
        except Exception as exc:
            raise ProviderError(
                "Foundry-Anfrage fehlgeschlagen. Kein Wechsel auf ein anderes Modell.",
                code="provider_unavailable",
            ) from exc
        if not isinstance(rewritten, str) or not rewritten.strip():
            raise ProviderError("Foundry-Antwort war leer.", code="invalid_model_response")
        return rewritten.strip()


class HybridFoundryProvider(EditorialProvider):
    name = "rules+foundry"

    def __init__(self) -> None:
        self.rules = LocalRuleProvider()
        self.foundry = FoundryEditorialProvider()

    def rewrite(self, text: str, constraints: SemanticConstraints, options: TransformOptions) -> str:
        cleaned = self.rules.rewrite(text, constraints, options)
        return self.foundry.rewrite(cleaned, constraints, options)
