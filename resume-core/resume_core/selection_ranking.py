"""MatchResult-driven content relevance ranking.

Relevance values are stable bands, not probabilistic scores:

- ``3.0``: content linked to ``exact_match``, ``alias_match``, or
  ``verified_fact_match`` requirement rows.
- ``2.0``: content linked to ``related_match`` or ``possible_match`` rows.
- ``1.0``: unlinked content.

Item-to-requirement linkage is deterministic. Requirement rows contribute their
matched evidence terms, matched fact IDs, and any explicit evidence
``field_path``/``claim_id`` refs. Resume content contributes its claim-field
path, claim ID, provenance claim IDs, and normalized text. No fuzzy matching is
performed; terms must match by the same whole-token rule used elsewhere in
resume-core. Sort ties are deterministic: relevance band, recency, then source
order and path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .dates import date_key, is_present_date_sentinel
from .schemas import JsonObject, ResolutionState, to_json_dict


RESOLVED_RELEVANCE = 3.0
RELATED_RELEVANCE = 2.0
UNLINKED_RELEVANCE = 1.0

_RESOLVED_STATES = {
    ResolutionState.EXACT_MATCH.value,
    ResolutionState.ALIAS_MATCH.value,
    ResolutionState.VERIFIED_FACT_MATCH.value,
}
_RELATED_STATES = {
    ResolutionState.RELATED_MATCH.value,
    ResolutionState.POSSIBLE_MATCH.value,
}


@dataclass(frozen=True)
class ContentRelevance:
    path: str
    kind: str
    source_index: int
    relevance: float
    recency_key: tuple[int, int]
    source_order: tuple[int, ...]
    requirement_ids: tuple[str, ...] = field(default_factory=tuple)
    fact_ids: tuple[str, ...] = field(default_factory=tuple)


def _rank_content_by_match_result(resume: JsonObject, match_result: Any) -> tuple[list[JsonObject], dict[str, JsonObject]]:
    """Return legacy ranked content plus per-plan-entry relevance metadata."""

    rows = _requirement_rows(match_result)
    candidates = _content_candidates(resume)
    item_relevance = {candidate.path: _score_candidate(candidate, rows) for candidate in candidates}
    ranked = _ranked_content(resume, item_relevance)
    entry_relevance = {
        path: {
            "relevance": relevance.relevance,
            "requirement_ids": list(relevance.requirement_ids),
            "fact_ids": list(relevance.fact_ids),
            "rank_key": _sort_key(relevance),
        }
        for path, relevance in item_relevance.items()
    }
    return ranked, entry_relevance


@dataclass(frozen=True)
class _RequirementRow:
    requirement_id: str
    relevance: float
    terms: tuple[str, ...]
    fact_ids: tuple[str, ...]
    field_paths: tuple[str, ...]
    claim_ids: tuple[str, ...]


@dataclass(frozen=True)
class _ContentCandidate:
    path: str
    kind: str
    source_index: int
    source_order: tuple[int, ...]
    recency_key: tuple[int, int]
    text: str
    field_paths: tuple[str, ...]
    claim_ids: tuple[str, ...]


def _requirement_rows(match_result: Any) -> list[_RequirementRow]:
    match = _unwrap(match_result, "match_result")
    if not isinstance(match, dict):
        return []
    rows: list[_RequirementRow] = []
    for row in _array(_item(match, "requirement_results", [])):
        if not isinstance(row, dict):
            continue
        requirement_id = str(_item(row, "requirement_id", ""))
        relevance = _state_relevance(str(_item(row, "resolution_state", "")))
        if not requirement_id or relevance <= 0:
            continue
        terms: set[Any] = set()
        fact_ids = {str(item) for item in _array(_item(row, "matched_fact_ids", [])) if str(item)}
        field_paths: set[str] = set()
        claim_ids: set[str] = set()
        for evidence in _array(_item(row, "evidence", [])):
            if not isinstance(evidence, dict):
                continue
            terms.update(_array(_item(evidence, "terms", [])))
            fact_id = _item(evidence, "fact_id")
            if fact_id:
                fact_ids.add(str(fact_id))
            field_path = _item(evidence, "field_path")
            if field_path:
                field_paths.add(_pointer_path(str(field_path)))
            claim_id = _item(evidence, "claim_id")
            if claim_id:
                claim_ids.add(str(claim_id))
            for ref in _array(_item(evidence, "where", [])):
                if not isinstance(ref, dict):
                    continue
                ref_path = _item(ref, "field_path")
                if ref_path:
                    field_paths.add(_pointer_path(str(ref_path)))
                ref_claim = _item(ref, "claim_id")
                if ref_claim:
                    claim_ids.add(str(ref_claim))
        rows.append(
            _RequirementRow(
                requirement_id=requirement_id,
                relevance=relevance,
                terms=tuple(sorted({_normal_text(term) for term in terms if _normal_text(term)})),
                fact_ids=tuple(sorted(fact_ids)),
                field_paths=tuple(sorted(field_paths)),
                claim_ids=tuple(sorted(claim_ids)),
            )
        )
    return rows


def _state_relevance(state: str) -> float:
    if state in _RESOLVED_STATES:
        return RESOLVED_RELEVANCE
    if state in _RELATED_STATES:
        return RELATED_RELEVANCE
    return 0.0


def _content_candidates(resume: JsonObject) -> list[_ContentCandidate]:
    candidates: list[_ContentCandidate] = []
    experience = _array(_item(resume, "experience", []))
    for experience_index, role in enumerate(experience):
        recency = _role_recency(role)
        role_text = _role_metadata_text(role)
        candidates.append(
            _ContentCandidate(
                path=f"/experience/{experience_index}",
                kind="experience",
                source_index=experience_index,
                source_order=(experience_index,),
                recency_key=recency,
                text=role_text,
                field_paths=_role_metadata_paths(role, experience_index),
                claim_ids=_claim_ids(role, include_children=False),
            )
        )
        bullets = _array(_item(role, "bullets", [])) if isinstance(role, dict) else []
        for bullet_index, bullet in enumerate(bullets):
            path = f"/experience/{experience_index}/bullets/{bullet_index}"
            candidates.append(
                _ContentCandidate(
                    path=path,
                    kind="bullet",
                    source_index=experience_index,
                    source_order=(experience_index, bullet_index),
                    recency_key=recency,
                    text=_field_text(bullet),
                    field_paths=(_claim_field_path(path),),
                    claim_ids=_claim_ids(bullet, include_children=True),
                )
            )
    for skill_index, skill in enumerate(_array(_item(resume, "skills", []))):
        path = f"/skills/{skill_index}"
        candidates.append(
            _ContentCandidate(
                path=path,
                kind="skill",
                source_index=skill_index,
                source_order=(skill_index,),
                recency_key=(0, 0),
                text=_field_text(skill),
                field_paths=(_claim_field_path(path),),
                claim_ids=_claim_ids(skill, include_children=True),
            )
        )
    return candidates


def _score_candidate(candidate: _ContentCandidate, rows: list[_RequirementRow]) -> ContentRelevance:
    matched: list[_RequirementRow] = []
    for row in rows:
        if _row_matches_candidate(row, candidate):
            matched.append(row)
    if not matched:
        return ContentRelevance(
            path=candidate.path,
            kind=candidate.kind,
            source_index=candidate.source_index,
            relevance=UNLINKED_RELEVANCE,
            recency_key=candidate.recency_key,
            source_order=candidate.source_order,
        )
    relevance = max(row.relevance for row in matched)
    return ContentRelevance(
        path=candidate.path,
        kind=candidate.kind,
        source_index=candidate.source_index,
        relevance=relevance,
        recency_key=candidate.recency_key,
        source_order=candidate.source_order,
        requirement_ids=tuple(sorted({row.requirement_id for row in matched})),
        fact_ids=tuple(sorted({fact_id for row in matched for fact_id in row.fact_ids})),
    )


def _row_matches_candidate(row: _RequirementRow, candidate: _ContentCandidate) -> bool:
    candidate_paths = set(candidate.field_paths)
    if candidate_paths.intersection(row.field_paths):
        return True
    candidate_claims = set(candidate.claim_ids)
    if candidate_claims.intersection(row.claim_ids):
        return True
    return any(_term_in_text(term, candidate.text) for term in row.terms)


def _ranked_content(resume: JsonObject, item_relevance: dict[str, ContentRelevance]) -> list[JsonObject]:
    ranked: list[JsonObject] = []
    experience = _array(_item(resume, "experience", []))
    for index, role in enumerate(experience):
        role_id = _item(role, "id", f"experience_{index}") if isinstance(role, dict) else f"experience_{index}"
        paths = [f"/experience/{index}"]
        paths.extend(f"/experience/{index}/bullets/{bullet_index}" for bullet_index, _bullet in enumerate(_array(_item(role, "bullets", []))))
        relevances = [item_relevance[path] for path in paths if path in item_relevance]
        best = sorted(relevances, key=_sort_key)[0] if relevances else None
        ranked.append(
            {
                "kind": "experience",
                "id": role_id,
                "source_index": index,
                "score": best.relevance if best else UNLINKED_RELEVANCE,
                "requirement_ids": list(best.requirement_ids) if best else [],
                "fact_ids": list(best.fact_ids) if best else [],
                "_rank_key": _sort_key(best) if best else (0, 0, 0, index, f"/experience/{index}"),
            }
        )
    for index, _skill in enumerate(_array(_item(resume, "skills", []))):
        path = f"/skills/{index}"
        relevance = item_relevance[path]
        ranked.append(
            {
                "kind": "skill",
                "id": f"skill_{index}",
                "source_index": index,
                "score": relevance.relevance,
                "requirement_ids": list(relevance.requirement_ids),
                "fact_ids": list(relevance.fact_ids),
                "_rank_key": _sort_key(relevance),
            }
        )
    ranked.sort(key=lambda item: tuple(_item(item, "_rank_key", ())))
    for item in ranked:
        item.pop("_rank_key", None)
    return ranked


def _sort_key(relevance: ContentRelevance) -> tuple[Any, ...]:
    source_primary = relevance.source_order[0] if relevance.source_order else 0
    source_secondary = relevance.source_order[1] if len(relevance.source_order) > 1 else -1
    return (
        -relevance.relevance,
        -relevance.recency_key[0],
        -relevance.recency_key[1],
        source_primary,
        source_secondary,
        relevance.path,
    )


def _role_recency(role: Any) -> tuple[int, int]:
    if not isinstance(role, dict):
        return (0, 0)
    end_value = _item(role, "end_date")
    if is_present_date_sentinel(end_value):
        return (9999, 12)
    end = date_key(end_value).key
    if end:
        return end
    start = date_key(_item(role, "start_date")).key
    return start or (0, 0)


def _role_metadata_text(role: Any) -> str:
    if not isinstance(role, dict):
        return _field_text(role)
    return " ".join(_field_text(value) for key, value in sorted(role.items()) if key not in {"bullets", "metadata"})


def _role_metadata_paths(role: Any, experience_index: int) -> tuple[str, ...]:
    if not isinstance(role, dict):
        return (f"experience/{experience_index}",)
    paths = []
    for key in sorted(role):
        if key in {"bullets", "metadata"}:
            continue
        paths.append(f"experience/{experience_index}/{key}")
    return tuple(paths)


def _claim_field_path(path: str) -> str:
    return path.lstrip("/")


def _pointer_path(path: str) -> str:
    return path.lstrip("/")


def _claim_ids(value: Any, *, include_children: bool) -> tuple[str, ...]:
    ids: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            claim_id = _item(item, "claim_id")
            if claim_id:
                ids.add(str(claim_id))
            for provenance in _array(_item(item, "provenance", [])):
                if isinstance(provenance, dict) and _item(provenance, "claim_id"):
                    ids.add(str(_item(provenance, "claim_id")))
            if include_children:
                for key, child in item.items():
                    if key != "metadata":
                        visit(child)
            return
        if include_children and isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return tuple(sorted(ids))


def _field_text(value: Any) -> str:
    payload = to_json_dict(value)
    if isinstance(payload, dict) and "value" in payload:
        return _field_text(_item(payload, "value"))
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, (int, float, bool)):
        return str(payload)
    if isinstance(payload, list):
        return " ".join(_field_text(item) for item in payload)
    if isinstance(payload, dict):
        return " ".join(_field_text(item) for key, item in sorted(payload.items()) if key not in {"metadata", "provenance"})
    return str(payload)


def _term_in_text(term: Any, text: Any) -> bool:
    normalized = _normal_text(term)
    normalized_text = _normal_text(text)
    if not normalized or not normalized_text:
        return False
    if " " in normalized:
        pattern = r"(?<![a-z0-9])" + r"\s+".join(re.escape(part) for part in normalized.split()) + r"(?![a-z0-9])"
        return bool(re.search(pattern, normalized_text))
    words = normalized_text.split()
    return normalized in words or f"{normalized}s" in words or (normalized.endswith("s") and normalized[:-1] in words)


def _normal_text(value: Any) -> str:
    text = str(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _unwrap(value: Any, key: str) -> Any:
    payload = to_json_dict(value)
    if isinstance(payload, dict) and key in payload:
        return payload[key]
    return payload


def _item(mapping: Any, key: str, default: Any = None) -> Any:
    if isinstance(mapping, dict) and key in mapping:
        return mapping[key]
    return default


def _array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
