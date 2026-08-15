import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
for package_dir in ("resume-core", "career-store"):
    package_path = str(ROOT / package_dir)
    if package_path not in sys.path:
        sys.path.insert(0, package_path)

from career_store import MergeConflictError, openCareerStore  # noqa: E402
from career_store.migrations import _stable_id  # noqa: E402


FIXED_TIME = "2026-01-01T00:00:00Z"


def _source_fact(store, fact_id: str, text: str, terms: list[str], **extra):
    return store.upsertFact(
        {
            "fact_id": fact_id,
            "type": "skill",
            "text": text,
            "normalized_terms": terms,
            "verification_state": "source_stated",
            **extra,
        },
        {"source": "resume", "source_id": "resume_1", "text": text},
        source="resume",
        policy={},
    )


def _inferred_fact(store, fact_id: str, text: str, terms: list[str]):
    return store.upsertFact(
        {
            "fact_id": fact_id,
            "type": "skill",
            "text": text,
            "normalized_terms": terms,
            "verification_state": "inferred",
        },
        {"source": "agent_proposal", "text": f"possible {text}", "metadata": {"rationale": f"{text} overlap"}},
        source="agent_proposal",
        policy={"allow_inferred_final": False},
    )


def _verify_user(store, fact_id: str):
    return store.verifyFact(
        fact_id,
        "user_verified",
        confirmation={
            "factId": fact_id,
            "outcome": "affirmed",
            "provenance": [{"source": "user_answer", "text": "Yes, this is correct."}],
        },
        source="user_answer",
    )


class CareerStoreMergeFactsUnitTests(unittest.TestCase):
    def test_merge_facts_retains_aliases_evidence_history_redirect_and_job_matches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            store = openCareerStore(str(database_path), clock=lambda: FIXED_TIME)
            survivor = _source_fact(
                store,
                "fact_node",
                "Node backend experience.",
                ["node", "backend"],
                canonical_name="Node",
                description="backend runtime work",
            )
            merged = _source_fact(
                store,
                "fact_nodejs",
                "Node.js service experience.",
                ["node.js", "service"],
                canonical_name="Node.js",
                description="server runtime experience",
            )
            store.recordJobMatch("job_a", "req_nodejs", [merged["fact_id"]], "exact_match")

            result = store.mergeFacts(
                survivor["fact_id"],
                merged["fact_id"],
                {"source": "user_answer", "text": "These are the same skill.", "reason": "dedupe"},
            )

            self.assertEqual(result["status"], "updated")
            self.assertEqual(result["merge_id"], _stable_id("fact_merge", survivor["fact_id"], merged["fact_id"]))
            redirected = store.getFact(merged["fact_id"])
            self.assertEqual(redirected["status"], "ok")
            self.assertEqual(redirected["fact"]["fact_id"], survivor["fact_id"])
            self.assertEqual(redirected["fact"]["verification_state"], "source_stated")
            self.assertIn("node js", redirected["fact"]["normalized_terms"])
            self.assertIn("server runtime experience", redirected["fact"]["normalized_terms"])
            evidence_fact_ids = {item["evidence_id"]: item for item in redirected["evidence"]}
            self.assertEqual(len(evidence_fact_ids), 4)

            search = store.searchFacts("Node.js", include_evidence=True)
            self.assertEqual([fact["fact_id"] for fact in search["facts"]], [survivor["fact_id"]])
            redirected_search = store.searchFacts(merged["fact_id"])
            self.assertEqual([fact["fact_id"] for fact in redirected_search["facts"]], [survivor["fact_id"]])
            all_active = store.searchFacts("")["facts"]
            self.assertEqual([fact["fact_id"] for fact in all_active], [survivor["fact_id"]])

            with sqlite3.connect(database_path) as conn:
                conn.row_factory = sqlite3.Row
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM evidence WHERE fact_id = ?", (merged["fact_id"],)).fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM evidence WHERE fact_id = ?", (survivor["fact_id"],)).fetchone()[0], 4)
                match = conn.execute("SELECT fact_ids_json FROM job_matches").fetchone()
                self.assertEqual(json.loads(match["fact_ids_json"]), [survivor["fact_id"]])
                merge = conn.execute("SELECT * FROM fact_merges WHERE merge_id = ?", (result["merge_id"],)).fetchone()
                self.assertEqual(merge["survivor_fact_id"], survivor["fact_id"])
                self.assertEqual(merge["merged_fact_id"], merged["fact_id"])
                self.assertEqual(json.loads(merge["provenance_json"])["reason"], "dedupe")
                alias = conn.execute(
                    """
                    SELECT relationship_type FROM relationships
                    WHERE from_fact_id = ? AND to_fact_id = ?
                    """,
                    (survivor["fact_id"], merged["fact_id"]),
                ).fetchone()
                self.assertEqual(alias["relationship_type"], "alias")

    def test_merge_facts_preserves_user_verified_survivor_when_merged_is_inferred(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            survivor = _inferred_fact(store, "fact_react", "React", ["react"])
            _verify_user(store, survivor["fact_id"])
            merged = _inferred_fact(store, "fact_reactjs", "React.js", ["react.js"])

            result = store.mergeFacts(survivor["fact_id"], merged["fact_id"], {"source": "user_answer", "text": "same"})

            self.assertEqual(result["verification_state"], "user_verified")
            self.assertEqual(store.getFact(survivor["fact_id"])["fact"]["verification_state"], "user_verified")

    def test_merge_facts_does_not_promote_inferred_survivor_from_user_verified_merged_fact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            survivor = _inferred_fact(store, "fact_graphql", "GraphQL", ["graphql"])
            merged = _inferred_fact(store, "fact_gql", "GQL", ["gql"])
            _verify_user(store, merged["fact_id"])

            result = store.mergeFacts(survivor["fact_id"], merged["fact_id"], {"source": "user_answer", "text": "same"})

            self.assertEqual(result["verification_state"], "inferred")
            self.assertEqual(store.getFact(survivor["fact_id"])["fact"]["verification_state"], "inferred")

    def test_merge_facts_returns_typed_conflicts_for_unknown_self_and_redirected_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            survivor = _source_fact(store, "fact_a", "A", ["a"])
            merged = _source_fact(store, "fact_b", "B", ["b"])
            third = _source_fact(store, "fact_c", "C", ["c"])

            unknown = store.mergeFacts("fact_missing", merged["fact_id"], {"source": "test", "text": "unknown"})
            self.assertEqual(unknown["errors"][0]["type"], MergeConflictError.__name__)
            self.assertEqual(unknown["errors"][0]["code"], "unknown_fact_id")
            self.assertEqual(unknown["transaction_result"]["mutation_status"], "rejected")

            self_merge = store.mergeFacts(survivor["fact_id"], survivor["fact_id"], {"source": "test", "text": "self"})
            self.assertEqual(self_merge["errors"][0]["type"], MergeConflictError.__name__)
            self.assertEqual(self_merge["errors"][0]["code"], "self_merge")

            store.mergeFacts(survivor["fact_id"], merged["fact_id"], {"source": "test", "text": "first merge"})
            from_redirected = store.mergeFacts(merged["fact_id"], third["fact_id"], {"source": "test", "text": "redirected survivor"})
            into_redirected = store.mergeFacts(survivor["fact_id"], merged["fact_id"], {"source": "test", "text": "redirected merged"})
            self.assertEqual(from_redirected["errors"][0]["code"], "already_merged")
            self.assertEqual(into_redirected["errors"][0]["code"], "already_merged")

    def test_merge_facts_rolls_back_after_repoint_interruption(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "career.db"
            store = openCareerStore(str(database_path), clock=lambda: FIXED_TIME)
            survivor = _source_fact(store, "fact_python", "Python", ["python"])
            merged = _source_fact(store, "fact_py", "Py", ["py"])
            store.recordJobMatch("job_a", "req_py", [merged["fact_id"]], "exact_match")

            def fail_after_repoint(operation: str) -> None:
                self.assertEqual(operation, "mergeFacts")
                raise RuntimeError("injected merge interruption")

            with self.assertRaises(RuntimeError) as raised:
                store.mergeFacts(
                    survivor["fact_id"],
                    merged["fact_id"],
                    {"source": "test", "text": "interrupt", "_after_repoint": fail_after_repoint},
                )

            self.assertEqual(raised.exception.transaction_result.status, "rolled_back")
            with sqlite3.connect(database_path) as conn:
                conn.row_factory = sqlite3.Row
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM fact_merges").fetchone()[0], 0)
                self.assertIsNone(
                    conn.execute("SELECT merged_into_fact_id FROM facts WHERE fact_id = ?", (merged["fact_id"],)).fetchone()[
                        "merged_into_fact_id"
                    ]
                )
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM evidence WHERE fact_id = ?", (merged["fact_id"],)).fetchone()[0], 2)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM relationships WHERE relationship_type = 'alias'").fetchone()[0], 0)
                match = conn.execute("SELECT fact_ids_json FROM job_matches").fetchone()
                self.assertEqual(json.loads(match["fact_ids_json"]), [merged["fact_id"]])


if __name__ == "__main__":
    unittest.main()
