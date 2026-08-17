"""Deterministic fixture-backed adapter for resume-agent gates."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ._adapters import AdapterCompletion, AdapterProviderError, AdapterRequest, ValidatingModelAdapter
from ._agent_config import AgentConfig, resolve_agent_config
from ._extraction_schemas import EXTRACTION_OUTPUT_SCHEMAS
from ._interview_schemas import INTERVIEW_OUTPUT_SCHEMAS
from ._rewrite_schemas import REWRITE_OUTPUT_SCHEMAS, REWRITE_PROPOSAL_SCHEMA_ID
from ._schema_validation import JsonObject, JsonSchemaRegistry, validate_schema_id


FAKE_ADAPTER_ID = "resume-agent-deterministic-fake"
FAKE_ADAPTER_VERSION = "0.1.0"
FAKE_MODEL_ID = "deterministic-fixture-v1"
FAKE_FIXTURE_SCHEMA_VERSION = "resume-agent.fake-adapter-fixture.v1"
FAKE_CONFIG_HASH = "fixture-config-v1"

FACT_PROPOSAL_SCHEMA_ID = "resume-agent.fact-proposals.v1"
MANIFEST_VERIFICATION_STATES = ("source_stated", "user" + "_verified", "imported", "inferred", "unknown")


DEFAULT_FAKE_OUTPUT_SCHEMAS: JsonSchemaRegistry = {
    FACT_PROPOSAL_SCHEMA_ID: {
        "type": "object",
        "required": ["schema_version", "proposal_type", "requires_validation", "uncertainty", "fact_proposals", "source_evidence"],
        "properties": {
            "schema_version": {"enum": [FACT_PROPOSAL_SCHEMA_ID]},
            "proposal_type": {"enum": ["resume_semantic_extraction"]},
            "requires_validation": {"enum": [True]},
            "uncertainty": {"type": "array"},
            "fact_proposals": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": [
                        "fact_id",
                        "category",
                        "text",
                        "normalized_terms",
                        "source_evidence_ids",
                        "verification_state",
                        "confidence",
                        "review_required",
                    ],
                    "properties": {
                        "fact_id": {"type": "string", "minLength": 1},
                        "category": {"type": "string", "minLength": 1},
                        "text": {"type": "string", "minLength": 1},
                        "normalized_terms": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
                        "source_evidence_ids": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 1}},
                        "verification_state": {"enum": list(MANIFEST_VERIFICATION_STATES)},
                        "confidence": {"type": "string", "minLength": 1},
                        "review_required": {"enum": [True]},
                    },
                    "additionalProperties": False,
                },
            },
            "source_evidence": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["evidence_id", "text", "span"],
                    "properties": {
                        "evidence_id": {"type": "string", "minLength": 1},
                        "text": {"type": "string", "minLength": 1},
                        "span": {
                            "type": "object",
                            "required": ["start", "end"],
                            "properties": {"start": {"type": "integer"}, "end": {"type": "integer"}},
                            "additionalProperties": False,
                        },
                    },
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    },
}
DEFAULT_FAKE_OUTPUT_SCHEMAS.update(EXTRACTION_OUTPUT_SCHEMAS)
DEFAULT_FAKE_OUTPUT_SCHEMAS.update(INTERVIEW_OUTPUT_SCHEMAS)
DEFAULT_FAKE_OUTPUT_SCHEMAS.update(REWRITE_OUTPUT_SCHEMAS)


@dataclass(frozen=True)
class FakeFixture:
    path: Path
    key_hash: str
    prompt_template_id: str
    output_schema_id: str
    canonical_input_json: str
    payload: JsonObject


def default_fake_fixture_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "fixtures" / "resume-agent" / "fake-adapter"


def canonical_input_json(input_payload: Mapping[str, Any]) -> str:
    return json.dumps(input_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def deterministic_fake_key(prompt_template_id: str, output_schema_id: str, input_payload: Mapping[str, Any]) -> str:
    material = json.dumps(
        [prompt_template_id, output_schema_id, canonical_input_json(input_payload)],
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class DeterministicFakeAdapter(ValidatingModelAdapter):
    def __init__(
        self,
        *,
        fixture_dir: Path | str | None = None,
        agent_config: AgentConfig | None = None,
        output_schemas: JsonSchemaRegistry | None = None,
    ) -> None:
        self.fixture_dir = Path(fixture_dir) if fixture_dir is not None else default_fake_fixture_dir()
        if agent_config is not None and not isinstance(agent_config, AgentConfig):
            raise TypeError("agent_config must be a validated AgentConfig.")
        resolved_agent_config = agent_config or resolve_agent_config({}).config
        schemas = dict(DEFAULT_FAKE_OUTPUT_SCHEMAS)
        schemas.update(output_schemas or {})
        self._fixtures = _load_fixture_index(self.fixture_dir)
        super().__init__(
            adapter_id=FAKE_ADAPTER_ID,
            adapter_version=FAKE_ADAPTER_VERSION,
            model_id=FAKE_MODEL_ID,
            agent_config=resolved_agent_config,
            runtime_config={"fixture_dir": str(self.fixture_dir), "key_algorithm": "sha256:v1"},
            output_schemas=schemas,
        )

    def _complete_unchecked(self, request: AdapterRequest) -> AdapterCompletion:
        key_hash = deterministic_fake_key(request.prompt_template_id, request.output_schema_id, request.input_payload)
        fixture = self._fixtures.get(key_hash)
        if fixture is None:
            raise AdapterProviderError(
                "Deterministic fake fixture is missing for "
                f"key={key_hash} template={request.prompt_template_id} schema={request.output_schema_id}.",
                details={
                    "reason": "deterministic_fake_missing_fixture",
                    "missing_key_hash": key_hash,
                    "prompt_template_id": request.prompt_template_id,
                    "output_schema_id": request.output_schema_id,
                },
            )
        return AdapterCompletion(payload=copy.deepcopy(fixture.payload), retries=0, usage={"fixture_hits": 1})


def validate_fake_fixture_file(
    path: Path | str,
    *,
    output_schemas: JsonSchemaRegistry | None = None,
) -> list[JsonObject]:
    try:
        fixture = _read_fixture(Path(path))
    except AdapterProviderError as exc:
        return [{"code": "invalid_fake_fixture", "message": str(exc), "severity": "error", "details": exc.details}]
    schemas = dict(DEFAULT_FAKE_OUTPUT_SCHEMAS)
    schemas.update(output_schemas or {})
    return validate_schema_id(fixture.payload, fixture.output_schema_id, schemas)


def validate_fake_fixture_dir(
    fixture_dir: Path | str | None = None,
    *,
    output_schemas: JsonSchemaRegistry | None = None,
) -> dict[str, list[JsonObject]]:
    base = Path(fixture_dir) if fixture_dir is not None else default_fake_fixture_dir()
    failures: dict[str, list[JsonObject]] = {}
    for path in sorted(base.rglob("*.json")):
        violations = validate_fake_fixture_file(path, output_schemas=output_schemas)
        if violations:
            failures[str(path)] = violations
    return failures


def _load_fixture_index(fixture_dir: Path) -> dict[str, FakeFixture]:
    fixtures: dict[str, FakeFixture] = {}
    if not fixture_dir.exists():
        return fixtures
    for path in sorted(fixture_dir.rglob("*.json")):
        fixture = _read_fixture(path)
        existing = fixtures.get(fixture.key_hash)
        if existing is not None:
            raise AdapterProviderError(
                f"Duplicate deterministic fake fixture key {fixture.key_hash}.",
                details={"reason": "deterministic_fake_duplicate_key", "first_path": str(existing.path), "second_path": str(path)},
            )
        fixtures[fixture.key_hash] = fixture
    return fixtures


def _read_fixture(path: Path) -> FakeFixture:
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AdapterProviderError(
            f"Deterministic fake fixture has invalid JSON: {path}: {exc.msg}.",
            details={"reason": "deterministic_fake_invalid_json", "path": str(path), "line": exc.lineno},
        ) from exc
    if not isinstance(envelope, dict):
        raise AdapterProviderError(
            f"Deterministic fake fixture envelope must be an object: {path}.",
            details={"reason": "deterministic_fake_invalid_envelope", "path": str(path)},
        )
    _require_envelope(envelope, path)
    data = envelope.get("data")
    if not isinstance(data, dict):
        raise AdapterProviderError(
            f"Deterministic fake fixture data must be an object: {path}.",
            details={"reason": "deterministic_fake_invalid_data", "path": str(path)},
        )
    key = data.get("key")
    payload = data.get("payload")
    if not isinstance(key, dict) or not isinstance(payload, dict):
        raise AdapterProviderError(
            f"Deterministic fake fixture data requires object key and payload: {path}.",
            details={"reason": "deterministic_fake_invalid_data", "path": str(path)},
        )
    key_hash = key.get("sha256")
    prompt_template_id = key.get("prompt_template_id")
    output_schema_id = key.get("output_schema_id")
    canonical = key.get("canonical_input_json")
    if not all(isinstance(item, str) and item for item in [key_hash, prompt_template_id, output_schema_id, canonical]):
        raise AdapterProviderError(
            f"Deterministic fake fixture key requires sha256, prompt_template_id, output_schema_id, and canonical_input_json: {path}.",
            details={"reason": "deterministic_fake_invalid_key", "path": str(path)},
        )
    try:
        input_payload = json.loads(canonical)
    except json.JSONDecodeError as exc:
        raise AdapterProviderError(
            f"Deterministic fake fixture canonical input is invalid JSON: {path}: {exc.msg}.",
            details={"reason": "deterministic_fake_invalid_key", "path": str(path), "line": exc.lineno},
        ) from exc
    expected = deterministic_fake_key(prompt_template_id, output_schema_id, input_payload)
    if key_hash != expected:
        raise AdapterProviderError(
            f"Deterministic fake fixture key mismatch: expected {expected}, observed {key_hash}: {path}.",
            details={"reason": "deterministic_fake_key_mismatch", "path": str(path), "expected": expected, "observed": key_hash},
        )
    return FakeFixture(
        path=path,
        key_hash=key_hash,
        prompt_template_id=prompt_template_id,
        output_schema_id=output_schema_id,
        canonical_input_json=canonical,
        payload=payload,
    )


def _require_envelope(envelope: JsonObject, path: Path) -> None:
    required = ["fixture_id", "schema_version", "config_hash", "reviewed", "expected_observations", "comment", "data"]
    missing = [field for field in required if field not in envelope]
    if missing:
        raise AdapterProviderError(
            f"Deterministic fake fixture envelope is missing {missing}: {path}.",
            details={"reason": "deterministic_fake_invalid_envelope", "path": str(path), "missing": missing},
        )
    if envelope.get("schema_version") != FAKE_FIXTURE_SCHEMA_VERSION:
        raise AdapterProviderError(
            f"Deterministic fake fixture schema_version must be {FAKE_FIXTURE_SCHEMA_VERSION}: {path}.",
            details={"reason": "deterministic_fake_invalid_envelope", "path": str(path)},
        )
    if envelope.get("config_hash") != FAKE_CONFIG_HASH or envelope.get("reviewed") is not True:
        raise AdapterProviderError(
            f"Deterministic fake fixture requires config_hash={FAKE_CONFIG_HASH} and reviewed=true: {path}.",
            details={"reason": "deterministic_fake_invalid_envelope", "path": str(path)},
        )


__all__ = [
    "DEFAULT_FAKE_OUTPUT_SCHEMAS",
    "FAKE_ADAPTER_ID",
    "FAKE_ADAPTER_VERSION",
    "FAKE_CONFIG_HASH",
    "FAKE_FIXTURE_SCHEMA_VERSION",
    "FAKE_MODEL_ID",
    "FACT_PROPOSAL_SCHEMA_ID",
    "REWRITE_PROPOSAL_SCHEMA_ID",
    "DeterministicFakeAdapter",
    "canonical_input_json",
    "default_fake_fixture_dir",
    "deterministic_fake_key",
    "validate_fake_fixture_dir",
    "validate_fake_fixture_file",
]
