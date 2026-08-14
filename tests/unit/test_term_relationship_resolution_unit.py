"""Unit coverage for caller-supplied term relationship resolution."""

from __future__ import annotations

import copy
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


def _resume(summary: str) -> dict:
    return {
        "schema_version": "canonical-resume.v1",
        "resume_id": "resume_term_relationship_unit",
        "source": {"kind": "unit"},
        "summary": summary,
        "experience": [],
        "skills": [],
        "education": [],
    }


def _requirement(requirement_id: str, concept: str, terms: list[str] | None = None) -> dict:
    return {
        "requirement_id": requirement_id,
        "classification": "required",
        "concept": concept,
        "importance": "high",
        "weight": 1.0,
        "source_text": concept,
        "normalized_terms": terms or [concept.lower()],
    }


def _job(*requirements: dict) -> dict:
    return {
        "schema_version": "job-model.v1",
        "job_id": "job_term_relationship_unit",
        "requirements": list(requirements),
        "preferred": [],
    }


def _relationship(from_term: str, to_term: str, kind: str) -> dict:
    return {
        "from": from_term,
        "to": to_term,
        "kind": kind,
        "provenance": {"source": "unit"},
    }


def _result_by_id(match_result: dict) -> dict[str, dict]:
    return {item["requirement_id"]: item for item in match_result["requirement_results"]}


class TermRelationshipResolutionUnitTests(unittest.TestCase):
    def test_supplied_alias_resolves_at_alias_rung(self):
        result = resume_core.scoreMatch(
            _resume("Built Vue dashboards."),
            _job(_requirement("req_angular", "Angular")),
            [],
            {},
            [_relationship("Vue", "Angular", "alias")],
        )["match_result"]

        requirement = _result_by_id(result)["req_angular"]
        self.assertEqual(requirement["resolution_state"], "alias_match")
        self.assertEqual(requirement["score"], 1.0)
        self.assertTrue(result["hardRequirementsResolved"])

    def test_related_azure_to_aws_does_not_exact_match_or_resolve_hard_requirement(self):
        result = resume_core.scoreMatch(
            _resume("Built Azure cloud services."),
            _job(_requirement("req_aws", "AWS")),
            [],
            {},
            [_relationship("Azure", "AWS", "related")],
        )["match_result"]

        requirement = _result_by_id(result)["req_aws"]
        self.assertEqual(requirement["resolution_state"], "related_match")
        self.assertNotEqual(requirement["resolution_state"], "exact_match")
        self.assertEqual(requirement["score"], 0.0)
        self.assertTrue(requirement["blocking"])
        self.assertFalse(result["hardRequirementsResolved"])
        self.assertEqual(result["unresolved_requirement_ids"], ["req_aws"])

    def test_parent_and_child_kinds_resolve_only_at_related_rung(self):
        for kind in ["parent", "child"]:
            with self.subTest(kind=kind):
                result = resume_core.scoreMatch(
                    _resume("Built queueing systems."),
                    _job(_requirement("req_event_architecture", "Event Architecture", ["event architecture"])),
                    [],
                    {},
                    [_relationship("queueing systems", "event architecture", kind)],
                )["match_result"]

                requirement = _result_by_id(result)["req_event_architecture"]
                self.assertEqual(requirement["resolution_state"], "related_match")
                self.assertEqual(requirement["score"], 0.0)
                self.assertTrue(requirement["blocking"])

    def test_contradicts_blocks_positive_resolution_for_the_pair(self):
        result = resume_core.scoreMatch(
            _resume("Built Vue dashboards."),
            _job(_requirement("req_angular", "Angular")),
            [],
            {},
            [
                _relationship("Vue", "Angular", "alias"),
                _relationship("Vue", "Angular", "contradicts"),
            ],
        )["match_result"]

        requirement = _result_by_id(result)["req_angular"]
        self.assertEqual(requirement["resolution_state"], "unknown")
        self.assertEqual(requirement["score"], 0.0)
        self.assertTrue(requirement["blocking"])

    def test_relationship_order_does_not_change_match_result(self):
        relationships = [
            _relationship("Vue", "Angular", "alias"),
            _relationship("Azure", "AWS", "related"),
            _relationship("Ember", "Angular", "contradicts"),
        ]
        resume = _resume("Built Vue dashboards and Azure cloud services.")
        job = _job(_requirement("req_angular", "Angular"), _requirement("req_aws", "AWS"))

        first = resume_core.scoreMatch(copy.deepcopy(resume), copy.deepcopy(job), [], {}, copy.deepcopy(relationships))
        second = resume_core.scoreMatch(copy.deepcopy(resume), copy.deepcopy(job), [], {}, list(reversed(copy.deepcopy(relationships))))

        self.assertEqual(first, second)

    def test_invalid_relationship_kind_and_missing_field_are_rejected(self):
        unknown_kind = resume_core.scoreMatch(
            _resume("Built Vue dashboards."),
            _job(_requirement("req_angular", "Angular")),
            [],
            {},
            [_relationship("Vue", "Angular", "equivalent")],
        )
        missing_field = resume_core.scoreMatch(
            _resume("Built Vue dashboards."),
            _job(_requirement("req_angular", "Angular")),
            [],
            {},
            [{"from": "Vue", "to": "Angular", "kind": "alias"}],
        )

        self.assertEqual(unknown_kind["status"], "rejected")
        self.assertEqual(missing_field["status"], "rejected")
        self.assertEqual(unknown_kind["errors"][0]["code"], "invalid_term_relationship_kind")
        self.assertEqual(missing_field["errors"][0]["code"], "missing_term_relationship_field")


if __name__ == "__main__":
    unittest.main()
