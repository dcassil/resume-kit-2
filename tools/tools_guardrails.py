#!/usr/bin/env python3
"""Hard-blocking guardrails for local validation/release tools."""

from __future__ import annotations

import argparse
import ast
import io
import json
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path


REQUIRED_CAPABILITIES = {
    "test_runner_wrappers",
    "fixture_validators",
    "snapshot_review_helpers",
    "architecture_import_checkers",
    "migration_checkers",
    "release_checks",
}

RELEASE_BLOCKING_EXPECTATIONS = {
    "build_package_import_success",
    "pr_gate_tests",
    "full_smoke_test",
    "hallucination_rejection",
    "base_immutability",
    "deterministic_scoring",
    "render_validation",
    "audit_completeness",
    "full_e2e_for_release_candidate",
    "job_b_persistent_learning",
    "recovery_tests",
    "migration_upgrade_tests",
}

HIDDEN_PRODUCT_PATTERNS = {
    r"\bdef\s+(calculate|compute|score)_": "Tools must run package tests or call public package APIs; they must not implement scoring.",
    r"\b(class|def)\s+.*Migration": "Migration behavior belongs to career-store/tool-owned migration helpers, not ad hoc product logic.",
    r"\bCREATE\s+TABLE\b": "SQLite schema belongs to career-store migrations, not local validation tools.",
    r"\bINSERT\s+INTO\s+(facts|evidence|relationships)\b": "Tools must not write product tables directly.",
    r"\bdef\s+apply_(resume_)?change": "Resume mutation logic belongs to resume-core/workflow, not tools.",
    r"\bdef\s+rewrite_bullet": "Semantic rewrite logic belongs to agent proposals/core validation, not tools.",
    r"\bdef\s+validate_(resume_schema|job_schema|change_operation)": "Domain validation belongs to owning packages; tools may invoke validators, not reimplement them.",
}

WEAK_TOOL_PATTERNS = {
    r"except\s+Exception\s*:\s*pass": "Gate tools must surface failures with useful messages.",
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


def strip_string_literals(text: str) -> str:
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


def load_manifest(root: Path) -> tuple[dict, list[Failure]]:
    path = root / "tools" / "tool_manifest.json"
    if not path.exists():
        return {}, [Failure(path, "Missing tools manifest.", "Restore tools/tool_manifest.json so local utilities are documented and gateable.")]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return {}, [Failure(path, f"Invalid JSON: {exc.msg}.", "Fix JSON so tool contracts are machine-checkable.", exc.lineno)]


def capability_to_tool_kind(capability: str) -> str:
    if capability.endswith("ies"):
        return f"{capability[:-3]}y"
    if capability.endswith("s"):
        return capability[:-1]
    return capability


def validate_manifest(root: Path, manifest: dict) -> list[Failure]:
    path = root / "tools" / "tool_manifest.json"
    failures: list[Failure] = []
    if manifest.get("schema_version") != "tools.v1":
        failures.append(Failure(path, "schema_version must be tools.v1.", "Keep the tools manifest version stable until the tools contract changes."))

    capabilities = set(manifest.get("required_capabilities", []))
    if capabilities != REQUIRED_CAPABILITIES:
        failures.append(
            Failure(
                path,
                f"Required capabilities are misaligned. Missing={sorted(REQUIRED_CAPABILITIES - capabilities)}; extra={sorted(capabilities - REQUIRED_CAPABILITIES)}.",
                "Keep tools coverage aligned with tools/TEST_SPEC.md.",
            )
        )

    expectations = set(manifest.get("release_blocking_expectations", []))
    if expectations != RELEASE_BLOCKING_EXPECTATIONS:
        failures.append(
            Failure(
                path,
                f"Release-blocking expectations are misaligned. Missing={sorted(RELEASE_BLOCKING_EXPECTATIONS - expectations)}; extra={sorted(expectations - RELEASE_BLOCKING_EXPECTATIONS)}.",
                "Keep release checks aligned with tools/TEST_SPEC.md.",
            )
        )

    entries = manifest.get("tools")
    if not isinstance(entries, list):
        return [Failure(path, "tool_manifest.json must define a tools array.", "Declare one entry per primary local utility.")]

    tool_kinds = {entry.get("kind") for entry in entries if isinstance(entry, dict)}
    for capability in sorted(capabilities):
        expected_kind = capability_to_tool_kind(capability)
        if expected_kind not in tool_kinds:
            failures.append(
                Failure(
                    path,
                    f"Required capability '{capability}' has no implementing tool kind '{expected_kind}'.",
                    f"Add a tools[] entry with kind='{expected_kind}' or remove the orphaned required_capabilities entry '{capability}'.",
                )
            )

    documented_paths = {entry.get("path") for entry in entries if isinstance(entry, dict)}
    required_primary_tools = {
        str(tool.relative_to(root))
        for tool in (root / "tools").glob("*_guardrails.py")
        if not tool.name.startswith("watch_")
    }
    missing = required_primary_tools - documented_paths
    if missing:
        failures.append(
            Failure(
                path,
                f"Primary guardrail tools are undocumented: {sorted(missing)}.",
                "Add each primary guardrail tool to tools/tool_manifest.json with gate, read/write, and release-blocking metadata.",
            )
        )

    for entry in entries:
        if not isinstance(entry, dict):
            failures.append(Failure(path, "Tool manifest entry is not an object.", "Use an object with path, kind, supports_gate, invokes_surfaces, reads, writes, release_blocking, and description."))
            continue
        tool_path = root / entry.get("path", "")
        if not tool_path.exists():
            failures.append(Failure(tool_path, "Documented tool path does not exist.", "Create the tool or remove/update its manifest entry."))
        for field in ["kind", "supports_gate", "invokes_surfaces", "reads", "writes", "release_blocking", "description"]:
            if field not in entry:
                failures.append(Failure(path, f"Tool entry {entry.get('path')} is missing '{field}'.", "Every tool must document gate, surfaces, file access, blocking behavior, and purpose."))
        if entry.get("release_blocking") is not True:
            failures.append(Failure(path, f"Tool entry {entry.get('path')} must be release_blocking=true.", "Contract-enforcing tools must fail hard when they detect release blockers."))
    return failures


def scan_tools(root: Path) -> list[Failure]:
    failures: list[Failure] = []
    for path in (root / "tools").glob("*.py"):
        original = path.read_text(encoding="utf-8")
        text = strip_string_literals(original)
        for pattern, solution in HIDDEN_PRODUCT_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                failures.append(
                    Failure(
                        path,
                        "Tool file appears to implement hidden product behavior.",
                        solution,
                        line_for_offset(original, match.start()),
                    )
                )
        for pattern, solution in WEAK_TOOL_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                failures.append(
                    Failure(
                        path,
                        "Tool file contains a gate-weakening pattern.",
                        solution,
                        line_for_offset(original, match.start()),
                    )
                )
        failures.extend(scan_always_green_main(path, original))
    return failures


def scan_always_green_main(path: Path, text: str) -> list[Failure]:
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return []
    failures: list[Failure] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != "main":
            continue
        meaningful = [stmt for stmt in node.body if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str))]
        if len(meaningful) == 1 and isinstance(meaningful[0], ast.Return):
            value = meaningful[0].value
            if isinstance(value, ast.Constant) and value.value == 0:
                failures.append(
                    Failure(
                        path,
                        "Tool main() unconditionally returns success.",
                        "A gate tool must inspect inputs and return non-zero on blocking failures.",
                        meaningful[0].lineno,
                    )
                )
    return failures


def run(root: Path) -> list[Failure]:
    manifest, failures = load_manifest(root)
    if manifest:
        failures.extend(validate_manifest(root, manifest))
    failures.extend(scan_tools(root))
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    failures = run(root)
    if failures:
        print("tools guardrails failed.\n")
        print("Tools may run gates, validate fixtures, inspect boundaries, check manifests, and report results only.")
        print("Undocumented tools, hidden scoring/validation/mutation logic, and weak gate behavior are hard-blocked.\n")
        for failure in failures:
            print(failure.format(root))
        return 1

    print("tools guardrails passed: utility manifest, release gates, and hidden-logic boundaries are aligned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
