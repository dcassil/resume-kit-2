"""Render-overflow loop state and constraint artifact helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .config import DEFAULT_MAX_RENDER_OVERFLOW_ITERATIONS


JsonObject = dict[str, Any]


def empty_render_overflow_state() -> JsonObject:
    return {
        "status": "clear",
        "iteration_count": 0,
        "last_constraints": {},
        "constraint_ref": None,
        "blocking_reasons": [],
    }


def normalize_render_overflow_state(value: Any, run_state: JsonObject | None = None) -> JsonObject:
    raw = value if isinstance(value, dict) else {}
    normalized = empty_render_overflow_state()
    status = raw.get("status")
    normalized["status"] = str(status) if status in {"clear", "pending", "consumed", "blocked", "fits"} else "clear"
    iteration = raw.get("iteration_count", raw.get("overflow_iteration", 0))
    normalized["iteration_count"] = int(iteration) if isinstance(iteration, int) and not isinstance(iteration, bool) and iteration >= 0 else 0
    constraints = raw.get("last_constraints")
    if isinstance(constraints, dict):
        normalized["last_constraints"] = _normalize_overflow_constraints(constraints)
    constraint_ref = raw.get("constraint_ref")
    normalized["constraint_ref"] = dict(constraint_ref) if isinstance(constraint_ref, dict) else None
    normalized["blocking_reasons"] = _dedupe([str(reason) for reason in raw.get("blocking_reasons", []) if str(reason)])
    if run_state is not None and isinstance(run_state.get("overflow_iteration"), int):
        normalized["iteration_count"] = max(normalized["iteration_count"], int(run_state["overflow_iteration"]))
    return normalized


def render_overflow_decision(run_state: JsonObject) -> JsonObject:
    state = normalize_render_overflow_state(run_state.get("render_overflow_state", {}), run_state)
    if state["status"] == "blocked":
        predicate = {
            "branch": "render_overflow_bound_exhausted",
            "action": "blocked",
            "blocking_reasons": state["blocking_reasons"] or ["render_overflow_bound_exhausted"],
        }
    elif state["status"] == "pending":
        predicate = {
            "branch": "render_overflow_loop_back",
            "action": "loop_back",
            "blocking_reasons": [],
            "overflow_constraints": dict(state["last_constraints"]),
        }
    else:
        predicate = {"branch": "not_applicable", "action": "advance", "blocking_reasons": []}
    return {"state": state, "predicate": predicate}


def record_render_overflow_result(run_state: JsonObject, checkpoint: str, checkpoint_result: JsonObject) -> JsonObject:
    if checkpoint != "RENDER":
        return {"status": "not_applicable"}
    constraints = _overflow_constraints_from_render_result(checkpoint_result)
    if not constraints:
        if str(checkpoint_result.get("status", "")).lower() in {"fits", "ok", "pass", "passed"}:
            state = normalize_render_overflow_state(run_state.get("render_overflow_state", {}), run_state)
            state["status"] = "fits"
            state["last_constraints"] = {}
            state["constraint_ref"] = None
            state["blocking_reasons"] = []
            run_state["render_overflow_state"] = state
            run_state["render_overflow_blocking_reasons"] = []
            return {"status": "fits", "state": state}
        return {"status": "not_applicable"}

    state = normalize_render_overflow_state(run_state.get("render_overflow_state", {}), run_state)
    iteration = int(state.get("iteration_count", 0)) + 1
    max_iterations = max_render_overflow_iterations(run_state)
    constraint_ref = _write_render_overflow_constraint(run_state, iteration, constraints)
    state.update(
        {
            "status": "pending",
            "iteration_count": iteration,
            "last_constraints": constraints,
            "constraint_ref": constraint_ref,
            "blocking_reasons": [],
        }
    )
    run_state["overflow_iteration"] = iteration
    if iteration > max_iterations:
        reasons = [
            "render_overflow_bound_exhausted",
            f"workflow.maxRenderOverflowIterations:{max_iterations}",
            f"requiredReduction:{constraints['requiredReduction']}",
        ]
        state["status"] = "blocked"
        state["blocking_reasons"] = reasons
        run_state["render_overflow_blocking_reasons"] = reasons
    else:
        run_state["render_overflow_blocking_reasons"] = []
    run_state["render_overflow_state"] = state
    return {
        "status": state["status"],
        "iteration": iteration,
        "max_iterations": max_iterations,
        "constraints": constraints,
        "constraint_ref": constraint_ref,
        "blocking_reasons": list(state.get("blocking_reasons", [])),
    }


def mark_render_overflow_consumed(run_state: JsonObject) -> None:
    state = normalize_render_overflow_state(run_state.get("render_overflow_state", {}), run_state)
    if state["status"] == "pending":
        state["status"] = "consumed"
        state["blocking_reasons"] = []
        run_state["render_overflow_state"] = state
        run_state["render_overflow_blocking_reasons"] = []


def max_render_overflow_iterations(run_state: JsonObject) -> int:
    workflow_config = run_state.get("workflow_config")
    if isinstance(workflow_config, dict):
        value = workflow_config.get("maxRenderOverflowIterations")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return int(value)
    return DEFAULT_MAX_RENDER_OVERFLOW_ITERATIONS


def render_overflow_completion_gate_passed(run_state: JsonObject) -> bool:
    state = normalize_render_overflow_state(run_state.get("render_overflow_state", {}), run_state)
    return state["status"] not in {"pending", "blocked"}


def render_overflow_completion_reason(run_state: JsonObject) -> str:
    state = normalize_render_overflow_state(run_state.get("render_overflow_state", {}), run_state)
    reasons = state.get("blocking_reasons", [])
    return ",".join(reasons) if reasons else f"render_overflow_{state['status']}"


def _overflow_constraints_from_render_result(result: JsonObject) -> JsonObject | None:
    if str(result.get("status", "")).lower() != "overflow":
        return None
    source = result.get("overflow_constraints")
    if not isinstance(source, dict):
        source = result.get("constraints") if isinstance(result.get("constraints"), dict) else result
    constraints = _normalize_overflow_constraints(source)
    return constraints if constraints.get("requiredReduction", 0) > 0 else None


def _normalize_overflow_constraints(value: Any) -> JsonObject:
    raw = value if isinstance(value, dict) else {}
    required = raw.get("requiredReduction")
    if required is None:
        required = raw.get("required_reduction")
    required_reduction = int(required) if isinstance(required, int) and not isinstance(required, bool) and required > 0 else 0
    offending = raw.get("offending_sections", raw.get("offendingSections", []))
    offending_sections = _dedupe([str(section) for section in offending if str(section)]) if isinstance(offending, list) else []
    return {
        "requiredReduction": required_reduction,
        "offending_sections": offending_sections,
    }


def _write_render_overflow_constraint(run_state: JsonObject, iteration: int, constraints: JsonObject) -> JsonObject:
    workspace = run_state.get("workspace")
    run_id = run_state.get("run_id")
    if not workspace or not run_id:
        raise ValueError("Render overflow constraint recording requires a run_state with workspace and run_id.")
    workspace_path = Path(str(workspace))
    path = workspace_path / ".workflow" / "runs" / str(run_id) / "checkpoints" / f"RENDER-overflow-{iteration:04d}.json"
    payload = {
        "status": "overflow",
        "checkpoint": "RENDER",
        "overflow_iteration": iteration,
        "constraints": dict(constraints),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(payload), sort_keys=True, indent=2), encoding="utf-8")
    return {
        "kind": "artifact",
        "path": str(path.relative_to(workspace_path)),
        "sha256": _file_sha256(path),
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result
