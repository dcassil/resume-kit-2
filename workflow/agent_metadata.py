"""Private workflow helpers for agent manifest metadata and call-audit refs."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path


JsonObject = dict[str, object]
AGENT_CALL_AUDIT_LOG = "agent-call-audit.jsonl"


class WorkflowCallAuditSink:
    def __init__(self, run_state: JsonObject) -> None:
        self._run_state = run_state

    def record(self, record: JsonObject) -> None:
        validated = dict(record)
        ref = _append_jsonl_record(self._run_state, AGENT_CALL_AUDIT_LOG, validated)
        refs = [str(value) for value in self._run_state.get("audit_refs", [])]
        if ref not in refs:
            refs.append(ref)
        self._run_state["audit_refs"] = refs
        _persist_run_state(self._run_state)


def call_audit_sink_for_run(run_state: JsonObject) -> WorkflowCallAuditSink:
    return WorkflowCallAuditSink(run_state)


def read_call_audit_records(workspace: str | Path, refs: list[str]) -> list[JsonObject]:
    records: list[JsonObject] = []
    for ref in refs:
        path_text, line_number = _split_line_ref(ref)
        path = Path(workspace) / path_text
        lines = path.read_text(encoding="utf-8").splitlines()
        records.append(json.loads(lines[line_number - 1]))
    return records


def _append_jsonl_record(run_state: JsonObject, filename: str, record: JsonObject) -> str:
    path = _run_dir(run_state) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    line_number = _jsonl_line_count(path) + 1
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return f".workflow/runs/{run_state['run_id']}/{filename}#L{line_number}"


def _run_dir(run_state: JsonObject) -> Path:
    workspace = run_state.get("workspace")
    run_id = run_state.get("run_id")
    if not workspace or not run_id:
        raise ValueError("Workflow call-audit recording requires workspace and run_id.")
    return Path(str(workspace)) / ".workflow" / "runs" / str(run_id)


def _jsonl_line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _persist_run_state(run_state: JsonObject) -> None:
    path = _run_dir(run_state).with_suffix(".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(run_state), sort_keys=True, indent=2), encoding="utf-8")


def _split_line_ref(ref: str) -> tuple[str, int]:
    path_text, marker, line_text = ref.partition("#L")
    if not marker or not path_text or not line_text.isdigit():
        raise ValueError(f"Invalid agent call-audit ref: {ref}")
    return path_text, int(line_text)


def _jsonable(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return copy.deepcopy(value)


__all__ = ["AGENT_CALL_AUDIT_LOG", "WorkflowCallAuditSink", "call_audit_sink_for_run", "read_call_audit_records"]
