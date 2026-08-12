#!/usr/bin/env python3
"""Single entry point for repository completion gates."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path


def run_command(command: list[str], cwd: Path, env: dict[str, str]) -> int:
    print(f"$ {shlex.join(command)}", flush=True)
    completed = subprocess.run(command, cwd=cwd, env=env, text=True, check=False)
    return completed.returncode


def run_pr_gate(root: Path) -> int:
    return run_test_runner(root, [], "Running PR gate: install check, contract tests, boundary tests, and guardrails.")


def run_future_contract_gate(root: Path) -> int:
    return run_test_runner(
        root,
        ["--future-contract"],
        "Running future contract gate: resume-core and career-store contracts plus boundary guardrails.",
    )


def run_test_runner(root: Path, extra_args: list[str], label: str) -> int:
    runner = root / "tools" / "run_tests.py"
    if not runner.exists():
        print(f"Gate failed: missing test runner at {runner}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [sys.executable, str(runner), "--root", str(root), *extra_args]
    print(label, flush=True)
    return run_command(command, cwd=root, env=env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    gate = parser.add_mutually_exclusive_group(required=True)
    gate.add_argument("--pr", action="store_true", help="Run the PR completion gate.")
    gate.add_argument(
        "--future-contract",
        action="store_true",
        help="Run the opt-in future package contract gate for resume-core and career-store.",
    )
    args = parser.parse_args(argv)

    if args.future_contract:
        return run_future_contract_gate(Path(args.root).resolve())
    return run_pr_gate(Path(args.root).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
