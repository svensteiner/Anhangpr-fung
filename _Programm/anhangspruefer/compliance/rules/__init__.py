"""
Rule-specific evaluators.

Each evaluator implements the formalized audit logic for one checklist item.
"""

from .anteilsbesitz_evaluator import (
    AnteilsbesitzEvaluator,
    evaluate_anteilsbesitz,
)

__all__ = [
    "AnteilsbesitzEvaluator",
    "evaluate_anteilsbesitz",
]
