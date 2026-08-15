"""Ordered SQLite migrations for career-store."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from resume_core import ResolutionState, VerificationState


SCHEMA_VERSION = "career-store.v1"


class IncompatibleSchemaVersionError(RuntimeError):
    """Raised when a database is stamped with a version this package cannot open."""

    def __init__(self, found: int, supported: int) -> None:
        self.found = found
        self.supported = supported
        super().__init__(f"Unsupported career-store schema version {found}; supported version is {supported}.")


class MigrationFailedError(RuntimeError):
    """Raised when an identified migration fails."""

    def __init__(self, migrationId: str, cause: BaseException) -> None:
        self.migrationId = migrationId
        self.migration_id = migrationId
        self.cause = cause
        super().__init__(f"Career-store migration {migrationId} failed: {cause}")


@dataclass(frozen=True)
class MigrationEntry:
    id: str
    apply: Callable[[sqlite3.Connection], None]


def _apply_initial(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
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


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row["name"] if isinstance(row, sqlite3.Row) else row[1]) for row in rows}


def _add_column(conn: sqlite3.Connection, table_name: str, column_definition: str) -> None:
    column_name = column_definition.split()[0]
    if column_name not in _table_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}")


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _row_value(row: sqlite3.Row | tuple[Any, ...], name: str, index: int) -> Any:
    if isinstance(row, sqlite3.Row):
        return row[name]
    return row[index]


_CANONICAL_VERIFICATION_STATES = tuple(state.value for state in VerificationState)
_CANONICAL_RESOLUTION_STATES = tuple(state.value for state in ResolutionState)


def _apply_section_6_fact_columns(conn: sqlite3.Connection) -> None:
    _add_column(conn, "facts", "canonical_name TEXT")
    _add_column(conn, "facts", "description TEXT")
    _add_column(conn, "facts", "years INTEGER")
    _add_column(conn, "facts", "confidence REAL")


def _apply_jobs_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            source_job_id TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        )
        """
    )
    conn.create_function("career_stable_job_id", 1, lambda value: _stable_id("job", value))
    conn.execute(
        """
        INSERT OR IGNORE INTO jobs (job_id, source_job_id, created_at, updated_at, metadata_json)
        SELECT career_stable_job_id(job_id), job_id, '1970-01-01T00:00:00Z', '1970-01-01T00:00:00Z', '{}'
        FROM (SELECT DISTINCT job_id FROM job_matches WHERE job_id IS NOT NULL AND job_id != '' ORDER BY job_id)
        """
    )


def _apply_match_relationship_columns(conn: sqlite3.Connection) -> None:
    _add_column(conn, "job_matches", "match_type TEXT")
    _add_column(conn, "job_matches", "confidence REAL")
    _add_column(conn, "job_matches", "user_confirmed INTEGER")
    _add_column(conn, "relationships", "confidence REAL")


def _apply_enum_value_remap(conn: sqlite3.Connection) -> None:
    placeholders = ", ".join("?" for _ in _CANONICAL_VERIFICATION_STATES)
    drifted_facts = conn.execute(
        f"""
        SELECT fact_id, verification_state, created_at, updated_at
        FROM facts
        WHERE verification_state NOT IN ({placeholders})
        ORDER BY fact_id
        """,
        _CANONICAL_VERIFICATION_STATES,
    ).fetchall()
    for row in drifted_facts:
        fact_id = str(_row_value(row, "fact_id", 0))
        prior_state = str(_row_value(row, "verification_state", 1))
        if prior_state != "conflicted":
            continue
        reason = "legacy conflicted verification state"
        conflict_id = _stable_id("conflict", fact_id, reason)
        created_at = str(_row_value(row, "updated_at", 3) or _row_value(row, "created_at", 2) or "1970-01-01T00:00:00Z")
        metadata = {
            "fact_id": fact_id,
            "migration_id": "005_enum_value_remap",
            "verification_state": prior_state,
        }
        conn.execute(
            """
            INSERT OR IGNORE INTO conflicts (
                conflict_id, fact_ids_json, reason, status, evidence_ids_json, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conflict_id,
                json.dumps([fact_id], sort_keys=True, separators=(",", ":")),
                reason,
                "open",
                "[]",
                json.dumps(metadata, sort_keys=True, separators=(",", ":")),
                created_at,
            ),
        )
    conn.execute(
        f"UPDATE facts SET verification_state = 'unknown' WHERE verification_state NOT IN ({placeholders})",
        _CANONICAL_VERIFICATION_STATES,
    )
    resolution_placeholders = ", ".join("?" for _ in _CANONICAL_RESOLUTION_STATES)
    conn.execute(
        f"UPDATE job_matches SET resolution_state = 'unknown' WHERE resolution_state NOT IN ({resolution_placeholders})",
        _CANONICAL_RESOLUTION_STATES,
    )


def _apply_fact_merge_redirects(conn: sqlite3.Connection) -> None:
    _add_column(conn, "facts", "merged_into_fact_id TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_merges (
            merge_id TEXT PRIMARY KEY,
            survivor_fact_id TEXT NOT NULL,
            merged_fact_id TEXT NOT NULL UNIQUE,
            provenance_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(survivor_fact_id) REFERENCES facts(fact_id),
            FOREIGN KEY(merged_fact_id) REFERENCES facts(fact_id)
        )
        """
    )


MIGRATIONS: tuple[MigrationEntry, ...] = (
    MigrationEntry("001_initial", _apply_initial),
    MigrationEntry("002_section_6_fact_columns", _apply_section_6_fact_columns),
    MigrationEntry("003_jobs_table_backfill", _apply_jobs_table),
    MigrationEntry("004_match_relationship_columns", _apply_match_relationship_columns),
    MigrationEntry("005_enum_value_remap", _apply_enum_value_remap),
    MigrationEntry("006_fact_merge_redirects", _apply_fact_merge_redirects),
)

SUPPORTED_SCHEMA_VERSION = len(MIGRATIONS)
MIGRATION_IDS = tuple(migration.id for migration in MIGRATIONS)


def user_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    if row is None:
        return 0
    return int(row[0])


def set_user_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(f"PRAGMA user_version = {int(version)}")


def has_table(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def applied_migration_ids(conn: sqlite3.Connection) -> list[str]:
    if not has_table(conn, "schema_migrations"):
        return []
    rows = conn.execute("SELECT id FROM schema_migrations ORDER BY id").fetchall()
    return [str(row["id"] if isinstance(row, sqlite3.Row) else row[0]) for row in rows]


def pending_migrations(conn: sqlite3.Connection) -> list[MigrationEntry]:
    applied = set(applied_migration_ids(conn))
    return [migration for migration in MIGRATIONS if migration.id not in applied]


def _record_migration(conn: sqlite3.Connection, migration_id: str, applied_at: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (id, applied_at) VALUES (?, ?)",
        (migration_id, applied_at),
    )
    conn.execute(
        "INSERT OR IGNORE INTO migrations (migration_id, schema_version, applied_at) VALUES (?, ?, ?)",
        (migration_id, SCHEMA_VERSION, applied_at),
    )


def migration_state(database_path: str, conn: sqlite3.Connection) -> dict[str, Any]:
    applied = applied_migration_ids(conn)
    pending = [migration.id for migration in MIGRATIONS if migration.id not in set(applied)]
    return {
        "schema_version": SCHEMA_VERSION,
        "database_path": database_path,
        "applied_migrations": applied,
        "pending_migrations": pending,
        "status": "ok" if not pending else "pending",
        "metadata": {
            "user_version": user_version(conn),
            "supported_user_version": SUPPORTED_SCHEMA_VERSION,
        },
    }


__all__ = [
    "MIGRATIONS",
    "MIGRATION_IDS",
    "SCHEMA_VERSION",
    "SUPPORTED_SCHEMA_VERSION",
    "IncompatibleSchemaVersionError",
    "MigrationEntry",
    "MigrationFailedError",
    "applied_migration_ids",
    "migration_state",
    "pending_migrations",
    "set_user_version",
    "user_version",
]
