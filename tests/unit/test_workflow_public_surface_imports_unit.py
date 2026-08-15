"""AST boundary check for workflow cross-package public imports."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = ROOT / "workflow"
PACKAGE_ROOTS = {
    "resume_core": ROOT / "resume-core" / "resume_core" / "__init__.py",
    "resume_render": ROOT / "resume-render" / "resume_render" / "__init__.py",
}


def exported_names(package_init: Path) -> set[str]:
    tree = ast.parse(package_init.read_text(encoding="utf-8"), filename=str(package_init))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            continue
        return {
            element.value
            for element in node.value.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        }
    return set()


class WorkflowPublicSurfaceImportTests(unittest.TestCase):
    def test_workflow_imports_resume_packages_only_through_public_roots(self):
        exported_by_package = {
            package: exported_names(package_init)
            for package, package_init in PACKAGE_ROOTS.items()
        }
        violations: list[str] = []

        for path in sorted(WORKFLOW_ROOT.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            relative = path.relative_to(ROOT)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        package = alias.name.split(".", 1)[0]
                        if package in PACKAGE_ROOTS and alias.name != package:
                            violations.append(f"{relative}: import {alias.name} reaches past {package} package root")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    package = node.module.split(".", 1)[0]
                    if package not in PACKAGE_ROOTS:
                        continue
                    if node.module != package:
                        violations.append(f"{relative}: from {node.module} import ... reaches past {package} package root")
                        continue
                    for alias in node.names:
                        if alias.name == "*":
                            violations.append(f"{relative}: wildcard import from {package} hides public-surface use")
                        elif alias.name not in exported_by_package[package]:
                            violations.append(f"{relative}: {alias.name} is not exported by {package}.__all__")
                elif self._is_dynamic_submodule_import(node):
                    package, imported = self._dynamic_import_value(node)
                    violations.append(f"{relative}: dynamic import {imported!r} reaches past {package} package root")

        self.assertEqual(violations, [])

    def _is_dynamic_submodule_import(self, node: ast.AST) -> bool:
        package, imported = self._dynamic_import_value(node)
        return bool(package and imported and imported != package)

    def _dynamic_import_value(self, node: ast.AST) -> tuple[str | None, str | None]:
        if not isinstance(node, ast.Call):
            return None, None
        function = node.func
        is_importlib = (
            isinstance(function, ast.Attribute)
            and function.attr == "import_module"
            and isinstance(function.value, ast.Name)
            and function.value.id == "importlib"
        )
        is_dunder_import = isinstance(function, ast.Name) and function.id == "__import__"
        if not (is_importlib or is_dunder_import) or not node.args:
            return None, None
        first_arg = node.args[0]
        if not isinstance(first_arg, ast.Constant) or not isinstance(first_arg.value, str):
            return None, None
        imported = first_arg.value
        package = imported.split(".", 1)[0]
        if package not in PACKAGE_ROOTS:
            return None, None
        return package, imported


if __name__ == "__main__":
    unittest.main()
