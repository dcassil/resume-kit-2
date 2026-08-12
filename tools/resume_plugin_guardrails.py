#!/usr/bin/env python3
"""Hard-blocking guardrails for the resume-plugin adapter boundary."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ALLOWED_SURFACES = {
    "getPluginManifest",
    "registerTools",
    "mapConversationToWorkflow",
    "presentConfirmationRequest",
    "presentDiff",
    "presentReport",
    "presentAuditSummary",
}

FORBIDDEN_IMPORTS = {
    "sqlite3": "resume-plugin must not write SQLite directly. Route persistence through CLI/workflow/store APIs.",
    "aiosqlite": "resume-plugin must not write SQLite directly. Route persistence through CLI/workflow/store APIs.",
    "sqlalchemy": "resume-plugin must not own SQLite schema, migrations, sessions, or table models.",
}

PRIVATE_IMPORT_PATTERNS = [
    r"\bfrom\s+(resume_core|career_store|career_mcp|resume_agent|resume_render|workflow)\.(?:_internal|internal|private|migrations|schema|schemas|tables|adapters)\b",
    r"\bimport\s+(resume_core|career_store|career_mcp|resume_agent|resume_render|workflow)\.(?:_internal|internal|private|migrations|schema|schemas|tables|adapters)\b",
]

FORBIDDEN_TERMS = {
    "scoring_algorithm": "Plugin must display domain scores, not define scoring algorithms.",
    "scoring_weights": "Scoring configuration belongs to resume-core/config, not plugin code.",
    "calculate_score": "Independent scoring logic is forbidden in resume-plugin.",
    "compute_score": "Independent scoring logic is forbidden in resume-plugin.",
    "sqlite_schema": "SQLite schema and migrations belong to career-store.",
    "create table": "SQLite schema and migrations belong to career-store.",
    "ats_sanitize": "ATS sanitation belongs to resume-core/renderer validation, not plugin code.",
    "sanitize_ats": "ATS sanitation belongs to resume-core/renderer validation, not plugin code.",
    "canonical_resume_schema": "Canonical resume schema belongs to resume-core.",
    "canonical_job_schema": "Canonical job schema belongs to resume-core.",
    "career_learning": "Career learning behavior belongs to career-store/workflow, not plugin code.",
    "learn_fact": "Career learning behavior belongs to career-store/workflow, not plugin code.",
    "apply_resume_change": "Mutation logic belongs to resume-core/workflow. Plugin may present diffs only.",
    "apply_change_operation": "Mutation logic belongs to resume-core/workflow. Plugin may present diffs only.",
    "validation_bypass": "Host instructions must not allow bypassing validation.",
    "bypass validation": "Host instructions must not allow bypassing validation.",
    "skip validation": "Host instructions must not allow bypassing validation.",
    "internal_provenance": "Final resume/plugin presentation must not export internal provenance metadata.",
    "raw_career_db": "Plugin prompts must not include broad raw career DB context.",
    "career_db_dump": "Plugin prompts must not include broad raw career DB context.",
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
    path = root / "resume-plugin" / "plugin_surface.json"
    if not path.exists():
        return {}, [
            Failure(
                path,
                "Missing machine-readable plugin surface contract.",
                "Restore resume-plugin/plugin_surface.json and update it before changing adapter behavior.",
            )
        ]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return {}, [
            Failure(
                path,
                f"Invalid JSON: {exc.msg}.",
                "Fix the JSON so contract tests and guardrails can compare the declared plugin surface to implementation.",
                exc.lineno,
            )
        ]


def validate_surface(root: Path, surface: dict) -> list[Failure]:
    path = root / "resume-plugin" / "plugin_surface.json"
    failures: list[Failure] = []
    functions = set(surface.get("public_api", {}).get("functions", []))
    if functions != ALLOWED_SURFACES:
        failures.append(
            Failure(
                path,
                f"Declared public functions differ from resume-plugin adapter contract. Missing={sorted(ALLOWED_SURFACES - functions)}; extra={sorted(functions - ALLOWED_SURFACES)}.",
                "Expose only adapter surfaces for manifest, registration, mapping, confirmations, diffs, reports, and audit presentation.",
            )
        )

    surfaces = surface.get("surfaces")
    if not isinstance(surfaces, list):
        return [
            Failure(
                path,
                "plugin_surface.json must define a surfaces array.",
                "Declare one surface entry per public adapter function.",
            )
        ]
    surface_names = {entry.get("name") for entry in surfaces if isinstance(entry, dict)}
    if surface_names != ALLOWED_SURFACES:
        failures.append(
            Failure(
                path,
                f"Surface entries do not match allowed adapter functions. Missing={sorted(ALLOWED_SURFACES - surface_names)}; extra={sorted(surface_names - ALLOWED_SURFACES)}.",
                "Keep the manifest and public adapter API in lockstep.",
            )
        )

    for entry in surfaces:
        if not isinstance(entry, dict):
            failures.append(
                Failure(
                    path,
                    "Surface entry is not an object.",
                    "Use an object with name, description, and output_contract.",
                )
            )
            continue
        name = entry.get("name", "<unknown>")
        output = entry.get("output_contract", {})
        required_fields = set(output.get("required_fields", [])) if isinstance(output, dict) else set()
        if not required_fields:
            failures.append(
                Failure(
                    path,
                    f"{name} output contract has no required fields.",
                    "Adapter outputs need stable DTO fields so host presentations stay synchronized.",
                )
            )
        if "must_not_include" not in output and name != "registerTools":
            failures.append(
                Failure(
                    path,
                    f"{name} must declare forbidden adapter output fields.",
                    "Add output_contract.must_not_include to prevent domain behavior, provenance leaks, and validation bypasses.",
                )
            )
    return failures


def iter_code_files(root: Path) -> Iterable[Path]:
    package_root = root / "resume-plugin"
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
                            "Keep resume-plugin as a host adapter over public workflow/CLI/domain APIs.",
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
                    "Plugin imports private package internals instead of public APIs.",
                    "Route through public CLI/workflow/domain APIs; add a public package surface if the adapter needs new data.",
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
                    f"Forbidden plugin ownership term '{term}' appears in code. {message}",
                    "Keep plugin code to mapping and presentation; delegate domain behavior to public package APIs.",
                    line_for_offset(text, match.start()),
                )
            )

    for pattern in DIRECT_DB_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            failures.append(
                Failure(
                    path,
                    "Direct SQLite/table write pattern appears in resume-plugin code.",
                    "Use CLI/workflow/store public APIs. Plugin adapters must not own persistence.",
                    line_for_offset(text, match.start()),
                )
            )

    if re.search(r"resume/working\.json", text) and re.search(r"(write_text|writeFile|fs\.write|open\(|replace|patch|apply)", text, re.IGNORECASE):
        failures.append(
            Failure(
                path,
                "Plugin appears to write resume/working.json directly.",
                "Map to CLI/workflow tailoring commands and present the resulting diff/report instead.",
            )
        )

    if re.search(r"\b(score|points|rank)\b\s*=\s*[^#\n]*(\+|\*|/|weight|points)", text, re.IGNORECASE):
        failures.append(
            Failure(
                path,
                "Possible independent scoring formula found in resume-plugin code.",
                "Present score/report DTOs returned by domain workflow; do not compute scores in the adapter.",
            )
        )

    if "all career facts" in lowered or "entire career database" in lowered or "full career db" in lowered:
        failures.append(
            Failure(
                path,
                "Plugin prompt appears to include broader career DB context than needed.",
                "Present only the code-selected requirement and minimum fact/evidence summary needed for confirmation.",
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
        failures.extend(scan_text(path, text))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    failures = run(root)
    if failures:
        print("resume-plugin guardrails failed.\n")
        print("The plugin package may map host interactions and present workflow outputs only.")
        print("Scoring, SQLite schema/migrations, ATS sanitation, mutation logic, canonical schemas, career learning, validation bypass, and private internals are hard-blocked.\n")
        for failure in failures:
            print(failure.format(root))
        return 1

    print("resume-plugin guardrails passed: adapter surface, presentation scope, and forbidden domain ownership paths are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
