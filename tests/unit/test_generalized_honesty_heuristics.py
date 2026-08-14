"""Unit coverage for generalized resume-core honesty heuristics."""

from __future__ import annotations

import copy
import importlib
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()
domain = importlib.import_module("resume_core.domain")


BASE_RESUME = {
    "schema_version": "canonical-resume.v1",
    "resume_id": "resume_generalized_honesty_unit",
    "source": {"kind": "unit"},
    "basics": {"summary": "Built React workflows."},
    "experience": [
        {
            "company": "Example",
            "title": "Senior Software Engineer",
            "bullets": ["Built React workflows.", "Led a small team."],
        }
    ],
    "skills": ["React", "Azure"],
    "education": [],
    "provenance": [{"source": "unit", "text": "React"}],
    "verification_state": "source_stated",
}

JOB_MODEL = {
    "schema_version": "job-model.v1",
    "job_id": "job_generalized_honesty_unit",
    "requirements": [
        {
            "requirement_id": "req_general",
            "classification": "required",
            "concept": "General evidence",
            "importance": "high",
            "weight": 10,
            "source_text": "General evidence",
            "normalized_terms": ["general"],
        }
    ],
    "preferred": [],
    "industries": [],
    "domains": [],
    "terminology": [],
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


def _operation(after, *, before="Built React workflows.", path="/basics/summary", fact_ids=None):
    return {
        "schema_version": "resume-change-operation.v1",
        "operation_id": "op_generalized_honesty",
        "status": "proposed",
        "op": "replace",
        "path": path,
        "before": before,
        "after": after,
        "reason": "Exercise generalized honesty heuristics.",
        "linked_requirement_ids": ["req_general"],
        "linked_fact_ids": fact_ids or ["fact_support"],
        "provenance": [{"source": "unit"}],
    }


def _validate(after, facts, *, before="Built React workflows.", path="/basics/summary", resume=None, fact_ids=None):
    return resume_core.validateChange(
        resume or BASE_RESUME,
        _operation(after, before=before, path=path, fact_ids=fact_ids),
        JOB_MODEL,
        facts,
        {},
    )


class GuardedTermsNeutralizer:
    def __enter__(self):
        self.original = copy.deepcopy(domain._GUARDED_TERMS)
        domain._GUARDED_TERMS.clear()

    def __exit__(self, exc_type, exc, tb):
        domain._GUARDED_TERMS.clear()
        domain._GUARDED_TERMS.update(self.original)


class GeneralizedHonestyHeuristicTests(unittest.TestCase):
    def assert_rejected_claim(self, result, claim):
        self.assertEqual(result.get("status"), "rejected", result)
        unsupported = [
            error
            for error in result.get("errors", [])
            if error.get("code") == "unsupported_guarded_claim"
        ]
        self.assertTrue(unsupported, result)
        claims = set().union(*(set(error.get("details", {}).get("claims", [])) for error in unsupported))
        self.assertIn(claim, claims, result)

    def test_audit_fabrications_reject_with_guarded_terms_neutralized(self):
        with GuardedTermsNeutralizer():
            scale = _validate("Served 50 million users daily.", [_fact("fact_support", "Built React workflows.")])
            self.assert_rejected_claim(scale, "quantity:50000000:user")

            title = _validate(
                "Principal Engineer leading 100 people.",
                [_fact("fact_support", "Formal employment title was Senior Software Engineer.")],
                before="Senior Software Engineer",
                path="/experience/0/title",
            )
            self.assertEqual(title.get("status"), "rejected", title)
            self.assertIn("title_inflation", {error.get("code") for error in title.get("errors", [])})

            skill = _validate("Kubernetes expert.", [_fact("fact_support", "Built React workflows.")])
            self.assert_rejected_claim(skill, "skill:kubernetes")

    def test_original_guarded_fixture_behaviors_reject_with_lookup_neutralized(self):
        cases = [
            ("AWS", [_fact("fact_support", "Azure cloud services.")], "skill:aws"),
            ("GraphQL", [_fact("fact_support", "REST API design.")], "skill:graphql"),
            (
                "Architected React platforms serving 20 million users globally.",
                [_fact("fact_support", "Built React applications.")],
                "quantity:20000000:user",
            ),
            (
                "Managed 30 engineers across multiple delivery teams.",
                [_fact("fact_support", "Led a small team of three developers.")],
                "quantity:30:engineer",
            ),
        ]
        with GuardedTermsNeutralizer():
            for after, facts, claim in cases:
                with self.subTest(after=after):
                    self.assert_rejected_claim(_validate(after, facts), claim)

            staff = _validate(
                "Staff Software Engineer",
                [_fact("fact_support", "Formal employment title was Senior Software Developer, not Staff Software Engineer.")],
                before="Senior Software Developer",
                path="/experience/0/title",
            )
            self.assertEqual(staff.get("status"), "rejected", staff)
            self.assertIn("title_inflation", {error.get("code") for error in staff.get("errors", [])})

    def test_quantity_claims_normalize_words_digits_and_require_compatible_fact_quantity(self):
        supported = _validate(
            "Served fifty million users daily.",
            [_fact("fact_support", "Served 50000000 users daily.")],
        )
        self.assertEqual(supported.get("status"), "ok", supported)

        rejected = _validate(
            "Served 50 million users daily.",
            [_fact("fact_support", "Served 5 million users daily.")],
        )
        self.assert_rejected_claim(rejected, "quantity:50000000:user")

    def test_title_ladder_rejects_inflation_and_allows_evidenced_or_lower_rung(self):
        resume = copy.deepcopy(BASE_RESUME)
        resume["experience"][0]["title"] = "Engineer"
        supported = _validate(
            "Senior Software Engineer",
            [_fact("fact_support", "Formal employment title was Senior Software Engineer.")],
            before="Engineer",
            path="/experience/0/title",
            resume=resume,
        )
        self.assertEqual(supported.get("status"), "ok", supported)

        inflated = _validate(
            "Principal Software Engineer",
            [_fact("fact_support", "Formal employment title was Senior Software Engineer.")],
            before="Senior Software Engineer",
            path="/experience/0/title",
        )
        self.assertEqual(inflated.get("status"), "rejected", inflated)
        self.assertIn("title_inflation", {error.get("code") for error in inflated.get("errors", [])})

    def test_year_claims_normalize_words_digits_and_scope_to_subject(self):
        supported = _validate(
            "AWS experience, six years.",
            [_fact("fact_support", "6 years of AWS.")],
        )
        self.assertEqual(supported.get("status"), "ok", supported)

        rejected = _validate(
            "AWS experience, ten years.",
            [_fact("fact_support", "10 years of React. AWS deployment familiarity.")],
        )
        self.assertEqual(rejected.get("status"), "rejected", rejected)
        self.assertIn("unsupported_years_claim", {error.get("code") for error in rejected.get("errors", [])})

    def test_structured_negation_rejects_without_not_substring_false_positive(self):
        negated = _validate("AWS", [_fact("fact_support", "AWS", negated=True)])
        self.assert_rejected_claim(negated, "skill:aws")

        incidental_not = _validate("AWS", [_fact("fact_support", "Not only AWS, also Lambda.")])
        self.assertEqual(incidental_not.get("status"), "ok", incidental_not)


if __name__ == "__main__":
    unittest.main()
