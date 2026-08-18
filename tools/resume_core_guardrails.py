#!/usr/bin/env python3
"""Hard-blocking guardrails for the resume-core truth boundary."""

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
    "normalizeResume",
    "validateResume",
    "sanitizeText",
    "normalizeJobModel",
    "scoreMatch",
    "getUnresolvedRequirements",
    "rankResumeContent",
    "toRenderableResume",
    "validateChange",
    "applyChange",
    "validateGrounding",
    "validateFinalResume",
}

REQUIRED_TYPES = {
    "CanonicalResume",
    "RenderableResume",
    "ResumeField",
    "JobModel",
    "JobRequirement",
    "MatchResult",
    "ResolutionState",
    "ResumeChangeOperation",
    "VerificationState",
}

REQUIRED_OUTPUTS = {
    "normalizeResume": {"canonical_resume", "warnings", "provenance_map"},
    "validateResume": {"errors", "warnings"},
    "sanitizeText": {"text", "warnings"},
    "normalizeJobModel": {"job_model", "warnings"},
    "scoreMatch": {"match_result"},
    "toRenderableResume": {"renderable_resume", "errors", "warnings"},
    "getUnresolvedRequirements": {"unresolved_requirements", "can_continue"},
    "rankResumeContent": {"selection_plan", "ranked_content"},
    "validateChange": {"operation_id", "validation_state", "errors", "grounding"},
    "applyChange": {"working_resume", "operation_id", "audit"},
    "validateGrounding": {"unsupported_claims", "missing_provenance", "warnings"},
    "validateFinalResume": {"final_resume", "match_result", "errors", "warnings"},
}

FORBIDDEN_IMPORTS = {
    "sqlite3": "resume-core must not depend on SQLite adapters. Consume supplied career fact DTOs instead.",
    "aiosqlite": "resume-core must not open SQLite connections. Persistence belongs to career-store.",
    "sqlalchemy": "resume-core must not own database sessions, schemas, migrations, or table models.",
    "career_store": "resume-core must not import career-store implementation details. Consume stable fact DTOs supplied by callers.",
    "career-store": "resume-core must not import career-store implementation details. Consume stable fact DTOs supplied by callers.",
    "career_mcp": "resume-core must not call MCP tools. Orchestration/adapters supply validated DTOs.",
    "career-mcp": "resume-core must not call MCP tools. Orchestration/adapters supply validated DTOs.",
    "resume_agent": "resume-core must not call agent runtimes. Validate proposals passed in as data.",
    "resume-agent": "resume-core must not call agent runtimes. Validate proposals passed in as data.",
    "resume_cli": "resume-core must not import CLI orchestration or workspace behavior.",
    "resume-cli": "resume-core must not import CLI orchestration or workspace behavior.",
    "resume_plugin": "resume-core must not import plugin presentation or host adapter code.",
    "resume-plugin": "resume-core must not import plugin presentation or host adapter code.",
    "resume_render": "resume-core must not render output. Return validated resume DTOs for renderer input.",
    "resume-render": "resume-core must not render output. Return validated resume DTOs for renderer input.",
    "openai": "resume-core must not call LLMs. Agent/language behavior must arrive as proposals for validation.",
    "anthropic": "resume-core must not call LLMs. Agent/language behavior must arrive as proposals for validation.",
    "langchain": "resume-core must not call LLM chains. Agent/language behavior must arrive as proposals for validation.",
    "requests": "resume-core must not fetch remote content as part of deterministic domain APIs.",
    "httpx": "resume-core must not fetch remote content as part of deterministic domain APIs.",
    "subprocess": "resume-core must not shell out or drive terminal workflows.",
    "typer": "resume-core must not own terminal UI.",
    "click": "resume-core must not own terminal UI.",
    "rich": "resume-core must not own terminal UI.",
    "prompt_toolkit": "resume-core must not ask terminal prompts.",
}

FORBIDDEN_TERMS = {
    "create_career_mcp": "MCP adapter construction belongs to career-mcp.",
    "call_tool": "MCP/tool calls belong to adapters or workflow, not resume-core.",
    "renderMarkdown": "Rendering belongs to resume-render.",
    "renderDocx": "Rendering belongs to resume-render.",
    "renderPdf": "Rendering belongs to resume-render.",
    "advanceCheckpoint": "Workflow state transitions belong to workflow/CLI, not resume-core.",
    "recordCheckpointResult": "Workflow state persistence belongs to workflow/CLI, not resume-core.",
    "ask_user": "Core may return unresolved requirements, but must not ask natural-language questions.",
    "prompt_user": "Core may return unresolved requirements, but must not ask terminal/chat prompts.",
}

FILE_IO_PATTERNS = [
    r"\bopen\s*\(",
    r"\.read_text\s*\(",
    r"\.write_text\s*\(",
    r"\.read_bytes\s*\(",
    r"\.write_bytes\s*\(",
    r"\breadFile(?:Sync)?\s*\(",
    r"\bwriteFile(?:Sync)?\s*\(",
]

CODE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
IGNORED_DIRS = {"__pycache__", ".pytest_cache", "node_modules", ".venv", "venv", "dist", "build"}
PUBLIC_FUNCTION_PREFIXES = ("normalize", "validate", "sanitize", "score", "get", "rank", "apply")


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
    path = root / "resume-core" / "core_surface.json"
    if not path.exists():
        return {}, [
            Failure(
                path,
                "Missing machine-readable resume-core surface contract.",
                "Restore resume-core/core_surface.json and update it before changing public domain behavior.",
            )
        ]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return {}, [
            Failure(
                path,
                f"Invalid JSON: {exc.msg}.",
                "Fix the JSON so contract tests and guardrails can compare the declared domain surface to implementation.",
                exc.lineno,
            )
        ]


def validate_surface(root: Path, surface: dict) -> list[Failure]:
    path = root / "resume-core" / "core_surface.json"
    failures: list[Failure] = []
    public_api = surface.get("public_api", {})
    functions = set(public_api.get("functions", []))
    if functions != ALLOWED_SURFACES:
        failures.append(
            Failure(
                path,
                f"Declared public functions differ from resume-core/TEST_SPEC.md. Missing={sorted(ALLOWED_SURFACES - functions)}; extra={sorted(functions - ALLOWED_SURFACES)}.",
                "Expose exactly the deterministic domain functions from resume-core/TEST_SPEC.md. Document contract changes before changing this manifest.",
            )
        )

    types = set(public_api.get("types", []))
    if types != REQUIRED_TYPES:
        failures.append(
            Failure(
                path,
                f"Declared public types differ from resume-core/TEST_SPEC.md. Missing={sorted(REQUIRED_TYPES - types)}; extra={sorted(types - REQUIRED_TYPES)}.",
                "Keep the canonical DTO/type surface aligned with the test spec.",
            )
        )

    surfaces = surface.get("surfaces")
    if not isinstance(surfaces, list):
        return [
            Failure(
                path,
                "core_surface.json must define a top-level surfaces array.",
                "Declare one surface entry per public domain function.",
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
            failures.append(Failure(path, "Surface entry is not an object.", "Use an object with name, input_contract, and output_contract."))
            continue
        name = entry.get("name", "<unknown>")
        output = entry.get("output_contract", {})
        required_fields = set(output.get("required_fields", [])) if isinstance(output, dict) else set()
        missing_basics = sorted({"schema_version", "status"} - required_fields)
        if missing_basics:
            failures.append(
                Failure(
                    path,
                    f"{name} output contract is missing standard fields {missing_basics}.",
                    "Every resume-core result must include schema_version and status for deterministic callers.",
                )
            )
        expected = REQUIRED_OUTPUTS.get(str(name), set())
        missing_expected = sorted(expected - required_fields)
        if missing_expected:
            failures.append(
                Failure(
                    path,
                    f"{name} output contract is missing required truth-owner fields {missing_expected}.",
                    "Declare the structured result fields needed by contract tests, workflow, audit, and downstream packages.",
                )
            )
        if "must_not_include" not in output:
            failures.append(
                Failure(
                    path,
                    f"{name} does not declare forbidden output fields.",
                    "Add output_contract.must_not_include so persistence, rendering, workflow writes, and ungrounded authority remain blocked.",
                )
            )
    return failures


def iter_code_files(root: Path) -> Iterable[Path]:
    package_root = root / "resume-core"
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
                            "Keep resume-core deterministic and data-only: callers pass parsed resume/job inputs and career fact DTOs; core returns validation, scoring, selection, and mutation results.",
                            getattr(node, "lineno", None),
                        )
                    )
    return failures


def is_unapproved_public_core_name(name: str) -> bool:
    return name.startswith(PUBLIC_FUNCTION_PREFIXES) and name not in ALLOWED_SURFACES and not name.startswith("_")


def literal_string_items(node: ast.AST) -> list[str]:
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return []
    return [item.value for item in node.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)]


def scan_python_public_api(path: Path, text: str) -> list[Failure]:
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return [
            Failure(
                path,
                f"Python source cannot be parsed: {exc.msg}.",
                "Fix syntax before boundary guardrails can classify public API definitions.",
                exc.lineno,
            )
        ]

    failures: list[Failure] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if is_unapproved_public_core_name(node.name):
                failures.append(
                    Failure(
                        path,
                        f"Potential public resume-core function '{node.name}' is not in resume-core/TEST_SPEC.md.",
                        "Keep public API to core_surface.json functions; make helpers private or update TEST_SPEC.md and the manifest first.",
                        node.lineno,
                    )
                )
        elif isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
                for exported_name in literal_string_items(node.value):
                    if is_unapproved_public_core_name(exported_name):
                        failures.append(
                            Failure(
                                path,
                                f"Exported resume-core name '{exported_name}' is not in resume-core/TEST_SPEC.md.",
                                "Keep exported API to core_surface.json functions/types; make helpers private or update TEST_SPEC.md and the manifest first.",
                                node.lineno,
                            )
                        )
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__" and node.value:
                for exported_name in literal_string_items(node.value):
                    if is_unapproved_public_core_name(exported_name):
                        failures.append(
                            Failure(
                                path,
                                f"Exported resume-core name '{exported_name}' is not in resume-core/TEST_SPEC.md.",
                                "Keep exported API to core_surface.json functions/types; make helpers private or update TEST_SPEC.md and the manifest first.",
                                node.lineno,
                            )
                        )
    return failures


def scan_text_public_api(path: Path, text: str) -> list[Failure]:
    failures: list[Failure] = []
    for match in re.finditer(r"\b(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\b", text):
        function_name = match.group(1)
        if is_unapproved_public_core_name(function_name):
            failures.append(
                Failure(
                    path,
                    f"Potential public resume-core function '{function_name}' is not in resume-core/TEST_SPEC.md.",
                    "Keep public API to core_surface.json functions; make helpers private or update TEST_SPEC.md and the manifest first.",
                    line_for_offset(text, match.start()),
                )
            )
    for match in re.finditer(r"\bexport\s*\{([^}]+)\}", text):
        for exported_name in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", match.group(1)):
            if is_unapproved_public_core_name(exported_name):
                failures.append(
                    Failure(
                        path,
                        f"Exported resume-core name '{exported_name}' is not in resume-core/TEST_SPEC.md.",
                        "Keep exported API to core_surface.json functions/types; make helpers private or update TEST_SPEC.md and the manifest first.",
                        line_for_offset(text, match.start()),
                    )
                )
    return failures


def scan_text(path: Path, text: str) -> list[Failure]:
    failures: list[Failure] = []
    lowered = text.lower()

    for banned, message in FORBIDDEN_IMPORTS.items():
        if "-" in banned and banned in lowered:
            failures.append(
                Failure(
                    path,
                    f"Forbidden dependency reference '{banned}'. {message}",
                    "Remove the dependency and route behavior through the owning package boundary.",
                    line_for_offset(lowered, lowered.index(banned)),
                )
            )

    for term, message in FORBIDDEN_TERMS.items():
        pattern = re.compile(rf"(?<![a-z0-9_.-]){re.escape(term)}(?![a-z0-9_.-])", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            failures.append(
                Failure(
                    path,
                    f"Forbidden non-core ownership term '{term}' appears in resume-core code. {message}",
                    "Return deterministic domain outputs and leave adapter, workflow, rendering, prompting, and persistence side effects to their owners.",
                    line_for_offset(text, match.start()),
                )
            )

    for pattern in FILE_IO_PATTERNS:
        match = re.search(pattern, text)
        if match:
            failures.append(
                Failure(
                    path,
                    "File IO appears in resume-core source.",
                    "Keep resume-core APIs pure over supplied data. File ingest/export belongs to adapters, CLI, workflow, or renderer.",
                    line_for_offset(text, match.start()),
                )
            )

    if re.search(r"\b(select|insert|update|delete|create|drop|alter)\s+[^;\n]*(from|into|table|facts|evidence|resume_)\b", text, re.IGNORECASE):
        match = re.search(r"\b(select|insert|update|delete|create|drop|alter)\b", text, re.IGNORECASE)
        failures.append(
            Failure(
                path,
                "Raw SQL-like statement appears in resume-core code.",
                "Move career persistence/query behavior into career-store and pass stable DTOs into resume-core.",
                line_for_offset(text, match.start()) if match else None,
            )
        )

    if re.search(r"resume/(base|working)\.json", text) and re.search(r"(write_text|open\(|fs\.write|writeFile|unlink|rename|replace)", text):
        failures.append(
            Failure(
                path,
                "resume-core appears to write resume/base.json or resume/working.json.",
                "Core may return validated resume DTOs. Workspace artifact writes belong to workflow/CLI.",
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
            failures.extend(scan_python_architecture("resume-core", path, text))
            failures.extend(scan_python_public_api(path, text))
        else:
            failures.extend(scan_text_public_api(path, text))
        failures.extend(scan_text(path, text))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    failures = run(root)
    if failures:
        print("resume-core guardrails failed.\n")
        print("resume-core owns deterministic domain truth only.")
        print("Adapters, persistence, rendering, prompting, file IO, LLM calls, and workflow state transitions are hard-blocked.\n")
        for failure in failures:
            print(failure.format(root))
        return 1

    print("resume-core guardrails passed: domain surface, truth ownership, and forbidden dependency paths are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
