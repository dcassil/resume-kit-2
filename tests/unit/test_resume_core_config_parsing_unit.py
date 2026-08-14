"""Stable unit checks for resume-core config parsing surfaces.

RKIT-I-0001 chunk 6 (RKIT-T-0010) owns date, requirement, change, and enum
coverage. This module stays scoped to RKIT-I-0001-stable config inputs.
"""

from __future__ import annotations

import copy
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


class ConfigParsingUnitTests(unittest.TestCase):
    def test_requirement_id_prefix_config_is_applied_deterministically(self):
        source_job = {
            "schema_version": "job-model.v1",
            "job_id": "job_config_prefix_unit",
            "requirements": ["React"],
            "preferred": [],
        }
        config = {"requirement_id_prefix": "unitreq"}

        first = resume_core.normalizeJobModel(copy.deepcopy(source_job), copy.deepcopy(config))
        second = resume_core.normalizeJobModel(copy.deepcopy(source_job), copy.deepcopy(config))

        self.assertEqual(first, second)
        self.assertEqual(first["job_model"]["requirements"][0]["requirement_id"], "unitreq_0_27597608")

    def test_alias_map_config_accepts_scalar_alias_values(self):
        resume = {
            "schema_version": "canonical-resume.v1",
            "resume_id": "resume_config_alias_unit",
            "source": {"kind": "unit"},
            "summary": "Built Vue dashboards.",
            "experience": [],
            "skills": [],
            "education": [],
        }
        job = {
            "schema_version": "job-model.v1",
            "job_id": "job_config_alias_unit",
            "requirements": [
                {
                    "requirement_id": "req_react",
                    "classification": "required",
                    "concept": "React",
                    "weight": 10,
                    "source_text": "React",
                    "normalized_terms": ["react"],
                }
            ],
            "preferred": [],
        }

        match = resume_core.scoreMatch(resume, job, [], {"alias_map": {"react": "vue"}})["match_result"]

        result = match["requirement_results"][0]
        self.assertEqual(result["resolution_state"], "alias_match")
        self.assertEqual(result["score"], 10.0)
        self.assertEqual(result["evidence"], [{"source": "alias", "terms": ["vue"]}])

    def test_allow_inferred_facts_config_controls_fact_resolution(self):
        resume = {
            "schema_version": "canonical-resume.v1",
            "resume_id": "resume_config_inferred_unit",
            "source": {"kind": "unit"},
            "experience": [],
            "skills": [],
            "education": [],
        }
        job = {
            "schema_version": "job-model.v1",
            "job_id": "job_config_inferred_unit",
            "requirements": [
                {
                    "requirement_id": "req_aws",
                    "classification": "required",
                    "concept": "AWS",
                    "weight": 4,
                    "source_text": "AWS",
                    "normalized_terms": ["aws"],
                }
            ],
            "preferred": [],
        }
        facts = [{"fact_id": "fact_aws", "text": "AWS", "verification_state": "inferred"}]

        default_match = resume_core.scoreMatch(resume, job, facts, {})["match_result"]
        allowed_match = resume_core.scoreMatch(resume, job, facts, {"guardrails": {"allow_inferred_facts": True}})["match_result"]

        self.assertEqual(default_match["requirement_results"][0]["resolution_state"], "unknown")
        self.assertEqual(default_match["score"], 2.0)
        self.assertEqual(allowed_match["requirement_results"][0]["resolution_state"], "verified_fact_match")
        self.assertEqual(allowed_match["score"], 4.0)


if __name__ == "__main__":
    unittest.main()
