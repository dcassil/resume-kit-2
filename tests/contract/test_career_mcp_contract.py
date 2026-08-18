"""Contract-first tests for the future career_mcp package."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import re
import tempfile
import unittest
from pathlib import Path

from tests.e2e.test_career_mcp_audit_reconstruction_e2e import CareerMcpAuditReconstructionE2ETests  # bridge into gated contract module
from tests.e2e.test_career_mcp_real_store_scenarios_e2e import CareerMcpRealStoreScenarioE2ETests  # bridge into gated contract module
from tests.contract.test_career_mcp_server_contract import (  # bridge into gated contract module
    CareerMcpCliLifecycleContractTests,
    CareerMcpServerProtocolContractTests,
    CareerMcpSubprocessStartupFailureContractTests,
    CareerMcpSubprocessTransportContractTests,
)


ROOT = Path(__file__).resolve().parents[2]
SURFACE = json.loads((ROOT / "career-mcp" / "career_mcp" / "tool_surface.json").read_text(encoding="utf-8"))
STORE_SURFACE = json.loads((ROOT / "career-store" / "store_surface.json").read_text(encoding="utf-8"))

ALLOWED_TOOLS = tuple(tool["name"] for tool in SURFACE["tools"])
WRITE_TOOLS = tuple(tool["name"] for tool in SURFACE["tools"] if tool.get("mutates") is True)
FORBIDDEN_TOOLS = tuple(SURFACE["forbidden_tools"])
VERIFICATION_STATES = set(SURFACE["verification_states"])
RELATIONSHIP_TYPES = set(SURFACE["relationship_types"])
RESOLUTION_STATES = set(SURFACE["resolution_states"])
STORE_VERIFICATION_STATES = set(STORE_SURFACE["verification_states"])
STORE_RELATIONSHIP_TYPES = set(STORE_SURFACE["relationship_types"])
STORE_RESOLUTION_STATES = set(STORE_SURFACE["resolution_states"])
STORE_SURFACE_NAMES = {surface["name"] for surface in STORE_SURFACE["surfaces"]}
FIXED_TIME = "2026-01-01T00:00:00Z"
FIXED_OPERATION_ID = "00000000-0000-4000-8000-000000000108"
MUTATION_AUDIT_KEYS = {
    "operation_id",
    "timestamp",
    "tool",
    "is_mutation",
    "status",
    "args_redacted",
    "affected_fact_ids",
    "resulting_verification_state",
    "conflict_flag",
    "confirmation_required",
}
STORE_INTERNAL_AUDIT_TOKENS = (
    "raw_sql",
    "transaction_result",
    "normalized_terms_json",
    "metadata_json",
    "evidence_json",
    "fact_ids_json",
    "evidence_ids_json",
    "merged_into_fact_id",
    "sqlite_schema",
    "schema_migrations",
)


def store_rejection(operation: str, fact_id: str, code: str, field_path: str, allowed_values: set[str] | None = None):
    error = {"code": code, "field_path": field_path, "message": code.replace("_", " ")}
    if allowed_values is not None:
        error["allowed_values"] = sorted(allowed_values)
    return {
        "schema_version": "career-store.v1",
        "status": "error",
        "mutation_status": "rejected",
        "fact_id": fact_id,
        "verification_state": "unknown",
        "conflicts": [],
        "confirmation_required": True,
        "errors": [error],
        "audit": {"operation": operation, "mutated": False, "reason": code},
    }


class FakeCareerStore:
    """Small deterministic store double that future MCP code should call."""

    ACCEPTED_VERIFICATION_STATES = STORE_VERIFICATION_STATES
    ACCEPTED_RELATIONSHIP_TYPES = STORE_RELATIONSHIP_TYPES
    ACCEPTED_RESOLUTION_STATES = STORE_RESOLUTION_STATES

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.facts = {
            "fact_react": {
                "fact_id": "fact_react",
                "type": "skill",
                "text": "React",
                "verification_state": "source_stated",
                "evidence_summary": [{"source": "resume", "text": "React"}],
                "relationships": [],
                "conflicts": [],
                "contact_data": "must never leak",
            },
            "fact_api": {
                "fact_id": "fact_api",
                "type": "experience",
                "text": "REST/API design",
                "verification_state": "source_stated",
                "evidence_summary": [{"source": "resume", "text": "REST APIs"}],
                "relationships": [],
                "conflicts": [],
            },
            "fact_responsive": {
                "fact_id": "fact_responsive",
                "type": "experience",
                "text": "responsive web apps",
                "verification_state": "source_stated",
                "evidence_summary": [{"source": "resume", "text": "responsive apps"}],
                "relationships": [{"to_fact_id": "fact_responsive_design", "relationship_type": "alias"}],
                "conflicts": [],
            },
            "fact_aws": {
                "fact_id": "fact_aws",
                "type": "skill",
                "text": "AWS experience, six years",
                "verification_state": "user_verified",
                "evidence_summary": [{"source": "user_answer", "text": "about six years of AWS experience"}],
                "relationships": [{"to_fact_id": "fact_azure", "relationship_type": "related"}],
                "conflicts": [],
            },
            "fact_graphql": {
                "fact_id": "fact_graphql",
                "type": "skill",
                "text": "GraphQL APIs in production",
                "verification_state": "user_verified",
                "evidence_summary": [{"source": "user_answer", "text": "GraphQL APIs in production"}],
                "relationships": [],
                "conflicts": [],
            },
            "fact_candidate": {
                "fact_id": "fact_candidate",
                "type": "experience",
                "text": "candidate architecture experience",
                "verification_state": "unknown",
                "evidence_summary": [],
                "relationships": [],
                "conflicts": [],
            },
            "fact_inferred_architecture": {
                "fact_id": "fact_inferred_architecture",
                "type": "experience",
                "text": "inferred architecture experience",
                "verification_state": "inferred",
                "evidence_summary": [],
                "relationships": [],
                "conflicts": [],
            },
        }

    def searchFacts(self, query: str, filters=None, limit=None, include_evidence=True):
        self.calls.append(
            (
                "searchFacts",
                {
                    "query": query,
                    "filters": filters or {},
                    "limit": limit,
                    "include_evidence": include_evidence,
                },
            )
        )
        query = query.lower()
        verification_state = (filters or {}).get("verification_state")
        matches = [fact for fact in self.facts.values() if query in fact["text"].lower()]
        if verification_state:
            matches = [fact for fact in matches if fact.get("verification_state") == verification_state]
        if limit is not None:
            matches = matches[:limit]
        return {"facts": sorted(matches, key=lambda fact: fact["fact_id"])}

    def getFact(self, fact_id: str):
        self.calls.append(("getFact", {"fact_id": fact_id}))
        fact = self.facts.get(fact_id)
        if fact is None:
            return {"status": "not_found"}
        return {
            "fact": fact,
            "evidence": fact.get("evidence_summary", []),
            "relationships": fact.get("relationships", []),
            "conflicts": fact.get("conflicts", []),
        }

    def upsertFact(self, fact: dict, evidence=None, source=None, policy=None, dedupe_key=None):
        self.calls.append(
            (
                "upsertFact",
                {
                    "fact": fact,
                    "evidence": evidence,
                    "source": source,
                    "policy": policy,
                    "dedupe_key": dedupe_key,
                },
            )
        )
        fact_id = "fact_aws" if "aws" in fact["text"].lower() else "fact_candidate"
        return {
            "mutation_status": "deduped" if fact_id in self.facts else "created",
            "fact_id": fact_id,
            "verification_state": "unknown",
            "conflicts": [],
            "confirmation_required": True,
            "audit": {"operation": "upsertFact"},
        }

    def addEvidence(self, fact_id: str, evidence: dict, source: str):
        self.calls.append(("addEvidence", {"fact_id": fact_id, "evidence": evidence, "source": source}))
        return {
            "mutation_status": "updated",
            "fact_id": fact_id,
            "verification_state": self.facts[fact_id]["verification_state"],
            "conflicts": [],
            "confirmation_required": True,
            "audit": {"operation": "addEvidence"},
        }

    def verifyFact(self, fact_id: str, verification_state: str, confirmation: dict, source: str):
        self.calls.append(
            (
                "verifyFact",
                {
                    "fact_id": fact_id,
                    "verification_state": verification_state,
                    "confirmation": confirmation,
                    "source": source,
                },
            )
        )
        if verification_state not in self.ACCEPTED_VERIFICATION_STATES:
            return store_rejection("verifyFact", fact_id, "invalid_verification_state", "verification_state", self.ACCEPTED_VERIFICATION_STATES)
        if verification_state == "user_verified" and (
            not isinstance(confirmation, dict)
            or confirmation.get("outcome") != "affirmed"
            or not confirmation.get("provenance")
        ):
            return store_rejection("verifyFact", fact_id, "user_verified_without_explicit_confirmation", "confirmation")
        return {
            "mutation_status": "updated",
            "fact_id": fact_id,
            "verification_state": verification_state,
            "conflicts": [],
            "confirmation_required": False,
            "audit": {"operation": "verifyFact"},
        }

    def addRelationship(
        self,
        from_fact_id: str,
        to_fact_id: str,
        relationship_type: str,
        evidence_or_rationale: dict,
        policy: dict,
    ):
        self.calls.append(
            (
                "addRelationship",
                {
                    "from_fact_id": from_fact_id,
                    "to_fact_id": to_fact_id,
                    "relationship_type": relationship_type,
                    "evidence_or_rationale": evidence_or_rationale,
                    "policy": policy,
                },
            )
        )
        if relationship_type not in self.ACCEPTED_RELATIONSHIP_TYPES:
            return store_rejection("addRelationship", from_fact_id, "invalid_relationship_type", "relationship_type", self.ACCEPTED_RELATIONSHIP_TYPES)
        return {
            "mutation_status": "created",
            "fact_id": from_fact_id,
            "verification_state": "unknown",
            "conflicts": [],
            "confirmation_required": relationship_type in {"alias", "equivalent"},
            "audit": {"operation": "addRelationship"},
        }

    def findCandidateMatches(self, requirements: list[dict], policy: dict):
        self.calls.append(("findCandidateMatches", {"requirements": requirements, "policy": policy}))
        matches = []
        for req in requirements:
            terms = {str(term).casefold() for term in req.get("normalized_terms", [])}
            terms.add(str(req.get("source_text", req.get("text", ""))).casefold())
            matched_fact = None
            for fact in sorted(self.facts.values(), key=lambda item: item["fact_id"]):
                if any(term and term in fact["text"].casefold() for term in terms):
                    matched_fact = fact
                    break
            if matched_fact is None:
                matches.append({"requirement_id": req["requirement_id"], "resolution_state": "unknown", "fact_ids": []})
                continue
            state = "verified_fact_match" if matched_fact["verification_state"] == "user_verified" else "exact_match"
            if matched_fact["verification_state"] in {"unknown", "inferred"}:
                state = "possible_match"
            matches.append(
                {
                    "requirement_id": req["requirement_id"],
                    "resolution_state": state,
                    "fact_ids": [matched_fact["fact_id"]],
                    "reasoning": "classified by verified fake using local fact text",
                }
            )
        return matches

    def findConflicts(self, fact_or_claim: dict, scope=None):
        self.calls.append(("findConflicts", {"fact_or_claim": fact_or_claim, "scope": scope}))
        return {"conflicts": fact_or_claim.get("conflicts", [])}


def load_adapter(test_case: unittest.TestCase):
    try:
        module = importlib.import_module("career_mcp")
    except ModuleNotFoundError as exc:
        test_case.fail(
            "Expected importable package 'career_mcp'. Implement career_mcp.create_career_mcp(store, "
            "policy=None, audit_sink=None) as the public MCP adapter factory."
        )
        raise exc

    factory = getattr(module, "create_career_mcp", None)
    test_case.assertTrue(callable(factory), "career_mcp must expose create_career_mcp(store, policy=None, audit_sink=None).")
    signature = inspect.signature(factory)
    test_case.assertIn("store", signature.parameters, "create_career_mcp must use injected career-store service dependency.")
    adapter = factory(store=FakeCareerStore())
    test_case.assertTrue(callable(getattr(adapter, "list_tools", None)), "Adapter must expose list_tools().")
    test_case.assertTrue(callable(getattr(adapter, "call_tool", None)), "Adapter must expose call_tool(name, arguments).")
    return adapter


def maybe_await(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def call_tool(adapter, name: str, arguments: dict):
    return maybe_await(adapter.call_tool(name, arguments))


def confirmed(arguments: dict) -> dict:
    return {**arguments, "confirmed": True}


def audited_adapter(store=None, sink=None):
    career_mcp = importlib.import_module("career_mcp")
    return career_mcp.create_career_mcp(
        store=store if store is not None else FakeCareerStore(),
        audit_sink=sink if sink is not None else [],
        operation_id_provider=lambda: FIXED_OPERATION_ID,
        timestamp_provider=lambda: FIXED_TIME,
    )


def load_career_modules(test_case: unittest.TestCase):
    try:
        career_mcp = importlib.import_module("career_mcp")
        career_store = importlib.import_module("career_store")
    except ModuleNotFoundError as exc:
        test_case.fail("Expected importable career_mcp and career_store packages for real-store MCP contract tests.")
        raise exc
    return career_mcp, career_store


def open_real_store(test_case: unittest.TestCase):
    _career_mcp, career_store = load_career_modules(test_case)
    directory = tempfile.TemporaryDirectory()
    test_case.addCleanup(directory.cleanup)
    return career_store.openCareerStore(str(Path(directory.name) / "career.db"), clock=lambda: FIXED_TIME)


def real_store_adapter(test_case: unittest.TestCase):
    career_mcp, _career_store = load_career_modules(test_case)
    store = open_real_store(test_case)
    return store, career_mcp.create_career_mcp(store=store)


def confirmation_for_state(fact_id: str, verification_state: str) -> dict:
    if verification_state == "imported":
        return {
            "factId": fact_id,
            "outcome": "affirmed",
            "provenance": [
                {
                    "source": "external_system",
                    "source_id": "import_1",
                    "text": "Imported from durable profile.",
                    "metadata": {"import_id": "import_1", "external_id": fact_id},
                }
            ],
        }
    if verification_state == "inferred":
        return {
            "factId": fact_id,
            "outcome": "affirmed",
            "provenance": [
                {
                    "source": "agent_interpretation",
                    "text": "Agent inferred this career fact from matching context.",
                    "metadata": {"inference_id": "inference_1", "rationale": "semantic overlap"},
                }
            ],
        }
    if verification_state == "source_stated":
        return {
            "factId": fact_id,
            "outcome": "affirmed",
            "provenance": [{"source": "resume_source", "source_id": "resume_1", "text": "Resume states this fact."}],
        }
    return {
        "factId": fact_id,
        "outcome": "affirmed",
        "provenance": [{"source": "user_answer", "text": "Yes, confirmed."}],
    }


def assert_typed_error(test_case: unittest.TestCase, result: dict, error_type: str):
    test_case.assertEqual(result["status"], "error")
    test_case.assertEqual(result["error"]["type"], error_type)
    test_case.assertNotRegex(json.dumps(result).lower(), r"\b(sqlite|select|insert|update|delete|traceback)\b")


class ToolSurfaceManifestTests(unittest.TestCase):
    def test_manifest_declares_exact_allowed_tools(self):
        self.assertEqual(tuple(ALLOWED_TOOLS), (
            "career.search_facts",
            "career.get_fact",
            "career.propose_fact",
            "career.add_evidence",
            "career.verify_fact",
            "career.add_relationship",
            "career.find_matches",
            "career.get_unverified",
        ))
        self.assertEqual(len(ALLOWED_TOOLS), len(set(ALLOWED_TOOLS)))
        self.assertFalse(set(ALLOWED_TOOLS) & set(FORBIDDEN_TOOLS))

    def test_manifest_defines_inputs_and_outputs_for_every_tool(self):
        for tool in SURFACE["tools"]:
            with self.subTest(tool=tool["name"]):
                self.assertEqual(tool["input_schema"]["type"], "object")
                self.assertIn("additionalProperties", tool["input_schema"])
                self.assertIn("response_contract", tool)
                self.assertTrue(tool["response_contract"]["required_fields"])

    def test_write_tools_require_mutation_status_verification_conflicts_confirmation_and_audit(self):
        required = {"mutation_status", "fact_id", "verification_state", "conflicts", "confirmation_required", "audit"}
        for tool in SURFACE["tools"]:
            if tool.get("mutates"):
                with self.subTest(tool=tool["name"]):
                    response_fields = set(tool["response_contract"]["required_fields"])
                    self.assertTrue(required <= response_fields)

    def test_write_tool_schemas_accept_explicit_confirmed_argument(self):
        for tool in SURFACE["tools"]:
            if tool.get("mutates"):
                with self.subTest(tool=tool["name"]):
                    confirmed_schema = tool["input_schema"]["properties"].get("confirmed")
                    self.assertEqual(confirmed_schema, {
                        "type": "boolean",
                        "default": False,
                        "description": "Host-mediated user confirmation for this mutating tool call.",
                    })

    def test_policy_classifies_every_manifest_tool_from_mutates_flag(self):
        career_mcp = importlib.import_module("career_mcp")
        policy = importlib.import_module("career_mcp.policy")
        self.assertEqual(set(career_mcp.STORE_METHOD_BY_TOOL), set(ALLOWED_TOOLS))
        for tool in SURFACE["tools"]:
            name = tool["name"]
            with self.subTest(tool=name):
                unconfirmed = policy.evaluate_policy(name, {}, confirmed=False)
                confirmed_decision = policy.evaluate_policy(name, {}, confirmed=True)
                if tool.get("mutates"):
                    self.assertFalse(unconfirmed.allowed)
                    self.assertTrue(unconfirmed.requires_confirmation)
                    self.assertEqual(unconfirmed.reason, "confirmation_required")
                    self.assertTrue(confirmed_decision.allowed)
                    self.assertTrue(confirmed_decision.requires_confirmation)
                else:
                    self.assertTrue(unconfirmed.allowed)
                    self.assertFalse(unconfirmed.requires_confirmation)
                    self.assertTrue(confirmed_decision.allowed)
                    self.assertFalse(confirmed_decision.requires_confirmation)


class VerifiedFakeCareerStoreConformanceTests(unittest.TestCase):
    def test_fake_methods_are_exactly_the_adapter_called_store_surface(self):
        career_mcp = importlib.import_module("career_mcp")
        adapter_methods = set(career_mcp.STORE_METHOD_BY_TOOL.values())
        fake_methods = {
            name
            for name, value in inspect.getmembers(FakeCareerStore, predicate=inspect.isfunction)
            if not name.startswith("_") and name != "__init__"
        }

        self.assertTrue(adapter_methods <= STORE_SURFACE_NAMES)
        self.assertEqual(fake_methods, adapter_methods | {"findConflicts"})
        self.assertTrue(fake_methods <= STORE_SURFACE_NAMES | {"findConflicts"})

    def test_fake_enum_vocabulary_matches_store_surface_sets(self):
        self.assertEqual(FakeCareerStore.ACCEPTED_VERIFICATION_STATES, STORE_VERIFICATION_STATES)
        self.assertEqual(FakeCareerStore.ACCEPTED_RELATIONSHIP_TYPES, STORE_RELATIONSHIP_TYPES)
        self.assertEqual(FakeCareerStore.ACCEPTED_RESOLUTION_STATES, STORE_RESOLUTION_STATES)

    def test_fake_rejections_are_store_shaped_dicts_not_free_form_exceptions(self):
        fake = FakeCareerStore()
        rejected_state = fake.verifyFact("fact_aws", "made_up", confirmation={}, source="mcp_tool")
        rejected_relation = fake.addRelationship("fact_aws", "fact_azure", "made_up", {}, {})
        rejected_confirmation = fake.verifyFact(
            "fact_aws",
            "user_verified",
            confirmation={"outcome": "affirmed"},
            source="mcp_tool",
        )

        for result in (rejected_state, rejected_relation, rejected_confirmation):
            with self.subTest(result=result):
                self.assertIsInstance(result, dict)
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["mutation_status"], "rejected")
                self.assertIsInstance(result.get("errors"), list)
                self.assertIsInstance(result["errors"][0].get("code"), str)
                self.assertIn("audit", result)


class CareerMcpAdapterContractTests(unittest.TestCase):
    def setUp(self):
        self.adapter = load_adapter(self)

    def test_tool_discovery_returns_exact_allowed_surface(self):
        tools = maybe_await(self.adapter.list_tools())
        discovered = {tool["name"]: tool for tool in tools}
        self.assertEqual(set(discovered), set(ALLOWED_TOOLS))
        for forbidden in FORBIDDEN_TOOLS:
            self.assertNotIn(forbidden, discovered)
        for tool in discovered.values():
            text = tool.get("description", "").lower()
            self.assertNotRegex(text, r"\b(sql|database modification|raw update|raw delete)\b")
            self.assertEqual(tool.get("input_schema", {}).get("type"), "object")

    def test_write_tool_descriptions_disclose_confirmation_and_verification(self):
        tools = {tool["name"]: tool for tool in maybe_await(self.adapter.list_tools())}
        for name in WRITE_TOOLS:
            with self.subTest(tool=name):
                text = json.dumps(tools[name], sort_keys=True).lower()
                self.assertIn("confirmation", text)
                self.assertIn("verification", text)

    def test_argument_validation_returns_typed_errors_without_sql_details(self):
        invalid_calls = [
            ("career.search_facts", {"query": ""}),
            ("career.get_fact", {"fact_id": "not-a-valid-id"}),
            ("career.verify_fact", {"fact_id": "fact_aws", "verification_state": "made_up", "confirmation": {"by": "user"}}),
            ("career.add_relationship", {"from_fact_id": "fact_aws", "to_fact_id": "fact_azure", "relationship_type": "proves"}),
            ("career.verify_fact", {"fact_id": "fact_aws", "verification_state": "user_verified"}),
        ]
        for name, arguments in invalid_calls:
            with self.subTest(tool=name, arguments=arguments):
                result = call_tool(self.adapter, name, arguments)
                self.assertEqual(result["status"], "error")
                self.assertIn(result["error"]["type"], {"validation_error", "not_found", "policy_error"})
                self.assertNotRegex(json.dumps(result).lower(), r"\b(sqlite|select|insert|update|delete|traceback)\b")

    def test_unconfirmed_mutation_is_policy_rejected_before_store_dispatch(self):
        self.adapter._store.calls.clear()  # noqa: SLF001

        result = call_tool(
            self.adapter,
            "career.propose_fact",
            {"type": "skill", "text": "AWS experience", "source": "agent_interpretation"},
        )

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["error"]["type"], "policy_error")
        self.assertEqual(result["error"]["reason"], "confirmation_required")
        self.assertTrue(result["confirmation_required"])
        self.assertFalse(result["confirmed"])
        self.assertEqual(self.adapter._store.calls, [])  # noqa: SLF001

    def test_confirmed_mutation_proceeds_and_exposes_policy_flags(self):
        self.adapter._store.calls.clear()  # noqa: SLF001

        result = call_tool(
            self.adapter,
            "career.propose_fact",
            confirmed({"type": "skill", "text": "AWS experience", "source": "agent_interpretation"}),
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(self.adapter._store.calls[-1][0], "upsertFact")  # noqa: SLF001
        self.assertTrue(result["confirmation_required"])
        self.assertTrue(result["confirmed"])

    def test_read_tool_does_not_require_confirmation(self):
        result = call_tool(self.adapter, "career.search_facts", {"query": "React", "limit": 1})

        self.assertEqual(result["status"], "ok")
        self.assertNotIn("confirmed", result)

    def test_child_parent_relationship_types_are_accepted_and_unadvertised_values_rejected(self):
        for relationship_type in ("child", "parent"):
            with self.subTest(relationship_type=relationship_type):
                result = call_tool(
                    self.adapter,
                    "career.add_relationship",
                    confirmed({
                        "from_fact_id": "fact_aws",
                        "to_fact_id": "fact_azure",
                        "relationship_type": relationship_type,
                    }),
                )
                self.assertEqual(result["status"], "ok", result)
        result = call_tool(
            self.adapter,
            "career.add_relationship",
            {
                "from_fact_id": "fact_aws",
                "to_fact_id": "fact_azure",
                "relationship_type": "sibling",
            },
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["type"], "validation_error")
        self.assertEqual(result["error"]["message"], "relationship_type is not supported.")

    def test_search_facts_returns_deterministic_minimum_evidence_without_sensitive_fields(self):
        result = call_tool(self.adapter, "career.search_facts", {"query": "React", "verification": ["source_stated"]})
        self.assertEqual(result["status"], "ok")
        self.assertEqual([fact["fact_id"] for fact in result["facts"]], sorted(fact["fact_id"] for fact in result["facts"]))
        self.assertTrue(result["facts"])
        for fact in result["facts"]:
            self.assertIn("evidence_summary", fact)
            self.assertNotIn("contact_data", fact)
            self.assertNotIn("raw_sql", fact)

    def test_search_facts_honors_full_verification_and_type_lists_with_union_semantics(self):
        result = call_tool(
            self.adapter,
            "career.search_facts",
            {
                "query": "api",
                "verification": ["user_verified", "source_stated"],
                "types": ["skill", "experience"],
                "limit": 10,
            },
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual({fact["fact_id"] for fact in result["facts"]}, {"fact_api", "fact_graphql"})
        self.assertEqual(
            {fact["verification_state"] for fact in result["facts"]},
            {"source_stated", "user_verified"},
        )
        self.assertEqual(self.adapter._store.calls[-1][0], "searchFacts")  # noqa: SLF001
        self.assertEqual(self.adapter._store.calls[-1][1]["query"], "api")  # noqa: SLF001
        self.assertEqual(self.adapter._store.calls[-1][1]["filters"], {})  # noqa: SLF001
        self.assertIsNone(self.adapter._store.calls[-1][1]["limit"])  # noqa: SLF001

    def test_get_fact_returns_fact_context_and_typed_not_found(self):
        result = call_tool(self.adapter, "career.get_fact", {"fact_id": "fact_react"})
        self.assertEqual(result["status"], "ok")
        fact = result["fact"]
        self.assertEqual(fact["fact_id"], "fact_react")
        self.assertIn(fact["verification_state"], VERIFICATION_STATES)
        self.assertIn("evidence_summary", fact)
        self.assertIn("relationships", fact)
        self.assertIn("conflicts", fact)

        missing = call_tool(self.adapter, "career.get_fact", {"fact_id": "fact_missing"})
        self.assertEqual(missing["status"], "error")
        self.assertEqual(missing["error"]["type"], "not_found")

    def test_propose_fact_forwards_dedupe_key_when_store_surface_accepts_it(self):
        result = call_tool(
            self.adapter,
            "career.propose_fact",
            confirmed({
                "type": "skill",
                "text": "AWS experience",
                "source": "agent_interpretation",
                "dedupe_key": "proposal:aws",
            }),
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(self.adapter._store.calls[-1][0], "upsertFact")  # noqa: SLF001
        self.assertEqual(self.adapter._store.calls[-1][1]["dedupe_key"], "proposal:aws")  # noqa: SLF001

    def test_propose_fact_never_marks_agent_interpretation_user_verified(self):
        result = call_tool(
            self.adapter,
            "career.propose_fact",
            confirmed({"type": "skill", "text": "AWS experience", "source": "agent_interpretation"}),
        )
        self.assertIn(result["mutation_status"], {"created", "deduped", "updated", "noop"})
        self.assertEqual(result["fact_id"], "fact_aws")
        self.assertNotEqual(result["verification_state"], "user_verified")
        self.assertTrue(result["confirmation_required"])
        self.assertIn("audit", result)

    def test_evidence_and_verification_require_explicit_confirmation(self):
        evidence = call_tool(
            self.adapter,
            "career.add_evidence",
            confirmed({"fact_id": "fact_aws", "evidence": {"source": "user_answer", "text": "about six years of AWS experience"}}),
        )
        self.assertEqual(evidence["mutation_status"], "updated")
        self.assertIn(evidence["verification_state"], VERIFICATION_STATES)

        verified = call_tool(
            self.adapter,
            "career.verify_fact",
            confirmed({
                "fact_id": "fact_aws",
                "verification_state": "user_verified",
                "confirmation": {
                    "factId": "fact_aws",
                    "outcome": "affirmed",
                    "provenance": [{"source": "user_answer", "text": "Yes, about six years of AWS experience."}],
                },
            }),
        )
        self.assertEqual(verified["verification_state"], "user_verified")
        self.assertTrue(verified["confirmation_required"])
        self.assertTrue(verified["confirmed"])

    def test_consumed_arguments_assertion_catches_planted_dropped_argument(self):
        career_mcp = importlib.import_module("career_mcp")
        original = career_mcp.TOOL_ARGUMENTS["career.search_facts"]
        career_mcp.TOOL_ARGUMENTS["career.search_facts"] = original - {"limit"}
        try:
            with self.assertRaisesRegex(AssertionError, "validated arguments that dispatch does not consume: limit"):
                call_tool(self.adapter, "career.search_facts", {"query": "React", "limit": 1})
        finally:
            career_mcp.TOOL_ARGUMENTS["career.search_facts"] = original

    def test_consumed_arguments_assertion_covers_confirmed_argument(self):
        career_mcp = importlib.import_module("career_mcp")
        original = career_mcp.TOOL_ARGUMENTS["career.propose_fact"]
        career_mcp.TOOL_ARGUMENTS["career.propose_fact"] = original - {"confirmed"}
        try:
            with self.assertRaisesRegex(AssertionError, "validated arguments that dispatch does not consume: confirmed"):
                call_tool(
                    self.adapter,
                    "career.propose_fact",
                    confirmed({"type": "skill", "text": "AWS experience", "source": "agent_interpretation"}),
                )
        finally:
            career_mcp.TOOL_ARGUMENTS["career.propose_fact"] = original

    def test_relationship_creation_preserves_related_vs_equivalent_distinction(self):
        responsive = call_tool(
            self.adapter,
            "career.add_relationship",
            confirmed({"from_fact_id": "fact_responsive", "to_fact_id": "fact_responsive_design", "relationship_type": "alias"}),
        )
        self.assertEqual(responsive["mutation_status"], "created")

        azure_aws = call_tool(
            self.adapter,
            "career.add_relationship",
            confirmed({"from_fact_id": "fact_azure", "to_fact_id": "fact_aws", "relationship_type": "related"}),
        )
        self.assertEqual(azure_aws["mutation_status"], "created")
        self.assertNotEqual(azure_aws.get("relationship_type"), "equivalent")

    def test_find_matches_returns_resolution_states_without_official_scores(self):
        _store, adapter = real_store_adapter(self)
        seeded: dict[str, str] = {}
        for label, text, verification_state in (
            ("react", "React", "source_stated"),
            ("aws", "AWS experience, six years", "user_verified"),
            ("graphql", "GraphQL APIs in production", "user_verified"),
        ):
            proposed = call_tool(
                adapter,
                "career.propose_fact",
                confirmed({
                    "type": "skill",
                    "text": text,
                    "source": "user_answer" if verification_state == "user_verified" else "resume_source",
                    "evidence": {"source": "user_answer", "source_id": f"seed_{label}", "text": text},
                }),
            )
            self.assertEqual(proposed["status"], "ok", proposed)
            seeded[label] = proposed["fact_id"]
            arguments = {
                "fact_id": proposed["fact_id"],
                "verification_state": verification_state,
                "confirmation": confirmation_for_state(proposed["fact_id"], verification_state),
                "confirmed": True,
            }
            if verification_state == "source_stated":
                arguments["evidence_id"] = f"evidence_seed_{label}"
            verified = call_tool(adapter, "career.verify_fact", arguments)
            self.assertEqual(verified["status"], "ok", verified)

        azure = call_tool(
            adapter,
            "career.propose_fact",
            confirmed({
                "type": "skill",
                "text": "Azure",
                "source": "agent_interpretation",
                "evidence": {"source": "resume_source", "source_id": "seed_azure", "text": "Azure"},
            }),
        )
        self.assertEqual(azure["status"], "ok", azure)
        related = call_tool(
            adapter,
            "career.add_relationship",
            confirmed({
                "from_fact_id": seeded["aws"],
                "to_fact_id": azure["fact_id"],
                "relationship_type": "related",
                "evidence": {"source": "user_answer", "text": "AWS and Azure are related cloud platforms, not equivalent."},
            }),
        )
        self.assertEqual(related["status"], "ok", related)

        result = call_tool(
            adapter,
            "career.find_matches",
            {
                "requirements": [
                    {"requirement_id": "req_react", "source_text": "React", "normalized_terms": ["react"]},
                    {"requirement_id": "req_aws", "source_text": "AWS", "normalized_terms": ["aws"]},
                    {"requirement_id": "req_graphql", "source_text": "GraphQL", "normalized_terms": ["graphql"]},
                    {"requirement_id": "req_azure", "source_text": "Azure", "normalized_terms": ["azure"]},
                    {"requirement_id": "req_staff", "source_text": "Staff Engineer", "normalized_terms": ["staff engineer"]},
                ]
            },
        )
        self.assertEqual(result["status"], "ok")
        states = {match["requirement_id"]: match["resolution_state"] for match in result["matches"]}
        self.assertEqual(states["req_react"], "exact_match")
        self.assertEqual(states["req_aws"], "verified_fact_match")
        self.assertEqual(states["req_graphql"], "verified_fact_match")
        self.assertEqual(states["req_azure"], "related_match")
        self.assertEqual(states["req_staff"], "unknown")
        fact_ids = {match["requirement_id"]: match["fact_ids"] for match in result["matches"]}
        self.assertIn(seeded["aws"], fact_ids["req_aws"])
        self.assertIn(seeded["graphql"], fact_ids["req_graphql"])
        self.assertIn(seeded["aws"], fact_ids["req_azure"])
        self.assertTrue(set(states.values()) <= RESOLUTION_STATES)
        self.assertNotRegex(json.dumps(result).lower(), r"\b(official_score|overall_score)\b")

    def test_find_matches_collapses_store_weak_match_unresolved_overlap(self):
        class OverlappingWeakMatchStore(FakeCareerStore):
            def findCandidateMatches(self, requirements: list[dict], policy: dict):
                self.calls.append(("findCandidateMatches", {"requirements": requirements, "policy": policy}))
                return {
                    "status": "ok",
                    "matches": [
                        {
                            "requirement_id": "req_kubernetes",
                            "resolution_state": "possible_match",
                            "fact_ids": ["fact_candidate"],
                            "reasoning": "weak candidate retained",
                        }
                    ],
                    "unresolved": [
                        {
                            "requirement_id": "req_kubernetes",
                            "resolution_state": "possible_match",
                            "fact_ids": ["fact_candidate"],
                        }
                    ],
                }

        career_mcp = importlib.import_module("career_mcp")
        adapter = career_mcp.create_career_mcp(store=OverlappingWeakMatchStore())

        result = call_tool(
            adapter,
            "career.find_matches",
            {"requirements": [{"requirement_id": "req_kubernetes", "source_text": "Kubernetes", "normalized_terms": ["kubernetes"]}]},
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual([match["requirement_id"] for match in result["matches"]], ["req_kubernetes"])
        self.assertEqual(result["matches"][0]["resolution_state"], "possible_match")
        self.assertEqual(result["matches"][0]["fact_ids"], ["fact_candidate"])
        self.assertEqual(result["matches"][0]["reasoning"], "weak candidate retained")
        self.assertNotIn("No confirmed career fact matched", json.dumps(result))

    def test_find_matches_store_noncanonical_resolution_state_returns_store_error(self):
        class NonCanonicalResolutionStore(FakeCareerStore):
            def findCandidateMatches(self, requirements: list[dict], policy: dict):
                self.calls.append(("findCandidateMatches", {"requirements": requirements, "policy": policy}))
                return {
                    "status": "ok",
                    "matches": [
                        {
                            "requirement_id": "req_conflict",
                            "resolution_state": "conflicted",
                            "fact_ids": ["fact_candidate"],
                        }
                    ],
                    "unresolved": [],
                }

        career_mcp = importlib.import_module("career_mcp")
        adapter = career_mcp.create_career_mcp(store=NonCanonicalResolutionStore())

        result = call_tool(
            adapter,
            "career.find_matches",
            {"requirements": [{"requirement_id": "req_conflict", "source_text": "Conflict", "normalized_terms": ["conflict"]}]},
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["type"], "store_error")
        self.assertIn("conflicted", result["error"]["message"])
        self.assertNotEqual(result.get("data", {}).get("matches"), [{"resolution_state": "conflicted"}])

    def test_get_unverified_clearly_marks_unconfirmed_facts(self):
        result = call_tool(self.adapter, "career.get_unverified", {"topic": "architecture", "limit": 5})
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["facts"])
        self.assertIn("inferred", {fact["verification_state"] for fact in result["facts"]})
        for fact in result["facts"]:
            self.assertNotEqual(fact.get("verification_state"), "user_verified")
            self.assertTrue(fact.get("confirmation_required"))

    def test_get_unverified_confirmation_flag_comes_from_policy(self):
        career_mcp = importlib.import_module("career_mcp")
        original = career_mcp.policy.evaluate_policy

        def allow_without_confirmation(tool, arguments, confirmed):
            return career_mcp.policy.PolicyDecision(allowed=True, requires_confirmation=False)

        try:
            career_mcp.policy.evaluate_policy = allow_without_confirmation
            result = call_tool(self.adapter, "career.get_unverified", {"topic": "architecture", "limit": 5})
        finally:
            career_mcp.policy.evaluate_policy = original

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["facts"])
        self.assertTrue(all(fact["confirmation_required"] is False for fact in result["facts"]))


class CareerMcpAuditContractTests(unittest.TestCase):
    def test_call_tool_has_single_audit_emit_site(self):
        career_mcp = importlib.import_module("career_mcp")
        source = inspect.getsource(career_mcp.CareerMcpAdapter.call_tool)

        self.assertEqual(source.count("self._record_audit("), 1)

    def test_read_audit_events_keep_exact_two_key_shape_for_success_and_error(self):
        sink: list[dict] = []
        adapter = audited_adapter(sink=sink)

        ok = call_tool(adapter, "career.search_facts", {"query": "React", "limit": 1})
        error = call_tool(adapter, "career.get_fact", {"fact_id": "fact_missing"})

        self.assertEqual(ok["status"], "ok")
        self.assertEqual(error["status"], "error")
        self.assertEqual(sink, [
            {"tool": "career.search_facts", "status": "ok"},
            {"tool": "career.get_fact", "status": "error"},
        ])

    def test_successful_mutation_audit_event_has_exact_full_shape_without_error_type(self):
        sink: list[dict] = []
        adapter = audited_adapter(sink=sink)

        result = call_tool(
            adapter,
            "career.propose_fact",
            confirmed({"type": "skill", "text": "Rust", "source": "agent_interpretation"}),
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(sink), 1)
        event = sink[0]
        self.assertEqual(set(event), MUTATION_AUDIT_KEYS)
        self.assertEqual(event["operation_id"], FIXED_OPERATION_ID)
        self.assertEqual(event["timestamp"], FIXED_TIME)
        self.assertEqual(event["tool"], "career.propose_fact")
        self.assertTrue(event["is_mutation"])
        self.assertEqual(event["status"], "ok")
        self.assertEqual(event["affected_fact_ids"], [result["fact_id"]])
        self.assertEqual(event["resulting_verification_state"], result["verification_state"])
        self.assertFalse(event["conflict_flag"])
        self.assertTrue(event["confirmation_required"])
        self.assertEqual(json.loads(json.dumps(event)), event)

    def test_policy_rejected_mutation_emits_full_mutation_audit_event(self):
        sink: list[dict] = []
        adapter = audited_adapter(sink=sink)

        result = call_tool(
            adapter,
            "career.propose_fact",
            {"type": "skill", "text": "AWS experience", "source": "agent_interpretation"},
        )

        self.assertEqual(result["status"], "rejected")
        self.assertEqual(len(sink), 1)
        event = sink[0]
        self.assertEqual(set(event), MUTATION_AUDIT_KEYS | {"error_type"})
        self.assertEqual(event["tool"], "career.propose_fact")
        self.assertTrue(event["is_mutation"])
        self.assertEqual(event["status"], "rejected")
        self.assertEqual(event["affected_fact_ids"], [])
        self.assertEqual(event["error_type"], "policy_error")
        self.assertTrue(event["confirmation_required"])
        self.assertEqual(event["resulting_verification_state"], "unknown")
        self.assertEqual(json.loads(json.dumps(event)), event)

    def test_validation_error_mutation_emits_full_mutation_audit_event(self):
        sink: list[dict] = []
        adapter = audited_adapter(sink=sink)

        result = call_tool(
            adapter,
            "career.add_relationship",
            {"from_fact_id": "fact_aws", "to_fact_id": "fact_azure", "relationship_type": "sibling"},
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(len(sink), 1)
        event = sink[0]
        self.assertEqual(set(event), MUTATION_AUDIT_KEYS | {"error_type"})
        self.assertEqual(event["tool"], "career.add_relationship")
        self.assertTrue(event["is_mutation"])
        self.assertEqual(event["affected_fact_ids"], [])
        self.assertEqual(event["error_type"], "validation_error")
        self.assertTrue(event["confirmation_required"])

    def test_store_error_mutation_emits_full_event_without_persistence_details(self):
        class RaisingStore(FakeCareerStore):
            def upsertFact(self, fact: dict, evidence=None, source=None, policy=None, dedupe_key=None):
                self.calls.append(("upsertFact", {"fact": fact, "evidence": evidence, "source": source, "policy": policy}))
                raise RuntimeError("UNIQUE constraint failed: facts.fact_id")

        sink: list[dict] = []
        adapter = audited_adapter(store=RaisingStore(), sink=sink)

        result = call_tool(
            adapter,
            "career.propose_fact",
            confirmed({"type": "skill", "text": "Rust", "source": "agent_interpretation"}),
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["message"], "Career store operation failed.")
        event = sink[0]
        self.assertEqual(set(event), MUTATION_AUDIT_KEYS | {"error_type"})
        self.assertEqual(event["error_type"], "store_error")
        serialized = json.dumps(event, sort_keys=True).lower()
        self.assertNotRegex(serialized, r"\b(sqlite|select|insert|update|delete|traceback|constraint|facts\.fact_id)\b")

    def test_mutating_tool_audit_metadata_is_fed_from_result_envelope(self):
        cases = [
            (
                "career.propose_fact",
                confirmed({"type": "skill", "text": "Rust", "source": "agent_interpretation"}),
                None,
            ),
            (
                "career.add_evidence",
                confirmed({"fact_id": "fact_aws", "evidence": {"source": "user_answer", "text": "AWS evidence"}}),
                None,
            ),
            (
                "career.verify_fact",
                confirmed({
                    "fact_id": "fact_aws",
                    "verification_state": "user_verified",
                    "confirmation": {
                        "factId": "fact_aws",
                        "outcome": "affirmed",
                        "provenance": [{"source": "user_answer", "text": "Yes, six years."}],
                    },
                }),
                None,
            ),
            (
                "career.add_relationship",
                confirmed({"from_fact_id": "fact_aws", "to_fact_id": "fact_azure", "relationship_type": "related"}),
                ["fact_aws", "fact_azure"],
            ),
        ]

        for tool, arguments, expected_ids in cases:
            with self.subTest(tool=tool):
                sink: list[dict] = []
                adapter = audited_adapter(sink=sink)

                result = call_tool(adapter, tool, arguments)

                self.assertEqual(result["status"], "ok", result)
                self.assertEqual(len(sink), 1)
                event = sink[0]
                self.assertEqual(event["affected_fact_ids"], expected_ids or result["affected_fact_ids"])
                self.assertEqual(event["resulting_verification_state"], result["verification_state"])
                self.assertEqual(event["conflict_flag"], bool(result["conflicts"]))
                self.assertEqual(event["confirmation_required"], result["confirmation_required"])

    def test_audit_redaction_strips_sensitive_argument_values_and_keeps_benign_message(self):
        sink: list[dict] = []
        adapter = audited_adapter(sink=sink)
        secret = "planted-secret-value-0108"
        benign = "benign plain message survives verbatim"

        result = call_tool(
            adapter,
            "career.propose_fact",
            confirmed({
                "type": "skill",
                "text": "Rust",
                "source": "agent_interpretation",
                "evidence": {
                    "source": "user_answer",
                    "text": benign,
                    "contact_data": secret,
                    "raw_sql": f"select * from facts where secret = '{secret}'",
                },
            }),
        )

        self.assertEqual(result["status"], "ok")
        serialized = json.dumps(sink[0], sort_keys=True)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("contact_data", serialized)
        self.assertNotIn("raw_sql", serialized)
        self.assertIn(benign, serialized)

    def test_audit_events_are_json_round_trippable_and_omit_store_internal_identifiers(self):
        sink: list[dict] = []
        adapter = audited_adapter(sink=sink)

        call_tool(
            adapter,
            "career.propose_fact",
            confirmed({
                "type": "skill",
                "text": "Rust",
                "source": "agent_interpretation",
                "evidence": {
                    "source": "user_answer",
                    "text": "plain evidence",
                    "transaction_result": {"raw_sql": "select * from facts"},
                },
            }),
        )

        event = sink[0]
        self.assertEqual(json.loads(json.dumps(event)), event)
        serialized = json.dumps(event, sort_keys=True).lower()
        for token in STORE_INTERNAL_AUDIT_TOKENS:
            with self.subTest(token=token):
                self.assertNotIn(token, serialized)

    def test_audit_mutation_flag_reuses_policy_manifest_classification(self):
        career_mcp = importlib.import_module("career_mcp")
        policy_module = importlib.import_module("career_mcp.policy")

        for tool in SURFACE["tools"]:
            with self.subTest(tool=tool["name"]):
                result = {"tool": tool["name"], "status": "ok"}
                event = career_mcp.audit.build_audit_event(
                    tool=tool["name"],
                    result=result,
                    arguments={},
                    operation_id=FIXED_OPERATION_ID,
                    timestamp=FIXED_TIME,
                    policy_decision=None,
                )
                self.assertEqual("is_mutation" in event, policy_module.tool_mutates(tool["name"]))

    def test_jsonl_audit_sink_is_callable_append_only_jsonl(self):
        career_mcp = importlib.import_module("career_mcp")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit" / "events.jsonl"
            sink = career_mcp.audit.JsonlAuditSink(path)

            sink({"tool": "career.search_facts", "status": "ok"})
            sink({"tool": "career.get_fact", "status": "error"})

            self.assertTrue(callable(sink))
            self.assertEqual(
                [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()],
                [
                    {"tool": "career.search_facts", "status": "ok"},
                    {"tool": "career.get_fact", "status": "error"},
                ],
            )


class CareerMcpRealStoreContractTests(unittest.TestCase):
    def test_real_store_search_facts_types_experience_excludes_skill_facts(self):
        store, adapter = real_store_adapter(self)
        skill = store.upsertFact(
            {"type": "skill", "text": "AWS skill capability", "verification_state": "source_stated"},
            {"source": "resume_source", "source_id": "resume_1", "text": "AWS skill capability"},
            source="resume_source",
        )
        experience = store.upsertFact(
            {"type": "experience", "text": "AWS migration experience", "verification_state": "source_stated"},
            {"source": "resume_source", "source_id": "resume_1", "text": "AWS migration experience"},
            source="resume_source",
        )

        result = call_tool(adapter, "career.search_facts", {"query": "AWS", "types": ["experience"], "limit": 10})

        self.assertEqual(result["status"], "ok")
        self.assertEqual({fact["fact_id"] for fact in result["facts"]}, {experience["fact_id"]})
        self.assertNotIn(skill["fact_id"], {fact["fact_id"] for fact in result["facts"]})
        self.assertTrue(all(fact["type"] == "experience" for fact in result["facts"]))

    def test_real_store_search_facts_verification_filter_excludes_nonmatching_facts(self):
        store, adapter = real_store_adapter(self)
        unknown = store.upsertFact(
            {"type": "skill", "text": "Terraform automation", "verification_state": "unknown"},
            None,
            source="resume_source",
        )
        source_stated = store.upsertFact(
            {"type": "skill", "text": "Terraform modules", "verification_state": "source_stated"},
            {"source": "resume_source", "source_id": "resume_1", "text": "Terraform modules"},
            source="resume_source",
        )

        result = call_tool(adapter, "career.search_facts", {"query": "Terraform", "verification": ["source_stated"], "limit": 10})

        self.assertEqual(result["status"], "ok")
        self.assertEqual({fact["fact_id"] for fact in result["facts"]}, {source_stated["fact_id"]})
        self.assertNotIn(unknown["fact_id"], {fact["fact_id"] for fact in result["facts"]})

    def test_real_store_get_fact_ok_path_returns_context(self):
        store, adapter = real_store_adapter(self)
        created = store.upsertFact(
            {"type": "skill", "text": "React", "verification_state": "source_stated"},
            {"source": "resume_source", "source_id": "resume_1", "text": "React"},
            source="resume_source",
        )

        result = call_tool(adapter, "career.get_fact", {"fact_id": created["fact_id"]})

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["fact"]["fact_id"], created["fact_id"])
        self.assertIn("evidence_summary", result)
        self.assertIn("relationships", result)
        self.assertIn("conflicts", result)

    def test_real_store_propose_fact_ok_path_and_dedupe_key_rejection(self):
        _store, adapter = real_store_adapter(self)

        created = call_tool(
            adapter,
            "career.propose_fact",
            confirmed({"type": "skill", "text": "Rust", "source": "agent_interpretation"}),
        )
        rejected = call_tool(
            adapter,
            "career.propose_fact",
            confirmed({
                "type": "skill",
                "text": "Rust",
                "source": "agent_interpretation",
                "dedupe_key": "proposal:rust",
            }),
        )

        self.assertEqual(created["status"], "ok")
        self.assertIn(created["mutation_status"], {"created", "updated", "deduped", "noop"})
        self.assertNotEqual(created["verification_state"], "user_verified")
        assert_typed_error(self, rejected, "validation_error")
        self.assertIn("dedupe_key", rejected["error"]["message"])

    def test_real_store_add_evidence_ok_path_and_missing_fact_rejection(self):
        store, adapter = real_store_adapter(self)
        created = store.upsertFact(
            {"type": "skill", "text": "PostgreSQL", "verification_state": "unknown"},
            None,
            source="resume_source",
        )

        added = call_tool(
            adapter,
            "career.add_evidence",
            confirmed({"fact_id": created["fact_id"], "evidence": {"source": "user_answer", "text": "I use PostgreSQL."}}),
        )
        missing = call_tool(
            adapter,
            "career.add_evidence",
            confirmed({"fact_id": "fact_missing", "evidence": {"source": "user_answer", "text": "Missing fact."}}),
        )

        self.assertEqual(added["status"], "ok")
        self.assertIn(added["mutation_status"], {"created", "updated"})
        assert_typed_error(self, missing, "not_found")

    def test_real_store_verify_fact_imported_end_to_end_through_mcp(self):
        store, adapter = real_store_adapter(self)
        created = store.upsertFact(
            {"type": "skill", "text": "Go", "verification_state": "unknown"},
            None,
            source="resume_source",
        )

        result = call_tool(
            adapter,
            "career.verify_fact",
            confirmed({
                "fact_id": created["fact_id"],
                "verification_state": "imported",
                "confirmation": confirmation_for_state(created["fact_id"], "imported"),
            }),
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["verification_state"], "imported")
        self.assertEqual(store.getFact(created["fact_id"])["fact"]["verification_state"], "imported")

    def test_real_store_manifest_advertised_verification_states_are_accepted_through_mcp(self):
        for verification_state in sorted(VERIFICATION_STATES):
            with self.subTest(verification_state=verification_state):
                store, adapter = real_store_adapter(self)
                created = store.upsertFact(
                    {"type": "skill", "text": f"{verification_state} proof", "verification_state": "unknown"},
                    None,
                    source="resume_source",
                )
                arguments = {
                    "fact_id": created["fact_id"],
                    "verification_state": verification_state,
                    "confirmation": confirmation_for_state(created["fact_id"], verification_state),
                    "confirmed": True,
                }
                if verification_state == "source_stated":
                    arguments["evidence_id"] = f"evidence_{verification_state}"

                result = call_tool(adapter, "career.verify_fact", arguments)

                self.assertEqual(result["status"], "ok", result)
                self.assertNotEqual(result.get("error", {}).get("message"), "invalid verification state")

    def test_real_store_verify_fact_rejection_has_typed_envelope(self):
        store, adapter = real_store_adapter(self)
        created = store.upsertFact(
            {"type": "skill", "text": "PostgreSQL", "verification_state": "unknown"},
            None,
            source="resume_source",
        )
        confirmation = confirmation_for_state(created["fact_id"], "source_stated")

        result = call_tool(
            adapter,
            "career.verify_fact",
            confirmed({
                "fact_id": created["fact_id"],
                "verification_state": "source_stated",
                "confirmation": confirmation,
            }),
        )

        assert_typed_error(self, result, "validation_error")
        self.assertIn("evidence_id", result["error"]["message"])

    def test_real_store_add_relationship_ok_path_and_missing_fact_rejection(self):
        store, adapter = real_store_adapter(self)
        frontend = store.upsertFact(
            {"type": "skill", "text": "Frontend architecture", "verification_state": "source_stated"},
            {"source": "resume_source", "source_id": "resume_1", "text": "Frontend architecture"},
            source="resume_source",
        )
        react = store.upsertFact(
            {"type": "skill", "text": "React", "verification_state": "source_stated"},
            {"source": "resume_source", "source_id": "resume_1", "text": "React"},
            source="resume_source",
        )

        created = call_tool(
            adapter,
            "career.add_relationship",
            confirmed({
                "from_fact_id": frontend["fact_id"],
                "to_fact_id": react["fact_id"],
                "relationship_type": "related",
                "evidence": {"text": "React supports frontend architecture."},
            }),
        )
        missing = call_tool(
            adapter,
            "career.add_relationship",
            confirmed({
                "from_fact_id": "fact_missing",
                "to_fact_id": react["fact_id"],
                "relationship_type": "related",
                "evidence": {"text": "Missing source fact."},
            }),
        )

        self.assertEqual(created["status"], "ok")
        self.assertIn(created["mutation_status"], {"created", "updated"})
        assert_typed_error(self, missing, "not_found")

    def test_real_store_find_matches_ok_path_returns_canonical_resolution(self):
        store, adapter = real_store_adapter(self)
        created = store.upsertFact(
            {"type": "skill", "text": "React", "normalized_terms": ["react"], "verification_state": "source_stated"},
            {"source": "resume_source", "source_id": "resume_1", "text": "React"},
            source="resume_source",
        )

        result = call_tool(
            adapter,
            "career.find_matches",
            {"requirements": [{"requirement_id": "req_react", "source_text": "React", "normalized_terms": ["react"]}]},
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual([match["requirement_id"] for match in result["matches"]], ["req_react"])
        self.assertIn(created["fact_id"], result["matches"][0]["fact_ids"])
        self.assertIn(result["matches"][0]["resolution_state"], RESOLUTION_STATES)
        self.assertNotRegex(json.dumps(result).lower(), r"\b(official_score|overall_score)\b")

    def test_real_store_get_unverified_ok_path_marks_unknown_fact_for_confirmation(self):
        store, adapter = real_store_adapter(self)
        created = store.upsertFact(
            {"type": "experience", "text": "Architecture review work", "verification_state": "unknown"},
            None,
            source="resume_source",
        )

        result = call_tool(adapter, "career.get_unverified", {"topic": "architecture", "limit": 5})

        self.assertEqual(result["status"], "ok")
        self.assertIn(created["fact_id"], {fact["fact_id"] for fact in result["facts"]})
        self.assertTrue(all(fact["confirmation_required"] for fact in result["facts"]))

    def test_real_store_get_unverified_returns_inferred_facts(self):
        store, adapter = real_store_adapter(self)
        created = store.upsertFact(
            {"type": "experience", "text": "Inferred Kubernetes operations", "verification_state": "unknown"},
            None,
            source="resume_source",
        )
        store.verifyFact(
            created["fact_id"],
            "inferred",
            confirmation_for_state(created["fact_id"], "inferred"),
            source="agent_interpretation",
        )

        result = call_tool(adapter, "career.get_unverified", {"topic": "Kubernetes", "limit": 5})

        self.assertEqual(result["status"], "ok")
        self.assertIn(created["fact_id"], {fact["fact_id"] for fact in result["facts"]})
        self.assertIn("inferred", {fact["verification_state"] for fact in result["facts"]})


class CareerMcpErrorEnvelopeTests(unittest.TestCase):
    def test_envelope_helper_refuses_non_ok_without_error_object(self):
        career_mcp = importlib.import_module("career_mcp")
        with self.assertRaisesRegex(ValueError, "require an error object"):
            career_mcp._tool_result("career.get_fact", "error")  # noqa: SLF001

    def test_raw_sql_fragment_in_envelope_message_is_redacted_without_touching_type_or_data(self):
        career_mcp = importlib.import_module("career_mcp")
        leaked = "INSERT INTO facts (fact_id, text) VALUES ('fact_1', 'secret')"

        result = career_mcp._tool_result(  # noqa: SLF001
            "career.get_fact",
            "error",
            data={"store_diagnostic": leaked},
            error={"type": "store_error", "message": leaked},
        )

        self.assertEqual(result["error"]["type"], "store_error")
        self.assertEqual(result["error"]["message"], "Career store operation failed.")
        self.assertEqual(result["data"]["store_diagnostic"], leaked)

    def test_validation_message_with_plain_update_survives_scrub_verbatim(self):
        career_mcp = importlib.import_module("career_mcp")
        message = "cannot update verification state without evidence"

        result = career_mcp._tool_result(  # noqa: SLF001
            "career.verify_fact",
            "error",
            error={"type": "validation_error", "message": message},
        )

        self.assertEqual(result["error"]["type"], "validation_error")
        self.assertEqual(result["error"]["message"], message)

    def test_sqlite_error_signature_in_envelope_message_is_redacted(self):
        career_mcp = importlib.import_module("career_mcp")

        result = career_mcp._tool_result(  # noqa: SLF001
            "career.get_fact",
            "error",
            error={"type": "store_error", "message": "UNIQUE constraint failed: facts.fact_id"},
        )

        self.assertEqual(result["error"]["message"], "Career store operation failed.")

    def test_exception_classification_is_independent_of_message_wording(self):
        career_mcp = importlib.import_module("career_mcp")
        self.assertEqual(career_mcp._exception_type(ValueError("not found")), "validation_error")  # noqa: SLF001
        self.assertEqual(career_mcp._exception_type(ValueError("confirmation required")), "validation_error")  # noqa: SLF001

    def test_real_store_verify_fact_rejected_dict_has_typed_error_envelope(self):
        career_mcp = importlib.import_module("career_mcp")
        career_store = importlib.import_module("career_store")
        with tempfile.TemporaryDirectory() as temp_dir:
            store = career_store.openCareerStore(str(Path(temp_dir) / "career.db"), clock=lambda: "2026-01-01T00:00:00Z")
            created = store.upsertFact(
                {"type": "skill", "text": "Rust", "verification_state": "unknown"},
                None,
                source="resume_source",
            )
            adapter = career_mcp.create_career_mcp(store=store)

            result = call_tool(
                adapter,
                "career.verify_fact",
                confirmed({
                    "fact_id": created["fact_id"],
                    "verification_state": "imported",
                    "confirmation": {
                        "factId": created["fact_id"],
                        "outcome": "affirmed",
                        "provenance": [{"source": "user_answer", "text": "Yes."}],
                    },
                }),
            )

        self.assertEqual(result["tool"], "career.verify_fact")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["data"]["mutation_status"], "rejected")
        self.assertEqual(result["error"]["type"], "policy_error")
        self.assertIn("message", result["error"])

    def test_real_store_full_list_filters_post_filter_without_silent_narrowing(self):
        career_mcp = importlib.import_module("career_mcp")
        career_store = importlib.import_module("career_store")
        with tempfile.TemporaryDirectory() as temp_dir:
            store = career_store.openCareerStore(str(Path(temp_dir) / "career.db"), clock=lambda: "2026-01-01T00:00:00Z")
            source_stated = store.upsertFact(
                {"type": "skill", "text": "AWS source stated", "verification_state": "source_stated"},
                {"source": "resume_source", "source_id": "resume-1", "text": "AWS source stated"},
                source="resume_source",
            )
            user_fact = store.upsertFact(
                {"type": "experience", "text": "AWS user verified", "verification_state": "unknown"},
                None,
                source="resume_source",
            )
            store.verifyFact(
                user_fact["fact_id"],
                "user_verified",
                {
                    "factId": user_fact["fact_id"],
                    "outcome": "affirmed",
                    "provenance": [{"source": "user_answer", "text": "Yes, AWS user verified."}],
                },
                source="user_answer",
            )
            adapter = career_mcp.create_career_mcp(store=store)

            result = call_tool(
                adapter,
                "career.search_facts",
                {
                    "query": "AWS",
                    "verification": ["user_verified", "source_stated"],
                    "types": ["skill", "experience"],
                    "limit": 10,
                },
            )

        self.assertEqual(result["status"], "ok")
        self.assertEqual({fact["fact_id"] for fact in result["facts"]}, {source_stated["fact_id"], user_fact["fact_id"]})
        self.assertEqual({fact["verification_state"] for fact in result["facts"]}, {"source_stated", "user_verified"})

    def test_real_store_dedupe_key_is_typed_rejected_when_upsert_fact_cannot_honor_it(self):
        career_mcp = importlib.import_module("career_mcp")
        career_store = importlib.import_module("career_store")
        with tempfile.TemporaryDirectory() as temp_dir:
            store = career_store.openCareerStore(str(Path(temp_dir) / "career.db"), clock=lambda: "2026-01-01T00:00:00Z")
            adapter = career_mcp.create_career_mcp(store=store)

            result = call_tool(
                adapter,
                "career.propose_fact",
                confirmed({
                    "type": "skill",
                    "text": "Rust",
                    "source": "agent_interpretation",
                    "dedupe_key": "proposal:rust",
                }),
            )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["type"], "validation_error")
        self.assertIn("dedupe_key", result["error"]["message"])

    def test_real_store_get_fact_include_conflicts_observably_controls_conflict_records(self):
        career_mcp = importlib.import_module("career_mcp")
        career_store = importlib.import_module("career_store")
        with tempfile.TemporaryDirectory() as temp_dir:
            store = career_store.openCareerStore(str(Path(temp_dir) / "career.db"), clock=lambda: "2026-01-01T00:00:00Z")
            six = store.upsertFact(
                {"type": "skill", "text": "AWS, six years", "verification_state": "unknown"},
                None,
                source="resume_source",
            )
            ten = store.upsertFact(
                {"type": "skill", "text": "AWS, ten years", "verification_state": "unknown"},
                None,
                source="resume_source",
            )
            self.assertTrue(ten["conflicts"])
            adapter = career_mcp.create_career_mcp(store=store)

            without_conflicts = call_tool(adapter, "career.get_fact", {"fact_id": six["fact_id"], "include_conflicts": False})
            with_conflicts = call_tool(adapter, "career.get_fact", {"fact_id": six["fact_id"], "include_conflicts": True})

        self.assertEqual(without_conflicts["status"], "ok")
        self.assertEqual(without_conflicts["conflicts"], [])
        self.assertEqual(with_conflicts["status"], "ok")
        self.assertTrue(with_conflicts["conflicts"])

    def test_real_store_verify_fact_requires_and_forwards_evidence_id_for_source_document_state(self):
        career_mcp = importlib.import_module("career_mcp")
        career_store = importlib.import_module("career_store")
        with tempfile.TemporaryDirectory() as temp_dir:
            store = career_store.openCareerStore(str(Path(temp_dir) / "career.db"), clock=lambda: "2026-01-01T00:00:00Z")
            created = store.upsertFact(
                {"type": "skill", "text": "PostgreSQL", "verification_state": "unknown"},
                None,
                source="resume_source",
            )
            adapter = career_mcp.create_career_mcp(store=store)
            confirmation = {
                "factId": created["fact_id"],
                "outcome": "affirmed",
                "provenance": [{"source": "resume_source", "text": "PostgreSQL"}],
            }

            missing = call_tool(
                adapter,
                "career.verify_fact",
                confirmed({
                    "fact_id": created["fact_id"],
                    "verification_state": "source_stated",
                    "confirmation": confirmation,
                }),
            )
            verified = call_tool(
                adapter,
                "career.verify_fact",
                confirmed({
                    "fact_id": created["fact_id"],
                    "verification_state": "source_stated",
                    "confirmation": confirmation,
                    "evidence_id": "evidence_resume_pg",
                }),
            )
            fetched = store.getFact(created["fact_id"])

        self.assertEqual(missing["status"], "error")
        self.assertEqual(missing["error"]["type"], "validation_error")
        self.assertIn("evidence_id", missing["error"]["message"])
        self.assertEqual(verified["status"], "ok")
        self.assertEqual(verified["verification_state"], "source_stated")
        self.assertTrue(any(item.get("source_id") == "evidence_resume_pg" for item in fetched["evidence"]))


class CareerMcpNoRawToolTests(unittest.TestCase):
    def setUp(self):
        self.adapter = load_adapter(self)

    def test_raw_sql_style_tool_calls_are_not_exposed(self):
        for forbidden in FORBIDDEN_TOOLS:
            with self.subTest(tool=forbidden):
                result = call_tool(self.adapter, forbidden, {"sql": "select * from facts"})
                if isinstance(result, dict):
                    self.assertEqual(result["status"], "error")
                    self.assertIn(result["error"]["type"], {"unknown_tool", "not_found", "validation_error"})
                    self.assertNotRegex(json.dumps(result).lower(), r"\bselect \*|sqlite|traceback\b")



if __name__ == "__main__":
    unittest.main()
