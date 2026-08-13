#!/usr/bin/env python3
"""Canonical current test runner for the contract scaffold."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


CONTRACT_TEST_MODULES = [
    "tests.contract.test_resume_core_contract",
    "tests.contract.test_career_store_contract",
    "tests.contract.test_career_mcp_contract",
    "tests.contract.test_workflow_contract",
    "tests.contract.test_resume_agent_contract",
    "tests.contract.test_resume_render_contract",
    "tests.contract.test_resume_cli_contract",
    "tests.contract.test_resume_plugin_contract",
    "tests.contract.test_fixtures_contract",
    "tests.contract.test_runtime_package_layout_contract",
    "tests.contract.test_shared_dto_schemas_contract",
    "tests.contract.test_tests_contract",
    "tests.contract.test_tools_contract",
]

BOUNDARY_TEST_MODULES = [
    "tests.boundary.test_architecture_lint_guardrails",
    "tests.boundary.test_career_mcp_guardrails",
    "tests.boundary.test_career_store_guardrails",
    "tests.boundary.test_resume_agent_guardrails",
    "tests.boundary.test_resume_core_guardrails",
    "tests.boundary.test_resume_render_guardrails",
    "tests.boundary.test_resume_cli_guardrails",
    "tests.boundary.test_resume_plugin_guardrails",
    "tests.boundary.test_workflow_guardrails",
    "tests.boundary.test_fixtures_guardrails",
    "tests.boundary.test_tests_guardrails",
    "tests.boundary.test_tools_guardrails",
]

CURRENT_TEST_MODULES = [
    *CONTRACT_TEST_MODULES,
    *BOUNDARY_TEST_MODULES,
]

FUTURE_CONTRACT_TEST_MODULES = [
    *CONTRACT_TEST_MODULES,
    *BOUNDARY_TEST_MODULES,
]


GENERATED_DIRS = [
    "resume_kit.egg-info",
]


def venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def clean_generated_artifacts(root: Path) -> None:
    for rel_path in GENERATED_DIRS:
        shutil.rmtree(root / rel_path, ignore_errors=True)
    for path in root.rglob("__pycache__"):
        shutil.rmtree(path, ignore_errors=True)


def run_command(command: list[str], cwd: Path, env: dict[str, str]) -> int:
    completed = subprocess.run(command, cwd=cwd, env=env, text=True, check=False)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument(
        "--future-contract",
        action="store_true",
        help="Run the full package contract target plus boundary guardrails.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    test_modules = FUTURE_CONTRACT_TEST_MODULES if args.future_contract else CURRENT_TEST_MODULES
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    with tempfile.TemporaryDirectory(prefix="resume-kit-tests-") as temp:
        env_dir = Path(temp) / ".venv"
        venv.EnvBuilder(with_pip=True).create(env_dir)
        python = venv_python(env_dir)

        try:
            install_code = run_command([str(python), "-m", "pip", "install", "-e", str(root)], cwd=root, env=env)
            if install_code:
                return install_code

            return run_command([str(python), "-m", "unittest", *test_modules], cwd=root, env=env)
        finally:
            clean_generated_artifacts(root)


if __name__ == "__main__":
    raise SystemExit(main())
