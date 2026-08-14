"""E2E regression for Definition of Done steps 10-14 through the resume_core surface.

PRODUCT_VISION_AND_CONTRACTS.md section 18, steps 10-14: produce grounded tailoring
operations, reject a hallucinated operation, produce a final working resume,
re-score, and pass final ATS/grounding checks. The final-validation step must
receive the applied operations so their linked fact IDs keep grounding the
claims they introduced (RKIT-I-0004 requirement 1; RKIT-A-0006 surface authority).
"""

from __future__ import annotations

import asyncio
import copy
import importlib
import inspect
import unittest


BASE_RESUME = {
    "schema_version": "test-1",
    "resume_id": "resume_e2e_base",
    "source": {"kind": "test_fixture"},
    "basics": {"name": "Dana Candidate", "email": "candidate@example.com"},
    "experience": [
        {
            "id": "exp_1",
            "company": "Example SaaS",
            "title": "Senior Software Engineer",
            "start_date": "2018-03",
            "end_date": "2024-06",
            "bullets": [
                "Built Python microservices for multi-tenant billing workflows.",
                "Designed PostgreSQL schemas and migration tooling.",
            ],
        }
    ],
    "skills": ["Python", "PostgreSQL"],
    "education": [],
    "provenance": [{"claim_id": "skill_python", "source": "resume", "text": "Python"}],
    "verification_state": "source_stated",
}

JOB_MODEL = {
    "schema_version": "test-1",
    "requirements": [
        {
            "requirement_id": "req_python",
            "classification": "required",
            "concept": "Python",
            "importance": "high",
            "weight": 10,
            "source_text": "Python",
            "normalized_terms": ["python"],
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
        "fact_id": "fact_aws",
        "text": "AWS experience across ECS and Lambda deployments",
        "verification_state": "user_verified",
        "evidence": [{"source": "interview", "text": "Confirmed AWS deployment ownership"}],
    }
]

CONFIG = {"matching": {"requireHardRequirementsResolved": True}}


def maybe_await(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def load_core_module(test_case: unittest.TestCase):
    try:
        return importlib.import_module("resume_core")
    except ModuleNotFoundError:
        test_case.fail(
            "Expected importable package 'resume_core'. Run 'pip install -e .' from the repo root first."
        )


def grounded_aws_operation():
    return {
        "schema_version": "resume-change-operation.v1",
        "operation_id": "op_insert_aws",
        "status": "proposed",
        "op": "insert",
        "path": "/skills/-",
        "reason": "Add AWS only because supplied career facts ground the requirement.",
        "before": None,
        "after": "AWS",
        "linked_requirement_ids": ["req_aws"],
        "linked_fact_ids": ["fact_aws"],
        "provenance": [{"source": "test"}],
    }


def hallucinated_graphql_operation():
    return {
        "schema_version": "resume-change-operation.v1",
        "operation_id": "op_insert_graphql",
        "status": "proposed",
        "op": "insert",
        "path": "/skills/-",
        "reason": "GraphQL must still be rejected when ungrounded.",
        "before": None,
        "after": "GraphQL",
        "linked_requirement_ids": [],
        "linked_fact_ids": [],
        "provenance": [{"source": "test"}],
    }


class GroundedTailoringFinalValidationTests(unittest.TestCase):
    """DoD steps 10-14: grounded tailoring must survive final validation."""

    def setUp(self):
        self.core = load_core_module(self)

    def validated_and_applied_aws(self):
        validated = maybe_await(
            self.core.validateChange(BASE_RESUME, grounded_aws_operation(), JOB_MODEL, CAREER_FACTS, CONFIG)
        )
        self.assertEqual(validated.get("status"), "ok", validated)
        applied = maybe_await(self.core.applyChange(BASE_RESUME, validated["validated_operation"]))
        self.assertEqual(applied.get("status"), "ok", applied)
        return applied["working_resume"], applied["applied_operation"]

    def test_grounded_operation_validates_then_applies_to_working_resume(self):
        pristine_base = copy.deepcopy(BASE_RESUME)
        validated = maybe_await(
            self.core.validateChange(BASE_RESUME, grounded_aws_operation(), JOB_MODEL, CAREER_FACTS, CONFIG)
        )
        self.assertEqual(validated.get("status"), "ok", validated)
        self.assertEqual(validated.get("validation_state"), "validated")
        self.assertEqual(validated["validated_operation"].get("status"), "validated")
        self.assertIn("fact_aws", validated["grounding"].get("supporting_fact_ids", []))

        applied = maybe_await(self.core.applyChange(BASE_RESUME, validated["validated_operation"]))
        self.assertEqual(applied.get("status"), "ok", applied)
        self.assertTrue(applied["audit"].get("applied"))
        self.assertIn("AWS", applied["working_resume"].get("skills", []))
        self.assertEqual(applied["applied_operation"].get("status"), "applied")
        self.assertEqual(BASE_RESUME, pristine_base)

    def test_hallucinated_operation_is_rejected(self):
        result = maybe_await(
            self.core.validateChange(BASE_RESUME, hallucinated_graphql_operation(), JOB_MODEL, CAREER_FACTS, CONFIG)
        )
        self.assertEqual(result.get("status"), "rejected", result)
        self.assertEqual(result.get("validation_state"), "rejected")
        self.assertNotIn("validated_operation", result)
        error_codes = {error.get("code") for error in result.get("errors", [])}
        self.assertIn("unsupported_guarded_claim", error_codes)

    def test_rescore_after_apply_upgrades_requirement_resolution(self):
        final_resume, _ = self.validated_and_applied_aws()
        before = maybe_await(self.core.scoreMatch(BASE_RESUME, JOB_MODEL, CAREER_FACTS, CONFIG))
        after_first = maybe_await(self.core.scoreMatch(final_resume, JOB_MODEL, CAREER_FACTS, CONFIG))
        after_second = maybe_await(self.core.scoreMatch(final_resume, JOB_MODEL, CAREER_FACTS, CONFIG))
        self.assertEqual(after_first, after_second)

        def requirement_states(match_payload):
            return {
                item["requirement_id"]: item["resolution_state"]
                for item in match_payload["match_result"].get("requirement_results", [])
            }

        before_states = requirement_states(before)
        after_states = requirement_states(after_first)
        self.assertIn("req_aws", before_states)
        self.assertNotEqual(before_states["req_aws"], "exact_match", before_states)
        self.assertEqual(after_states.get("req_aws"), "exact_match", after_states)
        before_score = before["match_result"].get("score", 0)
        after_score = after_first["match_result"].get("score", 0)
        self.assertGreaterEqual(after_score, before_score)

    def test_final_validation_passes_for_validated_and_applied_grounded_addition(self):
        final_resume, applied_operation = self.validated_and_applied_aws()
        report = maybe_await(
            self.core.validateFinalResume(final_resume, JOB_MODEL, CAREER_FACTS, CONFIG, [applied_operation])
        )
        self.assertEqual(report.get("status"), "pass", report)
        self.assertEqual(report.get("errors"), [])
        self.assertIn("match_result", report)
        self.assertIn("AWS", report["final_resume"].get("skills", []))

    def test_final_validation_still_rejects_ungrounded_guarded_claims(self):
        tampered = copy.deepcopy(BASE_RESUME)
        tampered["skills"].append("GraphQL")
        report = maybe_await(self.core.validateFinalResume(tampered, JOB_MODEL, CAREER_FACTS, CONFIG))
        self.assertEqual(report.get("status"), "fail", report)
        reasons = {error.get("reason") for error in report.get("errors", [])}
        self.assertIn("missing_verified_fact", reasons)

    def test_final_validation_is_deterministic(self):
        final_resume, applied_operation = self.validated_and_applied_aws()
        first = maybe_await(
            self.core.validateFinalResume(final_resume, JOB_MODEL, CAREER_FACTS, CONFIG, [applied_operation])
        )
        second = maybe_await(
            self.core.validateFinalResume(final_resume, JOB_MODEL, CAREER_FACTS, CONFIG, [applied_operation])
        )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
