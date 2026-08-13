#!/usr/bin/env python3
"""Hard-blocking guardrails for the workflow state-machine boundary."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from architecture_lint import scan_python_architecture


ALLOWED_SURFACES = {
    "createRun",
    "getNextCheckpoint",
    "advanceCheckpoint",
    "recordCheckpointResult",
    "buildRunManifest",
    "recoverRun",
    "assertCanComplete",
}

REQUIRED_CHECKPOINTS = [
    "INIT",
    "INGEST_RESUME",
    "VALIDATE_BASE",
    "EXTRACT_PERSIST_CAREER_FACTS",
    "INGEST_JOB",
    "NORMALIZE_JOB",
    "MATCH_BASE",
    "RESOLVE_GAPS",
    "BUILD_SELECTION_PLAN",
    "PROPOSE_TAILORING_CHANGES",
    "VALIDATE_CHANGES",
    "APPLY_CHANGES",
    "FINAL_MATCH",
    "GROUNDING_AUDIT",
    "ATS_STRUCTURE_VALIDATION",
    "RENDER",
    "RENDER_VALIDATION",
    "COMPLETE",
]

REQUIRED_MANIFEST_FIELDS = {
    "run_id",
    "base_resume_id",
    "base_resume_hash",
    "job_id",
    "config_hash",
    "canonical_resume_schema_version",
    "job_schema_version",
    "career_db_schema_version",
    "change_operation_schema_version",
    "matching_algorithm_version",
    "matching_config_version",
    "renderer_template_version",
    "agent_model_config",
    "initial_score",
    "final_score",
    "facts_added",
    "facts_verified",
    "operations_applied",
    "operations_rejected",
    "validation_status",
    "output_artifact_paths",
}

FORBIDDEN_IMPORTS = {
    "sqlite3": "workflow must not write career DB tables directly. Route persistence through career-store/CLI public APIs.",
    "aiosqlite": "workflow must not write career DB tables directly. Route persistence through career-store/CLI public APIs.",
    "sqlalchemy": "workflow must not own database sessions, schemas, migrations, or table models.",
}

PRIVATE_IMPORT_PATTERNS = [
    r"\bfrom\s+(resume_core|career_store|career_mcp|resume_agent|resume_render|resume_cli|resume_plugin)\.(?:_internal|internal|private|migrations|schema|schemas|tables|adapters)\b",
    r"\bimport\s+(resume_core|career_store|career_mcp|resume_agent|resume_render|resume_cli|resume_plugin)\.(?:_internal|internal|private|migrations|schema|schemas|tables|adapters)\b",
]

FORBIDDEN_TERMS = {
    "calculate_score": "Workflow may record official scores, not compute an alternate scoring rule.",
    "compute_score": "Workflow may record official scores, not compute an alternate scoring rule.",
    "scoring_weights": "Scoring weights belong to resume-core/config, not workflow code.",
    "requirement_weight": "Requirement weighting belongs to resume-core.",
    "validate_resume_schema": "Schema validation belongs to resume-core. Workflow records validation outcomes.",
    "validate_job_schema": "Schema validation belongs to resume-core. Workflow records validation outcomes.",
    "apply_resume_change": "Resume mutation application belongs to resume-core. Workflow records validated operation state.",
    "apply_change_operation": "Resume mutation application belongs to resume-core. Workflow records validated operation state.",
    "rewrite_bullet": "Semantic rewrite belongs to agent proposal plus core validation, not workflow.",
    "truncate_to_fit": "Render overflow returns constraints; workflow must not silently truncate content.",
    "agent_says_ok": "No checkpoint may be skipped because an agent output appears plausible.",
    "looks_correct": "No checkpoint may be skipped because output looks plausible.",
    "skip_checkpoint": "Workflow must not skip required checkpoints.",
    "bypass_checkpoint": "Workflow must not bypass required checkpoints.",
}

DIRECT_DB_PATTERNS = [
    r"\b(insert|update|delete|drop|alter|create)\s+[^;\n]*(career_|facts|evidence|relationships|verification|data/career\.db)\b",
    r"\bexecute(?:many)?\s*\(\s*['\"]\s*(insert|update|delete|drop|alter|create)\b",
    r"\bconnect\s*\(\s*['\"][^'\"]*career\.db['\"]",
]

CODE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
IGNORED_DIRS = {"__pycache__", ".pytest_cache", "node_modules", ".venv", "venv", "dist", "build"}


@dataclass(frozen=True)
class Failure:
    path: Path
    message: str
    solution: str
    line: int | None = None

    def format(self, root: Path) -> str:
        rel = self.path.relative_to(root) if self.path.is_relative_to(root) else self.path
        where = f"{rel}:{self.line}" if self.line else str(rel)
        return f"- {where}\n  Why it failed: {self.message}\n  Possible solution: {self.solution}"


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def load_surface(root: Path) -> tuple[dict, list[Failure]]:
    path = root / "workflow" / "workflow_surface.json"
    if not path.exists():
        return {}, [
            Failure(
                path,
                "Missing machine-readable workflow surface contract.",
                "Restore workflow/workflow_surface.json and update it before changing state-machine behavior.",
            )
        ]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return {}, [
            Failure(
                path,
                f"Invalid JSON: {exc.msg}.",
                "Fix the JSON so contract tests and guardrails can compare the declared workflow surface to implementation.",
                exc.lineno,
            )
        ]


def validate_surface(root: Path, surface: dict) -> list[Failure]:
    path = root / "workflow" / "workflow_surface.json"
    failures: list[Failure] = []
    functions = set(surface.get("public_api", {}).get("functions", []))
    if functions != ALLOWED_SURFACES:
        failures.append(
            Failure(
                path,
                f"Declared public functions differ from workflow/TEST_SPEC.md. Missing={sorted(ALLOWED_SURFACES - functions)}; extra={sorted(functions - ALLOWED_SURFACES)}.",
                "Expose only the workflow state-machine, manifest, audit, recovery, and completion gate surfaces.",
            )
        )

    checkpoints = surface.get("canonical_checkpoints")
    if checkpoints != REQUIRED_CHECKPOINTS:
        failures.append(
            Failure(
                path,
                "Canonical checkpoints are missing, reordered, or renamed.",
                "Keep the checkpoint sequence exactly aligned with workflow/TEST_SPEC.md and CONTRACT_SURFACE_ALIGNMENT.md.",
            )
        )

    manifest_fields = set(surface.get("run_manifest_required_fields", []))
    if manifest_fields != REQUIRED_MANIFEST_FIELDS:
        failures.append(
            Failure(
                path,
                f"Run manifest fields are misaligned. Missing={sorted(REQUIRED_MANIFEST_FIELDS - manifest_fields)}; extra={sorted(manifest_fields - REQUIRED_MANIFEST_FIELDS)}.",
                "Record enough versions, hashes, scores, facts, operations, validations, and outputs to reconstruct the run.",
            )
        )

    surfaces = surface.get("surfaces")
    if not isinstance(surfaces, list):
        return [
            Failure(
                path,
                "workflow_surface.json must define a surfaces array.",
                "Declare one surface entry per public workflow function.",
            )
        ]
    surface_names = {entry.get("name") for entry in surfaces if isinstance(entry, dict)}
    if surface_names != ALLOWED_SURFACES:
        failures.append(
            Failure(
                path,
                f"Surface entries do not match allowed workflow functions. Missing={sorted(ALLOWED_SURFACES - surface_names)}; extra={sorted(surface_names - ALLOWED_SURFACES)}.",
                "Keep the manifest and public workflow API in lockstep.",
            )
        )
    for entry in surfaces:
        if not isinstance(entry, dict):
            failures.append(
                Failure(path, "Surface entry is not an object.", "Use an object with name, input_contract, and output_contract.")
            )
            continue
        name = entry.get("name", "<unknown>")
        output = entry.get("output_contract", {})
        if not isinstance(output, dict) or not output.get("required_fields"):
            failures.append(
                Failure(
                    path,
                    f"{name} output contract has no required fields.",
                    "Workflow outputs need stable DTO fields for CLI/plugin/audit consumers.",
                )
            )
    return failures


def iter_code_files(root: Path) -> Iterable[Path]:
    package_root = root / "workflow"
    if not package_root.exists():
        return
    for path in package_root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in CODE_SUFFIXES:
            yield path


def dotted_root(name: str) -> str:
    return name.split(".", 1)[0]


def scan_python_imports(path: Path, text: str) -> list[Failure]:
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return [
            Failure(
                path,
                f"Python source cannot be parsed: {exc.msg}.",
                "Fix syntax before boundary guardrails can classify imports.",
                exc.lineno,
            )
        ]
    failures: list[Failure] = []
    for node in ast.walk(tree):
        imported_names: list[str] = []
        if isinstance(node, ast.Import):
            imported_names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names = [node.module]
        for imported in imported_names:
            root_name = dotted_root(imported)
            for banned, message in FORBIDDEN_IMPORTS.items():
                banned_root = dotted_root(banned.replace("-", "_"))
                if root_name == banned_root or imported == banned:
                    failures.append(
                        Failure(
                            path,
                            f"Forbidden import '{imported}'. {message}",
                            "Keep workflow as a coordinator over public package APIs and persisted workflow artifacts.",
                            getattr(node, "lineno", None),
                        )
                    )
    return failures


def scan_text(path: Path, text: str) -> list[Failure]:
    failures: list[Failure] = []
    lowered = text.lower()

    for pattern in PRIVATE_IMPORT_PATTERNS:
        match = re.search(pattern, text)
        if match:
            failures.append(
                Failure(
                    path,
                    "Workflow imports private package internals instead of public APIs.",
                    "Add or use a public package surface; workflow must coordinate package outputs, not reach into private logic.",
                    line_for_offset(text, match.start()),
                )
            )

    for term, message in FORBIDDEN_TERMS.items():
        pattern = re.compile(rf"(?<![a-z0-9_.-]){re.escape(term)}(?![a-z0-9_.-])", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            failures.append(
                Failure(
                    path,
                    f"Forbidden workflow ownership term '{term}' appears in code. {message}",
                    "Record public package outputs and enforce checkpoints; do not reimplement domain truth rules inside workflow.",
                    line_for_offset(text, match.start()),
                )
            )

    for pattern in DIRECT_DB_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            failures.append(
                Failure(
                    path,
                    "Direct career database table write/query pattern appears in workflow code.",
                    "Use career-store/CLI public APIs and record artifact refs in workflow state.",
                    line_for_offset(text, match.start()),
                )
            )

    if re.search(r"resume/(base|working)\.json", text) and re.search(r"(replace|patch|apply|jsonpatch|set_path|delete_path|write_text|writeFile|fs\.write)", text, re.IGNORECASE):
        if not re.search(r"resume[_-]?core|core\.", text, re.IGNORECASE):
            failures.append(
                Failure(
                    path,
                    "Workflow appears to mutate resume files without a resume-core public API.",
                    "Workflow may record artifacts and operation state, but resume mutation must go through resume-core validation/application.",
                )
            )

    if re.search(r"(agent says|agent output|looks correct|plausible)", lowered) and re.search(r"(skip|bypass|complete).*(checkpoint|validation|gate)", lowered):
        failures.append(
            Failure(
                path,
                "Workflow appears to skip a checkpoint/gate based on agent plausibility.",
                "No checkpoint may be skipped because an agent output appears plausible. Require persisted deterministic evidence.",
            )
        )
    return failures


def run(root: Path) -> list[Failure]:
    surface, surface_failures = load_surface(root)
    failures = list(surface_failures)
    if surface:
        failures.extend(validate_surface(root, surface))

    for path in iter_code_files(root):
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            failures.extend(scan_python_imports(path, text))
            failures.extend(scan_python_architecture("workflow", path, text))
        failures.extend(scan_text(path, text))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    failures = run(root)
    if failures:
        print("workflow guardrails failed.\n")
        print("The workflow package may own state transitions, manifests, audit, and recovery only.")
        print("Package-private imports, alternate truth/scoring/validation rules, direct DB writes, direct resume mutation, and checkpoint skips are hard-blocked.\n")
        for failure in failures:
            print(failure.format(root))
        return 1

    print("workflow guardrails passed: state machine, manifest, audit, recovery, and ownership boundaries are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
