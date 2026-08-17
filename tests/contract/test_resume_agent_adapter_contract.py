"""Contract tests for the private resume-agent model adapter seam."""

from __future__ import annotations

import unittest
import json
import tempfile
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
from resume_agent._fake_adapter import (
    FACT_PROPOSAL_SCHEMA_ID,
    REWRITE_PROPOSAL_SCHEMA_ID,
    DeterministicFakeAdapter,
    deterministic_fake_key,
    validate_fake_fixture_dir,
)
from resume_agent._schema_validation import validate_json_schema


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


if __name__ == "__main__":
    unittest.main()
