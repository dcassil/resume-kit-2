"""Contract tests for the private resume-agent model adapter seam."""

from __future__ import annotations

import unittest
import copy
import json
import sys
import tempfile
import types
from pathlib import Path

from resume_agent._adapters import (
    ADAPTER_FAILURE_TYPES,
    AdapterCompletion,
    AdapterProviderError,
    AdapterRefusalError,
    AdapterRequest,
    LiveAdapterConstructionBlockedError,
    ValidatingModelAdapter,
    create_live_model_adapter,
)
from resume_agent import AGENT_CONFIG_DEFAULTS, resolve_agent_config, stable_agent_config_hash
from resume_agent._fake_adapter import (
    DEFAULT_FAKE_OUTPUT_SCHEMAS,
    FACT_PROPOSAL_SCHEMA_ID,
    REWRITE_PROPOSAL_SCHEMA_ID,
    DeterministicFakeAdapter,
    deterministic_fake_key,
    validate_fake_fixture_dir,
)
from resume_agent._extraction_requests import (
    JOB_EXTRACTION_PROMPT_TEMPLATE_ID,
    RESUME_EXTRACTION_PROMPT_TEMPLATE_ID,
    build_job_extraction_request,
    build_resume_extraction_request,
    prompt_template_text,
)
from resume_agent._extraction_schemas import JOB_EXTRACTION_SCHEMA_ID, RESUME_EXTRACTION_SCHEMA_ID
from resume_agent._interview_requests import (
    ANSWER_INTERPRETATION_PROMPT_TEMPLATE_ID,
    QUESTION_GENERATION_PROMPT_TEMPLATE_ID,
    build_answer_interpretation_request,
    build_question_request,
    prompt_template_text as interview_prompt_template_text,
)
from resume_agent._interview_schemas import ANSWER_INTERPRETATION_SCHEMA_ID, QUESTION_GENERATION_SCHEMA_ID
from resume_agent._schema_validation import validate_json_schema, validate_schema_id


ROOT = Path(__file__).resolve().parents[2]
FAKE_FIXTURES = ROOT / "fixtures" / "resume-agent" / "fake-adapter"
TEST_SCHEMA_ID = "contract.proposal.v1"
TEST_SCHEMA = {
    "schema_version": TEST_SCHEMA_ID,
    "type": "object",
    "required": ["schema_version", "proposal_type", "requires_validation", "items"],
    "properties": {
        "schema_version": {"type": "string", "minLength": 1},
        "proposal_type": {"enum": ["contract_demo"]},
        "requires_validation": {"enum": [True]},
        "items": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name", "count"],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "count": {"type": "number"},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}


VALID_PAYLOAD = {
    "schema_version": TEST_SCHEMA_ID,
    "proposal_type": "contract_demo",
    "requires_validation": True,
    "items": [{"name": "one", "count": 1}],
}


FACT_SEED_INPUT = {
    "resume_text": "Daniel Candidate\nSoftware Engineer\nBuilt React and TypeScript front ends and designed REST API architecture for SaaS products."
}
FACT_SEED_TEMPLATE = "resume-agent.extract-resume-semantics.v1"
FACT_SEED_KEY = "300120704f1c601ece4f28ecbe7767029407485e3c14ed5dae4a4ad5b80ca684"

REWRITE_SEED_INPUT = {
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
    "length_constraints": {"max_chars": 160},
    "voice_constraints": {"style": "concise", "tense": "past"},
}
REWRITE_SEED_TEMPLATE = "resume-agent.propose-rewrite.v1"
REWRITE_SEED_KEY = "804cc1b63efc716aff6873933e8a999a57551ee379f20315212d8a12f70cf2de"

LEGACY_RESUME_FIXTURE = """
Daniel Candidate
Software Engineer

Experience building React and TypeScript front ends, REST APIs, and responsive web applications.
Designed API architecture for customer-facing SaaS products.
"""

LEGACY_JOB_FIXTURE = """
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

AWS_QUESTION_REQUEST_ARGS = (
    "AWS",
    {"requirement_ids": ["req_aws"], "fact_ids": ["fact_cloud"]},
    ["Preferred: AWS production experience."],
)
TERRAFORM_QUESTION_REQUEST_ARGS = (
    "Terraform",
    {"requirement_ids": ["req_terraform"], "fact_ids": ["fact_iac"]},
    ["Preferred: Terraform infrastructure-as-code experience."],
)
AWS_DENIAL_ANSWER = "No, I have never used AWS professionally"
GRAPHQL_QUALIFIED_ANSWER = "Yes, but only internal tools"
ARCHITECTURE_AFFIRMED_ANSWER = "Yes, I designed REST API architecture for customer-facing SaaS products."
AWS_UNRESPONSIVE_ANSWER = "I really prefer working on frontend design systems."
TERRAFORM_AFFIRMED_ANSWER = "I used Terraform to manage GCP infrastructure modules for internal platform environments."


def request() -> AdapterRequest:
    return AdapterRequest(
        prompt_template_id="contract-template",
        prompt="Return a contract demo object.",
        input_payload={"subject": "adapter"},
        output_schema_id=TEST_SCHEMA_ID,
    )


class StaticAdapter(ValidatingModelAdapter):
    def __init__(self, outcome):
        super().__init__(
            adapter_id="contract-double",
            adapter_version="0.0.1",
            model_id="contract-model",
            runtime_config={"temperature": 0, "timeout_ms": 1000},
            output_schemas={TEST_SCHEMA_ID: TEST_SCHEMA},
        )
        self.outcome = outcome

    def _complete_unchecked(self, _request):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class RetryProviderError(AdapterProviderError):
    retries = 2
    usage = {"input_tokens": 9}


class ResumeAgentAdapterContractTests(unittest.TestCase):
    def assert_metadata(self, result):
        self.assertEqual(result.adapter_id, "contract-double")
        self.assertEqual(result.adapter_version, "0.0.1")
        self.assertEqual(result.model_id, "contract-model")
        self.assertEqual(result.runtime_config["temperature"], 0)
        self.assertIsInstance(result.retries, int)
        self.assertIsInstance(result.usage, dict)

        as_dict = result.to_dict()
        for field in ["adapter_id", "adapter_version", "model_id", "runtime_config", "retries", "usage"]:
            self.assertIn(field, as_dict)

    def test_success_result_carries_checked_payload_and_model_metadata(self):
        adapter = StaticAdapter(AdapterCompletion(payload=VALID_PAYLOAD, retries=1, usage={"output_tokens": 7}))
        result = adapter.complete(request())

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.payload, VALID_PAYLOAD)
        self.assertEqual(result.retries, 1)
        self.assertEqual(result.usage["output_tokens"], 7)
        self.assert_metadata(result)
        self.assertNotIn("error", result.to_dict())

    def test_failure_result_carries_model_metadata(self):
        result = StaticAdapter(RetryProviderError("provider unavailable")).complete(request())

        self.assertEqual(result.status, "error")
        self.assertEqual(result.error.type, "provider_error")
        self.assertEqual(result.retries, 2)
        self.assertEqual(result.usage["input_tokens"], 9)
        self.assert_metadata(result)
        self.assertIn("error", result.to_dict())

    def test_out_of_schema_payload_returns_schema_invalid_with_violations(self):
        invalid_payload = {
            "schema_version": TEST_SCHEMA_ID,
            "proposal_type": "contract_demo",
            "requires_validation": True,
            "items": [{"name": "", "count": "one", "extra": True}],
        }
        result = StaticAdapter(invalid_payload).complete(request())

        self.assertEqual(result.status, "error")
        self.assertEqual(result.error.type, "schema_invalid")
        violations = result.error.violations
        self.assertTrue(violations)
        self.assertIn(("min_length", "items/0/name"), {(item.get("code"), item.get("field_path")) for item in violations})
        self.assertIn(("invalid_type", "items/0/count"), {(item.get("code"), item.get("field_path")) for item in violations})
        self.assertIn(("additional_property", "items/0/extra"), {(item.get("code"), item.get("field_path")) for item in violations})
        self.assertNotIn("payload", result.to_dict())

    def test_failure_taxonomy_is_closed_and_class_based(self):
        cases = [
            (TimeoutError("arbitrary wording"), "timeout"),
            (AdapterRefusalError("arbitrary wording"), "refused"),
            (AdapterProviderError("arbitrary wording"), "provider_error"),
            (RuntimeError("arbitrary wording"), "provider_error"),
        ]
        self.assertEqual(set(ADAPTER_FAILURE_TYPES), {"timeout", "schema_invalid", "refused", "provider_error"})
        for exc, expected_type in cases:
            with self.subTest(exc=exc.__class__.__name__):
                result = StaticAdapter(exc).complete(request())
                self.assertEqual(result.status, "error")
                self.assertEqual(result.error.type, expected_type)


class ResumeAgentDeterministicFakeAdapterContractTests(unittest.TestCase):
    def fake_request(self) -> AdapterRequest:
        return AdapterRequest(
            prompt_template_id=FACT_SEED_TEMPLATE,
            prompt="Extract source-grounded fact proposals.",
            input_payload=FACT_SEED_INPUT,
            output_schema_id=FACT_PROPOSAL_SCHEMA_ID,
        )

    def test_seed_fixture_keys_are_stable_hashes_of_template_schema_and_canonical_input(self):
        self.assertEqual(deterministic_fake_key(FACT_SEED_TEMPLATE, FACT_PROPOSAL_SCHEMA_ID, FACT_SEED_INPUT), FACT_SEED_KEY)
        self.assertEqual(
            deterministic_fake_key(REWRITE_SEED_TEMPLATE, REWRITE_PROPOSAL_SCHEMA_ID, REWRITE_SEED_INPUT),
            REWRITE_SEED_KEY,
        )
        self.assertTrue((FAKE_FIXTURES / f"{FACT_SEED_KEY}.json").is_file())
        self.assertTrue((FAKE_FIXTURES / f"{REWRITE_SEED_KEY}.json").is_file())

    def test_fake_success_carries_metadata_and_seed_payload(self):
        result = DeterministicFakeAdapter(fixture_dir=FAKE_FIXTURES).complete(self.fake_request())

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.adapter_id, "resume-agent-deterministic-fake")
        self.assertEqual(result.model_id, "deterministic-fixture-v1")
        self.assertEqual(result.runtime_config["key_algorithm"], "sha256:v1")
        self.assertEqual(result.retries, 0)
        self.assertEqual(result.usage["fixture_hits"], 1)
        self.assertEqual(result.payload["proposal_type"], "resume_semantic_extraction")
        self.assertTrue(result.payload["requires_validation"])

    def test_fake_result_is_byte_deterministic_for_identical_requests(self):
        adapter = DeterministicFakeAdapter(fixture_dir=FAKE_FIXTURES)
        first = json.dumps(adapter.complete(self.fake_request()).to_dict(), sort_keys=True, separators=(",", ":"))
        second = json.dumps(adapter.complete(self.fake_request()).to_dict(), sort_keys=True, separators=(",", ":"))

        self.assertEqual(first, second)

    def test_unknown_fake_key_returns_typed_provider_error_without_improvised_output(self):
        request = AdapterRequest(
            prompt_template_id=FACT_SEED_TEMPLATE,
            prompt="Extract source-grounded fact proposals.",
            input_payload={"resume_text": "Different input with no fixture."},
            output_schema_id=FACT_PROPOSAL_SCHEMA_ID,
        )
        expected_key = deterministic_fake_key(request.prompt_template_id, request.output_schema_id, request.input_payload)
        result = DeterministicFakeAdapter(fixture_dir=FAKE_FIXTURES).complete(request)

        self.assertEqual(result.status, "error")
        self.assertIsNone(result.payload)
        self.assertEqual(result.error.type, "provider_error")
        self.assertIn(expected_key, result.error.message)
        self.assertIn(FACT_SEED_TEMPLATE, result.error.message)
        self.assertIn(FACT_PROPOSAL_SCHEMA_ID, result.error.message)
        self.assertEqual(result.error.details["reason"], "deterministic_fake_missing_fixture")
        self.assertEqual(result.error.details["missing_key_hash"], expected_key)

    def test_deliberately_broken_in_test_fixture_returns_schema_invalid(self):
        with tempfile.TemporaryDirectory(prefix="resume-agent-fake-") as temp:
            temp_dir = Path(temp)
            fixture_path = temp_dir / f"{FACT_SEED_KEY}.json"
            fixture_path.write_text(json.dumps(_fake_fixture_envelope({"schema_version": FACT_PROPOSAL_SCHEMA_ID}), indent=2), encoding="utf-8")

            result = DeterministicFakeAdapter(fixture_dir=temp_dir).complete(self.fake_request())

        self.assertEqual(result.status, "error")
        self.assertEqual(result.error.type, "schema_invalid")
        self.assertIn(("missing_field", "proposal_type"), {(item.get("code"), item.get("field_path")) for item in result.error.violations})
        self.assertIn(("missing_field", "fact_proposals"), {(item.get("code"), item.get("field_path")) for item in result.error.violations})

    def test_all_official_fake_fixtures_self_validate_against_shared_schema_validator(self):
        failures = validate_fake_fixture_dir(FAKE_FIXTURES)

        self.assertEqual(failures, {})

    def test_live_adapter_construction_is_blocked_without_opt_in_and_in_gate_profile(self):
        with self.assertRaises(LiveAdapterConstructionBlockedError) as absent_opt_in:
            create_live_model_adapter(env={})
        self.assertEqual(absent_opt_in.exception.details["reason"], "live_adapter_requires_explicit_opt_in")

        with self.assertRaises(LiveAdapterConstructionBlockedError):
            create_live_model_adapter(env={"RESUME_AGENT_ALLOW_LIVE": "1", "RESUME_AGENT_GATE_PROFILE": "1"})

    def test_public_adapter_construction_paths_do_not_accept_raw_runtime_config_dicts(self):
        with self.assertRaises(TypeError):
            DeterministicFakeAdapter(fixture_dir=FAKE_FIXTURES, runtime_config={"model": "raw-dict"})

        with self.assertRaises(TypeError):
            create_live_model_adapter(env={"RESUME_AGENT_ALLOW_LIVE": "1"}, runtime_config={"model": "raw-dict"})

        with self.assertRaises(TypeError):
            DeterministicFakeAdapter(fixture_dir=FAKE_FIXTURES, agent_config={"model": "raw-dict"})

        with self.assertRaises(TypeError):
            create_live_model_adapter(env={"RESUME_AGENT_ALLOW_LIVE": "1"}, agent_config={"model": "raw-dict"})


class ResumeAgentExtractionSchemaContractTests(unittest.TestCase):
    def test_extraction_schema_ids_are_registered_with_fake_adapter_validator(self):
        self.assertIn(RESUME_EXTRACTION_SCHEMA_ID, DEFAULT_FAKE_OUTPUT_SCHEMAS)
        self.assertIn(JOB_EXTRACTION_SCHEMA_ID, DEFAULT_FAKE_OUTPUT_SCHEMAS)

        resume_payload = _fixture_payload("resume-agent-extraction-ml-engineer-resume")
        job_payload = _fixture_payload("resume-agent-extraction-python-spark-job")

        self.assertEqual(validate_schema_id(resume_payload, RESUME_EXTRACTION_SCHEMA_ID, DEFAULT_FAKE_OUTPUT_SCHEMAS), [])
        self.assertEqual(validate_schema_id(job_payload, JOB_EXTRACTION_SCHEMA_ID, DEFAULT_FAKE_OUTPUT_SCHEMAS), [])

    def test_extraction_schemas_require_item_evidence_and_confidence(self):
        resume_payload = copy.deepcopy(_fixture_payload("resume-agent-extraction-ml-engineer-resume"))
        del resume_payload["skills"][0]["evidence"]
        del resume_payload["experience"][0]["confidence"]

        job_payload = copy.deepcopy(_fixture_payload("resume-agent-extraction-python-spark-job"))
        del job_payload["requirements"][0]["evidence"]
        del job_payload["requirements"][0]["confidence"]

        resume_violations = validate_schema_id(resume_payload, RESUME_EXTRACTION_SCHEMA_ID, DEFAULT_FAKE_OUTPUT_SCHEMAS)
        job_violations = validate_schema_id(job_payload, JOB_EXTRACTION_SCHEMA_ID, DEFAULT_FAKE_OUTPUT_SCHEMAS)

        resume_pairs = {(item.get("code"), item.get("field_path")) for item in resume_violations}
        job_pairs = {(item.get("code"), item.get("field_path")) for item in job_violations}
        self.assertIn(("missing_field", "skills/0/evidence"), resume_pairs)
        self.assertIn(("missing_field", "experience/0/confidence"), resume_pairs)
        self.assertIn(("missing_field", "requirements/0/evidence"), job_pairs)
        self.assertIn(("missing_field", "requirements/0/confidence"), job_pairs)

    def test_prompt_assets_use_template_id_at_version_convention(self):
        self.assertEqual(RESUME_EXTRACTION_PROMPT_TEMPLATE_ID, "resume-agent.resume-extraction@v1")
        self.assertEqual(JOB_EXTRACTION_PROMPT_TEMPLATE_ID, "resume-agent.job-extraction@v1")
        self.assertIn("Return only JSON", prompt_template_text(RESUME_EXTRACTION_PROMPT_TEMPLATE_ID))
        self.assertIn("Return only JSON", prompt_template_text(JOB_EXTRACTION_PROMPT_TEMPLATE_ID))

    def test_extraction_request_builders_are_deterministic(self):
        first = build_resume_extraction_request(ML_ENGINEER_RESUME, source_id="ml-engineer-golden-resume")
        second = build_resume_extraction_request(ML_ENGINEER_RESUME, source_id="ml-engineer-golden-resume")
        changed_source = build_resume_extraction_request(ML_ENGINEER_RESUME, source_id="other-source")

        self.assertEqual(first, second)
        self.assertNotEqual(first.input_payload, changed_source.input_payload)
        self.assertEqual(first.prompt_template_id, RESUME_EXTRACTION_PROMPT_TEMPLATE_ID)
        self.assertEqual(first.output_schema_id, RESUME_EXTRACTION_SCHEMA_ID)
        self.assertEqual(first.input_payload["schema_id"], RESUME_EXTRACTION_SCHEMA_ID)

        job_first = build_job_extraction_request(PYTHON_SPARK_JOB, source_id="python-spark-golden-job")
        job_second = build_job_extraction_request(PYTHON_SPARK_JOB, source_id="python-spark-golden-job")
        self.assertEqual(job_first, job_second)
        self.assertEqual(job_first.prompt_template_id, JOB_EXTRACTION_PROMPT_TEMPLATE_ID)
        self.assertEqual(job_first.output_schema_id, JOB_EXTRACTION_SCHEMA_ID)

    def test_golden_extraction_fixtures_are_retrievable_by_deterministic_requests(self):
        cases = [
            build_resume_extraction_request(LEGACY_RESUME_FIXTURE, source_id="legacy-resume-fixture"),
            build_job_extraction_request(LEGACY_JOB_FIXTURE, source_id="legacy-job-fixture"),
            build_resume_extraction_request(ML_ENGINEER_RESUME, source_id="ml-engineer-golden-resume"),
            build_job_extraction_request(PYTHON_SPARK_JOB, source_id="python-spark-golden-job"),
            build_job_extraction_request(GRAPHQL_API_JOB, source_id="graphql-api-design-golden-job"),
        ]
        adapter = DeterministicFakeAdapter(fixture_dir=FAKE_FIXTURES)

        for request in cases:
            key = deterministic_fake_key(request.prompt_template_id, request.output_schema_id, request.input_payload)
            with self.subTest(key=key):
                result = adapter.complete(request)
                self.assertEqual(result.status, "ok")
                self.assertTrue(result.payload["requires_validation"])

    def test_ml_engineer_resume_fixture_represents_every_populated_section(self):
        payload = _fixture_payload("resume-agent-extraction-ml-engineer-resume")

        for section in ["skills", "experience", "education", "certifications", "projects", "employment"]:
            with self.subTest(section=section):
                self.assertTrue(payload[section])

        serialized = json.dumps(payload, sort_keys=True).lower()
        for expected in ["python", "tensorflow", "kubernetes", "gcp", "go", "phd"]:
            self.assertIn(expected, serialized)

    def test_jd_golden_skills_are_present_in_requirement_entries(self):
        cases = [
            ("resume-agent-extraction-python-spark-job", ["python", "spark", "kubernetes"]),
            ("resume-agent-extraction-graphql-api-job", ["graphql", "api design", "typescript"]),
        ]

        for fixture_id, expected_skills in cases:
            payload = _fixture_payload(fixture_id)
            requirement_text = json.dumps(payload["requirements"] + payload["preferred"], sort_keys=True).lower()
            for skill_name in expected_skills:
                with self.subTest(fixture_id=fixture_id, skill=skill_name):
                    self.assertIn(skill_name, requirement_text)


class ResumeAgentInterviewSchemaContractTests(unittest.TestCase):
    def test_interview_schema_ids_are_registered_with_fake_adapter_validator(self):
        self.assertIn(QUESTION_GENERATION_SCHEMA_ID, DEFAULT_FAKE_OUTPUT_SCHEMAS)
        self.assertIn(ANSWER_INTERPRETATION_SCHEMA_ID, DEFAULT_FAKE_OUTPUT_SCHEMAS)

        question_payload = _fixture_payload("resume-agent-question-generation-aws")
        interpretation_payload = _fixture_payload("resume-agent-answer-interpretation-aws-denial")

        self.assertEqual(validate_schema_id(question_payload, QUESTION_GENERATION_SCHEMA_ID, DEFAULT_FAKE_OUTPUT_SCHEMAS), [])
        self.assertEqual(validate_schema_id(interpretation_payload, ANSWER_INTERPRETATION_SCHEMA_ID, DEFAULT_FAKE_OUTPUT_SCHEMAS), [])

    def test_answer_interpretation_schema_requires_polarity_and_canonical_resolution_state(self):
        payload = copy.deepcopy(_fixture_payload("resume-agent-answer-interpretation-aws-denial"))
        del payload["polarity"]
        payload["requirementResolutions"][0]["suggested_state"] = "explicit_absence"

        violations = validate_schema_id(payload, ANSWER_INTERPRETATION_SCHEMA_ID, DEFAULT_FAKE_OUTPUT_SCHEMAS)
        pairs = {(item.get("code"), item.get("field_path")) for item in violations}

        self.assertIn(("missing_field", "polarity"), pairs)
        self.assertIn(("invalid_enum", "requirementResolutions/0/suggested_state"), pairs)

    def test_interview_prompt_assets_use_template_id_at_version_convention(self):
        self.assertEqual(QUESTION_GENERATION_PROMPT_TEMPLATE_ID, "resume-agent.question-generation@v1")
        self.assertEqual(ANSWER_INTERPRETATION_PROMPT_TEMPLATE_ID, "resume-agent.answer-interpretation@v1")
        self.assertIn("Return only JSON", interview_prompt_template_text(QUESTION_GENERATION_PROMPT_TEMPLATE_ID))
        self.assertIn("Return only JSON", interview_prompt_template_text(ANSWER_INTERPRETATION_PROMPT_TEMPLATE_ID))

    def test_interview_request_builders_are_deterministic_and_do_not_filter_verified_facts(self):
        first = build_question_request(*AWS_QUESTION_REQUEST_ARGS)
        second = build_question_request(*AWS_QUESTION_REQUEST_ARGS)
        changed_topic = build_question_request("Terraform", AWS_QUESTION_REQUEST_ARGS[1], AWS_QUESTION_REQUEST_ARGS[2])

        self.assertEqual(first, second)
        self.assertNotEqual(first.input_payload, changed_topic.input_payload)
        self.assertEqual(first.prompt_template_id, QUESTION_GENERATION_PROMPT_TEMPLATE_ID)
        self.assertEqual(first.output_schema_id, QUESTION_GENERATION_SCHEMA_ID)
        self.assertEqual(first.input_payload["schema_id"], QUESTION_GENERATION_SCHEMA_ID)
        self.assertNotIn("already_verified_fact_ids", first.input_payload)

        answer_first = build_answer_interpretation_request("What AWS services have you used professionally?", AWS_DENIAL_ANSWER, "AWS")
        answer_second = build_answer_interpretation_request("What AWS services have you used professionally?", AWS_DENIAL_ANSWER, "AWS")
        self.assertEqual(answer_first, answer_second)
        self.assertEqual(answer_first.prompt_template_id, ANSWER_INTERPRETATION_PROMPT_TEMPLATE_ID)
        self.assertEqual(answer_first.output_schema_id, ANSWER_INTERPRETATION_SCHEMA_ID)

    def test_golden_interview_fixtures_are_retrievable_by_deterministic_requests(self):
        cases = [
            build_question_request(*AWS_QUESTION_REQUEST_ARGS),
            build_question_request(*TERRAFORM_QUESTION_REQUEST_ARGS),
            build_answer_interpretation_request("What AWS services have you used professionally?", AWS_DENIAL_ANSWER, "AWS"),
            build_answer_interpretation_request("Have you built GraphQL APIs in production?", GRAPHQL_QUALIFIED_ANSWER, "GraphQL"),
            build_answer_interpretation_request("What API or application architecture have you designed?", ARCHITECTURE_AFFIRMED_ANSWER, "API architecture"),
            build_answer_interpretation_request("What AWS services have you used professionally?", AWS_UNRESPONSIVE_ANSWER, "AWS"),
            build_answer_interpretation_request(
                "What Terraform infrastructure-as-code experience do you have?",
                TERRAFORM_AFFIRMED_ANSWER,
                "Terraform",
            ),
        ]
        adapter = DeterministicFakeAdapter(fixture_dir=FAKE_FIXTURES)

        for request in cases:
            key = deterministic_fake_key(request.prompt_template_id, request.output_schema_id, request.input_payload)
            with self.subTest(key=key):
                result = adapter.complete(request)
                self.assertEqual(result.status, "ok")
                self.assertTrue(result.payload["requires_validation"])

    def test_denial_fixture_has_explicit_absence_and_zero_positive_fact_proposals(self):
        payload = _fixture_payload("resume-agent-answer-interpretation-aws-denial")

        self.assertEqual(payload["polarity"], "denied")
        self.assertEqual(payload["requirementResolutions"][0]["suggested_state"], "explicitly_missing")
        self.assertEqual(payload["factProposals"], [])

    def test_qualified_fixture_preserves_hedge(self):
        payload = _fixture_payload("resume-agent-answer-interpretation-graphql-qualified")

        self.assertEqual(payload["polarity"], "qualified")
        self.assertEqual(payload["requirementResolutions"][0]["hedge_or_qualifier"], "only internal tools")
        self.assertEqual(payload["factProposals"][0]["hedge_or_qualifier"], "only internal tools")

    def test_non_fixture_topic_pair_covers_terraform_question_and_interpretation(self):
        question = _fixture_payload("resume-agent-question-generation-terraform")
        answer = _fixture_payload("resume-agent-answer-interpretation-terraform-affirmed")

        self.assertIn("Terraform", question["question"])
        self.assertEqual(answer["polarity"], "affirmed")
        self.assertIn("terraform", json.dumps(answer["factProposals"], sort_keys=True).lower())


class ResumeAgentAnthropicAdapterContractTests(unittest.TestCase):
    def setUp(self):
        self.previous_anthropic = sys.modules.get("anthropic")
        self.stub = _install_anthropic_stub()

    def tearDown(self):
        if self.previous_anthropic is None:
            sys.modules.pop("anthropic", None)
        else:
            sys.modules["anthropic"] = self.previous_anthropic

    def live_adapter(self):
        return create_live_model_adapter(
            env={"RESUME_AGENT_ALLOW_LIVE": "1", "ANTHROPIC_API_KEY": "test-key"},
            agent_config=resolve_agent_config({"agent": {"timeout_ms": 1234, "max_retries": 3}}).config,
            output_schemas={TEST_SCHEMA_ID: TEST_SCHEMA},
        )

    def test_missing_api_key_returns_typed_provider_error_before_sdk_construction(self):
        with self.assertRaises(AdapterProviderError) as missing_key:
            create_live_model_adapter(env={"RESUME_AGENT_ALLOW_LIVE": "1"})

        self.assertEqual(missing_key.exception.details["reason"], "live_adapter_missing_api_key")
        self.assertEqual(self.stub.clients, [])

    def test_gate_profile_blocks_live_even_when_smoke_and_api_key_are_set(self):
        with self.assertRaises(LiveAdapterConstructionBlockedError):
            create_live_model_adapter(
                env={
                    "RESUME_AGENT_ALLOW_LIVE": "1",
                    "RESUME_AGENT_LIVE_SMOKE": "1",
                    "ANTHROPIC_API_KEY": "test-key",
                    "RESUME_AGENT_GATE_PROFILE": "1",
                }
            )
        self.assertEqual(self.stub.clients, [])

    def test_success_uses_configured_model_client_options_output_config_and_metadata(self):
        self.stub.next_response = _stub_response(
            output=VALID_PAYLOAD,
            stop_reason="end_turn",
            retries=1,
            usage=types.SimpleNamespace(input_tokens=11, output_tokens=7),
        )

        result = self.live_adapter().complete(request())

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.payload, VALID_PAYLOAD)
        self.assertEqual(result.adapter_id, "resume-agent-anthropic-claude")
        self.assertEqual(result.model_id, "claude-sonnet-4-6")
        self.assertEqual(result.runtime_config["provider"], "anthropic")
        self.assertEqual(result.runtime_config["temperature"], 0)
        self.assertEqual(result.retries, 1)
        self.assertEqual(result.usage["input_tokens"], 11)
        client = self.stub.clients[-1]
        self.assertEqual(client.kwargs["api_key"], "test-key")
        self.assertEqual(client.kwargs["timeout"], 1.234)
        self.assertEqual(client.kwargs["max_retries"], 3)
        params = client.last_create_kwargs
        self.assertEqual(params["model"], "claude-sonnet-4-6")
        self.assertEqual(params["temperature"], 0)
        self.assertEqual(params["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(params["output_config"]["format"]["schema"], TEST_SCHEMA)

    def test_out_of_schema_anthropic_payload_is_revalidated_as_schema_invalid(self):
        self.stub.next_response = _stub_response(output={"schema_version": TEST_SCHEMA_ID})

        result = self.live_adapter().complete(request())

        self.assertEqual(result.status, "error")
        self.assertEqual(result.error.type, "schema_invalid")
        self.assertIn(("missing_field", "proposal_type"), {(item.get("code"), item.get("field_path")) for item in result.error.violations})

    def test_refusal_stop_reason_maps_to_refused(self):
        self.stub.next_response = _stub_response(output=VALID_PAYLOAD, stop_reason="refusal", retries=2)

        result = self.live_adapter().complete(request())

        self.assertEqual(result.status, "error")
        self.assertEqual(result.error.type, "refused")
        self.assertEqual(result.retries, 2)

    def test_anthropic_exception_mapping_is_class_based_and_wording_independent(self):
        cases = [
            (self.stub.APITimeoutError("provider said bananas"), "timeout"),
            (self.stub.RateLimitError("provider said bananas"), "provider_error"),
            (self.stub.APIConnectionError("provider said bananas"), "provider_error"),
            (self.stub.APIStatusError("provider said bananas", status_code=503), "provider_error"),
            (RuntimeError("provider said bananas"), "provider_error"),
        ]
        for exc, expected_type in cases:
            with self.subTest(exc=exc.__class__.__name__):
                self.stub.next_exception = exc
                result = self.live_adapter().complete(request())
                self.assertEqual(result.status, "error")
                self.assertEqual(result.error.type, expected_type)


class ResumeAgentSchemaValidatorContractTests(unittest.TestCase):
    def test_validator_reports_structured_violation_list_content(self):
        payload = {
            "schema_version": "",
            "proposal_type": "wrong",
            "requires_validation": False,
            "items": [],
            "unexpected": True,
        }
        violations = validate_json_schema(payload, TEST_SCHEMA)

        by_path = {(item.get("code"), item.get("field_path")): item for item in violations}
        self.assertIn(("min_length", "schema_version"), by_path)
        self.assertIn(("invalid_enum", "proposal_type"), by_path)
        self.assertIn(("invalid_enum", "requires_validation"), by_path)
        self.assertIn(("min_items", "items"), by_path)
        self.assertIn(("additional_property", "unexpected"), by_path)
        self.assertEqual(by_path[("invalid_enum", "proposal_type")]["details"]["allowed"], ["contract_demo"])


class ResumeAgentConfigContractTests(unittest.TestCase):
    def test_agent_config_defaults_are_documented_and_applied(self):
        result = resolve_agent_config({})

        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.config.to_dict(), AGENT_CONFIG_DEFAULTS)

    def test_unknown_agent_config_key_is_rejected_with_typed_error(self):
        result = resolve_agent_config({"agent": {"bogus_key": True}})

        self.assertFalse(result.ok)
        self.assertEqual(result.errors[0]["code"], "unknown_agent_config_key")
        self.assertEqual(result.errors[0]["field_path"], "agent.bogus_key")

    def test_agent_config_hash_is_stable_for_validated_config_and_changes_with_model(self):
        first = resolve_agent_config({"agent": {"model": "claude-sonnet-4-6"}}).config
        second = resolve_agent_config({"agent": {"model": "claude-sonnet-4-6"}}).config
        changed = resolve_agent_config({"agent": {"model": "claude-sonnet-4-6-next"}}).config

        self.assertEqual(stable_agent_config_hash(first), stable_agent_config_hash(second))
        self.assertNotEqual(stable_agent_config_hash(first), stable_agent_config_hash(changed))


def _fake_fixture_envelope(payload):
    return {
        "fixture_id": "resume-agent-fake-broken-in-test",
        "schema_version": "resume-agent.fake-adapter-fixture.v1",
        "config_hash": "fixture-config-v1",
        "reviewed": True,
        "expected_observations": ["Deliberately invalid payload for schema_invalid coverage."],
        "comment": "This temporary fixture is created only inside the contract test.",
        "data": {
            "key": {
                "sha256": FACT_SEED_KEY,
                "prompt_template_id": FACT_SEED_TEMPLATE,
                "output_schema_id": FACT_PROPOSAL_SCHEMA_ID,
                "canonical_input_json": json.dumps(FACT_SEED_INPUT, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            },
            "payload": payload,
        },
    }


def _fixture_payload(fixture_id: str):
    for path in sorted(FAKE_FIXTURES.glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        if fixture.get("fixture_id") == fixture_id:
            return fixture["data"]["payload"]
    raise AssertionError(f"Missing fake adapter fixture {fixture_id}.")


def _install_anthropic_stub():
    class APITimeoutError(Exception):
        pass

    class RateLimitError(Exception):
        pass

    class APIConnectionError(Exception):
        pass

    class APIStatusError(Exception):
        def __init__(self, message, *, status_code):
            super().__init__(message)
            self.status_code = status_code

    stub = types.ModuleType("anthropic")
    stub.APITimeoutError = APITimeoutError
    stub.RateLimitError = RateLimitError
    stub.APIConnectionError = APIConnectionError
    stub.APIStatusError = APIStatusError
    stub.next_response = _stub_response(output=VALID_PAYLOAD)
    stub.next_exception = None
    stub.clients = []

    class Anthropic:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.last_create_kwargs = {}
            self.messages = types.SimpleNamespace(create=self.create)
            stub.clients.append(self)

        def create(self, **kwargs):
            self.last_create_kwargs = kwargs
            if stub.next_exception is not None:
                exc = stub.next_exception
                stub.next_exception = None
                raise exc
            return stub.next_response

    stub.Anthropic = Anthropic
    sys.modules["anthropic"] = stub
    return stub


def _stub_response(*, output, stop_reason="end_turn", retries=0, usage=None):
    return types.SimpleNamespace(
        output=output,
        stop_reason=stop_reason,
        retries=retries,
        usage=usage if usage is not None else {"input_tokens": 1, "output_tokens": 1},
    )


if __name__ == "__main__":
    unittest.main()
