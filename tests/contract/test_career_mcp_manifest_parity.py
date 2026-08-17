"""Manifest/runtime parity tests for career-mcp."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import json
import re
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_SURFACE_PATH = ROOT / "career-mcp" / "career_mcp" / "tool_surface.json"
GENERATED_SURFACE_PATH = ROOT / "career-mcp" / "tool_surface.json"
STORE_SURFACE_PATH = ROOT / "career-store" / "store_surface.json"
CAREER_MCP_CONTRACT_TEST_PATH = ROOT / "tests" / "contract" / "test_career_mcp_contract.py"
SYNC_TOOL_PATH = "career-mcp/tools/sync_tool_surface.py"
POLICY_VOCABULARY_BLOCKLIST = frozenset({"scope", "principal", "role", "authorization"})

JsonObject = dict[str, Any]


def load_json(path: Path) -> JsonObject:
    return json.loads(path.read_text(encoding="utf-8"))


def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        import asyncio

        return asyncio.run(value)
    return value


def manifest_tools_by_name(surface: JsonObject) -> dict[str, JsonObject]:
    tools = surface.get("tools", [])
    return {tool.get("name"): tool for tool in tools if isinstance(tool, dict)}


def declared_policy_gated_tools(surface: JsonObject) -> set[str]:
    policy = surface.get("policy", {})
    gated_tools = policy.get("gated_tools", [])
    return {tool for tool in gated_tools if isinstance(tool, str)}


def runtime_policy_gated_tools() -> set[str]:
    career_mcp_policy = importlib.import_module("career_mcp.policy")
    mutation_map = career_mcp_policy._tool_mutation_map()  # noqa: SLF001 - contract test for policy classification.
    return {name for name, mutates in mutation_map.items() if mutates}


def fake_career_store_class() -> Any:
    spec = importlib.util.spec_from_file_location("career_mcp_contract_helpers", CAREER_MCP_CONTRACT_TEST_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Unable to load contract helpers from {CAREER_MCP_CONTRACT_TEST_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FakeCareerStore


def runtime_tools() -> list[JsonObject]:
    career_mcp = importlib.import_module("career_mcp")
    adapter = career_mcp.create_career_mcp(store=object())
    tools = maybe_await(adapter.list_tools())
    return list(tools)


def registered_runtime_tool_names() -> set[str]:
    career_mcp = importlib.import_module("career_mcp")
    table = getattr(career_mcp, "STORE_METHOD_BY_TOOL", {})
    return {name for name in table if isinstance(name, str) and re.fullmatch(r"career\.[a-z_]+", name)}


def assert_manifest_matches_runtime(
    test_case: unittest.TestCase,
    manifest_surface: JsonObject,
    discovered_tools: list[JsonObject],
    registered_tools: set[str] | None = None,
) -> None:
    manifest_by_name = manifest_tools_by_name(manifest_surface)
    runtime_by_name = {tool.get("name"): tool for tool in discovered_tools if isinstance(tool, dict)}
    manifest_names = set(manifest_by_name)
    discovered_names = set(runtime_by_name)
    registered_names = registered_tools if registered_tools is not None else registered_runtime_tool_names()
    runtime_names = discovered_names | registered_names

    manifest_only = sorted(manifest_names - runtime_names)
    runtime_only = sorted(runtime_names - manifest_names)
    unregistered_discovered = sorted(discovered_names - registered_names)
    test_case.assertFalse(manifest_only, f"manifest-only tools: {manifest_only}")
    test_case.assertFalse(runtime_only, f"runtime-only tools: {runtime_only}")
    test_case.assertFalse(unregistered_discovered, f"manifest-only tools: {unregistered_discovered}")

    for name in sorted(manifest_names):
        test_case.assertEqual(
            manifest_by_name[name].get("input_schema"),
            runtime_by_name[name].get("input_schema"),
            f"input schema mismatch for {name}",
        )


def collect_relationship_type_values(value: Any, path: tuple[str, ...] = ()) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = (*path, key)
            if key == "relationship_types" and isinstance(child, list):
                found.update(item for item in child if isinstance(item, str))
            elif key == "enum" and "relationship_type" in path and isinstance(child, list):
                found.update(item for item in child if isinstance(item, str))
            found.update(collect_relationship_type_values(child, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.update(collect_relationship_type_values(item, (*path, str(index))))
    return found


def collect_policy_vocabulary_hits(value: Any, path: tuple[str, ...] = ()) -> list[tuple[str, str, str]]:
    hits: list[tuple[str, str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = (*path, str(key))
            hits.extend(_policy_vocabulary_hits(str(key), child_path, context="key"))
            hits.extend(collect_policy_vocabulary_hits(child, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(collect_policy_vocabulary_hits(item, (*path, str(index))))
    elif isinstance(value, str):
        hits.extend(_policy_vocabulary_hits(value, path, context="value"))
    return hits


def _policy_vocabulary_hits(text: str, path: tuple[str, ...], context: str) -> list[tuple[str, str, str]]:
    hits: list[tuple[str, str, str]] = []
    for token in re.findall(r"[A-Za-z]+", text.lower()):
        normalized = token[:-1] if token.endswith("s") else token
        if normalized not in POLICY_VOCABULARY_BLOCKLIST:
            continue
        if _is_legitimate_policy_vocabulary_use(normalized, text, path, context):
            continue
        hits.append((normalized, ".".join(path), text))
    return hits


def _is_legitimate_policy_vocabulary_use(term: str, text: str, path: tuple[str, ...], context: str) -> bool:
    # The manifest's fact vocabulary includes "role" as a fact type. That is
    # domain data, not an access-control role claim.
    return (
        term == "role"
        and context == "value"
        and text == "role"
        and len(path) >= 4
        and path[-2] == "enum"
        and path[-3] == "items"
        and path[-4] == "types"
    )


def minimal_valid_arguments(tool: JsonObject) -> JsonObject:
    samples: JsonObject = {
        "type": "skill",
        "text": "AWS experience",
        "source": "agent_interpretation",
        "fact_id": "fact_aws",
        "verification_state": "source_stated",
        "confirmation": {
            "outcome": "affirmed",
            "provenance": [{"source": "resume_source", "source_id": "resume_1", "text": "Resume states this fact."}],
        },
        "evidence": {"source": "user_answer", "text": "Additional evidence."},
        "from_fact_id": "fact_aws",
        "to_fact_id": "fact_azure",
        "relationship_type": "related",
    }
    required = tool.get("input_schema", {}).get("required", [])
    return {name: samples[name] for name in required}


def assert_manifest_relationship_types_supported(
    test_case: unittest.TestCase,
    manifest_surface: JsonObject,
    store_surface: JsonObject,
) -> None:
    advertised = collect_relationship_type_values(manifest_surface)
    supported = set(store_surface.get("relationship_types", []))
    unsupported = sorted(advertised - supported)
    test_case.assertFalse(
        unsupported,
        "Manifest advertises relationship types unsupported by career-store/store_surface.json: "
        f"{unsupported}",
    )


def assert_manifest_enums_match_store_surface(
    test_case: unittest.TestCase,
    manifest_surface: JsonObject,
    store_surface: JsonObject,
) -> None:
    for key in ("verification_states", "resolution_states", "relationship_types"):
        with test_case.subTest(enum=key):
            test_case.assertEqual(set(manifest_surface.get(key, [])), set(store_surface.get(key, [])))


class CareerMcpManifestParityTests(unittest.TestCase):
    def test_package_manifest_matches_runtime_list_tools_names_and_input_schemas(self):
        manifest = load_json(PACKAGE_SURFACE_PATH)
        assert_manifest_matches_runtime(self, manifest, runtime_tools())

    def test_manifest_only_tool_fails_parity_assertion(self):
        manifest = load_json(PACKAGE_SURFACE_PATH)
        manifest["tools"] = [
            *manifest["tools"],
            {**deepcopy(manifest["tools"][0]), "name": "career.manifest_only"},
        ]

        with self.assertRaisesRegex(AssertionError, "manifest-only tools: .*career\\.manifest_only"):
            assert_manifest_matches_runtime(self, manifest, runtime_tools())

    def test_runtime_only_tool_fails_parity_assertion(self):
        manifest = load_json(PACKAGE_SURFACE_PATH)
        discovered = runtime_tools()
        discovered.append({**deepcopy(discovered[0]), "name": "career.runtime_only"})

        with self.assertRaisesRegex(AssertionError, "runtime-only tools: .*career\\.runtime_only"):
            assert_manifest_matches_runtime(self, manifest, discovered)

    def test_manifest_input_schema_drift_fails_parity_assertion(self):
        manifest = load_json(PACKAGE_SURFACE_PATH)
        mutated_runtime = deepcopy(runtime_tools())
        mutated_runtime[0]["input_schema"] = {**mutated_runtime[0]["input_schema"], "required": []}

        with self.assertRaisesRegex(AssertionError, "input schema mismatch for career\\.search_facts"):
            assert_manifest_matches_runtime(self, manifest, mutated_runtime)

    def test_manifest_relationship_types_are_store_contract_subset(self):
        assert_manifest_relationship_types_supported(
            self,
            load_json(PACKAGE_SURFACE_PATH),
            load_json(STORE_SURFACE_PATH),
        )

    def test_manifest_declared_enum_sets_match_store_surface_sets(self):
        assert_manifest_enums_match_store_surface(
            self,
            load_json(PACKAGE_SURFACE_PATH),
            load_json(STORE_SURFACE_PATH),
        )

    def test_manifest_policy_statement_matches_runtime_confirmation_policy(self):
        career_mcp_policy = importlib.import_module("career_mcp.policy")
        manifest = load_json(PACKAGE_SURFACE_PATH)
        statement = manifest.get("policy", {})

        self.assertEqual(statement.get("model"), "single-user-local-v1")
        self.assertIn("Single-user local", statement.get("posture", ""))
        self.assertIn("No v1 multi-user permission layer", statement.get("posture", ""))
        self.assertIn("confirmed=true", statement.get("confirmation", ""))
        self.assertNotIn("scope_enforcement", statement)
        self.assertEqual(declared_policy_gated_tools(manifest), runtime_policy_gated_tools())

        for name, tool in manifest_tools_by_name(manifest).items():
            with self.subTest(tool=name):
                decision = career_mcp_policy.evaluate_policy(name, {}, confirmed=False)
                self.assertEqual(decision.requires_confirmation, tool.get("mutates") is True)

    def test_manifest_policy_block_declares_exact_runtime_gated_tool_set(self):
        manifest = load_json(PACKAGE_SURFACE_PATH)
        declared = declared_policy_gated_tools(manifest)
        manifest_mutating = {name for name, tool in manifest_tools_by_name(manifest).items() if tool.get("mutates") is True}

        self.assertEqual(declared, runtime_policy_gated_tools())
        self.assertEqual(declared, manifest_mutating)

    def test_manifest_has_no_access_control_vocabulary_outside_fact_type_role(self):
        manifest = load_json(PACKAGE_SURFACE_PATH)

        self.assertEqual(collect_policy_vocabulary_hits(manifest), [])

    def test_manifest_declared_gated_tools_reject_unconfirmed_minimal_valid_mutations(self):
        career_mcp = importlib.import_module("career_mcp")
        FakeCareerStore = fake_career_store_class()
        manifest = load_json(PACKAGE_SURFACE_PATH)
        manifest_by_name = manifest_tools_by_name(manifest)

        for name in sorted(declared_policy_gated_tools(manifest)):
            with self.subTest(tool=name):
                store = FakeCareerStore()
                adapter = career_mcp.create_career_mcp(store=store)
                result = maybe_await(adapter.call_tool(name, minimal_valid_arguments(manifest_by_name[name])))

                self.assertEqual(result["status"], "rejected")
                self.assertEqual(result["error"]["type"], "policy_error")
                self.assertEqual(result["error"]["reason"], "confirmation_required")
                self.assertTrue(result["confirmation_required"])
                self.assertFalse(result["confirmed"])
                self.assertEqual(store.calls, [])

    def test_store_accepts_every_declared_relationship_type_behaviorally(self):
        career_store = importlib.import_module("career_store")
        declared = set(load_json(STORE_SURFACE_PATH).get("relationship_types", []))
        accepted: set[str] = set()

        with tempfile.TemporaryDirectory() as temp_dir:
            store = career_store.openCareerStore(f"{temp_dir}/career.db", clock=lambda: "2026-01-01T00:00:00Z")
            source = store.upsertFact(
                {"type": "skill", "text": "Frontend systems", "verification_state": "source_stated"},
                {"source": "resume_source", "source_id": "resume_1", "text": "Frontend systems"},
                source="resume_source",
            )
            target = store.upsertFact(
                {"type": "skill", "text": "React", "verification_state": "source_stated"},
                {"source": "resume_source", "source_id": "resume_1", "text": "React"},
                source="resume_source",
            )
            for relationship_type in sorted(declared):
                result = store.addRelationship(
                    source["fact_id"],
                    target["fact_id"],
                    relationship_type,
                    evidence_or_rationale={"text": f"{relationship_type} relationship"},
                    policy={},
                )
                if result.get("status") != "error":
                    accepted.add(relationship_type)

        # parent/child re-advertisement is deferred to Daniel's approval batch:
        # protected tools/career_store_guardrails.py currently pins the
        # declared store_surface.json relationship set to these four types.
        self.assertTrue(accepted >= declared, f"store rejected declared relationship types: {sorted(declared - accepted)}")

    def test_undeclared_relationship_type_fails_store_subset_assertion(self):
        manifest = load_json(PACKAGE_SURFACE_PATH)
        manifest["relationship_types"] = [*manifest["relationship_types"], "sibling"]
        add_relationship = manifest_tools_by_name(manifest)["career.add_relationship"]
        relationship_schema = add_relationship["input_schema"]["properties"]["relationship_type"]
        relationship_schema["enum"] = [*relationship_schema["enum"], "sibling"]

        with self.assertRaisesRegex(AssertionError, "unsupported.*sibling"):
            assert_manifest_relationship_types_supported(self, manifest, load_json(STORE_SURFACE_PATH))

    def test_generated_tool_surface_is_byte_identical_to_package_manifest(self):
        self.assertEqual(
            GENERATED_SURFACE_PATH.read_bytes(),
            PACKAGE_SURFACE_PATH.read_bytes(),
            "career-mcp/tool_surface.json must be byte-identical to "
            "career-mcp/career_mcp/tool_surface.json; run "
            f"{SYNC_TOOL_PATH}",
        )


if __name__ == "__main__":
    unittest.main()
