"""Durable SQLite-backed career fact store."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = "career-store.v1"
_MIGRATION_ID = "001_initial"
_VERIFICATION_STATES = {
    # Confirmation policy keeps inferred/unknown distinct from user_verified.
    "source_stated",
    "user_verified",
    "inferred",
    "unknown",
    "explicitly_missing",
    "conflicted",
}
_RELATIONSHIP_TYPES = {"alias", "equivalent", "related", "contradicts"}
_RESOLUTION_STATES = {
    "exact_match",
    "alias_match",
    "verified_fact_match",
    "related_match",
    "possible_match",
    "unknown",
    "explicitly_missing",
    "conflicted",
}
_FORBIDDEN_RESULT_KEYS = {
    "raw_sql",
    "connection",
    "internal_rows",
    "silent_user_verified_promotion",
    "implicit_confirmation",
    "destructive_delete",
    "related_as_equivalent_without_policy",
    "official_score",
    "destructive_resolution",
    "resume_patch",
    "working_resume",
    "base_resume",
}


JsonObject = dict[str, Any]


class CareerStore:
    """Small contract-driven SQLite service for career facts."""

    def __init__(self, database_path: str, clock: Callable[[], str] | None = None) -> None:
        self._database_path = str(database_path)
        self._clock = clock or _default_clock
        Path(self._database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def searchFacts(
        self,
        query: str,
        filters: JsonObject | None = None,
        limit: int | None = None,
        include_evidence: bool = False,
    ) -> JsonObject:
        filters = filters or {}
        terms = _normalized_terms({"text": query, "normalized_terms": [query]})
        rows = self._fact_rows()
        matches: list[JsonObject] = []
        for row in rows:
            fact = self._fact_from_row(row)
            if filters.get("verification_state") and fact["verification_state"] != filters["verification_state"]:
                continue
            fact_terms = set(fact["normalized_terms"] + [_normalize(fact["text"])])
            relationship_terms = set(self._relationship_terms(fact["fact_id"]))
            if not terms or fact_terms.intersection(terms) or relationship_terms.intersection(terms):
                if include_evidence:
                    fact["evidence"] = self._evidence_for_fact(fact["fact_id"])
                matches.append(fact)
        matches.sort(key=lambda item: (item["type"], item["text"].casefold(), item["fact_id"]))
        if limit is not None:
            matches = matches[: max(0, int(limit))]
        return _clean_result(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "ok",
                "facts": matches,
                "query": query,
                "audit": self._audit("searchFacts", mutated=False),
            }
        )

    def getFact(self, fact_id: str) -> JsonObject:
        row = self._fact_row(fact_id)
        if row is None:
            return _clean_result(
                {
                    "schema_version": SCHEMA_VERSION,
                    "status": "not_found",
                    "fact": None,
                    "evidence": [],
                    "relationships": [],
                    "conflicts": [],
                    "audit": self._audit("getFact", mutated=False),
                }
            )
        fact = self._fact_from_row(row)
        return _clean_result(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "ok",
                "fact": fact,
                "evidence": self._evidence_for_fact(fact_id),
                "relationships": self._relationships_for_fact(fact_id),
                "conflicts": self._conflicts_for_fact(fact_id),
                "audit": self._audit("getFact", mutated=False),
            }
        )

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
        if requested_state == "user_verified" and not _has_explicit_confirmation(policy, evidence, source):
            requested_state = "unknown"
            confirmation_required = True
        else:
            confirmation_required = requested_state in {"inferred", "unknown"} and not policy.get("allow_inferred_final", True)
        if requested_state not in _VERIFICATION_STATES:
            requested_state = "unknown"
        conflicts = self._detect_conflicts({**fact, "fact_id": fact_id, "normalized_terms": normalized})
        mutation_status = "created"
        with self._connect() as conn:
            existing = conn.execute("SELECT fact_id, verification_state, created_at FROM facts WHERE fact_id = ?", (fact_id,)).fetchone()
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO facts (
                        fact_id, type, text, normalized_terms_json, verification_state, created_at, updated_at, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fact_id,
                        str(fact.get("type", "fact")),
                        str(fact.get("text", "")),
                        _to_json(normalized),
                        requested_state,
                        now,
                        now,
                        _to_json(fact.get("metadata", {})),
                    ),
                )
            else:
                mutation_status = "updated"
                current_state = str(existing["verification_state"])
                next_state = self._merged_verification_state(current_state, requested_state, policy, evidence, source)
                if next_state == current_state and requested_state == "user_verified" and current_state in {"inferred", "unknown"}:
                    confirmation_required = True
                conn.execute(
                    """
                    UPDATE facts
                    SET type = ?, text = ?, normalized_terms_json = ?, verification_state = ?, updated_at = ?, metadata_json = ?
                    WHERE fact_id = ?
                    """,
                    (
                        str(fact.get("type", "fact")),
                        str(fact.get("text", "")),
                        _to_json(normalized),
                        next_state,
                        now,
                        _to_json(fact.get("metadata", {})),
                        fact_id,
                    ),
                )
                requested_state = next_state
            if evidence:
                self._insert_evidence(conn, fact_id, evidence, source, now)
            for conflict in conflicts:
                self._insert_conflict(conn, conflict, now)
            conn.commit()
        return _clean_result(
            {
                "schema_version": SCHEMA_VERSION,
                "status": mutation_status,
                "mutation_status": mutation_status,
                "fact_id": fact_id,
                "verification_state": requested_state,
                "conflicts": conflicts,
                "confirmation_required": bool(confirmation_required),
                "audit": self._audit("upsertFact", mutated=True),
            }
        )

    def verifyFact(
        self,
        fact_id: str,
        verification_state: str,
        confirmation: JsonObject | str | bool | None,
        source: str,
    ) -> JsonObject:
        requested_state = _state_value(verification_state)
        if requested_state not in _VERIFICATION_STATES:
            return self._mutation_error("verifyFact", fact_id, "unknown", "invalid_verification_state", True)
        row = self._fact_row(fact_id)
        if row is None:
            return self._mutation_error("verifyFact", fact_id, "unknown", "not_found", True)
        current_state = str(row["verification_state"])
        if requested_state == "user_verified" and current_state in {"inferred", "unknown"} and not _confirmation_is_explicit(confirmation):
            return _clean_result(
                {
                    "schema_version": SCHEMA_VERSION,
                    "status": "rejected",
                    "mutation_status": "rejected",
                    "fact_id": fact_id,
                    "verification_state": current_state,
                    "conflicts": self._conflicts_for_fact(fact_id),
                    "confirmation_required": True,
                    "audit": self._audit("verifyFact", mutated=False, source=source),
                }
            )
        now = self._clock()
        with self._connect() as conn:
            conn.execute(
                "UPDATE facts SET verification_state = ?, updated_at = ? WHERE fact_id = ?",
                (requested_state, now, fact_id),
            )
            evidence = {
                "source": source,
                "text": _confirmation_text(confirmation, requested_state),
                "metadata": {"confirmation": confirmation} if isinstance(confirmation, dict) else {},
            }
            self._insert_evidence(conn, fact_id, evidence, source, now)
            conn.commit()
        return _clean_result(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "updated",
                "mutation_status": "updated",
                "fact_id": fact_id,
                "verification_state": requested_state,
                "conflicts": self._conflicts_for_fact(fact_id),
                "confirmation_required": False,
                "audit": self._audit("verifyFact", mutated=True, source=source),
            }
        )

    def addEvidence(self, fact_id: str, evidence: JsonObject, source: str) -> JsonObject:
        row = self._fact_row(fact_id)
        if row is None:
            return self._mutation_error("addEvidence", fact_id, "unknown", "not_found", False)
        now = self._clock()
        with self._connect() as conn:
            evidence_id = self._insert_evidence(conn, fact_id, evidence, source, now)
            conn.execute("UPDATE facts SET updated_at = ? WHERE fact_id = ?", (now, fact_id))
            conn.commit()
        return _clean_result(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "created",
                "mutation_status": "created",
                "fact_id": fact_id,
                "evidence_id": evidence_id,
                "verification_state": str(row["verification_state"]),
                "conflicts": self._conflicts_for_fact(fact_id),
                "confirmation_required": False,
                "audit": self._audit("addEvidence", mutated=True, source=source),
            }
        )

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
        if self._fact_row(from_fact_id) is None or self._fact_row(to_fact_id) is None:
            return self._relationship_error(from_fact_id, "not_found", True)
        now = self._clock()
        relationship_id = _stable_id("relationship", from_fact_id, to_fact_id, relationship_type, _to_json(evidence_or_rationale or {}))
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT relationship_id FROM relationships WHERE relationship_id = ?",
                (relationship_id,),
            ).fetchone()
            mutation_status = "updated" if existing else "created"
            conn.execute(
                """
                INSERT INTO relationships (
                    relationship_id, from_fact_id, to_fact_id, relationship_type, evidence_json, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(relationship_id) DO UPDATE SET
                    evidence_json = excluded.evidence_json,
                    metadata_json = excluded.metadata_json
                """,
                (
                    relationship_id,
                    from_fact_id,
                    to_fact_id,
                    relationship_type,
                    _to_json(evidence_or_rationale or {}),
                    now,
                    _to_json({"policy": policy}),
                ),
            )
            if relationship_type == "contradicts":
                self._insert_conflict(
                    conn,
                    {
                        "conflict_id": _stable_id("conflict", from_fact_id, to_fact_id, relationship_type),
                        "fact_ids": sorted([from_fact_id, to_fact_id]),
                        "reason": str((evidence_or_rationale or {}).get("text", "relationship contradiction")),
                        "status": "open",
                        "evidence_ids": [],
                        "metadata": {"relationship_id": relationship_id},
                    },
                    now,
                )
            conn.commit()
        from_fact = self._fact_from_row(self._fact_row(from_fact_id))
        return _clean_result(
            {
                "schema_version": SCHEMA_VERSION,
                "status": mutation_status,
                "mutation_status": mutation_status,
                "fact_id": from_fact_id,
                "relationship_id": relationship_id,
                "verification_state": from_fact["verification_state"],
                "conflicts": self._conflicts_for_fact(from_fact_id),
                "confirmation_required": relationship_type in {"alias", "equivalent"} and policy.get("requires_confirmation_for_equivalence", False),
                "audit": self._audit("addRelationship", mutated=True),
            }
        )

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
        facts = [self._fact_from_row(row) for row in self._fact_rows()]
        for requirement in requirements:
            requirement_id = str(requirement.get("requirement_id", requirement.get("id", "")))
            requirement_terms = _normalized_terms(requirement)
            best = self._best_match(requirement_terms, facts, policy)
            if best is None:
                unresolved.append(
                    {
                        "requirement_id": requirement_id,
                        "resolution_state": "unknown",
                        "concept": requirement.get("concept", requirement.get("text", "")),
                    }
                )
                continue
            fact = dict(best["fact"])
            if include_evidence:
                fact["evidence"] = self._evidence_for_fact(fact["fact_id"])
            item = {
                "requirement_id": requirement_id,
                "job_id": job_id,
                "fact_id": fact["fact_id"],
                "fact": fact,
                "resolution_state": best["resolution_state"],
                "match_type": best["resolution_state"],
            }
            matches.append(item)
            conflicts.extend(self._conflicts_for_fact(fact["fact_id"]))
        matches.sort(key=lambda item: (item["requirement_id"], item["resolution_state"], item["fact_id"]))
        unresolved.sort(key=lambda item: item["requirement_id"])
        return _clean_result(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "ok",
                "matches": matches,
                "unresolved": unresolved,
                "conflicts": _dedupe_conflicts(conflicts),
                "audit": self._audit("findCandidateMatches", mutated=False),
            }
        )

    def recordJobMatch(
        self,
        job_id: str,
        requirement_id: str,
        fact_ids: list[str],
        resolution_state: str,
    ) -> JsonObject:
        resolution_state = str(resolution_state)
        if resolution_state not in _RESOLUTION_STATES:
            resolution_state = "unknown"
        now = self._clock()
        clean_fact_ids = sorted(str(fact_id) for fact_id in fact_ids)
        job_match_id = _stable_id("job_match", job_id, requirement_id, "|".join(clean_fact_ids), resolution_state)
        with self._connect() as conn:
            existing = conn.execute("SELECT job_match_id FROM job_matches WHERE job_match_id = ?", (job_match_id,)).fetchone()
            mutation_status = "updated" if existing else "created"
            conn.execute(
                """
                INSERT INTO job_matches (
                    job_match_id, job_id, requirement_id, fact_ids_json, resolution_state, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_match_id) DO UPDATE SET
                    fact_ids_json = excluded.fact_ids_json,
                    resolution_state = excluded.resolution_state,
                    metadata_json = excluded.metadata_json
                """,
                (job_match_id, str(job_id), str(requirement_id), _to_json(clean_fact_ids), resolution_state, now, _to_json({})),
            )
            conn.commit()
        return _clean_result(
            {
                "schema_version": SCHEMA_VERSION,
                "status": mutation_status,
                "mutation_status": mutation_status,
                "job_match_id": job_match_id,
                "audit": self._audit("recordJobMatch", mutated=True),
            }
        )

    def findConflicts(self, fact_or_claim: JsonObject, scope: JsonObject | None = None) -> JsonObject:
        conflicts = self._detect_conflicts(fact_or_claim)
        fact_id = fact_or_claim.get("fact_id")
        if fact_id:
            conflicts.extend(self._conflicts_for_fact(str(fact_id)))
        return _clean_result(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "ok",
                "conflicts": _dedupe_conflicts(conflicts),
                "audit": self._audit("findConflicts", mutated=False, scope=scope or {}),
            }
        )

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS migrations (
                    migration_id TEXT PRIMARY KEY,
                    schema_version TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS facts (
                    fact_id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    text TEXT NOT NULL,
                    normalized_terms_json TEXT NOT NULL,
                    verification_state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    fact_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    text TEXT NOT NULL,
                    source_span_json TEXT,
                    observed_at TEXT,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(fact_id) REFERENCES facts(fact_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS relationships (
                    relationship_id TEXT PRIMARY KEY,
                    from_fact_id TEXT NOT NULL,
                    to_fact_id TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    FOREIGN KEY(from_fact_id) REFERENCES facts(fact_id),
                    FOREIGN KEY(to_fact_id) REFERENCES facts(fact_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conflicts (
                    conflict_id TEXT PRIMARY KEY,
                    fact_ids_json TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS job_matches (
                    job_match_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    requirement_id TEXT NOT NULL,
                    fact_ids_json TEXT NOT NULL,
                    resolution_state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "INSERT OR IGNORE INTO migrations (migration_id, schema_version, applied_at) VALUES (?, ?, ?)",
                (_MIGRATION_ID, SCHEMA_VERSION, self._clock()),
            )
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

    def _audit(self, operation: str, mutated: bool, **extra: Any) -> JsonObject:
        audit = {
            "operation": operation,
            "schema_version": SCHEMA_VERSION,
            "mutated": mutated,
            "observed_at": self._clock(),
        }
        audit.update(extra)
        return audit

    def _fact_row(self, fact_id: str) -> sqlite3.Row | None:
        with self._connect() as conn:
            return conn.execute("SELECT * FROM facts WHERE fact_id = ?", (fact_id,)).fetchone()

    def _fact_rows(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return list(conn.execute("SELECT * FROM facts ORDER BY type, text, fact_id").fetchall())

    def _fact_from_row(self, row: sqlite3.Row | None) -> JsonObject:
        if row is None:
            return {}
        evidence_ids = [item["evidence_id"] for item in self._evidence_for_fact(str(row["fact_id"]))]
        return {
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

    def _insert_evidence(self, conn: sqlite3.Connection, fact_id: str, evidence: JsonObject, source: str, now: str) -> str:
        evidence_source = str(evidence.get("source", source))
        evidence_text = str(evidence.get("text", ""))
        evidence_id = str(
            evidence.get("evidence_id")
            or _stable_id("evidence", fact_id, evidence_source, str(evidence.get("source_id", "")), evidence_text)
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

    def _evidence_for_fact(self, fact_id: str) -> list[JsonObject]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM evidence WHERE fact_id = ? ORDER BY created_at, evidence_id",
                (fact_id,),
            ).fetchall()
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

    def _relationships_for_fact(self, fact_id: str) -> list[JsonObject]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM relationships
                WHERE from_fact_id = ? OR to_fact_id = ?
                ORDER BY relationship_type, relationship_id
                """,
                (fact_id, fact_id),
            ).fetchall()
        return [
            {
                "relationship_id": str(row["relationship_id"]),
                "from_fact_id": str(row["from_fact_id"]),
                "to_fact_id": str(row["to_fact_id"]),
                "relationship_type": str(row["relationship_type"]),
                "evidence_or_rationale": _from_json(str(row["evidence_json"]), {}),
                "created_at": str(row["created_at"]),
                "metadata": _from_json(str(row["metadata_json"]), {}),
            }
            for row in rows
        ]

    def _relationship_terms(self, fact_id: str) -> list[str]:
        terms: list[str] = []
        for relationship in self._relationships_for_fact(fact_id):
            other_id = relationship["to_fact_id"] if relationship["from_fact_id"] == fact_id else relationship["from_fact_id"]
            other = self._fact_from_row(self._fact_row(other_id))
            if other:
                terms.extend(other["normalized_terms"])
                terms.append(_normalize(other["text"]))
        return sorted(set(term for term in terms if term))

    def _conflicts_for_fact(self, fact_id: str) -> list[JsonObject]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM conflicts ORDER BY conflict_id").fetchall()
        conflicts = []
        for row in rows:
            fact_ids = _from_json(str(row["fact_ids_json"]), [])
            if fact_id in fact_ids:
                conflicts.append(_conflict_from_row(row))
        return conflicts

    def _detect_conflicts(self, claim: JsonObject) -> list[JsonObject]:
        claim_terms = set(_normalized_terms(claim))
        claim_text = str(claim.get("text", ""))
        claim_year = _year_claim(claim_text, claim_terms)
        claim_title = _title_claim(claim_text, claim_terms)
        conflicts: list[JsonObject] = []
        for row in self._fact_rows():
            fact = self._fact_from_row(row)
            if claim.get("fact_id") and fact["fact_id"] == claim.get("fact_id"):
                related = set(fact["normalized_terms"]).intersection(claim_terms)
            else:
                related = set(fact["normalized_terms"]).intersection(claim_terms)
            if not related:
                continue
            fact_terms = set(fact["normalized_terms"])
            fact_year = _year_claim(fact["text"], fact_terms)
            if claim_year and fact_year and claim_year != fact_year:
                conflicts.append(
                    _conflict_object(
                        [fact["fact_id"], str(claim.get("fact_id", "claim"))],
                        f"conflicting years claim: existing '{fact['text']}' versus proposed '{claim_text}'",
                        {"existing": fact["text"], "proposed": claim_text},
                    )
                )
            fact_title = _title_claim(fact["text"], fact_terms)
            if claim_title and fact_title and claim_title != fact_title:
                conflicts.append(
                    _conflict_object(
                        [fact["fact_id"], str(claim.get("fact_id", "claim"))],
                        f"conflicting title claim: existing '{fact['text']}' versus proposed '{claim_text}'",
                        {"existing": fact["text"], "proposed": claim_text},
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

    def _merged_verification_state(
        self,
        current_state: str,
        requested_state: str,
        policy: JsonObject,
        evidence: JsonObject | None,
        source: str,
    ) -> str:
        if current_state == "user_verified":
            return current_state
        if requested_state == "user_verified" and not _has_explicit_confirmation(policy, evidence, source):
            return current_state
        precedence = {
            "unknown": 0,
            "inferred": 1,
            "explicitly_missing": 2,
            "source_stated": 3,
            "conflicted": 4,
            "user_verified": 5,
        }
        return requested_state if precedence.get(requested_state, 0) >= precedence.get(current_state, 0) else current_state

    def _best_match(self, requirement_terms: list[str], facts: list[JsonObject], policy: JsonObject) -> JsonObject | None:
        requirement_set = set(requirement_terms)
        if not requirement_set:
            return None
        ranked: list[tuple[int, str, JsonObject, str]] = []
        for fact in facts:
            fact_terms = set(fact["normalized_terms"] + [_normalize(fact["text"])])
            overlap = requirement_set.intersection(fact_terms)
            if overlap:
                if fact["verification_state"] == "conflicted":
                    resolution = "conflicted"
                    score = 0
                elif fact["verification_state"] == "explicitly_missing":
                    resolution = "explicitly_missing"
                    score = 1
                elif fact["verification_state"] == "user_verified":
                    resolution = "verified_fact_match"
                    score = 2
                else:
                    resolution = "exact_match"
                    score = 3
                ranked.append((score, fact["text"].casefold(), fact, resolution))
                continue
            relationship_match = self._relationship_match(fact["fact_id"], requirement_set, policy)
            if relationship_match:
                ranked.append((relationship_match[0], fact["text"].casefold(), fact, relationship_match[1]))
        if not ranked:
            return None
        ranked.sort(key=lambda item: (-item[0], item[1], item[2]["fact_id"]))
        _, _, fact, resolution = ranked[0]
        return {"fact": fact, "resolution_state": resolution}

    def _relationship_match(self, fact_id: str, requirement_terms: set[str], policy: JsonObject) -> tuple[int, str] | None:
        for relationship in self._relationships_for_fact(fact_id):
            other_id = relationship["to_fact_id"] if relationship["from_fact_id"] == fact_id else relationship["from_fact_id"]
            other = self._fact_from_row(self._fact_row(other_id))
            other_terms = set(other.get("normalized_terms", []) + [_normalize(other.get("text", ""))])
            if not requirement_terms.intersection(other_terms):
                continue
            relationship_type = relationship["relationship_type"]
            if relationship_type in {"alias", "equivalent"}:
                return (2, "alias_match")
            if relationship_type == "related":
                if policy.get("allow_related_as_equivalent"):
                    return (1, "related_match")
                return (0, "possible_match")
            if relationship_type == "contradicts":
                return (0, "conflicted")
        return None

    def _mutation_error(
        self,
        operation: str,
        fact_id: str,
        verification_state: str,
        status: str,
        confirmation_required: bool,
    ) -> JsonObject:
        return _clean_result(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "error" if status != "rejected" else "rejected",
                "mutation_status": "rejected",
                "fact_id": fact_id,
                "verification_state": verification_state,
                "conflicts": [],
                "confirmation_required": confirmation_required,
                "audit": self._audit(operation, mutated=False, reason=status),
            }
        )

    def _relationship_error(self, fact_id: str, reason: str, confirmation_required: bool) -> JsonObject:
        return _clean_result(
            {
                "schema_version": SCHEMA_VERSION,
                "status": "error",
                "mutation_status": "rejected",
                "fact_id": fact_id,
                "relationship_id": None,
                "verification_state": "unknown",
                "conflicts": [],
                "confirmation_required": confirmation_required,
                "audit": self._audit("addRelationship", mutated=False, reason=reason),
            }
        )


def openCareerStore(database_path: str, clock: Callable[[], str] | None = None) -> CareerStore:
    return CareerStore(database_path, clock=clock)


def _default_clock() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _to_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _from_json(value: str | None, fallback: Any) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _normalize(value: Any) -> str:
    text = str(value).casefold().strip()
    return " ".join("".join(char if char.isalnum() else " " for char in text).split())


def _normalized_terms(value: JsonObject) -> list[str]:
    raw_terms = value.get("normalized_terms") or []
    if isinstance(raw_terms, str):
        raw_terms = [raw_terms]
    terms = [_normalize(term) for term in raw_terms]
    for key in ("concept", "text", "type"):
        if value.get(key):
            terms.append(_normalize(value[key]))
    return sorted(set(term for term in terms if term))


def _state_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _has_explicit_confirmation(policy: JsonObject, evidence: JsonObject | None, source: str) -> bool:
    if policy.get("explicit_confirmation") is True:
        return True
    if source in {"user_answer", "user_confirmation", "manual_confirmation"}:
        return True
    if evidence and evidence.get("source") in {"user_answer", "user_confirmation", "manual_confirmation"}:
        return True
    return False


def _confirmation_is_explicit(confirmation: JsonObject | str | bool | None) -> bool:
    if confirmation is True:
        return True
    if isinstance(confirmation, str):
        return bool(confirmation.strip())
    if isinstance(confirmation, dict):
        return confirmation.get("explicit") is True or confirmation.get("confirmed") is True
    return False


def _confirmation_text(confirmation: JsonObject | str | bool | None, verification_state: str) -> str:
    if isinstance(confirmation, dict):
        return str(confirmation.get("text") or confirmation.get("answer") or f"confirmed {verification_state}")
    if isinstance(confirmation, str):
        return confirmation
    return f"confirmed {verification_state}"


def _year_claim(text: str, terms: set[str]) -> str | None:
    combined = " ".join([_normalize(text), *terms])
    number_words = {
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
        "ten": "10",
    }
    for word, number in number_words.items():
        if f"{word} year" in combined or f"{word} years" in combined:
            return number
    for token in combined.split():
        if token.isdigit() and 0 < int(token) < 60:
            return token
    return None


def _title_claim(text: str, terms: set[str]) -> str | None:
    combined = " ".join([_normalize(text), *terms])
    titles = [
        "staff engineer",
        "principal engineer",
        "senior engineer",
        "engineering manager",
        "software engineer",
    ]
    for title in titles:
        if title in combined:
            return title
    return None


def _conflict_object(fact_ids: list[str], reason: str, metadata: JsonObject) -> JsonObject:
    clean_fact_ids = sorted(set(fact_id for fact_id in fact_ids if fact_id))
    return {
        "conflict_id": _stable_id("conflict", "|".join(clean_fact_ids), reason),
        "fact_ids": clean_fact_ids,
        "reason": reason,
        "status": "open",
        "evidence_ids": [],
        "metadata": metadata,
    }


def _conflict_from_row(row: sqlite3.Row) -> JsonObject:
    return {
        "conflict_id": str(row["conflict_id"]),
        "fact_ids": _from_json(str(row["fact_ids_json"]), []),
        "reason": str(row["reason"]),
        "status": str(row["status"]),
        "evidence_ids": _from_json(str(row["evidence_ids_json"]), []),
        "metadata": _from_json(str(row["metadata_json"]), {}),
    }


def _dedupe_conflicts(conflicts: list[JsonObject]) -> list[JsonObject]:
    deduped = {str(conflict["conflict_id"]): conflict for conflict in conflicts}
    return [deduped[key] for key in sorted(deduped)]


def _clean_result(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean_result(item) for key, item in value.items() if key not in _FORBIDDEN_RESULT_KEYS}
    if isinstance(value, list):
        return [_clean_result(item) for item in value]
    return value


__all__ = ["CareerStore", "openCareerStore"]
