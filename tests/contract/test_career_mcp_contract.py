"""Contract-first tests for the future career_mcp package."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import re
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
        }

    def search_facts(self, **kwargs):
        self.calls.append(("search_facts", kwargs))
        query = kwargs["query"].lower()
        matches = [fact for fact in self.facts.values() if query in fact["text"].lower()]
        return sorted(matches, key=lambda fact: fact["fact_id"])

    def get_fact(self, fact_id: str, **kwargs):
        self.calls.append(("get_fact", {"fact_id": fact_id, **kwargs}))
        return self.facts.get(fact_id)

    def propose_fact(self, **kwargs):
        self.calls.append(("propose_fact", kwargs))
        fact_id = "fact_aws" if "aws" in kwargs["text"].lower() else "fact_candidate"
        return {
            "mutation_status": "deduped" if fact_id in self.facts else "created",
            "fact_id": fact_id,
            "verification_state": "unknown",
            "conflicts": [],
            "confirmation_required": True,
            "audit": {"operation": "propose_fact"},
        }

    def add_evidence(self, **kwargs):
        self.calls.append(("add_evidence", kwargs))
        return {
            "mutation_status": "updated",
            "fact_id": kwargs["fact_id"],
            "verification_state": self.facts[kwargs["fact_id"]]["verification_state"],
            "conflicts": [],
            "confirmation_required": True,
            "audit": {"operation": "add_evidence"},
        }

    def verify_fact(self, **kwargs):
        self.calls.append(("verify_fact", kwargs))
        confirmation = kwargs.get("confirmation")
        if kwargs["verification_state"] == "user_verified" and (
            not isinstance(confirmation, dict)
            or confirmation.get("outcome") != "affirmed"
            or not confirmation.get("provenance")
        ):
            raise ValueError("affirmed interpretation proposal required")
        return {
            "mutation_status": "updated",
            "fact_id": kwargs["fact_id"],
            "verification_state": kwargs["verification_state"],
            "conflicts": [],
            "confirmation_required": False,
            "audit": {"operation": "verify_fact"},
        }

    def add_relationship(self, **kwargs):
        self.calls.append(("add_relationship", kwargs))
        if kwargs["relationship_type"] not in RELATIONSHIP_TYPES:
            raise ValueError("unsupported relationship type")
        return {
            "mutation_status": "created",
            "fact_id": kwargs["from_fact_id"],
            "verification_state": "unknown",
            "conflicts": [],
            "confirmation_required": kwargs["relationship_type"] in {"alias", "equivalent"},
            "audit": {"operation": "add_relationship"},
        }

    def find_matches(self, **kwargs):
        self.calls.append(("find_matches", kwargs))
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
            for req in kwargs["requirements"]
        ]

    def get_unverified(self, **kwargs):
        self.calls.append(("get_unverified", kwargs))
        return [
            {
                "fact_id": "fact_candidate",
                "text": "candidate architecture experience",
                "verification_state": "unknown",
                "confirmation_required": True,
            }
        ]


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
