"""Private support helpers for the SQLite-backed career store."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from typing import Any

from .confirmations import validate_user_confirmation_provenance
from .schemas import InterpretationProposal, InvalidRelationshipConfirmationError, MergeConflictError
from .transactions import transaction_result_payload
from .terms import _STOP_TERMS


JsonObject = dict[str, Any]
RELATIONSHIP_CONFIRMATION_UNCONFIRMED = "unconfirmed"
RELATIONSHIP_CONFIRMATION_USER_CONFIRMED = "user_confirmed"
RELATIONSHIP_CONFIRMATION_STATUSES = {
    RELATIONSHIP_CONFIRMATION_UNCONFIRMED,
    RELATIONSHIP_CONFIRMATION_USER_CONFIRMED,
}
CONFLICT_TERMINAL_STATUSES = {"resolved", "dismissed"}
_YEARS_RE = re.compile(
    r"\b(?P<value>\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty)\+?\s+years?\b",
    re.IGNORECASE,
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
_YEAR_VALUE_TERMS = {str(value) for value in range(0, 101)} | set(_NUMBER_WORDS)
_YEAR_GENERIC_TERMS = {"year", "years", "yr", "yrs"}
_YEAR_CONCEPT_GENERIC_TERMS = {"fact", "skill", "skills"}
_TITLE_FACT_TYPES = {"title", "job title", "employment title", "role", "position", "role title"}
_TITLE_SIGNAL_TERMS = {"title", "job title", "employment title", "role", "position"}
_TITLE_ROLE_GENERIC_TERMS = {
    "current",
    "employment",
    "formal",
    "job",
    "position",
    "role",
    "title",
}

_FORBIDDEN_RESULT_KEYS = {
    "raw_sql",
    "connection",
    "internal_rows",
    "silent_user_verified_promotion",
    "implicit_confirmation",
    "destructive_delete",
    "related_as_equivalent_without_policy",
    "official_score",
    "destructive_resolution",
    "resume_patch",
    "working_resume",
    "base_resume",
}


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _to_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _from_json(value: str | None, fallback: Any) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if value else 0
    normalized = _normalize(value)
    if normalized in {"true", "yes", "confirmed", "user confirmed", "1"}:
        return 1
    if normalized in {"false", "no", "unconfirmed", "0"}:
        return 0
    return None


def _add_if_not_none(target: JsonObject, key: str, value: Any) -> None:
    if value is not None:
        target[key] = value


def _job_metadata(metadata: JsonObject) -> JsonObject:
    job_keys = {"title", "job_title", "company", "employer", "url", "job_url", "source", "source_id"}
    return {key: value for key, value in metadata.items() if key in job_keys}


def _normalize(value: Any) -> str:
    text = str(value).casefold().strip()
    return " ".join("".join(char if char.isalnum() else " " for char in text).split())


def _state_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _validation_error(code: str, field_path: str, allowed_values: set[str]) -> JsonObject:
    return {
        "code": code,
        "field_path": field_path,
        "message": f"Invalid {field_path}.",
        "allowed_values": sorted(allowed_values),
    }


def _has_explicit_confirmation(policy: JsonObject, evidence: JsonObject | None, source: str) -> bool:
    if policy.get("explicit_confirmation") is True:
        return True
    if policy.get("confirmation") is True or policy.get("confirmed") is True:
        return True
    if source in {"user_confirmation", "manual_confirmation", "explicit_user_answer"}:
        return True
    if evidence:
        if evidence.get("source") in {"user_confirmation", "manual_confirmation", "explicit_user_answer"}:
            return True
        metadata = evidence.get("metadata", {})
        if isinstance(metadata, dict) and (metadata.get("explicit") is True or metadata.get("confirmed") is True):
            return True
    return False


def _authority_ref(evidence: JsonObject | None, source: str, fallback_text: str) -> JsonObject:
    if isinstance(evidence, dict):
        ref = dict(evidence)
    else:
        ref = {}
    ref["source"] = str(ref.get("source") or source)
    ref["text"] = str(ref.get("text") or fallback_text)
    if isinstance(ref.get("metadata"), dict):
        ref["metadata"] = dict(ref["metadata"])
    return ref


def _source_document_ref(fact_id: str, evidence: JsonObject | None, source: str, policy: JsonObject) -> JsonObject:
    ref = _authority_ref(evidence, source, "Source document stated this career fact.")
    metadata = dict(ref.get("metadata", {})) if isinstance(ref.get("metadata"), dict) else {}
    if not any(ref.get(key) for key in ("source_id", "source_span")) and not any(
        metadata.get(key) for key in ("document_id", "resume_id", "claim_id")
    ):
        if ref["source"] in {"resume", "job", "document", "profile"}:
            metadata["document_id"] = str(policy.get("document_id") or policy.get("resume_id") or ref["source"])
            metadata["claim_id"] = fact_id
    if metadata:
        ref["metadata"] = metadata
    return ref


def _inference_ref(fact_id: str, evidence: JsonObject | None, source: str) -> JsonObject:
    ref = _authority_ref(evidence, source, "Agent inferred this career fact.")
    metadata = dict(ref.get("metadata", {})) if isinstance(ref.get("metadata"), dict) else {}
    if not any(metadata.get(key) for key in ("agent_id", "model", "rationale", "inference_id")):
        metadata["rationale"] = f"upsertFact inference for {fact_id}"
    ref["metadata"] = metadata
    return ref


def _upsert_user_proposal(fact_id: str, evidence: JsonObject | None, source: str) -> InterpretationProposal:
    ref = _authority_ref(evidence, source, "User explicitly confirmed this career fact.")
    return InterpretationProposal(
        factId=fact_id,
        questionId=None,
        outcome="affirmed",
        confirmedValue=None,
        provenance=[ref],
    )


def _conflict_object(fact_ids: list[str], reason: str, metadata: JsonObject) -> JsonObject:
    clean_fact_ids = sorted(set(fact_id for fact_id in fact_ids if fact_id))
    return {
        "conflict_id": _stable_id("conflict", "|".join(clean_fact_ids), reason),
        "fact_ids": clean_fact_ids,
        "reason": reason,
        "status": "open",
        "evidence_ids": [],
        "metadata": metadata,
    }


def _conflict_from_row(row: sqlite3.Row) -> JsonObject:
    conflict = {
        "conflict_id": str(row["conflict_id"]),
        "fact_ids": _from_json(str(row["fact_ids_json"]), []),
        "reason": str(row["reason"]),
        "status": str(row["status"]),
        "evidence_ids": _from_json(str(row["evidence_ids_json"]), []),
        "metadata": _from_json(str(row["metadata_json"]), {}),
    }
    keys = set(row.keys())
    if "resolution_provenance_json" in keys:
        conflict["resolution_provenance"] = _from_json(row["resolution_provenance_json"], None)
    if "resolved_at" in keys:
        conflict["resolved_at"] = row["resolved_at"]
    if "winning_claim_ref" in keys:
        conflict["winning_claim_ref"] = row["winning_claim_ref"]
    return conflict


def _dedupe_conflicts(conflicts: list[JsonObject]) -> list[JsonObject]:
    deduped = {str(conflict["conflict_id"]): conflict for conflict in conflicts}
    return [deduped[key] for key in sorted(deduped)]


def _clean_result(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean_result(item) for key, item in value.items() if key not in _FORBIDDEN_RESULT_KEYS}
    if isinstance(value, list):
        return [_clean_result(item) for item in value]
    return value


def _normalized_terms(value: JsonObject) -> list[str]:
    raw_terms = value.get("normalized_terms") or []
    if isinstance(raw_terms, str):
        raw_terms = [raw_terms]
    terms = [_normalize(term) for term in raw_terms]
    for key in ("concept", "source_text", "text", "type"):
        if value.get(key):
            terms.append(_normalize(value[key]))
    return sorted(set(_expanded_terms(terms)))


def _expanded_terms(values: list[Any] | set[Any] | tuple[Any, ...]) -> list[str]:
    terms: set[str] = set()
    for value in values:
        normalized = _normalize(value)
        if not normalized:
            continue
        terms.add(normalized)
        pieces = normalized.split()
        terms.update(piece for piece in pieces if len(piece) > 1)
    return sorted(term for term in terms if term)


def _metadata_terms(metadata: JsonObject) -> list[str]:
    terms: list[str] = []
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)):
            terms.append(_normalize(key))
            terms.append(_normalize(value))
        elif isinstance(value, list):
            terms.append(_normalize(key))
            terms.extend(_normalize(item) for item in value if isinstance(item, (str, int, float, bool)))
        elif isinstance(value, dict):
            terms.append(_normalize(key))
            terms.extend(_metadata_terms(value))
    return terms


def _term_in_text(term: str, text: str) -> bool:
    normalized = _normalize(term)
    haystack = f" {_normalize(text)} "
    return bool(normalized and f" {normalized} " in haystack)


def _meaningful_overlap(requirement_terms: set[str], fact_terms: set[str]) -> set[str]:
    overlap = requirement_terms.intersection(fact_terms)
    return {term for term in overlap if term not in _STOP_TERMS}


def _required_years(requirement: JsonObject) -> int | None:
    raw_years = requirement.get("years")
    if isinstance(raw_years, (int, float)) and 0 < int(raw_years) < 60:
        return int(raw_years)
    if isinstance(raw_years, str):
        parsed = _year_claim(raw_years, {_normalize(raw_years)})
        if parsed is not None:
            return int(parsed)
    parsed = _year_claim(
        " ".join(str(requirement.get(key, "")) for key in ("concept", "source_text", "text")),
        set(_normalized_terms(requirement)),
    )
    return int(parsed) if parsed is not None else None


def _direct_resolution(fact: JsonObject, requirement_year: int | None, fact_terms: set[str]) -> tuple[str, JsonObject]:
    if fact["verification_state"] == "conflicted":
        return "possible_match", {"conflicts": [_legacy_state_conflict(fact, "conflicted")]}
    if fact.get("resolution_state") == "explicitly_missing":
        return "explicitly_missing", {}
    fact_year_text = " ".join([str(fact.get("text", "")), *fact.get("normalized_terms", [])])
    fact_year = _year_claim(fact_year_text, fact_terms)
    metadata: JsonObject = {}
    if requirement_year is not None:
        metadata["required_years"] = requirement_year
        if fact_year is not None:
            fact_year_int = int(fact_year)
            metadata["fact_years"] = fact_year_int
            metadata["years_satisfied"] = fact_year_int >= requirement_year
            if fact_year_int < requirement_year:
                return "possible_match", metadata
        else:
            metadata["years_satisfied"] = False
            return "possible_match", metadata
    # Resolution only; verification transitions require explicit confirmation.
    if fact["verification_state"] == "user_verified":
        return "verified_fact_match", metadata
    if fact["verification_state"] in {"unknown", "inferred"}:
        return "possible_match", metadata
    return "exact_match", metadata


def _relationship_policy_match_type(
    relationship_type: str,
    confirmation_status: str,
    config: JsonObject,
    relationship_direction: str | None = None,
) -> str | None:
    clean_type = str(relationship_type)
    clean_status = (
        str(confirmation_status)
        if str(confirmation_status) in RELATIONSHIP_CONFIRMATION_STATUSES
        else RELATIONSHIP_CONFIRMATION_UNCONFIRMED
    )
    allow_unverified_alias = bool(
        config.get("allowUnverifiedAliasCreation", config.get("allow_unverified_alias_creation", False))
    )
    allow_related_as_equivalent = bool(config.get("allow_related_as_equivalent", False))
    if clean_type in {"alias", "equivalent"}:
        if clean_status == RELATIONSHIP_CONFIRMATION_USER_CONFIRMED or allow_unverified_alias:
            return "alias_match"
        return "possible_match"
    if clean_type == "related":
        return "alias_match" if allow_related_as_equivalent else "related_match"
    if clean_type in {"parent", "child"}:
        return "related_match" if relationship_direction == "child_to_parent" else "possible_match"
    if clean_type == "contradicts":
        return None
    return "possible_match"


def _relationship_direction(relationship: JsonObject, fact_id: str) -> str:
    relationship_type = relationship["relationship_type"]
    from_fact_id = relationship["from_fact_id"]
    to_fact_id = relationship["to_fact_id"]
    if relationship_type == "parent":
        return "parent_to_child" if fact_id == from_fact_id else "child_to_parent"
    if relationship_type == "child":
        return "child_to_parent" if fact_id == from_fact_id else "parent_to_child"
    return "from_to" if fact_id == from_fact_id else "to_from"


def _relationship_candidate(
    resolution: str,
    overlap: set[str],
    relationship: JsonObject,
    relationship_direction: str,
    metadata: JsonObject,
    conflicts: list[JsonObject],
) -> JsonObject:
    return {
        "resolution_state": resolution,
        "match_type": resolution,
        "match_terms": sorted(overlap),
        "relationship_id": relationship["relationship_id"],
        "via_relationships": [
            {
                "relationshipId": relationship["relationship_id"],
                "type": relationship["relationship_type"],
                "confirmationStatus": relationship["confirmation_status"],
                "fromFactId": relationship["from_fact_id"],
                "toFactId": relationship["to_fact_id"],
                "direction": relationship_direction,
            }
        ],
        "metadata": metadata,
        "conflicts": conflicts,
    }


def _search_error(store: Any, schema_version: str, code: str, field_path: str) -> JsonObject:
    return _clean_result(
        {
            "schema_version": schema_version,
            "status": "error",
            "mutation_status": "rejected",
            "facts": [],
            "errors": [
                {
                    "type": "InvalidSearchFilterError",
                    "code": code,
                    "field_path": field_path,
                    "message": f"Invalid {field_path}.",
                }
            ],
            "audit": store._audit("searchFacts", mutated=False, reason=code),
        }
    )


def _search_filters(store: Any, schema_version: str, filters: JsonObject | None) -> JsonObject:
    if filters is None:
        filters = {}
    if not isinstance(filters, dict):
        return _search_error(store, schema_version, "invalid_filter_shape", "filters")

    concept = filters.get("concept")
    concept_terms: list[str] = []
    if concept is not None:
        if not isinstance(concept, str):
            return _search_error(store, schema_version, "invalid_filter_shape", "filters.concept")
        concept_terms = _expanded_terms([concept])

    terms_result = _search_filter_terms(store, schema_version, filters.get("terms"), "filters.terms")
    if isinstance(terms_result, dict):
        return terms_result
    terms = terms_result

    alias_result = _search_filter_alias(store, schema_version, filters.get("alias"), terms)
    if alias_result.get("status") == "error":
        return alias_result

    verification_state = filters.get("verification_state")
    if verification_state is not None and not isinstance(verification_state, str):
        return _search_error(store, schema_version, "invalid_filter_shape", "filters.verification_state")

    fact_type = filters.get("type")
    if fact_type is not None and not isinstance(fact_type, str):
        return _search_error(store, schema_version, "invalid_filter_shape", "filters.type")

    return {
        "status": "ok",
        "filters": {
            "concept_terms": concept_terms,
            "terms": terms,
            "alias_enabled": bool(alias_result["enabled"]),
            "alias_terms": alias_result["terms"],
            "allowUnverifiedAliasCreation": bool(alias_result["allowUnverifiedAliasCreation"]),
            "verification_state": verification_state,
            "type": fact_type,
        },
    }


def _search_filter_terms(store: Any, schema_version: str, value: Any, field_path: str) -> list[str] | JsonObject:
    if value is None:
        return []
    if isinstance(value, str):
        raw_terms = [value]
    elif isinstance(value, (list, tuple)):
        if not all(isinstance(item, str) for item in value):
            return _search_error(store, schema_version, "invalid_filter_shape", field_path)
        raw_terms = list(value)
    else:
        return _search_error(store, schema_version, "invalid_filter_shape", field_path)
    return _expanded_terms(raw_terms)


def _search_filter_alias(store: Any, schema_version: str, value: Any, term_filters: list[str]) -> JsonObject:
    if value is None or value is False:
        return {"enabled": False, "terms": [], "allowUnverifiedAliasCreation": False}
    if value is True:
        return {"enabled": True, "terms": term_filters, "allowUnverifiedAliasCreation": False}
    if isinstance(value, str) or isinstance(value, list | tuple):
        terms_result = _search_filter_terms(store, schema_version, value, "filters.alias")
        if isinstance(terms_result, dict):
            return terms_result
        return {"enabled": True, "terms": terms_result, "allowUnverifiedAliasCreation": False}
    if isinstance(value, dict):
        enabled = value.get("enabled", True)
        if not isinstance(enabled, bool):
            return _search_error(store, schema_version, "invalid_filter_shape", "filters.alias.enabled")
        terms_result = _search_filter_terms(store, schema_version, value.get("terms", term_filters), "filters.alias.terms")
        if isinstance(terms_result, dict):
            return terms_result
        allow_unverified = value.get("allowUnverifiedAliasCreation", value.get("allow_unverified_alias_creation", False))
        if not isinstance(allow_unverified, bool):
            return _search_error(store, schema_version, "invalid_filter_shape", "filters.alias.allowUnverifiedAliasCreation")
        return {
            "enabled": enabled,
            "terms": terms_result if enabled else [],
            "allowUnverifiedAliasCreation": allow_unverified,
        }
    return _search_error(store, schema_version, "invalid_filter_shape", "filters.alias")


def _search_allowed_fact_ids(store: Any, conn: sqlite3.Connection, filters: JsonObject) -> set[str]:
    allowed = {str(row["fact_id"]) for row in store._fact_rows(conn=conn, active_only=True)}
    if filters["verification_state"] is not None:
        allowed &= {
            str(row["fact_id"])
            for row in conn.execute(
                """
                SELECT fact_id FROM facts
                WHERE merged_into_fact_id IS NULL
                  AND verification_state = ?
                """,
                (filters["verification_state"],),
            ).fetchall()
        }
    if filters["type"] is not None:
        allowed &= {
            str(row["fact_id"])
            for row in conn.execute(
                """
                SELECT fact_id FROM facts
                WHERE merged_into_fact_id IS NULL
                  AND type = ?
                """,
                (filters["type"],),
            ).fetchall()
        }
    if filters["terms"]:
        term_ids = _search_fact_ids_for_terms(conn, filters["terms"])
        if filters["alias_enabled"]:
            term_ids |= _search_fact_ids_for_alias_terms(conn, filters)
        allowed &= term_ids
    if filters["concept_terms"]:
        allowed &= _search_fact_ids_for_concept(conn, filters["concept_terms"])
    if filters["alias_terms"] and not filters["terms"]:
        allowed &= _search_fact_ids_for_alias_terms(conn, filters)
    return allowed


def _search_fact_ids_for_terms(conn: sqlite3.Connection, terms: list[str]) -> set[str]:
    placeholders = ",".join("?" for _ in terms)
    rows = conn.execute(
        f"""
        SELECT DISTINCT f.fact_id
        FROM facts AS f, json_each(f.normalized_terms_json) AS term
        WHERE f.merged_into_fact_id IS NULL
          AND term.value IN ({placeholders})
        """,
        tuple(terms),
    ).fetchall()
    return {str(row["fact_id"]) for row in rows}


def _search_fact_ids_for_concept(conn: sqlite3.Connection, terms: list[str]) -> set[str]:
    matched: set[str] = set()
    rows = conn.execute(
        """
        SELECT fact_id, text, canonical_name, description
        FROM facts
        WHERE merged_into_fact_id IS NULL
        ORDER BY type, text, fact_id
        """
    ).fetchall()
    for row in rows:
        haystacks = [str(row["text"]), str(row["canonical_name"] or ""), str(row["description"] or "")]
        if any(_term_in_text(term, haystack) for term in terms for haystack in haystacks):
            matched.add(str(row["fact_id"]))
    return matched


def _search_fact_ids_for_alias_terms(conn: sqlite3.Connection, filters: JsonObject) -> set[str]:
    terms = list(filters["alias_terms"])
    if not terms:
        return set()
    placeholders = ",".join("?" for _ in terms)
    policy = {"allowUnverifiedAliasCreation": filters["allowUnverifiedAliasCreation"]}
    rows = conn.execute(
        f"""
        SELECT DISTINCT f.fact_id, r.relationship_type, r.confirmation_status
        FROM facts AS f
        JOIN relationships AS r
          ON r.from_fact_id = f.fact_id OR r.to_fact_id = f.fact_id
        JOIN facts AS other
          ON other.fact_id = CASE
               WHEN r.from_fact_id = f.fact_id THEN r.to_fact_id
               ELSE r.from_fact_id
             END
        JOIN json_each(other.normalized_terms_json) AS term
        WHERE f.merged_into_fact_id IS NULL
          AND other.merged_into_fact_id IS NULL
          AND r.relationship_type IN ('alias', 'equivalent')
          AND term.value IN ({placeholders})
        """,
        tuple(terms),
    ).fetchall()
    return {
        str(row["fact_id"])
        for row in rows
        if _relationship_policy_match_type(
            str(row["relationship_type"]),
            str(row["confirmation_status"] or "unconfirmed"),
            policy,
        )
        == "alias_match"
    }


def _search_fact_match_terms(fact: JsonObject) -> set[str]:
    return set(
        _expanded_terms(
            [
                *fact.get("normalized_terms", []),
                fact.get("text", ""),
                fact.get("canonical_name", ""),
                fact.get("description", ""),
            ]
        )
    )


def _search_fact_normalized_terms(fact: JsonObject) -> set[str]:
    return set(_expanded_terms(fact.get("normalized_terms", [])))


def _search_fact_concept_terms(fact: JsonObject) -> set[str]:
    terms: set[str] = set()
    for value in (fact.get("text", ""), fact.get("canonical_name", ""), fact.get("description", "")):
        terms.update(_expanded_terms([value]))
    return terms


def _search_alias_terms(store: Any, fact_id: str, terms: set[str], filters: JsonObject, conn: sqlite3.Connection | None = None) -> set[str]:
    if not terms:
        return set()
    policy = {"allowUnverifiedAliasCreation": filters["allowUnverifiedAliasCreation"]}
    matched: set[str] = set()
    for relationship in store._relationships_for_fact(fact_id, conn=conn):
        if relationship["relationship_type"] not in {"alias", "equivalent"}:
            continue
        if (
            _relationship_policy_match_type(
                relationship["relationship_type"],
                relationship["confirmation_status"],
                policy,
            )
            != "alias_match"
        ):
            continue
        other_id = relationship["to_fact_id"] if relationship["from_fact_id"] == fact_id else relationship["from_fact_id"]
        other_row = store._fact_row(other_id, conn=conn)
        if other_row is None or other_row["merged_into_fact_id"] is not None:
            continue
        other = store._fact_from_row(other_row, conn=conn)
        if not other:
            continue
        matched.update(_search_fact_match_terms(other).intersection(terms))
    return matched


def _evidence_for_fact_matching_terms(
    store: Any,
    fact_id: str,
    terms: set[str],
    conn: sqlite3.Connection | None = None,
) -> list[JsonObject]:
    evidence = store._evidence_for_fact(fact_id, conn=conn)
    if not terms:
        return evidence
    filtered: list[JsonObject] = []
    for row in evidence:
        row_terms = set(_expanded_terms(_normalized_terms(row)))
        metadata = row.get("metadata", {})
        if isinstance(metadata, dict):
            row_terms.update(_expanded_terms(_metadata_terms(metadata)))
        if row_terms.intersection(terms):
            filtered.append(row)
    return filtered


def _store_fact_match_terms(store: Any, fact_id: str, conn: sqlite3.Connection | None = None) -> set[str]:
    fact = store._fact_from_row(store._fact_row(fact_id, conn=conn), conn=conn)
    terms: list[str] = []
    if fact:
        terms.extend(fact.get("normalized_terms", []))
        terms.append(_normalize(fact.get("text", "")))
        terms.append(_normalize(fact.get("canonical_name", "")))
        terms.append(_normalize(fact.get("description", "")))
        metadata = fact.get("metadata", {})
        if isinstance(metadata, dict):
            terms.extend(_metadata_terms(metadata))
    for evidence in store._evidence_for_fact(fact_id, conn=conn):
        terms.append(_normalize(evidence.get("text", "")))
        terms.extend(_normalized_terms(evidence))
        metadata = evidence.get("metadata", {})
        if isinstance(metadata, dict):
            terms.extend(_metadata_terms(metadata))
    return set(_expanded_terms(terms))


def _relationship_conflict_signals(
    conn: sqlite3.Connection,
    requirement_id: str,
    requirement_terms: set[str],
    fact_match_terms: Any,
) -> list[JsonObject]:
    if not requirement_terms:
        return []
    signals: list[JsonObject] = []
    rows = conn.execute(
        """
        SELECT * FROM relationships
        WHERE relationship_type = 'contradicts'
        ORDER BY relationship_id, from_fact_id, to_fact_id
        """
    ).fetchall()
    for row in rows:
        relationship_id = str(row["relationship_id"])
        from_fact_id = str(row["from_fact_id"])
        to_fact_id = str(row["to_fact_id"])
        from_overlap = _meaningful_overlap(requirement_terms, fact_match_terms(from_fact_id, conn=conn))
        to_overlap = _meaningful_overlap(requirement_terms, fact_match_terms(to_fact_id, conn=conn))
        if to_overlap:
            signals.append(
                {
                    "type": "contradicts",
                    "factId": from_fact_id,
                    "relationshipId": relationship_id,
                    "contradictedFactId": to_fact_id,
                    "requirementId": requirement_id,
                }
            )
        if from_overlap:
            signals.append(
                {
                    "type": "contradicts",
                    "factId": to_fact_id,
                    "relationshipId": relationship_id,
                    "contradictedFactId": from_fact_id,
                    "requirementId": requirement_id,
                }
            )
    return signals


def _dedupe_conflict_signals(signals: list[JsonObject]) -> list[JsonObject]:
    deduped = {
        (
            str(signal["requirementId"]),
            str(signal["relationshipId"]),
            str(signal["factId"]),
            str(signal["contradictedFactId"]),
        ): signal
        for signal in signals
    }
    return [deduped[key] for key in sorted(deduped)]


def _confirm_relationship(store: Any, schema_version: str, relationshipId: str, provenance: list[JsonObject]) -> JsonObject:
    relationship_id = str(relationshipId)
    now = store._clock()
    with store._transaction("confirmRelationship", "updated") as txn:
        conn = txn.connection
        assert conn is not None
        txn.touch("relationship_id", relationship_id)
        row = conn.execute("SELECT * FROM relationships WHERE relationship_id = ?", (relationship_id,)).fetchone()
        if row is None:
            txn.set_mutation_status("rejected")
            result = _relationship_confirmation_error(
                store,
                schema_version,
                relationship_id,
                InvalidRelationshipConfirmationError(
                    "unknown_relationship_id",
                    "relationshipId",
                    "Relationship ID does not reference an existing relationship.",
                ),
            )
            result["transaction_result"] = None
        else:
            try:
                clean_provenance = validate_user_confirmation_provenance(provenance)
            except InvalidRelationshipConfirmationError as exc:
                txn.set_mutation_status("rejected")
                result = _relationship_confirmation_error(store, schema_version, relationship_id, exc)
                result["transaction_result"] = None
            else:
                if str(row["confirmation_status"] or RELATIONSHIP_CONFIRMATION_UNCONFIRMED) == RELATIONSHIP_CONFIRMATION_USER_CONFIRMED:
                    txn.set_mutation_status("unchanged")
                    result = {
                        "schema_version": schema_version,
                        "status": "unchanged",
                        "mutation_status": "unchanged",
                        "relationship_id": relationship_id,
                        "confirmation_status": RELATIONSHIP_CONFIRMATION_USER_CONFIRMED,
                        "confirmed_by_provenance": _from_json(row["confirmed_by_provenance"], []),
                        "confirmed_at": row["confirmed_at"],
                        "transaction_result": None,
                        "audit": store._audit("confirmRelationship", mutated=True),
                    }
                else:
                    conn.execute(
                        """
                        UPDATE relationships
                        SET confirmation_status = ?, confirmed_by_provenance = ?, confirmed_at = ?
                        WHERE relationship_id = ?
                        """,
                        (RELATIONSHIP_CONFIRMATION_USER_CONFIRMED, _to_json(clean_provenance), now, relationship_id),
                    )
                    result = {
                        "schema_version": schema_version,
                        "status": "updated",
                        "mutation_status": "updated",
                        "relationship_id": relationship_id,
                        "confirmation_status": RELATIONSHIP_CONFIRMATION_USER_CONFIRMED,
                        "confirmed_by_provenance": clean_provenance,
                        "confirmed_at": now,
                        "transaction_result": None,
                        "audit": store._audit("confirmRelationship", mutated=True),
                    }
    transaction_result = txn.result
    result["transaction_result"] = transaction_result_payload(transaction_result)
    return _clean_result(result)


def _relationship_confirmation_error(
    store: Any,
    schema_version: str,
    relationship_id: str,
    error: InvalidRelationshipConfirmationError,
) -> JsonObject:
    return _clean_result(
        {
            "schema_version": schema_version,
            "status": "error",
            "mutation_status": "rejected",
            "relationship_id": relationship_id,
            "confirmation_status": RELATIONSHIP_CONFIRMATION_UNCONFIRMED,
            "errors": [error.to_error()],
            "audit": store._audit("confirmRelationship", mutated=False, reason=error.code),
        }
    )


def _merged_metadata(existing: JsonObject, incoming: Any) -> JsonObject:
    merged = dict(existing) if isinstance(existing, dict) else {}
    if isinstance(incoming, dict):
        merged.update(incoming)
    return merged


def _merge_alias_terms(survivor_row: sqlite3.Row, merged_row: sqlite3.Row) -> list[str]:
    terms: list[str] = []
    for row in (survivor_row, merged_row):
        terms.extend(_from_json(str(row["normalized_terms_json"]), []))
        terms.append(_normalize(row["text"]))
        terms.append(_normalize(row["canonical_name"] or ""))
        terms.append(_normalize(row["description"] or ""))
    return sorted(set(term for term in _expanded_terms(terms) if term))


def _merge_provenance_payload(provenance: JsonObject | list[JsonObject] | None) -> Any:
    if isinstance(provenance, dict):
        return {
            key: value
            for key, value in provenance.items()
            if not key.startswith("_") and isinstance(value, (str, int, float, bool, list, dict, type(None)))
        }
    if isinstance(provenance, list):
        cleaned = []
        for item in provenance:
            if isinstance(item, dict):
                cleaned.append(_merge_provenance_payload(item))
        return cleaned
    return {}


def _resolve_fact_id(conn: sqlite3.Connection, fact_id: str) -> str | None:
    current = str(fact_id)
    seen: set[str] = set()
    while current not in seen:
        seen.add(current)
        row = conn.execute(
            "SELECT fact_id, merged_into_fact_id FROM facts WHERE fact_id = ?",
            (current,),
        ).fetchone()
        if row is None:
            return None
        redirected = row["merged_into_fact_id"]
        if redirected is None or not str(redirected):
            return str(row["fact_id"])
        current = str(redirected)
    return None


def _merge_conflict(conn: sqlite3.Connection, survivor_id: str, merged_id: str) -> MergeConflictError | None:
    if survivor_id == merged_id:
        return MergeConflictError("self_merge", survivor_id, merged_id, "Cannot merge a fact into itself.")
    survivor_row = conn.execute("SELECT fact_id, merged_into_fact_id FROM facts WHERE fact_id = ?", (survivor_id,)).fetchone()
    merged_row = conn.execute("SELECT fact_id, merged_into_fact_id FROM facts WHERE fact_id = ?", (merged_id,)).fetchone()
    if survivor_row is None or merged_row is None:
        return MergeConflictError("unknown_fact_id", survivor_id, merged_id, "Both merge facts must exist.")
    if survivor_row["merged_into_fact_id"] is not None or merged_row["merged_into_fact_id"] is not None:
        return MergeConflictError("already_merged", survivor_id, merged_id, "Merge inputs must not already be redirected.")
    return None


def _merge_conflict_result(error: MergeConflictError, schema_version: str, audit: JsonObject) -> JsonObject:
    return _clean_result(
        {
            "schema_version": schema_version,
            "status": "error",
            "mutation_status": "rejected",
            "fact_id": error.survivor_id,
            "survivor_fact_id": error.survivor_id,
            "merged_fact_id": error.merged_id,
            "verification_state": "unknown",
            "conflicts": [],
            "confirmation_required": False,
            "errors": [error.to_error()],
            "audit": audit,
        }
    )


def _insert_merge_alias_relationship(
    conn: sqlite3.Connection,
    survivor_id: str,
    merged_id: str,
    provenance: JsonObject | list[JsonObject] | None,
    now: str,
) -> None:
    evidence = {
        "source": "mergeFacts",
        "text": "Merged fact retained as an alias.",
        "provenance": _merge_provenance_payload(provenance),
    }
    relationship_id = _stable_id("relationship", survivor_id, merged_id, "alias", _to_json(evidence))
    conn.execute(
        """
        INSERT OR IGNORE INTO relationships (
            relationship_id, from_fact_id, to_fact_id, relationship_type, evidence_json, created_at,
            metadata_json, confidence, confirmation_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            relationship_id,
            survivor_id,
            merged_id,
            "alias",
            _to_json(evidence),
            now,
            _to_json({"source": "mergeFacts"}),
            None,
            RELATIONSHIP_CONFIRMATION_UNCONFIRMED,
        ),
    )


def _repoint_job_matches(conn: sqlite3.Connection, survivor_id: str, merged_id: str) -> None:
    rows = conn.execute("SELECT job_match_id, fact_ids_json FROM job_matches ORDER BY job_match_id").fetchall()
    for row in rows:
        fact_ids = [str(fact_id) for fact_id in _from_json(str(row["fact_ids_json"]), [])]
        if merged_id not in fact_ids:
            continue
        repointed = sorted({survivor_id if fact_id == merged_id else fact_id for fact_id in fact_ids})
        conn.execute(
            "UPDATE job_matches SET fact_ids_json = ? WHERE job_match_id = ?",
            (_to_json(repointed), row["job_match_id"]),
        )


def _after_merge_repoint(provenance: JsonObject | list[JsonObject] | None) -> None:
    if isinstance(provenance, dict):
        hook = provenance.get("_after_repoint")
        if callable(hook):
            hook("mergeFacts")


def _legacy_state_conflict(fact: JsonObject, state: str) -> JsonObject:
    return _conflict_object(
        [str(fact.get("fact_id", ""))],
        f"legacy {state} verification state",
        {
            "verification_state": state,
            "fact_id": str(fact.get("fact_id", "")),
        },
    )


def _year_claim(text: str, terms: set[str]) -> int | None:
    combined = " ".join([str(text), *terms])
    match = _YEARS_RE.search(combined)
    if match is None:
        return None
    value = match.group("value").casefold()
    if value.isdigit():
        return int(value)
    return _NUMBER_WORDS[value]


def _year_claim_tuple(claim: JsonObject, terms: set[str]) -> tuple[str, int] | None:
    fields = _claim_fields(claim)
    years = _year_claim(" ".join(fields), terms)
    if years is None:
        return None
    concept = _year_claim_concept(fields, _claim_normalized_terms_only(claim) or terms)
    if not concept:
        return None
    return (concept, years)


def _title_claim(claim: JsonObject, terms: set[str]) -> tuple[str, str] | None:
    if not _is_structured_title_claim(claim, terms):
        return None
    canonical_name = _optional_text(claim.get("canonical_name"))
    description = _optional_text(claim.get("description"))
    title = _normalize(canonical_name or description or "")
    if not title:
        return None
    role = _title_role_slot(claim, terms, title)
    if not role:
        return None
    return (role, title)


def _claim_fields(claim: JsonObject) -> list[str]:
    fields = []
    for key in ("text", "canonical_name", "description"):
        value = claim.get(key)
        if isinstance(value, (str, int, float, bool)):
            fields.append(str(value))
    return fields


def _claim_normalized_terms_only(claim: JsonObject) -> set[str]:
    raw_terms = claim.get("normalized_terms") or []
    if isinstance(raw_terms, str):
        raw_terms = [raw_terms]
    if not isinstance(raw_terms, (list, tuple, set)):
        return set()
    return set(_expanded_terms([term for term in raw_terms if isinstance(term, str)]))


def _year_claim_concept(fields: list[str], terms: set[str]) -> str:
    concept_terms = _expanded_terms([*fields, *terms])
    return " ".join(
        sorted(
            term
            for term in concept_terms
            if term
            and term not in _YEAR_VALUE_TERMS
            and term not in _YEAR_GENERIC_TERMS
            and term not in _YEAR_CONCEPT_GENERIC_TERMS
            and not _has_year_component(term)
            and not _YEARS_RE.fullmatch(term)
        )
    )


def _has_year_component(term: str) -> bool:
    pieces = set(term.split())
    return bool(pieces.intersection(_YEAR_GENERIC_TERMS) or pieces.intersection(_YEAR_VALUE_TERMS))


def _is_structured_title_claim(claim: JsonObject, terms: set[str]) -> bool:
    if not (_optional_text(claim.get("canonical_name")) or _optional_text(claim.get("description"))):
        return False
    fact_type = _normalize(claim.get("type", ""))
    if fact_type in _TITLE_FACT_TYPES:
        return True
    expanded_terms = set(_expanded_terms(terms))
    return bool(expanded_terms.intersection(_TITLE_SIGNAL_TERMS))


def _title_role_slot(claim: JsonObject, terms: set[str], title: str) -> str:
    title_terms = set(_expanded_terms([title]))
    description = _optional_text(claim.get("description"))
    if description and _normalize(description) != title:
        fallback_role = _normalize(description)
        description_terms = [
            term
            for term in _expanded_terms([description])
            if term
            and term not in title_terms
            and term not in _TITLE_ROLE_GENERIC_TERMS
            and not _has_title_role_generic_component(term)
        ]
        if description_terms:
            return " ".join(sorted(description_terms))
        if fallback_role:
            return fallback_role
    role_source_terms = _claim_normalized_terms_only(claim) or terms
    role_terms = [
        term
        for term in _expanded_terms(role_source_terms)
        if term
        and term not in title_terms
        and term not in _TITLE_ROLE_GENERIC_TERMS
        and not _has_title_role_generic_component(term)
    ]
    if role_terms:
        return " ".join(sorted(role_terms))
    return ""


def _has_title_role_generic_component(term: str) -> bool:
    return bool(set(term.split()).intersection(_TITLE_ROLE_GENERIC_TERMS))
