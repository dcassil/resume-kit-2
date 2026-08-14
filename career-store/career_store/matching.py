"""Pure deterministic matching helpers for career-store.

This module is intentionally data-only: no SQLite, file IO, network access,
prompting, rendering, or delivery-adapter imports belong here.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Iterable
from unicodedata import category as _unicode_category
from unicodedata import normalize as _unicode_normalize

from .schemas import RelationshipType, ResolutionState, VerificationState


JsonObject = dict[str, Any]

ALGORITHM_VERSION = "career-store.matching.v1"
NORMALIZATION_VERSION = "career-store.normalize.v1"

_VERIFIED_STATES = {
    VerificationState.SOURCE_STATED.value,
    VerificationState.USER_VERIFIED.value,
    VerificationState.IMPORTED.value,
}
# Search ranking only; no confirmation or verification-state mutation occurs here.
_SEARCH_STATE_PRIORITY = {
    VerificationState.USER_VERIFIED.value: 0,
    VerificationState.SOURCE_STATED.value: 1,
    VerificationState.IMPORTED.value: 2,
    VerificationState.INFERRED.value: 3,
    VerificationState.UNKNOWN.value: 4,
}
_RESOLUTION_PRIORITY = {
    ResolutionState.EXACT_MATCH.value: 0,
    ResolutionState.ALIAS_MATCH.value: 1,
    ResolutionState.VERIFIED_FACT_MATCH.value: 2,
    ResolutionState.RELATED_MATCH.value: 3,
    ResolutionState.POSSIBLE_MATCH.value: 4,
    ResolutionState.UNKNOWN.value: 5,
    "explicitly_missing": 6,
    ResolutionState.NOT_APPLICABLE.value: 7,
}
_SMART_TRANSLATION = str.maketrans(
    {
        "\u00a0": " ",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2022": "-",
    }
)
_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
_YEARS_RE = re.compile(
    r"\b(?P<value>\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty)\+?\s+years?\b",
    re.IGNORECASE,
)
_TITLE_PREFIX_RE = re.compile(
    r"^(?:actual\s+title|fabricated\s+title|claimed\s+title|job\s+title|title|position)\s*[:=-]?\s*",
    re.IGNORECASE,
)
_KNOWN_TITLE_TERMS = (
    "staff software engineer",
    "principal software engineer",
    "senior software engineer",
    "software engineer",
    "engineering manager",
    "staff engineer",
    "principal engineer",
    "senior engineer",
)
_TERM_STOPWORDS = {"year", "years", "experience", "of", "with", "in", "and", "the", "a", "an"}


def normalize_term(value: Any) -> str:
    """Return a stable lowercase term string for matching and IDs."""

    if value is None:
        return ""
    text = _unicode_normalize("NFKC", str(value).translate(_SMART_TRANSLATION))
    chars: list[str] = []
    for char in text:
        if _unicode_category(char).startswith("C"):
            continue
        if char.isalnum() or char in {"+", "#"}:
            chars.append(char.casefold())
        else:
            chars.append(" ")
    return " ".join("".join(chars).split())


def normalize_text(value: Any) -> str:
    """Alias for normalize_term when callers are normalizing longer text."""

    return normalize_term(value)


def normalize_terms(value: Any = None, *extra_values: Any) -> list[str]:
    """Normalize supplied terms, text, or DTOs into sorted unique terms."""

    raw_terms: list[Any] = []
    for item in (value, *extra_values):
        _collect_raw_terms(item, raw_terms)
    return sorted({term for item in raw_terms if (term := normalize_term(item))})


def terms_for_text(value: Any) -> list[str]:
    """Return deterministic whole-phrase and token terms for free text."""

    normalized = normalize_term(value)
    if not normalized:
        return []
    terms = {normalized}
    terms.update(token for token in normalized.split() if len(token) > 1)
    return sorted(terms)


def fact_terms(fact: Any) -> list[str]:
    """Return normalized searchable terms for a fact DTO."""

    data = _as_mapping(fact)
    terms = set(normalize_terms(_item(data, "normalized_terms", [])))
    terms.update(terms_for_text(_item(data, "text", "")))
    for key in ("type", "name", "concept"):
        value = _item(data, key)
        if value:
            terms.add(normalize_term(value))
    return sorted(term for term in terms if term)


def requirement_terms(requirement: Any) -> list[str]:
    """Return normalized terms for a job requirement DTO or string."""

    data = _as_mapping(requirement)
    if data:
        raw = _item(data, "normalized_terms")
        if raw:
            terms = set(normalize_terms(raw))
        else:
            terms = set()
        for key in ("concept", "source_text", "text", "requirement"):
            terms.update(terms_for_text(_item(data, key, "")))
        return sorted(term for term in terms if term)
    return terms_for_text(requirement)


def stable_fact_id(
    fact_or_type: Any,
    text: Any | None = None,
    normalized_terms: Iterable[Any] | None = None,
    *,
    prefix: str = "fact",
) -> str:
    """Generate a stable fact ID from a fact DTO or explicit fact fields."""

    data = _as_mapping(fact_or_type)
    if data:
        fact_type = normalize_term(_item(data, "type", "fact"))
        fact_text = normalize_term(_item(data, "text", ""))
        terms = normalize_terms(_item(data, "normalized_terms", []))
    else:
        fact_type = normalize_term(fact_or_type or "fact")
        fact_text = normalize_term(text or "")
        terms = normalize_terms(list(normalized_terms or []))

    payload = {
        "normalization_version": NORMALIZATION_VERSION,
        "type": fact_type,
        "text": fact_text,
        "normalized_terms": terms,
    }
    return _stable_id(prefix, payload)


generate_stable_fact_id = stable_fact_id
make_fact_id = stable_fact_id


def _search_sort_key(fact: Any, query: Any = None) -> tuple[Any, ...]:
    """Return a deterministic sort key for fact search results."""

    data = _as_mapping(fact)
    query_terms = requirement_terms(query) if query is not None else []
    searchable = fact_terms(data)
    score = _term_overlap_score(query_terms, searchable)
    return (
        -score,
        _SEARCH_STATE_PRIORITY.get(_state_value(_item(data, "verification_state")), 99),
        normalize_term(_item(data, "type", "")),
        normalize_term(_item(data, "text", "")),
        str(_item(data, "fact_id", stable_fact_id(data))),
    )


def order_search_results(facts: Iterable[Any], query: Any = None, limit: int | None = None) -> list[Any]:
    """Sort facts with stable ordering for identical inputs."""

    ordered = sorted(list(facts), key=lambda fact: _search_sort_key(fact, query))
    if limit is None:
        return ordered
    return ordered[: max(int(limit), 0)]


deterministic_search_order = order_search_results


def resolve_relationship_label(relationship_type: Any, policy: JsonObject | None = None) -> str:
    """Return the resolution label implied by a relationship type and policy."""

    policy = policy or {}
    relationship = _relationship_type_value(relationship_type)
    if relationship in {RelationshipType.ALIAS.value, RelationshipType.EQUIVALENT.value}:
        return ResolutionState.ALIAS_MATCH.value
    if relationship == RelationshipType.RELATED.value:
        if bool(_item(policy, "allow_related_as_equivalent")) or bool(_item(policy, "promote_related_to_equivalent")):
            return ResolutionState.ALIAS_MATCH.value
        return ResolutionState.RELATED_MATCH.value
    if relationship == RelationshipType.CONTRADICTS.value:
        return ResolutionState.POSSIBLE_MATCH.value
    return ResolutionState.POSSIBLE_MATCH.value


relationship_resolution_state = resolve_relationship_label


def match_requirement_to_facts(
    requirement: Any,
    facts: Iterable[Any],
    relationships: Iterable[Any] | None = None,
    policy: JsonObject | None = None,
    limit: int | None = None,
) -> list[JsonObject]:
    """Match one requirement against facts with relationship-aware labels."""

    policy = policy or {}
    fact_list = [_as_mapping(fact) for fact in facts]
    fact_list = [fact for fact in fact_list if fact]
    relationship_list = [_as_mapping(relationship) for relationship in relationships or []]
    req_terms = requirement_terms(requirement)
    req_id = _requirement_id(requirement)

    direct_fact_ids = {
        _fact_id(fact)
        for fact in fact_list
        if _term_overlap_score(req_terms, fact_terms(fact)) > 0
    }

    matches: list[JsonObject] = []
    for fact in fact_list:
        fact_id = _fact_id(fact)
        direct_score = _term_overlap_score(req_terms, fact_terms(fact))
        relationship = None
        related_fact_id = None
        if direct_score <= 0:
            relationship, related_fact_id = _best_relationship_to_direct_fact(fact_id, direct_fact_ids, relationship_list, policy)
        if direct_score <= 0 and relationship is None:
            continue

        resolution_state = _direct_resolution(fact) if direct_score > 0 else resolve_relationship_label(_item(relationship, "relationship_type"), policy)
        evidence = [{"source": "fact_terms", "fact_id": fact_id, "matched_terms": sorted(set(req_terms) & set(fact_terms(fact)))}]
        conflicts = _match_conflicts(req_id, fact, relationship, related_fact_id, resolution_state)
        if relationship is not None:
            evidence.append(
                {
                    "source": "relationship",
                    "relationship_id": str(_item(relationship, "relationship_id", "")),
                    "relationship_type": _relationship_type_value(_item(relationship, "relationship_type")),
                    "linked_fact_id": related_fact_id,
                }
            )

        matches.append(
            {
                "requirement_id": req_id,
                "fact_id": fact_id,
                "resolution_state": resolution_state,
                "score": _match_score(resolution_state, direct_score),
                "matched_terms": sorted(set(req_terms) & set(fact_terms(fact))),
                "relationship_id": _item(relationship, "relationship_id") if relationship else None,
                "evidence": evidence,
                "conflicts": conflicts,
            }
        )

    matches.sort(key=_match_sort_key)
    if limit is not None:
        matches = matches[: max(int(limit), 0)]
    return matches


def match_requirements_to_facts(
    requirements: Iterable[Any],
    facts: Iterable[Any],
    relationships: Iterable[Any] | None = None,
    policy: JsonObject | None = None,
) -> JsonObject:
    """Match many requirements and return contract-shaped data."""

    matches: list[JsonObject] = []
    unresolved: list[JsonObject] = []
    conflicts: list[JsonObject] = []
    for requirement in requirements:
        requirement_matches = match_requirement_to_facts(requirement, facts, relationships, policy)
        matches.extend(requirement_matches)
        for match in requirement_matches:
            conflicts.extend(_item(match, "conflicts", []))
        if not any(_item(match, "resolution_state") in _resolved_states(policy) for match in requirement_matches):
            unresolved.append(
                {
                    "requirement_id": _requirement_id(requirement),
                    "resolution_state": _item(requirement_matches[0], "resolution_state", ResolutionState.UNKNOWN.value)
                    if requirement_matches
                    else ResolutionState.UNKNOWN.value,
                }
            )
    return {
        "schema_version": "career-store.candidate-matches.v1",
        "status": "ok",
        "matches": matches,
        "unresolved": unresolved,
        "conflicts": _dedupe_conflicts(conflicts),
        "audit": {"algorithm_version": ALGORITHM_VERSION},
    }


def detect_conflicts(
    fact_or_claim: Any,
    existing_facts: Iterable[Any] | None = None,
    relationships: Iterable[Any] | None = None,
) -> list[JsonObject]:
    """Detect simple contradictory year, title, and contradicts-relationship claims."""

    if existing_facts is None and isinstance(fact_or_claim, list):
        facts = [_as_mapping(fact) for fact in fact_or_claim]
        pairs = [(facts[index], facts[other]) for index in range(len(facts)) for other in range(index + 1, len(facts))]
    else:
        claim = _as_mapping(fact_or_claim)
        pairs = [(claim, _as_mapping(fact)) for fact in existing_facts or []]

    conflicts: list[JsonObject] = []
    seen: set[str] = set()
    for left, right in pairs:
        if not left or not right:
            continue
        for conflict in _pair_conflicts(left, right):
            conflict_id = _item(conflict, "conflict_id")
            if conflict_id not in seen:
                seen.add(conflict_id)
                conflicts.append(conflict)

    conflicts.extend(_relationship_conflicts(fact_or_claim, existing_facts or [], relationships or [], seen))
    conflicts.sort(key=lambda item: (str(_item(item, "reason", "")), str(_item(item, "conflict_id", ""))))
    return conflicts


def _collect_raw_terms(value: Any, output: list[Any]) -> None:
    if value is None:
        return
    data = _as_mapping(value)
    if data:
        for key in ("normalized_terms", "terms", "aliases"):
            _collect_raw_terms(_item(data, key), output)
        for key in ("text", "concept", "source_text", "requirement", "type"):
            item = _item(data, key)
            if item:
                output.append(item)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _collect_raw_terms(item, output)
        return
    output.append(value)


def _as_mapping(value: Any) -> JsonObject:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return {}


def _item(mapping: Any, key: str, default: Any = None) -> Any:
    if isinstance(mapping, dict) and key in mapping:
        return mapping[key]
    return default


def _stable_id(prefix: str, value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _state_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value or VerificationState.UNKNOWN.value)


def _relationship_type_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return normalize_term(value).replace(" ", "_")


def _fact_id(fact: JsonObject) -> str:
    fact_id = _item(fact, "fact_id")
    return str(fact_id) if fact_id else stable_fact_id(fact)


def _requirement_id(requirement: Any) -> str:
    data = _as_mapping(requirement)
    if data and _item(data, "requirement_id"):
        return str(_item(data, "requirement_id"))
    return _stable_id("req", {"terms": requirement_terms(requirement)})


def _term_overlap_score(required_terms: list[str], candidate_terms: list[str]) -> int:
    if not required_terms or not candidate_terms:
        return 0
    candidate_text = " ".join(candidate_terms)
    score = 0
    for term in required_terms:
        if term in candidate_terms:
            score += 3
        elif term and term in candidate_text:
            score += 1
    return score


def _direct_resolution(fact: JsonObject) -> str:
    state = _state_value(_item(fact, "verification_state"))
    if str(_item(fact, "resolution_state", "")) == "explicitly_missing":
        return "explicitly_missing"
    if state == "conflicted":
        return ResolutionState.POSSIBLE_MATCH.value
    if state == VerificationState.UNKNOWN.value:
        return ResolutionState.UNKNOWN.value
    if state == VerificationState.INFERRED.value:
        return ResolutionState.POSSIBLE_MATCH.value
    if state in _VERIFIED_STATES:
        return ResolutionState.EXACT_MATCH.value
    return ResolutionState.UNKNOWN.value


def _best_relationship_to_direct_fact(
    fact_id: str,
    direct_fact_ids: set[str],
    relationships: list[JsonObject],
    policy: JsonObject,
) -> tuple[JsonObject | None, str | None]:
    candidates: list[tuple[int, str, JsonObject, str]] = []
    for relationship in relationships:
        from_fact_id = str(_item(relationship, "from_fact_id", ""))
        to_fact_id = str(_item(relationship, "to_fact_id", ""))
        if from_fact_id == fact_id and to_fact_id in direct_fact_ids:
            label = resolve_relationship_label(_item(relationship, "relationship_type"), policy)
            candidates.append((_RESOLUTION_PRIORITY.get(label, 99), to_fact_id, relationship, to_fact_id))
        elif to_fact_id == fact_id and from_fact_id in direct_fact_ids:
            label = resolve_relationship_label(_item(relationship, "relationship_type"), policy)
            candidates.append((_RESOLUTION_PRIORITY.get(label, 99), from_fact_id, relationship, from_fact_id))
    if not candidates:
        return None, None
    candidates.sort(key=lambda item: (item[0], item[1], str(_item(item[2], "relationship_id", ""))))
    return candidates[0][2], candidates[0][3]


def _match_score(resolution_state: str, direct_score: int) -> float:
    base = {
        ResolutionState.EXACT_MATCH.value: 1.0,
        ResolutionState.ALIAS_MATCH.value: 0.9,
        ResolutionState.VERIFIED_FACT_MATCH.value: 0.85,
        ResolutionState.RELATED_MATCH.value: 0.45,
        ResolutionState.POSSIBLE_MATCH.value: 0.25,
        ResolutionState.UNKNOWN.value: 0.0,
        "explicitly_missing": 0.0,
        ResolutionState.NOT_APPLICABLE.value: 0.0,
    }.get(resolution_state, 0.0)
    return round(base + min(direct_score, 10) / 1000, 4)


def _match_sort_key(match: JsonObject) -> tuple[Any, ...]:
    state = str(_item(match, "resolution_state", ResolutionState.UNKNOWN.value))
    return (
        _RESOLUTION_PRIORITY.get(state, 99),
        -float(_item(match, "score", 0.0)),
        str(_item(match, "requirement_id", "")),
        str(_item(match, "fact_id", "")),
        str(_item(match, "relationship_id", "")),
    )


def _resolved_states(policy: JsonObject | None) -> set[str]:
    policy = policy or {}
    states = {
        ResolutionState.EXACT_MATCH.value,
        ResolutionState.ALIAS_MATCH.value,
        ResolutionState.VERIFIED_FACT_MATCH.value,
    }
    if bool(_item(policy, "allow_related_as_resolved")):
        states.add(ResolutionState.RELATED_MATCH.value)
    return states


def _match_conflicts(
    requirement_id: str,
    fact: JsonObject,
    relationship: JsonObject | None,
    related_fact_id: str | None,
    resolution_state: str,
) -> list[JsonObject]:
    conflicts: list[JsonObject] = []
    if _state_value(_item(fact, "verification_state")) == "conflicted":
        conflicts.append(
            {
                "conflict_id": _stable_id("conflict", {"reason": "legacy_conflicted_verification_state", "fact_id": _fact_id(fact)}),
                "fact_ids": [_fact_id(fact)],
                "reason": "legacy_conflicted_verification_state",
                "status": "open",
                "evidence_ids": _evidence_ids(fact),
                "metadata": {
                    "requirement_id": requirement_id,
                    "resolution_state": resolution_state,
                    "verification_state": "conflicted",
                },
            }
        )
    if relationship is not None and _relationship_type_value(_item(relationship, "relationship_type")) == RelationshipType.CONTRADICTS.value:
        fact_ids = sorted({_fact_id(fact), str(related_fact_id or "")} - {""})
        conflicts.append(
            {
                "conflict_id": _stable_id(
                    "conflict",
                    {
                        "reason": "contradicts_relationship",
                        "relationship_id": str(_item(relationship, "relationship_id", "")),
                        "fact_ids": fact_ids,
                    },
                ),
                "fact_ids": fact_ids,
                "reason": "contradicts_relationship",
                "status": "open",
                "evidence_ids": [],
                "metadata": {
                    "relationship_id": str(_item(relationship, "relationship_id", "")),
                    "relationship_type": RelationshipType.CONTRADICTS.value,
                    "requirement_id": requirement_id,
                    "resolution_state": resolution_state,
                },
            }
        )
    return conflicts


def _dedupe_conflicts(conflicts: list[JsonObject]) -> list[JsonObject]:
    deduped = {str(_item(conflict, "conflict_id", "")): conflict for conflict in conflicts if _item(conflict, "conflict_id")}
    return [deduped[key] for key in sorted(deduped)]


def _pair_conflicts(left: JsonObject, right: JsonObject) -> list[JsonObject]:
    conflicts: list[JsonObject] = []
    year_conflict = _years_conflict(left, right)
    if year_conflict:
        conflicts.append(year_conflict)
    title_conflict = _title_conflict(left, right)
    if title_conflict:
        conflicts.append(title_conflict)
    return conflicts


def _years_conflict(left: JsonObject, right: JsonObject) -> JsonObject | None:
    left_year = _extract_year_claim(left)
    right_year = _extract_year_claim(right)
    if left_year is None or right_year is None or left_year["value"] == right_year["value"]:
        return None

    shared_terms = sorted(_claim_terms_without_years(left) & _claim_terms_without_years(right))
    if not shared_terms:
        return None

    fact_ids = sorted({_fact_id(left), _fact_id(right)})
    return {
        "conflict_id": _stable_id("conflict", {"reason": "contradictory_years", "fact_ids": fact_ids, "years": [left_year, right_year]}),
        "fact_ids": fact_ids,
        "reason": "contradictory_years",
        "status": "open",
        "evidence_ids": sorted(set(_evidence_ids(left)) | set(_evidence_ids(right))),
        "metadata": {
            "shared_terms": shared_terms,
            "left_text": str(_item(left, "text", "")),
            "right_text": str(_item(right, "text", "")),
            "left_years": left_year,
            "right_years": right_year,
        },
    }


def _title_conflict(left: JsonObject, right: JsonObject) -> JsonObject | None:
    left_title = _extract_title_claim(left)
    right_title = _extract_title_claim(right)
    if not left_title or not right_title or left_title == right_title:
        return None

    fact_ids = sorted({_fact_id(left), _fact_id(right)})
    return {
        "conflict_id": _stable_id("conflict", {"reason": "contradictory_titles", "fact_ids": fact_ids, "titles": [left_title, right_title]}),
        "fact_ids": fact_ids,
        "reason": "contradictory_titles",
        "status": "open",
        "evidence_ids": sorted(set(_evidence_ids(left)) | set(_evidence_ids(right))),
        "metadata": {
            "left_title": left_title,
            "right_title": right_title,
            "left_text": str(_item(left, "text", "")),
            "right_text": str(_item(right, "text", "")),
        },
    }


def _relationship_conflicts(
    fact_or_claim: Any,
    existing_facts: Iterable[Any],
    relationships: Iterable[Any],
    seen: set[str],
) -> list[JsonObject]:
    facts = [_as_mapping(fact_or_claim), *[_as_mapping(fact) for fact in existing_facts]]
    fact_ids = {_fact_id(fact) for fact in facts if fact}
    conflicts: list[JsonObject] = []
    for relationship in (_as_mapping(item) for item in relationships):
        if _relationship_type_value(_item(relationship, "relationship_type")) != RelationshipType.CONTRADICTS.value:
            continue
        endpoints = [str(_item(relationship, "from_fact_id", "")), str(_item(relationship, "to_fact_id", ""))]
        if not any(endpoint in fact_ids for endpoint in endpoints):
            continue
        conflict_id = _stable_id("conflict", {"reason": "contradicts_relationship", "relationship": relationship})
        if conflict_id in seen:
            continue
        seen.add(conflict_id)
        conflicts.append(
            {
                "conflict_id": conflict_id,
                "fact_ids": sorted(endpoint for endpoint in endpoints if endpoint),
                "reason": "contradicts_relationship",
                "status": "open",
                "evidence_ids": [],
                "metadata": {
                    "relationship_id": str(_item(relationship, "relationship_id", "")),
                    "relationship_type": RelationshipType.CONTRADICTS.value,
                },
            }
        )
    return conflicts


def _extract_year_claim(fact: JsonObject) -> JsonObject | None:
    texts = [str(_item(fact, "text", ""))]
    texts.extend(str(term) for term in _item(fact, "normalized_terms", []) if term is not None)
    for text in texts:
        match = _YEARS_RE.search(text)
        if match:
            raw_value = match.group("value").casefold()
            value = int(raw_value) if raw_value.isdigit() else _NUMBER_WORDS[raw_value]
            return {"value": value, "text": normalize_term(match.group(0))}
    return None


def _claim_terms_without_years(fact: JsonObject) -> set[str]:
    terms = set(fact_terms(fact))
    for year in _YEARS_RE.finditer(" ".join(terms)):
        terms.discard(normalize_term(year.group(0)))
        terms.discard(normalize_term(year.group("value")))
    terms.difference_update(_TERM_STOPWORDS)
    terms.difference_update(str(number) for number in _NUMBER_WORDS.values())
    terms.difference_update(_NUMBER_WORDS)
    return {term for term in terms if term}


def _extract_title_claim(fact: JsonObject) -> str | None:
    fact_type = normalize_term(_item(fact, "type", ""))
    text = normalize_term(_TITLE_PREFIX_RE.sub("", str(_item(fact, "text", ""))))
    if fact_type in {"title", "job_title", "position"}:
        return text or None
    for title in _KNOWN_TITLE_TERMS:
        normalized_title = normalize_term(title)
        if normalized_title in text:
            return normalized_title
    return None


def _evidence_ids(fact: JsonObject) -> list[str]:
    return [str(item) for item in _item(fact, "evidence_ids", []) if item is not None]


__all__ = [
    "ALGORITHM_VERSION",
    "NORMALIZATION_VERSION",
    "detect_conflicts",
    "deterministic_search_order",
    "fact_terms",
    "generate_stable_fact_id",
    "make_fact_id",
    "match_requirement_to_facts",
    "match_requirements_to_facts",
    "normalize_term",
    "normalize_terms",
    "normalize_text",
    "order_search_results",
    "relationship_resolution_state",
    "requirement_terms",
    "resolve_relationship_label",
    "stable_fact_id",
    "terms_for_text",
]
