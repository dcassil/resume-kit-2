"""Contract tests for shared DTO and schema definitions."""

from __future__ import annotations

import unittest
from dataclasses import fields

import career_store
import resume_core
import workflow


class SharedDtoSchemaContractTests(unittest.TestCase):
    def test_resume_core_exports_canonical_dtos_and_schemas(self):
        for name in [
            "Result",
            "Error",
            "CanonicalResume",
            "JobModel",
            "JobRequirement",
            "MatchResult",
            "ContentSelectionPlan",
            "ResumeChangeOperation",
            "VerificationState",
            "ResolutionState",
        ]:
            with self.subTest(name=name):
                self.assertTrue(hasattr(resume_core, name))
                if name not in {"VerificationState", "ResolutionState"}:
                    self.assertIn(name, resume_core.SCHEMAS)

    def test_resume_core_schema_required_fields_are_stable(self):
        expected = {
            "Result": {"schema_version", "status"},
            "Error": {"code", "message", "severity"},
            "CanonicalResume": {"schema_version", "resume_id", "source", "experience", "skills", "education"},
            "JobModel": {"schema_version", "job_id", "requirements", "preferred", "industries", "domains", "terminology"},
            "JobRequirement": {"requirement_id", "classification", "concept", "importance", "weight", "source_text", "normalized_terms"},
            "MatchDimension": {"name", "weight", "score", "contribution", "evidence"},
            "MatchResult": {
                "schema_version",
                "match_id",
                "job_id",
                "resume_id",
                "score",
                "max_score",
                "threshold",
                "hardRequirementsResolved",
                "decision",
                "dimensions",
                "requirement_results",
            },
            "ContentSelectionPlan": {"schema_version", "sections", "entries", "constraint_report", "metadata"},
            "ResumeChangeOperation": {
                "schema_version",
                "operation_id",
                "status",
                "op",
                "path",
                "reason",
                "linked_requirement_ids",
                "linked_fact_ids",
                "provenance",
            },
        }
        for schema_name, required_fields in expected.items():
            with self.subTest(schema_name=schema_name):
                self.assertEqual(set(resume_core.SCHEMAS[schema_name]["required"]), required_fields)

    def test_resume_core_enums_preserve_truth_and_match_states(self):
        self.assertEqual(
            {state.value for state in resume_core.VerificationState},
            {"source_stated", "user_verified", "imported", "inferred", "unknown"},
        )
        self.assertEqual(
            {state.value for state in resume_core.ResolutionState},
            {
                "exact_match",
                "alias_match",
                "verified_fact_match",
                "related_match",
                "possible_match",
                "unknown",
                "explicitly_missing",
                "not_applicable",
            },
        )

    def test_career_store_exports_fact_evidence_and_shared_states(self):
        for name in [
            "Fact",
            "CareerFact",
            "Evidence",
            "FactRelationship",
            "VerificationState",
            "ResolutionState",
            "TransactionResult",
            "MigrationState",
        ]:
            with self.subTest(name=name):
                self.assertTrue(hasattr(career_store, name))
        self.assertIs(career_store.CareerFact, career_store.Fact)
        self.assertIs(career_store.VerificationState, resume_core.VerificationState)

    def test_career_store_schema_required_fields_are_stable(self):
        self.assertEqual(
            set(career_store.SCHEMAS["Fact"]["required"]),
            {"fact_id", "type", "text", "normalized_terms", "verification_state"},
        )
        self.assertEqual(set(career_store.SCHEMAS["Evidence"]["required"]), {"evidence_id", "source", "text"})

    def test_run_manifest_has_all_required_workflow_fields(self):
        manifest_fields = {field.name for field in fields(workflow.RunManifest)}
        required_fields = set(workflow.RUN_MANIFEST_SCHEMA["required"])
        self.assertTrue(required_fields <= manifest_fields)
        self.assertEqual(
            required_fields,
            {
                "run_id",
                "base_resume_id",
                "base_resume_hash",
                "job_id",
                "config_hash",
                "canonical_resume_schema_version",
                "job_schema_version",
                "career_db_schema_version",
                "careerDbVersion",
                "change_operation_schema_version",
                "matching_algorithm_version",
                "matching_config_version",
                "renderer_template_version",
                "agent_model_config",
                "initial_score",
                "final_score",
                "facts_added",
                "facts_verified",
                "operations_applied",
                "operations_rejected",
                "validation_status",
                "output_artifact_paths",
            },
        )

    def test_dtos_serialize_to_plain_json_shapes(self):
        requirement = resume_core.JobRequirement(
            requirement_id="req_react",
            classification=resume_core.RequirementClassification.REQUIRED,
            concept="React",
            importance="high",
            weight=10,
            source_text="Required: React",
            normalized_terms=["react"],
        )
        job = resume_core.JobModel(schema_version="job-model.v1", job_id="job_a", requirements=[requirement])
        fact = career_store.Fact(
            fact_id="fact_react",
            type="skill",
            text="React",
            normalized_terms=["react"],
            verification_state=resume_core.VerificationState.SOURCE_STATED,
        )
        payload = resume_core.to_json_dict({"job": job, "fact": fact})
        self.assertEqual(payload["job"]["requirements"][0]["classification"], "required")
        self.assertEqual(payload["fact"]["verification_state"], "source_stated")


if __name__ == "__main__":
    unittest.main()
