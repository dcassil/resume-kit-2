"""Unit checks for ResumeChangeOperation structural validation."""

from __future__ import annotations

import copy
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


CANONICAL_RESUME = {
    "schema_version": "canonical-resume.v1",
    "resume_id": "resume_change_operation_unit",
    "source": {"kind": "unit"},
    "experience": [],
    "skills": ["React"],
    "education": [],
}

JOB_MODEL = {
    "schema_version": "job-model.v1",
    "job_id": "job_change_operation_unit",
    "requirements": [
        {
            "requirement_id": "req_react",
            "classification": "required",
            "concept": "React",
            "importance": "high",
            "weight": 10,
            "source_text": "React",
            "normalized_terms": ["react"],
        }
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
    }
]


def _operation(op: str = "replace", status: str = "proposed") -> dict:
    if op == "insert":
        path = "/skills/-"
        before = None
        after = "TypeScript"
    elif op == "remove":
        path = "/skills/0"
        before = "React"
        after = None
    else:
        path = "/skills/0"
        before = "React"
        after = "React"
    return {
        "schema_version": "resume-change-operation.v1",
        "operation_id": f"op_{op}_{status}",
        "status": status,
        "op": op,
        "path": path,
        "reason": "Exercise structural validation for canonical change operations.",
        "before": before,
        "after": after,
        "linked_requirement_ids": ["req_react"],
        "linked_fact_ids": ["fact_react"],
        "provenance": [{"source": "unit", "text": "React"}],
    }


class ChangeOperationStructuralTests(unittest.TestCase):
    def test_all_canonical_verbs_are_structurally_accepted(self):
        self.assertEqual(
            set(resume_core.RESUME_CHANGE_OPERATION_SCHEMA["properties"]["op"]["enum"]),
            {"replace", "rewrite", "insert", "remove", "move"},
        )
        for verb in ("replace", "rewrite", "insert", "remove", "move"):
            with self.subTest(verb=verb):
                result = resume_core.validateChange(CANONICAL_RESUME, _operation(verb), JOB_MODEL, CAREER_FACTS, {})
                self.assertEqual(result.get("status"), "ok", result)
                self.assertEqual(result["validated_operation"]["op"], verb)

    def test_invalid_operation_verb_is_rejected_with_invalid_op(self):
        operation = _operation("replace")
        operation["op"] = "add"

        result = resume_core.validateChange(CANONICAL_RESUME, operation, JOB_MODEL, CAREER_FACTS, {})

        self.assertEqual(result.get("status"), "rejected", result)
        self.assertIn("invalid_op", {error.get("code") for error in result.get("errors", [])})

    def test_all_canonical_statuses_are_structurally_accepted(self):
        expected_statuses = {"proposed", "validated", "rejected", "applied", "accepted", "modified"}
        self.assertEqual(
            set(resume_core.RESUME_CHANGE_OPERATION_SCHEMA["properties"]["status"]["enum"]),
            expected_statuses,
        )

        for status in sorted(expected_statuses):
            with self.subTest(status=status):
                result = resume_core.validateChange(CANONICAL_RESUME, _operation("replace", status), JOB_MODEL, CAREER_FACTS, {})
                self.assertEqual(result.get("status"), "ok", result)

    def test_invalid_status_is_rejected_with_invalid_status(self):
        operation = _operation("replace")
        operation["status"] = "done"

        result = resume_core.validateChange(CANONICAL_RESUME, operation, JOB_MODEL, CAREER_FACTS, {})

        self.assertEqual(result.get("status"), "rejected", result)
        self.assertIn("invalid_status", {error.get("code") for error in result.get("errors", [])})

    def test_mandatory_structural_fields_emit_missing_field(self):
        required = set(resume_core.RESUME_CHANGE_OPERATION_SCHEMA["required"])
        self.assertTrue(
            {
                "reason",
                "linked_requirement_ids",
                "linked_fact_ids",
                "provenance",
            }
            <= required
        )

        operation = _operation("replace")
        for field_name in ("reason", "linked_requirement_ids", "linked_fact_ids", "provenance"):
            with self.subTest(field_name=field_name):
                missing = copy.deepcopy(operation)
                del missing[field_name]
                result = resume_core.validateChange(CANONICAL_RESUME, missing, JOB_MODEL, CAREER_FACTS, {})
                missing_fields = {
                    error.get("field_path")
                    for error in result.get("errors", [])
                    if error.get("code") == "missing_field"
                }
                self.assertEqual(result.get("status"), "rejected", result)
                self.assertIn(field_name, missing_fields)


if __name__ == "__main__":
    unittest.main()
