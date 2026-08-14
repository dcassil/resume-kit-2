"""Shared Python architecture lint helpers for package boundary guardrails."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PACKAGE_IMPORT_ROOTS = {
    "resume-core": "resume_core",
    "career-store": "career_store",
    "career-mcp": "career_mcp",
    "resume-agent": "resume_agent",
    "resume-cli": "resume_cli",
    "resume-plugin": "resume_plugin",
    "resume-render": "resume_render",
    "workflow": "workflow",
}

PUBLIC_PACKAGE_ROOTS = set(PACKAGE_IMPORT_ROOTS.values())
MAX_FILE_LINES = 1500
MAX_FUNCTION_LINES = 140
MAX_COMPLEXITY = 35
MAX_NESTING_DEPTH = 10


@dataclass(frozen=True)
class ArchitectureFailure:
    path: Path
    message: str
    solution: str
    line: int | None = None

    def format(self, root: Path) -> str:
        rel = self.path.relative_to(root) if self.path.is_relative_to(root) else self.path
        where = f"{rel}:{self.line}" if self.line else str(rel)
        return f"- {where}\n  Why it failed: {self.message}\n  Possible solution: {self.solution}"


def scan_python_architecture(package_folder: str, path: Path, text: str) -> list[ArchitectureFailure]:
    """Run cross-package and quality checks shared by package guardrails.

    This adapts the Agent Kit robust-lint pattern to Python: public-root package
    imports are the cross-package boundary, dynamic imports are treated as
    bypass attempts, and coarse numeric caps prevent unbounded package files.
    """

    current_root = PACKAGE_IMPORT_ROOTS[package_folder]
    failures = _scan_file_size(path, text)
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return failures + [
            ArchitectureFailure(
                path,
                f"Python source cannot be parsed for shared architecture lint: {exc.msg}.",
                "Fix syntax so package-boundary and quality rules can classify the file.",
                exc.lineno,
            )
        ]

    failures.extend(_scan_import_boundaries(current_root, path, tree))
    failures.extend(_scan_dynamic_imports(current_root, path, tree))
    failures.extend(_scan_star_imports(path, tree))
    failures.extend(_scan_eval_exec(path, tree))
    failures.extend(_scan_function_caps(path, tree))
    return failures


def _scan_file_size(path: Path, text: str) -> list[ArchitectureFailure]:
    line_count = len(text.splitlines())
    if line_count <= MAX_FILE_LINES:
        return []
    return [
        ArchitectureFailure(
            path,
            f"Python source file has {line_count} lines, over the {MAX_FILE_LINES}-line architecture cap.",
            "Split by package-owned responsibility and keep the package root as a thin public facade.",
        )
    ]


def _scan_import_boundaries(current_root: str, path: Path, tree: ast.AST) -> list[ArchitectureFailure]:
    failures: list[ArchitectureFailure] = []
    for node in ast.walk(tree):
        imported_names: list[str] = []
        if isinstance(node, ast.Import):
            imported_names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_names = [node.module]
        for imported in imported_names:
            root = imported.split(".", 1)[0]
            if root not in PUBLIC_PACKAGE_ROOTS or root == current_root:
                continue
            if imported == root:
                continue
            failures.append(
                ArchitectureFailure(
                    path,
                    f"Cross-package import '{imported}' reaches past the public package root.",
                    "Import from the target package root only, for example `from resume_core import Result`. Add a public export if another package needs a new contract.",
                    getattr(node, "lineno", None),
                )
            )
    return failures


def _scan_dynamic_imports(current_root: str, path: Path, tree: ast.AST) -> list[ArchitectureFailure]:
    failures: list[ArchitectureFailure] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        import_name = _dynamic_import_name(node)
        if import_name is None:
            continue
        root = import_name.split(".", 1)[0]
        if root not in PUBLIC_PACKAGE_ROOTS or root == current_root:
            continue
        failures.append(
            ArchitectureFailure(
                path,
                f"Dynamic import '{import_name}' bypasses static package-boundary checks.",
                "Use a normal public-root import so the dependency direction remains visible to guardrails and reviewers.",
                getattr(node, "lineno", None),
            )
        )
    return failures


def _dynamic_import_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name) and node.func.id == "__import__":
        return _first_string_arg(node)
    if (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "import_module"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "importlib"
    ):
        return _first_string_arg(node)
    return None


def _first_string_arg(node: ast.Call) -> str | None:
    if not node.args:
        return None
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _scan_star_imports(path: Path, tree: ast.AST) -> list[ArchitectureFailure]:
    failures: list[ArchitectureFailure] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and any(alias.name == "*" for alias in node.names):
            failures.append(
                ArchitectureFailure(
                    path,
                    "Wildcard imports hide the dependency graph and public API surface.",
                    "Import named symbols from the package root or defining module so ownership and cycles remain reviewable.",
                    getattr(node, "lineno", None),
                )
            )
    return failures


def _scan_eval_exec(path: Path, tree: ast.AST) -> list[ArchitectureFailure]:
    failures: list[ArchitectureFailure] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
            failures.append(
                ArchitectureFailure(
                    path,
                    f"`{node.func.id}` hides behavior from static architecture checks.",
                    "Use explicit parsing, dispatch tables, or public package APIs instead of runtime code execution.",
                    getattr(node, "lineno", None),
                )
            )
    return failures


def _scan_function_caps(path: Path, tree: ast.AST) -> list[ArchitectureFailure]:
    failures: list[ArchitectureFailure] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        end_line = getattr(node, "end_lineno", node.lineno)
        function_lines = end_line - node.lineno + 1
        if function_lines > MAX_FUNCTION_LINES:
            failures.append(
                ArchitectureFailure(
                    path,
                    f"Function `{node.name}` has {function_lines} lines, over the {MAX_FUNCTION_LINES}-line cap.",
                    "Extract cohesive private helpers or package-owned collaborator modules while preserving the public API.",
                    node.lineno,
                )
            )
        complexity = _complexity(node)
        if complexity > MAX_COMPLEXITY:
            failures.append(
                ArchitectureFailure(
                    path,
                    f"Function `{node.name}` has complexity {complexity}, over the {MAX_COMPLEXITY} cap.",
                    "Prefer early returns, lookup tables, or strategy helpers owned by the same package.",
                    node.lineno,
                )
            )
        depth = _nesting_depth(node)
        if depth > MAX_NESTING_DEPTH:
            failures.append(
                ArchitectureFailure(
                    path,
                    f"Function `{node.name}` has nesting depth {depth}, over the {MAX_NESTING_DEPTH} cap.",
                    "Invert conditions, return early, or extract nested branches into named helpers.",
                    node.lineno,
                )
            )
    return failures


def _complexity(node: ast.AST) -> int:
    score = 1
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.IfExp, ast.Match)):
            score += 1
        elif isinstance(child, ast.BoolOp):
            score += max(1, len(child.values) - 1)
    return score


def _nesting_depth(node: ast.AST) -> int:
    return _max_depth(ast.iter_child_nodes(node), 0)


def _max_depth(nodes: Iterable[ast.AST], level: int) -> int:
    max_level = level
    for node in nodes:
        nested = isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.Match))
        child_level = level + 1 if nested else level
        max_level = max(max_level, child_level, _max_depth(ast.iter_child_nodes(node), child_level))
    return max_level
