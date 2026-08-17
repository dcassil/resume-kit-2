"""Contract-first tests for the future resume_agent package."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import re
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SURFACE = json.loads((ROOT / "resume-agent" / "agent_surface.json").read_text(encoding="utf-8"))
PUBLIC_FUNCTIONS = tuple(SURFACE["public_api"]["functions"])


RESUME_FIXTURE = """
Daniel Candidate
Software Engineer

Experience building React and TypeScript front ends, REST APIs, and responsive web applications.
Designed API architecture for customer-facing SaaS products.
"""

JOB_FIXTURE = """
Senior Software Engineer, Example SaaS Co.
Required: 8+ years of software engineering experience, React, TypeScript, API architecture/design, responsive design.
Preferred: AWS, GraphQL, SaaS experience, and technical leadership.
"""

ML_ENGINEER_RESUME = """Maya Patel
Machine Learning Engineer

Skills: Python, TensorFlow, Kubernetes, Google Cloud Platform (GCP), Go, Spark, MLOps.
Experience
Senior ML Engineer, CloudScale AI, 2021-Present
Built TensorFlow training pipelines in Python and deployed model serving workloads on Kubernetes and GCP.
Machine Learning Engineer, DataWorks, 2018-2021
Developed Go services for feature ingestion and batch prediction.
Education
PhD in Computer Science, University of Illinois, 2018
Certifications
Google Professional Machine Learning Engineer, Google Cloud, 2022
Projects
Realtime Fraud Detection: Python and TensorFlow system with Kubernetes inference services.
"""

PYTHON_SPARK_JOB = """Senior Data Platform Engineer
DataLake Systems
Requirements:
- 5+ years with Python, Spark, and distributed data processing.
- Build production ETL pipelines on cloud infrastructure.
Preferred:
- Kubernetes experience.
"""

GRAPHQL_API_JOB = """Backend Platform Engineer
API Studio
Required:
- Design GraphQL APIs for customer-facing products.
- Lead REST API design and versioning for partner integrations.
Preferred:
- TypeScript experience.
"""


def maybe_await(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def load_agent_module(test_case: unittest.TestCase):
    try:
        module = importlib.import_module("resume_agent")
    except ModuleNotFoundError as exc:
        test_case.fail(
            "Expected importable package 'resume_agent'. Implement the five proposal functions from "
            "resume-agent/TEST_SPEC.md: extractResumeSemantics, extractJobSemantics, "
            "generateClarificationQuestion, interpretUserAnswer, and proposeRewrite."
        )
        raise exc
    for function_name in PUBLIC_FUNCTIONS:
        test_case.assertTrue(callable(getattr(module, function_name, None)), f"resume_agent must expose {function_name}().")
    return module


def assert_proposal_handoff(test_case: unittest.TestCase, result: dict, proposal_type: str) -> None:
    test_case.assertIsInstance(result, dict)
    test_case.assertEqual(result.get("proposal_type"), proposal_type)
    test_case.assertIn("schema_version", result)
    test_case.assertIn("uncertainty", result)
    test_case.assertTrue(result.get("requires_validation"), "Agent outputs must require downstream code validation.")
    serialized = json.dumps(result, sort_keys=True).lower()
    test_case.assertNotRegex(serialized, r"\b(official_score|overall_score|sqlite|traceback)\b")
    test_case.assertNotIn("canonical_resume", serialized)
    test_case.assertNotIn("working_resume", serialized)


def assert_fact_proposals_have_verification_state(test_case: unittest.TestCase, result: dict) -> None:
    allowed_states = set(SURFACE["verification_states"])
    facts = result.get("fact_proposals", [])
    test_case.assertTrue(facts)
    for fact in facts:
        with test_case.subTest(fact=fact.get("fact_id")):
            test_case.assertIn("verification_state", fact)
            test_case.assertIn(fact["verification_state"], allowed_states)
            test_case.assertEqual(fact["verification_state"], "inferred")


def assert_resume_fact_proposals_have_model_evidence(test_case: unittest.TestCase, result: dict) -> None:
    evidence_ids = {item.get("evidence_id") for item in result.get("source_evidence", [])}
    for fact in result.get("fact_proposals", []):
        with test_case.subTest(fact=fact.get("fact_id")):
            test_case.assertTrue(fact.get("source_evidence_ids"))
            test_case.assertTrue(set(fact["source_evidence_ids"]) <= evidence_ids)
            test_case.assertTrue(fact.get("evidence"))
            test_case.assertIsInstance(fact.get("model_confidence"), (int, float))
            test_case.assertEqual(fact.get("confidence"), fact.get("model_confidence"))


def assert_job_requirement_proposals_have_model_evidence(test_case: unittest.TestCase, result: dict) -> None:
    evidence_ids = {item.get("evidence_id") for item in result.get("source_evidence", [])}
    requirements = result.get("requirement_proposals", [])
    test_case.assertTrue(requirements)
    for requirement in requirements:
        with test_case.subTest(requirement=requirement.get("requirement_id")):
            test_case.assertTrue(requirement.get("source_evidence_ids"))
            test_case.assertTrue(set(requirement["source_evidence_ids"]) <= evidence_ids)
            test_case.assertTrue(requirement.get("evidence"))
            test_case.assertIsInstance(requirement.get("model_confidence"), (int, float))
            test_case.assertEqual(requirement.get("confidence"), requirement.get("model_confidence"))
            for field in ["classification", "seniority", "industries", "domains"]:
                test_case.assertIn(field, requirement)


class ResumeAgentSurfaceManifestTests(unittest.TestCase):
    def test_manifest_declares_exact_public_functions(self):
        self.assertEqual(PUBLIC_FUNCTIONS, (
            "extractResumeSemantics",
            "extractJobSemantics",
            "generateClarificationQuestion",
            "interpretUserAnswer",
            "proposeRewrite",
        ))

    def test_manifest_defines_contracts_for_every_surface(self):
        surfaces = {surface["name"]: surface for surface in SURFACE["surfaces"]}
        self.assertEqual(set(surfaces), set(PUBLIC_FUNCTIONS))
        for name, surface in surfaces.items():
            with self.subTest(surface=name):
                self.assertIn("input_contract", surface)
                self.assertIn("output_contract", surface)
                required_fields = set(surface["output_contract"]["required_fields"])
                self.assertTrue({"schema_version", "proposal_type", "uncertainty", "requires_validation"} <= required_fields)
                self.assertIn("must_not_include", surface["output_contract"])
        rewrite = surfaces["proposeRewrite"]["output_contract"]
        self.assertIn("reason", rewrite["operation_fields"])


class ResumeAgentProposalContractTests(unittest.TestCase):
    def setUp(self):
        self.agent = load_agent_module(self)

    def test_resume_semantic_extraction_returns_evidence_backed_proposals_only(self):
        result = maybe_await(self.agent.extractResumeSemantics(RESUME_FIXTURE))
        assert_proposal_handoff(self, result, "resume_semantic_extraction")
        self.assertIn("fact_proposals", result)
        self.assertIn("source_evidence", result)
        assert_fact_proposals_have_verification_state(self, result)
        assert_resume_fact_proposals_have_model_evidence(self, result)
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertIn("react", serialized)
        self.assertIn("api", serialized)
        self.assertNotIn("aws", serialized)
        self.assertNotIn("graphql", serialized)
        self.assertNotIn("staff software engineer", serialized)
        self.assertNotRegex(serialized, r"\b20 million\b|\b30 engineers\b")

    def test_ml_engineer_resume_public_extraction_covers_every_populated_section(self):
        result = maybe_await(
            self.agent.extractResumeSemantics(ML_ENGINEER_RESUME, {"source_id": "ml-engineer-golden-resume"})
        )
        assert_proposal_handoff(self, result, "resume_semantic_extraction")
        assert_fact_proposals_have_verification_state(self, result)
        assert_resume_fact_proposals_have_model_evidence(self, result)

        categories = {proposal.get("category") for proposal in result.get("fact_proposals", [])}
        for category in ["skill", "experience", "education", "certification", "project", "employment"]:
            with self.subTest(category=category):
                self.assertIn(category, categories)

        serialized = json.dumps(result, sort_keys=True).lower()
        for expected in ["python", "tensorflow", "kubernetes", "gcp", "go", "phd"]:
            self.assertIn(expected, serialized)

    def test_resume_extraction_adapter_missing_fixture_returns_typed_error_without_partial_proposals(self):
        from resume_agent._fake_adapter import DeterministicFakeAdapter

        with tempfile.TemporaryDirectory(prefix="resume-agent-missing-fixture-") as temp:
            result = maybe_await(
                self.agent.extractResumeSemantics(RESUME_FIXTURE, {"_adapter": DeterministicFakeAdapter(fixture_dir=Path(temp))})
            )

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error", {}).get("type"), "provider_error")
        self.assertNotIn("fact_proposals", result)
        self.assertNotIn("proposals", result)

    def test_resume_extraction_adapter_schema_invalid_returns_typed_error_without_partial_proposals(self):
        from resume_agent._extraction_requests import build_resume_extraction_request
        from resume_agent._fake_adapter import DeterministicFakeAdapter, deterministic_fake_key

        with tempfile.TemporaryDirectory(prefix="resume-agent-broken-fixture-") as temp:
            fixture_dir = Path(temp)
            request = build_resume_extraction_request(RESUME_FIXTURE, source_id="inline")
            key_hash = deterministic_fake_key(request.prompt_template_id, request.output_schema_id, request.input_payload)
            fixture = {
                "fixture_id": "resume-agent-public-broken-schema-invalid",
                "schema_version": "resume-agent.fake-adapter-fixture.v1",
                "config_hash": "fixture-config-v1",
                "reviewed": True,
                "expected_observations": ["Deliberately malformed extraction payload for public error mapping."],
                "comment": "Temporary in-test fixture.",
                "data": {
                    "key": {
                        "sha256": key_hash,
                        "prompt_template_id": request.prompt_template_id,
                        "output_schema_id": request.output_schema_id,
                        "canonical_input_json": json.dumps(
                            request.input_payload,
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                        ),
                    },
                    "payload": {"schema_version": request.output_schema_id},
                },
            }
            (fixture_dir / f"{key_hash}.json").write_text(json.dumps(fixture), encoding="utf-8")
            result = maybe_await(
                self.agent.extractResumeSemantics(RESUME_FIXTURE, {"_adapter": DeterministicFakeAdapter(fixture_dir=fixture_dir)})
            )

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error", {}).get("type"), "schema_invalid")
        self.assertTrue(result.get("error", {}).get("violations"))
        self.assertNotIn("fact_proposals", result)
        self.assertNotIn("proposals", result)

    def test_job_semantic_extraction_preserves_requirement_source_and_classification(self):
        result = maybe_await(self.agent.extractJobSemantics(JOB_FIXTURE))
        assert_proposal_handoff(self, result, "job_semantic_extraction")
        requirements = result.get("requirement_proposals", [])
        self.assertTrue(requirements)
        serialized = json.dumps(result, sort_keys=True).lower()
        for expected in ["8+ years", "react", "typescript", "api", "responsive", "saas", "aws", "graphql"]:
            self.assertIn(expected, serialized)
        classifications = {requirement.get("classification") for requirement in requirements}
        self.assertTrue({"required", "preferred"} <= classifications)
        self.assertTrue(result.get("requirement_classification_proposals"))
        assert_job_requirement_proposals_have_model_evidence(self, result)
        for requirement in requirements:
            self.assertIn("source_text", requirement)
            self.assertIn("normalized_terms", requirement)

    def test_job_extraction_public_goldens_keep_all_named_skills(self):
        cases = [
            (PYTHON_SPARK_JOB, "python-spark-golden-job", ["python", "spark", "kubernetes"]),
            (GRAPHQL_API_JOB, "graphql-api-design-golden-job", ["graphql", "api design", "typescript"]),
        ]

        for job_text, source_id, expected_skills in cases:
            result = maybe_await(self.agent.extractJobSemantics(job_text, {"source_id": source_id}))
            assert_proposal_handoff(self, result, "job_semantic_extraction")
            assert_job_requirement_proposals_have_model_evidence(self, result)
            requirement_text = json.dumps(result.get("requirement_proposals", []), sort_keys=True).lower()
            for skill_name in expected_skills:
                with self.subTest(source_id=source_id, skill=skill_name):
                    self.assertIn(skill_name, requirement_text)

    def test_job_extraction_preserves_model_sourced_confidence_values(self):
        result = maybe_await(self.agent.extractJobSemantics(PYTHON_SPARK_JOB, {"source_id": "python-spark-golden-job"}))
        assert_proposal_handoff(self, result, "job_semantic_extraction")

        by_id = {requirement.get("requirement_id"): requirement for requirement in result.get("requirement_proposals", [])}
        self.assertEqual(by_id["req_python_spark_years"].get("confidence"), 0.94)
        self.assertEqual(by_id["req_python_spark_years"].get("model_confidence"), 0.94)
        self.assertIsInstance(by_id["req_python_spark_years"].get("confidence"), (int, float))

    def test_job_extraction_surfaces_model_marked_uncertain_requirement(self):
        result = maybe_await(self.agent.extractJobSemantics(PYTHON_SPARK_JOB, {"source_id": "python-spark-golden-job"}))
        assert_proposal_handoff(self, result, "job_semantic_extraction")

        by_id = {requirement.get("requirement_id"): requirement for requirement in result.get("requirement_proposals", [])}
        kubernetes = by_id.get("req_kubernetes")
        self.assertIsNotNone(kubernetes)
        self.assertEqual(kubernetes.get("concept"), "Kubernetes")
        self.assertEqual(kubernetes.get("uncertainty", {}).get("code"), "preferred_scope_sparse")
        self.assertTrue(kubernetes.get("uncertainty", {}).get("requires_review"))
        self.assertIn(
            "req_kubernetes",
            {item.get("requirement_id") for item in result.get("uncertainty", []) if isinstance(item, dict)},
        )

    def test_job_extraction_public_goldens_preserve_co_required_concepts(self):
        python_spark = maybe_await(self.agent.extractJobSemantics(PYTHON_SPARK_JOB, {"source_id": "python-spark-golden-job"}))
        python_spark_text = json.dumps(python_spark.get("requirement_proposals", []), sort_keys=True).lower()
        self.assertIn("python", python_spark_text)
        self.assertIn("spark", python_spark_text)

        graphql_api = maybe_await(self.agent.extractJobSemantics(GRAPHQL_API_JOB, {"source_id": "graphql-api-design-golden-job"}))
        concepts = {requirement.get("concept") for requirement in graphql_api.get("requirement_proposals", [])}
        self.assertIn("GraphQL APIs", concepts)
        self.assertIn("REST API design", concepts)

    def test_job_extraction_adapter_missing_fixture_returns_typed_error_without_partial_proposals(self):
        from resume_agent._fake_adapter import DeterministicFakeAdapter

        with tempfile.TemporaryDirectory(prefix="resume-agent-job-missing-fixture-") as temp:
            result = maybe_await(
                self.agent.extractJobSemantics(JOB_FIXTURE, {"_adapter": DeterministicFakeAdapter(fixture_dir=Path(temp))})
            )

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error", {}).get("type"), "provider_error")
        self.assertNotIn("requirement_proposals", result)
        self.assertNotIn("proposals", result)

    def test_job_extraction_adapter_schema_invalid_returns_typed_error_without_partial_proposals(self):
        from resume_agent._extraction_requests import build_job_extraction_request
        from resume_agent._fake_adapter import DeterministicFakeAdapter, deterministic_fake_key

        with tempfile.TemporaryDirectory(prefix="resume-agent-job-broken-fixture-") as temp:
            fixture_dir = Path(temp)
            request = build_job_extraction_request(JOB_FIXTURE, source_id="inline")
            key_hash = deterministic_fake_key(request.prompt_template_id, request.output_schema_id, request.input_payload)
            fixture = {
                "fixture_id": "resume-agent-public-job-broken-schema-invalid",
                "schema_version": "resume-agent.fake-adapter-fixture.v1",
                "config_hash": "fixture-config-v1",
                "reviewed": True,
                "expected_observations": ["Deliberately malformed job extraction payload for public error mapping."],
                "comment": "Temporary in-test fixture.",
                "data": {
                    "key": {
                        "sha256": key_hash,
                        "prompt_template_id": request.prompt_template_id,
                        "output_schema_id": request.output_schema_id,
                        "canonical_input_json": json.dumps(
                            request.input_payload,
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                        ),
                    },
                    "payload": {"schema_version": request.output_schema_id},
                },
            }
            (fixture_dir / f"{key_hash}.json").write_text(json.dumps(fixture), encoding="utf-8")
            result = maybe_await(
                self.agent.extractJobSemantics(JOB_FIXTURE, {"_adapter": DeterministicFakeAdapter(fixture_dir=fixture_dir)})
            )

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error", {}).get("type"), "schema_invalid")
        self.assertTrue(result.get("error", {}).get("violations"))
        self.assertNotIn("requirement_proposals", result)
        self.assertNotIn("proposals", result)

    def test_clarification_question_phrases_only_code_selected_topic(self):
        context = {
            "selected_requirement_ids": ["req_aws"],
            "topic": "AWS",
            "already_verified_fact_ids": ["fact_react"],
        }
        result = maybe_await(self.agent.generateClarificationQuestion(context))
        assert_proposal_handoff(self, result, "clarification_question")
        self.assertEqual(result.get("selected_requirement_ids"), ["req_aws"])
        self.assertEqual(result.get("topic"), "AWS")
        self.assertRegex(result.get("question", "").lower(), r"aws")
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertNotIn("selected_next_topic", serialized)
        self.assertNotIn("score_impact", serialized)
        self.assertNotRegex(result.get("question", "").lower(), r"anything else|tell me about your background")

    def test_answer_interpretation_keeps_aws_six_years_as_proposal_not_final_verification(self):
        context = {"selected_requirement_ids": ["req_aws"], "topic": "AWS"}
        answer = "Yes. I have about six years of AWS experience, mainly EC2, S3, Lambda, RDS, and IAM."
        result = maybe_await(self.agent.interpretUserAnswer(answer, context))
        assert_proposal_handoff(self, result, "answer_interpretation")
        assert_fact_proposals_have_verification_state(self, result)
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertIn("aws", serialized)
        self.assertRegex(serialized, r"\bsix\b|\b6\b")
        for service in ["ec2", "s3", "lambda", "rds", "iam"]:
            self.assertIn(service, serialized)
        self.assertNotIn("ten years", serialized)
        self.assertNotIn("final_verification_state", serialized)
        self.assertNotIn("persisted", serialized)
        for fact in result.get("fact_proposals", []):
            self.assertEqual(fact.get("confidence"), "unscored")
            self.assertEqual(fact.get("confidence_source"), "placeholder_unscored")
            self.assertNotIn("model_confidence", fact)

    def test_answer_interpretation_preserves_graphql_production_context(self):
        context = {"selected_requirement_ids": ["req_graphql"], "topic": "GraphQL"}
        answer = "Yes, around five years. I've built and maintained GraphQL APIs in production."
        result = maybe_await(self.agent.interpretUserAnswer(answer, context))
        assert_proposal_handoff(self, result, "answer_interpretation")
        assert_fact_proposals_have_verification_state(self, result)
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertIn("graphql", serialized)
        self.assertRegex(serialized, r"\bfive\b|\b5\b")
        self.assertIn("production", serialized)

    def test_answer_interpretation_records_architecture_without_staff_title_inflation(self):
        context = {"selected_requirement_ids": ["req_architecture"], "topic": "architecture"}
        answer = "I've designed APIs and application architecture for more than ten years, but I haven't had Staff Engineer as my formal title."
        result = maybe_await(self.agent.interpretUserAnswer(answer, context))
        assert_proposal_handoff(self, result, "answer_interpretation")
        assert_fact_proposals_have_verification_state(self, result)
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertIn("architecture", serialized)
        self.assertIn("api", serialized)
        self.assertRegex(serialized, r"not.*staff|staff.*not|explicit_negative")
        self.assertNotIn("staff_title_employment_history", serialized)

    def test_rewrite_proposals_are_resume_change_operations_grounded_in_allowed_facts(self):
        context = {
            "original_text": "Built web applications.",
            "allowed_facts": [
                {"fact_id": "fact_api", "text": "API design experience", "verification_state": "source_stated"},
                {"fact_id": "fact_responsive", "text": "responsive web applications", "verification_state": "source_stated"},
            ],
            "job_terminology": ["API architecture", "responsive design"],
            "requirements": [
                {"requirement_id": "req_api", "source_text": "API architecture/design"},
                {"requirement_id": "req_responsive", "source_text": "responsive design"},
            ],
            "prohibited_additions": ["AWS", "GraphQL", "Staff Software Engineer", "20 million users", "30 engineers"],
            "length_constraints": {"max_chars": 160},
            "voice_constraints": {"tense": "past", "style": "concise"},
        }
        result = maybe_await(self.agent.proposeRewrite(context))
        assert_proposal_handoff(self, result, "rewrite_proposal")
        operations = result.get("operations", [])
        self.assertTrue(operations)
        for operation in operations:
            with self.subTest(operation=operation.get("operation_id")):
                for field in [
                    "operation_id",
                    "operation_type",
                    "target_path",
                    "before",
                    "after",
                    "facts_used",
                    "requirements_targeted",
                    "terminology_changes",
                    "provenance",
                    "reason",
                    "status",
                ]:
                    self.assertIn(field, operation)
                self.assertNotEqual(operation["status"], "applied")
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertNotIn("aws", serialized)
        self.assertNotIn("graphql", serialized)
        self.assertNotIn("staff software engineer", serialized)
        self.assertNotRegex(serialized, r"\b20 million\b|\b30 engineers\b")

    def test_malformed_or_empty_inputs_return_typed_errors_without_tracebacks(self):
        invalid_calls = [
            (self.agent.extractResumeSemantics, [""]),
            (self.agent.extractJobSemantics, [""]),
            (self.agent.generateClarificationQuestion, [{"selected_requirement_ids": [], "topic": ""}]),
            (self.agent.interpretUserAnswer, ["", {"selected_requirement_ids": ["req_aws"], "topic": "AWS"}]),
            (self.agent.proposeRewrite, [{"original_text": "Built apps."}]),
        ]
        for function, args in invalid_calls:
            with self.subTest(function=function.__name__):
                result = maybe_await(function(*args))
                self.assertEqual(result["status"], "error")
                self.assertIn(result["error"]["type"], {"validation_error", "schema_error", "policy_error"})
                self.assertNotRegex(json.dumps(result).lower(), r"\btraceback|sqlite|select|insert|update|delete\b")


# Bridge the private adapter seam tests into the current static PR/future gate
# module list until tools/run_tests.py is approved to include it directly.
from tests.contract.test_resume_agent_adapter_contract import (  # noqa: E402,F401
    ResumeAgentAnthropicAdapterContractTests,
    ResumeAgentAdapterContractTests,
    ResumeAgentDeterministicFakeAdapterContractTests,
    ResumeAgentExtractionSchemaContractTests,
    ResumeAgentSchemaValidatorContractTests,
)


if __name__ == "__main__":
    unittest.main()
