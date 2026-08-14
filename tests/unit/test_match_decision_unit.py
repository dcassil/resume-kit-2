"""Unit coverage for MatchResult decision semantics."""

from __future__ import annotations

import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


def _resume() -> dict:
    return {
        "schema_version": "canonical-resume.v1",
        "resume_id": "resume_match_decision_unit",
        "source": {"kind": "unit"},
        "summary": "Built REST API services and React interfaces.",
        "experience": [],
        "skills": ["React"],
        "education": [],
    }


def _job(requirements: list[dict]) -> dict:
    return {
        "schema_version": "job-model.v1",
        "job_id": "job_match_decision_unit",
        "requirements": requirements,
        "preferred": [],
    }


def _required(requirement_id: str, concept: str, terms: list[str] | None = None, weight: float = 10.0) -> dict:
    return {
        "requirement_id": requirement_id,
        "classification": "required",
        "concept": concept,
        "weight": weight,
        "source_text": concept,
        "normalized_terms": terms or [concept.lower()],
    }


class MatchDecisionUnitTests(unittest.TestCase):
    def test_decide_match_matrix(self):
        from resume_core.domain import decide_match
        from resume_core.matching_config import resolve_matching_config

        strict = resolve_matching_config({"matching": {"requireHardRequirementsResolved": True}}).config
        permissive = resolve_matching_config({"matching": {"requireHardRequirementsResolved": False}}).config

        cases = [
            (10.0, 7.5, False, strict, "blocked"),
            (5.0, 7.5, False, strict, "blocked"),
            (5.0, 7.5, True, strict, "resolve_gaps"),
            (5.0, 7.5, False, permissive, "resolve_gaps"),
            (7.5, 7.5, True, strict, "continue"),
            (8.0, 7.5, False, permissive, "continue"),
        ]
        for score, threshold, hard_resolved, config, expected in cases:
            with self.subTest(score=score, threshold=threshold, hard_resolved=hard_resolved, expected=expected):
                self.assertEqual(decide_match(score, threshold, hard_resolved, config), expected)

    def test_score_match_blocks_unresolved_required_when_documented_hard_gate_is_enabled(self):
        result = resume_core.scoreMatch(
            _resume(),
            _job([_required("req_node", "Node.js")]),
            [],
            {"matching": {"requireHardRequirementsResolved": True, "scoreAutoThreshold": 7.5}},
        )

        self.assertEqual(result["status"], "ok", result)
        match = result["match_result"]
        self.assertEqual(match["threshold"], 7.5)
        self.assertFalse(match["hardRequirementsResolved"])
        self.assertEqual(match["decision"], "blocked")
        self.assertFalse(match["can_continue"])
        self.assertEqual(match["can_continue"], match["decision"] == "continue")

    def test_low_score_without_required_blocker_routes_to_resolve_gaps(self):
        result = resume_core.scoreMatch(
            _resume(),
            _job([_required("req_react", "React")]),
            [],
            {"matching": {"scoreAutoThreshold": 15.0, "requireHardRequirementsResolved": True}},
        )

        match = result["match_result"]
        self.assertTrue(match["hardRequirementsResolved"])
        self.assertEqual(match["decision"], "resolve_gaps")
        self.assertFalse(match["can_continue"])
        self.assertEqual(match["can_continue"], match["decision"] == "continue")

    def test_met_threshold_with_required_resolved_continues(self):
        result = resume_core.scoreMatch(
            _resume(),
            _job([_required("req_react", "React")]),
            [],
            {"matching": {"scoreAutoThreshold": 7.5, "requireHardRequirementsResolved": True}},
        )

        match = result["match_result"]
        self.assertTrue(match["hardRequirementsResolved"])
        self.assertEqual(match["decision"], "continue")
        self.assertTrue(match["can_continue"])
        self.assertEqual(match["can_continue"], match["decision"] == "continue")

    def test_related_and_possible_do_not_resolve_hard_requirements(self):
        result = resume_core.scoreMatch(
            _resume(),
            _job(
                [
                    _required("req_graphql", "GraphQL"),
                    _required("req_react_native", "React Native", ["react native"]),
                ]
            ),
            [],
            {"matching": {"requireHardRequirementsResolved": True}},
        )

        match = result["match_result"]
        states = {item["requirement_id"]: item["resolution_state"] for item in match["requirement_results"]}
        self.assertEqual(states["req_graphql"], "related_match")
        self.assertEqual(states["req_react_native"], "possible_match")
        self.assertFalse(match["hardRequirementsResolved"])
        self.assertEqual(match["decision"], "blocked")
        self.assertFalse(match["can_continue"])


if __name__ == "__main__":
    unittest.main()
