"""
Audit-Grade Rule Definitions

Each module in this package defines ONE formalized disclosure requirement
with explicit sub-requirements, evaluation logic, and integration points.

Design principles:
- Depth over breadth
- Explicit over heuristic
- Conservative uncertainty handling
- No auto-judgment of materiality
"""

from .anteilsbesitz_238_z2 import (
    RULE_ID as ANTEILSBESITZ_RULE_ID,
    RULE_SCHEMA as ANTEILSBESITZ_SCHEMA,
    REQUIRED_ELEMENTS as ANTEILSBESITZ_ELEMENTS,
    RuleEvaluationResult,
    ParticipationAssessment,
    ElementAssessment,
    DisclosureStatus,
    determine_compliance_status,
)

__all__ = [
    "ANTEILSBESITZ_RULE_ID",
    "ANTEILSBESITZ_SCHEMA",
    "ANTEILSBESITZ_ELEMENTS",
    "RuleEvaluationResult",
    "ParticipationAssessment",
    "ElementAssessment",
    "DisclosureStatus",
    "determine_compliance_status",
]
