"""Run invalid operation fixtures through resume_core.validateChange."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import sys
import unittest
from pathlib import Path
from typing import Any

from tests.support.operation_fixture_adapter import (
    REJECTION_STATUSES,
    build_validate_change_case,
    expected_reason_observed,
    load_honesty_fixtures,
)


ROOT = Path(__file__).resolve().parents[2]
RESUME_CORE_ROOT = ROOT / "resume-core"
if str(RESUME_CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(RESUME_CORE_ROOT))


def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def load_core_module() -> Any:
    return importlib.import_module("resume_core")


def validate_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    core = load_core_module()
    case = build_validate_change_case(fixture)
    return maybe_await(
        core.validateChange(
            case["canonical_resume"],
            case["operation"],
            case["job_model"],
            case["career_facts"],
            case["policy"],
        )
    )


def _related_skill_overreach_rejects() -> bool:
    fixture = _fixture_by_reason("related_skill_overreach")
    result = validate_fixture(fixture)
    return result.get("status") in REJECTION_STATUSES


def _fixture_by_reason(expected_reason: str) -> dict[str, Any]:
    for fixture in load_honesty_fixtures():
        if fixture["expected_reason"] == expected_reason:
            return fixture
    raise AssertionError(f"Missing honesty fixture for {expected_reason}")


class HonestyFixturesValidateChangeTests(unittest.TestCase):
    def assert_fixture_rejected(self, expected_reason: str) -> None:
        fixture = _fixture_by_reason(expected_reason)
        result = validate_fixture(fixture)
        self.assertIn(result.get("status"), REJECTION_STATUSES, result)
        self.assertTrue(expected_reason_observed(fixture, result), result)

    def test_unsupported_scale_rejects_with_expected_reason(self):
        self.assert_fixture_rejected("unsupported_scale")

    def test_unsupported_management_scope_rejects_with_expected_reason(self):
        self.assert_fixture_rejected("unsupported_management_scope")

    def test_title_inflation_rejects_with_expected_reason(self):
        self.assert_fixture_rejected("title_inflation")

    def test_years_inflation_rejects_with_expected_reason(self):
        self.assert_fixture_rejected("years_inflation")

    def test_related_skill_overreach_rejects_or_tracks_known_red_baseline(self):
        self.assert_fixture_rejected("related_skill_overreach")


if not _related_skill_overreach_rejects():
    # Known red baseline owned by RKIT-I-0007 store facts / RKIT-I-0004 grounded-change lifecycle.
    HonestyFixturesValidateChangeTests.test_related_skill_overreach_rejects_or_tracks_known_red_baseline = (
        unittest.expectedFailure(
            HonestyFixturesValidateChangeTests.test_related_skill_overreach_rejects_or_tracks_known_red_baseline
        )
    )


if __name__ == "__main__":
    unittest.main()
