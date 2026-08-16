"""Resolution-loop DTO and predicate helpers for workflow."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]


def empty_resolution_loop_state() -> JsonObject:
    return {
        "open_requirements": [],
        "asked_questions": [],
        "facts_since_last_match": [],
        "iteration_count": 0,
    }


def normalize_resolution_loop_state(value: Any, run_state: JsonObject | None = None) -> JsonObject:
    raw = value if isinstance(value, dict) else {}
    normalized = empty_resolution_loop_state()
    normalized["open_requirements"] = ordered_requirement_entries(raw.get("open_requirements", []))
    normalized["asked_questions"] = _ordered_asked_question_entries(raw.get("asked_questions", []))
    facts = raw.get("facts_since_last_match")
    if isinstance(facts, list):
        normalized["facts_since_last_match"] = _dedupe([str(item) for item in facts])
    if run_state is not None:
        normalized["facts_since_last_match"] = facts_since_last_match(run_state)
    normalized["iteration_count"] = int(raw.get("iteration_count", 0)) if isinstance(raw.get("iteration_count", 0), int) else 0
    return normalized


def update_resolution_loop_state(
    run_state: JsonObject,
    checkpoint: str,
    checkpoint_result: JsonObject,
    question_records: list[JsonObject],
) -> None:
    loop_state = normalize_resolution_loop_state(run_state.get("resolution_loop_state", {}), run_state)
    if checkpoint == "MATCH_BASE" and run_state.get("resolution_match_rerun_pending") is True:
        loop_state["iteration_count"] = int(loop_state.get("iteration_count", 0)) + 1
    if checkpoint == "MATCH_BASE":
        match_result = _match_result_from_checkpoint_payload(checkpoint_result)
        loop_state["open_requirements"] = _merge_match_requirements(loop_state.get("open_requirements", []), match_result)
        run_state["resolution_blocking_reasons"] = _match_blocking_reasons(match_result) if _match_decision(match_result) == "blocked" else []
    else:
        loop_state["open_requirements"] = _apply_requirement_status_updates(
            loop_state.get("open_requirements", []),
            checkpoint_result,
        )
    loop_state["asked_questions"] = _ordered_asked_question_entries(
        list(loop_state.get("asked_questions", [])) + _asked_question_entries(question_records)
    )
    loop_state["facts_since_last_match"] = facts_since_last_match(run_state)
    run_state["resolution_loop_state"] = normalize_resolution_loop_state(loop_state, run_state)


def resolution_loop_surface(run_state: JsonObject) -> JsonObject:
    loop_state = normalize_resolution_loop_state(run_state.get("resolution_loop_state", {}), run_state)
    return {
        "state": loop_state,
        "next_topic": _next_open_requirement(loop_state, run_state),
        "predicate": {
            "branch": "not_applicable",
            "decision": None,
            "action": "advance",
            "blocking_reasons": [],
            "unresolved_requirements": _loop_unresolved_requirements(loop_state),
        },
    }


def resolution_loop_decision(run_state: JsonObject) -> JsonObject:
    loop_state = normalize_resolution_loop_state(run_state.get("resolution_loop_state", {}), run_state)
    if facts_beyond_match_watermark(run_state):
        predicate = {
            "branch": "rerun_match_for_new_facts",
            "decision": None,
            "action": "rerun_match",
            "blocking_reasons": [],
            "unresolved_requirements": _loop_unresolved_requirements(loop_state),
        }
        return {"state": loop_state, "next_topic": None, "predicate": predicate}

    match_result = _last_recorded_match_result(run_state)
    decision = _match_decision(match_result)
    unresolved = _loop_unresolved_requirements(loop_state)
    next_topic = _next_open_requirement(loop_state, run_state)
    if decision == "blocked":
        reasons = _dedupe(list(run_state.get("resolution_blocking_reasons", [])) + _match_blocking_reasons(match_result))
        predicate = {
            "branch": "d_blocked_hard_requirement",
            "decision": decision,
            "action": "blocked",
            "blocking_reasons": reasons or ["unresolved_hard_requirements"],
            "unresolved_requirements": unresolved,
        }
    elif decision == "resolve_gaps" and next_topic is not None:
        predicate = {
            "branch": "b_resolve_gaps_next_topic",
            "decision": decision,
            "action": "select_next_topic",
            "blocking_reasons": ["resolution_loop_next_topic"],
            "unresolved_requirements": unresolved,
        }
    elif decision == "resolve_gaps":
        predicate = {
            "branch": "c_resolve_gaps_all_exhausted",
            "decision": decision,
            "action": "advance_with_unresolved",
            "blocking_reasons": [],
            "unresolved_requirements": unresolved,
        }
    else:
        predicate = {
            "branch": "a_continue",
            "decision": decision,
            "action": "advance",
            "blocking_reasons": [],
            "unresolved_requirements": unresolved,
        }
    return {"state": loop_state, "next_topic": next_topic, "predicate": predicate}


def facts_beyond_match_watermark(run_state: JsonObject) -> bool:
    return bool(_fact_id_set(run_state.get("facts_verified", [])) - _fact_id_set(run_state.get("last_match_fact_watermark", [])))


def facts_since_last_match(run_state: JsonObject) -> list[str]:
    watermark = _fact_id_set(run_state.get("last_match_fact_watermark", []))
    return [str(value) for value in run_state.get("facts_verified", []) if str(value) not in watermark]


def ordered_requirement_entries(values: Any) -> list[JsonObject]:
    entries: list[JsonObject] = []
    if not isinstance(values, list):
        return entries
    for item in values:
        if not isinstance(item, dict):
            continue
        requirement_id = item.get("requirement_id")
        if not isinstance(requirement_id, str) or not requirement_id:
            continue
        entries.append(
            {
                "requirement_id": requirement_id,
                "impact_rank": _impact_rank_value(item),
                "status": _loop_requirement_status(item.get("status")),
            }
        )
    return sorted(entries, key=_requirement_entry_sort_key)


def _ordered_asked_question_entries(values: Any) -> list[JsonObject]:
    entries: list[JsonObject] = []
    seen: set[str] = set()
    if not isinstance(values, list):
        return entries
    for item in values:
        if not isinstance(item, dict):
            continue
        question_id = item.get("question_id")
        requirement_id = item.get("requirement_id")
        interaction_ref = item.get("interaction_ref")
        if not all(isinstance(value, str) and value for value in (question_id, requirement_id, interaction_ref)):
            continue
        entry = {"question_id": question_id, "requirement_id": requirement_id, "interaction_ref": interaction_ref}
        identity = _stable_hash(entry)
        if identity in seen:
            continue
        seen.add(identity)
        entries.append(entry)
    return entries


def _merge_match_requirements(existing: Any, match_result: JsonObject) -> list[JsonObject]:
    by_id = {entry["requirement_id"]: dict(entry) for entry in ordered_requirement_entries(existing)}
    unresolved_ids = _match_unresolved_ids(match_result)
    seen_match_ids: set[str] = set()
    results = match_result.get("requirement_results", [])
    for result in results if isinstance(results, list) else []:
        if not isinstance(result, dict):
            continue
        requirement_id = result.get("requirement_id")
        if not isinstance(requirement_id, str) or not requirement_id:
            continue
        seen_match_ids.add(requirement_id)
        prior = by_id.get(requirement_id, {})
        status = _loop_requirement_status(prior.get("status"))
        if requirement_id not in unresolved_ids:
            status = "resolved"
        elif status == "resolved":
            status = "open"
        by_id[requirement_id] = {
            "requirement_id": requirement_id,
            "impact_rank": _impact_rank_value(
                {
                    **result,
                    "impact_rank": result.get(
                        "impact_rank",
                        result.get("impact", result.get("max_score", result.get("weight", prior.get("impact_rank", 0.0)))),
                    ),
                }
            ),
            "status": status,
        }
    for requirement_id in sorted(unresolved_ids - seen_match_ids):
        prior = by_id.get(requirement_id, {})
        by_id[requirement_id] = {
            "requirement_id": requirement_id,
            "impact_rank": _impact_rank_value(prior),
            "status": _loop_requirement_status(prior.get("status")),
        }
    return sorted(by_id.values(), key=_requirement_entry_sort_key)


def _apply_requirement_status_updates(existing: Any, checkpoint_result: JsonObject) -> list[JsonObject]:
    by_id = {entry["requirement_id"]: dict(entry) for entry in ordered_requirement_entries(existing)}
    for update in _requirement_status_updates(checkpoint_result):
        requirement_id = update["requirement_id"]
        if requirement_id not in by_id:
            by_id[requirement_id] = {"requirement_id": requirement_id, "impact_rank": 0.0, "status": update["status"]}
        else:
            by_id[requirement_id]["status"] = update["status"]
    return sorted(by_id.values(), key=_requirement_entry_sort_key)


def _requirement_status_updates(checkpoint_result: JsonObject) -> list[JsonObject]:
    updates: list[JsonObject] = []
    for key in ("requirement_statuses", "resolution_updates", "open_requirements"):
        values = checkpoint_result.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            requirement_id = item.get("requirement_id")
            status = _loop_requirement_status(item.get("status") or item.get("resolution_state"))
            if isinstance(requirement_id, str) and requirement_id and status != "open":
                updates.append({"requirement_id": requirement_id, "status": status})
    for status, key in (("resolved", "resolved_requirements"), ("user_declined", "user_declined_requirements"), ("exhausted", "exhausted_requirements")):
        values = checkpoint_result.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            requirement_id = item.get("requirement_id") if isinstance(item, dict) else item
            if isinstance(requirement_id, str) and requirement_id:
                updates.append({"requirement_id": requirement_id, "status": status})
    return updates


def _asked_question_entries(records: list[JsonObject]) -> list[JsonObject]:
    entries: list[JsonObject] = []
    for record in records:
        question_id = _first_string(record, ("question_id", "question_ref", "question_answer_ref"))
        requirement_id = _first_string(record, ("requirement_id", "selected_requirement_id"))
        interaction_ref = _first_string(
            record,
            (
                "interaction_ref",
                "career_store_interaction_ref",
                "career_store_interaction_id",
                "question_answer_ref",
                "answer_ref",
                "question_ref",
            ),
        )
        if question_id and requirement_id and interaction_ref:
            entries.append({"question_id": question_id, "requirement_id": requirement_id, "interaction_ref": interaction_ref})
    return entries


def _last_recorded_match_result(run_state: JsonObject) -> JsonObject:
    checkpoint_result = _read_recorded_checkpoint_result(run_state, "MATCH_BASE")
    return _match_result_from_checkpoint_payload(checkpoint_result)


def _read_recorded_checkpoint_result(run_state: JsonObject, checkpoint: str) -> JsonObject:
    workspace = run_state.get("workspace")
    run_id = run_state.get("run_id")
    if not workspace or not run_id:
        return {}
    path = Path(str(workspace)) / ".workflow" / "runs" / str(run_id) / "checkpoints" / f"{checkpoint}.json"
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _match_result_from_checkpoint_payload(payload: JsonObject) -> JsonObject:
    match = payload.get("match_result") if isinstance(payload, dict) else None
    if isinstance(match, dict) and isinstance(match.get("match_result"), dict):
        return dict(match["match_result"])
    return dict(match) if isinstance(match, dict) else {}


def _match_decision(match_result: JsonObject) -> str:
    decision = match_result.get("decision")
    return str(decision) if decision in {"continue", "resolve_gaps", "blocked"} else "continue"


def _match_unresolved_ids(match_result: JsonObject) -> set[str]:
    ids: set[str] = set()
    for key in ("unresolved_requirement_ids", "preferred_unresolved_requirement_ids"):
        values = match_result.get(key)
        if isinstance(values, list):
            ids.update(str(value) for value in values if str(value))
    results = match_result.get("requirement_results", [])
    for result in results if isinstance(results, list) else []:
        if isinstance(result, dict) and result.get("unresolved") is True and result.get("requirement_id"):
            ids.add(str(result["requirement_id"]))
    return ids


def _next_open_requirement(loop_state: JsonObject, run_state: JsonObject | None = None) -> JsonObject | None:
    already_asked = _already_asked_requirement_ids(loop_state, run_state)
    for entry in ordered_requirement_entries(loop_state.get("open_requirements", [])):
        if entry["status"] == "open" and entry["requirement_id"] not in already_asked:
            return dict(entry)
    return None


def _already_asked_requirement_ids(loop_state: JsonObject, run_state: JsonObject | None) -> set[str]:
    if run_state is None:
        return set()
    recovery_refs = {str(value) for value in run_state.get("already_asked_questions", []) if str(value)}
    if not recovery_refs:
        return set()
    requirement_ids: set[str] = set()
    for record in loop_state.get("asked_questions", []):
        if not isinstance(record, dict):
            continue
        refs = {
            str(record.get("question_id", "")),
            str(record.get("interaction_ref", "")),
            str(record.get("requirement_id", "")),
        }
        if refs & recovery_refs and isinstance(record.get("requirement_id"), str):
            requirement_ids.add(str(record["requirement_id"]))
    return requirement_ids


def _loop_unresolved_requirements(loop_state: JsonObject) -> list[JsonObject]:
    return [
        dict(entry)
        for entry in ordered_requirement_entries(loop_state.get("open_requirements", []))
        if entry["status"] != "resolved"
    ]


def _match_blocking_reasons(match_result: JsonObject) -> list[str]:
    reasons: list[str] = []
    for requirement_id in sorted(_match_unresolved_ids(match_result)):
        reasons.append(f"unresolved_hard_requirement:{requirement_id}")
    explanations = match_result.get("explanations")
    if isinstance(explanations, list):
        reasons.extend(str(item) for item in explanations if isinstance(item, str) and item)
    return _dedupe(reasons)


def _loop_requirement_status(value: Any) -> str:
    text = str(value or "open")
    return text if text in {"open", "resolved", "user_declined", "exhausted"} else "open"


def _requirement_entry_sort_key(entry: JsonObject) -> tuple[float, str]:
    return (-float(entry.get("impact_rank", 0.0)), str(entry.get("requirement_id", "")))


def _impact_rank_value(item: JsonObject) -> float:
    for key in ("impact_rank", "impact", "max_score", "weight", "score"):
        value = item.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return 0.0


def _first_string(record: JsonObject, keys: tuple[str, ...]) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _fact_id_set(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {str(value) for value in values}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _stable_hash(value: Any) -> str:
    payload = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value
