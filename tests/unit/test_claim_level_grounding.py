"""Unit checks for claim-level grounding over ResumeField provenance."""

from __future__ import annotations

import copy
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


def _resume_with_claim_fields() -> dict:
    return {
        "schema_version": "canonical-resume.v1",
        "resume_id": "resume_claim_grounding_unit",
        "source": {"kind": "unit"},
        "skills": [
            {
                "value": "React",
                "claim_id": "claim_react",
                "provenance": [
                    {
                        "source": "resume",
                        "text": "React",
                        "verification_state": "source_stated",
                    }
                ],
                "verification_state": "source_stated",
            },
            {
                "value": "Node.js",
                "claim_id": "claim_node",
                "provenance": [],
                "verification_state": "unknown",
            },
        ],
        "experience": [],
        "education": [],
        "provenance": [{"source": "resume", "text": "React"}],
    }


def _aws_resume() -> dict:
    return {
        "schema_version": "canonical-resume.v1",
        "resume_id": "resume_claim_grounding_aws",
        "source": {"kind": "unit"},
        "skills": [
            {
                "value": "AWS",
                "claim_id": "claim_aws",
                "provenance": [{"source": "career_fact", "text": "AWS", "fact_id": "fact_aws"}],
                "verification_state": "unknown",
            }
        ],
        "experience": [],
        "education": [],
        "provenance": [],
    }


def _aws_fact(verification_state: str) -> dict:
    return {
        "fact_id": "fact_aws",
        "text": "AWS deployment ownership",
        "verification_state": verification_state,
        "evidence": [{"source": "unit", "text": "Confirmed AWS"}],
    }


class ClaimLevelGroundingTests(unittest.TestCase):
    def test_mixed_resume_field_provenance_reports_only_unprovenanced_claim(self):
        result = resume_core.validateGrounding(_resume_with_claim_fields(), [], [], {})

        self.assertEqual(result.get("status"), "fail", result)
        self.assertEqual(result.get("unsupported_claims"), [])
        self.assertEqual(len(result.get("missing_provenance", [])), 1, result)
        finding = result["missing_provenance"][0]
        self.assertEqual(finding.get("field_path"), "/skills/1")
        self.assertEqual(finding.get("reason"), "missing_provenance")
        self.assertEqual(finding["details"].get("claim_id"), "claim_node")

    def test_legacy_root_provenance_does_not_default_deny_all_base_claims(self):
        resume = _resume_with_claim_fields()
        for skill in resume["skills"]:
            skill["provenance"] = []
            skill["verification_state"] = "unknown"

        result = resume_core.validateGrounding(resume, [], [], {})

        self.assertEqual(result.get("status"), "pass", result)
        self.assertEqual(result.get("missing_provenance"), [])

    def test_inferred_fact_does_not_ground_claim_requiring_verification(self):
        result = resume_core.validateGrounding(_aws_resume(), [_aws_fact("inferred")], [], {"allow_inferred_facts": True})

        self.assertEqual(result.get("status"), "fail", result)
        finding = result["missing_provenance"][0]
        self.assertEqual(finding.get("field_path"), "/skills/0")
        self.assertEqual(finding.get("reason"), "inferred_fact_not_allowed")
        self.assertEqual(finding["details"].get("supporting_fact_ids"), ["fact_aws"])

    def test_verified_fact_states_ground_claims(self):
        for state in ("user_verified", "source_stated", "imported"):
            with self.subTest(state=state):
                result = resume_core.validateGrounding(_aws_resume(), [_aws_fact(state)], [], {})

                self.assertEqual(result.get("status"), "pass", result)
                self.assertEqual(result.get("unsupported_claims"), [])
                self.assertEqual(result.get("missing_provenance"), [])

    def test_applied_operation_claims_are_grounded_by_linked_fact_ids(self):
        operation = {
            "operation_id": "op_insert_aws",
            "status": "applied",
            "op": "insert",
            "path": "/skills/-",
            "after": "AWS",
            "linked_fact_ids": ["fact_aws"],
            "provenance": [{"source": "unit", "text": "AWS"}],
        }
        resume = {
            "schema_version": "canonical-resume.v1",
            "resume_id": "resume_applied_operation_claim",
            "source": {"kind": "unit"},
            "skills": ["AWS"],
            "experience": [],
            "education": [],
            "provenance": [],
        }

        result = resume_core.validateGrounding(resume, [_aws_fact("user_verified")], [operation], {})

        self.assertEqual(result.get("status"), "pass", result)
        self.assertEqual(result.get("unsupported_claims"), [])
        self.assertEqual(result.get("missing_provenance"), [])

    def test_claim_grounding_findings_are_deterministic_and_sorted_by_pointer(self):
        resume = copy.deepcopy(_resume_with_claim_fields())
        resume["summary"] = [
            {
                "value": "Builds web tooling.",
                "claim_id": "claim_summary",
                "provenance": [],
                "verification_state": "unknown",
            }
        ]

        first = resume_core.validateGrounding(resume, [], [], {})
        second = resume_core.validateGrounding(resume, [], [], {})

        self.assertEqual(first, second)
        self.assertEqual(
            [item.get("field_path") for item in first.get("missing_provenance", [])],
            ["/skills/1", "/summary/0"],
        )


if __name__ == "__main__":
    unittest.main()
