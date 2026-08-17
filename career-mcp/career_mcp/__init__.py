"""Public runtime package for career-mcp."""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Any

from career_store import (
    AUTHORITY_SOURCE_DOCUMENT_EVIDENCE,
    DisallowedTransitionError,
    IncompatibleSchemaVersionError,
    InvalidInterpretationProposalError,
    InvalidRelationshipConfirmationError,
    MergeConflictError,
    MigrationFailedError,
    VERIFICATION_TRANSITION_MATRIX,
)

from . import audit, policy


JsonObject = dict[str, Any]


class StoreContractError(Exception):
    """Raised when career-store returns a value outside the declared surface."""

ERROR_TYPES = {"validation_error", "policy_error", "not_found", "store_error", "unknown_tool"}
REJECTION_STATUSES = {"error", "rejected"}
NOT_FOUND_REASON_CODES = {"not_found", "unknown_fact_id"}
GENERIC_STORE_ERROR_MESSAGE = audit.GENERIC_STORE_ERROR_MESSAGE
UNVERIFIED_VERIFICATION_STATES = ("unknown", "inferred")
PERSISTENCE_LEAK_PATTERNS = audit.PERSISTENCE_LEAK_PATTERNS
POLICY_REASON_CODES = {
    "confirmation_required",
    "disallowed_verification_transition",
    "user_verified_without_explicit_confirmation",
}
TOOL_ARGUMENTS = {
    "career.search_facts": {"query", "types", "verification", "limit"},
    "career.get_fact": {"fact_id", "include_conflicts"},
    "career.propose_fact": {"type", "text", "source", "evidence", "dedupe_key", "confirmed"},
    "career.add_evidence": {"fact_id", "evidence", "confirmed"},
    "career.verify_fact": {"fact_id", "verification_state", "confirmation", "evidence_id", "confirmed"},
    "career.add_relationship": {"from_fact_id", "to_fact_id", "relationship_type", "evidence", "confirmation", "confirmed"},
    "career.find_matches": {"requirements"},
    "career.get_unverified": {"topic", "limit"},
}
STORE_METHOD_BY_TOOL = {
    "career.search_facts": "searchFacts",
    "career.get_fact": "getFact",
    "career.propose_fact": "upsertFact",
    "career.add_evidence": "addEvidence",
    "career.verify_fact": "verifyFact",
    "career.add_relationship": "addRelationship",
    "career.find_matches": "findCandidateMatches",
    "career.get_unverified": "searchFacts",
}
HANDLER_BY_TOOL = {
    "career.search_facts": "_handle_search",
    "career.get_fact": "_handle_fetch",
    "career.propose_fact": "_handle_proposal",
    "career.add_evidence": "_handle_evidence_append",
    "career.verify_fact": "_handle_verification",
    "career.add_relationship": "_handle_relation",
    "career.find_matches": "_handle_matching",
    "career.get_unverified": "_handle_review_queue",
}


class CareerMcpAdapter:
    """Narrow tool adapter over an injected career-store service."""

    def __init__(
        self,
        store: Any,
        policy: JsonObject | None = None,
        audit_sink: Any = None,
        operation_id_provider: Any = audit.default_operation_id,
        timestamp_provider: Any = audit.default_timestamp_utc,
    ) -> None:
        self._store = store
        self._policy = policy or {}
        self._audit_sink = audit_sink
        self._operation_id_provider = operation_id_provider
        self._timestamp_provider = timestamp_provider
        self._tools = _load_tools()
        self._tool_by_name = {tool["name"]: tool for tool in self._tools}

    def list_tools(self) -> list[JsonObject]:
        return [dict(tool) for tool in self._tools]

    async def call_tool(self, name: str, arguments: JsonObject | None) -> JsonObject:
        operation_id = self._operation_id_provider()
        timestamp = self._timestamp_provider()
        arguments = arguments or {}
        policy_decision: policy.PolicyDecision | None = None
        if name in self._tool_by_name:
            confirmed = bool(arguments.get("confirmed", False))
            policy_decision = policy.evaluate_policy(name, arguments, confirmed=confirmed)

        if name not in self._tool_by_name:
            result = _tool_result(name, "error", error={"type": "unknown_tool", "message": "Unknown career tool."})
        else:
            validation_error = _validate(arguments, self._tool_by_name[name]["input_schema"])
            if validation_error:
                result = _tool_result(name, "error", error={"type": "validation_error", "message": validation_error})
            else:
                _assert_consumed_arguments(name, arguments)
                confirmed = bool(arguments.get("confirmed", False))
                assert policy_decision is not None
                if not policy_decision.allowed:
                    result = _tool_result(
                        name,
                        "rejected",
                        data={
                            "confirmation_required": policy_decision.requires_confirmation,
                            "confirmed": confirmed,
                        },
                        error={
                            "type": "policy_error",
                            "reason": policy_decision.reason,
                            "message": policy_decision.reason or "Policy rejected career tool call.",
                        },
                    )
                else:
                    try:
                        handler = getattr(self, HANDLER_BY_TOOL[name])
                        payload = await handler(name, arguments)
                        result = _normalize_tool_result(name, payload)
                        _apply_policy_decision(result, policy_decision, confirmed=confirmed)
                    except AssertionError:
                        raise
                    except Exception as exc:
                        result = _tool_result(name, "error", error={"type": _exception_type(exc), "message": _safe_message(exc)})
        self._record_audit(name, result, arguments, operation_id, timestamp, policy_decision)
        return result

    def _surface(self, tool: str) -> Any:
        return getattr(self._store, STORE_METHOD_BY_TOOL[tool])

    async def _handle_search(self, tool: str, arguments: JsonObject) -> JsonObject:
        value = await _maybe_await(
            self._surface(tool)(
                arguments["query"],
                filters={},
                limit=None,
                include_evidence=True,
            )
        )
        facts = value.get("facts", value) if isinstance(value, dict) else value
        filtered = _post_filter_facts(facts, arguments)
        limit = arguments.get("limit", 10)
        return {
            "status": "ok",
            "facts": sorted((_fact_summary(fact) for fact in filtered), key=lambda fact: fact["fact_id"])[:limit],
        }

    async def _handle_fetch(self, tool: str, arguments: JsonObject) -> JsonObject:
        include_conflicts = arguments.get("include_conflicts", True)
        value = await _maybe_await(self._surface(tool)(arguments["fact_id"]))
        fact = _extract_fact(value)
        if not fact:
            return {"status": "error", "error": {"type": "not_found", "message": "Career fact not found."}}
        evidence = value.get("evidence", []) if isinstance(value, dict) else fact.get("evidence_summary", [])
        relationships = value.get("relationships", fact.get("relationships", [])) if isinstance(value, dict) else fact.get("relationships", [])
        conflicts = value.get("conflicts", fact.get("conflicts", [])) if isinstance(value, dict) else fact.get("conflicts", [])
        if include_conflicts and hasattr(self._store, "findConflicts"):
            conflict_value = await _maybe_await(self._store.findConflicts(fact, scope={"source": "career.get_fact"}))
            if isinstance(conflict_value, dict) and isinstance(conflict_value.get("conflicts"), list):
                conflicts = conflict_value["conflicts"]
        elif not include_conflicts:
            conflicts = []
        normalized = _fact_detail(fact, evidence, relationships, conflicts)
        return {
            "status": "ok",
            "fact": normalized,
            "verification_state": normalized["verification_state"],
            "evidence_summary": normalized["evidence_summary"],
            "relationships": normalized["relationships"],
            "conflicts": normalized["conflicts"],
        }

    async def _handle_proposal(self, tool: str, arguments: JsonObject) -> JsonObject:
        store_call = self._surface(tool)
        if arguments.get("dedupe_key") is not None and not _method_accepts_argument(store_call, "dedupe_key"):
            return _validation_error("Unsupported argument for career-store upsertFact: dedupe_key.")
        fact = {"type": arguments["type"], "text": arguments["text"], "verification_state": "unknown"}
        kwargs = {
            "source": arguments["source"],
            "policy": {**self._policy, "allow_inferred_final": False},
        }
        if _method_accepts_argument(store_call, "dedupe_key"):
            kwargs["dedupe_key"] = arguments.get("dedupe_key")
        value = await _maybe_await(store_call(fact, arguments.get("evidence"), **kwargs))
        return _mutation(value)

    async def _handle_evidence_append(self, tool: str, arguments: JsonObject) -> JsonObject:
        source = str(arguments["evidence"].get("source", "mcp_tool"))
        value = await _maybe_await(self._surface(tool)(arguments["fact_id"], arguments["evidence"], source=source))
        return _mutation(value)

    async def _handle_verification(self, tool: str, arguments: JsonObject) -> JsonObject:
        if _verification_state_requires_evidence(arguments["verification_state"]) and not arguments.get("evidence_id"):
            return _validation_error(f"evidence_id is required when verification_state is {arguments['verification_state']}.")
        confirmation = _confirmation_with_evidence_id(arguments["confirmation"], arguments.get("evidence_id"))
        provenance = confirmation.get("provenance", []) if isinstance(confirmation, dict) else []
        first_provenance = provenance[0] if provenance and isinstance(provenance[0], dict) else {}
        source = str(first_provenance.get("source", first_provenance.get("kind", "mcp_tool")))
        value = await _maybe_await(
            self._surface(tool)(arguments["fact_id"], arguments["verification_state"], confirmation, source=source)
        )
        return _mutation(value)

    async def _handle_relation(self, tool: str, arguments: JsonObject) -> JsonObject:
        value = await _maybe_await(
            self._surface(tool)(
                arguments["from_fact_id"],
                arguments["to_fact_id"],
                arguments["relationship_type"],
                evidence_or_rationale=arguments.get("evidence") or arguments.get("confirmation") or {},
                policy=self._policy,
            )
        )
        return _mutation(value, affected_fact_ids=[arguments["from_fact_id"], arguments["to_fact_id"]])

    async def _handle_matching(self, tool: str, arguments: JsonObject) -> JsonObject:
        value = await _maybe_await(self._surface(tool)(arguments["requirements"], policy=self._policy))
        if isinstance(value, dict) and value.get("status") in REJECTION_STATUSES:
            return value
        matches = _coherent_matches(value, arguments["requirements"])
        return {"status": "ok", "matches": sorted(matches, key=lambda item: item["requirement_id"])}

    async def _handle_review_queue(self, tool: str, arguments: JsonObject) -> JsonObject:
        query = arguments.get("topic") or ""
        limit = arguments.get("limit", 10)
        facts_by_id: dict[str, JsonObject] = {}
        for verification_state in UNVERIFIED_VERIFICATION_STATES:
            value = await _maybe_await(
                self._surface(tool)(
                    query,
                    filters={"verification_state": verification_state},
                    limit=limit,
                    include_evidence=True,
                )
            )
            if isinstance(value, dict) and value.get("status") in REJECTION_STATUSES:
                return value
            facts = value.get("facts", value) if isinstance(value, dict) else value
            for fact in _post_filter_facts(facts, {"verification": list(UNVERIFIED_VERIFICATION_STATES)}):
                facts_by_id[str(fact.get("fact_id", ""))] = fact
        facts = sorted(facts_by_id.values(), key=lambda fact: str(fact.get("fact_id", "")))[:limit]
        return {"status": "ok", "facts": [_unverified_fact(fact) for fact in facts]}

    def _record_audit(
        self,
        name: str,
        result: JsonObject,
        arguments: JsonObject,
        operation_id: str,
        timestamp: str,
        policy_decision: policy.PolicyDecision | None,
    ) -> None:
        event = audit.build_audit_event(
            tool=name,
            result=result,
            arguments=arguments,
            operation_id=operation_id,
            timestamp=timestamp,
            policy_decision=policy_decision,
        )
        audit.emit_audit_event(self._audit_sink, event)


def create_career_mcp(
    store: Any,
    policy: JsonObject | None = None,
    audit_sink: Any = None,
    operation_id_provider: Any = audit.default_operation_id,
    timestamp_provider: Any = audit.default_timestamp_utc,
) -> CareerMcpAdapter:
    return CareerMcpAdapter(
        store=store,
        policy=policy,
        audit_sink=audit_sink,
        operation_id_provider=operation_id_provider,
        timestamp_provider=timestamp_provider,
    )


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


_SURFACE_CACHE: JsonObject | None = None


def _load_surface() -> JsonObject:
    global _SURFACE_CACHE
    if _SURFACE_CACHE is not None:
        return _SURFACE_CACHE
    package_surface_path = Path(__file__).with_name("tool_surface.json")
    source_surface_path = Path(__file__).resolve().parents[1] / "tool_surface.json"
    surface_path = package_surface_path if package_surface_path.exists() else source_surface_path
    _SURFACE_CACHE = json.loads(surface_path.read_text(encoding="utf-8"))
    return _SURFACE_CACHE


def _load_tools() -> list[JsonObject]:
    return list(_load_surface()["tools"])


def _contract_set(name: str) -> set[str]:
    values = _load_surface().get(name, [])
    return {str(value) for value in values}


def _assert_consumed_arguments(tool: str, arguments: JsonObject) -> None:
    consumed = TOOL_ARGUMENTS.get(tool)
    if consumed is None:
        raise AssertionError(f"No consumed-arguments entry for {tool}.")
    dropped = sorted(set(arguments) - consumed)
    if dropped:
        raise AssertionError(f"{tool} validated arguments that dispatch does not consume: {', '.join(dropped)}.")


def _post_filter_facts(facts: Any, arguments: JsonObject) -> list[JsonObject]:
    verification = set(arguments.get("verification") or [])
    types = set(arguments.get("types") or [])
    filtered = []
    for fact in facts or []:
        if not isinstance(fact, dict):
            continue
        if verification and fact.get("verification_state") not in verification:
            continue
        if types and fact.get("type") not in types:
            continue
        filtered.append(fact)
    return filtered


def _validation_error(message: str) -> JsonObject:
    return {"status": "error", "error": {"type": "validation_error", "message": message}}


def _method_accepts_argument(method: Any, argument: str) -> bool:
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return False
    for parameter in signature.parameters.values():
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            return True
    return argument in signature.parameters


def _verification_state_requires_evidence(verification_state: str) -> bool:
    evidence_states = {
        to_state
        for (_from_state, to_state), authority in VERIFICATION_TRANSITION_MATRIX.items()
        if authority == AUTHORITY_SOURCE_DOCUMENT_EVIDENCE
    }
    return verification_state in evidence_states


def _confirmation_with_evidence_id(confirmation: Any, evidence_id: Any) -> Any:
    if not evidence_id or not isinstance(confirmation, dict):
        return confirmation
    forwarded = dict(confirmation)
    provenance = forwarded.get("provenance")
    if not isinstance(provenance, list):
        return forwarded
    forwarded_provenance = []
    for entry in provenance:
        if not isinstance(entry, dict):
            forwarded_provenance.append(entry)
            continue
        clean_entry = dict(entry)
        clean_entry.setdefault("source_id", str(evidence_id))
        metadata = dict(clean_entry.get("metadata", {})) if isinstance(clean_entry.get("metadata"), dict) else {}
        metadata.setdefault("evidence_id", str(evidence_id))
        clean_entry["metadata"] = metadata
        forwarded_provenance.append(clean_entry)
    forwarded["provenance"] = forwarded_provenance
    return forwarded


def _validate(arguments: JsonObject, schema: JsonObject) -> str | None:
    if not isinstance(arguments, dict):
        return "Arguments must be an object."
    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        extra = sorted(set(arguments) - set(properties))
        if extra:
            return f"Unsupported argument: {extra[0]}."
    for required in schema.get("required", []):
        if required not in arguments:
            return f"Missing required argument: {required}."
    for key, value in arguments.items():
        error = _validate_value(key, value, properties.get(key, {}))
        if error:
            return error
    return None


def _validate_value(name: str, value: Any, schema: JsonObject) -> str | None:
    expected = schema.get("type")
    if expected == "string":
        if not isinstance(value, str):
            return f"{name} must be a string."
        if len(value) < schema.get("minLength", 0):
            return f"{name} cannot be empty."
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value):
            return f"{name} has an invalid format."
        if "enum" in schema and value not in schema["enum"]:
            return f"{name} is not supported."
    elif expected == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            return f"{name} must be an integer."
        if "minimum" in schema and value < schema["minimum"]:
            return f"{name} is too small."
        if "maximum" in schema and value > schema["maximum"]:
            return f"{name} is too large."
    elif expected == "boolean":
        if not isinstance(value, bool):
            return f"{name} must be true or false."
    elif expected == "object":
        if not isinstance(value, dict):
            return f"{name} must be an object."
        if len(value) < schema.get("minProperties", 0):
            return f"{name} cannot be empty."
    elif expected == "array":
        if not isinstance(value, list):
            return f"{name} must be an array."
        if len(value) < schema.get("minItems", 0):
            return f"{name} cannot be empty."
        if schema.get("uniqueItems") and len(value) != len(set(json.dumps(item, sort_keys=True) for item in value)):
            return f"{name} must contain unique values."
        item_schema = schema.get("items", {})
        for index, item in enumerate(value):
            error = _validate_value(f"{name}[{index}]", item, item_schema)
            if error:
                return error
            if item_schema.get("type") == "object":
                nested = _validate(item, {"properties": item_schema.get("properties", {}), "required": item_schema.get("required", [])})
                if nested:
                    return nested
    if "enum" in schema and value not in schema["enum"]:
        return f"{name} is not supported."
    return None


def _extract_fact(value: Any) -> JsonObject | None:
    if value is None:
        return None
    if isinstance(value, dict) and value.get("status") in {"not_found", "error"}:
        return None
    if isinstance(value, dict) and isinstance(value.get("fact"), dict):
        return value["fact"]
    if isinstance(value, dict) and value.get("fact_id"):
        return value
    return None


def _fact_summary(fact: JsonObject) -> JsonObject:
    return {
        "fact_id": str(fact.get("fact_id", "")),
        "type": str(fact.get("type", "")),
        "text": str(fact.get("text", "")),
        "verification_state": str(fact.get("verification_state", "unknown")),
        "evidence_summary": _evidence_summary(fact),
    }


def _fact_detail(fact: JsonObject, evidence: list[JsonObject], relationships: list[JsonObject], conflicts: list[JsonObject]) -> JsonObject:
    detail = _fact_summary({**fact, "evidence_summary": evidence or fact.get("evidence_summary", [])})
    detail["relationships"] = list(relationships)
    detail["conflicts"] = list(conflicts)
    if fact.get("normalized_terms"):
        detail["normalized_terms"] = list(fact["normalized_terms"])
    return detail


def _evidence_summary(fact: JsonObject) -> list[JsonObject]:
    evidence = fact.get("evidence_summary", fact.get("evidence", []))
    summaries = []
    for item in evidence:
        if isinstance(item, dict):
            summaries.append({key: item[key] for key in ("source", "text", "source_id") if key in item})
    return summaries


def _mutation(value: Any, affected_fact_ids: list[str] | None = None) -> JsonObject:
    value = dict(value or {})
    status = "ok" if value.get("status") not in REJECTION_STATUSES else str(value.get("status"))
    error = _store_rejection_error(value) if status != "ok" else None
    fact_id = str(value.get("fact_id", ""))
    affected = affected_fact_ids if affected_fact_ids is not None else ([fact_id] if fact_id else [])
    payload = {
        "status": status,
        "mutation_status": value.get("mutation_status", value.get("status", "noop")),
        "fact_id": fact_id,
        "verification_state": value.get("verification_state", "unknown"),
        "conflicts": value.get("conflicts", []),
        "confirmation_required": bool(value.get("confirmation_required", False)),
        "audit": value.get("audit", {}),
        "affected_fact_ids": [str(item) for item in affected if str(item)] if status == "ok" else [],
    }
    if error is not None:
        payload["error"] = error
    return payload


def _normalize_tool_result(tool: str, payload: JsonObject) -> JsonObject:
    status = "ok" if payload.get("status") not in REJECTION_STATUSES else str(payload.get("status"))
    data = {key: value for key, value in payload.items() if key not in {"status", "tool", "data", "error", "errors"}}
    error = payload.get("error")
    if status != "ok" and not isinstance(error, dict):
        error = _store_rejection_error(payload)
    return _tool_result(tool, status, data=data, error=error)


def _tool_result(tool: str, status: str, data: JsonObject | None = None, error: JsonObject | None = None) -> JsonObject:
    if status not in {"ok", "rejected", "error"}:
        raise ValueError(f"Unsupported tool result status: {status}.")
    if status != "ok" and not isinstance(error, dict):
        raise ValueError("Non-ok career tool results require an error object.")
    result: JsonObject = {"tool": tool, "status": status}
    if data is not None:
        result["data"] = data
        result.update(data)
    if status != "ok":
        result["error"] = _normalize_error(error)
    return result


def _normalize_error(error: JsonObject | None) -> JsonObject:
    if not isinstance(error, dict):
        raise ValueError("Career tool error must be an object.")
    error_type = str(error.get("type", "store_error"))
    if error_type not in ERROR_TYPES:
        error_type = "store_error"
    message = _safe_text_message(str(error.get("message") or GENERIC_STORE_ERROR_MESSAGE))
    normalized = {"type": error_type, "message": message}
    reason = error.get("reason")
    if isinstance(reason, str) and reason:
        normalized["reason"] = reason
    return normalized


def _store_rejection_error(value: JsonObject) -> JsonObject:
    error = _first_store_error(value)
    reason_code = _store_reason_code(value, error)
    message = _safe_text_message(_store_error_message(reason_code, error))
    return {
        "type": _reason_code_type(reason_code),
        "message": message,
    }


def _first_store_error(value: JsonObject) -> JsonObject:
    errors = value.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        return errors[0]
    return {}


def _store_reason_code(value: JsonObject, error: JsonObject) -> str:
    code = error.get("code")
    if isinstance(code, str) and code.strip():
        return code
    audit = value.get("audit")
    if isinstance(audit, dict) and isinstance(audit.get("reason"), str) and audit["reason"].strip():
        return audit["reason"]
    status = value.get("status")
    return str(status or "store_error")


def _store_error_message(reason_code: str, error: JsonObject) -> str:
    message = error.get("message")
    if isinstance(message, str) and message.strip():
        return message
    return reason_code.replace("_", " ")


def _reason_code_type(reason_code: str) -> str:
    if reason_code in NOT_FOUND_REASON_CODES or reason_code.endswith("_not_found"):
        return "not_found"
    if reason_code in POLICY_REASON_CODES:
        return "policy_error"
    if reason_code.startswith(("invalid_", "malformed_", "missing_", "unknown_")) or reason_code == "fact_id_mismatch":
        return "validation_error"
    return "store_error"


def _match(row: JsonObject) -> JsonObject:
    fact_ids = row.get("fact_ids")
    if fact_ids is None and row.get("fact_id"):
        fact_ids = [row["fact_id"]]
    resolution_state = str(row.get("resolution_state", "unknown"))
    if resolution_state not in _contract_set("resolution_states"):
        raise StoreContractError(f"career-store returned non-canonical resolution_state: {resolution_state}")
    return {
        "requirement_id": str(row.get("requirement_id", "")),
        "resolution_state": resolution_state,
        "fact_ids": list(fact_ids or []),
        "reasoning": str(row.get("reasoning", row.get("match_type", "classified by career-store fact graph"))),
    }


def _coherent_matches(value: Any, requirements: list[JsonObject]) -> list[JsonObject]:
    rows_by_requirement: dict[str, JsonObject] = {}
    if isinstance(value, dict):
        match_rows = value.get("matches", [])
        unresolved_rows = value.get("unresolved", [])
    else:
        match_rows = value or []
        unresolved_rows = []
    for row in match_rows or []:
        if not isinstance(row, dict):
            continue
        requirement_id = str(row.get("requirement_id", ""))
        if requirement_id and requirement_id not in rows_by_requirement:
            rows_by_requirement[requirement_id] = row
    for row in unresolved_rows or []:
        if not isinstance(row, dict):
            continue
        requirement_id = str(row.get("requirement_id", ""))
        if requirement_id and requirement_id not in rows_by_requirement:
            rows_by_requirement[requirement_id] = row
    for requirement in requirements:
        requirement_id = str(requirement.get("requirement_id", requirement.get("id", "")))
        if requirement_id and requirement_id not in rows_by_requirement:
            rows_by_requirement[requirement_id] = {
                "requirement_id": requirement_id,
                "resolution_state": "unknown",
                "fact_ids": [],
            }
    return [_match(row) for row in rows_by_requirement.values()]


def _apply_policy_decision(result: JsonObject, policy_decision: policy.PolicyDecision, confirmed: bool) -> None:
    if not policy_decision.requires_confirmation:
        return
    result["confirmation_required"] = True
    result["confirmed"] = confirmed
    data = result.get("data")
    if isinstance(data, dict):
        data["confirmation_required"] = True
        data["confirmed"] = confirmed


def _unverified_fact(fact: JsonObject) -> JsonObject:
    fact_id = str(fact.get("fact_id", ""))
    policy_decision = policy.evaluate_policy(
        "career.verify_fact",
        {"fact_id": fact_id, "verification_state": "user_verified", "confirmation": {}},
        confirmed=False,
    )
    return {
        "fact_id": fact_id,
        "text": str(fact.get("text", "")),
        "verification_state": str(fact.get("verification_state", "unknown")),
        "confirmation_required": policy_decision.requires_confirmation,
    }


def _exception_type(exc: Exception) -> str:
    if isinstance(exc, StoreContractError):
        return "store_error"
    if isinstance(exc, DisallowedTransitionError):
        return "policy_error"
    if isinstance(
        exc,
        (
            InvalidInterpretationProposalError,
            InvalidRelationshipConfirmationError,
            MergeConflictError,
            TypeError,
            ValueError,
        ),
    ):
        return "validation_error"
    if isinstance(exc, KeyError):
        return "not_found"
    if isinstance(exc, (IncompatibleSchemaVersionError, MigrationFailedError)):
        return "store_error"
    transaction_result = getattr(exc, "transaction_result", None)
    if transaction_result is not None:
        return "store_error"
    return "store_error"


def _safe_text_message(text: str) -> str:
    return audit.safe_text_message(text)


def _safe_message(exc: Exception) -> str:
    text = str(exc) or GENERIC_STORE_ERROR_MESSAGE
    return _safe_text_message(text)


__all__ = ["CareerMcpAdapter", "create_career_mcp"]
