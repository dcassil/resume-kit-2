"""Opt-in live eval harness and capture/promote tooling for resume-agent proposal outputs.

This script is intentionally excluded from official gates. It runs only when
all three environment gates are present:

- RESUME_AGENT_LIVE_SMOKE=1
- RESUME_AGENT_ALLOW_LIVE=1
- ANTHROPIC_API_KEY
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = ROOT / "resume-agent"
FIXTURES_ROOT = ROOT / "fixtures" / "resume-agent"
DEFAULT_EVAL_FIXTURE_DIR = FIXTURES_ROOT / "eval"
DEFAULT_QUARANTINE_DIR = FIXTURES_ROOT / "quarantine"
DEFAULT_FAKE_FIXTURE_DIR = FIXTURES_ROOT / "fake-adapter"
DEFAULT_REPORT_PATH = ROOT / "build" / "resume-agent" / "eval-report.json"
CAPTURE_CANDIDATE_SCHEMA_VERSION = "resume-agent.quarantine-candidate.v1"
EVAL_REPORT_SCHEMA_VERSION = "resume-agent.eval-report.v1"
SUPPORTED_RUBRIC_CHECKS = {
    "forbidden_terms_absent",
    "grounding_terms",
    "json_pointer_equals",
    "required_terms",
    "schema_fields_populated",
}


class EvalHarnessBlockedError(RuntimeError):
    """Raised when live eval/capture is blocked before adapter construction."""


class EvalFixtureError(ValueError):
    """Raised when an eval or quarantine fixture is malformed."""


class CollectingCallAuditSink:
    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def record(self, record: dict[str, Any]) -> None:
        self._records.append(copy.deepcopy(record))

    @property
    def records(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._records)


class CapturingLiveAdapter:
    def __init__(self, delegate: Any, *, project_root: Path | str = ROOT) -> None:
        self._delegate = delegate
        self._project_root = Path(project_root)

    def complete(self, request: Any) -> Any:
        result = self._delegate.complete(request)
        if getattr(result, "status", None) == "ok" and getattr(result, "payload", None) is not None:
            write_quarantine_candidate(request, result, project_root=self._project_root)
        return result


def require_live_eval_allowed(env: Mapping[str, str] | None = None) -> None:
    environment = env or os.environ
    if environment.get("RESUME_AGENT_GATE_PROFILE") == "1":
        raise EvalHarnessBlockedError(
            "live eval blocked: RESUME_AGENT_GATE_PROFILE=1 prevents live adapter construction."
        )
    if environment.get("RESUME_AGENT_LIVE_SMOKE") != "1":
        raise EvalHarnessBlockedError("live eval skipped: set RESUME_AGENT_LIVE_SMOKE=1 to opt in.")
    missing = [
        name
        for name in ("RESUME_AGENT_ALLOW_LIVE", "ANTHROPIC_API_KEY")
        if not environment.get(name)
    ]
    if missing:
        raise EvalHarnessBlockedError(f"live eval not run: missing {', '.join(missing)}.")


def create_capturing_live_adapter(
    *,
    env: Mapping[str, str] | None = None,
    adapter_factory: Callable[..., Any] | None = None,
    output_schemas: Mapping[str, Any] | None = None,
    call_audit_sink: Any | None = None,
    project_root: Path | str = ROOT,
) -> CapturingLiveAdapter:
    require_live_eval_allowed(env)
    factory = adapter_factory or _default_live_adapter_factory()
    delegate = factory(env=env, output_schemas=output_schemas, call_audit_sink=call_audit_sink)
    return CapturingLiveAdapter(delegate, project_root=project_root)


def run_eval(
    *,
    fixtures_dir: Path | str = DEFAULT_EVAL_FIXTURE_DIR,
    report_path: Path | str = DEFAULT_REPORT_PATH,
    env: Mapping[str, str] | None = None,
    adapter_factory: Callable[..., Any] | None = None,
    capture: bool = False,
    project_root: Path | str = ROOT,
) -> dict[str, Any]:
    require_live_eval_allowed(env)
    _ensure_package_path()
    from resume_agent._fake_adapter import DEFAULT_FAKE_OUTPUT_SCHEMAS

    sink = CollectingCallAuditSink()
    output_schemas = dict(DEFAULT_FAKE_OUTPUT_SCHEMAS)
    if capture:
        adapter = create_capturing_live_adapter(
            env=env,
            adapter_factory=adapter_factory,
            output_schemas=output_schemas,
            call_audit_sink=sink,
            project_root=project_root,
        )
    else:
        factory = adapter_factory or _default_live_adapter_factory()
        adapter = factory(env=env, output_schemas=output_schemas, call_audit_sink=sink)

    fixtures = load_eval_fixtures(fixtures_dir)
    results: list[dict[str, Any]] = []
    for fixture in fixtures:
        start = len(sink.records)
        request = adapter_request_from_fixture(fixture)
        adapter_result = adapter.complete(request)
        records = sink.records[start:]
        score = score_fixture(fixture, getattr(adapter_result, "payload", None))
        results.append(
            {
                "fixture_id": fixture["fixture_id"],
                "surface": fixture["surface"],
                "status": getattr(adapter_result, "status", "error"),
                "score": score,
                "call_audit_record_ids": [record["call_id"] for record in records],
                "adapter_result": _adapter_result_dict(adapter_result),
            }
        )

    report_file = Path(report_path)
    audit_refs = _write_call_audit_records(sink.records, report_file)
    by_id = {item["call_id"]: item["path"] for item in audit_refs}
    for result in results:
        result["call_audit_records"] = [
            {"call_id": call_id, "path": by_id.get(call_id)}
            for call_id in result.pop("call_audit_record_ids")
        ]
    report = {
        "schema_version": EVAL_REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "fixtures_dir": str(Path(fixtures_dir)),
        "capture": capture,
        "summary": _summary(results),
        "results": results,
        "call_audit_records": audit_refs,
    }
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def load_eval_fixtures(fixtures_dir: Path | str = DEFAULT_EVAL_FIXTURE_DIR) -> list[dict[str, Any]]:
    base = Path(fixtures_dir)
    fixtures: list[dict[str, Any]] = []
    for path in sorted(base.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else [data]
        for item in items:
            fixtures.append(_require_eval_fixture(item, path))
    return fixtures


def adapter_request_from_fixture(fixture: Mapping[str, Any]) -> Any:
    _ensure_package_path()
    from resume_agent._adapters import AdapterRequest

    prompt_template_id = _require_string(fixture, "prompt_template_id")
    return AdapterRequest(
        prompt_template_id=prompt_template_id,
        prompt=_prompt_template_text(prompt_template_id),
        input_payload=copy.deepcopy(fixture["input"]),
        output_schema_id=_require_string(fixture, "output_schema_id"),
    )


def score_fixture(fixture: Mapping[str, Any], payload: Any) -> dict[str, Any]:
    criteria = fixture.get("rubric", [])
    scored: list[dict[str, Any]] = []
    earned = 0
    possible = 0
    for criterion in criteria:
        points = int(criterion.get("points", 1))
        possible += points
        passed, details = _score_criterion(criterion, payload)
        if passed:
            earned += points
        scored.append(
            {
                "id": criterion["id"],
                "check": criterion["check"],
                "points": points,
                "earned": points if passed else 0,
                "passed": passed,
                "details": details,
            }
        )
    return {"earned": earned, "possible": possible, "criteria": scored}


def write_quarantine_candidate(request: Any, result: Any, *, project_root: Path | str = ROOT) -> Path:
    _ensure_package_path()
    from resume_agent._fake_adapter import canonical_input_json, deterministic_fake_key

    root = Path(project_root)
    quarantine_dir = root / "fixtures" / "resume-agent" / "quarantine"
    key = deterministic_fake_key(request.prompt_template_id, request.output_schema_id, request.input_payload)
    path = quarantine_dir / f"{key}.json"
    _assert_child_path(path, quarantine_dir)
    candidate = {
        "candidate_schema_version": CAPTURE_CANDIDATE_SCHEMA_VERSION,
        "fixture_id": f"resume-agent-quarantine-{key}",
        "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "reviewed": False,
        "expected_observations": [
            "Candidate captured from a live adapter run; review before promotion to fake-adapter fixtures."
        ],
        "data": {
            "key": {
                "sha256": key,
                "prompt_template_id": request.prompt_template_id,
                "output_schema_id": request.output_schema_id,
                "canonical_input_json": canonical_input_json(request.input_payload),
            },
            "payload": copy.deepcopy(result.payload),
        },
        "adapter_result": _adapter_result_dict(result),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def promote_fixture(key: str, *, project_root: Path | str = ROOT, replace: bool = False) -> Path:
    _ensure_package_path()
    from resume_agent._fake_adapter import FAKE_CONFIG_HASH, FAKE_FIXTURE_SCHEMA_VERSION

    if not key or "/" in key or "\\" in key:
        raise EvalFixtureError("promote requires a bare fixture key.")
    root = Path(project_root)
    quarantine_path = root / "fixtures" / "resume-agent" / "quarantine" / f"{key}.json"
    target_path = root / "fixtures" / "resume-agent" / "fake-adapter" / f"{key}.json"
    _assert_child_path(quarantine_path, root / "fixtures" / "resume-agent" / "quarantine")
    _assert_child_path(target_path, root / "fixtures" / "resume-agent" / "fake-adapter")
    if not quarantine_path.exists():
        raise FileNotFoundError(f"Missing quarantine candidate for key {key}: {quarantine_path}")
    if target_path.exists() and not replace:
        raise FileExistsError(f"Refusing to overwrite existing pinned fake fixture without --replace: {target_path}")
    candidate = json.loads(quarantine_path.read_text(encoding="utf-8"))
    data = candidate.get("data")
    if not isinstance(data, dict):
        raise EvalFixtureError("quarantine candidate requires data object.")
    key_data = data.get("key")
    payload = data.get("payload")
    if not isinstance(key_data, dict) or not isinstance(payload, dict):
        raise EvalFixtureError("quarantine candidate requires data.key and data.payload objects.")
    if key_data.get("sha256") != key:
        raise EvalFixtureError(f"quarantine candidate key mismatch: expected {key}, observed {key_data.get('sha256')}")
    fixture = {
        "fixture_id": f"resume-agent-promoted-{key}",
        "schema_version": FAKE_FIXTURE_SCHEMA_VERSION,
        "config_hash": FAKE_CONFIG_HASH,
        "reviewed": True,
        "expected_observations": candidate.get("expected_observations")
        or ["Promoted from a reviewed live-adapter quarantine candidate."],
        "comment": f"Promoted from fixtures/resume-agent/quarantine/{key}.json.",
        "data": {"key": copy.deepcopy(key_data), "payload": copy.deepcopy(payload)},
    }
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target_path


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.command == "promote":
        try:
            promoted = promote_fixture(args.key, project_root=args.root, replace=args.replace)
        except Exception as exc:  # noqa: BLE001 - CLI should print concise operational errors.
            print(str(exc), file=sys.stderr)
            return 2
        print(f"promoted quarantine fixture: {promoted}")
        return 0

    if os.environ.get("RESUME_AGENT_GATE_PROFILE") == "1":
        print("live eval blocked: RESUME_AGENT_GATE_PROFILE=1 prevents live adapter construction.", file=sys.stderr)
        return 2
    if os.environ.get("RESUME_AGENT_LIVE_SMOKE") != "1":
        print("live eval skipped: set RESUME_AGENT_LIVE_SMOKE=1 to opt in.")
        return 0
    missing = [
        name
        for name in ("RESUME_AGENT_ALLOW_LIVE", "ANTHROPIC_API_KEY")
        if not os.environ.get(name)
    ]
    if missing:
        print(f"live eval not run: missing {', '.join(missing)}.", file=sys.stderr)
        return 2

    try:
        report = run_eval(
            fixtures_dir=args.fixtures_dir,
            report_path=args.report,
            capture=args.command == "capture",
            project_root=args.root,
        )
    except Exception as exc:  # noqa: BLE001 - eval is opt-in and should return a report/setup error, not traceback by default.
        print(str(exc), file=sys.stderr)
        return 2
    print(f"eval report written: {args.report}")
    print(f"score: {report['summary']['earned_points']}/{report['summary']['possible_points']}")
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run opt-in live resume-agent evals or promote captured fixtures.")
    parser.add_argument("--root", type=Path, default=ROOT)
    subparsers = parser.add_subparsers(dest="command")
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--fixtures-dir", type=Path, default=DEFAULT_EVAL_FIXTURE_DIR)
    run_parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    capture_parser = subparsers.add_parser("capture")
    capture_parser.add_argument("--fixtures-dir", type=Path, default=DEFAULT_EVAL_FIXTURE_DIR)
    capture_parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    promote_parser = subparsers.add_parser("promote")
    promote_parser.add_argument("key")
    promote_parser.add_argument("--replace", action="store_true")
    args = parser.parse_args(argv)
    if args.command is None:
        args.command = "run"
        args.fixtures_dir = DEFAULT_EVAL_FIXTURE_DIR
        args.report = DEFAULT_REPORT_PATH
    return args


def _require_eval_fixture(candidate: Any, path: Path) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        raise EvalFixtureError(f"Eval fixture must be an object: {path}")
    required = ["fixture_id", "surface", "prompt_template_id", "output_schema_id", "input", "rubric"]
    missing = [field for field in required if field not in candidate]
    if missing:
        raise EvalFixtureError(f"Eval fixture {path} missing fields: {missing}")
    if not isinstance(candidate["input"], dict):
        raise EvalFixtureError(f"Eval fixture input must be an object: {path}")
    if not isinstance(candidate["rubric"], list) or not candidate["rubric"]:
        raise EvalFixtureError(f"Eval fixture rubric must be a non-empty list: {path}")
    for criterion in candidate["rubric"]:
        _require_rubric_criterion(criterion, path)
    return copy.deepcopy(candidate)


def _require_rubric_criterion(criterion: Any, path: Path) -> None:
    if not isinstance(criterion, dict):
        raise EvalFixtureError(f"Rubric criterion must be an object: {path}")
    required = ["id", "check", "points"]
    missing = [field for field in required if field not in criterion]
    if missing:
        raise EvalFixtureError(f"Rubric criterion missing fields {missing}: {path}")
    if criterion["check"] not in SUPPORTED_RUBRIC_CHECKS:
        raise EvalFixtureError(f"Unsupported rubric check {criterion['check']}: {path}")
    if not isinstance(criterion["points"], int) or criterion["points"] <= 0:
        raise EvalFixtureError(f"Rubric criterion points must be a positive integer: {path}")


def _score_criterion(criterion: Mapping[str, Any], payload: Any) -> tuple[bool, dict[str, Any]]:
    if not isinstance(payload, dict):
        return False, {"reason": "missing_payload"}
    check = criterion["check"]
    if check == "schema_fields_populated":
        paths = list(criterion.get("paths", []))
        missing = [path for path in paths if not _is_populated(_json_pointer(payload, path))]
        return not missing, {"missing_paths": missing}
    if check == "required_terms":
        terms = list(criterion.get("terms", []))
        text = json.dumps(payload, sort_keys=True, ensure_ascii=False).lower()
        missing = [term for term in terms if str(term).lower() not in text]
        return not missing, {"missing_terms": missing}
    if check == "forbidden_terms_absent":
        terms = list(criterion.get("terms", []))
        text = json.dumps(payload, sort_keys=True, ensure_ascii=False).lower()
        present = [term for term in terms if str(term).lower() in text]
        return not present, {"present_terms": present}
    if check == "json_pointer_equals":
        observed = _json_pointer(payload, str(criterion.get("path", "")))
        expected = criterion.get("expected")
        return observed == expected, {"expected": expected, "observed": observed}
    if check == "grounding_terms":
        expected_entries = criterion.get("entries", [])
        observed = {
            (entry.get("term"), entry.get("fact_id"))
            for operation in payload.get("operations", [])
            if isinstance(operation, dict)
            for entry in operation.get("grounding", [])
            if isinstance(entry, dict)
        }
        missing = [
            entry
            for entry in expected_entries
            if (entry.get("term"), entry.get("fact_id")) not in observed
        ]
        return not missing, {"missing_grounding": missing}
    return False, {"reason": f"unsupported_check:{check}"}


def _json_pointer(value: Any, pointer: str) -> Any:
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        return None
    current = value
    for raw_token in pointer.strip("/").split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current.get(token)
        elif isinstance(current, list) and token.isdigit():
            index = int(token)
            current = current[index] if 0 <= index < len(current) else None
        else:
            return None
    return current


def _is_populated(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return bool(value)
    return True


def _summary(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    possible = sum(result["score"]["possible"] for result in results)
    earned = sum(result["score"]["earned"] for result in results)
    return {
        "fixtures": len(results),
        "adapter_ok": sum(1 for result in results if result["status"] == "ok"),
        "earned_points": earned,
        "possible_points": possible,
    }


def _write_call_audit_records(records: Sequence[Mapping[str, Any]], report_path: Path) -> list[dict[str, str]]:
    audit_dir = report_path.parent / "call-audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    refs: list[dict[str, str]] = []
    for record in records:
        call_id = str(record["call_id"])
        path = audit_dir / f"{call_id}.json"
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        refs.append({"call_id": call_id, "path": str(path)})
    return refs


def _adapter_result_dict(result: Any) -> dict[str, Any]:
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return {"status": getattr(result, "status", "unknown")}


def _default_live_adapter_factory() -> Callable[..., Any]:
    _ensure_package_path()
    from resume_agent._adapters import create_live_model_adapter

    return create_live_model_adapter


def _prompt_template_text(prompt_template_id: str) -> str:
    _ensure_package_path()
    from importlib import resources

    try:
        return resources.files("resume_agent").joinpath("prompts", f"{prompt_template_id}.txt").read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _ensure_package_path() -> None:
    if str(PACKAGE_ROOT) not in sys.path:
        sys.path.insert(0, str(PACKAGE_ROOT))


def _assert_child_path(path: Path, parent: Path) -> None:
    path.resolve().relative_to(parent.resolve())


def _require_string(mapping: Mapping[str, Any], field: str) -> str:
    value = mapping.get(field)
    if not isinstance(value, str) or not value:
        raise EvalFixtureError(f"{field} must be a non-empty string.")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
