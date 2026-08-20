"""Persisted-artifact readers for CLI inspect commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from career_store import openCareerStore


JsonObject = dict[str, Any]
StoreFactory = Callable[[str], Any]


def inspect_requirement(
    workspace: Path,
    requirement_id: str,
    *,
    store_factory: StoreFactory = openCareerStore,
) -> JsonObject:
    """Return persisted requirement state without computing or defaulting it."""

    paths = _paths(workspace)
    match_report = paths["reports_dir"] / "match.json"
    match_result = _read_json(match_report, None)
    if not isinstance(match_result, dict) or not match_result:
        return _no_requirement_data(requirement_id, "missing_match_report")

    requirement = _persisted_requirement(match_result, requirement_id)
    if requirement is None:
        return _no_requirement_data(requirement_id, "requirement_not_in_match_report")

    fact_ids = _supporting_fact_ids(requirement)
    supporting_facts = _supporting_facts(paths["career_db"], fact_ids, store_factory)
    return {
        "status": "ok",
        "exit_code": 0,
        "requirement_id": requirement_id,
        **requirement,
        "supporting_fact_ids": fact_ids,
        "supporting_facts": supporting_facts,
        "supporting_evidence_refs": _supporting_evidence_refs(requirement, supporting_facts),
        "resolution_records": [
            {
                "source_artifact": "reports/match.json",
                "requirement_id": requirement_id,
                "resolution_state": requirement.get("resolution_state"),
                "matched_fact_ids": fact_ids,
            }
        ],
        "source_artifacts": {"match_report": str(match_report)},
    }


def _no_requirement_data(requirement_id: str, reason: str) -> JsonObject:
    return {
        "status": "no_data",
        "exit_code": 0,
        "requirement_id": requirement_id,
        "reason": reason,
        "message": "No persisted requirement resolution exists; run `resume match` before inspecting requirement state.",
        "source_artifacts": {"match_report": "reports/match.json"},
    }


def _persisted_requirement(match_result: JsonObject, requirement_id: str) -> JsonObject | None:
    for collection_name in ("requirement_results", "requirements"):
        collection = match_result.get(collection_name)
        if not isinstance(collection, list):
            continue
        for item in collection:
            if isinstance(item, dict) and str(item.get("requirement_id") or "") == requirement_id:
                return dict(item)
    return None


def _supporting_fact_ids(requirement: JsonObject) -> list[str]:
    ordered: list[str] = []
    for key in ("matched_fact_ids", "fact_ids"):
        _extend_unique(ordered, requirement.get(key))
    _extend_unique(ordered, [requirement.get("fact_id"), requirement.get("factId")])
    evidence = requirement.get("evidence")
    if isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, dict):
                _extend_unique(ordered, [item.get("fact_id"), item.get("factId")])
                _extend_unique(ordered, item.get("fact_ids"))
    supporting = requirement.get("supporting_facts")
    if isinstance(supporting, list):
        for item in supporting:
            if isinstance(item, dict):
                _extend_unique(ordered, [item.get("fact_id"), item.get("factId")])
    return ordered


def _supporting_facts(career_db: Path, fact_ids: list[str], store_factory: StoreFactory) -> list[JsonObject]:
    if not fact_ids:
        return []
    store = store_factory(str(career_db))
    facts = []
    for fact_id in fact_ids:
        payload = store.getFact(fact_id)
        if isinstance(payload, dict) and payload.get("status") == "ok":
            facts.append(
                {
                    "fact_id": fact_id,
                    "fact": payload.get("fact"),
                    "evidence": payload.get("evidence", []),
                    "relationships": payload.get("relationships", []),
                    "conflicts": payload.get("conflicts", []),
                }
            )
    return facts


def _supporting_evidence_refs(requirement: JsonObject, supporting_facts: list[JsonObject]) -> list[JsonObject]:
    refs: list[JsonObject] = []
    for evidence in requirement.get("evidence", []):
        if not isinstance(evidence, dict):
            continue
        ref = _evidence_ref(evidence)
        if ref:
            refs.append(ref)
    for item in supporting_facts:
        fact_id = str(item.get("fact_id") or "")
        if fact_id:
            refs.append({"type": "fact", "ref": f"career-store/facts/{fact_id}", "fact_id": fact_id})
        evidence_items = item.get("evidence", [])
        if isinstance(evidence_items, list):
            for evidence in evidence_items:
                if isinstance(evidence, dict):
                    evidence_id = str(evidence.get("evidence_id") or "")
                    if evidence_id:
                        refs.append({"type": "evidence", "ref": f"career-store/evidence/{evidence_id}", "evidence_id": evidence_id, "fact_id": fact_id})
    return _unique_refs(refs)


def _evidence_ref(evidence: JsonObject) -> JsonObject:
    evidence_id = str(evidence.get("evidence_id") or "")
    if evidence_id:
        return {"type": "evidence", "ref": f"career-store/evidence/{evidence_id}", "evidence_id": evidence_id}
    fact_id = str(evidence.get("fact_id") or evidence.get("factId") or "")
    if fact_id:
        return {"type": "fact", "ref": f"career-store/facts/{fact_id}", "fact_id": fact_id}
    relationship_id = str(evidence.get("relationship_id") or "")
    if relationship_id:
        return {"type": "relationship", "ref": f"career-store/relationships/{relationship_id}", "relationship_id": relationship_id}
    source = str(evidence.get("source") or "")
    if source:
        return {"type": "match_evidence", "ref": f"reports/match.json#{source}", "source": source}
    return {}


def _unique_refs(refs: list[JsonObject]) -> list[JsonObject]:
    unique: list[JsonObject] = []
    seen: set[str] = set()
    for ref in refs:
        key = json.dumps(ref, sort_keys=True)
        if key not in seen:
            unique.append(ref)
            seen.add(key)
    return unique


def _extend_unique(target: list[str], values: Any) -> None:
    if values is None:
        return
    if isinstance(values, (str, int, float)):
        values = [values]
    if not isinstance(values, list):
        return
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text not in target:
            target.append(text)


def _paths(workspace: Path) -> dict[str, Path]:
    return {
        "career_db": workspace / "data" / "career.db",
        "reports_dir": workspace / "reports",
    }


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return fallback
    return json.loads(text)
