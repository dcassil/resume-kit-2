#!/usr/bin/env python3
"""Run resume-core guardrails whenever relevant files change."""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


WATCHED_PREFIXES = ("resume-core", "tools", "tests/contract", "tests/boundary")


def snapshot(root: Path) -> dict[Path, tuple[int, int]]:
    state: dict[Path, tuple[int, int]] = {}
    for prefix in WATCHED_PREFIXES:
        base = root / prefix
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                stat = path.stat()
                state[path] = (stat.st_mtime_ns, stat.st_size)
    return state


def run_guardrail(root: Path) -> int:
    command = [sys.executable, str(root / "tools" / "resume_core_guardrails.py"), "--root", str(root)]
    return subprocess.run(command, cwd=root).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    previous = snapshot(root)
    print("Watching resume-core guardrails. Press Ctrl-C to stop.")
    run_guardrail(root)
    try:
        while True:
            time.sleep(args.interval)
            current = snapshot(root)
            if current != previous:
                previous = current
                print("\nDetected relevant file change; running resume-core guardrails...")
                run_guardrail(root)
    except KeyboardInterrupt:
        print("\nStopped resume-core guardrail watcher.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
