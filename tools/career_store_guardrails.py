#!/usr/bin/env python3
"""Hard-blocking guardrails for the career-store truth boundary."""

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
    "searchFacts",
    "getFact",
    "upsertFact",
    "verifyFact",
    "addEvidence",
    "addRelationship",
    "findCandidateMatches",
    "recordJobMatch",
    "findConflicts",
}

REQUIRED_TYPES = {
    "CareerFact",
    "Evidence",
    "FactRelationship",
    "VerificationState",
    "ConflictRecord",
    "JobAssociation",
    "TransactionResult",
    "MigrationState",
}

REQUIRED_VERIFICATION_STATES = {
    "source_stated",
    "user_verified",
    "inferred",
    "unknown",
    "explicitly_missing",
    "conflicted",
}

REQUIRED_RELATIONSHIP_TYPES = {"alias", "equivalent", "related", "contradicts"}

REQUIRED_RESOLUTION_STATES = {
    "exact_match",
    "alias_match",
    "verified_fact_match",
    "related_match",
    "possible_match",
    "unknown",
    "explicitly_missing",
    "conflicted",
}

MUTATING_SURFACES = {"upsertFact", "verifyFact", "addEvidence", "addRelationship", "recordJobMatch"}

FORBIDDEN_PUBLIC_API = {
    "executeSql",
    "runQuery",
    "rawQuery",
    "queryDatabase",
    "truncateTable",
    "deleteEvidence",
    "askUser",
    "renderResume",
}

FORBIDDEN_IMPORTS = {
    "career_mcp": "career-store must not import MCP adapter code. Adapters call store services, not the reverse.",
    "career-mcp": "career-store must not import MCP adapter code. Adapters call store services, not the reverse.",
    "resume_agent": "career-store must not call agent runtimes or proposal code.",
    "resume-agent": "career-store must not call agent runtimes or proposal code.",
    "resume_cli": "career-store must not import CLI orchestration or workspace behavior.",
    "resume-cli": "career-store must not import CLI orchestration or workspace behavior.",
    "resume_plugin": "career-store must not import plugin presentation or host adapter code.",
    "resume-plugin": "career-store must not import plugin presentation or host adapter code.",
    "resume_render": "career-store must not render output or depend on renderer behavior.",
    "resume-render": "career-store must not render output or depend on renderer behavior.",
    "openai": "career-store must not call LLMs. Agent/language behavior must arrive as proposals for validation.",
    "anthropic": "career-store must not call LLMs. Agent/language behavior must arrive as proposals for validation.",
    "langchain": "career-store must not call LLM chains. Agent/language behavior must arrive as proposals for validation.",
    "typer": "career-store must not own terminal UI.",
    "click": "career-store must not own terminal UI.",
    "rich": "career-store must not own terminal UI.",
    "prompt_toolkit": "career-store must not ask terminal prompts.",
}

QUESTION_PATTERNS = {
    r"\binput\s*\(": "career-store must not ask natural-language questions or read terminal input.",
    r"\bask[_A-Za-z0-9]*\s*\(": "Question generation belongs to agent/workflow; store records facts and confirmations.",
    r"\bprompt[_A-Za-z0-9]*\s*\(": "Prompting belongs to adapters/workflow; store APIs accept explicit data.",
    r"generateClarificationQuestion": "Clarification question generation belongs to resume-agent.",
}

CODE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
IGNORED_DIRS = {"__pycache__", ".pytest_cache", "node_modules", ".venv", "venv", "dist", "build"}
PUBLIC_FUNCTION_PREFIXES = ("search", "get", "upsert", "verify", "add", "find", "record")
RAW_API_PATTERN = re.compile(r"(sql|query|truncate|deleteEvidence|askUser|renderResume)", re.IGNORECASE)


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
    path = root / "career-store" / "store_surface.json"
    if not path.exists():
        return {}, [
            Failure(
                path,
                "Missing machine-readable career-store surface contract.",
                "Restore career-store/store_surface.json and update it before changing public persistence behavior.",
            )
        ]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return {}, [
            Failure(
                path,
                f"Invalid JSON: {exc.msg}.",
                "Fix the JSON so contract tests and guardrails can compare the declared store surface to implementation.",
                exc.lineno,
            )
        ]


def validate_surface(root: Path, surface: dict) -> list[Failure]:
    path = root / "career-store" / "store_surface.json"
    failures: list[Failure] = []
    public_api = surface.get("public_api", {})
    functions = set(public_api.get("functions", []))
    if functions != ALLOWED_SURFACES:
        failures.append(
            Failure(
                path,
                f"Declared public functions differ from career-store/TEST_SPEC.md. Missing={sorted(ALLOWED_SURFACES - functions)}; extra={sorted(functions - ALLOWED_SURFACES)}.",
                "Expose exactly the career-store service functions from career-store/TEST_SPEC.md. Document contract changes before changing this manifest.",
            )
        )
    types = set(public_api.get("types", []))
    if types != REQUIRED_TYPES:
        failures.append(
            Failure(
                path,
                f"Declared public types differ from career-store/TEST_SPEC.md. Missing={sorted(REQUIRED_TYPES - types)}; extra={sorted(types - REQUIRED_TYPES)}.",
                "Keep the durable store DTO/type surface aligned with the test spec.",
            )
        )
    if set(surface.get("verification_states", [])) != REQUIRED_VERIFICATION_STATES:
        failures.append(
            Failure(
                path,
                "Verification states are misaligned with career-store/TEST_SPEC.md.",
                "Keep source_stated, user_verified, inferred, unknown, explicitly_missing, and conflicted states distinct.",
            )
        )
    if set(surface.get("relationship_types", [])) != REQUIRED_RELATIONSHIP_TYPES:
        failures.append(
            Failure(
                path,
                "Relationship types are misaligned with career-store/TEST_SPEC.md.",
                "Keep alias/equivalent distinct from related and contradiction relationships.",
            )
        )
    if set(surface.get("resolution_states", [])) != REQUIRED_RESOLUTION_STATES:
        failures.append(
            Failure(
                path,
                "Resolution states are misaligned with career-store/TEST_SPEC.md.",
                "Keep exact, alias, verified, related, possible, unknown, missing, and conflicted outcomes distinct.",
            )
        )
    forbidden = set(surface.get("forbidden_public_api", []))
    if not FORBIDDEN_PUBLIC_API <= forbidden:
        failures.append(
            Failure(
                path,
                f"Forbidden public API declarations are incomplete. Missing={sorted(FORBIDDEN_PUBLIC_API - forbidden)}.",
                "Declare raw SQL, destructive, prompting, and rendering APIs as forbidden so adapter surfaces cannot grow around them.",
            )
        )

    surfaces = surface.get("surfaces")
    if not isinstance(surfaces, list):
        return [
            Failure(
                path,
                "store_surface.json must define a top-level surfaces array.",
                "Declare one surface entry per public store function.",
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
        missing_basics = sorted({"schema_version", "status", "audit"} - required_fields)
        if missing_basics:
            failures.append(
                Failure(
                    path,
                    f"{name} output contract is missing standard fields {missing_basics}.",
                    "Every career-store result must include schema_version, status, and audit metadata.",
                )
            )
        if name in MUTATING_SURFACES:
            missing_mutation = sorted({"mutation_status"} - required_fields)
            if missing_mutation:
                failures.append(
                    Failure(
                        path,
                        f"{name} mutation output is missing {missing_mutation}.",
                        "Mutating store APIs must report mutation status for idempotency, retry, and audit reconstruction.",
                    )
                )
        if "must_not_include" not in output:
            failures.append(
                Failure(
                    path,
                    f"{name} does not declare forbidden output fields.",
                    "Add output_contract.must_not_include so raw SQL, connections, resume patches, and silent promotions stay blocked.",
                )
            )
    return failures


def iter_code_files(root: Path) -> Iterable[Path]:
    package_root = root / "career-store"
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
                            "Keep career-store limited to durable facts/evidence/relationships/conflicts/migrations/transactions and expose semantic service APIs to adapters.",
                            getattr(node, "lineno", None),
                        )
                    )
    return failures


def literal_string_items(node: ast.AST) -> list[str]:
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return []
    return [item.value for item in node.elts if isinstance(item, ast.Constant) and isinstance(item.value, str)]


def is_forbidden_store_public_api_name(name: str) -> bool:
    return name in FORBIDDEN_PUBLIC_API or (RAW_API_PATTERN.search(name) and not name.startswith("_"))


def is_unapproved_public_store_name(name: str) -> bool:
    return name.startswith(PUBLIC_FUNCTION_PREFIXES) and name not in ALLOWED_SURFACES and not name.startswith("_")


def store_public_api_failure(path: Path, name: str, line: int | None) -> Failure | None:
    if is_forbidden_store_public_api_name(name):
        return Failure(
            path,
            f"Forbidden raw/destructive/prompt/render public API '{name}' appears in career-store source.",
            "Expose semantic store APIs only. Raw SQL execution, destructive evidence deletion, prompting, and rendering are not public store surfaces.",
            line,
        )
    if is_unapproved_public_store_name(name):
        return Failure(
            path,
            f"Potential public career-store function '{name}' is not in career-store/TEST_SPEC.md.",
            "Keep public API to store_surface.json functions; make helpers private or update TEST_SPEC.md and the manifest first.",
            line,
        )
    return None


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
            failure = store_public_api_failure(path, node.name, node.lineno)
            if failure:
                failures.append(failure)
        elif isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
                for exported_name in literal_string_items(node.value):
                    failure = store_public_api_failure(path, exported_name, node.lineno)
                    if failure:
                        failures.append(failure)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__" and node.value:
                for exported_name in literal_string_items(node.value):
                    failure = store_public_api_failure(path, exported_name, node.lineno)
                    if failure:
                        failures.append(failure)
    return failures


def scan_text_public_api(path: Path, text: str) -> list[Failure]:
    failures: list[Failure] = []
    for match in re.finditer(r"\b(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)\b", text):
        failure = store_public_api_failure(path, match.group(1), line_for_offset(text, match.start()))
        if failure:
            failures.append(failure)
    for match in re.finditer(r"\bexport\s*\{([^}]+)\}", text):
        for exported_name in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", match.group(1)):
            failure = store_public_api_failure(path, exported_name, line_for_offset(text, match.start()))
            if failure:
                failures.append(failure)
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

    for pattern, message in QUESTION_PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            failures.append(
                Failure(
                    path,
                    "Natural-language questioning or prompting appears in career-store source.",
                    message,
                    line_for_offset(text, match.start()),
                )
            )

    if re.search(r"resume/(base|working)\.json", text) and re.search(r"(write_text|open\(|fs\.write|writeFile|unlink|rename|replace|jsonpatch|patch)", text, re.IGNORECASE):
        failures.append(
            Failure(
                path,
                "career-store appears to change resume/base.json or resume/working.json.",
                "Store may persist career facts and job associations only. Resume mutation belongs to resume-core/workflow/CLI.",
            )
        )

    if re.search(r"\b(renderMarkdown|renderDocx|renderPdf|renderResume)\b", text):
        match = re.search(r"\b(renderMarkdown|renderDocx|renderPdf|renderResume)\b", text)
        failures.append(
            Failure(
                path,
                "Rendering behavior appears in career-store source.",
                "Return fact/evidence DTOs. Rendering belongs to resume-render.",
                line_for_offset(text, match.start()) if match else None,
            )
        )

    promotion = re.search(r"\binferred\b[\s\S]{0,160}\buser_verified\b|\buser_verified\b[\s\S]{0,160}\binferred\b", text, re.IGNORECASE)
    if promotion:
        window = text[max(0, promotion.start() - 160) : promotion.end() + 160].lower()
        if "confirmation" not in window and "explicit" not in window:
            failures.append(
                Failure(
                    path,
                    "Potential silent inferred-to-user_verified promotion appears in career-store source.",
                    "Require explicit confirmation and audit metadata before user_verified can be set from inferred/unknown information.",
                    line_for_offset(text, promotion.start()),
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
        print("career-store guardrails failed.\n")
        print("career-store owns durable career truth only.")
        print("Adapter imports, raw SQL public APIs, prompting, rendering, resume mutation, LLM calls, and silent verification promotion are hard-blocked.\n")
        for failure in failures:
            print(failure.format(root))
        return 1

    print("career-store guardrails passed: store surface, durable truth ownership, and forbidden behavior paths are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
