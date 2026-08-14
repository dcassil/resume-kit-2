"""Unit coverage for MatchResult-driven content selection ranking."""

from __future__ import annotations

import copy
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()

from resume_core.selection_ranking import RELATED_RELEVANCE, RESOLVED_RELEVANCE, UNLINKED_RELEVANCE  # noqa: E402


CONFIG = {
    "resume": {
        "experience": {"min": 0, "max": 1},
        "skills": {"min": 0, "max": 1},
        "bulletsPerRole": {"min": 0, "max": 1},
    }
}


def _match(requirement_results: list[dict]) -> dict:
    return {
        "schema_version": "match-result.v1",
        "match_id": "match_selection_ranking_unit",
        "job_id": "job_selection_ranking_unit",
        "resume_id": "resume_selection_ranking_unit",
        "score": 0,
        "max_score": 0,
        "threshold": 0.7,
        "hardRequirementsResolved": True,
        "decision": "continue",
        "dimensions": [],
        "requirement_results": requirement_results,
    }


def _row(requirement_id: str, state: str, terms: list[str], fact_ids: list[str] | None = None) -> dict:
    return {
        "requirement_id": requirement_id,
        "classification": "required",
        "concept": " ".join(terms),
        "source_text": " ".join(terms),
        "normalized_terms": terms,
        "resolution_state": state,
        "score": 1,
        "max_score": 1,
        "matched_fact_ids": fact_ids or [],
        "blocking": False,
        "unresolved": False,
        "evidence": [{"source": "resume", "terms": terms}],
    }


class SelectionRankingUnitTests(unittest.TestCase):
    def test_resolution_state_flip_changes_ranking_and_identical_inputs_are_deterministic(self):
        resume = {
            "schema_version": "canonical-resume.v1",
            "resume_id": "resume_selection_ranking_unit",
            "source": {"kind": "unit"},
            "experience": [
                {
                    "id": "exp_react",
                    "start_date": "2020-01",
                    "end_date": "2021-01",
                    "bullets": ["Built React interfaces."],
                },
                {
                    "id": "exp_graphql",
                    "start_date": "2024-01",
                    "end_date": "2025-01",
                    "bullets": ["Built GraphQL services."],
                },
            ],
            "skills": [],
            "education": [],
        }
        job = {"schema_version": "job-model.v1", "job_id": "job_selection_ranking_unit", "requirements": []}
        react_exact = _match(
            [
                _row("req_react", "exact_match", ["react"]),
                _row("req_graphql", "possible_match", ["graphql"]),
            ]
        )
        graphql_exact = _match(
            [
                _row("req_react", "possible_match", ["react"]),
                _row("req_graphql", "exact_match", ["graphql"]),
            ]
        )

        first = resume_core.rankResumeContent(copy.deepcopy(resume), job, react_exact, CONFIG)
        repeated = resume_core.rankResumeContent(copy.deepcopy(resume), job, react_exact, CONFIG)
        flipped = resume_core.rankResumeContent(copy.deepcopy(resume), job, graphql_exact, CONFIG)

        self.assertEqual(first, repeated)
        self.assertEqual(_kept_paths(first), ["/experience/0/bullets/0"])
        self.assertEqual(_kept_paths(flipped), ["/experience/1/bullets/0"])
        self.assertNotEqual(first["ranked_content"], flipped["ranked_content"])
        self.assertEqual(_entry(first, "/experience/0/bullets/0")["relevance"], RESOLVED_RELEVANCE)
        self.assertEqual(_entry(first, "/experience/1/bullets/0")["relevance"], RELATED_RELEVANCE)

    def test_max_overflow_drops_by_match_result_relevance_not_source_order(self):
        resume = {
            "schema_version": "canonical-resume.v1",
            "resume_id": "resume_selection_ranking_unit",
            "source": {"kind": "unit"},
            "experience": [],
            "skills": ["React", "AWS"],
            "education": [],
        }
        job = {"schema_version": "job-model.v1", "job_id": "job_selection_ranking_unit", "requirements": []}
        match = _match(
            [
                _row("req_react", "possible_match", ["react"]),
                _row("req_aws", "verified_fact_match", ["aws"], ["fact_aws"]),
            ]
        )

        result = resume_core.rankResumeContent(resume, job, match, CONFIG)

        self.assertEqual(_entry(result, "/skills/1")["action"], "keep")
        self.assertEqual(_entry(result, "/skills/0")["action"], "drop")
        self.assertEqual(_entry(result, "/skills/1")["requirement_ids"], ["req_aws"])
        self.assertEqual(_entry(result, "/skills/1")["fact_ids"], ["fact_aws"])
        self.assertEqual(_entry(result, "/skills/1")["relevance"], RESOLVED_RELEVANCE)

    def test_claim_field_refs_link_without_term_fuzzy_matching(self):
        resume = {
            "schema_version": "canonical-resume.v1",
            "resume_id": "resume_selection_ranking_unit",
            "source": {"kind": "unit"},
            "experience": [
                {
                    "id": "exp_cloud",
                    "bullets": [
                        {
                            "value": "Built cloud platform automation.",
                            "claim_id": "claim_cloud_platform",
                            "provenance": [{"claim_id": "claim_cloud_platform", "source": "resume", "text": "cloud platform"}],
                        }
                    ],
                }
            ],
            "skills": [],
            "education": [],
        }
        job = {"schema_version": "job-model.v1", "job_id": "job_selection_ranking_unit", "requirements": []}
        match = _match(
            [
                {
                    **_row("req_kubernetes", "exact_match", ["kubernetes"]),
                    "evidence": [{"source": "resume", "claim_id": "claim_cloud_platform"}],
                }
            ]
        )

        result = resume_core.rankResumeContent(resume, job, match, CONFIG)
        entry = _entry(result, "/experience/0/bullets/0")

        self.assertEqual(entry["relevance"], RESOLVED_RELEVANCE)
        self.assertEqual(entry["requirement_ids"], ["req_kubernetes"])

    def test_unlinked_content_uses_recency_then_source_order(self):
        resume = {
            "schema_version": "canonical-resume.v1",
            "resume_id": "resume_selection_ranking_unit",
            "source": {"kind": "unit"},
            "experience": [
                {"id": "exp_old", "end_date": "2020-01", "bullets": ["Maintained tools."]},
                {"id": "exp_new", "end_date": "2024-01", "bullets": ["Maintained tools."]},
            ],
            "skills": ["React", "AWS"],
            "education": [],
        }
        job = {"schema_version": "job-model.v1", "job_id": "job_selection_ranking_unit", "requirements": []}

        result = resume_core.rankResumeContent(resume, job, _match([]), CONFIG)

        self.assertEqual(_kept_paths(result), ["/experience/1/bullets/0", "/skills/0"])
        self.assertTrue(all(entry["relevance"] == UNLINKED_RELEVANCE for entry in result["selection_plan"]["entries"]))


def _entry(result: dict, path: str) -> dict:
    matches = [entry for entry in result["selection_plan"]["entries"] if entry["path"] == path]
    assert len(matches) == 1
    return matches[0]


def _kept_paths(result: dict) -> list[str]:
    return [entry["path"] for entry in result["selection_plan"]["entries"] if entry["action"] == "keep"]


if __name__ == "__main__":
    unittest.main()
