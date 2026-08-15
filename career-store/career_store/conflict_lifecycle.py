"""Conflict lifecycle adjudication for career-store."""

from __future__ import annotations

from typing import Any

from .interactions import _record_interaction_in_transaction
from .schemas import InterpretationProposal
from .store_support import CONFLICT_TERMINAL_STATUSES, _clean_result, _conflict_from_row, _state_value, _to_json
from .transactions import transaction_result_payload
from .verification import (
    DisallowedTransitionError,
    evaluate_verification_transition,
    explicit_user_correction_authority,
    user_affirmed_proposal_authority,
)


JsonObject = dict[str, Any]
_VERIFICATION_STATES = {"source_stated", "user_verified", "imported", "inferred", "unknown"}


class ConflictAdjudicationError(ValueError):
    """Typed validation error for conflict lifecycle adjudication."""

    def __init__(
        self,
        code: str,
        field_path: str,
        message: str,
        allowed_values: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.field_path = field_path
        self.message = message
        self.allowed_values = allowed_values

    def to_error(self) -> JsonObject:
        payload: JsonObject = {
            "type": self.__class__.__name__,
            "code": self.code,
            "field_path": self.field_path,
            "message": self.message,
        }
        if self.allowed_values is not None:
            payload["allowed_values"] = self.allowed_values
        return payload


def _adjudicate_conflict(store: Any, schema_version: str, conflictId: str, decision: str | JsonObject, provenance: list[JsonObject]) -> JsonObject:
    conflict_id = str(conflictId)
    now = store._clock()
    try:
        clean_decision = _validate_conflict_decision(decision)
        clean_provenance = _validate_conflict_adjudication_provenance(provenance)
    except ConflictAdjudicationError as exc:
        return _conflict_adjudication_error(store, schema_version, conflict_id, exc, current_status="unknown")

    resolution_payload: JsonObject = {
        "decision": clean_decision,
        "provenance": clean_provenance,
    }
    with store._transaction("adjudicateConflict", "updated") as txn:
        conn = txn.connection
        assert conn is not None
        txn.touch("conflict_id", conflict_id)
        row = conn.execute("SELECT * FROM conflicts WHERE conflict_id = ?", (conflict_id,)).fetchone()
        if row is None:
            txn.set_mutation_status("rejected")
            result = _conflict_adjudication_error(
                store,
                schema_version,
                conflict_id,
                ConflictAdjudicationError(
                    "unknown_conflict_id",
                    "conflictId",
                    "Conflict ID does not reference an existing conflict.",
                ),
                current_status="unknown",
            )
            result["transaction_result"] = None
        else:
            current = _conflict_from_row(row)
            current_status = str(current["status"])
            if current_status in CONFLICT_TERMINAL_STATUSES:
                if _is_identical_adjudication(current, clean_decision, clean_provenance):
                    txn.set_mutation_status("unchanged")
                    result = {
                        "schema_version": schema_version,
                        "status": "unchanged",
                        "mutation_status": "unchanged",
                        "conflict_id": conflict_id,
                        "conflict": current,
                        "verification_state": None,
                        "interaction_id": None,
                        "transaction_result": None,
                        "audit": store._audit("adjudicateConflict", mutated=True, idempotent=True),
                    }
                else:
                    txn.set_mutation_status("rejected")
                    result = _conflict_adjudication_error(
                        store,
                        schema_version,
                        conflict_id,
                        ConflictAdjudicationError(
                            "conflicting_readjudication",
                            "decision",
                            "Conflict has already been adjudicated with a different decision.",
                        ),
                        current_status=current_status,
                    )
                    result["transaction_result"] = None
            else:
                transition_result = _apply_adjudication_verification_transition(
                    store,
                    schema_version,
                    conn,
                    txn,
                    conflict_id,
                    clean_decision,
                    clean_provenance,
                    current_status,
                    now,
                )
                if transition_result.get("status") == "error":
                    result = transition_result
                    result["transaction_result"] = None
                else:
                    resolution_payload["interaction_type"] = "answer_recorded"
                    conn.execute(
                        """
                        UPDATE conflicts
                        SET status = ?, resolution_provenance_json = ?, resolved_at = ?, winning_claim_ref = ?
                        WHERE conflict_id = ?
                        """,
                        (
                            clean_decision["status"],
                            _to_json(resolution_payload),
                            now,
                            clean_decision.get("winning_claim_ref"),
                            conflict_id,
                        ),
                    )
                    interaction = _record_interaction_in_transaction(
                        conn,
                        txn,
                        "answer_recorded",
                        conflict_id,
                        {
                            "conflict_id": conflict_id,
                            "decision": clean_decision,
                            "provenance": clean_provenance,
                        },
                        {
                            "status": clean_decision["status"],
                            "winning_claim_ref": clean_decision.get("winning_claim_ref"),
                            "verification_state": transition_result.get("verification_state"),
                        },
                        now,
                    )
                    updated = conn.execute("SELECT * FROM conflicts WHERE conflict_id = ?", (conflict_id,)).fetchone()
                    assert updated is not None
                    result = {
                        "schema_version": schema_version,
                        "status": "updated",
                        "mutation_status": "updated",
                        "conflict_id": conflict_id,
                        "conflict": _conflict_from_row(updated),
                        "verification_state": transition_result.get("verification_state"),
                        "interaction_id": interaction["id"],
                        "transaction_result": None,
                        "audit": store._audit("adjudicateConflict", mutated=True),
                    }
    result["transaction_result"] = transaction_result_payload(txn.result)
    return _clean_result(result)


def _apply_adjudication_verification_transition(
    store: Any,
    schema_version: str,
    conn: Any,
    txn: Any,
    conflict_id: str,
    decision: JsonObject,
    provenance: list[JsonObject],
    current_status: str,
    now: str,
) -> JsonObject:
    requested_state = decision.get("verification_state")
    if requested_state is None:
        return {"status": "ok", "verification_state": None}
    target_fact_id = str(decision.get("fact_id") or decision.get("winning_claim_ref") or "")
    fact_row = store._fact_row(target_fact_id, conn=conn) if target_fact_id else None
    if fact_row is None:
        txn.set_mutation_status("rejected")
        return _conflict_adjudication_error(
            store,
            schema_version,
            conflict_id,
            ConflictAdjudicationError(
                "unknown_fact_id",
                "decision.fact_id",
                "Verification-changing adjudication must reference an existing fact.",
            ),
            current_status=current_status,
        )
    current_state = str(fact_row["verification_state"])
    if requested_state == current_state:
        return {"status": "ok", "verification_state": current_state}
    try:
        proposal = _adjudication_proposal(target_fact_id, decision, provenance)
        authority = user_affirmed_proposal_authority(proposal)
        if current_state == "user_verified" and requested_state != current_state:
            authority = explicit_user_correction_authority(proposal)
        transition = evaluate_verification_transition(
            target_fact_id,
            current_state,
            str(requested_state),
            authority,
            now,
        )
    except DisallowedTransitionError as exc:
        txn.set_mutation_status("rejected")
        result = store._disallowed_transition_error(
            target_fact_id,
            current_state,
            exc,
            "conflict_adjudication",
            "adjudicateConflict",
        )
        result["conflict_id"] = conflict_id
        return result
    conn.execute(
        "UPDATE facts SET verification_state = ?, updated_at = ? WHERE fact_id = ?",
        (requested_state, now, target_fact_id),
    )
    evidence_id = store._insert_transition_evidence(conn, transition, now)
    txn.touch("verification_transition_evidence_id", evidence_id)
    return {"status": "ok", "verification_state": str(requested_state)}


def _conflict_adjudication_error(
    store: Any,
    schema_version: str,
    conflict_id: str,
    error: ConflictAdjudicationError,
    current_status: str,
) -> JsonObject:
    return _clean_result(
        {
            "schema_version": schema_version,
            "status": "error",
            "mutation_status": "rejected",
            "conflict_id": conflict_id,
            "current_status": current_status,
            "conflict": None,
            "verification_state": None,
            "interaction_id": None,
            "errors": [error.to_error()],
            "audit": store._audit("adjudicateConflict", mutated=False, reason=error.code),
        }
    )


def _validate_conflict_decision(decision: str | JsonObject) -> JsonObject:
    if isinstance(decision, str):
        raw: JsonObject = {"status": decision}
    elif isinstance(decision, dict):
        raw = dict(decision)
    else:
        raise ConflictAdjudicationError(
            "invalid_conflict_decision",
            "decision",
            "Conflict decision must be 'resolved', 'dismissed', or a decision object.",
            ["dismissed", "resolved"],
        )
    status = raw.get("status", raw.get("decision"))
    if status not in {"resolved", "dismissed"}:
        raise ConflictAdjudicationError(
            "invalid_conflict_decision",
            "decision.status",
            "Conflict decision must be resolved or dismissed.",
            ["dismissed", "resolved"],
        )
    clean: JsonObject = {"status": str(status)}
    winning_claim_ref = raw.get("winning_claim_ref", raw.get("winningClaimRef"))
    if status == "resolved":
        if not isinstance(winning_claim_ref, str) or not winning_claim_ref.strip():
            raise ConflictAdjudicationError(
                "missing_winning_claim_ref",
                "decision.winning_claim_ref",
                "Resolved conflicts require a non-empty winning_claim_ref.",
            )
        clean["winning_claim_ref"] = winning_claim_ref.strip()
    elif isinstance(winning_claim_ref, str) and winning_claim_ref.strip():
        clean["winning_claim_ref"] = winning_claim_ref.strip()
    fact_id = raw.get("fact_id", raw.get("factId"))
    if fact_id is not None:
        if not isinstance(fact_id, str) or not fact_id.strip():
            raise ConflictAdjudicationError(
                "invalid_conflict_decision",
                "decision.fact_id",
                "decision.fact_id must be a non-empty string when provided.",
            )
        clean["fact_id"] = fact_id.strip()
    verification_state = raw.get("verification_state", raw.get("verificationState"))
    if verification_state is not None:
        verification_state = _state_value(verification_state)
        if verification_state not in _VERIFICATION_STATES:
            raise ConflictAdjudicationError(
                "invalid_verification_state",
                "decision.verification_state",
                "decision.verification_state must be a canonical verification state.",
                sorted(_VERIFICATION_STATES),
            )
        if not clean.get("fact_id") and not clean.get("winning_claim_ref"):
            raise ConflictAdjudicationError(
                "missing_fact_ref",
                "decision.fact_id",
                "Verification-changing adjudication must provide fact_id or winning_claim_ref.",
            )
        clean["verification_state"] = verification_state
    question_id = raw.get("question_id", raw.get("questionId"))
    if question_id is not None:
        if not isinstance(question_id, str) or not question_id.strip():
            raise ConflictAdjudicationError(
                "invalid_conflict_decision",
                "decision.question_id",
                "decision.question_id must be a non-empty string when provided.",
            )
        clean["question_id"] = question_id.strip()
    if "confirmedValue" in raw:
        clean["confirmed_value"] = raw.get("confirmedValue")
    elif "confirmed_value" in raw:
        clean["confirmed_value"] = raw.get("confirmed_value")
    return clean


def _validate_conflict_adjudication_provenance(provenance: Any) -> list[JsonObject]:
    if not isinstance(provenance, list) or not provenance:
        raise ConflictAdjudicationError(
            "missing_provenance",
            "provenance",
            "Conflict adjudication provenance must be a non-empty ProvenanceRef array.",
        )
    clean: list[JsonObject] = []
    for index, entry in enumerate(provenance):
        if not isinstance(entry, dict):
            raise ConflictAdjudicationError(
                "malformed_provenance",
                f"provenance/{index}",
                "Each ProvenanceRef must be an object.",
            )
        source = entry.get("source", entry.get("kind"))
        text = entry.get("text")
        if not isinstance(source, str) or not source.strip() or not isinstance(text, str) or not text.strip():
            raise ConflictAdjudicationError(
                "malformed_provenance",
                f"provenance/{index}",
                "Each ProvenanceRef requires non-empty source and text fields.",
            )
        clean_entry = dict(entry)
        clean_entry["source"] = source.strip()
        clean.append(clean_entry)
    return clean


def _adjudication_proposal(fact_id: str, decision: JsonObject, provenance: list[JsonObject]) -> InterpretationProposal:
    return InterpretationProposal(
        factId=fact_id,
        questionId=decision.get("question_id"),
        outcome="affirmed",
        confirmedValue=decision.get("confirmed_value", decision.get("winning_claim_ref")),
        provenance=[dict(ref) for ref in provenance],
    )


def _is_identical_adjudication(conflict: JsonObject, decision: JsonObject, provenance: list[JsonObject]) -> bool:
    resolution = conflict.get("resolution_provenance")
    if not isinstance(resolution, dict):
        return False
    return (
        conflict.get("status") == decision.get("status")
        and conflict.get("winning_claim_ref") == decision.get("winning_claim_ref")
        and resolution.get("decision") == decision
        and resolution.get("provenance") == provenance
    )
