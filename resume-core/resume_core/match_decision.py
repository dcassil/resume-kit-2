"""MatchResult decision helpers."""

from __future__ import annotations

from .matching_config import DEFAULT_SCORE_AUTO_THRESHOLD, MatchingConfig
from .schemas import JsonObject


def decide_match(score: float, threshold: float, hard_resolved: bool, config: MatchingConfig) -> str:
    """Return the section-4.3 MatchResult decision."""

    if config.require_hard_requirements_resolved and not hard_resolved:
        return "blocked"
    if score < threshold:
        return "resolve_gaps"
    return "continue"


def match_decision_explanation(decision: str) -> str:
    if decision == "blocked":
        return "Required unresolved requirements block continuation."
    if decision == "resolve_gaps":
        return "Score is below the configured continuation threshold."
    return "No required hard gate is blocking continuation and score meets threshold."


def empty_match(algorithm_version: str) -> JsonObject:
    return {
        "schema_version": "match-result.v1",
        "match_id": "match_empty",
        "job_id": "",
        "resume_id": "",
        "score": 0.0,
        "max_score": 0.0,
        "threshold": DEFAULT_SCORE_AUTO_THRESHOLD,
        "hardRequirementsResolved": False,
        "decision": "blocked",
        "dimensions": [],
        "requirement_results": [],
        "unresolved_requirement_ids": [],
        "can_continue": False,
        "algorithm_version": algorithm_version,
    }
