"""
Report formatter for § 238 Abs 1 Z 2 UGB (Anteilsbesitz) findings.

Produces audit working paper-grade output for the rule evaluation result.
"""

from ...knowledge.rules.anteilsbesitz_238_z2 import (
    RuleEvaluationResult,
    DisclosureStatus,
    REQUIRED_ELEMENTS,
    JUDGMENT_REASONS,
)


def format_anteilsbesitz_finding(result: RuleEvaluationResult) -> str:
    """
    Format the Anteilsbesitz evaluation result for the review protocol.

    Output is designed for:
    - Audit working paper documentation
    - Clear indication of what tool found vs. what auditor must verify
    - No ambiguity about certainty levels
    """
    lines = []

    # Header
    lines.append("### Anteilsbesitz (§ 238 Abs 1 Z 2 UGB)")
    lines.append("")

    # Status with explicit caveat
    status_display = {
        "COMPLIANT": "[ENTSPRICHT - VORLÄUFIG]",
        "PARTIALLY_COMPLIANT": "[TEILWEISE - LÜCKEN IDENTIFIZIERT]",
        "NOT_COMPLIANT": "[NICHT ENTSPRECHEND - FESTSTELLUNG]",
        "NOT_ASSESSABLE": "[NICHT AUTOMATISCH BEURTEILBAR]",
    }

    lines.append(f"**Status:** {status_display.get(result.compliance_status, '[?]')}")
    lines.append("")
    lines.append(f"**Begründung:** {result.compliance_reasoning}")
    lines.append("")

    # What was found
    lines.append("#### Automatisch identifizierte Beteiligungen")
    lines.append("")

    if result.participations_found:
        lines.append(f"Anzahl erkannt: **{result.total_participations_detected}**")
        lines.append("")

        # Table of findings
        lines.append("| Gesellschaft | Anteil | Eigenkapital | Ergebnis | Status |")
        lines.append("|--------------|--------|--------------|----------|--------|")

        for p in result.participations_found:
            name = p.entity_name or "_nicht erkannt_"
            percentage = "_-_"
            equity = "_-_"
            result_val = "_-_"
            status_icons = []

            for elem in p.element_assessments:
                if elem.element_id == "share_percentage":
                    if elem.status == DisclosureStatus.PRESENT:
                        percentage = f"{elem.extracted_value}%"
                        status_icons.append("✓")
                    else:
                        status_icons.append("✗")

                elif elem.element_id == "equity_capital":
                    if elem.status == DisclosureStatus.PRESENT:
                        equity = elem.extracted_value
                        status_icons.append("✓")
                    elif elem.status == DisclosureStatus.ABSENT:
                        status_icons.append("✗")
                    else:
                        status_icons.append("?")

                elif elem.element_id == "last_year_result":
                    if elem.status == DisclosureStatus.PRESENT:
                        result_val = elem.extracted_value
                        status_icons.append("✓")
                    elif elem.status == DisclosureStatus.ABSENT:
                        status_icons.append("✗")
                    else:
                        status_icons.append("?")

            status_str = " ".join(status_icons)
            if p.protective_clause_claimed:
                status_str += " (§241)"

            lines.append(f"| {name[:30]} | {percentage} | {equity} | {result_val} | {status_str} |")

        lines.append("")
        lines.append("_Legende: ✓ = erkannt, ✗ = nicht gefunden, ? = nicht beurteilbar, (§241) = Schutzklausel_")
    else:
        lines.append("_Keine Beteiligungen automatisch identifiziert._")

    lines.append("")

    # Explicit gaps
    if result.compliance_status in ("PARTIALLY_COMPLIANT", "NOT_COMPLIANT"):
        lines.append("#### Identifizierte Lücken")
        lines.append("")
        for p in result.participations_found:
            gaps = []
            for elem in p.element_assessments:
                if elem.status == DisclosureStatus.ABSENT:
                    elem_name = next(
                        (e.name_de for e in REQUIRED_ELEMENTS if e.element_id == elem.element_id),
                        elem.element_id
                    )
                    gaps.append(elem_name)
            if gaps:
                lines.append(f"- **{p.entity_name}**: {', '.join(gaps)}")
        lines.append("")

    # Auditor action items
    lines.append("#### Erforderliche Prüfungshandlungen")
    lines.append("")
    for i, action in enumerate(result.auditor_actions_required, 1):
        lines.append(f"{i}. [ ] {action}")
    lines.append("")

    # Uncertainties
    lines.append("#### Automatisch nicht prüfbar")
    lines.append("")
    for uncertainty in result.uncertainties:
        lines.append(f"- {uncertainty}")
    lines.append("")

    # Judgment areas
    lines.append("#### Bereiche mit Ermessensspielraum")
    lines.append("")
    for reason in JUDGMENT_REASONS[:3]:  # Top 3
        lines.append(f"- {reason}")
    lines.append("")

    # Auditor sign-off
    lines.append("---")
    lines.append("")
    lines.append("**Prüferkommentar:**")
    lines.append("_[Platzhalter für manuelle Beurteilung]_")
    lines.append("")
    lines.append("**Geprüft von:** _______________ **Datum:** _______________")
    lines.append("")

    return "\n".join(lines)


def format_missing_evidence(result: RuleEvaluationResult) -> dict:
    """
    Generate structured missing-evidence objects for downstream processing.

    Returns explicit objects, not scores or probabilities.
    """
    missing = {
        "rule_id": result.rule_id,
        "status": result.compliance_status,
        "missing_elements": [],
        "not_assessable_elements": [],
        "auditor_required": True,
    }

    for p in result.participations_found:
        for elem in p.element_assessments:
            if elem.status == DisclosureStatus.ABSENT:
                missing["missing_elements"].append({
                    "entity": p.entity_name,
                    "element": elem.element_id,
                    "note": elem.confidence_note or "Nicht gefunden",
                })
            elif elem.status == DisclosureStatus.NOT_ASSESSABLE:
                missing["not_assessable_elements"].append({
                    "entity": p.entity_name,
                    "element": elem.element_id,
                    "note": elem.confidence_note or "Nicht automatisch beurteilbar",
                })

    return missing
