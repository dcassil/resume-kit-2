"""Contract tests for runtime package naming and install layout."""

from __future__ import annotations

import importlib
import importlib.metadata
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
EXPECTED_PACKAGES = {
    "resume-core": "resume_core",
    "career-store": "career_store",
    "career-mcp": "career_mcp",
    "resume-agent": "resume_agent",
    "resume-cli": "resume_cli",
    "resume-plugin": "resume_plugin",
    "resume-render": "resume_render",
    "workflow": "workflow",
}


class RuntimePackageLayoutContractTests(unittest.TestCase):
    def test_distribution_declares_runtime_packages(self):
        self.assertEqual(PYPROJECT["project"]["name"], "resume-kit")
        self.assertEqual(set(PYPROJECT["tool"]["setuptools"]["packages"]), set(EXPECTED_PACKAGES.values()))

    def test_hyphenated_folders_map_to_snake_case_imports(self):
        package_dir = PYPROJECT["tool"]["setuptools"]["package-dir"]
        declared_layout = {
            entry["folder"]: entry["import_name"]
            for entry in PYPROJECT["tool"]["resume-kit"]["packages"]
        }
        self.assertEqual(declared_layout, EXPECTED_PACKAGES)
        for folder, import_name in EXPECTED_PACKAGES.items():
            with self.subTest(folder=folder, import_name=import_name):
                if folder == "workflow":
                    expected_path = folder
                else:
                    expected_path = f"{folder}/{import_name}"
                self.assertEqual(package_dir[import_name], expected_path)
                self.assertTrue((ROOT / expected_path / "__init__.py").is_file())

    def test_canonical_test_command_is_declared(self):
        self.assertEqual(
            PYPROJECT["tool"]["resume-kit"]["canonical_test_command"],
            "python3 tools/run_gate.py --pr --root .",
        )

    def test_packages_import_after_editable_install(self):
        self.assertEqual(importlib.metadata.version("resume-kit"), PYPROJECT["project"]["version"])
        for folder, import_name in EXPECTED_PACKAGES.items():
            with self.subTest(import_name=import_name):
                module = importlib.import_module(import_name)
                module_file = Path(module.__file__).resolve()
                self.assertIn(ROOT / folder, module_file.parents)


if __name__ == "__main__":
    unittest.main()
