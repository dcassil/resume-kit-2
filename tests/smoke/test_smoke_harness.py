"""Executable smoke test wrapper for SMOKE_TEST.md."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class SmokeHarnessTests(unittest.TestCase):
    def test_smoke_harness_passes_against_installed_package(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "run_smoke.py"), "--root", str(ROOT)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("smoke passed", result.stdout)


if __name__ == "__main__":
    unittest.main()
