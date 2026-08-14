"""Weighted MatchDimension construction for scoreMatch.

Partition rules are deterministic and metadata-first. Preferred requirements
always go to ``preferredSkills``. Otherwise, explicit years requirements go to
``experience`` before ambiguity checks. Other experience-shaped requirements go
to ``experience``, role/title/seniority requirements go to ``roleAlignment``,
and domain/industry requirements go to ``domainIndustry``. Remaining required or
contextual requirements go to ``requiredSkills``. If multiple semantic
dimensions match the same non-preferred requirement, the ambiguous requirement
falls back by classification instead of inference. ``terminology`` is emitted as
a section-13 placeholder with its configured weight, score 0, and no evidence
until Chunk 5 owns live term scoring. Empty non-terminology dimensions are not
emitted or included in the score denominator.
"""

from __future__ import annotations

import re
from typing import Any

from .matching_config import MATCHING_WEIGHT_KEYS, default_requirement_weight, resolve_matching_config
from .schemas import JsonObject, RequirementClassification


DIMENSION_SCORE_PRECISION = 6
MATCH_SCORE_PRECISION = 4
_YEARS_RE = re.compile(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\+?\s+years?\b", re.IGNORECASE)
_SENIORITY_HINTS = (
    re.compile(r"\b(junior|jr\.?)\b", re.IGNORECASE),
    re.compile(r"\b(mid[- ]level|midlevel)\b", re.IGNORECASE),
    re.compile(r"\b(senior|sr\.?)\b", re.IGNORECASE),
    re.compile(r"\bstaff\b", re.IGNORECASE),
    re.compile(r"\bprincipal\b", re.IGNORECASE),
    re.compile(r"\blead\b", re.IGNORECASE),
    re.compile(r"\bmanager\b", re.IGNORECASE),
    re.compile(r"\bdirector\b", re.IGNORECASE),
    re.compile(r"\b(vp|vice president|head of|chief)\b", re.IGNORECASE),
)
_INDUSTRY_HINTS = (
    re.compile(r"\b(saas|software as a service)\b", re.IGNORECASE),
    re.compile(r"\b(fintech|financial technology|payments?|banking)\b", re.IGNORECASE),
    re.compile(r"\b(healthcare|health care|medical|clinical)\b", re.IGNORECASE),
    re.compile(r"\b(e[- ]?commerce|marketplace|retail)\b", re.IGNORECASE),
    re.compile(r"\b(edtech|education|learning platform)\b", re.IGNORECASE),
)
_DOMAIN_HINTS = (
    re.compile(r"\b(api architecture|api design|rest api|graphql)\b", re.IGNORECASE),
    re.compile(r"\b(cloud infrastructure|aws|azure|gcp|kubernetes)\b", re.IGNORECASE),
    re.compile(r"\b(responsive design|responsive web|desktop and mobile)\b", re.IGNORECASE),
)


def _match_dimensions(requirement_results: list[JsonObject], weights: dict[str, float]) -> list[JsonObject]:
    dimensions: list[JsonObject] = []
    by_dimension = {name: [] for name in MATCHING_WEIGHT_KEYS}
    for result in requirement_results:
        by_dimension[_dimension_for_requirement(result)].append(result)

    for name in MATCHING_WEIGHT_KEYS:
        weight = float(weights.get(name, 0.0))
        rows = by_dimension[name]
        if name == "terminology":
            score = 0.0
            evidence: list[JsonObject] = []
        elif rows:
            score = _dimension_requirement_score(rows)
            evidence = _dimension_evidence(rows)
        else:
            continue
        dimensions.append(
            {
                "name": name,
                "weight": round(weight, DIMENSION_SCORE_PRECISION),
                "score": round(score, DIMENSION_SCORE_PRECISION),
                "contribution": round(weight * score, DIMENSION_SCORE_PRECISION),
                "evidence": evidence,
            }
        )
    return dimensions


def _score_from_dimensions(dimensions: list[JsonObject], max_score: float) -> float:
    weight_total = sum(max(_number(_item(item, "weight", 0.0), 0.0), 0.0) for item in dimensions)
    contribution_total = sum(max(_number(_item(item, "contribution", 0.0), 0.0), 0.0) for item in dimensions)
    if not weight_total or not max_score:
        return 0.0
    return round((contribution_total / weight_total) * max_score, MATCH_SCORE_PRECISION)


def _configured_default_weight(
    config: JsonObject,
    classification: str,
    importance: Any,
    concept: str,
    source_text: str,
    terms: list[str],
    years: Any,
) -> float:
    matching_config = resolve_matching_config(config).config
    dimension = _dimension_for_requirement(
        {
            "classification": classification,
            "importance": str(importance),
            "concept": concept,
            "source_text": source_text,
            "normalized_terms": terms,
            "years": years,
        }
    )
    return default_requirement_weight(
        dimension,
        matching_config.weights,
        classification=classification,
        importance=str(importance),
    )


def _dimension_for_requirement(requirement: JsonObject) -> str:
    classification = _classification(requirement)
    if classification == RequirementClassification.PREFERRED.value:
        return "preferredSkills"
    if _has_explicit_years(requirement):
        return "experience"

    semantic_matches = []
    if _is_experience_requirement(requirement):
        semantic_matches.append("experience")
    if _is_role_alignment_requirement(requirement):
        semantic_matches.append("roleAlignment")
    if _is_domain_industry_requirement(requirement):
        semantic_matches.append("domainIndustry")
    if len(semantic_matches) == 1:
        return semantic_matches[0]
    return "requiredSkills"


def _dimension_requirement_score(rows: list[JsonObject]) -> float:
    max_score = sum(max(_number(_item(row, "max_score", 0.0), 0.0), 0.0) for row in rows)
    if not max_score:
        return 1.0
    score = sum(max(_number(_item(row, "score", 0.0), 0.0), 0.0) for row in rows)
    return max(0.0, min(1.0, score / max_score))


def _dimension_evidence(rows: list[JsonObject]) -> list[JsonObject]:
    evidence: list[JsonObject] = []
    for row in rows:
        requirement_id = str(_item(row, "requirement_id", ""))
        if not requirement_id:
            continue
        entry: JsonObject = {"requirement_id": requirement_id}
        fact_ids = [str(fact_id) for fact_id in _array(_item(row, "matched_fact_ids", [])) if str(fact_id)]
        if fact_ids:
            entry["fact_ids"] = fact_ids
        evidence.append(entry)
    return evidence


def _classification(requirement: JsonObject) -> str:
    value = str(_item(requirement, "classification", RequirementClassification.CONTEXTUAL.value))
    if value == RequirementClassification.CONTEXTUAL.value and _item(requirement, "required") is True:
        return RequirementClassification.REQUIRED.value
    return value if value in {item.value for item in RequirementClassification} else RequirementClassification.CONTEXTUAL.value


def _dimension_text(requirement: JsonObject) -> str:
    return " ".join(
        part
        for part in [
            str(_item(requirement, "concept", "")),
            str(_item(requirement, "source_text", "")),
            " ".join(str(term) for term in _array(_item(requirement, "normalized_terms", []))),
        ]
        if part
    )


def _is_experience_requirement(requirement: JsonObject) -> bool:
    if _has_explicit_years(requirement):
        return True
    text = _normal_text(_dimension_text(requirement))
    experience_phrases = (
        "software engineering experience",
        "engineering experience",
        "professional experience",
        "years experience",
        "years of experience",
        "years of software",
    )
    return any(phrase in text for phrase in experience_phrases)


def _has_explicit_years(requirement: JsonObject) -> bool:
    if _item(requirement, "years"):
        return True
    return bool(_YEARS_RE.search(_normal_text(_dimension_text(requirement))))


def _is_role_alignment_requirement(requirement: JsonObject) -> bool:
    text = _dimension_text(requirement)
    normalized = _normal_text(text)
    role_terms = ("job title", "role alignment", "role fit", "staff engineer", "staff software engineer")
    return any(term in normalized for term in role_terms) or any(pattern.search(text) for pattern in _SENIORITY_HINTS)


def _is_domain_industry_requirement(requirement: JsonObject) -> bool:
    text = _dimension_text(requirement)
    return any(pattern.search(text) for pattern in (*_INDUSTRY_HINTS, *_DOMAIN_HINTS))


def _item(mapping: Any, key: str, default: Any = None) -> Any:
    if isinstance(mapping, dict) and key in mapping:
        return mapping[key]
    return default


def _array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return default


def _normal_text(value: Any) -> str:
    text = str(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())
