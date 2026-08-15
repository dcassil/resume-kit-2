"""Interpretation proposal validation for career-store verification."""

from __future__ import annotations

from typing import Any

from .schemas import (
    INTERPRETATION_PROPOSAL_OUTCOMES,
    InterpretationProposal,
    InvalidInterpretationProposalError,
    InvalidRelationshipConfirmationError,
)


JsonObject = dict[str, Any]
USER_CONFIRMATION_SOURCES = {"user_answer", "user_confirmation", "manual_confirmation", "explicit_user_answer"}


def validate_interpretation_proposal(value: Any, expected_fact_id: str, fact_exists: bool) -> InterpretationProposal:
    if not isinstance(value, dict):
        raise InvalidInterpretationProposalError(
            "malformed_interpretation_proposal",
            "confirmation",
            "verifyFact confirmation must be an InterpretationProposal object.",
        )
    fact_id = value.get("factId")
    if not isinstance(fact_id, str) or not fact_id.strip():
        raise InvalidInterpretationProposalError(
            "malformed_interpretation_proposal",
            "confirmation.factId",
            "InterpretationProposal.factId must be a non-empty string.",
        )
    if fact_id != expected_fact_id:
        raise InvalidInterpretationProposalError(
            "fact_id_mismatch",
            "confirmation.factId",
            "InterpretationProposal.factId must match the verifyFact fact_id.",
        )
    if not fact_exists:
        raise InvalidInterpretationProposalError(
            "unknown_fact_id",
            "confirmation.factId",
            "InterpretationProposal.factId does not reference an existing fact.",
        )
    outcome = value.get("outcome")
    if outcome not in INTERPRETATION_PROPOSAL_OUTCOMES:
        raise InvalidInterpretationProposalError(
            "unknown_outcome",
            "confirmation.outcome",
            "InterpretationProposal.outcome must be affirmed, denied, or unclear.",
            sorted(INTERPRETATION_PROPOSAL_OUTCOMES),
        )
    provenance = value.get("provenance")
    if not isinstance(provenance, list) or not provenance:
        raise InvalidInterpretationProposalError(
            "missing_provenance",
            "confirmation.provenance",
            "InterpretationProposal.provenance must be a non-empty ProvenanceRef array.",
        )
    clean_provenance: list[JsonObject] = []
    for index, entry in enumerate(provenance):
        if not isinstance(entry, dict):
            raise InvalidInterpretationProposalError(
                "malformed_provenance",
                f"confirmation.provenance/{index}",
                "Each ProvenanceRef must be an object.",
            )
        source = entry.get("source", entry.get("kind"))
        text = entry.get("text")
        if not isinstance(source, str) or not source.strip() or not isinstance(text, str) or not text.strip():
            raise InvalidInterpretationProposalError(
                "malformed_provenance",
                f"confirmation.provenance/{index}",
                "Each ProvenanceRef requires non-empty source and text fields.",
            )
        clean_provenance.append(dict(entry))
    question_id = value.get("questionId")
    if question_id is not None and (not isinstance(question_id, str) or not question_id.strip()):
        raise InvalidInterpretationProposalError(
            "malformed_interpretation_proposal",
            "confirmation.questionId",
            "InterpretationProposal.questionId must be a non-empty string when provided.",
        )
    return InterpretationProposal(
        factId=fact_id,
        questionId=question_id,
        outcome=str(outcome),
        confirmedValue=value.get("confirmedValue"),
        provenance=clean_provenance,
    )


def proposal_has_user_provenance(proposal: InterpretationProposal) -> bool:
    for entry in proposal.provenance:
        source = str(entry.get("source", entry.get("kind", "")))
        if source in USER_CONFIRMATION_SOURCES:
            return True
    return False


def validate_user_confirmation_provenance(value: Any, field_path: str = "provenance") -> list[JsonObject]:
    if not isinstance(value, list) or not value:
        raise InvalidRelationshipConfirmationError(
            "missing_user_provenance",
            field_path,
            "Relationship confirmation provenance must be a non-empty ProvenanceRef array.",
        )
    clean_provenance: list[JsonObject] = []
    has_user_source = False
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise InvalidRelationshipConfirmationError(
                "malformed_provenance",
                f"{field_path}/{index}",
                "Each ProvenanceRef must be an object.",
            )
        source = entry.get("source", entry.get("kind"))
        text = entry.get("text")
        if not isinstance(source, str) or not source.strip() or not isinstance(text, str) or not text.strip():
            raise InvalidRelationshipConfirmationError(
                "malformed_provenance",
                f"{field_path}/{index}",
                "Each ProvenanceRef requires non-empty source and text fields.",
            )
        clean_entry = dict(entry)
        clean_entry["source"] = source
        clean_provenance.append(clean_entry)
        if source in USER_CONFIRMATION_SOURCES:
            has_user_source = True
    if not has_user_source:
        raise InvalidRelationshipConfirmationError(
            "missing_user_confirmation_source",
            field_path,
            "Relationship confirmation provenance must include a structural user confirmation source.",
            sorted(USER_CONFIRMATION_SOURCES),
        )
    return clean_provenance


def proposal_evidence(proposal: InterpretationProposal, verification_state: str, source: str) -> list[JsonObject]:
    evidence_entries: list[JsonObject] = []
    proposal_metadata = {
        "interpretation_proposal": {
            "factId": proposal.factId,
            "questionId": proposal.questionId,
            "outcome": proposal.outcome,
            "confirmedValue": proposal.confirmedValue,
        },
        "verification_state": verification_state,
        "confirmation_source": source,
    }
    for entry in proposal.provenance:
        metadata = dict(entry.get("metadata", {})) if isinstance(entry.get("metadata"), dict) else {}
        metadata.update(proposal_metadata)
        evidence: JsonObject = {
            "source": str(entry.get("source", entry.get("kind", source))),
            "text": str(entry.get("text", "")),
            "metadata": metadata,
        }
        for key in ("source_id", "source_span", "observed_at"):
            if entry.get(key) is not None:
                evidence[key] = entry.get(key)
        evidence_entries.append(evidence)
    return evidence_entries
