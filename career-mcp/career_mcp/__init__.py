"""Public runtime package for career-mcp."""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from typing import Any


JsonObject = dict[str, Any]


class CareerMcpAdapter:
    """Narrow tool adapter over an injected career-store service."""

    def __init__(self, store: Any, policy: JsonObject | None = None, audit_sink: Any = None) -> None:
        self._store = store
        self._policy = policy or {}
        self._audit_sink = audit_sink
        self._tools = _load_tools()
        self._tool_by_name = {tool["name"]: tool for tool in self._tools}

    def list_tools(self) -> list[JsonObject]:
        return [dict(tool) for tool in self._tools]

    async def call_tool(self, name: str, arguments: JsonObject | None, context: JsonObject | None = None) -> JsonObject:
        if name not in self._tool_by_name:
            return _error("unknown_tool", "Unknown career tool.")
        arguments = arguments or {}
        validation_error = _validate(arguments, self._tool_by_name[name]["input_schema"])
        if validation_error:
            return _error("validation_error", validation_error)
        try:
            if name == "career.search_facts":
                result = await self._search_facts(arguments)
            elif name == "career.get_fact":
                result = await self._get_fact(arguments)
            elif name == "career.propose_fact":
                result = await self._propose_fact(arguments)
            elif name == "career.add_evidence":
                result = await self._add_evidence(arguments)
            elif name == "career.verify_fact":
                result = await self._verify_fact(arguments)
            elif name == "career.add_relationship":
                result = await self._add_relationship(arguments)
            elif name == "career.find_matches":
                result = await self._find_matches(arguments)
            elif name == "career.get_unverified":
                result = await self._get_unverified(arguments)
            else:
                result = _error("unknown_tool", "Unknown career tool.")
        except (KeyError, TypeError, ValueError) as exc:
            result = _error(_exception_type(exc), _safe_message(exc))
        if context is not None and isinstance(result, dict):
            result.setdefault("context", context)
        self._record_audit(name, result)
        return result

    async def _search_facts(self, arguments: JsonObject) -> JsonObject:
        if hasattr(self._store, "search_facts"):
            value = await _maybe_await(self._store.search_facts(**arguments))
        else:
            filters: JsonObject = {}
            if arguments.get("verification"):
                filters["verification_state"] = arguments["verification"][0]
            if arguments.get("types"):
                filters["type"] = arguments["types"][0]
            value = await _maybe_await(
                self._store.searchFacts(
                    arguments["query"],
                    filters=filters,
                    limit=arguments.get("limit", 10),
                    include_evidence=True,
                )
            )
        facts = value.get("facts", value) if isinstance(value, dict) else value
        return {"status": "ok", "facts": sorted((_fact_summary(fact) for fact in facts), key=lambda fact: fact["fact_id"])}

    async def _get_fact(self, arguments: JsonObject) -> JsonObject:
        if hasattr(self._store, "get_fact"):
            value = await _maybe_await(self._store.get_fact(**arguments))
        else:
            value = await _maybe_await(self._store.getFact(arguments["fact_id"]))
        fact = _extract_fact(value)
        if not fact:
            return _error("not_found", "Career fact not found.")
        evidence = value.get("evidence", []) if isinstance(value, dict) else fact.get("evidence_summary", [])
        relationships = value.get("relationships", fact.get("relationships", [])) if isinstance(value, dict) else fact.get("relationships", [])
        conflicts = value.get("conflicts", fact.get("conflicts", [])) if isinstance(value, dict) else fact.get("conflicts", [])
        normalized = _fact_detail(fact, evidence, relationships, conflicts)
        return {
            "status": "ok",
            "fact": normalized,
            "verification_state": normalized["verification_state"],
            "evidence_summary": normalized["evidence_summary"],
            "relationships": normalized["relationships"],
            "conflicts": normalized["conflicts"],
        }

    async def _propose_fact(self, arguments: JsonObject) -> JsonObject:
        if hasattr(self._store, "propose_fact"):
            value = await _maybe_await(self._store.propose_fact(**arguments))
        else:
            fact = {"type": arguments["type"], "text": arguments["text"], "verification_state": "unknown"}
            value = await _maybe_await(
                self._store.upsertFact(
                    fact,
                    arguments.get("evidence"),
                    source=arguments["source"],
                    policy={**self._policy, "allow_inferred_final": False},
                )
            )
        return _mutation(value)

    async def _add_evidence(self, arguments: JsonObject) -> JsonObject:
        if hasattr(self._store, "add_evidence"):
            value = await _maybe_await(self._store.add_evidence(**arguments))
        else:
            source = str(arguments["evidence"].get("source", "mcp_tool"))
            value = await _maybe_await(self._store.addEvidence(arguments["fact_id"], arguments["evidence"], source=source))
        return _mutation(value)

    async def _verify_fact(self, arguments: JsonObject) -> JsonObject:
        if hasattr(self._store, "verify_fact"):
            value = await _maybe_await(self._store.verify_fact(**arguments))
        else:
            confirmation = arguments["confirmation"]
            source = str(confirmation.get("source", confirmation.get("kind", "mcp_tool")))
            value = await _maybe_await(
                self._store.verifyFact(arguments["fact_id"], arguments["verification_state"], confirmation, source=source)
            )
        return _mutation(value)

    async def _add_relationship(self, arguments: JsonObject) -> JsonObject:
        if hasattr(self._store, "add_relationship"):
            value = await _maybe_await(self._store.add_relationship(**arguments))
        else:
            value = await _maybe_await(
                self._store.addRelationship(
                    arguments["from_fact_id"],
                    arguments["to_fact_id"],
                    arguments["relationship_type"],
                    evidence_or_rationale=arguments.get("evidence") or arguments.get("confirmation") or {},
                    policy=self._policy,
                )
            )
        return _mutation(value)

    async def _find_matches(self, arguments: JsonObject) -> JsonObject:
        if hasattr(self._store, "find_matches"):
            value = await _maybe_await(self._store.find_matches(**arguments))
        else:
            value = await _maybe_await(self._store.findCandidateMatches(arguments["requirements"], policy=self._policy))
        rows = value.get("matches", value) if isinstance(value, dict) else value
        matches = [_match(row) for row in rows]
        if isinstance(value, dict):
            matches.extend(_unresolved_match(row) for row in value.get("unresolved", []))
        return {"status": "ok", "matches": sorted(matches, key=lambda item: item["requirement_id"])}

    async def _get_unverified(self, arguments: JsonObject) -> JsonObject:
        if hasattr(self._store, "get_unverified"):
            value = await _maybe_await(self._store.get_unverified(**arguments))
            facts = value.get("facts", value) if isinstance(value, dict) else value
        else:
            query = arguments.get("topic") or ""
            value = await _maybe_await(
                self._store.searchFacts(
                    query,
                    filters={"verification_state": "unknown"},
                    limit=arguments.get("limit", 10),
                    include_evidence=True,
                )
            )
            facts = value.get("facts", [])
        return {"status": "ok", "facts": [_unverified_fact(fact) for fact in facts]}

    def _record_audit(self, name: str, result: JsonObject) -> None:
        if self._audit_sink is None:
            return
        event = {"tool": name, "status": result.get("status")}
        if callable(self._audit_sink):
            self._audit_sink(event)
        elif hasattr(self._audit_sink, "append"):
            self._audit_sink.append(event)


def create_career_mcp(store: Any, policy: JsonObject | None = None, audit_sink: Any = None) -> CareerMcpAdapter:
    return CareerMcpAdapter(store=store, policy=policy, audit_sink=audit_sink)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _load_tools() -> list[JsonObject]:
    surface_path = Path(__file__).resolve().parents[1] / "tool_surface.json"
    surface = json.loads(surface_path.read_text(encoding="utf-8"))
    return list(surface["tools"])


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


def _mutation(value: Any) -> JsonObject:
    value = dict(value or {})
    return {
        "status": "ok" if value.get("status") not in {"error", "rejected"} else value.get("status"),
        "mutation_status": value.get("mutation_status", value.get("status", "noop")),
        "fact_id": value.get("fact_id", ""),
        "verification_state": value.get("verification_state", "unknown"),
        "conflicts": value.get("conflicts", []),
        "confirmation_required": bool(value.get("confirmation_required", False)),
        "audit": value.get("audit", {}),
    }


def _match(row: JsonObject) -> JsonObject:
    fact_ids = row.get("fact_ids")
    if fact_ids is None and row.get("fact_id"):
        fact_ids = [row["fact_id"]]
    return {
        "requirement_id": str(row.get("requirement_id", "")),
        "resolution_state": str(row.get("resolution_state", "unknown")),
        "fact_ids": list(fact_ids or []),
        "reasoning": str(row.get("reasoning", row.get("match_type", "classified by career-store fact graph"))),
    }


def _unresolved_match(row: JsonObject) -> JsonObject:
    return {
        "requirement_id": str(row.get("requirement_id", "")),
        "resolution_state": str(row.get("resolution_state", "unknown")),
        "fact_ids": [],
        "reasoning": "No confirmed career fact matched this requirement.",
    }


def _unverified_fact(fact: JsonObject) -> JsonObject:
    return {
        "fact_id": str(fact.get("fact_id", "")),
        "text": str(fact.get("text", "")),
        "verification_state": str(fact.get("verification_state", "unknown")),
        "confirmation_required": True,
    }


def _error(error_type: str, message: str) -> JsonObject:
    return {"status": "error", "error": {"type": error_type, "message": message}}


def _exception_type(exc: Exception) -> str:
    text = str(exc).casefold()
    if "confirmation" in text:
        return "policy_error"
    if "not found" in text or "not_found" in text:
        return "not_found"
    return "validation_error"


def _safe_message(exc: Exception) -> str:
    text = str(exc) or "Tool call failed validation."
    blocked = ("traceback", "sqlite", "select", "insert", "update", "delete")
    if any(word in text.casefold() for word in blocked):
        return "Tool call failed validation."
    return text


__all__ = ["CareerMcpAdapter", "create_career_mcp"]
