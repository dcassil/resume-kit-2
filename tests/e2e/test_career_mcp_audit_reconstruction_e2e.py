"""E2E proof that the career-mcp audit stream is sufficient to reconstruct mutations."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any


FIXED_TIME = "2026-01-01T00:00:00Z"
READ_EVENT_KEYS = {"tool", "status"}


def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def call_tool(adapter: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return maybe_await(adapter.call_tool(name, arguments))


def confirmed(arguments: dict[str, Any]) -> dict[str, Any]:
    return {**arguments, "confirmed": True}


def load_modules(test_case: unittest.TestCase):
    try:
        return importlib.import_module("career_mcp"), importlib.import_module("career_store")
    except ModuleNotFoundError:
        test_case.fail("Expected importable career_mcp and career_store packages. Run 'pip install -e .' first.")


def deterministic_ids(prefix: str):
    counter = 0

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"{prefix}-{counter:03d}"

    return next_id


def source_stated_confirmation(fact_id: str) -> dict[str, Any]:
    return {
        "factId": fact_id,
        "outcome": "affirmed",
        "provenance": [
            {
                "source": "resume",
                "source_id": "resume_1",
                "text": "Resume states React production delivery.",
            }
        ],
    }


def user_verified_confirmation(fact_id: str) -> dict[str, Any]:
    return {
        "factId": fact_id,
        "outcome": "affirmed",
        "provenance": [{"source": "user_answer", "text": "Yes, confirmed by the user."}],
    }


def reconstruct_changed_fact_states(events: list[dict[str, Any]]) -> dict[str, str]:
    changed: dict[str, str] = {}
    for event in events:
        if not event.get("is_mutation"):
            if set(event) != READ_EVENT_KEYS:
                raise AssertionError(f"Read audit event leaked reconstruction data: {event!r}")
            continue
        if event["status"] != "ok":
            if event.get("affected_fact_ids") != []:
                raise AssertionError(f"Rejected mutation must not report changed facts: {event!r}")
            continue
        for fact_id in event["affected_fact_ids"]:
            changed[str(fact_id)] = str(event["resulting_verification_state"])
    return changed


def run_reconstruction_script(test_case: unittest.TestCase, audit_sink: Any) -> dict[str, str]:
    career_mcp, career_store = load_modules(test_case)
    directory = tempfile.TemporaryDirectory()
    test_case.addCleanup(directory.cleanup)
    store = career_store.openCareerStore(str(Path(directory.name) / "career.db"), clock=lambda: FIXED_TIME)
    target = store.upsertFact(
        {
            "fact_id": "fact_frontend_architecture",
            "type": "skill",
            "text": "Frontend architecture",
            "normalized_terms": ["frontend architecture"],
            "verification_state": "source_stated",
        },
        {"source": "resume_source", "source_id": "resume_1", "text": "Frontend architecture"},
        source="resume_source",
    )
    test_case.assertEqual(target["verification_state"], "source_stated")

    adapter = career_mcp.create_career_mcp(
        store=store,
        audit_sink=audit_sink,
        operation_id_provider=deterministic_ids("audit-reconstruct-op"),
        timestamp_provider=lambda: FIXED_TIME,
    )

    proposed = call_tool(
        adapter,
        "career.propose_fact",
        confirmed({
            "type": "skill",
            "text": "React production delivery",
            "source": "agent_interpretation",
        }),
    )
    test_case.assertEqual(proposed["status"], "ok", proposed)
    fact_id = proposed["fact_id"]

    read_after_propose = call_tool(adapter, "career.get_fact", {"fact_id": fact_id})
    test_case.assertEqual(read_after_propose["status"], "ok", read_after_propose)

    verified = call_tool(
        adapter,
        "career.verify_fact",
        confirmed({
            "fact_id": fact_id,
            "verification_state": "source_stated",
            "evidence_id": "evidence_resume_1",
            "confirmation": source_stated_confirmation(fact_id),
        }),
    )
    test_case.assertEqual(verified["status"], "ok", verified)
    test_case.assertEqual(verified["verification_state"], "source_stated")

    search_after_verify = call_tool(adapter, "career.search_facts", {"query": "React", "limit": 5})
    test_case.assertEqual(search_after_verify["status"], "ok", search_after_verify)

    related = call_tool(
        adapter,
        "career.add_relationship",
        confirmed({
            "from_fact_id": fact_id,
            "to_fact_id": target["fact_id"],
            "relationship_type": "child",
            "evidence": {"source": "resume_source", "text": "React is a frontend architecture implementation."},
        }),
    )
    test_case.assertEqual(related["status"], "ok", related)

    rejected = call_tool(
        adapter,
        "career.verify_fact",
        {
            "fact_id": fact_id,
            "verification_state": "user_verified",
            "confirmation": user_verified_confirmation(fact_id),
        },
    )
    test_case.assertEqual(rejected["status"], "rejected", rejected)
    test_case.assertEqual(rejected["error"]["type"], "policy_error")

    final_read = call_tool(adapter, "career.get_fact", {"fact_id": target["fact_id"]})
    test_case.assertEqual(final_read["status"], "ok", final_read)

    return {
        fact_id: "source_stated",
        target["fact_id"]: "source_stated",
    }


class CareerMcpAuditReconstructionE2ETests(unittest.TestCase):
    def test_audit_stream_reconstructs_changed_facts_and_states_without_store_access(self) -> None:
        events: list[dict[str, Any]] = []
        expected = run_reconstruction_script(self, events)

        self.assertEqual(reconstruct_changed_fact_states(events), expected)
        self.assertEqual(
            [event["operation_id"] for event in events if event.get("is_mutation")],
            ["audit-reconstruct-op-001", "audit-reconstruct-op-003", "audit-reconstruct-op-005", "audit-reconstruct-op-006"],
        )
        rejected = [event for event in events if event.get("status") == "rejected"]
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["tool"], "career.verify_fact")
        self.assertEqual(rejected[0]["affected_fact_ids"], [])
        self.assertGreaterEqual(sum(1 for event in events if not event.get("is_mutation")), 3)

    def test_jsonl_audit_sink_round_trip_reconstructs_changed_facts_and_states(self) -> None:
        career_mcp, _career_store = load_modules(self)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "career-audit.jsonl"
            expected = run_reconstruction_script(self, career_mcp.audit.JsonlAuditSink(path))

            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertTrue(lines)
            events = [json.loads(line) for line in lines]

        self.assertEqual(reconstruct_changed_fact_states(events), expected)
        self.assertTrue(all(isinstance(event, dict) for event in events))


if __name__ == "__main__":
    unittest.main()
