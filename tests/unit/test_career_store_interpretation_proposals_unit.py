import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
for package_dir in ("resume-core", "career-store"):
    package_path = str(ROOT / package_dir)
    if package_path not in sys.path:
        sys.path.insert(0, package_path)

from career_store import InvalidInterpretationProposalError, openCareerStore  # noqa: E402


FIXED_TIME = "2026-01-01T00:00:00Z"


def proposal(fact_id: str, outcome: str = "affirmed", text: str = "I built React apps") -> dict:
    return {
        "factId": fact_id,
        "outcome": outcome,
        "provenance": [{"source": "user_answer", "text": text}],
    }


class CareerStoreInterpretationProposalUnitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = openCareerStore(str(Path(self.directory.name) / "career.db"), clock=lambda: FIXED_TIME)
        self.fact = self.store.upsertFact(
            {"type": "skill", "text": "AWS experience", "normalized_terms": ["aws"], "verification_state": "inferred"},
            {"source": "agent_proposal", "text": "possible AWS match"},
            source="agent_proposal",
            policy={"allow_inferred_final": False},
        )

    def test_affirmed_user_provenance_promotes_fact(self) -> None:
        result = self.store.verifyFact(
            self.fact["fact_id"],
            "user_verified",
            confirmation=proposal(self.fact["fact_id"], text="Yes, I have AWS experience."),
            source="user_answer",
        )

        self.assertEqual(result["status"], "updated")
        self.assertEqual(result["verification_state"], "user_verified")
        self.assertFalse(result["confirmation_required"])
        evidence = self.store.getFact(self.fact["fact_id"])["evidence"]
        self.assertTrue(any(item["metadata"].get("interpretation_proposal", {}).get("outcome") == "affirmed" for item in evidence))

    def test_denied_and_unclear_are_evidence_only_and_do_not_promote(self) -> None:
        for outcome in ("denied", "unclear"):
            with self.subTest(outcome=outcome):
                result = self.store.verifyFact(
                    self.fact["fact_id"],
                    "user_verified",
                    confirmation=proposal(self.fact["fact_id"], outcome=outcome, text=f"{outcome}: AWS"),
                    source="user_answer",
                )

                self.assertEqual(result["status"], "unchanged")
                self.assertEqual(result["mutation_status"], "evidence_only")
                self.assertEqual(result["verification_state"], "inferred")
                self.assertTrue(result["confirmation_required"])

    def test_audit_probe_raw_text_inputs_are_rejected_without_promotion(self) -> None:
        for answer in ("incorrect", "yesterday I did nothing"):
            with self.subTest(answer=answer):
                result = self.store.verifyFact(self.fact["fact_id"], "user_verified", confirmation=answer, source="user_answer")

                self.assertEqual(result["status"], "error")
                self.assertEqual(result["mutation_status"], "rejected")
                self.assertEqual(result["verification_state"], "inferred")
                self.assertEqual(result["errors"][0]["type"], InvalidInterpretationProposalError.__name__)
                self.assertEqual(result["errors"][0]["code"], "malformed_interpretation_proposal")

    def test_audit_probe_non_affirmed_proposals_are_evidence_only(self) -> None:
        for answer in ("incorrect", "yesterday I did nothing"):
            for outcome in ("denied", "unclear"):
                with self.subTest(answer=answer, outcome=outcome):
                    result = self.store.verifyFact(
                        self.fact["fact_id"],
                        "user_verified",
                        confirmation=proposal(self.fact["fact_id"], outcome=outcome, text=answer),
                        source="user_answer",
                    )

                    self.assertEqual(result["verification_state"], "inferred")
                    self.assertEqual(result["mutation_status"], "evidence_only")

    def test_invalid_proposal_shape_returns_typed_validation_errors(self) -> None:
        cases = [
            ({"factId": self.fact["fact_id"], "outcome": "maybe", "provenance": [{"source": "user_answer", "text": "yes"}]}, "unknown_outcome"),
            ({"factId": self.fact["fact_id"], "outcome": "affirmed", "provenance": []}, "missing_provenance"),
            ({"factId": "fact_missing", "outcome": "affirmed", "provenance": [{"source": "user_answer", "text": "yes"}]}, "fact_id_mismatch"),
            ({"source": "user_answer", "text": "Yes", "confirmed": True}, "malformed_interpretation_proposal"),
        ]
        for candidate, code in cases:
            with self.subTest(code=code):
                result = self.store.verifyFact(self.fact["fact_id"], "user_verified", confirmation=candidate, source="user_answer")

                self.assertEqual(result["status"], "error")
                self.assertEqual(result["errors"][0]["type"], InvalidInterpretationProposalError.__name__)
                self.assertEqual(result["errors"][0]["code"], code)

    def test_unknown_fact_id_is_typed_validation_error(self) -> None:
        result = self.store.verifyFact(
            "fact_missing",
            "user_verified",
            confirmation=proposal("fact_missing", text="Yes"),
            source="user_answer",
        )

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["errors"][0]["type"], InvalidInterpretationProposalError.__name__)
        self.assertEqual(result["errors"][0]["code"], "unknown_fact_id")


if __name__ == "__main__":
    unittest.main()
