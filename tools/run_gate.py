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
    runner = root / "tools" / "run_tests.py"
    if not runner.exists():
        print(f"PR gate failed: missing test runner at {runner}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [sys.executable, str(runner), "--root", str(root)]
    print("Running PR gate: install check, contract tests, boundary tests, and guardrails.", flush=True)
    return run_command(command, cwd=root, env=env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--pr", action="store_true", help="Run the PR completion gate.")
    args = parser.parse_args(argv)

    if not args.pr:
        parser.error("choose a gate to run; currently supported: --pr")

    return run_pr_gate(Path(args.root).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
