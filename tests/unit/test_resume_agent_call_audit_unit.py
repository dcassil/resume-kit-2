"""Unit checks for resume-agent call-audit records and sinks."""

from __future__ import annotations

import hashlib
import json
import unittest
from importlib import resources
from pathlib import Path

from resume_agent import resolve_agent_config, stable_agent_config_hash
from resume_agent._adapters import (
    AdapterCompletion,
    AdapterProviderError,
    AdapterRefusalError,
    AdapterRequest,
    ValidatingModelAdapter,
)
from resume_agent._call_audit import (
    CALL_AUDIT_RECORD_FIELDS,
    CallAuditRecordValidationError,
    InMemoryCallAuditSink,
    hash_output_schema,
    hash_prompt_template,
    require_call_audit_record,
)
from resume_agent._fake_adapter import DeterministicFakeAdapter
from resume_agent._interview_requests import QUESTION_GENERATION_PROMPT_TEMPLATE_ID, build_question_request
from resume_agent._interview_schemas import QUESTION_GENERATION_SCHEMA, QUESTION_GENERATION_SCHEMA_ID


ROOT = Path(__file__).resolve().parents[2]
FAKE_FIXTURES = ROOT / "fixtures" / "resume-agent" / "fake-adapter"
TEST_SCHEMA_ID = "call-audit-unit.v1"
TEST_SCHEMA = {
    "schema_version": TEST_SCHEMA_ID,
    "type": "object",
    "required": ["schema_version", "proposal_type", "requires_validation", "items"],
    "properties": {
        "schema_version": {"enum": [TEST_SCHEMA_ID]},
        "proposal_type": {"enum": ["call_audit_unit"]},
        "requires_validation": {"enum": [True]},
        "items": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
    },
    "additionalProperties": False,
}
VALID_PAYLOAD = {
    "schema_version": TEST_SCHEMA_ID,
    "proposal_type": "call_audit_unit",
    "requires_validation": True,
    "items": ["ok"],
}
FACT_SEED_INPUT = {
    "resume_text": "Daniel Candidate\nSoftware Engineer\nBuilt React and TypeScript front ends and designed REST API architecture for SaaS products."
}
FACT_SEED_TEMPLATE = "resume-agent.extract-resume-semantics.v1"
FACT_PROPOSAL_SCHEMA_ID = "resume-agent.fact-proposals.v1"


def audit_request(input_payload=None) -> AdapterRequest:
    return AdapterRequest(
        prompt_template_id="call-audit-unit-template",
        prompt="Return a call audit unit object.",
        input_payload=input_payload or {"subject": "audit"},
        output_schema_id=TEST_SCHEMA_ID,
    )


def fake_seed_request(input_payload=None) -> AdapterRequest:
    return AdapterRequest(
        prompt_template_id=FACT_SEED_TEMPLATE,
        prompt="Extract source-grounded fact proposals.",
        input_payload=input_payload or FACT_SEED_INPUT,
        output_schema_id=FACT_PROPOSAL_SCHEMA_ID,
    )


class StaticAuditAdapter(ValidatingModelAdapter):
    def __init__(self, outcome, *, sink=None, schemas=None, agent_config=None):
        super().__init__(
            adapter_id="call-audit-double",
            adapter_version="0.0.1",
            model_id="call-audit-model",
            agent_config=agent_config,
            runtime_config={"temperature": 0},
            output_schemas=schemas or {TEST_SCHEMA_ID: TEST_SCHEMA},
            call_audit_sink=sink,
        )
        self.outcome = outcome

    def _complete_unchecked(self, _request):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


class RetryTimeout(TimeoutError):
    retries = 2
    usage = {"input_tokens": 5}


class RetryRefusal(AdapterRefusalError):
    retries = 3
    usage = {"input_tokens": 7}


class RetryProviderError(AdapterProviderError):
    retries = 4
    usage = {"input_tokens": 11}


class ResumeAgentCallAuditUnitTests(unittest.TestCase):
    def test_every_adapter_call_emits_record_for_ok_and_all_failure_taxonomies(self):
        cases = [
            ("ok", AdapterCompletion(payload=VALID_PAYLOAD, retries=1, usage={"output_tokens": 13}), "ok", 1),
            ("timeout", RetryTimeout("timed out"), "timeout", 2),
            (
                "schema_invalid",
                AdapterCompletion(payload={"schema_version": TEST_SCHEMA_ID}, retries=5, usage={"output_tokens": 17}),
                "schema_invalid",
                5,
            ),
            ("refused", RetryRefusal("refused"), "refused", 3),
            ("provider_error", RetryProviderError("provider failed"), "provider_error", 4),
        ]

        for label, outcome, expected_outcome, expected_retries in cases:
            with self.subTest(label=label):
                sink = InMemoryCallAuditSink()
                result = StaticAuditAdapter(outcome, sink=sink).complete(audit_request())

                self.assertEqual(len(sink.records), 1)
                self.assertEqual(sink.records[0]["outcome"], expected_outcome)
                self.assertEqual(sink.records[0]["retry_count"], expected_retries)
                self.assertEqual(set(sink.records[0]), set(CALL_AUDIT_RECORD_FIELDS))
                self.assertEqual(result.retries, expected_retries)

    def test_identical_fake_inputs_on_fresh_adapters_yield_byte_identical_records(self):
        first_sink = InMemoryCallAuditSink()
        second_sink = InMemoryCallAuditSink()
        first = DeterministicFakeAdapter(fixture_dir=FAKE_FIXTURES, call_audit_sink=first_sink)
        second = DeterministicFakeAdapter(fixture_dir=FAKE_FIXTURES, call_audit_sink=second_sink)

        self.assertEqual(first.complete(fake_seed_request()).status, "ok")
        self.assertEqual(second.complete(fake_seed_request()).status, "ok")

        first_record = json.dumps(first_sink.records[0], sort_keys=True, separators=(",", ":"))
        second_record = json.dumps(second_sink.records[0], sort_keys=True, separators=(",", ":"))
        self.assertEqual(first_record, second_record)

    def test_distinct_fake_inputs_yield_distinct_call_ids(self):
        sink = InMemoryCallAuditSink()
        adapter = DeterministicFakeAdapter(fixture_dir=FAKE_FIXTURES, call_audit_sink=sink)

        self.assertEqual(adapter.complete(fake_seed_request()).status, "ok")
        missing_result = adapter.complete(fake_seed_request({"resume_text": "Different input without a fixture."}))

        self.assertEqual(missing_result.status, "error")
        self.assertEqual(sink.records[0]["outcome"], "ok")
        self.assertEqual(sink.records[1]["outcome"], "provider_error")
        self.assertNotEqual(sink.records[0]["call_id"], sink.records[1]["call_id"])

    def test_complete_chokepoint_emits_when_subclass_overrides_unchecked_completion(self):
        sink = InMemoryCallAuditSink()
        adapter = StaticAuditAdapter(AdapterCompletion(payload=VALID_PAYLOAD), sink=sink)

        result = adapter.complete(audit_request())

        self.assertEqual(result.status, "ok")
        self.assertEqual(len(sink.records), 1)
        self.assertEqual(sink.records[0]["adapter_id"], "call-audit-double")

    def test_record_self_validation_reports_missing_field_as_typed_error(self):
        sink = InMemoryCallAuditSink()
        StaticAuditAdapter(AdapterCompletion(payload=VALID_PAYLOAD), sink=sink).complete(audit_request())
        record = sink.records[0]
        del record["usage"]

        with self.assertRaises(CallAuditRecordValidationError) as raised:
            require_call_audit_record(record)

        self.assertIn(("missing_field", "usage"), {(item.get("code"), item.get("field_path")) for item in raised.exception.violations})

    def test_hashes_use_prompt_asset_schema_and_stable_agent_config_hash(self):
        request = build_question_request("AWS", {"requirement_ids": ["req_aws"], "fact_ids": []}, ["AWS preferred."])
        agent_config = resolve_agent_config({"agent": {"model": "claude-sonnet-4-6"}}).config
        sink = InMemoryCallAuditSink()
        adapter = StaticAuditAdapter(
            AdapterCompletion(
                payload={
                    "schema_version": QUESTION_GENERATION_SCHEMA_ID,
                    "proposal_type": "question_generation",
                    "requires_validation": True,
                    "question": "What AWS services have you used professionally?",
                    "target_ids": {"requirement_ids": ["req_aws"], "fact_ids": []},
                    "rationale": "Selected unresolved AWS requirement.",
                    "confidence": 0.9,
                }
            ),
            sink=sink,
            schemas={QUESTION_GENERATION_SCHEMA_ID: QUESTION_GENERATION_SCHEMA},
            agent_config=agent_config,
        )

        result = adapter.complete(request)

        expected_prompt_hash = hashlib.sha256(
            resources.files("resume_agent").joinpath("prompts", f"{QUESTION_GENERATION_PROMPT_TEMPLATE_ID}.txt").read_bytes()
        ).hexdigest()
        self.assertEqual(result.status, "ok")
        self.assertEqual(sink.records[0]["prompt_hash"], expected_prompt_hash)
        self.assertEqual(sink.records[0]["prompt_hash"], hash_prompt_template(request))
        self.assertEqual(sink.records[0]["schema_hash"], hash_output_schema(QUESTION_GENERATION_SCHEMA_ID, adapter.output_schemas))
        self.assertEqual(sink.records[0]["config_hash"], stable_agent_config_hash(agent_config))


if __name__ == "__main__":
    unittest.main()
