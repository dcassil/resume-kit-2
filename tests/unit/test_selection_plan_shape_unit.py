"""Unit coverage for deterministic content selection plan shape."""

from __future__ import annotations

import copy
import json
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


CANONICAL_RESUME = {
    "schema_version": "canonical-resume.v1",
    "resume_id": "selection_plan_unit_resume",
    "source": {"kind": "unit"},
    "basics": {"name": "Candidate"},
    "summary": "React platform engineer.",
    "experience": [
        {
            "id": "exp_react",
            "company": "Example SaaS",
            "title": "Engineer",
            "bullets": [
                "Built React interfaces.",
                "Designed API integrations.",
            ],
        },
        {
            "id": "exp_ops",
            "company": "Example Ops",
            "title": "Engineer",
            "bullets": ["Maintained internal tools."],
        },
    ],
    "skills": ["React", "TypeScript", "AWS"],
    "education": [],
}

JOB_MODEL = {
    "schema_version": "job-model.v1",
    "job_id": "selection_plan_unit_job",
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
}

CONFIG = {
    "resume": {
        "sectionOrder": ["summary", "skills", "experience", "projects", "education"],
        "experience": {"min": 0, "max": 2},
        "skills": {"min": 0, "max": 2},
        "bulletsPerRole": {"min": 0, "max": 4},
        "targetPages": 1,
    },
}


class SelectionPlanShapeUnitTests(unittest.TestCase):
    def _plan(self) -> dict:
        result = resume_core.rankResumeContent(CANONICAL_RESUME, JOB_MODEL, {"ignored": True}, CONFIG)
        self.assertEqual(result.get("status"), "ok", result)
        return result["selection_plan"]

    def test_content_selection_plan_has_required_shape(self):
        plan = self._plan()

        self.assertEqual(plan["schema_version"], "content-selection-plan.v1")
        self.assertEqual(plan["sections"], CONFIG["resume"]["sectionOrder"])
        self.assertTrue(plan["entries"])
        self.assertEqual(set(plan), {"schema_version", "sections", "entries", "constraint_report", "metadata"})

        actions = {entry["action"] for entry in plan["entries"]}
        self.assertTrue(actions <= {"keep", "drop", "reorder"})
        self.assertIn("drop", actions)
        for entry in plan["entries"]:
            with self.subTest(path=entry["path"]):
                self.assertEqual(
                    set(entry),
                    {"path", "action", "relevance", "reason", "requirement_ids", "fact_ids"},
                )
                self.assertTrue(entry["path"].startswith("/"))
                self.assertIsInstance(entry["relevance"], (int, float))
                self.assertIsInstance(entry["reason"], str)
                self.assertEqual(entry["requirement_ids"], [])
                self.assertEqual(entry["fact_ids"], [])

        bullet_paths = [entry["path"] for entry in plan["entries"] if "/bullets/" in entry["path"]]
        self.assertTrue(bullet_paths)

    def test_configured_section_order_is_honored(self):
        config = copy.deepcopy(CONFIG)
        config["resume"]["sectionOrder"] = ["skills", "summary", "projects", "experience", "education"]

        result = resume_core.rankResumeContent(CANONICAL_RESUME, JOB_MODEL, {"ignored": True}, config)

        self.assertEqual(result.get("status"), "ok", result)
        self.assertEqual(result["selection_plan"]["sections"], ["skills", "summary", "projects", "experience", "education"])

    def test_default_section_13_order_includes_projects_before_education(self):
        result = resume_core.rankResumeContent(CANONICAL_RESUME, JOB_MODEL, {"ignored": True}, {})

        self.assertEqual(result.get("status"), "ok", result)
        self.assertEqual(result["selection_plan"]["sections"], ["summary", "skills", "experience", "projects", "education"])

    def test_constraint_report_truthfully_records_skills_cap(self):
        plan = self._plan()

        constraints = {row["constraint"]: row for row in plan["constraint_report"]}
        self.assertEqual(
            constraints["resume.skills.max"],
            {"constraint": "resume.skills.max", "limit": 2, "actual": 3, "status": "violated"},
        )
        self.assertEqual(constraints["resume.skills.min"]["status"], "satisfied")
        self.assertEqual(constraints["resume.experience.max"]["status"], "satisfied")
        self.assertEqual(constraints["resume.experience.min"]["status"], "satisfied")
        self.assertEqual(constraints["resume.bulletsPerRole.max"]["status"], "satisfied")
        self.assertEqual(constraints["resume.bulletsPerRole.min"]["status"], "satisfied")
        self.assertEqual(plan["metadata"]["target_pages"], 1.0)
        self.assertEqual(plan["metadata"]["config_snapshot"], CONFIG["resume"])

    def test_rank_resume_content_preserves_input_resume_byte_identically(self):
        resume_before = json.dumps(CANONICAL_RESUME, sort_keys=True, separators=(",", ":"))
        resume_copy = copy.deepcopy(CANONICAL_RESUME)

        resume_core.rankResumeContent(resume_copy, JOB_MODEL, {"ignored": True}, CONFIG)

        resume_after = json.dumps(resume_copy, sort_keys=True, separators=(",", ":"))
        self.assertEqual(resume_after, resume_before)

    def test_rank_resume_content_is_deterministic(self):
        first = resume_core.rankResumeContent(CANONICAL_RESUME, JOB_MODEL, {"ignored": True}, CONFIG)
        second = resume_core.rankResumeContent(CANONICAL_RESUME, JOB_MODEL, {"ignored": True}, CONFIG)

        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
