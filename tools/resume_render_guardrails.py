#!/usr/bin/env python3
"""Hard-blocking guardrails for the resume-render semantic neutrality boundary."""

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
    "renderMarkdown",
    "renderDocx",
    "renderPdf",
    "measureLayout",
    "validateRenderedOutput",
}

FORBIDDEN_IMPORTS = {
    "career_store": "resume-render must not query career knowledge. Pass validated resume DTOs into the renderer.",
    "career-store": "resume-render must not query career knowledge. Pass validated resume DTOs into the renderer.",
    "career_mcp": "resume-render must not call MCP tools. Career lookup belongs upstream.",
    "career-mcp": "resume-render must not call MCP tools. Career lookup belongs upstream.",
    "resume_agent": "resume-render must not ask the agent to rewrite content. Return layout constraints to orchestration instead.",
    "resume-agent": "resume-render must not ask the agent to rewrite content. Return layout constraints to orchestration instead.",
    "resume_cli": "resume-render must not orchestrate workspace artifacts or commands.",
    "resume-cli": "resume-render must not orchestrate workspace artifacts or commands.",
    "resume_plugin": "resume-render must not import plugin presentation or host adapter code.",
    "resume-plugin": "resume-render must not import plugin presentation or host adapter code.",
    "sqlite3": "resume-render must not read or write SQLite. Career persistence belongs to career-store.",
    "aiosqlite": "resume-render must not read or write SQLite. Career persistence belongs to career-store.",
    "sqlalchemy": "resume-render must not own persistence sessions or database models.",
}

FORBIDDEN_TERMS = {
    "official_score": "Official match scoring belongs to resume-core. Renderer may not compute or return scores.",
    "overall_score": "Overall score belongs to resume-core. Renderer may not compute or return scores.",
    "matchresult": "MatchResult is a resume-core authority surface, not renderer output.",
    "match_result": "MatchResult is a resume-core authority surface, not renderer output.",
    "resumechangeoperation": "Applying or owning ResumeChangeOperation belongs to resume-core/workflow.",
    "resume_change_operation": "Applying or owning ResumeChangeOperation belongs to resume-core/workflow.",
    "apply_change": "Renderer must not apply semantic resume changes.",
    "apply_changes": "Renderer must not apply semantic resume changes.",
    "rewrite_bullet": "Renderer must not semantically rewrite bullets.",
    "rewriteBullet": "Renderer must not semantically rewrite bullets.",
    "select_relevance": "Relevance selection belongs to resume-core/workflow, not renderer.",
    "selectRelevant": "Relevance selection belongs to resume-core/workflow, not renderer.",
    "add_skill": "Renderer must not add skills. Missing skills require validated resume changes upstream.",
    "addSkill": "Renderer must not add skills. Missing skills require validated resume changes upstream.",
}

INFLATION_PATTERNS = {
    "20 million users": "Renderer must not add unsupported user-scale claims.",
    "30 engineers": "Renderer must not add unsupported management-scope claims.",
    "staff software engineer": "Renderer must not inflate employment titles.",
    "staff engineer": "Renderer must not add Staff title employment history.",
    "aws": "Renderer must not add missing skills. AWS must already exist in canonical input to appear in output.",
    "graphql": "Renderer must not add missing skills. GraphQL must already exist in canonical input to appear in output.",
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
    path = root / "resume-render" / "render_surface.json"
    if not path.exists():
        return {}, [
            Failure(
                path,
                "Missing machine-readable render surface contract.",
                "Restore resume-render/render_surface.json and update it before changing public renderer APIs.",
            )
        ]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return {}, [
            Failure(
                path,
                f"Invalid JSON: {exc.msg}.",
                "Fix the JSON so contract tests and guardrails can compare the declared renderer surface to implementation.",
                exc.lineno,
            )
        ]


def validate_surface(root: Path, surface: dict) -> list[Failure]:
    path = root / "resume-render" / "render_surface.json"
    failures: list[Failure] = []
    functions = set(surface.get("public_api", {}).get("functions", []))
    if functions != ALLOWED_SURFACES:
        failures.append(
            Failure(
                path,
                f"Declared public functions differ from resume-render/TEST_SPEC.md. Missing={sorted(ALLOWED_SURFACES - functions)}; extra={sorted(functions - ALLOWED_SURFACES)}.",
                "Expose exactly renderMarkdown, renderDocx, renderPdf, measureLayout, and validateRenderedOutput.",
            )
        )

    surfaces = surface.get("surfaces")
    if not isinstance(surfaces, list):
        return [
            Failure(
                path,
                "render_surface.json must define a top-level surfaces array.",
                "Declare one surface entry per renderer public function.",
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
        if name.startswith("render"):
            missing = sorted({"status", "format", "template_version", "semantic_fingerprint", "warnings"} - required_fields)
            if missing:
                failures.append(
                    Failure(
                        path,
                        f"{name} output contract is missing render result fields {missing}.",
                        "Render results must include status, format, template version, semantic fingerprint, and warnings.",
                    )
                )
        if name == "measureLayout":
            missing = sorted({"status", "estimated_pages", "target_pages", "required_reduction", "constraints", "warnings"} - required_fields)
            if missing:
                failures.append(
                    Failure(
                        path,
                        f"measureLayout output contract is missing layout fields {missing}.",
                        "Layout reports must include overflow constraints rather than silently shortening content.",
                    )
                )
        if name == "validateRenderedOutput":
            missing = sorted({"status", "text_extracted", "missing_sections", "unsupported_characters", "semantic_differences", "warnings"} - required_fields)
            if missing:
                failures.append(
                    Failure(
                        path,
                        f"validateRenderedOutput output contract is missing validation fields {missing}.",
                        "Rendered output validation must expose parse-back and ATS/semantic-loss findings.",
                    )
                )
    return failures


def iter_code_files(root: Path) -> Iterable[Path]:
    package_root = root / "resume-render"
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
                            "Keep resume-render limited to templates, formatting, layout, and render validation. Send career lookup, scoring, rewrite, and workflow decisions upstream.",
                            getattr(node, "lineno", None),
                        )
                    )
    return failures


def scan_text(path: Path, text: str) -> list[Failure]:
    failures: list[Failure] = []
    lowered = text.lower()

    for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", text):
        function_name = match.group(1)
        if function_name.startswith("render") or function_name.startswith("measure") or function_name.startswith("validate"):
            if function_name not in ALLOWED_SURFACES and not function_name.startswith("_"):
                failures.append(
                    Failure(
                        path,
                        f"Potential public renderer function '{function_name}' is not in resume-render/TEST_SPEC.md.",
                        "Keep public API to renderMarkdown, renderDocx, renderPdf, measureLayout, and validateRenderedOutput; make helpers private.",
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
                    f"Forbidden renderer authority term '{term}' appears in code. {message}",
                    "Return rendered output, layout constraints, or validation findings; route semantic changes through resume-core/workflow.",
                    line_for_offset(text, match.start()),
                )
            )

    for phrase, message in INFLATION_PATTERNS.items():
        index = lowered.find(phrase)
        if index != -1:
            failures.append(
                Failure(
                    path,
                    f"Blocked unsupported renderer addition phrase '{phrase}'. {message}",
                    "Renderer output must be a projection of canonical input only. Add or reject content upstream before rendering.",
                    line_for_offset(lowered, index),
                )
            )

    sql = re.search(r"\b(select|insert|update|delete|create|drop|alter)\s+[^;\n]*(from|into|table|facts|evidence|resume_)\b", text, re.IGNORECASE)
    if sql:
        failures.append(
            Failure(
                path,
                "Raw SQL-like statement appears in resume-render code.",
                "Move career persistence/query behavior into career-store and pass validated resume DTOs into the renderer.",
                line_for_offset(text, sql.start()),
            )
        )

    if re.search(r"resume/(base|working)\.json", text) and re.search(r"(write_text|open\(|fs\.write|writeFile|unlink|rename|replace)", text):
        failures.append(
            Failure(
                path,
                "resume-render appears to write resume/base.json or resume/working.json.",
                "Renderer may create output artifacts only. Canonical resume files are workflow/CLI artifacts.",
            )
        )

    truncation = re.search(r"\.(slice|substring|substr)\s*\([^)]*(max|limit|chars|length)", text, re.IGNORECASE)
    if truncation and not re.search(r"overflow|required_reduction|constraints", text, re.IGNORECASE):
        failures.append(
            Failure(
                path,
                "Potential silent content truncation found without overflow constraint reporting.",
                "Report layout overflow with target pages, estimated pages, and required reduction instead of shortening semantic content inside renderer.",
                line_for_offset(text, truncation.start()),
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
        print("resume-render guardrails failed.\n")
        print("The renderer package may format, export, measure, and validate only.")
        print("Career lookup, scoring, semantic rewrite, resume mutation, and silent truncation are hard-blocked.\n")
        for failure in failures:
            print(failure.format(root))
        return 1

    print("resume-render guardrails passed: render API, semantic neutrality, and forbidden ownership paths are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
