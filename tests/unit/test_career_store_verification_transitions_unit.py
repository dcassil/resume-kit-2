import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
for package_dir in ("resume-core", "career-store"):
    package_path = str(ROOT / package_dir)
    if package_path not in sys.path:
        sys.path.insert(0, package_path)

from career_store import InterpretationProposal, openCareerStore  # noqa: E402
from career_store.verification import (  # noqa: E402
    AUTHORITY_AGENT_INFERENCE_PROVENANCE,
    AUTHORITY_EXPLICIT_USER_CORRECTION,
    AUTHORITY_IMPORT_PROVENANCE,
    AUTHORITY_KINDS,
    AUTHORITY_SOURCE_DOCUMENT_EVIDENCE,
    AUTHORITY_USER_AFFIRMED_PROPOSAL,
    CANONICAL_VERIFICATION_STATES,
    VERIFICATION_TRANSITION_MATRIX,
    DisallowedTransitionError,
    agent_inference_provenance_authority,
    evaluate_verification_transition,
    explicit_user_correction_authority,
    import_provenance_authority,
    source_document_evidence_authority,
    transition_evidence_row,
    user_affirmed_proposal_authority,
)


FIXED_TIME = "2026-01-01T00:00:00Z"

EXPECTED_MATRIX = {
    ("unknown", "inferred"): AUTHORITY_AGENT_INFERENCE_PROVENANCE,
    ("unknown", "source_stated"): AUTHORITY_SOURCE_DOCUMENT_EVIDENCE,
    ("unknown", "imported"): AUTHORITY_IMPORT_PROVENANCE,
    ("unknown", "user_verified"): AUTHORITY_USER_AFFIRMED_PROPOSAL,
    ("inferred", "source_stated"): AUTHORITY_SOURCE_DOCUMENT_EVIDENCE,
    ("inferred", "imported"): AUTHORITY_IMPORT_PROVENANCE,
    ("inferred", "user_verified"): AUTHORITY_USER_AFFIRMED_PROPOSAL,
    ("imported", "source_stated"): AUTHORITY_SOURCE_DOCUMENT_EVIDENCE,
    ("imported", "user_verified"): AUTHORITY_USER_AFFIRMED_PROPOSAL,
    ("source_stated", "user_verified"): AUTHORITY_USER_AFFIRMED_PROPOSAL,
    ("user_verified", "source_stated"): AUTHORITY_EXPLICIT_USER_CORRECTION,
    ("user_verified", "imported"): AUTHORITY_EXPLICIT_USER_CORRECTION,
    ("user_verified", "inferred"): AUTHORITY_EXPLICIT_USER_CORRECTION,
    ("user_verified", "unknown"): AUTHORITY_EXPLICIT_USER_CORRECTION,
}


def _proposal(fact_id: str = "fact_1", source: str = "user_answer", confirmed_value: object | None = None) -> InterpretationProposal:
    return InterpretationProposal(
        factId=fact_id,
        questionId="question_1",
        outcome="affirmed",
        confirmedValue=confirmed_value,
        provenance=[{"source": source, "text": "I confirm this fact."}],
    )


def _authorities() -> dict[str, object]:
    return {
        AUTHORITY_AGENT_INFERENCE_PROVENANCE: agent_inference_provenance_authority(
            {"source": "agent", "text": "Inferred from overlapping terms.", "metadata": {"rationale": "term overlap"}}
        ),
        AUTHORITY_EXPLICIT_USER_CORRECTION: explicit_user_correction_authority(
            _proposal(confirmed_value={"verification_state": "unknown"})
        ),
        AUTHORITY_IMPORT_PROVENANCE: import_provenance_authority(
            {"source": "external_system", "text": "Imported durable profile fact.", "metadata": {"import_id": "import_1"}}
        ),
        AUTHORITY_SOURCE_DOCUMENT_EVIDENCE: source_document_evidence_authority(
            {"source": "resume", "source_id": "resume_1", "text": "Built React applications."}
        ),
        AUTHORITY_USER_AFFIRMED_PROPOSAL: user_affirmed_proposal_authority(_proposal()),
    }


class CareerStoreVerificationTransitionUnitTests(unittest.TestCase):
    def test_exported_transition_matrix_is_the_full_declared_edge_set(self) -> None:
        self.assertEqual(VERIFICATION_TRANSITION_MATRIX, EXPECTED_MATRIX)
        self.assertEqual(
            set(CANONICAL_VERIFICATION_STATES),
            {"source_stated", "user_verified", "imported", "inferred", "unknown"},
        )
        self.assertEqual(set(VERIFICATION_TRANSITION_MATRIX.values()), set(AUTHORITY_KINDS))

    def test_every_allowed_edge_requires_its_exact_authority_and_every_other_edge_is_disallowed(self) -> None:
        authorities = _authorities()
        for prior_state in CANONICAL_VERIFICATION_STATES:
            for new_state in CANONICAL_VERIFICATION_STATES:
                required = VERIFICATION_TRANSITION_MATRIX.get((prior_state, new_state))
                with self.subTest(prior_state=prior_state, new_state=new_state):
                    if required is None:
                        with self.assertRaises(DisallowedTransitionError) as raised:
                            evaluate_verification_transition("fact_1", prior_state, new_state, authorities[AUTHORITY_USER_AFFIRMED_PROPOSAL], FIXED_TIME)
                        self.assertIsNone(raised.exception.requiredAuthority)
                    else:
                        transition = evaluate_verification_transition("fact_1", prior_state, new_state, authorities[required], FIXED_TIME)
                        self.assertEqual(transition.priorState, prior_state)
                        self.assertEqual(transition.newState, new_state)
                        self.assertEqual(transition.authorityKind, required)
                        for authority_kind, authority in authorities.items():
                            if authority_kind == required:
                                continue
                            with self.assertRaises(DisallowedTransitionError):
                                evaluate_verification_transition("fact_1", prior_state, new_state, authority, FIXED_TIME)

    def test_authority_validation_is_structural_for_each_authority_kind(self) -> None:
        malformed_by_required_kind = {
            AUTHORITY_AGENT_INFERENCE_PROVENANCE: agent_inference_provenance_authority({"source": "agent", "text": "No rationale."}),
            AUTHORITY_EXPLICIT_USER_CORRECTION: explicit_user_correction_authority(_proposal(confirmed_value=None)),
            AUTHORITY_IMPORT_PROVENANCE: import_provenance_authority({"source": "external_system", "text": "No import anchor."}),
            AUTHORITY_SOURCE_DOCUMENT_EVIDENCE: source_document_evidence_authority({"source": "resume", "text": "No document anchor."}),
            AUTHORITY_USER_AFFIRMED_PROPOSAL: user_affirmed_proposal_authority(_proposal(source="agent")),
        }
        example_edge_by_required_kind = {
            AUTHORITY_AGENT_INFERENCE_PROVENANCE: ("unknown", "inferred"),
            AUTHORITY_EXPLICIT_USER_CORRECTION: ("user_verified", "unknown"),
            AUTHORITY_IMPORT_PROVENANCE: ("unknown", "imported"),
            AUTHORITY_SOURCE_DOCUMENT_EVIDENCE: ("inferred", "source_stated"),
            AUTHORITY_USER_AFFIRMED_PROPOSAL: ("inferred", "user_verified"),
        }
        for required_kind, authority in malformed_by_required_kind.items():
            with self.subTest(required_kind=required_kind):
                prior_state, new_state = example_edge_by_required_kind[required_kind]
                with self.assertRaises(DisallowedTransitionError):
                    evaluate_verification_transition("fact_1", prior_state, new_state, authority, FIXED_TIME)

    def test_transition_evidence_payload_contains_required_fields_for_each_authority_kind(self) -> None:
        authorities = _authorities()
        representative_edges = {
            AUTHORITY_AGENT_INFERENCE_PROVENANCE: ("unknown", "inferred"),
            AUTHORITY_EXPLICIT_USER_CORRECTION: ("user_verified", "unknown"),
            AUTHORITY_IMPORT_PROVENANCE: ("unknown", "imported"),
            AUTHORITY_SOURCE_DOCUMENT_EVIDENCE: ("inferred", "source_stated"),
            AUTHORITY_USER_AFFIRMED_PROPOSAL: ("inferred", "user_verified"),
        }
        for authority_kind, edge in representative_edges.items():
            with self.subTest(authority_kind=authority_kind):
                transition = evaluate_verification_transition("fact_1", edge[0], edge[1], authorities[authority_kind], FIXED_TIME)
                row = transition_evidence_row(transition)
                payload = row["metadata"]["verification_transition"]
                self.assertEqual(
                    payload,
                    {
                        "factId": "fact_1",
                        "priorState": edge[0],
                        "newState": edge[1],
                        "authorityKind": authority_kind,
                        "provenanceRefs": authorities[authority_kind].provenanceRefs,
                        "createdAt": FIXED_TIME,
                    },
                )

    def test_verify_fact_appends_transition_evidence_inside_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            fact = store.upsertFact(
                {"type": "skill", "text": "React", "normalized_terms": ["react"], "verification_state": "inferred"},
                {"source": "agent_proposal", "text": "possible React match"},
                source="agent_proposal",
                policy={"allow_inferred_final": False},
            )

            result = store.verifyFact(
                fact["fact_id"],
                "user_verified",
                confirmation={
                    "factId": fact["fact_id"],
                    "questionId": "question_1",
                    "outcome": "affirmed",
                    "provenance": [{"source": "user_answer", "text": "Yes, I built React apps."}],
                },
                source="user_answer",
            )

            self.assertEqual(result["status"], "updated")
            self.assertEqual(result["transaction_result"]["status"], "committed")
            self.assertIn("verification_transition_evidence_id", result["transaction_result"]["ids"])
            transition_rows = [
                row
                for row in store.getFact(fact["fact_id"])["evidence"]
                if row["metadata"].get("verification_transition", {}).get("authorityKind") == AUTHORITY_USER_AFFIRMED_PROPOSAL
            ]
            self.assertEqual(len(transition_rows), 1)
            payload = transition_rows[0]["metadata"]["verification_transition"]
            self.assertEqual(payload["factId"], fact["fact_id"])
            self.assertEqual(payload["priorState"], "inferred")
            self.assertEqual(payload["newState"], "user_verified")
            self.assertEqual(payload["createdAt"], FIXED_TIME)
            self.assertEqual(payload["provenanceRefs"], [{"source": "user_answer", "text": "Yes, I built React apps."}])

    def test_verify_fact_rejects_inferred_to_source_stated_without_source_document_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = openCareerStore(str(Path(directory) / "career.db"), clock=lambda: FIXED_TIME)
            fact = store.upsertFact(
                {"type": "skill", "text": "AWS", "normalized_terms": ["aws"], "verification_state": "inferred"},
                {"source": "agent_proposal", "text": "possible AWS match"},
                source="agent_proposal",
                policy={"allow_inferred_final": False},
            )

            result = store.verifyFact(
                fact["fact_id"],
                "source_stated",
                confirmation={
                    "factId": fact["fact_id"],
                    "outcome": "affirmed",
                    "provenance": [{"source": "user_answer", "text": "Yes."}],
                },
                source="user_answer",
            )

            self.assertEqual(result["status"], "error")
            self.assertEqual(result["mutation_status"], "rejected")
            self.assertEqual(result["verification_state"], "inferred")
            self.assertEqual(result["errors"][0]["type"], DisallowedTransitionError.__name__)
            self.assertEqual(result["errors"][0]["requiredAuthority"], AUTHORITY_SOURCE_DOCUMENT_EVIDENCE)
            self.assertEqual(store.getFact(fact["fact_id"])["fact"]["verification_state"], "inferred")


if __name__ == "__main__":
    unittest.main()
