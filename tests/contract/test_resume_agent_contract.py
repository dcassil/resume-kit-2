"""Contract-first tests for the future resume_agent package."""

from __future__ import annotations

import asyncio
import copy
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


def fixture_payload(fixture_id: str) -> dict:
    for path in sorted((ROOT / "fixtures" / "resume-agent" / "fake-adapter").glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        if fixture.get("fixture_id") == fixture_id:
            return fixture["data"]["payload"]
    raise AssertionError(f"Missing fake adapter fixture {fixture_id}.")


def _answer_interpretation_fixture_envelope(key_hash: str, request, payload: dict) -> dict:
    return {
        "fixture_id": "resume-agent-answer-interpretation-denied-guard-in-test",
        "schema_version": "resume-agent.fake-adapter-fixture.v1",
        "config_hash": "fixture-config-v1",
        "reviewed": True,
        "expected_observations": ["Deliberately inconsistent denied payload for post-guard coverage."],
        "comment": "Temporary fixture created inside the public contract test.",
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
            "payload": payload,
        },
    }


def _fake_adapter_fixture_envelope(fixture_id: str, key_hash: str, request, payload: dict, observations: list[str]) -> dict:
    return {
        "fixture_id": fixture_id,
        "schema_version": "resume-agent.fake-adapter-fixture.v1",
        "config_hash": "fixture-config-v1",
        "reviewed": True,
        "expected_observations": observations,
        "comment": "Temporary fixture created inside the public contract test.",
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
            "payload": payload,
        },
    }


REWRITE_API_ONLY_CONTEXT = {
    "original_text": "Built web applications.",
    "target_path": "/experience/0/bullets/0",
    "allowed_facts": [
        {
            "fact_id": "fact_api",
            "text": "Designed REST API architecture for customer-facing SaaS products.",
            "verification_state": "source_stated",
            "evidence_id": "ev_api",
        },
    ],
    "requirement_ids": ["req_api"],
    "job_terminology": ["API architecture", "responsive design"],
    "requirements": [{"requirement_id": "req_api", "source_text": "API architecture/design"}],
    "prohibited_additions": ["GraphQL", "AWS", "responsive design"],
    "length_constraints": {"max_chars": 150},
    "voice_constraints": {},
}

REWRITE_API_FACT = {
    "fact_id": "fact_api",
    "text": "Designed REST API architecture for customer-facing SaaS products.",
    "verification_state": "source_stated",
    "evidence_id": "ev_api",
}

REWRITE_DOCS_FACT = {
    "fact_id": "fact_docs",
    "text": "Wrote concise API documentation for partner developers.",
    "verification_state": "source_stated",
    "evidence_id": "ev_docs",
}

REWRITE_GRAPHQL_FACT = {
    "fact_id": "fact_graphql",
    "text": "Designed GraphQL APIs for customer-facing products.",
    "verification_state": "source_stated",
    "evidence_id": "ev_graphql",
}

REWRITE_VOICE_VIOLATION_CONTEXT = {
    "original_text": "Built web applications.",
    "target_path": "/experience/0/bullets/0",
    "allowed_facts": [REWRITE_API_FACT],
    "requirement_ids": ["req_api"],
    "voice_constraints": {"tense": "past", "person": "first-person-implied"},
    "length_constraints": {"max_chars": 150},
    "prohibited_additions": ["AWS", "GraphQL", "team leadership"],
}

REWRITE_LENGTH_VIOLATION_CONTEXT = {
    "original_text": "Built web applications.",
    "target_path": "/experience/0/bullets/0",
    "allowed_facts": [REWRITE_API_FACT, REWRITE_DOCS_FACT],
    "requirement_ids": ["req_api", "req_docs"],
    "voice_constraints": {"tense": "past", "person": "first-person-implied"},
    "length_constraints": {"max_chars": 70},
    "prohibited_additions": ["AWS", "GraphQL", "team leadership"],
}

REWRITE_PROHIBITED_ADDITION_CONTEXT = {
    "original_text": "Built web applications.",
    "target_path": "/experience/0/bullets/0",
    "allowed_facts": [REWRITE_API_FACT, REWRITE_GRAPHQL_FACT],
    "requirement_ids": ["req_api", "req_graphql"],
    "voice_constraints": {},
    "length_constraints": {"max_chars": 180},
    "prohibited_additions": ["GraphQL"],
}

EQUIVALENCE_ALIAS_CONTEXT = {
    "candidate_pairs": [
        {
            "term_a": "responsive web apps",
            "term_b": "responsive design",
            "evidence_refs": ["ev_resume_responsive", "ev_job_responsive"],
        }
    ],
    "evidence": [
        {
            "evidence_id": "ev_resume_responsive",
            "source": "resume",
            "text": "Experience building React and TypeScript front ends, REST APIs, and responsive web applications.",
        },
        {
            "evidence_id": "ev_job_responsive",
            "source": "job",
            "text": "Required: React, TypeScript, API architecture/design, responsive design.",
        },
    ],
}

EQUIVALENCE_SUBSUMPTION_CONTEXT = {
    "candidate_pairs": [
        {
            "term_a": "React",
            "term_b": "JavaScript framework experience",
            "direction_hint": "narrower_than",
            "evidence_refs": ["ev_resume_react", "ev_job_js_framework"],
        }
    ],
    "evidence": [
        {
            "evidence_id": "ev_resume_react",
            "source": "resume",
            "text": "Experience building React and TypeScript front ends.",
        },
        {
            "evidence_id": "ev_job_js_framework",
            "source": "job",
            "text": "Requires JavaScript framework experience for frontend applications.",
        },
    ],
}

EQUIVALENCE_DTO_FIELDS = {
    "id",
    "term_a",
    "term_b",
    "direction",
    "rationale",
    "evidence_refs",
    "confidence",
    "requires_validation",
}


def load_agent_module(test_case: unittest.TestCase):
    try:
        module = importlib.import_module("resume_agent")
    except ModuleNotFoundError as exc:
        test_case.fail(
            "Expected importable package 'resume_agent'. Implement the proposal functions from "
            "resume-agent/TEST_SPEC.md: extractResumeSemantics, extractJobSemantics, "
            "generateClarificationQuestion, interpretUserAnswer, proposeEquivalences, and proposeRewrite."
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


def assert_answer_fact_proposals_have_model_confidence(test_case: unittest.TestCase, result: dict) -> None:
    facts = result.get("fact_proposals", [])
    test_case.assertTrue(facts)
    for fact in facts:
        with test_case.subTest(fact=fact.get("fact_id")):
            test_case.assertIsInstance(fact.get("model_confidence"), (int, float))
            test_case.assertEqual(fact.get("confidence"), fact.get("model_confidence"))
            test_case.assertNotIn("confidence_source", fact)


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


def assert_rewrite_constraint_error(test_case: unittest.TestCase, result: dict, expected_code: str) -> list[dict]:
    test_case.assertEqual(result.get("status"), "error")
    test_case.assertEqual(result.get("error", {}).get("type"), "constraint_error")
    test_case.assertNotIn("operations", result)
    violations = result.get("error", {}).get("violations", [])
    test_case.assertTrue(violations)
    test_case.assertIn(expected_code, {item.get("code") for item in violations})
    return violations


class ResumeAgentSurfaceManifestTests(unittest.TestCase):
    def test_manifest_declares_exact_public_functions(self):
        self.assertEqual(PUBLIC_FUNCTIONS, (
            "extractResumeSemantics",
            "extractJobSemantics",
            "generateClarificationQuestion",
            "interpretUserAnswer",
            "proposeEquivalences",
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

    def test_clarification_question_filters_verified_fact_targets_before_adapter_request(self):
        from resume_agent._fake_adapter import DeterministicFakeAdapter

        class RecordingAdapter:
            def __init__(self):
                self.requests = []
                self.delegate = DeterministicFakeAdapter()

            def complete(self, request):
                self.requests.append(request)
                return self.delegate.complete(request)

        adapter = RecordingAdapter()
        context = {
            "selected_requirement_ids": ["req_aws"],
            "topic": "AWS",
            "target_fact_ids": ["fact_verified", "fact_cloud"],
            "already_verified_fact_ids": ["fact_verified"],
            "context_snippets": ["Preferred: AWS production experience."],
            "_adapter": adapter,
        }
        result = maybe_await(self.agent.generateClarificationQuestion(context))

        assert_proposal_handoff(self, result, "clarification_question")
        self.assertEqual(len(adapter.requests), 1)
        self.assertEqual(adapter.requests[0].input_payload["target_ids"]["fact_ids"], ["fact_cloud"])
        self.assertEqual(result.get("target_fact_ids"), ["fact_cloud"])
        self.assertNotIn("fact_verified", json.dumps(result.get("target_ids"), sort_keys=True))
        self.assertNotIn("fact_verified", json.dumps(result.get("proposals"), sort_keys=True))

    def test_clarification_question_returns_no_question_without_adapter_when_all_fact_targets_verified(self):
        class RaisingAdapter:
            def complete(self, request):
                raise AssertionError("adapter should not be called for fully verified fact targets")

        context = {
            "selected_requirement_ids": ["req_aws"],
            "topic": "AWS",
            "target_fact_ids": ["fact_verified"],
            "already_verified_fact_ids": ["fact_verified"],
            "_adapter": RaisingAdapter(),
        }
        result = maybe_await(self.agent.generateClarificationQuestion(context))

        assert_proposal_handoff(self, result, "clarification_question")
        self.assertEqual(result.get("status"), "ok")
        self.assertFalse(result.get("question_needed"))
        self.assertEqual(result.get("proposals"), [])
        self.assertNotIn("question", result)
        self.assertEqual(result.get("target_fact_ids"), [])

    def test_clarification_question_adapter_failure_returns_typed_error_without_canned_fallback(self):
        context = {
            "selected_requirement_ids": ["req_unpinned"],
            "topic": "Unpinned specialty",
            "already_verified_fact_ids": [],
        }
        result = maybe_await(self.agent.generateClarificationQuestion(context))

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error", {}).get("type"), "provider_error")
        self.assertNotIn("question", result)
        self.assertNotIn("proposals", result)

    def test_canned_clarification_question_literals_are_deleted_from_production_code(self):
        source = (ROOT / "resume-agent" / "resume_agent" / "__init__.py").read_text(encoding="utf-8")
        deleted_literals = [
            " ".join(["What AWS services have you used professionally, and", "for roughly how many years?"]),
            " ".join(["Have you built or maintained GraphQL APIs in production, and", "for roughly how many years?"]),
            " ".join(
                [
                    "What API or application architecture have you designed, and",
                    "what was your role in that work?",
                ]
            ),
        ]

        for literal in deleted_literals:
            with self.subTest(literal=literal):
                self.assertNotIn(literal, source)

    def test_answer_interpretation_keeps_aws_six_years_as_proposal_not_final_verification(self):
        context = {
            "selected_requirement_ids": ["req_aws"],
            "topic": "AWS",
            "question": "What AWS experience can you confirm for this requirement, including services used and production context?",
        }
        answer = "Yes. I have about six years of AWS experience, mainly EC2, S3, Lambda, RDS, and IAM."
        result = maybe_await(self.agent.interpretUserAnswer(answer, context))
        assert_proposal_handoff(self, result, "answer_interpretation")
        assert_fact_proposals_have_verification_state(self, result)
        assert_answer_fact_proposals_have_model_confidence(self, result)
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertIn("aws", serialized)
        self.assertRegex(serialized, r"\bsix\b|\b6\b")
        for service in ["ec2", "s3", "lambda", "rds", "iam"]:
            self.assertIn(service, serialized)
        self.assertNotIn("ten years", serialized)
        self.assertNotIn("final_verification_state", serialized)
        self.assertNotIn("persisted", serialized)

    def test_verified_aws_denial_regression_emits_explicit_absence_without_positive_fact(self):
        context = {
            "selected_requirement_ids": ["req_aws"],
            "topic": "AWS",
            "question": "What AWS services have you used professionally?",
        }
        result = maybe_await(self.agent.interpretUserAnswer("No, I have never used AWS professionally", context))

        assert_proposal_handoff(self, result, "answer_interpretation")
        self.assertEqual(result.get("polarity"), "denied")
        self.assertEqual(result.get("fact_proposals"), [])
        self.assertEqual(result.get("requirement_resolution_proposals", [])[0].get("suggested_state"), "explicitly_missing")
        self.assertEqual(result.get("requirement_resolution_proposals", [])[0].get("supporting_fact_ids"), [])

    def test_answer_interpretation_negation_battery_denials_are_explicit_absence_only(self):
        cases = [
            (
                "graphql_havent",
                "I haven't",
                {
                    "selected_requirement_ids": ["req_graphql"],
                    "topic": "GraphQL",
                    "question": "Have you built GraphQL APIs in production?",
                },
            ),
            (
                "kubernetes_not_professionally",
                "Not professionally",
                {
                    "selected_requirement_ids": ["req_kubernetes"],
                    "topic": "Kubernetes",
                    "question": "Have you used Kubernetes professionally?",
                },
            ),
            (
                "terraform_school_only",
                "Only in school",
                {
                    "selected_requirement_ids": ["req_terraform"],
                    "topic": "Terraform",
                    "question": "What Terraform infrastructure-as-code experience do you have?",
                },
            ),
        ]

        for name, answer, context in cases:
            with self.subTest(name=name):
                result = maybe_await(self.agent.interpretUserAnswer(answer, context))
                assert_proposal_handoff(self, result, "answer_interpretation")
                self.assertEqual(result.get("polarity"), "denied")
                self.assertEqual(result.get("fact_proposals"), [])
                self.assertTrue(result.get("evidence_proposals"))
                states = {item.get("suggested_state") for item in result.get("requirement_resolution_proposals", [])}
                self.assertEqual(states, {"explicitly_missing"})

    def test_answer_interpretation_denied_positive_fact_post_guard_blocks_payload(self):
        from resume_agent._fake_adapter import DeterministicFakeAdapter, deterministic_fake_key
        from resume_agent._interview_requests import build_answer_interpretation_request

        answer = "No, I have never used AWS professionally"
        context = {
            "selected_requirement_ids": ["req_aws"],
            "topic": "AWS",
            "question": "What AWS services have you used professionally?",
        }
        request = build_answer_interpretation_request(context["question"], answer, context["topic"])
        key_hash = deterministic_fake_key(request.prompt_template_id, request.output_schema_id, request.input_payload)
        payload = fixture_payload("resume-agent-answer-interpretation-aws-denial")
        inconsistent = copy.deepcopy(payload)
        inconsistent["factProposals"] = [
            {
                "fact_id": "fact_aws_inconsistent_positive",
                "category": "skill",
                "text": "AWS professional experience",
                "normalized_terms": ["aws"],
                "source_evidence_ids": ["ev_answer_aws_denial"],
                "evidence": [
                    {
                        "evidence_id": "ev_answer_aws_denial",
                        "source_text": answer,
                        "span": {"start": 0, "end": 40},
                    }
                ],
                "verification_state": "inferred",
                "confidence": 0.88,
                "hedge_or_qualifier": None,
            }
        ]

        with tempfile.TemporaryDirectory(prefix="resume-agent-denied-guard-") as temp:
            fixture_dir = Path(temp)
            fixture = _answer_interpretation_fixture_envelope(key_hash, request, inconsistent)
            (fixture_dir / f"{key_hash}.json").write_text(json.dumps(fixture), encoding="utf-8")
            result = maybe_await(
                self.agent.interpretUserAnswer(answer, {**context, "_adapter": DeterministicFakeAdapter(fixture_dir=fixture_dir)})
            )

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error", {}).get("type"), "schema_invalid")
        self.assertEqual(result.get("error", {}).get("details", {}).get("reason"), "denied_positive_fact_guard")
        self.assertNotIn("fact_proposals", result)
        self.assertNotIn("proposals", result)

    def test_answer_interpretation_qualified_graphql_preserves_hedge_and_partial_resolution(self):
        context = {
            "selected_requirement_ids": ["req_graphql"],
            "topic": "GraphQL",
            "question": "Have you built GraphQL APIs in production?",
        }
        answer = "Yes, but only internal tools"
        result = maybe_await(self.agent.interpretUserAnswer(answer, context))
        assert_proposal_handoff(self, result, "answer_interpretation")
        assert_fact_proposals_have_verification_state(self, result)
        assert_answer_fact_proposals_have_model_confidence(self, result)
        self.assertEqual(result.get("polarity"), "qualified")
        resolution = result.get("requirement_resolution_proposals", [])[0]
        fact = result.get("fact_proposals", [])[0]
        self.assertEqual(resolution.get("suggested_state"), "possible_match")
        self.assertEqual(resolution.get("hedge_or_qualifier"), "only internal tools")
        self.assertEqual(fact.get("hedge_or_qualifier"), "only internal tools")
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertIn("graphql", serialized)
        self.assertIn("internal tools", serialized)

    def test_answer_interpretation_records_architecture_without_staff_title_inflation(self):
        context = {
            "selected_requirement_ids": ["req_api_architecture"],
            "topic": "API architecture",
            "question": "What API or application architecture have you designed?",
        }
        answer = "Yes, I designed REST API architecture for customer-facing SaaS products."
        result = maybe_await(self.agent.interpretUserAnswer(answer, context))
        assert_proposal_handoff(self, result, "answer_interpretation")
        assert_fact_proposals_have_verification_state(self, result)
        assert_answer_fact_proposals_have_model_confidence(self, result)
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertIn("architecture", serialized)
        self.assertIn("api", serialized)
        self.assertNotIn("staff_title_employment_history", serialized)

    def test_answer_interpretation_handles_arbitrary_terraform_topic_via_adapter(self):
        context = {
            "selected_requirement_ids": ["req_terraform"],
            "topic": "Terraform",
            "question": "What Terraform infrastructure-as-code experience do you have?",
        }
        answer = "I used Terraform to manage GCP infrastructure modules for internal platform environments."
        result = maybe_await(self.agent.interpretUserAnswer(answer, context))

        assert_proposal_handoff(self, result, "answer_interpretation")
        assert_fact_proposals_have_verification_state(self, result)
        assert_answer_fact_proposals_have_model_confidence(self, result)
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertIn("terraform", serialized)
        self.assertIn("gcp infrastructure", serialized)

    def test_answer_interpretation_adapter_failure_returns_typed_error_without_partial_interpretation(self):
        context = {
            "selected_requirement_ids": ["req_unpinned"],
            "topic": "Unpinned answer topic",
            "question": "What can you confirm about this unpinned answer topic?",
        }
        result = maybe_await(self.agent.interpretUserAnswer("Yes, I have done that.", context))

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error", {}).get("type"), "provider_error")
        self.assertNotIn("fact_proposals", result)
        self.assertNotIn("proposals", result)

    def test_topic_substring_interpretation_and_service_list_are_deleted_from_production_code(self):
        source = (ROOT / "resume-agent" / "resume_agent" / "__init__.py").read_text(encoding="utf-8")

        deleted_fragments = [
            "topic_lower",
            "_mentioned_terms",
            "\"CloudFront\"",
            "\"DynamoDB\"",
            "\"EC2\", \"S3\", \"Lambda\", \"RDS\", \"IAM\"",
            "confidence_source",
            "Built {",
            "unique_phrases",
            "terminology_changes",
            "[:max_chars]",
            "[: max_chars]",
            "after[:",
            "after_text[:",
        ]
        for fragment in deleted_fragments:
            with self.subTest(fragment=fragment):
                self.assertNotIn(fragment, source)

    def test_equivalence_proposals_are_exact_dtos_requiring_validation(self):
        result = maybe_await(self.agent.proposeEquivalences(EQUIVALENCE_ALIAS_CONTEXT))

        self.assertIsInstance(result, list)
        self.assertTrue(result)
        proposal = result[0]
        self.assertEqual(set(proposal), EQUIVALENCE_DTO_FIELDS)
        self.assertEqual(proposal["term_a"], "responsive web apps")
        self.assertEqual(proposal["term_b"], "responsive design")
        self.assertIn(proposal["direction"], {"equivalent", "narrower_than", "broader_than"})
        self.assertEqual(proposal["direction"], "equivalent")
        self.assertTrue(proposal["requires_validation"])
        self.assertTrue(proposal["rationale"])
        self.assertIsInstance(proposal["confidence"], (int, float))
        self.assertTrue(set(proposal["evidence_refs"]) <= {"ev_resume_responsive", "ev_job_responsive"})
        serialized = json.dumps(result, sort_keys=True).lower()
        for forbidden in ["persisted_relationship", "official_truth", "final_verification_state", "sqlite"]:
            self.assertNotIn(forbidden, serialized)

    def test_equivalence_empty_candidate_context_returns_empty_list_without_adapter_call(self):
        from resume_agent._fake_adapter import DeterministicFakeAdapter

        adapter = DeterministicFakeAdapter()
        result = maybe_await(self.agent.proposeEquivalences({"candidate_pairs": [], "evidence": [], "_adapter": adapter}))

        self.assertEqual(result, [])
        self.assertEqual(adapter.call_audit_sink.records, [])

    def test_equivalence_ids_are_deterministic_for_identical_inputs(self):
        first = maybe_await(self.agent.proposeEquivalences(EQUIVALENCE_ALIAS_CONTEXT))
        second = maybe_await(self.agent.proposeEquivalences(copy.deepcopy(EQUIVALENCE_ALIAS_CONTEXT)))

        self.assertEqual(first, second)
        self.assertRegex(first[0]["id"], r"^equiv_[0-9a-f]{10}$")
        self.assertNotEqual(first[0]["id"], fixture_payload("resume-agent-equivalence-alias-responsive")[0]["id"])

    def test_equivalence_alias_miss_fixture_produces_proposal(self):
        result = maybe_await(self.agent.proposeEquivalences(EQUIVALENCE_ALIAS_CONTEXT))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["direction"], "equivalent")
        self.assertIn("responsive web apps", json.dumps(result, sort_keys=True).lower())
        self.assertIn("responsive design", json.dumps(result, sort_keys=True).lower())

    def test_equivalence_subsumption_fixture_preserves_direction(self):
        result = maybe_await(self.agent.proposeEquivalences(EQUIVALENCE_SUBSUMPTION_CONTEXT))

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["term_a"], "React")
        self.assertEqual(result[0]["term_b"], "JavaScript framework experience")
        self.assertEqual(result[0]["direction"], "narrower_than")

    def test_equivalence_post_guard_rejects_unresolved_evidence_refs(self):
        from resume_agent._adapters import AdapterRequest
        from resume_agent._equivalence_requests import build_equivalence_request
        from resume_agent._fake_adapter import DeterministicFakeAdapter, deterministic_fake_key

        request = build_equivalence_request(EQUIVALENCE_ALIAS_CONTEXT)
        self.assertIsInstance(request, AdapterRequest)
        payload = copy.deepcopy(fixture_payload("resume-agent-equivalence-alias-responsive"))
        payload[0]["evidence_refs"] = ["ev_external"]
        key_hash = deterministic_fake_key(request.prompt_template_id, request.output_schema_id, request.input_payload)

        with tempfile.TemporaryDirectory() as temp:
            fixture_dir = Path(temp)
            (fixture_dir / f"{key_hash}.json").write_text(
                json.dumps(
                    _fake_adapter_fixture_envelope(
                        "resume-agent-equivalence-unresolved-evidence-in-test",
                        key_hash,
                        request,
                        payload,
                        ["Schema-valid equivalence proposal cites evidence outside the supplied context."],
                    )
                ),
                encoding="utf-8",
            )
            result = maybe_await(
                self.agent.proposeEquivalences({**EQUIVALENCE_ALIAS_CONTEXT, "_adapter": DeterministicFakeAdapter(fixture_dir=fixture_dir)})
            )

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error", {}).get("type"), "guard_error")
        self.assertNotIsInstance(result, list)
        violation_codes = {item.get("code") for item in result.get("error", {}).get("violations", [])}
        self.assertIn("evidence_ref_not_supplied", violation_codes)

    def test_equivalence_adapter_failure_returns_typed_error_without_partial_proposals(self):
        from resume_agent._fake_adapter import DeterministicFakeAdapter

        with tempfile.TemporaryDirectory() as temp:
            result = maybe_await(
                self.agent.proposeEquivalences({**EQUIVALENCE_ALIAS_CONTEXT, "_adapter": DeterministicFakeAdapter(fixture_dir=Path(temp))})
            )

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error", {}).get("type"), "provider_error")
        self.assertNotIsInstance(result, list)

    def test_equivalence_adapter_call_emits_audit_record(self):
        from resume_agent._fake_adapter import DeterministicFakeAdapter

        adapter = DeterministicFakeAdapter()
        result = maybe_await(self.agent.proposeEquivalences({**EQUIVALENCE_ALIAS_CONTEXT, "_adapter": adapter}))

        self.assertIsInstance(result, list)
        self.assertEqual(len(adapter.call_audit_sink.records), 1)
        self.assertEqual(adapter.call_audit_sink.records[0]["outcome"], "ok")
        self.assertIn("schema_hash", adapter.call_audit_sink.records[0])

    def test_rewrite_proposals_are_resume_change_operations_grounded_in_allowed_facts(self):
        result = maybe_await(self.agent.proposeRewrite(REWRITE_API_ONLY_CONTEXT))
        assert_proposal_handoff(self, result, "rewrite_proposal")
        operations = result.get("operations", [])
        self.assertTrue(operations)
        for operation in operations:
            with self.subTest(operation=operation.get("operation_id")):
                for field in [
                    "operation_id",
                    "operation_type",
                    "op",
                    "target_path",
                    "path",
                    "before",
                    "after",
                    "linked_fact_ids",
                    "linked_requirement_ids",
                    "factIds",
                    "requirementIds",
                    "provenance",
                    "reason",
                    "confidence",
                    "grounding",
                    "status",
                ]:
                    self.assertIn(field, operation)
                self.assertEqual(operation["operation_type"], "rewrite")
                self.assertEqual(operation["op"], "rewrite")
                self.assertEqual(operation["target_path"], "/experience/0/bullets/0")
                self.assertEqual(operation["linked_fact_ids"], ["fact_api"])
                self.assertEqual(operation["factIds"], ["fact_api"])
                self.assertIsInstance(operation["confidence"], float)
                self.assertNotEqual(operation["status"], "applied")
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertNotIn("aws", serialized)
        self.assertNotIn("graphql", serialized)
        self.assertNotIn("staff software engineer", serialized)
        self.assertNotRegex(serialized, r"\b20 million\b|\b30 engineers\b")

    def test_api_fact_only_rewrite_never_adds_responsive_design(self):
        result = maybe_await(self.agent.proposeRewrite(REWRITE_API_ONLY_CONTEXT))

        self.assertNotEqual(result.get("status"), "error")
        serialized = json.dumps(result, sort_keys=True).lower()
        self.assertNotIn("responsive design", serialized)
        self.assertIn("rest api architecture", serialized)

    def test_rewrite_grounding_post_guard_rejects_missing_added_term_map_entry(self):
        context = {
            **REWRITE_API_ONLY_CONTEXT,
            "requirement_ids": ["req_api", "req_graphql"],
            "requirements": [
                {"requirement_id": "req_api", "source_text": "API architecture/design"},
                {"requirement_id": "req_graphql", "source_text": "GraphQL APIs"},
            ],
            "length_constraints": {"max_chars": 180},
            "prohibited_additions": [],
        }

        result = maybe_await(self.agent.proposeRewrite(context))

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error", {}).get("type"), "guard_error")
        self.assertNotIn("operations", result)
        violation_codes = {item.get("code") for item in result.get("error", {}).get("violations", [])}
        self.assertIn("ungrounded_added_content", violation_codes)

    def test_rewrite_grounding_post_guard_rejects_out_of_allowed_fact_id(self):
        from resume_agent._fake_adapter import DeterministicFakeAdapter, deterministic_fake_key
        from resume_agent._rewrite_requests import build_rewrite_request
        from resume_agent._adapters import AdapterRequest

        request = build_rewrite_request(REWRITE_API_ONLY_CONTEXT)
        self.assertIsInstance(request, AdapterRequest)
        payload = copy.deepcopy(fixture_payload("resume-agent-rewrite-grounded-api-only"))
        operation = payload["operations"][0]
        operation["linked_fact_ids"] = ["fact_external"]
        operation["factIds"] = ["fact_external"]
        operation["provenance"][0]["fact_id"] = "fact_external"
        operation["grounding"][0]["fact_id"] = "fact_external"
        key_hash = deterministic_fake_key(request.prompt_template_id, request.output_schema_id, request.input_payload)

        with tempfile.TemporaryDirectory() as temp:
            fixture_dir = Path(temp)
            (fixture_dir / f"{key_hash}.json").write_text(
                json.dumps(
                    _fake_adapter_fixture_envelope(
                        "resume-agent-rewrite-out-of-allowed-fact-in-test",
                        key_hash,
                        request,
                        payload,
                        ["Schema-valid rewrite cites a fact id outside the allowed set."],
                    )
                ),
                encoding="utf-8",
            )
            result = maybe_await(
                self.agent.proposeRewrite({**REWRITE_API_ONLY_CONTEXT, "_adapter": DeterministicFakeAdapter(fixture_dir=fixture_dir)})
            )

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error", {}).get("type"), "guard_error")
        violation_codes = {item.get("code") for item in result.get("error", {}).get("violations", [])}
        self.assertIn("fact_id_not_allowed", violation_codes)
        self.assertIn("ungrounded_added_content", violation_codes)

    def test_rewrite_voice_constraint_post_check_rejects_present_tense_fixture(self):
        result = maybe_await(self.agent.proposeRewrite(REWRITE_VOICE_VIOLATION_CONTEXT))

        violations = assert_rewrite_constraint_error(self, result, "voice_tense_not_past")
        self.assertIn(
            {"tense": "past", "leading_verb": "designs"},
            [item.get("details") for item in violations],
        )

    def test_rewrite_length_constraint_post_check_rejects_over_limit_fixture_without_truncation(self):
        payload = fixture_payload("resume-agent-rewrite-constraint-length-violation")
        operation = payload["operations"][0]
        self.assertGreater(len(operation["after"]), REWRITE_LENGTH_VIOLATION_CONTEXT["length_constraints"]["max_chars"])

        result = maybe_await(self.agent.proposeRewrite(REWRITE_LENGTH_VIOLATION_CONTEXT))

        violations = assert_rewrite_constraint_error(self, result, "length_max_chars_exceeded")
        length_details = [item.get("details", {}) for item in violations if item.get("code") == "length_max_chars_exceeded"]
        self.assertEqual(length_details[0]["max_chars"], 70)
        self.assertGreater(length_details[0]["actual_chars"], length_details[0]["max_chars"])

    def test_rewrite_prohibited_addition_post_check_rejects_grounded_banned_term_fixture(self):
        result = maybe_await(self.agent.proposeRewrite(REWRITE_PROHIBITED_ADDITION_CONTEXT))

        violations = assert_rewrite_constraint_error(self, result, "prohibited_addition")
        terms = {item.get("details", {}).get("term") for item in violations}
        self.assertIn("GraphQL", terms)

    def test_rewrite_adapter_failure_returns_typed_error_without_template_fallback(self):
        from resume_agent._fake_adapter import DeterministicFakeAdapter

        with tempfile.TemporaryDirectory() as temp:
            result = maybe_await(
                self.agent.proposeRewrite({**REWRITE_API_ONLY_CONTEXT, "_adapter": DeterministicFakeAdapter(fixture_dir=Path(temp))})
            )

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error", {}).get("type"), "provider_error")
        self.assertNotIn("operations", result)
        self.assertNotIn("proposals", result)
        self.assertNotIn("Built ", json.dumps(result, sort_keys=True))

    def test_malformed_or_empty_inputs_return_typed_errors_without_tracebacks(self):
        invalid_calls = [
            (self.agent.extractResumeSemantics, [""]),
            (self.agent.extractJobSemantics, [""]),
            (self.agent.generateClarificationQuestion, [{"selected_requirement_ids": [], "topic": ""}]),
            (self.agent.interpretUserAnswer, ["", {"selected_requirement_ids": ["req_aws"], "topic": "AWS"}]),
            (self.agent.proposeEquivalences, [None]),
            (self.agent.proposeEquivalences, [{"candidate_pairs": "responsive"}]),
            (self.agent.proposeRewrite, [{"original_text": "Built apps."}]),
        ]
        for function, args in invalid_calls:
            with self.subTest(function=function.__name__):
                result = maybe_await(function(*args))
                self.assertEqual(result["status"], "error")
                self.assertIn(result["error"]["type"], {"validation_error", "schema_error", "policy_error"})
                self.assertNotRegex(json.dumps(result).lower(), r"\btraceback|sqlite|select|insert|update|delete\b")



if __name__ == "__main__":
    unittest.main()
