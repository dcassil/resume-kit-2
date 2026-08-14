"""Unit checks for ResumeChangeOperation lifecycle enforcement."""

from __future__ import annotations

import copy
import importlib
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()
domain = importlib.import_module("resume_core.domain")


CANONICAL_RESUME = {
    "schema_version": "canonical-resume.v1",
    "resume_id": "resume_operation_lifecycle_unit",
    "source": {"kind": "unit"},
    "basics": {
        "summary": "Built React workflows.",
        "primary_skill": "React",
        "tagline": "Frontend engineer",
    },
    "experience": [{"company": "Example", "title": "Engineer", "bullets": ["Built React workflows."]}],
    "skills": ["React"],
    "education": [],
    "provenance": [{"source": "unit", "text": "React"}],
}

JOB_MODEL = {
    "schema_version": "job-model.v1",
    "job_id": "job_operation_lifecycle_unit",
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
            "classification": "required",
            "concept": "AWS",
            "importance": "high",
            "weight": 10,
            "source_text": "AWS",
            "normalized_terms": ["aws"],
        },
    ],
    "preferred": [],
    "industries": [],
    "domains": [],
    "terminology": [],
}

CAREER_FACTS = [
    {
        "fact_id": "fact_react",
        "text": "React",
        "verification_state": "source_stated",
        "evidence": [{"source": "resume", "text": "React"}],
    },
    {
        "fact_id": "fact_aws",
        "text": "AWS",
        "verification_state": "user_verified",
        "evidence": [{"source": "user", "text": "AWS"}],
    },
]


def _operation(**overrides):
    operation = {
        "schema_version": "resume-change-operation.v1",
        "operation_id": "op_lifecycle",
        "status": "proposed",
        "op": "replace",
        "path": "/basics/summary",
        "before": "Built React workflows.",
        "after": "Built React workflows.",
        "reason": "Grounded lifecycle unit operation.",
        "linked_requirement_ids": ["req_react"],
        "linked_fact_ids": ["fact_react"],
        "provenance": [{"source": "unit", "text": "React"}],
    }
    operation.update(overrides)
    return operation


def _validated_operation(**overrides):
    return _operation(status="validated", validation_state="validated", **overrides)


class OperationLifecycleEnforcementTests(unittest.TestCase):
    def test_validate_change_emits_typed_per_field_errors_for_missing_mandatory_fields(self):
        expected_codes = {
            "reason": "missing_reason",
            "linked_requirement_ids": "missing_linked_requirement_ids",
            "linked_fact_ids": "missing_linked_fact_ids",
            "provenance": "missing_provenance",
        }
        for field_name, expected_code in expected_codes.items():
            with self.subTest(field_name=field_name):
                operation = _operation()
                del operation[field_name]

                result = resume_core.validateChange(CANONICAL_RESUME, operation, JOB_MODEL, CAREER_FACTS, {})

                self.assertEqual(result.get("status"), "rejected", result)
                self.assertIn(expected_code, {error.get("code") for error in result.get("errors", [])})

    def test_validate_change_rejects_empty_mandatory_fields_with_typed_errors(self):
        cases = {
            "reason": ("", "missing_reason"),
            "linked_requirement_ids": ([], "missing_linked_requirement_ids"),
            "linked_fact_ids": ([], "missing_linked_fact_ids"),
            "provenance": ([], "missing_provenance"),
        }
        for field_name, (value, expected_code) in cases.items():
            with self.subTest(field_name=field_name):
                operation = _operation(**{field_name: value})

                result = resume_core.validateChange(CANONICAL_RESUME, operation, JOB_MODEL, CAREER_FACTS, {})

                self.assertEqual(result.get("status"), "rejected", result)
                self.assertIn(expected_code, {error.get("code") for error in result.get("errors", [])})

    def test_fully_grounded_operation_still_validates(self):
        result = resume_core.validateChange(CANONICAL_RESUME, _operation(), JOB_MODEL, CAREER_FACTS, {})

        self.assertEqual(result.get("status"), "ok", result)
        self.assertEqual(result["validated_operation"]["status"], "validated")

    def test_status_transition_table_allows_only_declared_edges(self):
        expected = {
            "proposed": {"validated"},
            "validated": {"applied", "rejected"},
            "applied": {"accepted", "modified"},
            "rejected": set(),
            "accepted": set(),
            "modified": set(),
        }
        self.assertEqual(domain.CHANGE_OPERATION_STATUS_TRANSITIONS, expected)
        statuses = sorted(expected)
        for from_status in statuses:
            for to_status in statuses:
                with self.subTest(from_status=from_status, to_status=to_status):
                    error = domain._operation_status_transition_error(from_status, to_status)
                    if to_status in expected[from_status]:
                        self.assertIsNone(error)
                    else:
                        self.assertEqual(error["code"], "invalid_status_transition")
                        self.assertEqual(error["details"]["from_status"], from_status)
                        self.assertEqual(error["details"]["to_status"], to_status)

    def test_apply_change_rejects_non_validated_operation_with_invalid_transition(self):
        result = resume_core.applyChange(CANONICAL_RESUME, _operation(status="proposed"))

        self.assertEqual(result.get("status"), "rejected", result)
        self.assertEqual(result["errors"][0]["code"], "invalid_status_transition")
        self.assertEqual(result["errors"][0]["details"], {"from_status": "proposed", "to_status": "applied"})
        self.assertEqual(result["working_resume"], CANONICAL_RESUME)

    def test_apply_change_rejects_validated_operation_missing_mandatory_fields(self):
        operation = _validated_operation()
        del operation["provenance"]

        result = resume_core.applyChange(CANONICAL_RESUME, operation)

        self.assertEqual(result.get("status"), "rejected", result)
        self.assertIn("missing_provenance", {error.get("code") for error in result.get("errors", [])})
        self.assertEqual(result["working_resume"], CANONICAL_RESUME)

    def test_apply_change_verbs_preserve_immutability_and_idempotence(self):
        cases = [
            (
                "replace",
                _validated_operation(path="/basics/summary", before="Built React workflows.", after="Built React and AWS workflows."),
                lambda resume: resume["basics"]["summary"] == "Built React and AWS workflows.",
            ),
            (
                "rewrite",
                _validated_operation(
                    op="rewrite",
                    path="/experience/0/bullets/0",
                    before="Built React workflows.",
                    after="Built React and AWS workflows.",
                ),
                lambda resume: resume["experience"][0]["bullets"][0] == "Built React and AWS workflows.",
            ),
            (
                "insert",
                _validated_operation(op="insert", path="/skills/-", before=None, after="AWS"),
                lambda resume: resume["skills"] == ["React", "AWS"],
            ),
            (
                "remove",
                _validated_operation(op="remove", path="/basics/tagline", before="Frontend engineer", after=None),
                lambda resume: "tagline" not in resume["basics"],
            ),
            (
                "move",
                _validated_operation(
                    op="move",
                    path="/basics/secondary_skill",
                    from_path="/basics/primary_skill",
                    before="React",
                    after="React",
                ),
                lambda resume: "primary_skill" not in resume["basics"] and resume["basics"]["secondary_skill"] == "React",
            ),
        ]
        for verb, operation, assertion in cases:
            with self.subTest(verb=verb):
                original = copy.deepcopy(CANONICAL_RESUME)

                first = resume_core.applyChange(original, operation)
                second = resume_core.applyChange(first["working_resume"], operation)

                self.assertEqual(first.get("status"), "ok", first)
                self.assertTrue(first["audit"]["applied"], first)
                self.assertTrue(assertion(first["working_resume"]), first)
                self.assertEqual(original, CANONICAL_RESUME)
                self.assertEqual(second.get("status"), "ok", second)
                self.assertFalse(second["audit"]["applied"], second)
                self.assertTrue(second["audit"]["already_applied"], second)

    def test_validate_final_resume_filters_applied_operation_statuses_before_grounding(self):
        resume = copy.deepcopy(CANONICAL_RESUME)
        resume["skills"] = ["AWS"]
        operation = _operation(
            operation_id="op_aws",
            status="proposed",
            op="insert",
            path="/skills/-",
            before=None,
            after="AWS",
            linked_requirement_ids=["req_aws"],
            linked_fact_ids=["fact_aws"],
            provenance=[{"source": "unit", "text": "AWS"}],
        )

        result = resume_core.validateFinalResume(resume, JOB_MODEL, CAREER_FACTS, {}, [operation])

        self.assertEqual(result.get("status"), "fail", result)
        error_codes = {error.get("code") for error in result.get("errors", [])}
        error_reasons = {error.get("reason") for error in result.get("errors", [])}
        self.assertIn("invalid_applied_operation_status", error_codes)
        self.assertIn("missing_verified_fact", error_reasons)

        for status in ("applied", "accepted", "modified"):
            with self.subTest(status=status):
                operation["status"] = status
                allowed = resume_core.validateFinalResume(resume, JOB_MODEL, CAREER_FACTS, {}, [operation])
                self.assertNotIn(
                    "invalid_applied_operation_status",
                    {error.get("code") for error in allowed.get("errors", [])},
                    allowed,
                )


if __name__ == "__main__":
    unittest.main()
