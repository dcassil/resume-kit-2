"""Ordered SQLite migrations for career-store."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


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


MIGRATIONS: tuple[MigrationEntry, ...] = (
    MigrationEntry("001_initial", _apply_initial),
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
