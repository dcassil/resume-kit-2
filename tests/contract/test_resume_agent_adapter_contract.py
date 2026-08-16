"""Contract tests for the private resume-agent model adapter seam."""

from __future__ import annotations

import unittest

from resume_agent._adapters import (
    ADAPTER_FAILURE_TYPES,
    AdapterCompletion,
    AdapterProviderError,
    AdapterRefusalError,
    AdapterRequest,
    ValidatingModelAdapter,
)
from resume_agent._schema_validation import validate_json_schema


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


if __name__ == "__main__":
    unittest.main()
