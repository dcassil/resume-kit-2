"""Durable SQLite-backed career fact store."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from .confirmations import proposal_evidence, validate_interpretation_proposal
from .conflict_lifecycle import _adjudicate_conflict
from .interactions import _list_interactions_result, _record_interaction_result
from .migrations import (
    MIGRATIONS,
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSION,
    IncompatibleSchemaVersionError,
    MigrationFailedError,
    migration_state,
    pending_migrations,
    _record_migration,
    set_user_version,
    user_version,
)
from .schemas import InvalidInterpretationProposalError, MigrationState, TransactionResult, VerificationState
from .store_support import (
    _add_if_not_none,
    _after_merge_repoint,
    _authority_ref,
    _confirm_relationship,
    _conflict_from_row,
    _conflict_object,
    _dedupe_conflict_signals,
    _dedupe_conflicts,
    _direct_resolution,
    _expanded_terms,
    _from_json,
    _has_explicit_confirmation,
    _inference_ref,
    _insert_merge_alias_relationship,
    _job_metadata,
    _meaningful_overlap,
    _merge_alias_terms,
    _merge_conflict,
    _merge_conflict_result,
    _merge_provenance_payload,
    _merged_metadata,
    _normalize,
    _normalized_terms,
    _optional_bool, _optional_float, _optional_int, _optional_text,
    _required_years,
    _repoint_job_matches,
    _resolve_fact_id,
    _relationship_candidate,
    _relationship_conflict_signals,
    _relationship_direction,
    _relationship_policy_match_type,
    _source_document_ref, _stable_id, _state_value, _title_claim, _to_json,
    _upsert_user_proposal,
    _validation_error,
    _evidence_for_fact_matching_terms,
    _search_alias_terms, _search_allowed_fact_ids, _search_fact_concept_terms, _search_fact_match_terms,
    _search_fact_normalized_terms, _search_filters, _store_fact_match_terms, _year_claim, _year_claim_tuple,
)
from .transactions import TransactionScope, transaction_result_payload
from .verification import (
    DisallowedTransitionError,
    agent_inference_provenance_authority,
    evaluate_verification_transition,
    explicit_user_correction_authority,
    import_provenance_authority,
    source_document_evidence_authority,
    transition_evidence_row,
    user_affirmed_proposal_authority,
)

_VERIFICATION_STATES = {state.value for state in VerificationState}
_RELATIONSHIP_TYPES = {"alias", "related", "parent", "child", "equivalent", "contradicts"}
_RESOLUTION_STATES = {"exact_match", "alias_match", "verified_fact_match", "related_match", "possible_match", "unknown", "explicitly_missing", "not_applicable"}
_RESOLUTION_RANK = {"not_applicable": 0, "unknown": 1, "explicitly_missing": 2, "possible_match": 3, "related_match": 4, "alias_match": 5, "exact_match": 6, "verified_fact_match": 7}


JsonObject = dict[str, Any]


class CareerStore:
    """Small contract-driven SQLite service for career facts."""

    def __init__(self, database_path: str, clock: Callable[[], str] | None = None) -> None:
        self._database_path = str(database_path)
        self._clock = clock or _default_clock
        self._last_transaction_result: TransactionResult | None = None
        Path(self._database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def searchFacts(
        self,
        query: str,
        filters: JsonObject | None = None,
        limit: int | None = None,
        include_evidence: bool = False,
    ) -> JsonObject:
        normalized_filters = _search_filters(self, SCHEMA_VERSION, filters)
        if normalized_filters.get("status") == "error":
            return normalized_filters
        filters = normalized_filters["filters"]
        query_terms = set(_normalized_terms({"text": query, "normalized_terms": [query]}))
        term_filters = set(filters["terms"])
        concept_terms = set(filters["concept_terms"])
        alias_terms = set(filters["alias_terms"])
        matches: list[JsonObject] = []
        with self._connect() as conn:
            redirected_query_id = _resolve_fact_id(conn, query)
            allowed_fact_ids = _search_allowed_fact_ids(self, conn, filters)
            rows = [row for row in self._fact_rows(conn=conn, active_only=True) if row["fact_id"] in allowed_fact_ids]
            for row in rows:
                fact = self._fact_from_row(row, conn=conn)
                matched_terms: set[str] = set()
                query_matched = not query_terms
                if query_terms:
                    query_match = _search_fact_match_terms(fact).intersection(query_terms)
                    if query_match:
                        matched_terms.update(query_match)
                        query_matched = True
                    elif redirected_query_id == fact["fact_id"]:
                        matched_terms.update(query_terms)
                        query_matched = True
                    elif filters["alias_enabled"]:
                        alias_match = _search_alias_terms(self, fact["fact_id"], query_terms, filters, conn=conn)
                        if alias_match:
                            matched_terms.update(alias_match)
                            query_matched = True
                if not query_matched:
                    continue
                if term_filters:
                    matched_terms.update(_search_fact_normalized_terms(fact).intersection(term_filters))
                if concept_terms:
                    matched_terms.update(_search_fact_concept_terms(fact).intersection(concept_terms))
                if alias_terms:
                    matched_terms.update(_search_alias_terms(self, fact["fact_id"], alias_terms, filters, conn=conn))
                if include_evidence:
                    evidence = (
                        self._evidence_for_fact(fact["fact_id"], conn=conn)
                        if not matched_terms
                        else _evidence_for_fact_matching_terms(self, fact["fact_id"], matched_terms, conn=conn)
                    )
                    fact["evidence"] = evidence
                    fact["evidence_ids"] = [item["evidence_id"] for item in evidence]
                if query_matched:
                    matches.append(fact)
        matches.sort(key=lambda item: (item["type"], item["text"].casefold(), item["fact_id"]))
        if limit is not None:
            matches = matches[: max(0, int(limit))]
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "ok",
            "facts": matches,
            "query": query,
            "audit": self._audit("searchFacts", mutated=False),
        }

    def getFact(self, fact_id: str) -> JsonObject:
        with self._connect() as conn:
            resolved_fact_id = _resolve_fact_id(conn, fact_id)
            row = self._fact_row(resolved_fact_id, conn=conn) if resolved_fact_id else None
            if row is None:
                return {
                    "schema_version": SCHEMA_VERSION,
                    "status": "not_found",
                    "fact": None,
                    "evidence": [],
                    "relationships": [],
                    "conflicts": [],
                    "audit": self._audit("getFact", mutated=False),
                }
            fact = self._fact_from_row(row, conn=conn)
            return {
                "schema_version": SCHEMA_VERSION,
                "status": "ok",
                "fact": fact,
                "evidence": self._evidence_for_fact(fact["fact_id"], conn=conn),
                "relationships": self._relationships_for_fact(fact["fact_id"], conn=conn),
                "conflicts": self._conflicts_for_fact(fact["fact_id"], conn=conn),
                "audit": self._audit("getFact", mutated=False),
            }

    def mergeFacts(self, survivorId: str, mergedId: str, provenance: JsonObject | list[JsonObject] | None) -> JsonObject:
        survivor_id = str(survivorId)
        merged_id = str(mergedId)
        now = self._clock()
        merge_id = _stable_id("fact_merge", survivor_id, merged_id)
        with self._transaction("mergeFacts", "updated") as txn:
            conn = txn.connection
            assert conn is not None
            txn.touch("survivor_fact_id", survivor_id)
            txn.touch("merged_fact_id", merged_id)
            txn.touch("merge_id", merge_id)
            error = _merge_conflict(conn, survivor_id, merged_id)
            if error is not None:
                txn.set_mutation_status("rejected")
                result = _merge_conflict_result(
                    error,
                    SCHEMA_VERSION,
                    self._audit("mergeFacts", mutated=False, reason=error.code),
                )
                result["transaction_result"] = None
            else:
                survivor_row = self._fact_row(survivor_id, conn=conn)
                merged_row = self._fact_row(merged_id, conn=conn)
                assert survivor_row is not None
                assert merged_row is not None
                alias_terms = _merge_alias_terms(survivor_row, merged_row)
                survivor_metadata = _from_json(str(survivor_row["metadata_json"]), {})
                metadata = _merged_metadata(
                    survivor_metadata,
                    {
                        "merged_fact_ids": sorted(
                            set([*survivor_metadata.get("merged_fact_ids", []), merged_id])
                            if isinstance(survivor_metadata.get("merged_fact_ids"), list)
                            else {merged_id}
                        )
                    },
                )
                canonical_name = survivor_row["canonical_name"] or merged_row["canonical_name"]
                description = survivor_row["description"] or merged_row["description"]
                conn.execute(
                    """
                    UPDATE facts
                    SET normalized_terms_json = ?, metadata_json = ?, canonical_name = ?, description = ?, updated_at = ?
                    WHERE fact_id = ?
                    """,
                    (_to_json(alias_terms), _to_json(metadata), canonical_name, description, now, survivor_id),
                )
                _insert_merge_alias_relationship(conn, survivor_id, merged_id, provenance, now)
                conn.execute(
                    "UPDATE evidence SET fact_id = ? WHERE fact_id = ?",
                    (survivor_id, merged_id),
                )
                _repoint_job_matches(conn, survivor_id, merged_id)
                _after_merge_repoint(provenance)
                conn.execute(
                    "UPDATE facts SET merged_into_fact_id = ?, updated_at = ? WHERE fact_id = ?",
                    (survivor_id, now, merged_id),
                )
                conn.execute(
                    """
                    INSERT INTO fact_merges (
                        merge_id, survivor_fact_id, merged_fact_id, provenance_json, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (merge_id, survivor_id, merged_id, _to_json(_merge_provenance_payload(provenance)), now),
                )
                result = {
                    "schema_version": SCHEMA_VERSION,
                    "status": "updated",
                    "mutation_status": "updated",
                    "fact_id": survivor_id,
                    "survivor_fact_id": survivor_id,
                    "merged_fact_id": merged_id,
                    "merge_id": merge_id,
                    "verification_state": str(survivor_row["verification_state"]),
                    "conflicts": self._conflicts_for_fact(survivor_id, conn=conn),
                    "confirmation_required": False,
                    "transaction_result": None,
                    "audit": self._audit("mergeFacts", mutated=True),
                }
        transaction_result = txn.result
        result["transaction_result"] = transaction_result_payload(transaction_result)
        return result

    def upsertFact(
        self,
        fact: JsonObject,
        evidence: JsonObject | None,
        source: str,
        policy: JsonObject | None = None,
    ) -> JsonObject:
        policy = policy or {}
        now = self._clock()
        normalized = _normalized_terms(fact)
        fact_id = str(fact.get("fact_id") or _stable_id("fact", fact.get("type", "fact"), "|".join(normalized), fact.get("text", "")))
        requested_state = _state_value(fact.get("verification_state", "unknown"))
        if requested_state not in _VERIFICATION_STATES:
            return self._mutation_error("upsertFact", fact_id, "unknown", "invalid_verification_state", True)
        if requested_state == "user_verified" and not _has_explicit_confirmation(policy, evidence, source):
            requested_state = "unknown"
            confirmation_required = True
        else:
            confirmation_required = requested_state in {"inferred", "unknown"} and not policy.get("allow_inferred_final", True)
        mutation_status = "created"
        evidence_id: str | None = None
        result: JsonObject | None = None
        with self._transaction("upsertFact", mutation_status) as txn:
            conn = txn.connection
            assert conn is not None
            txn.touch("fact_id", fact_id)
            conflicts = self._detect_conflicts({**fact, "fact_id": fact_id, "normalized_terms": normalized}, conn=conn)
            txn.touch("conflict_ids", ",".join(conflict["conflict_id"] for conflict in conflicts))
            self._after_conflict_detection("upsertFact", policy)
            existing = conn.execute(
                "SELECT fact_id, verification_state, created_at, metadata_json FROM facts WHERE fact_id = ?",
                (fact_id,),
            ).fetchone()
            if existing is None:
                transition = None
                persisted_state = requested_state
                if requested_state != "unknown":
                    try:
                        transition = self._evaluate_upsert_transition(
                            fact_id,
                            "unknown",
                            requested_state,
                            policy,
                            evidence,
                            source,
                            now,
                        )
                    except DisallowedTransitionError as exc:
                        if requested_state == "user_verified":
                            persisted_state = "unknown"
                            confirmation_required = True
                        else:
                            txn.set_mutation_status("rejected")
                            result = self._disallowed_transition_error(fact_id, "unknown", exc, source, "upsertFact")
                            result["transaction_result"] = None
                if result is None:
                    self._insert_fact_row(conn, fact_id, fact, normalized, persisted_state, now)
                    if transition is not None:
                        evidence_id = self._insert_transition_evidence(conn, transition, now)
                        txn.touch("verification_transition_evidence_id", evidence_id)
                    requested_state = persisted_state
            else:
                mutation_status = "updated"
                txn.set_mutation_status(mutation_status)
                current_state = str(existing["verification_state"])
                next_state = current_state
                transition = None
                try:
                    transition = self._evaluate_upsert_merge_transition(
                        fact_id,
                        current_state,
                        requested_state,
                        policy,
                        evidence,
                        source,
                        now,
                    )
                except DisallowedTransitionError as exc:
                    if requested_state == "user_verified" and current_state in {"inferred", "unknown"}:
                        confirmation_required = True
                    elif current_state == "user_verified":
                        pass
                    else:
                        txn.set_mutation_status("rejected")
                        result = self._disallowed_transition_error(fact_id, current_state, exc, source, "upsertFact")
                        result["transaction_result"] = None
                else:
                    if transition is not None:
                        next_state = transition.newState
                if next_state == current_state and requested_state == "user_verified" and current_state in {"inferred", "unknown"}:
                    confirmation_required = True
                if result is None:
                    self._update_fact_row(conn, fact_id, fact, normalized, next_state, now, str(existing["metadata_json"]))
                    if transition is not None:
                        transition_evidence_id = self._insert_transition_evidence(conn, transition, now)
                        txn.touch("verification_transition_evidence_id", transition_evidence_id)
                    requested_state = next_state
            if result is None:
                if evidence:
                    evidence_id = self._insert_evidence(conn, fact_id, evidence, source, now)
                    txn.touch("evidence_id", evidence_id)
                for conflict in conflicts:
                    self._insert_conflict(conn, conflict, now)
        transaction_result = txn.result
        if result is not None:
            result["transaction_result"] = transaction_result_payload(transaction_result)
            return result
        return {
            "schema_version": SCHEMA_VERSION,
            "status": mutation_status,
            "mutation_status": mutation_status,
            "fact_id": fact_id,
            "verification_state": requested_state,
            "conflicts": conflicts,
            "confirmation_required": bool(confirmation_required),
            "transaction_result": transaction_result_payload(transaction_result),
            "audit": self._audit("upsertFact", mutated=True),
        }

    def _insert_fact_row(
        self,
        conn: sqlite3.Connection,
        fact_id: str,
        fact: JsonObject,
        normalized: list[str],
        verification_state: str,
        now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO facts (
                fact_id, type, text, normalized_terms_json, verification_state, created_at, updated_at,
                metadata_json, canonical_name, description, years, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fact_id,
                str(fact.get("type", "fact")),
                str(fact.get("text", "")),
                _to_json(normalized),
                verification_state,
                now,
                now,
                _to_json(fact.get("metadata", {})),
                _optional_text(fact.get("canonical_name")),
                _optional_text(fact.get("description")),
                _optional_int(fact.get("years")),
                _optional_float(fact.get("confidence")),
            ),
        )

    def _update_fact_row(
        self,
        conn: sqlite3.Connection,
        fact_id: str,
        fact: JsonObject,
        normalized: list[str],
        verification_state: str,
        now: str,
        existing_metadata_json: str,
    ) -> None:
        conn.execute(
            """
            UPDATE facts
            SET type = ?, text = ?, normalized_terms_json = ?, verification_state = ?, updated_at = ?,
                metadata_json = ?, canonical_name = ?, description = ?, years = ?, confidence = ?
            WHERE fact_id = ?
            """,
            (
                str(fact.get("type", "fact")),
                str(fact.get("text", "")),
                _to_json(normalized),
                verification_state,
                now,
                _to_json(_merged_metadata(_from_json(existing_metadata_json, {}), fact.get("metadata", {}))),
                _optional_text(fact.get("canonical_name")),
                _optional_text(fact.get("description")),
                _optional_int(fact.get("years")),
                _optional_float(fact.get("confidence")),
                fact_id,
            ),
        )

    def verifyFact(
        self,
        fact_id: str,
        verification_state: str,
        confirmation: JsonObject | None,
        source: str,
    ) -> JsonObject:
        requested_state = _state_value(verification_state)
        if requested_state not in _VERIFICATION_STATES:
            return self._mutation_error("verifyFact", fact_id, "unknown", "invalid_verification_state", True)
        now = self._clock()
        mutation_status = "updated"
        with self._transaction("verifyFact", mutation_status) as txn:
            conn = txn.connection
            assert conn is not None
            txn.touch("fact_id", fact_id)
            row = self._fact_row(fact_id, conn=conn)
            current_state = str(row["verification_state"]) if row is not None else "unknown"
            try:
                proposal = validate_interpretation_proposal(confirmation, expected_fact_id=fact_id, fact_exists=row is not None)
            except InvalidInterpretationProposalError as exc:
                txn.set_mutation_status("rejected")
                result = self._interpretation_proposal_error(fact_id, current_state, exc, source)
                result["transaction_result"] = None
            else:
                if proposal.outcome != "affirmed":
                    txn.set_mutation_status("evidence_only")
                    for evidence in proposal_evidence(proposal, requested_state, source):
                        evidence_id = self._insert_evidence(conn, fact_id, evidence, source, now)
                        txn.touch("evidence_id", evidence_id)
                    result = {
                        "schema_version": SCHEMA_VERSION,
                        "status": "unchanged",
                        "mutation_status": "evidence_only",
                        "fact_id": fact_id,
                        "verification_state": current_state,
                        "conflicts": self._conflicts_for_fact(fact_id, conn=conn),
                        "confirmation_required": requested_state == "user_verified",
                        "transaction_result": None,
                        "audit": self._audit("verifyFact", mutated=True, source=source, outcome=proposal.outcome),
                    }
                elif requested_state == current_state:
                    txn.set_mutation_status("evidence_only")
                    for evidence in proposal_evidence(proposal, requested_state, source):
                        evidence_id = self._insert_evidence(conn, fact_id, evidence, source, now)
                        txn.touch("evidence_id", evidence_id)
                    result = {
                        "schema_version": SCHEMA_VERSION,
                        "status": "unchanged",
                        "mutation_status": "evidence_only",
                        "fact_id": fact_id,
                        "verification_state": current_state,
                        "conflicts": self._conflicts_for_fact(fact_id, conn=conn),
                        "confirmation_required": False,
                        "transaction_result": None,
                        "audit": self._audit("verifyFact", mutated=True, source=source, outcome=proposal.outcome),
                    }
                else:
                    try:
                        if current_state == "user_verified" and requested_state != current_state:
                            authority = explicit_user_correction_authority(proposal)
                        elif requested_state == "source_stated":
                            authority = self._source_document_authority_from_refs(proposal.provenance)
                        elif requested_state == "imported":
                            authority = self._import_authority_from_refs(proposal.provenance)
                        elif requested_state == "inferred":
                            authority = self._agent_inference_authority_from_refs(proposal.provenance)
                        else:
                            authority = user_affirmed_proposal_authority(proposal)
                        transition = evaluate_verification_transition(
                            fact_id,
                            current_state,
                            requested_state,
                            authority,
                            now,
                        )
                    except DisallowedTransitionError as exc:
                        txn.set_mutation_status("rejected")
                        result = self._disallowed_transition_error(fact_id, current_state, exc, source)
                        result["transaction_result"] = None
                    else:
                        conn.execute(
                            "UPDATE facts SET verification_state = ?, updated_at = ? WHERE fact_id = ?",
                            (requested_state, now, fact_id),
                        )
                        evidence_id = self._insert_transition_evidence(conn, transition, now)
                        txn.touch("verification_transition_evidence_id", evidence_id)
                        for evidence in proposal_evidence(proposal, requested_state, source):
                            evidence_id = self._insert_evidence(conn, fact_id, evidence, source, now)
                            txn.touch("evidence_id", evidence_id)
                        result = {
                            "schema_version": SCHEMA_VERSION,
                            "status": "updated",
                            "mutation_status": "updated",
                            "fact_id": fact_id,
                            "verification_state": requested_state,
                            "conflicts": self._conflicts_for_fact(fact_id, conn=conn),
                            "confirmation_required": False,
                            "transaction_result": None,
                            "audit": self._audit("verifyFact", mutated=True, source=source, outcome=proposal.outcome),
                        }
        transaction_result = txn.result
        result["transaction_result"] = transaction_result_payload(transaction_result)
        return result

    def addEvidence(self, fact_id: str, evidence: JsonObject, source: str) -> JsonObject:
        now = self._clock()
        with self._transaction("addEvidence", "created") as txn:
            conn = txn.connection
            assert conn is not None
            txn.touch("fact_id", fact_id)
            row = self._fact_row(fact_id, conn=conn)
            if row is None:
                txn.set_mutation_status("rejected")
                result = self._mutation_error("addEvidence", fact_id, "unknown", "not_found", False)
                result["transaction_result"] = None
            else:
                evidence_id = self._insert_evidence(conn, fact_id, evidence, source, now)
                txn.touch("evidence_id", evidence_id)
                conn.execute("UPDATE facts SET updated_at = ? WHERE fact_id = ?", (now, fact_id))
                result = {
                    "schema_version": SCHEMA_VERSION,
                    "status": "created",
                    "mutation_status": "created",
                    "fact_id": fact_id,
                    "evidence_id": evidence_id,
                    "verification_state": str(row["verification_state"]),
                    "conflicts": self._conflicts_for_fact(fact_id, conn=conn),
                    "confirmation_required": False,
                    "transaction_result": None,
                    "audit": self._audit("addEvidence", mutated=True, source=source),
                }
        transaction_result = txn.result
        result["transaction_result"] = transaction_result_payload(transaction_result)
        return result

    def addRelationship(
        self,
        from_fact_id: str,
        to_fact_id: str,
        relationship_type: str,
        evidence_or_rationale: JsonObject | None,
        policy: JsonObject | None = None,
    ) -> JsonObject:
        policy = policy or {}
        relationship_type = str(relationship_type)
        if relationship_type not in _RELATIONSHIP_TYPES:
            return self._relationship_error(from_fact_id, "invalid_relationship_type", True)
        now = self._clock()
        relationship_id = _stable_id("relationship", from_fact_id, to_fact_id, relationship_type, _to_json(evidence_or_rationale or {}))
        mutation_status = "created"
        with self._transaction("addRelationship", mutation_status) as txn:
            conn = txn.connection
            assert conn is not None
            txn.touch("fact_id", from_fact_id)
            txn.touch("related_fact_id", to_fact_id)
            txn.touch("relationship_id", relationship_id)
            from_row = self._fact_row(from_fact_id, conn=conn)
            to_row = self._fact_row(to_fact_id, conn=conn)
            if from_row is None or to_row is None:
                txn.set_mutation_status("rejected")
                result = self._relationship_error(from_fact_id, "not_found", True)
                result["transaction_result"] = None
            else:
                existing = conn.execute(
                    "SELECT relationship_id FROM relationships WHERE relationship_id = ?",
                    (relationship_id,),
                ).fetchone()
                mutation_status = "updated" if existing else "created"
                txn.set_mutation_status(mutation_status)
                conn.execute(
                    """
                    INSERT INTO relationships (
                        relationship_id, from_fact_id, to_fact_id, relationship_type, evidence_json, created_at,
                        metadata_json, confidence, confirmation_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(relationship_id) DO UPDATE SET
                        evidence_json = excluded.evidence_json,
                        metadata_json = excluded.metadata_json,
                        confidence = excluded.confidence
                    """,
                    (
                        relationship_id,
                        from_fact_id,
                        to_fact_id,
                        relationship_type,
                        _to_json(evidence_or_rationale or {}),
                        now,
                        _to_json({"policy": policy}),
                        _optional_float((evidence_or_rationale or {}).get("confidence")),
                        "unconfirmed",
                    ),
                )
                status_row = conn.execute(
                    "SELECT confirmation_status FROM relationships WHERE relationship_id = ?",
                    (relationship_id,),
                ).fetchone()
                confirmation_status = str(status_row["confirmation_status"] or "unconfirmed") if status_row else "unconfirmed"
                if relationship_type == "contradicts":
                    conflict_id = _stable_id("conflict", from_fact_id, to_fact_id, relationship_type)
                    txn.touch("conflict_id", conflict_id)
                    self._insert_conflict(
                        conn,
                        {
                            "conflict_id": conflict_id,
                            "fact_ids": sorted([from_fact_id, to_fact_id]),
                            "reason": str((evidence_or_rationale or {}).get("text", "relationship contradiction")),
                            "status": "open",
                            "evidence_ids": [],
                            "metadata": {"relationship_id": relationship_id},
                        },
                        now,
                    )
                from_fact = self._fact_from_row(from_row, conn=conn)
                result = {
                    "schema_version": SCHEMA_VERSION,
                    "status": mutation_status,
                    "mutation_status": mutation_status,
                    "fact_id": from_fact_id,
                    "relationship_id": relationship_id,
                    "confirmation_status": confirmation_status,
                    "verification_state": from_fact["verification_state"],
                    "conflicts": self._conflicts_for_fact(from_fact_id, conn=conn),
                    "confirmation_required": relationship_type in {"alias", "equivalent"}
                    and confirmation_status != "user_confirmed",
                    "transaction_result": None,
                    "audit": self._audit("addRelationship", mutated=True),
                }
        transaction_result = txn.result
        result["transaction_result"] = transaction_result_payload(transaction_result)
        return result

    def confirmRelationship(self, relationshipId: str, provenance: list[JsonObject]) -> JsonObject:
        return _confirm_relationship(self, SCHEMA_VERSION, relationshipId, provenance)

    def findCandidateMatches(
        self,
        requirements: list[JsonObject],
        policy: JsonObject | None = None,
        job_id: str | None = None,
        include_evidence: bool = False,
    ) -> JsonObject:
        policy = policy or {}
        matches: list[JsonObject] = []
        unresolved: list[JsonObject] = []
        conflicts: list[JsonObject] = []
        conflict_signals: list[JsonObject] = []
        facts = [self._fact_from_row(row) for row in self._fact_rows()]
        for requirement in requirements:
            requirement_id = str(requirement.get("requirement_id", requirement.get("id", "")))
            requirement_terms = set(_expanded_terms(_normalized_terms(requirement)))
            with self._connect() as conn:
                conflict_signals.extend(
                    _relationship_conflict_signals(
                        conn,
                        requirement_id,
                        requirement_terms,
                        lambda fact_id, conn=None: _store_fact_match_terms(self, fact_id, conn=conn),
                    )
                )
            candidates = self._candidate_matches(requirement, facts, policy)
            if not candidates:
                unresolved.append(
                    {
                        "requirement_id": requirement_id,
                        "resolution_state": "unknown",
                        "concept": requirement.get("concept", requirement.get("text", "")),
                        "source_text": requirement.get("source_text", requirement.get("text", "")),
                    }
                )
                continue
            best = candidates[0]
            fact = dict(best["fact"])
            if include_evidence:
                fact["evidence"] = self._evidence_for_fact(fact["fact_id"])
            supporting_facts = []
            for candidate in candidates:
                supporting = dict(candidate["fact"])
                if include_evidence:
                    supporting["evidence"] = self._evidence_for_fact(supporting["fact_id"])
                supporting_facts.append(
                    {
                        "factId": supporting["fact_id"],
                        "fact_id": supporting["fact_id"],
                        "fact": supporting,
                        "matchType": candidate["match_type"],
                        "resolution_state": candidate["resolution_state"],
                        "match_type": candidate["resolution_state"],
                        "terms": candidate["match_terms"],
                        "match_terms": candidate["match_terms"],
                        "relationship_id": candidate.get("relationship_id"),
                        "viaRelationships": candidate.get("via_relationships", []),
                        "via_relationships": candidate.get("via_relationships", []),
                        "metadata": candidate.get("metadata", {}),
                    }
                )
            item = {
                "requirement_id": requirement_id,
                "job_id": job_id,
                "factId": fact["fact_id"],
                "fact_id": fact["fact_id"],
                "fact_ids": [candidate["fact"]["fact_id"] for candidate in candidates],
                "fact": fact,
                "supporting_facts": supporting_facts,
                "matchType": best["match_type"],
                "resolution_state": best["resolution_state"],
                "match_type": best["resolution_state"],
                "terms": best["match_terms"],
                "match_terms": best["match_terms"],
                "viaRelationships": best.get("via_relationships", []),
                "via_relationships": best.get("via_relationships", []),
                "metadata": {
                    "concept": requirement.get("concept", requirement.get("text", "")),
                    "source_text": requirement.get("source_text", requirement.get("text", "")),
                    **best.get("metadata", {}),
                },
            }
            matches.append(item)
            conflicts.extend(best.get("conflicts", []))
            for candidate in candidates:
                conflicts.extend(candidate.get("conflicts", []))
                conflicts.extend(self._conflicts_for_fact(candidate["fact"]["fact_id"]))
            if best["resolution_state"] in {"unknown", "possible_match", "related_match", "explicitly_missing"}:
                unresolved.append(
                    {
                        "requirement_id": requirement_id,
                        "resolution_state": best["resolution_state"],
                        "concept": requirement.get("concept", requirement.get("text", "")),
                        "source_text": requirement.get("source_text", requirement.get("text", "")),
                        "fact_ids": item["fact_ids"],
                    }
                )
        matches.sort(key=lambda item: (item["requirement_id"], item["resolution_state"], item["fact_id"]))
        unresolved.sort(key=lambda item: item["requirement_id"])
        conflict_signals = _dedupe_conflict_signals(conflict_signals)
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "ok",
            "matches": matches,
            "unresolved": unresolved,
            "conflicts": _dedupe_conflicts(conflicts),
            # Result contract for RKIT-I-0008: contradicts relationships are
            # not match candidates. They surface here as typed directional
            # signals shaped as {type, factId, relationshipId,
            # contradictedFactId, requirementId}.
            "conflict_signals": conflict_signals,
            "audit": self._audit("findCandidateMatches", mutated=False),
        }

    def recordJobMatch(
        self,
        job_id: str,
        requirement_id: str,
        fact_ids: list[str],
        resolution_state: str,
        metadata: JsonObject | None = None,
    ) -> JsonObject:
        resolution_state = str(resolution_state)
        if resolution_state not in _RESOLUTION_STATES:
            return self._job_match_error(job_id, requirement_id, "invalid_resolution_state")
        now = self._clock()
        clean_fact_ids = sorted(str(fact_id) for fact_id in fact_ids)
        job_match_id = _stable_id("job_match", job_id, requirement_id, "|".join(clean_fact_ids), resolution_state)
        match_type = _optional_text((metadata or {}).get("match_type")) or resolution_state
        confidence = _optional_float((metadata or {}).get("confidence"))
        user_confirmed = _optional_bool((metadata or {}).get("user_confirmed", (metadata or {}).get("confirmed")))
        match_metadata = {
            "fact_count": len(clean_fact_ids),
            "resolution_state": resolution_state,
            **(metadata or {}),
        }
        job_identity_id = _stable_id("job", job_id)
        job_metadata = _job_metadata(metadata or {})
        with self._transaction("recordJobMatch", "created") as txn:
            conn = txn.connection
            assert conn is not None
            txn.touch("job_id", job_identity_id)
            txn.touch("source_job_id", job_id)
            txn.touch("job_match_id", job_match_id)
            conn.execute(
                """
                INSERT INTO jobs (job_id, source_job_id, created_at, updated_at, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_job_id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    metadata_json = excluded.metadata_json
                """,
                (job_identity_id, str(job_id), now, now, _to_json(job_metadata)),
            )
            existing = conn.execute("SELECT job_match_id FROM job_matches WHERE job_match_id = ?", (job_match_id,)).fetchone()
            mutation_status = "updated" if existing else "created"
            txn.set_mutation_status(mutation_status)
            conn.execute(
                """
                INSERT INTO job_matches (
                    job_match_id, job_id, requirement_id, fact_ids_json, resolution_state, created_at, metadata_json,
                    match_type, confidence, user_confirmed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_match_id) DO UPDATE SET
                    fact_ids_json = excluded.fact_ids_json,
                    resolution_state = excluded.resolution_state,
                    metadata_json = excluded.metadata_json,
                    match_type = excluded.match_type,
                    confidence = excluded.confidence,
                    user_confirmed = excluded.user_confirmed
                """,
                (
                    job_match_id,
                    str(job_id),
                    str(requirement_id),
                    _to_json(clean_fact_ids),
                    resolution_state,
                    now,
                    _to_json(match_metadata),
                    match_type,
                    confidence,
                    user_confirmed,
                ),
            )
        transaction_result = txn.result
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": mutation_status,
            "mutation_status": mutation_status,
            "job_match_id": job_match_id,
            "job_id": str(job_id),
            "requirement_id": str(requirement_id),
            "fact_ids": clean_fact_ids,
            "resolution_state": resolution_state,
            "match_type": match_type,
            "transaction_result": transaction_result_payload(transaction_result),
            "audit": self._audit("recordJobMatch", mutated=True),
        }
        _add_if_not_none(result, "confidence", confidence)
        _add_if_not_none(result, "user_confirmed", user_confirmed)
        return result

    def recordInteraction(
        self,
        interaction_type: str,
        subject_id: str,
        input_json: JsonObject,
        result_json: JsonObject | None = None,
    ) -> JsonObject:
        return _record_interaction_result(
            self._transaction, self._clock, self._audit, transaction_result_payload, SCHEMA_VERSION, interaction_type, subject_id, input_json, result_json
        )

    def listInteractions(self, filters: JsonObject | None = None) -> JsonObject:
        return _list_interactions_result(self._connect, self._audit, SCHEMA_VERSION, filters)

    def adjudicateConflict(self, conflictId: str, decision: str | JsonObject, provenance: list[JsonObject]) -> JsonObject:
        return _adjudicate_conflict(self, SCHEMA_VERSION, conflictId, decision, provenance)

    def findConflicts(self, fact_or_claim: JsonObject, scope: JsonObject | None = None) -> JsonObject:
        conflicts = self._detect_conflicts(fact_or_claim)
        fact_id = fact_or_claim.get("fact_id")
        if fact_id:
            conflicts.extend(self._conflicts_for_fact(str(fact_id)))
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "ok",
            "conflicts": _dedupe_conflicts(conflicts),
            "audit": self._audit("findConflicts", mutated=False, scope=scope or {}),
        }

    def getMigrationState(self) -> MigrationState:
        with self._connect() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            return MigrationState(**migration_state(self._database_path, conn))

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            found_version = user_version(conn)
            if found_version > SUPPORTED_SCHEMA_VERSION:
                raise IncompatibleSchemaVersionError(found=found_version, supported=SUPPORTED_SCHEMA_VERSION)
            for migration in pending_migrations(conn):
                migration_version = MIGRATIONS.index(migration) + 1
                try:
                    migration.apply(conn)
                    _record_migration(conn, migration.id, self._clock())
                    set_user_version(conn, migration_version)
                except Exception as exc:
                    if isinstance(exc, MigrationFailedError):
                        raise
                    raise MigrationFailedError(migration.id, exc) from exc
            if not pending_migrations(conn) and user_version(conn) < SUPPORTED_SCHEMA_VERSION:
                set_user_version(conn, SUPPORTED_SCHEMA_VERSION)
            conn.commit()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._database_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @contextmanager
    def _transaction(self, operation: str, mutation_status: str = "unknown") -> Iterator[TransactionScope]:
        with TransactionScope(
            self._database_path,
            SCHEMA_VERSION,
            self._clock,
            operation,
            mutation_status,
            lambda result: setattr(self, "_last_transaction_result", result),
        ) as txn:
            yield txn

    def _after_conflict_detection(self, operation: str, policy: JsonObject) -> None:
        hook = policy.get("_after_conflict_detection")
        if callable(hook):
            hook(operation)

    def _audit(self, operation: str, mutated: bool, **extra: Any) -> JsonObject:
        audit = {
            "operation": operation,
            "schema_version": SCHEMA_VERSION,
            "mutated": mutated,
            "observed_at": self._clock(),
        }
        audit.update(extra)
        return audit

    def _fact_row(self, fact_id: str, conn: sqlite3.Connection | None = None) -> sqlite3.Row | None:
        if conn is not None:
            return conn.execute("SELECT * FROM facts WHERE fact_id = ?", (fact_id,)).fetchone()
        with self._connect() as local_conn:
            return self._fact_row(fact_id, conn=local_conn)

    def _fact_rows(self, conn: sqlite3.Connection | None = None, active_only: bool = True) -> list[sqlite3.Row]:
        if conn is not None:
            if active_only:
                return list(
                    conn.execute(
                        "SELECT * FROM facts WHERE merged_into_fact_id IS NULL ORDER BY type, text, fact_id"
                    ).fetchall()
                )
            return list(conn.execute("SELECT * FROM facts ORDER BY type, text, fact_id").fetchall())
        with self._connect() as local_conn:
            return self._fact_rows(conn=local_conn, active_only=active_only)

    def _fact_from_row(self, row: sqlite3.Row | None, conn: sqlite3.Connection | None = None) -> JsonObject:
        if row is None:
            return {}
        evidence_ids = [item["evidence_id"] for item in self._evidence_for_fact(str(row["fact_id"]), conn=conn)]
        fact = {
            "fact_id": str(row["fact_id"]),
            "type": str(row["type"]),
            "text": str(row["text"]),
            "normalized_terms": _from_json(str(row["normalized_terms_json"]), []),
            "verification_state": str(row["verification_state"]),
            "evidence_ids": evidence_ids,
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "metadata": _from_json(str(row["metadata_json"]), {}),
        }
        _add_if_not_none(fact, "canonical_name", row["canonical_name"])
        _add_if_not_none(fact, "description", row["description"])
        _add_if_not_none(fact, "years", row["years"])
        _add_if_not_none(fact, "confidence", row["confidence"])
        return fact

    def _insert_evidence(self, conn: sqlite3.Connection, fact_id: str, evidence: JsonObject, source: str, now: str) -> str:
        evidence_source = str(evidence.get("source", source))
        evidence_text = str(evidence.get("text", ""))
        evidence_id = str(
            evidence.get("evidence_id")
            or _stable_id(
                "evidence",
                fact_id,
                evidence_source,
                str(evidence.get("source_id", "")),
                evidence_text,
                _to_json(evidence.get("source_span")),
                _to_json(evidence.get("metadata", {})),
            )
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO evidence (
                evidence_id, fact_id, source, source_id, text, source_span_json, observed_at, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                fact_id,
                evidence_source,
                evidence.get("source_id"),
                evidence_text,
                _to_json(evidence.get("source_span")) if evidence.get("source_span") is not None else None,
                evidence.get("observed_at"),
                _to_json(evidence.get("metadata", {})),
                now,
            ),
        )
        return evidence_id

    def _evidence_for_fact(self, fact_id: str, conn: sqlite3.Connection | None = None) -> list[JsonObject]:
        if conn is not None:
            rows = conn.execute(
                "SELECT * FROM evidence WHERE fact_id = ? ORDER BY created_at, evidence_id",
                (fact_id,),
            ).fetchall()
        else:
            with self._connect() as local_conn:
                return self._evidence_for_fact(fact_id, conn=local_conn)
        return [
            {
                "evidence_id": str(row["evidence_id"]),
                "source": str(row["source"]),
                "source_id": row["source_id"],
                "text": str(row["text"]),
                "source_span": _from_json(row["source_span_json"], None) if row["source_span_json"] else None,
                "observed_at": row["observed_at"],
                "metadata": _from_json(str(row["metadata_json"]), {}),
            }
            for row in rows
        ]

    def _relationships_for_fact(self, fact_id: str, conn: sqlite3.Connection | None = None) -> list[JsonObject]:
        if conn is not None:
            rows = conn.execute(
                """
                SELECT * FROM relationships
                WHERE from_fact_id = ? OR to_fact_id = ?
                ORDER BY relationship_type, relationship_id
                """,
                (fact_id, fact_id),
            ).fetchall()
        else:
            with self._connect() as local_conn:
                return self._relationships_for_fact(fact_id, conn=local_conn)
        relationships = []
        for row in rows:
            relationship = {
                "relationship_id": str(row["relationship_id"]),
                "from_fact_id": str(row["from_fact_id"]),
                "to_fact_id": str(row["to_fact_id"]),
                "relationship_type": str(row["relationship_type"]),
                "evidence_or_rationale": _from_json(str(row["evidence_json"]), {}),
                "created_at": str(row["created_at"]),
                "confirmation_status": str(row["confirmation_status"] or "unconfirmed"),
                "confirmed_by_provenance": _from_json(row["confirmed_by_provenance"], []),
                "confirmed_at": row["confirmed_at"],
                "metadata": _from_json(str(row["metadata_json"]), {}),
            }
            _add_if_not_none(relationship, "confidence", row["confidence"])
            relationships.append(relationship)
        return relationships

    def _conflicts_for_fact(self, fact_id: str, conn: sqlite3.Connection | None = None) -> list[JsonObject]:
        if conn is not None:
            rows = conn.execute("SELECT * FROM conflicts ORDER BY conflict_id").fetchall()
        else:
            with self._connect() as local_conn:
                return self._conflicts_for_fact(fact_id, conn=local_conn)
        conflicts = []
        for row in rows:
            fact_ids = _from_json(str(row["fact_ids_json"]), [])
            if fact_id in fact_ids:
                conflicts.append(_conflict_from_row(row))
        return conflicts

    def _detect_conflicts(self, claim: JsonObject, conn: sqlite3.Connection | None = None) -> list[JsonObject]:
        claim_terms = set(_normalized_terms(claim))
        claim_text = str(claim.get("text", ""))
        claim_id = str(claim.get("fact_id", "")) if claim.get("fact_id") else ""
        claim_year = _year_claim_tuple(claim, claim_terms)
        claim_title = _title_claim(claim, claim_terms)
        conflicts: list[JsonObject] = []
        for row in self._fact_rows(conn=conn):
            fact = self._fact_from_row(row, conn=conn)
            if claim_id and fact["fact_id"] == claim_id:
                continue
            fact_terms = set(_normalized_terms(fact))
            fact_year = _year_claim_tuple(fact, fact_terms)
            if claim_year and fact_year and claim_year[0] == fact_year[0] and claim_year[1] != fact_year[1]:
                conflicts.append(
                    _conflict_object(
                        [fact["fact_id"], claim_id or "claim"],
                        f"conflicting years claim: existing '{fact['text']}' versus proposed '{claim_text}'",
                        {
                            "existing": fact["text"],
                            "proposed": claim_text,
                            "existing_claim": {"concept": fact_year[0], "years": fact_year[1]},
                            "proposed_claim": {"concept": claim_year[0], "years": claim_year[1]},
                        },
                    )
                )
            fact_title = _title_claim(fact, fact_terms)
            if claim_title and fact_title and claim_title[0] == fact_title[0] and claim_title[1] != fact_title[1]:
                conflicts.append(
                    _conflict_object(
                        [fact["fact_id"], claim_id or "claim"],
                        f"conflicting title claim: existing '{fact['text']}' versus proposed '{claim_text}'",
                        {
                            "existing": fact["text"],
                            "proposed": claim_text,
                            "existing_claim": {"role": fact_title[0], "title": fact_title[1]},
                            "proposed_claim": {"role": claim_title[0], "title": claim_title[1]},
                        },
                    )
                )
        return conflicts

    def _insert_conflict(self, conn: sqlite3.Connection, conflict: JsonObject, now: str) -> None:
        conn.execute(
            """
            INSERT OR IGNORE INTO conflicts (
                conflict_id, fact_ids_json, reason, status, evidence_ids_json, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conflict["conflict_id"],
                _to_json(conflict["fact_ids"]),
                conflict["reason"],
                conflict.get("status", "open"),
                _to_json(conflict.get("evidence_ids", [])),
                _to_json(conflict.get("metadata", {})),
                now,
            ),
        )

    def _evaluate_upsert_merge_transition(
        self,
        fact_id: str,
        current_state: str,
        requested_state: str,
        policy: JsonObject,
        evidence: JsonObject | None,
        source: str,
        now: str,
    ):
        if requested_state == current_state or current_state == "user_verified":
            return None
        precedence = {
            "unknown": 0,
            "inferred": 1,
            "imported": 2,
            "source_stated": 3,
            "user_verified": 4,
        }
        if precedence.get(requested_state, 0) < precedence.get(current_state, 0):
            return None
        return self._evaluate_upsert_transition(fact_id, current_state, requested_state, policy, evidence, source, now)

    def _evaluate_upsert_transition(
        self,
        fact_id: str,
        current_state: str,
        requested_state: str,
        policy: JsonObject,
        evidence: JsonObject | None,
        source: str,
        now: str,
    ):
        authority = self._upsert_transition_authority(fact_id, requested_state, policy, evidence, source)
        return evaluate_verification_transition(fact_id, current_state, requested_state, authority, now)

    def _upsert_transition_authority(
        self,
        fact_id: str,
        requested_state: str,
        policy: JsonObject,
        evidence: JsonObject | None,
        source: str,
    ):
        if requested_state == "inferred":
            return agent_inference_provenance_authority(_inference_ref(fact_id, evidence, source))
        if requested_state == "source_stated":
            return source_document_evidence_authority(_source_document_ref(fact_id, evidence, source, policy))
        if requested_state == "imported":
            return import_provenance_authority(_authority_ref(evidence, source, "Imported durable career fact."))
        if requested_state == "user_verified":
            return user_affirmed_proposal_authority(_upsert_user_proposal(fact_id, evidence, source))
        return agent_inference_provenance_authority({"source": source, "text": "No verification transition authority."})

    def _source_document_authority_from_refs(self, refs: list[JsonObject]):
        for ref in refs:
            authority = source_document_evidence_authority(ref)
            if authority.authorityKind == "source_document_evidence":
                return authority
        return source_document_evidence_authority(refs[0] if refs else {})

    def _import_authority_from_refs(self, refs: list[JsonObject]):
        for ref in refs:
            authority = import_provenance_authority(ref)
            if authority.authorityKind == "import_provenance":
                return authority
        return import_provenance_authority(refs[0] if refs else {})

    def _agent_inference_authority_from_refs(self, refs: list[JsonObject]):
        for ref in refs:
            authority = agent_inference_provenance_authority(ref)
            if authority.authorityKind == "agent_inference_provenance":
                return authority
        return agent_inference_provenance_authority(refs[0] if refs else {})

    def _insert_transition_evidence(self, conn: sqlite3.Connection, transition: Any, now: str) -> str:
        transition_evidence = transition_evidence_row(transition)
        transition_evidence["evidence_id"] = _stable_id(
            "verification_transition",
            transition.factId,
            transition.priorState,
            transition.newState,
            transition.authorityKind,
            _to_json(transition.provenanceRefs),
            now,
        )
        return self._insert_evidence(conn, transition.factId, transition_evidence, "verification_transition", now)

    def _candidate_matches(self, requirement: JsonObject, facts: list[JsonObject], policy: JsonObject) -> list[JsonObject]:
        requirement_terms = _normalized_terms(requirement)
        requirement_set = set(_expanded_terms(requirement_terms))
        if not requirement_set:
            return []
        requirement_year = _required_years(requirement)
        ranked: list[tuple[int, int, str, str, JsonObject]] = []
        for fact in facts:
            fact_terms = _store_fact_match_terms(self, fact["fact_id"])
            overlap = _meaningful_overlap(requirement_set, fact_terms)
            if overlap:
                resolution, metadata = _direct_resolution(fact, requirement_year, fact_terms)
                conflicts = list(metadata.pop("conflicts", []))
                ranked.append(
                    (
                        _RESOLUTION_RANK[resolution],
                        len(overlap),
                        fact["text"].casefold(),
                        fact["fact_id"],
                        {
                            "fact": fact,
                            "resolution_state": resolution,
                            "match_type": resolution,
                            "match_terms": sorted(overlap),
                            "via_relationships": [],
                            "metadata": metadata,
                            "conflicts": conflicts,
                        },
                    )
                )
                continue
            relationship_match = self._relationship_match(fact["fact_id"], requirement_set, requirement_year, policy)
            if relationship_match is not None:
                resolution = relationship_match["resolution_state"]
                ranked.append(
                    (
                        _RESOLUTION_RANK[resolution],
                        len(relationship_match["match_terms"]),
                        fact["text"].casefold(),
                        fact["fact_id"],
                        {"fact": fact, **relationship_match},
                    )
                )
        if not ranked:
            return []
        ranked.sort(key=lambda item: (-item[0], -item[1], item[2], item[3]))
        selected: list[JsonObject] = []
        best_rank = ranked[0][0]
        for rank, _, _, _, candidate in ranked:
            if rank < best_rank and len(selected) >= 1:
                break
            selected.append(candidate)
            if len(selected) >= int(policy.get("max_supporting_facts", 3)):
                break
        return selected

    def _relationship_match(
        self,
        fact_id: str,
        requirement_terms: set[str],
        requirement_year: int | None,
        policy: JsonObject,
    ) -> JsonObject | None:
        relationship_matches: list[tuple[int, int, str, str, JsonObject]] = []
        for relationship in self._relationships_for_fact(fact_id):
            other_id = relationship["to_fact_id"] if relationship["from_fact_id"] == fact_id else relationship["from_fact_id"]
            other_terms = _store_fact_match_terms(self, other_id)
            overlap = _meaningful_overlap(requirement_terms, other_terms)
            if not overlap:
                continue
            relationship_type = relationship["relationship_type"]
            relationship_direction = _relationship_direction(relationship, fact_id)
            fact = self._fact_from_row(self._fact_row(fact_id))
            fact_terms = _store_fact_match_terms(self, fact_id)
            _, metadata = _direct_resolution(fact, requirement_year, fact_terms)
            conflicts = list(metadata.pop("conflicts", []))
            def append_candidate(resolution: str) -> None:
                if metadata.get("years_satisfied") is False:
                    resolution = "possible_match"
                relationship_matches.append(
                    (
                        _RESOLUTION_RANK[resolution],
                        len(overlap),
                        str(relationship["relationship_id"]),
                        other_id,
                        _relationship_candidate(
                            resolution,
                            overlap,
                            relationship,
                            relationship_direction,
                            metadata,
                            conflicts,
                        ),
                    )
                )
            resolution = _relationship_policy_match_type(
                relationship_type,
                relationship["confirmation_status"],
                policy,
                relationship_direction,
            )
            if resolution is not None:
                append_candidate(resolution)
        if not relationship_matches:
            return None
        relationship_matches.sort(key=lambda item: (-item[0], -item[1], item[2], item[3]))
        return relationship_matches[0][4]

    def _mutation_error(
        self,
        operation: str,
        fact_id: str,
        verification_state: str,
        status: str,
        confirmation_required: bool,
    ) -> JsonObject:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "error" if status != "rejected" else "rejected",
            "mutation_status": "rejected",
            "fact_id": fact_id,
            "verification_state": verification_state,
            "conflicts": [],
            "confirmation_required": confirmation_required,
            "errors": [_validation_error(status, "verification_state", _VERIFICATION_STATES)]
            if status == "invalid_verification_state"
            else [{"code": status, "message": status.replace("_", " ")}],
            "audit": self._audit(operation, mutated=False, reason=status),
        }

    def _interpretation_proposal_error(
        self,
        fact_id: str,
        verification_state: str,
        error: InvalidInterpretationProposalError,
        source: str,
    ) -> JsonObject:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "mutation_status": "rejected",
            "fact_id": fact_id,
            "verification_state": verification_state,
            "conflicts": [],
            "confirmation_required": True,
            "errors": [error.to_error()],
            "audit": self._audit("verifyFact", mutated=False, source=source, reason=error.code),
        }

    def _disallowed_transition_error(
        self,
        fact_id: str,
        verification_state: str,
        error: DisallowedTransitionError,
        source: str,
        operation: str = "verifyFact",
    ) -> JsonObject:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "mutation_status": "rejected",
            "fact_id": fact_id,
            "verification_state": verification_state,
            "conflicts": [],
            "confirmation_required": error.requiredAuthority == "user_affirmed_proposal",
            "errors": [error.to_error()],
            "audit": self._audit(operation, mutated=False, source=source, reason="disallowed_verification_transition"),
        }

    def _relationship_error(self, fact_id: str, reason: str, confirmation_required: bool) -> JsonObject:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "mutation_status": "rejected",
            "fact_id": fact_id,
            "relationship_id": None,
            "verification_state": "unknown",
            "conflicts": [],
            "confirmation_required": confirmation_required,
            "errors": [_validation_error(reason, "relationship_type", _RELATIONSHIP_TYPES)]
            if reason == "invalid_relationship_type"
            else [{"code": reason, "message": reason.replace("_", " ")}],
            "audit": self._audit("addRelationship", mutated=False, reason=reason),
        }

    def _job_match_error(self, job_id: str, requirement_id: str, reason: str) -> JsonObject:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "error",
            "mutation_status": "rejected",
            "job_match_id": None,
            "job_id": str(job_id),
            "requirement_id": str(requirement_id),
            "fact_ids": [],
            "resolution_state": "unknown",
            "errors": [_validation_error(reason, "resolution_state", _RESOLUTION_STATES)],
            "audit": self._audit("recordJobMatch", mutated=False, reason=reason),
        }


def openCareerStore(database_path: str, clock: Callable[[], str] | None = None) -> CareerStore:
    return CareerStore(database_path, clock=clock)


def _default_clock() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


__all__ = ["CareerStore", "IncompatibleSchemaVersionError", "MigrationFailedError", "openCareerStore"]
