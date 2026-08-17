"""Contract-first tests for the future resume_agent package."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import re
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
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertIn("react", serialized)
        self.assertIn("api", serialized)
        self.assertNotIn("aws", serialized)
        self.assertNotIn("graphql", serialized)
        self.assertNotIn("staff software engineer", serialized)
        self.assertNotRegex(serialized, r"\b20 million\b|\b30 engineers\b")

    def test_job_semantic_extraction_preserves_requirement_source_and_classification(self):
        result = maybe_await(self.agent.extractJobSemantics(JOB_FIXTURE))
        assert_proposal_handoff(self, result, "job_semantic_extraction")
        requirements = result.get("requirements", [])
        self.assertTrue(requirements)
        serialized = json.dumps(result, sort_keys=True).lower()
        for expected in ["8+ years", "react", "typescript", "api", "responsive", "saas", "aws", "graphql"]:
            self.assertIn(expected, serialized)
        classifications = {requirement.get("classification") for requirement in requirements}
        self.assertTrue({"required", "preferred"} <= classifications)
        for requirement in requirements:
            self.assertIn("source_text", requirement)
            self.assertIn("normalized_terms", requirement)

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
