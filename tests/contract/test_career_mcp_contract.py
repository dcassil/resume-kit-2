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


ROOT = Path(__file__).resolve().parents[2]
SURFACE = json.loads((ROOT / "career-mcp" / "career_mcp" / "tool_surface.json").read_text(encoding="utf-8"))

ALLOWED_TOOLS = tuple(tool["name"] for tool in SURFACE["tools"])
WRITE_TOOLS = tuple(tool["name"] for tool in SURFACE["tools"] if tool.get("mutates") is True)
FORBIDDEN_TOOLS = tuple(SURFACE["forbidden_tools"])
VERIFICATION_STATES = set(SURFACE["verification_states"])
RELATIONSHIP_TYPES = set(SURFACE["relationship_types"])
RESOLUTION_STATES = set(SURFACE["resolution_states"])


class FakeCareerStore:
    """Small deterministic store double that future MCP code should call."""

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
        if verification_state == "user_verified" and (
            not isinstance(confirmation, dict)
            or confirmation.get("outcome") != "affirmed"
            or not confirmation.get("provenance")
        ):
            raise ValueError("affirmed interpretation proposal required")
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
        if relationship_type not in RELATIONSHIP_TYPES:
            raise ValueError("unsupported relationship type")
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
        states = {
            "req_react": ("exact_match", ["fact_react"]),
            "req_api": ("verified_fact_match", ["fact_api"]),
            "req_responsive": ("alias_match", ["fact_responsive"]),
            "req_aws": ("verified_fact_match", ["fact_aws"]),
            "req_graphql": ("verified_fact_match", ["fact_graphql"]),
            "req_azure": ("related_match", ["fact_aws"]),
            "req_staff": ("unknown", []),
        }
        return [
            {
                "requirement_id": req["requirement_id"],
                "resolution_state": states.get(req["requirement_id"], ("possible_match", []))[0],
                "fact_ids": states.get(req["requirement_id"], ("possible_match", []))[1],
                "reasoning": "classified by career-store fact graph",
            }
            for req in requirements
        ]
        return {"matches": matches, "unresolved": []}

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
    test_case.assertTrue(callable(getattr(adapter, "call_tool", None)), "Adapter must expose call_tool(name, arguments, context=None).")
    return adapter


def maybe_await(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def call_tool(adapter, name: str, arguments: dict):
    return maybe_await(adapter.call_tool(name, arguments))


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

    def test_child_parent_relationship_types_fail_at_schema_validation(self):
        for relationship_type in ("child", "parent"):
            with self.subTest(relationship_type=relationship_type):
                result = call_tool(
                    self.adapter,
                    "career.add_relationship",
                    {
                        "from_fact_id": "fact_aws",
                        "to_fact_id": "fact_azure",
                        "relationship_type": relationship_type,
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
            {
                "type": "skill",
                "text": "AWS experience",
                "source": "agent_interpretation",
                "dedupe_key": "proposal:aws",
            },
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(self.adapter._store.calls[-1][0], "upsertFact")  # noqa: SLF001
        self.assertEqual(self.adapter._store.calls[-1][1]["dedupe_key"], "proposal:aws")  # noqa: SLF001

    def test_propose_fact_never_marks_agent_interpretation_user_verified(self):
        result = call_tool(
            self.adapter,
            "career.propose_fact",
            {"type": "skill", "text": "AWS experience", "source": "agent_interpretation"},
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
            {"fact_id": "fact_aws", "evidence": {"source": "user_answer", "text": "about six years of AWS experience"}},
        )
        self.assertEqual(evidence["mutation_status"], "updated")
        self.assertIn(evidence["verification_state"], VERIFICATION_STATES)

        verified = call_tool(
            self.adapter,
            "career.verify_fact",
            {
                "fact_id": "fact_aws",
                "verification_state": "user_verified",
                "confirmation": {
                    "factId": "fact_aws",
                    "outcome": "affirmed",
                    "provenance": [{"source": "user_answer", "text": "Yes, about six years of AWS experience."}],
                },
            },
        )
        self.assertEqual(verified["verification_state"], "user_verified")
        self.assertFalse(verified["confirmation_required"])

    def test_consumed_arguments_assertion_catches_planted_dropped_argument(self):
        career_mcp = importlib.import_module("career_mcp")
        original = career_mcp.TOOL_ARGUMENTS["career.search_facts"]
        career_mcp.TOOL_ARGUMENTS["career.search_facts"] = original - {"limit"}
        try:
            with self.assertRaisesRegex(AssertionError, "validated arguments that dispatch does not consume: limit"):
                call_tool(self.adapter, "career.search_facts", {"query": "React", "limit": 1})
        finally:
            career_mcp.TOOL_ARGUMENTS["career.search_facts"] = original

    def test_relationship_creation_preserves_related_vs_equivalent_distinction(self):
        responsive = call_tool(
            self.adapter,
            "career.add_relationship",
            {"from_fact_id": "fact_responsive", "to_fact_id": "fact_responsive_design", "relationship_type": "alias"},
        )
        self.assertEqual(responsive["mutation_status"], "created")

        azure_aws = call_tool(
            self.adapter,
            "career.add_relationship",
            {"from_fact_id": "fact_azure", "to_fact_id": "fact_aws", "relationship_type": "related"},
        )
        self.assertEqual(azure_aws["mutation_status"], "created")
        self.assertNotEqual(azure_aws.get("relationship_type"), "equivalent")

    def test_find_matches_returns_resolution_states_without_official_scores(self):
        result = call_tool(
            self.adapter,
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
        self.assertTrue(set(states.values()) <= RESOLUTION_STATES)
        self.assertNotRegex(json.dumps(result).lower(), r"\b(official_score|overall_score)\b")

    def test_get_unverified_clearly_marks_unconfirmed_facts(self):
        result = call_tool(self.adapter, "career.get_unverified", {"topic": "architecture", "limit": 5})
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["facts"])
        for fact in result["facts"]:
            self.assertNotEqual(fact.get("verification_state"), "user_verified")
            self.assertTrue(fact.get("confirmation_required"))


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
                {
                    "fact_id": created["fact_id"],
                    "verification_state": "imported",
                    "confirmation": {
                        "factId": created["fact_id"],
                        "outcome": "affirmed",
                        "provenance": [{"source": "user_answer", "text": "Yes."}],
                    },
                },
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
                {
                    "type": "skill",
                    "text": "Rust",
                    "source": "agent_interpretation",
                    "dedupe_key": "proposal:rust",
                },
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
                {
                    "fact_id": created["fact_id"],
                    "verification_state": "source_stated",
                    "confirmation": confirmation,
                },
            )
            verified = call_tool(
                adapter,
                "career.verify_fact",
                {
                    "fact_id": created["fact_id"],
                    "verification_state": "source_stated",
                    "confirmation": confirmation,
                    "evidence_id": "evidence_resume_pg",
                },
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


# Bridge the career-mcp manifest parity tests into the current static PR/future
# gate module list until tools/run_tests.py is approved to include it directly.
from tests.contract.test_career_mcp_manifest_parity import CareerMcpManifestParityTests  # noqa: E402,F401


if __name__ == "__main__":
    unittest.main()
