"""Adversarial honesty and lifecycle close-out coverage for RKIT-I-0004."""

from __future__ import annotations

import copy
import importlib
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()
domain = importlib.import_module("resume_core.domain")


BASE_RESUME = {
    "schema_version": "canonical-resume.v1",
    "resume_id": "resume_adversarial_honesty_unit",
    "source": {"kind": "unit"},
    "basics": {
        "summary": "Built React workflows.",
        "primary_skill": "React",
        "tagline": "Frontend engineer",
    },
    "experience": [
        {
            "company": "Example",
            "title": "Senior Software Engineer",
            "bullets": ["Built React workflows."],
        }
    ],
    "skills": ["React"],
    "education": [],
    "provenance": [{"source": "unit", "text": "React"}],
}

JOB_MODEL = {
    "schema_version": "job-model.v1",
    "job_id": "job_adversarial_honesty_unit",
    "requirements": [
        {
            "requirement_id": "req_general",
            "classification": "required",
            "concept": "General evidence",
            "importance": "high",
            "weight": 10,
            "source_text": "General evidence",
            "normalized_terms": ["general"],
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
        {
            "requirement_id": "req_terraform",
            "classification": "required",
            "concept": "Terraform",
            "importance": "high",
            "weight": 10,
            "source_text": "Terraform",
            "normalized_terms": ["terraform"],
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
        "fact_id": "fact_aws_years",
        "text": "6 years of AWS.",
        "verification_state": "user_verified",
        "evidence": [{"source": "unit", "text": "6 years of AWS"}],
    },
]

MANDATORY_FIELD_CODES = {
    "reason": "missing_reason",
    "linked_requirement_ids": "missing_linked_requirement_ids",
    "linked_fact_ids": "missing_linked_fact_ids",
    "provenance": "missing_provenance",
}


def _fact(fact_id: str, text: str, **overrides):
    fact = {
        "fact_id": fact_id,
        "text": text,
        "verification_state": "user_verified",
        "evidence": [{"source": "unit", "text": text}],
    }
    fact.update(overrides)
    return fact


def _operation(
    after,
    *,
    before="Built React workflows.",
    path="/basics/summary",
    op="replace",
    status="proposed",
    requirement_ids=None,
    fact_ids=None,
    **overrides,
):
    operation = {
        "schema_version": "resume-change-operation.v1",
        "operation_id": f"op_adversarial_{op}_{status}",
        "status": status,
        "op": op,
        "path": path,
        "before": before,
        "after": after,
        "reason": "Exercise adversarial honesty close-out behavior.",
        "linked_requirement_ids": requirement_ids or ["req_general"],
        "linked_fact_ids": fact_ids or ["fact_react"],
        "provenance": [{"source": "unit"}],
    }
    operation.update(overrides)
    return operation


def _validated_operation(op: str, **overrides):
    if op == "insert":
        return _operation("AWS", op=op, status="validated", path="/skills/-", before=None, **overrides)
    if op == "remove":
        return _operation(None, op=op, status="validated", path="/basics/tagline", before="Frontend engineer", **overrides)
    if op == "move":
        return _operation(
            "React",
            op=op,
            status="validated",
            path="/basics/secondary_skill",
            before="React",
            from_path="/basics/primary_skill",
            **overrides,
        )
    if op == "rewrite":
        return _operation("Built React and testing workflows.", op=op, status="validated", **overrides)
    return _operation("Built React and testing workflows.", op=op, status="validated", **overrides)


class GuardedTermsNeutralizer:
    def __enter__(self):
        self.original = copy.deepcopy(domain._GUARDED_TERMS)
        domain._GUARDED_TERMS.clear()

    def __exit__(self, exc_type, exc, tb):
        domain._GUARDED_TERMS.clear()
        domain._GUARDED_TERMS.update(self.original)


class AdversarialHonestySuiteTests(unittest.TestCase):
    def assert_rejected_claim(self, result, claim):
        self.assertEqual(result.get("status"), "rejected", result)
        claims = set()
        for error in result.get("errors", []):
            if error.get("code") == "unsupported_guarded_claim":
                claims.update(error.get("details", {}).get("claims", []))
        self.assertIn(claim, claims, result)

    def test_novel_fabrications_reject_without_guarded_term_lookup(self):
        cases = [
            (
                "cost_percent",
                _operation(
                    "Reduced costs by 80 percent.",
                    fact_ids=["fact_cost"],
                ),
                [_fact("fact_cost", "Reduced costs by 8 percent.")],
                "quantity:80:percent",
            ),
            (
                "distinguished_title",
                _operation(
                    "Distinguished Engineer",
                    before="Senior Software Engineer",
                    path="/experience/0/title",
                    fact_ids=["fact_title"],
                ),
                [_fact("fact_title", "Formal employment title was Senior Software Engineer.")],
                "title:distinguished",
            ),
            (
                "terraform_skill",
                _operation(
                    "Terraform expert.",
                    requirement_ids=["req_terraform"],
                    fact_ids=["fact_react"],
                ),
                CAREER_FACTS,
                "skill:terraform",
            ),
        ]
        with GuardedTermsNeutralizer():
            for name, operation, facts, claim in cases:
                with self.subTest(name=name):
                    result = resume_core.validateChange(BASE_RESUME, operation, JOB_MODEL, facts, {})
                    self.assert_rejected_claim(result, claim)

    def test_named_audit_regression_served_50_million_users_is_rejected(self):
        with GuardedTermsNeutralizer():
            result = resume_core.validateChange(
                BASE_RESUME,
                _operation("Served 50 million users daily."),
                JOB_MODEL,
                CAREER_FACTS,
                {},
            )
        self.assert_rejected_claim(result, "quantity:50000000:user")

    def test_named_audit_regression_principal_engineer_leading_100_people_is_rejected(self):
        with GuardedTermsNeutralizer():
            result = resume_core.validateChange(
                BASE_RESUME,
                _operation("Principal Engineer leading 100 people."),
                JOB_MODEL,
                CAREER_FACTS,
                {},
            )
        self.assert_rejected_claim(result, "title:principal")
        self.assert_rejected_claim(result, "quantity:100:person")

    def test_named_audit_regression_kubernetes_expert_is_rejected(self):
        with GuardedTermsNeutralizer():
            result = resume_core.validateChange(
                BASE_RESUME,
                _operation("Kubernetes expert."),
                JOB_MODEL,
                CAREER_FACTS,
                {},
            )
        self.assert_rejected_claim(result, "skill:kubernetes")

    def test_truthful_numeric_vs_word_years_are_accepted(self):
        result = resume_core.validateChange(
            BASE_RESUME,
            _operation(
                "AWS experience, six years.",
                requirement_ids=["req_aws"],
                fact_ids=["fact_aws_years"],
            ),
            JOB_MODEL,
            CAREER_FACTS,
            {},
        )

        self.assertEqual(result.get("status"), "ok", result)
        self.assertEqual(result["validated_operation"]["status"], "validated")

    def test_unrelated_years_figure_cannot_satisfy_subject_threshold(self):
        result = resume_core.validateChange(
            BASE_RESUME,
            _operation(
                "AWS experience, ten years.",
                requirement_ids=["req_aws"],
                fact_ids=["fact_java"],
            ),
            JOB_MODEL,
            [_fact("fact_java", "10 years of Java. AWS deployment familiarity.")],
            {},
        )

        self.assertEqual(result.get("status"), "rejected", result)
        self.assertIn("unsupported_years_claim", {error.get("code") for error in result.get("errors", [])})

    def test_one_provenanced_claim_does_not_silence_other_claims(self):
        resume = {
            "schema_version": "canonical-resume.v1",
            "resume_id": "resume_per_claim_provenance_regression",
            "source": {"kind": "unit"},
            "skills": [
                {
                    "value": "AWS",
                    "claim_id": "claim_aws",
                    "provenance": [{"source": "career_fact", "fact_id": "fact_aws"}],
                    "verification_state": "unknown",
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
            "provenance": [{"source": "resume", "text": "root provenance must not silence claim_node"}],
        }

        result = resume_core.validateGrounding(
            resume,
            [_fact("fact_aws", "AWS deployment ownership")],
            [],
            {},
        )

        self.assertEqual(result.get("status"), "fail", result)
        self.assertEqual(result.get("unsupported_claims"), [])
        self.assertEqual(
            [(item.get("field_path"), item.get("details", {}).get("claim_id")) for item in result["missing_provenance"]],
            [("/skills/1", "claim_node")],
        )

    def test_operation_mandatory_field_omission_matrix_rejects_validate_and_apply(self):
        for field_name, expected_code in MANDATORY_FIELD_CODES.items():
            with self.subTest(surface="validateChange", field_name=field_name):
                operation = _operation("Built React workflows.")
                del operation[field_name]

                result = resume_core.validateChange(BASE_RESUME, operation, JOB_MODEL, CAREER_FACTS, {})

                self.assertEqual(result.get("status"), "rejected", result)
                self.assertIn(expected_code, {error.get("code") for error in result.get("errors", [])})

            with self.subTest(surface="applyChange", field_name=field_name):
                operation = _validated_operation("replace")
                del operation[field_name]

                result = resume_core.applyChange(BASE_RESUME, operation)

                self.assertEqual(result.get("status"), "rejected", result)
                self.assertIn(expected_code, {error.get("code") for error in result.get("errors", [])})
                self.assertEqual(result["working_resume"], BASE_RESUME)

    def test_operation_apply_verb_matrix_has_defined_semantics(self):
        cases = {
            "replace": lambda resume: resume["basics"]["summary"] == "Built React and testing workflows.",
            "rewrite": lambda resume: resume["basics"]["summary"] == "Built React and testing workflows.",
            "insert": lambda resume: resume["skills"] == ["React", "AWS"],
            "remove": lambda resume: "tagline" not in resume["basics"],
            "move": lambda resume: "primary_skill" not in resume["basics"]
            and resume["basics"]["secondary_skill"] == "React",
        }
        for verb, assertion in cases.items():
            with self.subTest(verb=verb):
                original = copy.deepcopy(BASE_RESUME)

                result = resume_core.applyChange(original, _validated_operation(verb))

                self.assertEqual(result.get("status"), "ok", result)
                self.assertTrue(result["audit"]["applied"], result)
                self.assertTrue(assertion(result["working_resume"]), result)
                self.assertEqual(original, BASE_RESUME)

    def test_operation_status_transition_matrix_covers_legal_and_illegal_edges(self):
        expected = {
            "proposed": {"validated"},
            "validated": {"applied", "rejected"},
            "applied": {"accepted", "modified"},
            "rejected": set(),
            "accepted": set(),
            "modified": set(),
        }

        self.assertEqual(domain.CHANGE_OPERATION_STATUS_TRANSITIONS, expected)
        for from_status in sorted(expected):
            for to_status in sorted(expected):
                with self.subTest(from_status=from_status, to_status=to_status):
                    error = domain._operation_status_transition_error(from_status, to_status)
                    if to_status in expected[from_status]:
                        self.assertIsNone(error)
                    else:
                        self.assertEqual(error["code"], "invalid_status_transition")
                        self.assertEqual(error["details"]["from_status"], from_status)
                        self.assertEqual(error["details"]["to_status"], to_status)


if __name__ == "__main__":
    unittest.main()
