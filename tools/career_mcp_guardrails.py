#!/usr/bin/env python3
"""Hard-blocking guardrails for the career-mcp contract surface."""

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


ALLOWED_TOOLS = {
    "career.search_facts",
    "career.get_fact",
    "career.propose_fact",
    "career.add_evidence",
    "career.verify_fact",
    "career.add_relationship",
    "career.find_matches",
    "career.get_unverified",
}

FORBIDDEN_TOOL_NAMES = {
    "execute_sql",
    "run_query",
    "truncate",
    "truncate_table",
    "raw_update",
    "raw_delete",
}

FORBIDDEN_IMPORTS = {
    "sqlite3": "career-mcp must call the injected career-store service. Move direct SQLite access into career-store.",
    "aiosqlite": "career-mcp must not open SQLite connections. Add a career-store service method and call that instead.",
    "sqlalchemy": "career-mcp must not use ORM/session primitives. Persistence belongs in career-store.",
    "knex": "career-mcp must not construct database queries. Persistence belongs in career-store.",
    "better-sqlite3": "career-mcp must not open SQLite connections. Add a career-store service method and call that instead.",
    "resume_cli": "career-mcp is an adapter layer, not workflow orchestration. Move CLI behavior into resume-cli.",
    "resume-cli": "career-mcp is an adapter layer, not workflow orchestration. Move CLI behavior into resume-cli.",
    "resume_plugin": "career-mcp must not import plugin presentation or host code. Return normalized DTOs instead.",
    "resume-plugin": "career-mcp must not import plugin presentation or host code. Return normalized DTOs instead.",
    "resume_render": "career-mcp must not render or mutate resume output. Keep rendering in resume-render.",
    "resume-render": "career-mcp must not render or mutate resume output. Keep rendering in resume-render.",
    "resume_agent": "career-mcp exposes safe tools to agents but must not depend on agent runtime behavior.",
    "resume-agent": "career-mcp exposes safe tools to agents but must not depend on agent runtime behavior.",
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


def load_surface(root: Path) -> tuple[dict, list[Failure]]:
    path = root / "career-mcp" / "career_mcp" / "tool_surface.json"
    generated_path = root / "career-mcp" / "tool_surface.json"
    if not path.exists():
        return {}, [
            Failure(
                path,
                "Missing machine-readable MCP surface contract.",
                "Restore career-mcp/career_mcp/tool_surface.json and update it before changing exposed tools.",
            )
        ]
    try:
        failures: list[Failure] = []
        if generated_path.exists() and generated_path.read_bytes() != path.read_bytes():
            failures.append(
                Failure(
                    generated_path,
                    "Generated MCP surface copy is not byte-identical to the canonical package manifest.",
                    "Run career-mcp/tools/sync_tool_surface.py to regenerate career-mcp/tool_surface.json from the package manifest.",
                )
            )
        return json.loads(path.read_text(encoding="utf-8")), failures
    except json.JSONDecodeError as exc:
        return {}, [
            Failure(
                path,
                f"Invalid JSON: {exc.msg}.",
                "Fix the JSON so tests and guardrails can compare the declared surface to implementation.",
                exc.lineno,
            )
        ]


def validate_surface(root: Path, surface: dict) -> list[Failure]:
    path = root / "career-mcp" / "career_mcp" / "tool_surface.json"
    failures: list[Failure] = []
    tools = surface.get("tools")
    if not isinstance(tools, list):
        return [
            Failure(
                path,
                "tool_surface.json must define a top-level tools array.",
                "Declare the complete allowed career.* tool list in the tools array.",
            )
        ]

    names = [tool.get("name") for tool in tools if isinstance(tool, dict)]
    if set(names) != ALLOWED_TOOLS:
        missing = sorted(ALLOWED_TOOLS - set(names))
        extra = sorted(set(names) - ALLOWED_TOOLS)
        failures.append(
            Failure(
                path,
                f"Declared tool set differs from career-mcp/TEST_SPEC.md. Missing={missing}; extra={extra}.",
                "Expose exactly the eight allowed career.* tools. Contract changes must be documented in TEST_SPEC.md first.",
            )
        )

    forbidden_declared = sorted(set(names) & FORBIDDEN_TOOL_NAMES)
    if forbidden_declared:
        failures.append(
            Failure(
                path,
                f"Forbidden unrestricted database tools are declared: {forbidden_declared}.",
                "Remove raw database tools. Add a narrow career-store service method and expose a semantic career.* tool if needed.",
            )
        )

    for index, tool in enumerate(tools):
        if not isinstance(tool, dict):
            failures.append(
                Failure(
                    path,
                    f"Tool entry #{index} is not an object.",
                    "Use an object with name, description, input_schema, and response_contract.",
                )
            )
            continue
        name = tool.get("name", f"<tool #{index}>")
        description = str(tool.get("description", ""))
        lowered_description = description.lower()
        if "sql" in lowered_description or "database modification" in lowered_description:
            failures.append(
                Failure(
                    path,
                    f"{name} description mentions SQL or direct database modification.",
                    "Describe the semantic career-store operation and do not encourage raw persistence access.",
                )
            )
        schema = tool.get("input_schema")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            failures.append(
                Failure(
                    path,
                    f"{name} must define an object input_schema.",
                    "Add a JSON-schema-like object schema with required fields and properties.",
                )
            )
        response = tool.get("response_contract")
        if not isinstance(response, dict) or not response.get("required_fields"):
            failures.append(
                Failure(
                    path,
                    f"{name} must define required response fields.",
                    "Add response_contract.required_fields so adapters normalize outputs deterministically.",
                )
            )
        if tool.get("mutates") is True:
            response_fields = set(response.get("required_fields", [])) if isinstance(response, dict) else set()
            required = {"mutation_status", "fact_id", "verification_state", "conflicts", "confirmation_required", "audit"}
            missing = sorted(required - response_fields)
            if missing:
                failures.append(
                    Failure(
                        path,
                        f"{name} is a write tool but does not require {missing}.",
                        "Every write tool must return mutation status, fact ID, verification state, conflicts, confirmation-needed state, and audit metadata.",
                    )
                )
            text = f"{description} {json.dumps(response, sort_keys=True)}".lower()
            if "confirmation" not in text or "verification" not in text:
                failures.append(
                    Failure(
                        path,
                        f"{name} write contract does not disclose confirmation and verification behavior.",
                        "Document that agent-originated writes are proposals until career-store validation and explicit confirmation allow stronger verification.",
                    )
                )
    return failures


def iter_code_files(root: Path) -> Iterable[Path]:
    career_root = root / "career-mcp"
    if not career_root.exists():
        return
    for path in career_root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in CODE_SUFFIXES:
            yield path


def dotted_import_root(name: str) -> str:
    return name.split(".", 1)[0]


def scan_python_imports(root: Path, path: Path, text: str) -> list[Failure]:
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
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for imported in names:
            root_name = dotted_import_root(imported)
            for banned, message in FORBIDDEN_IMPORTS.items():
                banned_root = dotted_import_root(banned.replace("-", "_"))
                if root_name == banned_root or imported == banned:
                    failures.append(
                        Failure(
                            path,
                            f"Forbidden import '{imported}'. {message}",
                            "Keep career-mcp limited to its own adapter code, the injected career-store service interface, and public resume-core contracts.",
                            getattr(node, "lineno", None),
                        )
                    )
    return failures


def scan_text(root: Path, path: Path, text: str) -> list[Failure]:
    failures: list[Failure] = []
    lowered = text.lower()

    for tool_name in FORBIDDEN_TOOL_NAMES:
        pattern = re.compile(rf"(?<![a-z0-9_.-]){re.escape(tool_name)}(?![a-z0-9_.-])", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            failures.append(
                Failure(
                    path,
                    f"Forbidden raw/unrestricted tool or operation '{tool_name}' appears in career-mcp code.",
                    "Replace it with a narrow career.* semantic tool backed by a career-store service method.",
                    line_for_offset(text, match.start()),
                )
            )

    for match in re.finditer(r"career\.[a-z_]+", text):
        found = match.group(0)
        if found not in ALLOWED_TOOLS:
            failures.append(
                Failure(
                    path,
                    f"Undeclared MCP tool '{found}' appears in code.",
                    "Use one of the eight allowed tools or update TEST_SPEC.md and tool_surface.json before implementing a new surface.",
                    line_for_offset(text, match.start()),
                )
            )

    for banned, message in FORBIDDEN_IMPORTS.items():
        if "-" in banned and banned in lowered:
            failures.append(
                Failure(
                    path,
                    f"Forbidden dependency reference '{banned}'. {message}",
                    "Remove the dependency and route behavior through the package that owns it.",
                    line_for_offset(lowered, lowered.index(banned)),
                )
            )

    raw_sql = re.search(r"\b(select|insert|update|delete|create|drop|alter)\s+[^;\n]*(from|into|table|career_|facts|evidence)\b", text, re.IGNORECASE)
    if raw_sql:
        failures.append(
            Failure(
                path,
                "Raw SQL-like statement appears in career-mcp code.",
                "Move persistence/query logic into career-store and call an injected service method from the MCP adapter.",
                line_for_offset(text, raw_sql.start()),
            )
        )

    if re.search(r"resume/(base|working)\.json", text) and re.search(r"(write_text|open\(|fs\.write|writeFile|unlink|rename|replace)", text):
        failures.append(
            Failure(
                path,
                "career-mcp appears to write resume/base.json or resume/working.json.",
                "Resume mutation belongs to resume-core/workflow/CLI. MCP should return career knowledge DTOs only.",
            )
        )

    scoring_terms = ["official_score", "overall_score", "matchresult", "match_result", "assign_score"]
    for term in scoring_terms:
        if term in lowered:
            failures.append(
                Failure(
                    path,
                    f"Scoring ownership term '{term}' appears in career-mcp code.",
                    "career.find_matches may return resolution classifications, but official scoring belongs to resume-core.",
                    line_for_offset(lowered, lowered.index(term)),
                )
            )
    return failures


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def run(root: Path) -> list[Failure]:
    surface, surface_failures = load_surface(root)
    failures = list(surface_failures)
    if surface:
        failures.extend(validate_surface(root, surface))

    for path in iter_code_files(root):
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            failures.extend(scan_python_imports(root, path, text))
            failures.extend(scan_python_architecture("career-mcp", path, text))
        failures.extend(scan_text(root, path, text))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    failures = run(root)
    if failures:
        print("career-mcp guardrails failed.\n")
        print("The MCP package is allowed to expose only narrow semantic tools over career-store.")
        print("Raw SQL, unrestricted mutation, scoring, resume mutation, and presentation imports are hard-blocked.\n")
        for failure in failures:
            print(failure.format(root))
        return 1

    print("career-mcp guardrails passed: tool surface, module boundaries, API scope, and forbidden operations are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
