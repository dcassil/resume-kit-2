#!/usr/bin/env python3
"""Hard-blocking guardrails for the resume-cli orchestration boundary."""

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


REQUIRED_COMMANDS = {
    "resume init",
    "resume ingest <file>",
    "resume job ingest <file-or-url-text>",
    "resume match",
    "resume resolve",
    "resume tailor",
    "resume validate",
    "resume export --format docx",
    "resume run <resume> <job>",
    "resume inspect fact <id>",
    "resume inspect requirement <id>",
    "resume audit",
}

REQUIRED_CHECKPOINTS = {
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
}

FORBIDDEN_IMPORTS = {
    "sqlite3": "resume-cli must not write career DB tables directly. Initialize/migrate through career-store public APIs.",
    "aiosqlite": "resume-cli must not write career DB tables directly. Initialize/migrate through career-store public APIs.",
    "sqlalchemy": "resume-cli must not own career persistence sessions or table models.",
    "resume_plugin": "resume-cli must not import plugin host/presentation behavior. Keep plugin as an adapter over the same workflow/domain APIs.",
    "resume-plugin": "resume-cli must not import plugin host/presentation behavior. Keep plugin as an adapter over the same workflow/domain APIs.",
}

FORBIDDEN_TERMS = {
    "scoring_weights": "Scoring weights belong to resume-core configuration and scoring APIs, not CLI-local formulas.",
    "score_weight": "Scoring weights belong to resume-core configuration and scoring APIs, not CLI-local formulas.",
    "requirement_weight": "Requirement weighting belongs to resume-core. CLI may display results only.",
    "calculate_score": "Independent scoring logic is forbidden in resume-cli. Call resume-core scoring APIs.",
    "compute_score": "Independent scoring logic is forbidden in resume-cli. Call resume-core scoring APIs.",
    "score_resume": "Independent scoring logic is forbidden in resume-cli. Call resume-core scoring APIs.",
    "apply_resume_change": "Applying resume mutations must go through resume-core validated operation APIs.",
    "apply_change_operation": "Applying resume mutations must go through resume-core validated operation APIs.",
    "rewrite_to_fit": "Renderer path must not semantically rewrite or truncate; use renderer overflow constraints and rerun selection/rewrite upstream.",
    "truncate_to_fit": "Renderer path must not silently truncate content; use overflow constraints.",
    "plugin_tool": "Plugin behavior must not live in resume-cli. Share domain workflow APIs instead.",
    "plugin_manifest": "Plugin behavior must not live in resume-cli. Share domain workflow APIs instead.",
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
    path = root / "resume-cli" / "cli_surface.json"
    if not path.exists():
        return {}, [
            Failure(
                path,
                "Missing machine-readable CLI surface contract.",
                "Restore resume-cli/cli_surface.json and update it before changing command behavior.",
            )
        ]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return {}, [
            Failure(
                path,
                f"Invalid JSON: {exc.msg}.",
                "Fix the JSON so contract tests and guardrails can compare the declared CLI surface to implementation.",
                exc.lineno,
            )
        ]


def validate_surface(root: Path, surface: dict) -> list[Failure]:
    path = root / "resume-cli" / "cli_surface.json"
    failures: list[Failure] = []
    commands = set(surface.get("required_commands", []))
    if commands != REQUIRED_COMMANDS:
        failures.append(
            Failure(
                path,
                f"Declared command surface differs from resume-cli/TEST_SPEC.md. Missing={sorted(REQUIRED_COMMANDS - commands)}; extra={sorted(commands - REQUIRED_COMMANDS)}.",
                "Expose exactly the required resume CLI commands, or update TEST_SPEC.md before changing the contract.",
            )
        )
    checkpoints = set(surface.get("canonical_checkpoints", []))
    if checkpoints != REQUIRED_CHECKPOINTS:
        failures.append(
            Failure(
                path,
                f"Canonical checkpoints are misaligned. Missing={sorted(REQUIRED_CHECKPOINTS - checkpoints)}; extra={sorted(checkpoints - REQUIRED_CHECKPOINTS)}.",
                "Keep run orchestration aligned with PRODUCT_VISION_AND_CONTRACTS.md and resume-cli/TEST_SPEC.md.",
            )
        )
    entries = surface.get("commands")
    if not isinstance(entries, list):
        return [
            Failure(
                path,
                "cli_surface.json must define a commands array.",
                "Declare one command entry per required command with argv, description, and ownership limits.",
            )
        ]
    names = {entry.get("name") for entry in entries if isinstance(entry, dict)}
    required_names = {
        "init",
        "ingest_resume",
        "ingest_job",
        "match",
        "resolve",
        "tailor",
        "validate",
        "export",
        "run",
        "inspect_fact",
        "inspect_requirement",
        "audit",
    }
    if names != required_names:
        failures.append(
            Failure(
                path,
                f"Command entries are incomplete. Missing={sorted(required_names - names)}; extra={sorted(names - required_names)}.",
                "Keep the machine-readable command entries in lockstep with the required command surface.",
            )
        )
    for entry in entries:
        if not isinstance(entry, dict):
            failures.append(
                Failure(
                    path,
                    "Command entry is not an object.",
                    "Use an object with name, argv, description, and must_not/checkpoint fields.",
                )
            )
            continue
        name = entry.get("name", "<unknown>")
        if not entry.get("argv"):
            failures.append(
                Failure(
                    path,
                    f"{name} command is missing argv.",
                    "Declare the exact argument shape the CLI must accept.",
                )
            )
        if not entry.get("must_not"):
            failures.append(
                Failure(
                    path,
                    f"{name} command is missing must_not ownership guardrails.",
                    "Document what this command must not own so future implementation stays at orchestration level.",
                )
            )
    return failures


def iter_code_files(root: Path) -> Iterable[Path]:
    package_root = root / "resume-cli"
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
                            "Keep resume-cli as an orchestrator over public package APIs; move persistence, plugin presentation, and domain behavior to their owning packages.",
                            getattr(node, "lineno", None),
                        )
                    )
    return failures


def scan_text(path: Path, text: str) -> list[Failure]:
    failures: list[Failure] = []
    lowered = text.lower()

    for term, message in FORBIDDEN_TERMS.items():
        pattern = re.compile(rf"(?<![a-z0-9_.-]){re.escape(term)}(?![a-z0-9_.-])", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            failures.append(
                Failure(
                    path,
                    f"Forbidden CLI ownership term '{term}' appears in code. {message}",
                    "Call the owning package's public API and persist/report its result instead of reimplementing the behavior in CLI.",
                    line_for_offset(text, match.start()),
                )
            )

    for pattern in DIRECT_DB_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            failures.append(
                Failure(
                    path,
                    "Direct career database table write/query pattern appears in resume-cli code.",
                    "Use career-store service/migration APIs. CLI may create workspace paths but must not own career DB table writes.",
                    line_for_offset(text, match.start()),
                )
            )

    score_formula = re.search(r"\b(score|points|rank)\b\s*=\s*[^#\n]*(\+|\*|/|weight|points)", text, re.IGNORECASE)
    if score_formula and not re.search(r"resume[_-]?core|core\.", text, re.IGNORECASE):
        failures.append(
            Failure(
                path,
                "Possible independent scoring formula found in resume-cli code.",
                "Run official scoring through resume-core and display the returned MatchResult instead.",
                line_for_offset(text, score_formula.start()),
            )
        )

    if re.search(r"resume/(base|working)\.json", text) and re.search(r"(replace|patch|apply|jsonpatch|set_path|delete_path)", text, re.IGNORECASE):
        if not re.search(r"resume[_-]?core|core\.", text, re.IGNORECASE):
            failures.append(
                Failure(
                    path,
                    "CLI appears to apply resume JSON mutations without a resume-core call.",
                    "Persist proposed operations separately, validate/apply through resume-core, then write the validated working artifact.",
                )
            )

    if "resume/base.json" in lowered and re.search(r"(write_text|writefile|fs\.write|open\()", text, re.IGNORECASE):
        if not re.search(r"re[-_ ]?ingest|explicit", lowered):
            failures.append(
                Failure(
                    path,
                    "CLI writes resume/base.json without an explicit re-ingest guard.",
                    "Base resume is immutable after ingest. Only write it during ingest/re-ingest after validation and hash recording.",
                )
            )

    if re.search(r"(agent says|agent output|looks correct)", lowered) and re.search(r"(skip|bypass).*(validate|validation|checkpoint)", lowered):
        failures.append(
            Failure(
                path,
                "CLI appears to skip validation/checkpoints based on agent output.",
                "No checkpoint may be skipped because an agent says the result looks correct. Run deterministic workflow gates.",
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
            failures.extend(scan_python_architecture("resume-cli", path, text))
        failures.extend(scan_text(path, text))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    failures = run(root)
    if failures:
        print("resume-cli guardrails failed.\n")
        print("The CLI package may orchestrate public APIs and persist workflow artifacts only.")
        print("Independent scoring, direct career DB writes, private mutation logic, renderer semantic changes, plugin behavior, and checkpoint skips are hard-blocked.\n")
        for failure in failures:
            print(failure.format(root))
        return 1

    print("resume-cli guardrails passed: command surface, workflow checkpoints, and orchestration boundaries are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
