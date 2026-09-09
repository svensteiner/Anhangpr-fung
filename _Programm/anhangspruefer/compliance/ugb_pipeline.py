"""Zweistufige UGB-Inhaltsprüfung (Modus 3).

Teil 1 – Eingrenzung nach Rechtsform und Größenklasse.
Teil 2 – Nur den Rest gegen den Anhang; optional Foundry.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .. import __version__
from ..models.checklist import Checklist
from ..models.enums import ComplianceStatus
from ..models.finding import Finding, ReviewResult
from ..parsers.document_text import load_page_texts
from ..services.company_ai import is_ai_ready
from .knowledge.llm_matcher import (
    FoundryLLM,
    apply_heuristic_fundstellen,
    paragraphs_from_pages,
    refine_binaer,
)
from .knowledge.relevance import apply_company_scope, apply_topic_relevance, require_company_profile


def blank_review_result(checklist: Checklist, document_name: str) -> ReviewResult:
    result = ReviewResult(
        document_name=document_name,
        checklist_name=checklist.name,
        review_timestamp=datetime.now(),
        tool_version=__version__,
    )
    for item in checklist.items:
        result.add_finding(Finding(
            checklist_item_id=item.item_id,
            status=ComplianceStatus.NOT_ASSESSABLE,
            ugb_references=list(item.ugb_references),
        ))
    return result


def rest_zu_pruefen(result: ReviewResult) -> int:
    """Fragen, die nach Teil 1 und Teil 2a noch nicht n. a. sind."""
    return sum(
        1
        for finding in result.findings
        if finding.status != ComplianceStatus.NOT_APPLICABLE
    )


def format_review_hinweis(
    legal_form: str,
    size_class: str,
    teil1_zu_pruefen: int,
    rest: int,
    gesamt: int,
) -> str:
    form_txt = "GmbH" if legal_form == "gmbh" else "AG"
    size_txt = {"klein": "klein", "mittel": "mittel", "gross": "groß"}[size_class]
    return (
        f"Für {form_txt} {size_txt}: Teil 1 {teil1_zu_pruefen} Fragen (Rechtsgrund), "
        f"Teil 2 Rest {rest} von {gesamt} geprüft."
    )


def review_checklist(
    anhang_path: Path,
    checklist: Checklist,
    legal_form: str,
    size_class: str,
    ki_max_seconds: float = 180,
) -> tuple[ReviewResult, dict]:
    legal_form, size_class = require_company_profile(legal_form, size_class)
    anhang_path = Path(anhang_path)
    try:
        pages = load_page_texts(anhang_path)
    except ValueError:
        raise
    except Exception as exc:
        raise RuntimeError("Der Anhang konnte nicht gelesen werden.") from exc

    document_text = "\n".join(pages)
    paragraphs = paragraphs_from_pages(pages)
    result = blank_review_result(checklist, anhang_path.name)

    teil1 = apply_company_scope(result, checklist, legal_form, size_class)
    teil2 = apply_topic_relevance(result, checklist, document_text)
    heur = apply_heuristic_fundstellen(result, checklist, paragraphs)

    ki = None
    if is_ai_ready():
        ki = refine_binaer(
            result, checklist, paragraphs,
            llm=FoundryLLM(),
            max_seconds=ki_max_seconds,
        )

    rest = rest_zu_pruefen(result)
    return result, {
        "teil1": teil1,
        "teil2": teil2,
        "heuristik": heur,
        "ki": ki,
        "zu_pruefen": rest,
        "teil1_zu_pruefen": teil1["zu_pruefen"],
        "rechtsgrund": teil1["umgestellt"],
        "maschinell": teil2["umgestellt"],
        "absatzzahl": len(paragraphs),
        "hat_groessenklassen": any(it.size_classes for it in checklist.items),
        "hinweis": format_review_hinweis(
            legal_form,
            size_class,
            teil1["zu_pruefen"],
            rest,
            len(result.findings),
        ),
    }
