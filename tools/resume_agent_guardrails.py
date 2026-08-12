#!/usr/bin/env python3
"""Hard-blocking guardrails for the resume-agent proposal boundary."""

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
    "extractResumeSemantics",
    "extractJobSemantics",
    "generateClarificationQuestion",
    "interpretUserAnswer",
    "proposeRewrite",
}

FORBIDDEN_IMPORTS = {
    "sqlite3": "resume-agent must not directly update SQLite. Persist through career-store after validation outside the agent.",
    "aiosqlite": "resume-agent must not open SQLite connections. It emits proposals only.",
    "sqlalchemy": "resume-agent must not own persistence sessions or database models.",
    "career_store": "resume-agent must not bypass validation by importing career-store internals. Return fact/evidence proposals for store validation.",
    "career-store": "resume-agent must not bypass validation by importing career-store internals. Return fact/evidence proposals for store validation.",
    "career_mcp": "resume-agent must not call MCP tools as hidden workflow. Orchestration owns tool calls; agent returns proposals.",
    "career-mcp": "resume-agent must not call MCP tools as hidden workflow. Orchestration owns tool calls; agent returns proposals.",
    "resume_cli": "resume-agent must not orchestrate workflow or write workspace artifacts.",
    "resume-cli": "resume-agent must not orchestrate workflow or write workspace artifacts.",
    "resume_plugin": "resume-agent must not import plugin presentation or host adapter code.",
    "resume-plugin": "resume-agent must not import plugin presentation or host adapter code.",
    "resume_render": "resume-agent must not render output or change semantics for layout.",
    "resume-render": "resume-agent must not render output or change semantics for layout.",
}

FORBIDDEN_TERMS = {
    "official_score": "Official match scoring belongs to resume-core. Agent output may include reasoning proposals, not scores.",
    "overall_score": "Overall score belongs to resume-core. Do not compute or set it in resume-agent.",
    "matchresult": "MatchResult is a resume-core authority surface. Agent may not own or compute it.",
    "match_result": "MatchResult is a resume-core authority surface. Agent may not own or compute it.",
    "apply_change": "Applying ResumeChangeOperation belongs to resume-core/workflow. Agent may only propose operations.",
    "apply_changes": "Applying ResumeChangeOperation belongs to resume-core/workflow. Agent may only propose operations.",
    "persisted": "resume-agent should not report persistence authority. It returns proposals for validation and persistence elsewhere.",
    "user_verified": "resume-agent may mention requested verification targets only as proposals; it must not declare user_verified authority.",
    "final_verification_state": "Final verification state is store/core authority, not agent authority.",
    "workflow_transition": "Workflow transitions are code-owned. Agent may phrase or interpret, not advance stages.",
    "canonical_resume": "resume-agent must not output or mutate a canonical final resume object.",
    "working_resume": "resume-agent must not output or mutate resume/working.json authority.",
}

INFLATION_PATTERNS = {
    "20 million users": "Unsupported user-scale claims are blocked unless present in allowed facts and validated downstream.",
    "30 engineers": "Unsupported management-scope claims are blocked unless present in allowed facts and validated downstream.",
    "staff software engineer": "Do not inflate actual employment title to Staff Software Engineer from a target job title.",
    "staff engineer": "Do not add Staff title employment history unless source evidence explicitly supports it.",
    "10 years of aws": "Do not inflate AWS experience from six years to ten.",
    "ten years of aws": "Do not inflate AWS experience from six years to ten.",
}

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
    path = root / "resume-agent" / "agent_surface.json"
    if not path.exists():
        return {}, [
            Failure(
                path,
                "Missing machine-readable agent surface contract.",
                "Restore resume-agent/agent_surface.json and update it before changing the public proposal API.",
            )
        ]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return {}, [
            Failure(
                path,
                f"Invalid JSON: {exc.msg}.",
                "Fix the JSON so contract tests and guardrails can compare the declared proposal surface to implementation.",
                exc.lineno,
            )
        ]


def validate_surface(root: Path, surface: dict) -> list[Failure]:
    path = root / "resume-agent" / "agent_surface.json"
    failures: list[Failure] = []
    functions = set(surface.get("public_api", {}).get("functions", []))
    if functions != ALLOWED_SURFACES:
        failures.append(
            Failure(
                path,
                f"Declared public functions differ from resume-agent/TEST_SPEC.md. Missing={sorted(ALLOWED_SURFACES - functions)}; extra={sorted(functions - ALLOWED_SURFACES)}.",
                "Expose exactly the five proposal functions from resume-agent/TEST_SPEC.md. Document contract changes before changing this manifest.",
            )
        )

    surfaces = surface.get("surfaces")
    if not isinstance(surfaces, list):
        return [
            Failure(
                path,
                "agent_surface.json must define a top-level surfaces array.",
                "Declare one surface entry per public proposal function.",
            )
        ]
    surface_names = {entry.get("name") for entry in surfaces if isinstance(entry, dict)}
    if surface_names != ALLOWED_SURFACES:
        failures.append(
            Failure(
                path,
                f"Surface entries do not match allowed public functions. Missing={sorted(ALLOWED_SURFACES - surface_names)}; extra={sorted(surface_names - ALLOWED_SURFACES)}.",
                "Keep the manifest and public API in lockstep.",
            )
        )

    for entry in surfaces:
        if not isinstance(entry, dict):
            failures.append(
                Failure(
                    path,
                    "Surface entry is not an object.",
                    "Use an object with name, description, input_contract, and output_contract.",
                )
            )
            continue
        name = entry.get("name", "<unknown>")
        output = entry.get("output_contract", {})
        required_fields = set(output.get("required_fields", [])) if isinstance(output, dict) else set()
        required_basics = {"schema_version", "proposal_type", "uncertainty", "requires_validation"}
        missing = sorted(required_basics - required_fields)
        if missing:
            failures.append(
                Failure(
                    path,
                    f"{name} output contract is missing proposal handoff fields {missing}.",
                    "Every agent output must preserve schema version, proposal type, uncertainty, and downstream validation requirement.",
                )
            )
        if "must_not_include" not in output:
            failures.append(
                Failure(
                    path,
                    f"{name} does not declare forbidden authoritative output fields.",
                    "Add output_contract.must_not_include so full resume mutation, scoring, verification authority, and unsupported additions stay blocked.",
                )
            )
        text = json.dumps(entry, sort_keys=True).lower()
        if name in {"interpretUserAnswer", "proposeRewrite"} and "validation" not in text:
            failures.append(
                Failure(
                    path,
                    f"{name} does not clearly hand off to validation.",
                    "Document that generated proposals require core/store validation before use.",
                )
            )
    return failures


def iter_code_files(root: Path) -> Iterable[Path]:
    package_root = root / "resume-agent"
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
                            "Keep resume-agent limited to prompt/schema/proposal code and public contract DTOs. Route persistence, workflow, rendering, and presentation through their owning packages.",
                            getattr(node, "lineno", None),
                        )
                    )
    return failures


def scan_text(path: Path, text: str) -> list[Failure]:
    failures: list[Failure] = []
    lowered = text.lower()

    for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
        function_name = match.group(1)
        if function_name.startswith("extract") or function_name.startswith("generate") or function_name.startswith("interpret") or function_name.startswith("propose"):
            if function_name not in ALLOWED_SURFACES and not function_name.startswith("_"):
                failures.append(
                    Failure(
                        path,
                        f"Potential public proposal function '{function_name}' is not in resume-agent/TEST_SPEC.md.",
                        "Keep public API to extractResumeSemantics, extractJobSemantics, generateClarificationQuestion, interpretUserAnswer, and proposeRewrite; make helpers private.",
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
                    f"Forbidden authority term '{term}' appears in resume-agent code. {message}",
                    "Return structured proposals with requires_validation=true and let resume-core/career-store/workflow own authoritative state.",
                    line_for_offset(text, match.start()),
                )
            )

    for phrase, message in INFLATION_PATTERNS.items():
        index = lowered.find(phrase)
        if index != -1:
            failures.append(
                Failure(
                    path,
                    f"Blocked unsupported/inflation phrase '{phrase}'. {message}",
                    "Treat these as prohibited additions or explicit negative facts unless supplied as allowed, validated evidence.",
                    line_for_offset(lowered, index),
                )
            )

    sql = re.search(r"\b(select|insert|update|delete|create|drop|alter)\s+[^;\n]*(from|into|table|facts|evidence|resume_)\b", text, re.IGNORECASE)
    if sql:
        failures.append(
            Failure(
                path,
                "Raw SQL-like statement appears in resume-agent code.",
                "Move persistence/query behavior into career-store. Agent code returns fact/evidence proposals only.",
                line_for_offset(text, sql.start()),
            )
        )

    if re.search(r"resume/(base|working)\.json", text) and re.search(r"(write_text|open\(|fs\.write|writeFile|unlink|rename|replace)", text):
        failures.append(
            Failure(
                path,
                "resume-agent appears to write resume/base.json or resume/working.json.",
                "Resume files are workflow/CLI artifacts. Agent code must return proposal DTOs only.",
            )
        )

    if re.search(r"\b(canonical_resume|working_resume|resume)\b", lowered) and re.search(r"\b(return|yield)\b", lowered) and "proposal" not in lowered:
        failures.append(
            Failure(
                path,
                "resume-agent appears to return a resume object without proposal framing.",
                "Return ResumeChangeOperation proposals or extraction proposals, never a mutated authoritative resume.",
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
        print("resume-agent guardrails failed.\n")
        print("The agent package may produce schema-constrained proposals only.")
        print("Truth, scoring, persistence, validation authority, direct mutation, rendering, and presentation are hard-blocked.\n")
        for failure in failures:
            print(failure.format(root))
        return 1

    print("resume-agent guardrails passed: proposal API, module boundaries, and forbidden authority paths are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
