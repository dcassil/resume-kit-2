"""Shared stdlib-only helpers for resume-core unit suites."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


# tests/unit activation in the PR gate is owned by RKIT-T-0021; these suites
# are intentionally runnable through explicit unittest discovery for RKIT-T-0010.
ROOT = Path(__file__).resolve().parents[2]
RESUME_CORE_ROOT = ROOT / "resume-core"
if str(RESUME_CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(RESUME_CORE_ROOT))


def load_resume_core():
    return importlib.import_module("resume_core")
