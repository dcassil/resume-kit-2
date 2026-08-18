"""Fixture-driven career-mcp scenarios over a real SQLite career store."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import tempfile
import unittest
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tests.contract.test_career_mcp_server_contract import CareerMcpProcess, response_envelope


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"
FIXED_TIME = "2026-01-01T00:00:00Z"
FAKE_ONLY_REQUIREMENT_IDS = {
    "req_react",
    "req_api",
    "req_responsive",
    "req_aws",
    "req_graphql",
    "req_azure",
    "req_staff",
}
STORE_STRIPPED_FACT_KEYS = {"schema_version", "query", "audit"}
STORE_STRIPPED_ITEM_KEYS = {"created_at", "updated_at", "metadata", "evidence", "evidence_ids"}
STORE_STRIPPED_MATCH_KEYS = {
    "audit",
    "conflicts",
    "conflict_signals",
    "fact",
    "factId",
    "fact_id",
    "job_id",
    "matchType",
    "match_terms",
    "match_type",
    "metadata",
    "schema_version",
    "supporting_facts",
    "terms",
    "unresolved",
    "viaRelationships",
    "via_relationships",
}


def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def confirmed(arguments: dict[str, Any]) -> dict[str, Any]:
    return {**arguments, "confirmed": True}


def load_json(relative_path: str) -> dict[str, Any]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def answer_text(name: str) -> str:
    return (FIXTURES / "answers" / f"{name}.txt").read_text(encoding="utf-8").strip()


def expected_observations(fixture_id: str) -> list[str]:
    return load_json(f"fixtures/expected/{fixture_id}.json")["expected_observations"]


def normalized_job_requirements(fixture_id: str) -> list[dict[str, Any]]:
    job_model = load_json(f"fixtures/expected/{fixture_id}.json")["data"]["job_model"]
    return [*job_model["requirements"], *job_model["preferred"]]


def normalized_resume_claims() -> list[dict[str, str]]:
    resume = load_json("fixtures/expected/normalized-resume.json")["data"]["canonical_resume"]
    claims = [
        {
            "type": "experience",
            "text": resume["summary"]["value"],
            "source_id": resume["summary"]["claim_id"],
        }
    ]
    for skill in resume["skills"]:
        claims.append({"type": "skill", "text": skill["value"], "source_id": skill["claim_id"]})
    for experience in resume["experience"]:
        for bullet in experience["bullets"]:
            claims.append({"type": "experience", "text": bullet["value"], "source_id": bullet["claim_id"]})
    return claims


def operation_fact_label(operation_id: str) -> str:
    operations = load_json("fixtures/expected/valid-operations.json")["data"]["operations"]
    for operation in operations:
        payload = operation["operation"]
        if payload["operation_id"] == operation_id:
            return payload["linked_fact_ids"][0]
    raise AssertionError(f"Missing fixture operation: {operation_id}")


def user_confirmation(fact_id: str, text: str, source_id: str) -> dict[str, Any]:
    return {
        "factId": fact_id,
        "outcome": "affirmed",
        "provenance": [{"source": "user_answer", "source_id": source_id, "text": text}],
    }


def source_confirmation(fact_id: str, text: str, source_id: str) -> dict[str, Any]:
    return {
        "factId": fact_id,
        "outcome": "affirmed",
        "provenance": [{"source": "resume_source", "source_id": source_id, "text": text}],
    }


class ScenarioDriver:
    name: str
    audit_events: list[dict[str, Any]] | None = None

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def store_call(self, method: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def close(self) -> None:
        return None


class InProcessScenarioDriver(ScenarioDriver):
    name = "in_process"

    def __init__(self, audit_events: list[dict[str, Any]] | None = None) -> None:
        career_mcp = importlib.import_module("career_mcp")
        career_store = importlib.import_module("career_store")
        self._directory = tempfile.TemporaryDirectory()
        self._store = career_store.openCareerStore(str(Path(self._directory.name) / "career.db"), clock=lambda: FIXED_TIME)
        self.audit_events = audit_events
        self._adapter = career_mcp.create_career_mcp(
            store=self._store,
            audit_sink=audit_events,
            operation_id_provider=_deterministic_ids(f"{self.name}-op"),
            timestamp_provider=lambda: FIXED_TIME,
        )

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return maybe_await(self._adapter.call_tool(name, arguments))

    def store_call(self, method: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return getattr(self._store, method)(*args, **kwargs)

    def close(self) -> None:
        self._directory.cleanup()


class StdioScenarioDriver(ScenarioDriver):
    name = "stdio"

    def __init__(self, test_case: unittest.TestCase) -> None:
        career_store = importlib.import_module("career_store")
        self._store_factory = career_store.openCareerStore
        self._directory = tempfile.TemporaryDirectory()
        self._db_path = Path(self._directory.name) / "career.db"
        self._process = CareerMcpProcess(test_case, self._db_path)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = self._process.request(
            {
                "jsonrpc": "2.0",
                "id": f"{name}:{len(json.dumps(arguments, sort_keys=True))}",
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        return response_envelope(response)

    def store_call(self, method: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        store = self._store_factory(str(self._db_path), clock=lambda: FIXED_TIME)
        return getattr(store, method)(*args, **kwargs)

    def close(self) -> None:
        self._process.close_and_wait()
        self._directory.cleanup()


def _deterministic_ids(prefix: str) -> Callable[[], str]:
    counter = 0

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"{prefix}-{counter:03d}"

    return next_id


def assert_ok(test_case: unittest.TestCase, result: dict[str, Any]) -> None:
    test_case.assertEqual(result["status"], "ok", result)


def propose_and_verify(
    test_case: unittest.TestCase,
    driver: ScenarioDriver,
    *,
    fact_type: str,
    text: str,
    verification_state: str,
    source_id: str,
    source: str,
) -> str:
    proposed = driver.call_tool(
        "career.propose_fact",
        confirmed({
            "type": fact_type,
            "text": text,
            "source": source,
            "evidence": {"source": source, "source_id": source_id, "text": text},
        }),
    )
    assert_ok(test_case, proposed)
    fact_id = proposed["fact_id"]
    confirmation = (
        user_confirmation(fact_id, text, source_id)
        if verification_state == "user_verified"
        else source_confirmation(fact_id, text, source_id)
    )
    arguments = {
        "fact_id": fact_id,
        "verification_state": verification_state,
        "confirmation": confirmation,
        "evidence_id": f"evidence_{source_id}",
        "confirmed": True,
    }
    verified = driver.call_tool("career.verify_fact", arguments)
    assert_ok(test_case, verified)
    test_case.assertEqual(verified["verification_state"], verification_state, verified)
    return fact_id


def seed_resume_facts(test_case: unittest.TestCase, driver: ScenarioDriver) -> dict[str, str]:
    seeded: dict[str, str] = {}
    for claim in normalized_resume_claims():
        seeded[claim["source_id"]] = propose_and_verify(
            test_case,
            driver,
            fact_type=claim["type"],
            text=claim["text"],
            verification_state="source_stated",
            source_id=claim["source_id"],
            source="resume_source",
        )
    return seeded


def seed_answer_fact(test_case: unittest.TestCase, driver: ScenarioDriver, name: str, fact_type: str, text: str) -> str:
    operation_id = {
        "aws": "op_add_aws_skill",
        "graphql": "op_add_graphql_skill",
        "architecture": "op_rewrite_api_architecture",
    }[name]
    fixture_label = operation_fact_label(operation_id)
    return propose_and_verify(
        test_case,
        driver,
        fact_type=fact_type,
        text=text,
        verification_state="user_verified",
        source_id=fixture_label,
        source="user_answer",
    )


def mcp_search_expected(store_result: dict[str, Any], *, verification: list[str] | None = None, types: list[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
    verification_set = set(verification or [])
    type_set = set(types or [])
    facts = []
    for fact in store_result["facts"]:
        if verification_set and fact["verification_state"] not in verification_set:
            continue
        if type_set and fact["type"] not in type_set:
            continue
        facts.append(
            {
                "fact_id": fact["fact_id"],
                "type": fact["type"],
                "text": fact["text"],
                "verification_state": fact["verification_state"],
                "evidence_summary": [
                    {key: item[key] for key in ("source", "text", "source_id") if key in item}
                    for item in fact.get("evidence", [])
                ],
            }
        )
    return sorted(facts, key=lambda fact: fact["fact_id"])[:limit]


def mcp_get_fact_expected(store_result: dict[str, Any]) -> dict[str, Any]:
    fact = store_result["fact"]
    expected_fact = {
        "fact_id": fact["fact_id"],
        "type": fact["type"],
        "text": fact["text"],
        "verification_state": fact["verification_state"],
        "evidence_summary": [
            {key: item[key] for key in ("source", "text", "source_id") if key in item}
            for item in store_result["evidence"]
        ],
        "relationships": store_result["relationships"],
        "conflicts": store_result["conflicts"],
    }
    if fact.get("normalized_terms"):
        expected_fact["normalized_terms"] = fact["normalized_terms"]
    return expected_fact


def mcp_matches_expected(store_result: dict[str, Any], requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows_by_requirement: dict[str, dict[str, Any]] = {}
    for section in ("matches", "unresolved"):
        for row in store_result.get(section, []):
            requirement_id = row["requirement_id"]
            rows_by_requirement.setdefault(requirement_id, row)
    for requirement in requirements:
        requirement_id = requirement["requirement_id"]
        rows_by_requirement.setdefault(requirement_id, {"requirement_id": requirement_id, "resolution_state": "unknown", "fact_ids": []})
    expected = []
    for row in rows_by_requirement.values():
        expected.append(
            {
                "requirement_id": row["requirement_id"],
                "resolution_state": row["resolution_state"],
                "fact_ids": list(row.get("fact_ids") or ([row["fact_id"]] if row.get("fact_id") else [])),
                "reasoning": row.get("reasoning", row.get("match_type", "classified by career-store fact graph")),
            }
        )
    return sorted(expected, key=lambda item: item["requirement_id"])


def assert_search_alignment(test_case: unittest.TestCase, driver: ScenarioDriver, arguments: dict[str, Any]) -> dict[str, Any]:
    mcp_result = driver.call_tool("career.search_facts", arguments)
    assert_ok(test_case, mcp_result)
    store_result = driver.store_call("searchFacts", arguments["query"], filters={}, limit=None, include_evidence=True)
    test_case.assertTrue(STORE_STRIPPED_FACT_KEYS <= set(store_result))
    if store_result["facts"]:
        test_case.assertTrue({"normalized_terms", "created_at", "updated_at", "metadata", "evidence_ids"} <= set(store_result["facts"][0]))
    test_case.assertFalse(STORE_STRIPPED_FACT_KEYS & set(mcp_result))
    for fact in mcp_result["facts"]:
        test_case.assertFalse(STORE_STRIPPED_ITEM_KEYS & set(fact))
    test_case.assertEqual(
        mcp_result["facts"],
        mcp_search_expected(
            store_result,
            verification=arguments.get("verification"),
            types=arguments.get("types"),
            limit=arguments.get("limit", 10),
        ),
    )
    return mcp_result


def assert_get_fact_alignment(test_case: unittest.TestCase, driver: ScenarioDriver, fact_id: str) -> dict[str, Any]:
    mcp_result = driver.call_tool("career.get_fact", {"fact_id": fact_id})
    assert_ok(test_case, mcp_result)
    store_result = driver.store_call("getFact", fact_id)
    test_case.assertIn("audit", store_result)
    test_case.assertIn("evidence", store_result)
    test_case.assertNotIn("audit", mcp_result)
    test_case.assertNotIn("evidence", mcp_result)
    test_case.assertEqual(mcp_result["fact"], mcp_get_fact_expected(store_result))
    return mcp_result


def assert_match_alignment(test_case: unittest.TestCase, driver: ScenarioDriver, requirements: list[dict[str, Any]]) -> dict[str, Any]:
    mcp_result = driver.call_tool("career.find_matches", {"requirements": requirements})
    assert_ok(test_case, mcp_result)
    store_result = driver.store_call("findCandidateMatches", requirements, policy={})
    test_case.assertTrue({"schema_version", "audit", "matches", "unresolved"} <= set(store_result))
    if store_result["matches"]:
        test_case.assertTrue({"fact", "supporting_facts", "match_terms", "metadata"} <= set(store_result["matches"][0]))
    test_case.assertFalse(STORE_STRIPPED_MATCH_KEYS & set(mcp_result))
    test_case.assertEqual(mcp_result["matches"], mcp_matches_expected(store_result, requirements))
    return mcp_result


def assert_one_row_per_requirement(test_case: unittest.TestCase, matches: list[dict[str, Any]]) -> None:
    requirement_ids = [match["requirement_id"] for match in matches]
    test_case.assertEqual(len(requirement_ids), len(set(requirement_ids)), matches)


def run_answer_fixture_scenario(test_case: unittest.TestCase, driver: ScenarioDriver) -> None:
    seed_resume_facts(test_case, driver)
    observations = {
        "post-aws-match": expected_observations("post-aws-match"),
        "post-graphql-match": expected_observations("post-graphql-match"),
        "final-job-a-match": expected_observations("final-job-a-match"),
    }
    test_case.assertIn("AWS preferred requirement resolves from explicit user answer", observations["post-aws-match"])
    test_case.assertIn("GraphQL resolves from explicit user answer", observations["post-graphql-match"])
    test_case.assertIn("architecture/API-design evidence can support architecture requirements", observations["final-job-a-match"])

    aws_id = seed_answer_fact(test_case, driver, "aws", "skill", answer_text("aws"))
    graphql_id = seed_answer_fact(test_case, driver, "graphql", "skill", answer_text("graphql"))
    architecture_id = seed_answer_fact(test_case, driver, "architecture", "experience", answer_text("architecture"))

    aws_search = assert_search_alignment(test_case, driver, {"query": "AWS", "verification": ["user_verified"], "limit": 5})
    graphql_search = assert_search_alignment(test_case, driver, {"query": "GraphQL", "verification": ["user_verified"], "limit": 5})
    architecture_search = assert_search_alignment(test_case, driver, {"query": "architecture", "verification": ["user_verified"], "limit": 5})

    test_case.assertIn(aws_id, {fact["fact_id"] for fact in aws_search["facts"]})
    test_case.assertIn(graphql_id, {fact["fact_id"] for fact in graphql_search["facts"]})
    test_case.assertIn(architecture_id, {fact["fact_id"] for fact in architecture_search["facts"]})
    test_case.assertTrue(any("six years" in fact["text"] for fact in aws_search["facts"]))
    test_case.assertTrue(any("five years" in fact["text"] for fact in graphql_search["facts"]))
    test_case.assertFalse(any("Staff Engineer as my formal title" == fact["text"] for fact in architecture_search["facts"]))
    assert_get_fact_alignment(test_case, driver, architecture_id)


def run_job_a_to_b_reuse_scenario(test_case: unittest.TestCase, driver: ScenarioDriver) -> None:
    seed_resume_facts(test_case, driver)
    observations = expected_observations("job-b-initial-match")
    test_case.assertIn("AWS resolves from persisted Job A user-verified fact", observations)
    test_case.assertIn("GraphQL resolves from persisted Job A user-verified fact", observations)
    aws_id = seed_answer_fact(test_case, driver, "aws", "skill", answer_text("aws"))
    graphql_id = seed_answer_fact(test_case, driver, "graphql", "skill", answer_text("graphql"))

    job_b_requirements = normalized_job_requirements("normalized-job-b")
    result = assert_match_alignment(test_case, driver, job_b_requirements)
    assert_one_row_per_requirement(test_case, result["matches"])
    matches = {match["requirement_id"]: match for match in result["matches"]}
    graph_req = "fixture_req_2_bdba1a3e"
    aws_req = "fixture_req_3_c3f15cdb"
    test_case.assertEqual(matches[graph_req]["resolution_state"], "verified_fact_match")
    test_case.assertEqual(matches[aws_req]["resolution_state"], "verified_fact_match")
    test_case.assertIn(graphql_id, matches[graph_req]["fact_ids"])
    test_case.assertIn(aws_id, matches[aws_req]["fact_ids"])
    test_case.assertEqual(len([match for match in result["matches"] if match["requirement_id"] == graph_req]), 1)
    test_case.assertEqual(len([match for match in result["matches"] if match["requirement_id"] == aws_req]), 1)


def run_gap_resolution_and_audit_scenario(test_case: unittest.TestCase, driver: ScenarioDriver) -> None:
    observations = expected_observations("audit-report")
    test_case.assertIn("audit reconstructs source resume, job, config, questions, answers, facts, operations, validations, and outputs", observations)
    proposed = driver.call_tool(
        "career.propose_fact",
        confirmed({
            "type": "experience",
            "text": answer_text("architecture"),
            "source": "user_answer",
            "evidence": {"source": "user_answer", "source_id": "answer-architecture", "text": answer_text("architecture")},
        }),
    )
    assert_ok(test_case, proposed)
    fact_id = proposed["fact_id"]
    queue = driver.call_tool("career.get_unverified", {"topic": "architecture", "limit": 5})
    assert_ok(test_case, queue)
    test_case.assertIn(fact_id, {fact["fact_id"] for fact in queue["facts"]})
    verified = driver.call_tool(
        "career.verify_fact",
        confirmed({
            "fact_id": fact_id,
            "verification_state": "user_verified",
            "evidence_id": "evidence_answer-architecture",
            "confirmation": user_confirmation(fact_id, answer_text("architecture"), "answer-architecture"),
        }),
    )
    assert_ok(test_case, verified)
    test_case.assertEqual(verified["verification_state"], "user_verified")
    assert_get_fact_alignment(test_case, driver, fact_id)
    test_case.assertIsNotNone(driver.audit_events)
    changed = reconstruct_changed_fact_states(driver.audit_events or [])
    test_case.assertEqual(changed[fact_id], "user_verified")


def reconstruct_changed_fact_states(events: list[dict[str, Any]]) -> dict[str, str]:
    changed: dict[str, str] = {}
    for event in events:
        if not event.get("is_mutation"):
            if set(event) != {"tool", "status"}:
                raise AssertionError(f"Read audit event leaked reconstruction data: {event!r}")
            continue
        if event["status"] != "ok":
            if event.get("affected_fact_ids") != []:
                raise AssertionError(f"Rejected mutation must not report changed facts: {event!r}")
            continue
        for fact_id in event["affected_fact_ids"]:
            changed[fact_id] = event["resulting_verification_state"]
    return changed


@dataclass(frozen=True)
class Scenario:
    name: str
    run: Callable[[unittest.TestCase, ScenarioDriver], None]
    stdio: bool
    expected_match_requirement_ids: tuple[str, ...] = ()


SCENARIOS = (
    Scenario("fixture_answers", run_answer_fixture_scenario, True),
    Scenario(
        "job_a_to_b_reuse",
        run_job_a_to_b_reuse_scenario,
        True,
        ("fixture_req_2_bdba1a3e", "fixture_req_3_c3f15cdb"),
    ),
    Scenario("gap_resolution_audit", run_gap_resolution_and_audit_scenario, False),
)


class CareerMcpRealStoreScenarioE2ETests(unittest.TestCase):
    def test_scenarios_run_in_process_and_representative_subset_over_stdio(self) -> None:
        for scenario in SCENARIOS:
            with self.subTest(driver="in_process", scenario=scenario.name):
                driver = InProcessScenarioDriver(audit_events=[])
                try:
                    scenario.run(self, driver)
                finally:
                    driver.close()
            if scenario.stdio:
                with self.subTest(driver="stdio", scenario=scenario.name):
                    driver = StdioScenarioDriver(self)
                    try:
                        scenario.run(self, driver)
                    finally:
                        driver.close()

    def test_product_scenario_expectations_are_not_satisfiable_by_fake_only_classifications(self) -> None:
        scenario_requirement_ids = {
            requirement_id
            for scenario in SCENARIOS
            for requirement_id in scenario.expected_match_requirement_ids
        }

        self.assertTrue(scenario_requirement_ids)
        self.assertFalse(scenario_requirement_ids & FAKE_ONLY_REQUIREMENT_IDS)
        for requirement_id in scenario_requirement_ids:
            self.assertTrue(requirement_id.startswith("fixture_req_"))


if __name__ == "__main__":
    unittest.main()
