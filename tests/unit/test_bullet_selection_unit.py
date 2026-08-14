"""Unit coverage for bullet-level selection planning invariants."""

from __future__ import annotations

import copy
import json
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()

from resume_core.resume_config import resolve_resume_config  # noqa: E402
from resume_core.selection_plan import (  # noqa: E402
    MAX_CONSTRAINT_OVERFLOW,
    MATCH_RELEVANCE_KEEP,
    UNLINKED_FILL,
    UNLINKED_LOW_RELEVANCE,
    build_content_selection_plan,
)
from resume_core.selection_ranking import RESOLVED_RELEVANCE, UNLINKED_RELEVANCE  # noqa: E402


JOB_MODEL = {"schema_version": "job-model.v1", "job_id": "job_bullet_selection_unit", "requirements": []}


def _match(requirement_results: list[dict]) -> dict:
    return {
        "schema_version": "match-result.v1",
        "match_id": "match_bullet_selection_unit",
        "job_id": "job_bullet_selection_unit",
        "resume_id": "resume_bullet_selection_unit",
        "score": 0,
        "max_score": 0,
        "threshold": 0.7,
        "hardRequirementsResolved": True,
        "decision": "continue",
        "dimensions": [],
        "requirement_results": requirement_results,
    }


def _row(requirement_id: str, terms: list[str], fact_ids: list[str] | None = None) -> dict:
    return {
        "requirement_id": requirement_id,
        "classification": "required",
        "concept": " ".join(terms),
        "source_text": " ".join(terms),
        "normalized_terms": terms,
        "resolution_state": "verified_fact_match" if fact_ids else "exact_match",
        "score": 1,
        "max_score": 1,
        "matched_fact_ids": fact_ids or [],
        "blocking": False,
        "unresolved": False,
        "evidence": [{"source": "resume", "terms": terms, "fact_id": fact_ids[0]}] if fact_ids else [{"source": "resume", "terms": terms}],
    }


def _config(*, experience_max: int | None = None, skills_max: int | None = None, bullets_min: int = 0, bullets_max: int | None = None) -> dict:
    resume_config: dict = {
        "experience": {"min": 0},
        "skills": {"min": 0},
        "bulletsPerRole": {"min": bullets_min},
    }
    if experience_max is not None:
        resume_config["experience"]["max"] = experience_max
    if skills_max is not None:
        resume_config["skills"]["max"] = skills_max
    if bullets_max is not None:
        resume_config["bulletsPerRole"]["max"] = bullets_max
    return {"resume": resume_config}


class BulletSelectionUnitTests(unittest.TestCase):
    def test_per_role_max_keeps_highest_relevance_then_original_bullet_order(self):
        resume = {
            "schema_version": "canonical-resume.v1",
            "resume_id": "resume_bullet_selection_unit",
            "source": {"kind": "unit"},
            "experience": [
                {
                    "id": "exp_react",
                    "bullets": [
                        "Maintained internal tools.",
                        "Built React interfaces.",
                        "Built React design systems.",
                    ],
                }
            ],
            "skills": [],
            "education": [],
        }

        result = resume_core.rankResumeContent(resume, JOB_MODEL, _match([_row("req_react", ["react"])]), _config(experience_max=1, bullets_max=1))

        self.assertEqual(result["status"], "ok", result)
        entries = {entry["path"]: entry for entry in result["selection_plan"]["entries"]}
        self.assertEqual(entries["/experience/0/bullets/1"]["action"], "keep")
        self.assertEqual(entries["/experience/0/bullets/1"]["reason"], MATCH_RELEVANCE_KEEP)
        self.assertEqual(entries["/experience/0/bullets/2"]["action"], "drop")
        self.assertEqual(entries["/experience/0/bullets/2"]["reason"], MAX_CONSTRAINT_OVERFLOW)
        self.assertEqual(entries["/experience/0/bullets/0"]["action"], "drop")
        self.assertEqual(entries["/experience/0/bullets/0"]["reason"], UNLINKED_LOW_RELEVANCE)

    def test_min_bullets_per_role_reports_role_deficits(self):
        resume = {
            "schema_version": "canonical-resume.v1",
            "resume_id": "resume_bullet_selection_unit",
            "source": {"kind": "unit"},
            "experience": [
                {"id": "exp_short", "bullets": ["Maintained tools."]},
                {"id": "exp_full", "bullets": ["Built React.", "Built APIs."]},
            ],
            "skills": [],
            "education": [],
        }

        result = resume_core.rankResumeContent(resume, JOB_MODEL, _match([]), _config(experience_max=2, bullets_min=2))

        constraints = {row["constraint"]: row for row in result["selection_plan"]["constraint_report"]}
        self.assertEqual(constraints["min_bullets_per_role"]["status"], "deficit")
        self.assertEqual(
            constraints["min_bullets_per_role"]["role_deficits"],
            [{"role_index": 0, "role_id": "exp_short", "path": "/experience/0/bullets", "limit": 2, "actual": 1}],
        )

    def test_no_empty_reasons_and_match_derived_entries_have_requirement_traceability(self):
        resume = {
            "schema_version": "canonical-resume.v1",
            "resume_id": "resume_bullet_selection_unit",
            "source": {"kind": "unit"},
            "experience": [
                {
                    "id": "exp_react",
                    "bullets": [
                        "Built React interfaces.",
                        "Maintained internal tools.",
                    ],
                }
            ],
            "skills": ["React", "Operations"],
            "education": [],
        }

        result = resume_core.rankResumeContent(
            resume,
            JOB_MODEL,
            _match([_row("req_react", ["react"], ["fact_react"])]),
            _config(experience_max=1, skills_max=2, bullets_max=2),
        )

        entries = result["selection_plan"]["entries"]
        self.assertTrue(entries)
        self.assertTrue(all(entry["reason"] for entry in entries))
        for entry in entries:
            with self.subTest(path=entry["path"]):
                if entry["relevance"] > UNLINKED_RELEVANCE:
                    self.assertEqual(entry["reason"], MATCH_RELEVANCE_KEEP)
                    self.assertEqual(entry["requirement_ids"], ["req_react"])
                    self.assertEqual(entry["fact_ids"], ["fact_react"])
                else:
                    self.assertIn(entry["reason"], {UNLINKED_FILL, UNLINKED_LOW_RELEVANCE})
                    self.assertEqual(entry["requirement_ids"], [])

    def test_agent_proposed_over_max_ranked_input_cannot_exceed_configured_maxima(self):
        resume = {
            "schema_version": "canonical-resume.v1",
            "resume_id": "resume_bullet_selection_unit",
            "source": {"kind": "unit"},
            "experience": [
                {"id": "exp_0", "bullets": ["React one.", "React two."]},
                {"id": "exp_1", "bullets": ["React three.", "React four."]},
            ],
            "skills": ["React", "TypeScript"],
            "education": [],
        }
        agent_ranked = [
            {"kind": "experience", "id": "exp_0", "source_index": 0, "score": RESOLVED_RELEVANCE},
            {"kind": "experience", "id": "exp_1", "source_index": 1, "score": RESOLVED_RELEVANCE},
            {"kind": "skill", "id": "skill_0", "source_index": 0, "score": RESOLVED_RELEVANCE},
            {"kind": "skill", "id": "skill_1", "source_index": 1, "score": RESOLVED_RELEVANCE},
        ]
        entry_relevance = {
            "/experience/0": _relevance(["req_role_0"], "experience/0"),
            "/experience/1": _relevance(["req_role_1"], "experience/1"),
            "/experience/0/bullets/0": _relevance(["req_bullet_0"], "experience/0/bullets/0"),
            "/experience/0/bullets/1": _relevance(["req_bullet_1"], "experience/0/bullets/1"),
            "/experience/1/bullets/0": _relevance(["req_bullet_2"], "experience/1/bullets/0"),
            "/experience/1/bullets/1": _relevance(["req_bullet_3"], "experience/1/bullets/1"),
            "/skills/0": _relevance(["req_skill_0"], "skills/0"),
            "/skills/1": _relevance(["req_skill_1"], "skills/1"),
        }
        config = resolve_resume_config(_config(experience_max=1, skills_max=1, bullets_max=1)).config

        plan, _ranked = build_content_selection_plan(resume, agent_ranked, entry_relevance, config)

        kept = [entry for entry in plan["entries"] if entry["action"] == "keep"]
        kept_bullets_by_role = _kept_bullets_by_role(kept)
        self.assertLessEqual(len([entry for entry in kept if entry["path"].startswith("/skills/")]), 1)
        self.assertEqual(set(kept_bullets_by_role), {0})
        self.assertLessEqual(kept_bullets_by_role[0], 1)

    def test_bullet_granularity_is_deterministic_and_preserves_input_resume(self):
        resume = {
            "schema_version": "canonical-resume.v1",
            "resume_id": "resume_bullet_selection_unit",
            "source": {"kind": "unit"},
            "experience": [
                {
                    "id": "exp_react",
                    "bullets": [
                        "Built React interfaces.",
                        "Built React design systems.",
                    ],
                }
            ],
            "skills": ["React"],
            "education": [],
        }
        before = json.dumps(resume, sort_keys=True, separators=(",", ":"))

        first = resume_core.rankResumeContent(copy.deepcopy(resume), JOB_MODEL, _match([_row("req_react", ["react"])]), _config(bullets_max=1))
        second = resume_core.rankResumeContent(copy.deepcopy(resume), JOB_MODEL, _match([_row("req_react", ["react"])]), _config(bullets_max=1))

        self.assertEqual(first, second)
        self.assertEqual(json.dumps(resume, sort_keys=True, separators=(",", ":")), before)
        self.assertIn("/experience/0/bullets/0", [entry["path"] for entry in first["selection_plan"]["entries"]])


def _relevance(requirement_ids: list[str], path: str) -> dict:
    return {
        "relevance": RESOLVED_RELEVANCE,
        "requirement_ids": requirement_ids,
        "fact_ids": [],
        "rank_key": (-RESOLVED_RELEVANCE, 0, 0, 0, 0, path),
    }


def _kept_bullets_by_role(entries: list[dict]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for entry in entries:
        parts = entry["path"].split("/")
        if len(parts) >= 5 and parts[1] == "experience" and parts[3] == "bullets":
            role_index = int(parts[2])
            counts[role_index] = counts.get(role_index, 0) + 1
    return counts


if __name__ == "__main__":
    unittest.main()
