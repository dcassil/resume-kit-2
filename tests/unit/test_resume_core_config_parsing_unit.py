"""Stable unit checks for resume-core config parsing surfaces.

RKIT-I-0001 chunk 6 (RKIT-T-0010) owns date, requirement, change, and enum
coverage. This module stays scoped to RKIT-I-0001-stable config inputs.
"""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from resume_agent import AGENT_CONFIG_DEFAULTS
from resume_cli._config import (
    WorkspaceConfigValidationError,
    default_config,
    load_workspace_config,
    resolve_workspace_config,
    stable_config_hash,
)
from resume_core import (
    DEFAULT_ALLOW_INFERRED_FACTS,
    DEFAULT_MATCHING_WEIGHTS,
    DEFAULT_MAX_COUNT,
    DEFAULT_MIN_COUNT,
    DEFAULT_REQUIRE_HARD_REQUIREMENTS_RESOLVED,
    DEFAULT_SCORE_AUTO_THRESHOLD,
    DEFAULT_SECTION_ORDER,
    DEFAULT_TARGET_PAGES,
)
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


class ResumeCliConfigContractUnitTests(unittest.TestCase):
    def test_default_config_values_are_sourced_from_owning_package_defaults(self):
        config = default_config()

        self.assertEqual(
            config["matching"],
            {
                "scoreAutoThreshold": DEFAULT_SCORE_AUTO_THRESHOLD,
                "weights": DEFAULT_MATCHING_WEIGHTS,
                "requireHardRequirementsResolved": DEFAULT_REQUIRE_HARD_REQUIREMENTS_RESOLVED,
            },
        )
        self.assertEqual(
            config["resume"],
            {
                "targetPages": DEFAULT_TARGET_PAGES,
                "skills": {"min": DEFAULT_MIN_COUNT, "max": DEFAULT_MAX_COUNT},
                "experience": {"min": DEFAULT_MIN_COUNT, "max": DEFAULT_MAX_COUNT},
                "bulletsPerRole": {"min": DEFAULT_MIN_COUNT, "max": DEFAULT_MAX_COUNT},
                "sectionOrder": DEFAULT_SECTION_ORDER,
            },
        )
        self.assertEqual(config["guardrails"], {"allow_inferred_facts": DEFAULT_ALLOW_INFERRED_FACTS})
        self.assertEqual(config["agent"], AGENT_CONFIG_DEFAULTS)

    def test_load_schema_validates_unknown_key_anywhere_and_freezes_before_hash(self):
        raw = default_config()
        raw["matching"]["weights"]["mystery"] = 0.1
        result = resolve_workspace_config(raw)

        self.assertEqual(result.errors[0]["code"], "unknown_matching_config_key")
        self.assertEqual(result.errors[0]["field_path"], "matching.weights.mystery")

        valid = resolve_workspace_config(default_config())
        with self.assertRaises(TypeError):
            valid.frozen_config["matching"] = {}
        with self.assertRaises(TypeError):
            valid.frozen_config["resume"]["sectionOrder"][0] = "skills"
        self.assertEqual(valid.config_hash, stable_config_hash(valid.config))

    def test_legacy_flat_keys_fail_with_section_13_replacement_guidance(self):
        raw = default_config()
        raw.update(
            {
                "policy": "strict",
                "require_hard_resolution": True,
                "allow_inferred_facts": True,
                "max_skills": 12,
            }
        )
        result = resolve_workspace_config(raw)

        replacements = {error["field_path"]: error["details"]["replacement"] for error in result.errors if error["code"] == "legacy_cli_config_key"}
        self.assertEqual(
            replacements,
            {
                "policy": "matching.scoreAutoThreshold and matching.weights",
                "require_hard_resolution": "matching.requireHardRequirementsResolved",
                "allow_inferred_facts": "guardrails.allow_inferred_facts",
                "max_skills": "resume.skills.max",
            },
        )

    def test_load_config_file_raises_typed_error_for_top_level_unknown_key(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            config_path.write_text('{"config_version": "resume-cli.config.v1", "mystery": true}', encoding="utf-8")

            with self.assertRaises(WorkspaceConfigValidationError) as raised:
                load_workspace_config(config_path)

        self.assertEqual(raised.exception.errors[0]["code"], "unknown_cli_config_key")
        self.assertEqual(raised.exception.errors[0]["field_path"], "mystery")

    def test_config_hash_changes_for_sampled_section_13_values(self):
        base = default_config()
        base_hash = stable_config_hash(base)
        mutations = {
            "matching.scoreAutoThreshold": lambda cfg: cfg["matching"].update({"scoreAutoThreshold": 8.5}),
            "matching.weights.requiredSkills": lambda cfg: cfg["matching"]["weights"].update({"requiredSkills": 0.31}),
            "matching.requireHardRequirementsResolved": lambda cfg: cfg["matching"].update({"requireHardRequirementsResolved": not cfg["matching"]["requireHardRequirementsResolved"]}),
            "resume.targetPages": lambda cfg: cfg["resume"].update({"targetPages": 2.0}),
            "resume.sectionOrder": lambda cfg: cfg["resume"].update({"sectionOrder": list(reversed(cfg["resume"]["sectionOrder"]))}),
            "resume.skills.max": lambda cfg: cfg["resume"]["skills"].update({"max": 12}),
            "resume.experience.max": lambda cfg: cfg["resume"]["experience"].update({"max": 4}),
            "resume.bulletsPerRole.max": lambda cfg: cfg["resume"]["bulletsPerRole"].update({"max": 3}),
            "guardrails.allow_inferred_facts": lambda cfg: cfg["guardrails"].update({"allow_inferred_facts": not cfg["guardrails"]["allow_inferred_facts"]}),
            "agent.model": lambda cfg: cfg["agent"].update({"model": "claude-sonnet-4-6-next"}),
        }

        for field_path, mutate in mutations.items():
            with self.subTest(field_path=field_path):
                changed = copy.deepcopy(base)
                mutate(changed)
                self.assertNotEqual(base_hash, stable_config_hash(changed))


if __name__ == "__main__":
    unittest.main()
