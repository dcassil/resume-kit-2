#!/usr/bin/env python3
"""Hard-blocking guardrails for test-suite layout, gates, and test ownership."""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path


REQUIRED_LAYOUT = {"unit", "contract", "boundary", "integration", "smoke", "e2e", "fixtures", "snapshots"}
PR_GATE = {"unit", "contract", "boundary", "deterministic_scoring_fixtures", "hallucination_rejection_fixtures"}
MAIN_GATE = {"pr", "smoke"}
RELEASE_GATE = {"main", "e2e", "renderer_parse_back", "migration_upgrade"}
RELEASE_BLOCKERS = {
    "fabricated_skill_title_metric_years_responsibility_scale_or_outcome",
    "inferred_fact_treated_as_verified",
    "related_fact_treated_as_equivalent_without_relationship",
    "missing_provenance_for_generated_claim",
    "nondeterministic_official_score",
    "base_resume_mutation",
    "raw_sql_mcp_exposure",
    "renderer_semantic_mutation",
    "lost_learned_facts_between_jobs",
    "duplicate_questions_for_verified_facts",
    "false_resolution_of_unresolved_hard_requirement",
}

BUSINESS_LOGIC_PATTERNS = {
    r"\bdef\s+(calculate|compute|score)_": "Tests must assert scoring behavior through package APIs, not implement scoring helpers.",
    r"\b(class|def)\s+.*Migration": "Database migration logic belongs in career-store/tools, not tests.",
    r"\bCREATE\s+TABLE\b": "SQLite schema belongs in career-store fixtures/tools, not test code.",
    r"\bINSERT\s+INTO\s+(facts|evidence|relationships)\b": "Tests should use public store/CLI APIs or fixtures, not direct table writes.",
    r"\bdef\s+apply_(resume_)?change": "Resume mutation logic belongs to resume-core; tests should call/expect public APIs.",
    r"\bdef\s+rewrite_bullet": "Semantic rewrite logic belongs to agent proposals/core validation, not tests.",
}

WEAKENING_PATTERNS = {
    r"\bassert\s+True\b": "A test with assert True does not protect a contract.",
    r"self\.assertTrue\(\s*True\s*\)": "A test with assertTrue(True) does not protect a contract.",
    r"pytest\.mark\.skip": "Skipping contract/boundary tests weakens gates unless explicitly justified outside this guardrail.",
    r"unittest\.skip": "Skipping contract/boundary tests weakens gates unless explicitly justified outside this guardrail.",
    r"TODO:\s*(weaken|relax|remove)": "Do not leave planned gate weakening in tests.",
}


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


def load_manifest(root: Path) -> tuple[dict, list[Failure]]:
    path = root / "tests" / "suite_manifest.json"
    if not path.exists():
        return {}, [Failure(path, "Missing test-suite manifest.", "Restore tests/suite_manifest.json so gates are machine-checkable.")]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return {}, [Failure(path, f"Invalid JSON: {exc.msg}.", "Fix JSON so test gates are machine-checkable.", exc.lineno)]


def validate_manifest(root: Path, manifest: dict) -> list[Failure]:
    path = root / "tests" / "suite_manifest.json"
    failures: list[Failure] = []
    if manifest.get("schema_version") != "tests-suite.v1":
        failures.append(Failure(path, "schema_version must be tests-suite.v1.", "Keep suite manifest version stable until the test contract changes."))

    layout = set(manifest.get("required_layout", []))
    if layout != REQUIRED_LAYOUT:
        failures.append(
            Failure(
                path,
                f"Required test layout is misaligned. Missing={sorted(REQUIRED_LAYOUT - layout)}; extra={sorted(layout - REQUIRED_LAYOUT)}.",
                "Keep tests organized by unit, contract, boundary, integration, smoke, e2e, fixtures, and snapshots.",
            )
        )
    for directory in REQUIRED_LAYOUT:
        target = root / "tests" / directory
        if not target.is_dir():
            failures.append(Failure(target, "Required test directory is missing.", "Create the directory with a .gitkeep if no tests exist yet."))

    gates = manifest.get("required_gates", {})
    if set(gates.get("pr", [])) != PR_GATE:
        failures.append(Failure(path, "PR gate is missing required test categories.", "PR must run unit, contract, boundary, deterministic scoring, and hallucination fixtures."))
    if set(gates.get("main", [])) != MAIN_GATE:
        failures.append(Failure(path, "Main gate is missing required test categories.", "Main must run the PR gate and full smoke test."))
    if set(gates.get("release_candidate", [])) != RELEASE_GATE:
        failures.append(Failure(path, "Release-candidate gate is missing required test categories.", "Release candidates must run main, E2E, renderer parse-back, and migration upgrade tests."))

    blockers = set(manifest.get("release_blockers", []))
    if blockers != RELEASE_BLOCKERS:
        failures.append(
            Failure(
                path,
                f"Release blockers are misaligned. Missing={sorted(RELEASE_BLOCKERS - blockers)}; extra={sorted(blockers - RELEASE_BLOCKERS)}.",
                "Keep all product safety blockers represented in the suite manifest.",
            )
        )
    return failures


def scan_tests(root: Path) -> list[Failure]:
    failures: list[Failure] = []
    tests_root = root / "tests"
    for path in tests_root.rglob("*.py"):
        original_text = path.read_text(encoding="utf-8")
        text = strip_string_literals(original_text)
        for pattern, solution in BUSINESS_LOGIC_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                failures.append(
                    Failure(
                        path,
                        "Test file appears to define hidden business logic.",
                        solution,
                        line_for_offset(original_text, match.start()),
                    )
                )
        for pattern, solution in WEAKENING_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                failures.append(
                    Failure(
                        path,
                        "Test file contains a gate-weakening pattern.",
                        solution,
                        line_for_offset(original_text, match.start()),
                    )
                )
    return failures


def strip_string_literals(text: str) -> str:
    """Preserve line structure while removing string payloads used as guardrail fixtures."""
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        pieces: list[str] = []
        last_line = 1
        last_col = 0
        for token in tokens:
            start_line, start_col = token.start
            end_line, end_col = token.end
            if start_line > last_line:
                pieces.append("\n" * (start_line - last_line))
                last_col = 0
            if start_col > last_col:
                pieces.append(" " * (start_col - last_col))
            if token.type == tokenize.STRING:
                replacement = "''"
                if end_line > start_line:
                    replacement += "\n" * (end_line - start_line)
                pieces.append(replacement)
            else:
                pieces.append(token.string)
            last_line = end_line
            last_col = end_col
        return "".join(pieces)
    except tokenize.TokenError:
        return text


def run(root: Path) -> list[Failure]:
    manifest, failures = load_manifest(root)
    if manifest:
        failures.extend(validate_manifest(root, manifest))
    failures.extend(scan_tests(root))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    failures = run(root)
    if failures:
        print("tests guardrails failed.\n")
        print("The tests package owns suite layout and gates, not hidden business logic.")
        print("Layout drift, weakened gates, missing release blockers, and business logic inside tests are hard-blocked.\n")
        for failure in failures:
            print(failure.format(root))
        return 1

    print("tests guardrails passed: suite layout, gates, blockers, and test ownership are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
