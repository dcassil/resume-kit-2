"""Contract-first tests for the future resume_core package."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SURFACE = json.loads((ROOT / "resume-core" / "core_surface.json").read_text(encoding="utf-8"))
PUBLIC_FUNCTIONS = tuple(SURFACE["public_api"]["functions"])
PUBLIC_TYPES = tuple(SURFACE["public_api"]["types"])


CANONICAL_RESUME = {
    "schema_version": "test-1",
    "basics": {"name": "Daniel Candidate", "email": "candidate@example.com"},
    "experience": [
        {
            "id": "exp_1",
            "company": "Example SaaS",
            "title": "Software Engineer",
            "start_date": "2019-01",
            "end_date": "2024-06",
            "bullets": [
                "Built React and TypeScript interfaces for multi-tenant SaaS workflows.",
                "Designed REST APIs and integration patterns.",
            ],
        }
    ],
    "skills": ["React", "TypeScript", "Node.js", "PostgreSQL", "Azure", "REST APIs", "Responsive web apps"],
    "education": [],
    "provenance": [{"claim_id": "skill_react", "source": "resume", "text": "React"}],
    "verification_state": "source_stated",
}

JOB_MODEL = {
    "schema_version": "test-1",
    "requirements": [
        {
            "requirement_id": "req_react",
            "classification": "required",
            "concept": "React",
            "importance": "high",
            "weight": 10,
            "source_text": "React",
            "normalized_terms": ["react"],
        },
        {
            "requirement_id": "req_aws",
            "classification": "preferred",
            "concept": "AWS",
            "importance": "medium",
            "weight": 3,
            "source_text": "AWS",
            "normalized_terms": ["aws"],
        },
    ],
}

CAREER_FACTS = [
    {
        "fact_id": "fact_react",
        "text": "React",
        "verification_state": "source_stated",
        "evidence": [{"source": "resume", "text": "React"}],
    }
]


def maybe_await(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def load_core_module(test_case: unittest.TestCase):
    try:
        module = importlib.import_module("resume_core")
    except ModuleNotFoundError as exc:
        test_case.fail(
            "Expected importable package 'resume_core'. Implement the deterministic surfaces from "
            "resume-core/TEST_SPEC.md and resume-core/core_surface.json."
        )
        raise exc
    for function_name in PUBLIC_FUNCTIONS:
        test_case.assertTrue(callable(getattr(module, function_name, None)), f"resume_core must expose {function_name}().")
    for type_name in PUBLIC_TYPES:
        test_case.assertTrue(hasattr(module, type_name), f"resume_core must expose {type_name}.")
    return module


def serialized(result: dict) -> str:
    return json.dumps(result, sort_keys=True).lower()


class ResumeCoreSurfaceManifestTests(unittest.TestCase):
    def test_manifest_declares_exact_public_functions_and_types(self):
        self.assertEqual(
            PUBLIC_FUNCTIONS,
            (
                "normalizeResume",
                "validateResume",
                "sanitizeText",
                "normalizeJobModel",
                "scoreMatch",
                "getUnresolvedRequirements",
                "rankResumeContent",
                "validateChange",
                "applyChange",
                "validateGrounding",
                "validateFinalResume",
            ),
        )
        self.assertEqual(
            set(PUBLIC_TYPES),
            {
                "CanonicalResume",
                "ResumeField",
                "JobModel",
                "JobRequirement",
                "MatchResult",
                "ResolutionState",
                "ResumeChangeOperation",
                "VerificationState",
            },
        )

    def test_manifest_defines_contracts_for_every_surface(self):
        surfaces = {surface["name"]: surface for surface in SURFACE["surfaces"]}
        self.assertEqual(set(surfaces), set(PUBLIC_FUNCTIONS))
        for name, surface in surfaces.items():
            with self.subTest(surface=name):
                self.assertIn("input_contract", surface)
                self.assertIn("output_contract", surface)
                required_fields = set(surface["output_contract"]["required_fields"])
                self.assertTrue({"schema_version", "status"} <= required_fields)
                self.assertIn("must_not_include", surface["output_contract"])


class ResumeCoreDomainContractTests(unittest.TestCase):
    def setUp(self):
        self.core = load_core_module(self)

    def test_sanitization_is_deterministic_and_reports_without_changing_meaning(self):
        text = "Built\u00a0React interfaces with \u201cclean\u201d APIs.\x07"
        first = maybe_await(self.core.sanitizeText(text))
        second = maybe_await(self.core.sanitizeText(text))
        self.assertEqual(first, second)
        self.assertIn(first.get("status"), {"ok", "warning", "error"})
        self.assertIn("text", first)
        self.assertIn("warnings", first)
        self.assertIn("React", first.get("text", ""))

    def test_scoring_is_deterministic_and_keeps_missing_preferred_distinct(self):
        first = maybe_await(self.core.scoreMatch(CANONICAL_RESUME, JOB_MODEL, CAREER_FACTS, {"policy": "strict"}))
        second = maybe_await(self.core.scoreMatch(CANONICAL_RESUME, JOB_MODEL, CAREER_FACTS, {"policy": "strict"}))
        self.assertEqual(first, second)
        self.assertIn("match_result", first)
        text = serialized(first)
        self.assertIn("req_react", text)
        self.assertIn("req_aws", text)
        self.assertNotIn("staff software engineer", text)
        self.assertNotRegex(text, r"\b20 million\b|\b30 engineers\b")

    def test_unverified_or_related_facts_do_not_validate_unsupported_change(self):
        operation = {
            "operation_id": "op_aws_inflation",
            "status": "proposed",
            "path": "/skills/-",
            "before": None,
            "after": "AWS, ten years",
            "linked_requirement_ids": ["req_aws"],
            "linked_fact_ids": ["fact_react"],
        }
        result = maybe_await(self.core.validateChange(CANONICAL_RESUME, operation, JOB_MODEL, CAREER_FACTS, {"require_verified": True}))
        self.assertIn(result.get("status"), {"rejected", "error"})
        text = serialized(result)
        self.assertIn("aws", text)
        self.assertNotIn("validation_state\": \"validated", text)

    def test_apply_change_requires_validated_operation_and_preserves_base_resume(self):
        operation = {
            "operation_id": "op_bad",
            "status": "proposed",
            "path": "/summary",
            "before": None,
            "after": "Staff Software Engineer",
        }
        result = maybe_await(self.core.applyChange(CANONICAL_RESUME, operation))
        self.assertIn(result.get("status"), {"rejected", "error"})
        text = serialized(result)
        self.assertNotIn("base_resume_mutated", text)
        self.assertNotIn("staff software engineer", serialized(CANONICAL_RESUME))

    def test_final_validation_reports_grounding_and_match_result_without_rendering(self):
        result = maybe_await(self.core.validateFinalResume(CANONICAL_RESUME, JOB_MODEL, CAREER_FACTS, {"policy": "strict"}))
        self.assertIn(result.get("status"), {"pass", "fail", "error"})
        self.assertIn("match_result", result)
        text = serialized(result)
        self.assertNotRegex(text, r"\b(rendered_output|docx|pdf|sqlite|traceback)\b")


if __name__ == "__main__":
    unittest.main()
