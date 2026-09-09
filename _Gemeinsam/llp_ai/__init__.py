"""Zentraler KI-Zugang der LLP-Tools (nur Microsoft Foundry)."""

from .company_ai import (
    CompanyAIError,
    active_provider,
    ask_ai,
    ask_json,
    describe_status,
    get_config,
    is_ai_enabled,
    is_ai_ready,
)

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
