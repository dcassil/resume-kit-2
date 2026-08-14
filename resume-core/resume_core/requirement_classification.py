"""Requirement classification helpers."""

from __future__ import annotations

import re

from .schemas import RequirementClassification


_PLUS_YEARS_RE = re.compile(r"\b\d+\+\s*years?\b", re.IGNORECASE)


def infer_classification(text: str) -> str:
    lowered = text.lower()
    if "preferred" in lowered or "nice to have" in lowered:
        return RequirementClassification.PREFERRED.value
    if "required" in lowered or "must" in lowered or _PLUS_YEARS_RE.search(lowered) or "requirement" in lowered:
        return RequirementClassification.REQUIRED.value
    return RequirementClassification.CONTEXTUAL.value


def default_importance(classification: str) -> str:
    if classification == RequirementClassification.REQUIRED.value:
        return "high"
    if classification == RequirementClassification.PREFERRED.value:
        return "medium"
    return "low"
