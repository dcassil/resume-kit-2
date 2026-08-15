"""Verification-state transition policy for career-store."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .confirmations import USER_CONFIRMATION_SOURCES
from .schemas import InterpretationProposal


JsonObject = dict[str, Any]

# State vocabulary only; transitions to user_verified require explicit confirmation authority below.
SOURCE_STATED_STATE = "source_stated"
USER_VERIFIED_STATE = "user_verified"
IMPORTED_STATE = "imported"
INFERRED_STATE = "inferred"
UNKNOWN_STATE = "unknown"

CANONICAL_VERIFICATION_STATES: tuple[str, ...] = (
    SOURCE_STATED_STATE,
    USER_VERIFIED_STATE,
    IMPORTED_STATE,
    INFERRED_STATE,
    UNKNOWN_STATE,
)

AUTHORITY_USER_AFFIRMED_PROPOSAL = "user_affirmed_proposal"
AUTHORITY_SOURCE_DOCUMENT_EVIDENCE = "source_document_evidence"
AUTHORITY_IMPORT_PROVENANCE = "import_provenance"
AUTHORITY_AGENT_INFERENCE_PROVENANCE = "agent_inference_provenance"
AUTHORITY_EXPLICIT_USER_CORRECTION = "explicit_user_correction"

AUTHORITY_KINDS: tuple[str, ...] = (
    AUTHORITY_AGENT_INFERENCE_PROVENANCE,
    AUTHORITY_EXPLICIT_USER_CORRECTION,
    AUTHORITY_IMPORT_PROVENANCE,
    AUTHORITY_SOURCE_DOCUMENT_EVIDENCE,
    AUTHORITY_USER_AFFIRMED_PROPOSAL,
)

VERIFICATION_TRANSITION_MATRIX: dict[tuple[str, str], str] = {
    (UNKNOWN_STATE, INFERRED_STATE): AUTHORITY_AGENT_INFERENCE_PROVENANCE,
    (UNKNOWN_STATE, SOURCE_STATED_STATE): AUTHORITY_SOURCE_DOCUMENT_EVIDENCE,
    (UNKNOWN_STATE, IMPORTED_STATE): AUTHORITY_IMPORT_PROVENANCE,
    (UNKNOWN_STATE, USER_VERIFIED_STATE): AUTHORITY_USER_AFFIRMED_PROPOSAL,
    (INFERRED_STATE, SOURCE_STATED_STATE): AUTHORITY_SOURCE_DOCUMENT_EVIDENCE,
    (INFERRED_STATE, IMPORTED_STATE): AUTHORITY_IMPORT_PROVENANCE,
    (INFERRED_STATE, USER_VERIFIED_STATE): AUTHORITY_USER_AFFIRMED_PROPOSAL,
    (IMPORTED_STATE, SOURCE_STATED_STATE): AUTHORITY_SOURCE_DOCUMENT_EVIDENCE,
    (IMPORTED_STATE, USER_VERIFIED_STATE): AUTHORITY_USER_AFFIRMED_PROPOSAL,
    (SOURCE_STATED_STATE, USER_VERIFIED_STATE): AUTHORITY_USER_AFFIRMED_PROPOSAL,
    (USER_VERIFIED_STATE, SOURCE_STATED_STATE): AUTHORITY_EXPLICIT_USER_CORRECTION,
    (USER_VERIFIED_STATE, IMPORTED_STATE): AUTHORITY_EXPLICIT_USER_CORRECTION,
    (USER_VERIFIED_STATE, INFERRED_STATE): AUTHORITY_EXPLICIT_USER_CORRECTION,
    (USER_VERIFIED_STATE, UNKNOWN_STATE): AUTHORITY_EXPLICIT_USER_CORRECTION,
}


@dataclass(frozen=True)
class VerificationAuthority:
    authorityKind: str
    provenanceRefs: list[JsonObject]
    payload: JsonObject = field(default_factory=dict)

    @property
    def authority_kind(self) -> str:
        return self.authorityKind

    @property
    def provenance_refs(self) -> list[JsonObject]:
        return self.provenanceRefs


@dataclass(frozen=True)
class VerificationTransition:
    factId: str
    priorState: str
    newState: str
    authorityKind: str
    provenanceRefs: list[JsonObject]
    createdAt: str

    @property
    def fact_id(self) -> str:
        return self.factId

    @property
    def prior_state(self) -> str:
        return self.priorState

    @property
    def new_state(self) -> str:
        return self.newState

    @property
    def authority_kind(self) -> str:
        return self.authorityKind

    @property
    def provenance_refs(self) -> list[JsonObject]:
        return self.provenanceRefs

    @property
    def created_at(self) -> str:
        return self.createdAt


class DisallowedTransitionError(ValueError):
    """Raised when a verification-state transition lacks the exact required authority."""

    def __init__(self, from_state: str, to_state: str, required_authority: str | None) -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.requiredAuthority = required_authority
        self.required_authority = required_authority
        required = required_authority or "declared transition"
        super().__init__(f"Disallowed verification transition {from_state} -> {to_state}; requires {required}.")

    def to_error(self) -> JsonObject:
        return {
            "type": self.__class__.__name__,
            "code": "disallowed_verification_transition",
            "from": self.from_state,
            "to": self.to_state,
            "requiredAuthority": self.requiredAuthority,
            "message": str(self),
        }


def user_affirmed_proposal_authority(proposal: InterpretationProposal) -> VerificationAuthority:
    if not _is_interpretation_proposal(proposal) or proposal.outcome != "affirmed":
        return _invalid_authority(AUTHORITY_USER_AFFIRMED_PROPOSAL)
    if not _has_user_provenance(proposal.provenance):
        return _invalid_authority(AUTHORITY_USER_AFFIRMED_PROPOSAL)
    return VerificationAuthority(
        AUTHORITY_USER_AFFIRMED_PROPOSAL,
        [dict(ref) for ref in proposal.provenance],
        {
            "factId": proposal.factId,
            "questionId": proposal.questionId,
            "outcome": proposal.outcome,
            "confirmedValue": proposal.confirmedValue,
        },
    )


def source_document_evidence_authority(evidence_ref: JsonObject) -> VerificationAuthority:
    if not _is_structured_ref(evidence_ref) or not _has_document_anchor(evidence_ref):
        return _invalid_authority(AUTHORITY_SOURCE_DOCUMENT_EVIDENCE)
    return VerificationAuthority(AUTHORITY_SOURCE_DOCUMENT_EVIDENCE, [dict(evidence_ref)])


def import_provenance_authority(provenance_ref: JsonObject) -> VerificationAuthority:
    if not _is_structured_ref(provenance_ref) or not _has_import_anchor(provenance_ref):
        return _invalid_authority(AUTHORITY_IMPORT_PROVENANCE)
    return VerificationAuthority(AUTHORITY_IMPORT_PROVENANCE, [dict(provenance_ref)])


def agent_inference_provenance_authority(provenance_ref: JsonObject) -> VerificationAuthority:
    if not _is_structured_ref(provenance_ref) or not _has_inference_anchor(provenance_ref):
        return _invalid_authority(AUTHORITY_AGENT_INFERENCE_PROVENANCE)
    return VerificationAuthority(AUTHORITY_AGENT_INFERENCE_PROVENANCE, [dict(provenance_ref)])


def explicit_user_correction_authority(proposal: InterpretationProposal) -> VerificationAuthority:
    if not _is_interpretation_proposal(proposal) or proposal.outcome != "affirmed":
        return _invalid_authority(AUTHORITY_EXPLICIT_USER_CORRECTION)
    if not _has_user_provenance(proposal.provenance) or proposal.confirmedValue is None:
        return _invalid_authority(AUTHORITY_EXPLICIT_USER_CORRECTION)
    return VerificationAuthority(
        AUTHORITY_EXPLICIT_USER_CORRECTION,
        [dict(ref) for ref in proposal.provenance],
        {
            "factId": proposal.factId,
            "questionId": proposal.questionId,
            "outcome": proposal.outcome,
            "confirmedValue": proposal.confirmedValue,
        },
    )


def evaluate_verification_transition(
    fact_id: str,
    prior_state: str,
    new_state: str,
    authority: VerificationAuthority,
    created_at: str,
) -> VerificationTransition:
    required = VERIFICATION_TRANSITION_MATRIX.get((prior_state, new_state))
    if required is None or authority.authorityKind != required or not authority.provenanceRefs:
        raise DisallowedTransitionError(prior_state, new_state, required)
    return VerificationTransition(
        factId=fact_id,
        priorState=prior_state,
        newState=new_state,
        authorityKind=authority.authorityKind,
        provenanceRefs=[dict(ref) for ref in authority.provenanceRefs],
        createdAt=created_at,
    )


def transition_evidence_row(transition: VerificationTransition) -> JsonObject:
    payload = {
        "factId": transition.factId,
        "priorState": transition.priorState,
        "newState": transition.newState,
        "authorityKind": transition.authorityKind,
        "provenanceRefs": [dict(ref) for ref in transition.provenanceRefs],
        "createdAt": transition.createdAt,
    }
    return {
        "source": "verification_transition",
        "source_id": f"{transition.priorState}->{transition.newState}",
        "text": f"Verification transition {transition.priorState} -> {transition.newState}",
        "metadata": {"verification_transition": payload},
        "observed_at": transition.createdAt,
    }


def _invalid_authority(kind: str) -> VerificationAuthority:
    return VerificationAuthority(f"invalid:{kind}", [])


def _is_interpretation_proposal(value: Any) -> bool:
    return (
        isinstance(value, InterpretationProposal)
        and isinstance(value.factId, str)
        and bool(value.factId.strip())
        and isinstance(value.outcome, str)
        and isinstance(value.provenance, list)
        and bool(value.provenance)
        and all(_is_structured_ref(ref) for ref in value.provenance)
    )


def _is_structured_ref(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("source"), str) and bool(value["source"].strip()) and isinstance(
        value.get("text"), str
    ) and bool(value["text"].strip())


def _has_user_provenance(provenance_refs: list[JsonObject]) -> bool:
    return any(ref.get("source") in USER_CONFIRMATION_SOURCES for ref in provenance_refs if isinstance(ref, dict))


def _has_document_anchor(ref: JsonObject) -> bool:
    metadata = ref.get("metadata")
    return (
        isinstance(ref.get("source_id"), str)
        and bool(ref["source_id"].strip())
        or isinstance(ref.get("source_span"), dict)
        or isinstance(metadata, dict)
        and any(metadata.get(key) for key in ("document_id", "resume_id", "claim_id"))
    )


def _has_import_anchor(ref: JsonObject) -> bool:
    metadata = ref.get("metadata")
    return isinstance(metadata, dict) and any(metadata.get(key) for key in ("import_id", "external_id", "import_source"))


def _has_inference_anchor(ref: JsonObject) -> bool:
    metadata = ref.get("metadata")
    return isinstance(metadata, dict) and any(metadata.get(key) for key in ("agent_id", "model", "rationale", "inference_id"))


__all__ = [
    "AUTHORITY_AGENT_INFERENCE_PROVENANCE",
    "AUTHORITY_EXPLICIT_USER_CORRECTION",
    "AUTHORITY_IMPORT_PROVENANCE",
    "AUTHORITY_KINDS",
    "AUTHORITY_SOURCE_DOCUMENT_EVIDENCE",
    "AUTHORITY_USER_AFFIRMED_PROPOSAL",
    "CANONICAL_VERIFICATION_STATES",
    "DisallowedTransitionError",
    "VERIFICATION_TRANSITION_MATRIX",
    "VerificationAuthority",
    "VerificationTransition",
    "agent_inference_provenance_authority",
    "evaluate_verification_transition",
    "explicit_user_correction_authority",
    "import_provenance_authority",
    "source_document_evidence_authority",
    "transition_evidence_row",
    "user_affirmed_proposal_authority",
]
