from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from career_store.migrations import MIGRATIONS


FIXED_TIME = "2026-01-01T00:00:00Z"
EXPECTED_MIGRATIONS = [
    "001_initial",
    "002_section_6_fact_columns",
    "003_jobs_table_backfill",
    "004_match_relationship_columns",
]


def to_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def stable_id(prefix: str, *parts: Any) -> str:
    payload = "\x1f".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _canonical_sqlite_dump(database_path: Path) -> str:
    conn = sqlite3.connect(database_path)
    try:
        return "\n".join(conn.iterdump())
    finally:
        conn.close()


def build_pre_realignment_database(database_path: Path) -> None:
    conn = sqlite3.connect(database_path)
    try:
        MIGRATIONS[0].apply(conn)
        conn.execute(
            "INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)",
            ("001_initial", FIXED_TIME),
        )
        conn.execute(
            "INSERT INTO migrations (migration_id, schema_version, applied_at) VALUES (?, ?, ?)",
            ("001_initial", "career-store.v1", FIXED_TIME),
        )
        conn.execute("PRAGMA user_version = 1")
        for fact_id, text, terms in (
            ("fact_react", "React production experience.", ["react"]),
            ("fact_typescript", "TypeScript production experience.", ["typescript"]),
        ):
            conn.execute(
                """
                INSERT INTO facts (
                    fact_id, type, text, normalized_terms_json, verification_state, created_at, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (fact_id, "skill", text, to_json(terms), "source_stated", FIXED_TIME, FIXED_TIME, "{}"),
            )
        conn.execute(
            """
            INSERT INTO relationships (
                relationship_id, from_fact_id, to_fact_id, relationship_type, evidence_json, created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("rel_react_ts", "fact_react", "fact_typescript", "related", to_json({"text": "frontend stack"}), FIXED_TIME, "{}"),
        )
        for job_id, requirement_id, fact_ids in (
            ("job_b", "req_typescript", ["fact_typescript"]),
            ("job_a", "req_react", ["fact_react"]),
            ("job_a", "req_frontend", ["fact_react", "fact_typescript"]),
        ):
            conn.execute(
                """
                INSERT INTO job_matches (
                    job_match_id, job_id, requirement_id, fact_ids_json, resolution_state, created_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stable_id("job_match", job_id, requirement_id, "|".join(sorted(fact_ids)), "exact_match"),
                    job_id,
                    requirement_id,
                    to_json(sorted(fact_ids)),
                    "exact_match",
                    FIXED_TIME,
                    "{}",
                ),
            )
        conn.commit()
    finally:
        conn.close()
