"""Unit coverage for section-13 resume config resolution."""

from __future__ import annotations

import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()

from resume_core.resume_config import DEFAULT_SECTION_ORDER, resolve_resume_config  # noqa: E402


CANONICAL_RESUME = {
    "schema_version": "canonical-resume.v1",
    "resume_id": "resume_config_unit_resume",
    "source": {"kind": "unit"},
    "basics": {"name": "Candidate"},
    "summary": "React platform engineer.",
    "experience": [
        {
            "id": "exp_react",
            "company": "Example SaaS",
            "title": "Engineer",
            "bullets": ["Built React interfaces.", "Designed API integrations.", "Led testing improvements."],
        },
        {
            "id": "exp_ops",
            "company": "Example Ops",
            "title": "Engineer",
            "bullets": ["Maintained tools."],
        },
    ],
    "skills": ["React", "TypeScript", "AWS"],
    "education": [],
}

JOB_MODEL = {
    "schema_version": "job-model.v1",
    "job_id": "resume_config_unit_job",
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


class ResumeConfigUnitTests(unittest.TestCase):
    def test_defaults_are_single_source_and_use_section_13_order(self):
        result = resolve_resume_config({})

        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.config.section_order, DEFAULT_SECTION_ORDER)
        self.assertEqual(
            result.config.to_dict(),
            {
                "targetPages": None,
                "skills": {"min": 0, "max": None},
                "experience": {"min": 0, "max": None},
                "bulletsPerRole": {"min": 0, "max": None},
                "sectionOrder": ["summary", "skills", "experience", "projects", "education"],
            },
        )

    def test_unknown_resume_namespace_key_is_typed_error(self):
        result = resolve_resume_config({"resume": {"unexpected": True}})

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "unknown_resume_config_key")
        self.assertEqual(result.errors[0]["field_path"], "resume.unexpected")

    def test_unknown_nested_range_key_is_typed_error(self):
        result = resolve_resume_config({"resume": {"skills": {"minimum": 2}}})

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "unknown_resume_config_key")
        self.assertEqual(result.errors[0]["field_path"], "resume.skills.minimum")

    def test_invalid_section_order_rejects_basics_as_configurable_section(self):
        result = resolve_resume_config({"resume": {"sectionOrder": ["basics", "summary"]}})

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "invalid_resume_config_value")
        self.assertEqual(result.errors[0]["field_path"], "resume.sectionOrder.0")

    def test_removed_flat_skills_max_is_typed_unknown_key_error(self):
        removed_key = "max_" + "skills"
        result = resume_core.rankResumeContent(CANONICAL_RESUME, JOB_MODEL, {}, {removed_key: 2})

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["errors"][0]["code"], "unknown_resume_config_key")
        self.assertEqual(result["errors"][0]["field_path"], removed_key)
        self.assertEqual(result["warnings"], [])

    def test_min_deficits_are_reported_without_fabricating_content(self):
        result = resume_core.rankResumeContent(
            CANONICAL_RESUME,
            JOB_MODEL,
            {},
            {"resume": {"skills": {"min": 4}, "experience": {"min": 3}, "bulletsPerRole": {"min": 2}}},
        )

        self.assertEqual(result["status"], "ok", result)
        constraints = {row["constraint"]: row for row in result["selection_plan"]["constraint_report"]}
        self.assertEqual(constraints["resume.skills.min"]["status"], "deficit")
        self.assertEqual(constraints["resume.skills.min"]["actual"], 3)
        self.assertEqual(constraints["resume.experience.min"]["status"], "deficit")
        self.assertEqual(constraints["resume.experience.min"]["actual"], 2)
        self.assertEqual(constraints["resume.bulletsPerRole.min"]["status"], "deficit")
        self.assertEqual(constraints["resume.bulletsPerRole.min"]["actual"], 1)
        self.assertEqual(len([entry for entry in result["selection_plan"]["entries"] if entry["path"].startswith("/skills/")]), 3)

    def test_max_constraints_drop_lowest_relevance_content(self):
        result = resume_core.rankResumeContent(
            CANONICAL_RESUME,
            JOB_MODEL,
            {},
            {"resume": {"skills": {"max": 1}, "experience": {"max": 1}, "bulletsPerRole": {"max": 2}}},
        )

        self.assertEqual(result["status"], "ok", result)
        entries = result["selection_plan"]["entries"]
        self.assertEqual([entry["action"] for entry in entries if entry["path"] == "/skills/0"], ["keep"])
        self.assertEqual([entry["action"] for entry in entries if entry["path"] == "/skills/1"], ["drop"])
        self.assertEqual([entry["action"] for entry in entries if entry["path"] == "/experience/0/bullets/2"], ["drop"])
        self.assertTrue(all(entry["action"] == "drop" for entry in entries if entry["path"].startswith("/experience/1/")))


if __name__ == "__main__":
    unittest.main()
