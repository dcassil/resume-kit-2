#!/usr/bin/env python3
"""Generate the byte-stable previous-schema career-store migration fixture."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path


FIXTURE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = FIXTURE_DIR / "previous-schema-career.db"
TEMP_DATABASE_PATH = FIXTURE_DIR / "previous-schema-career.db.tmp"
PREVIOUS_SCHEMA_VERSION = "career-store.v0"
FIXED_TIMESTAMP = "2026-01-01T00:00:00Z"


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


FACTS = [
    {
        "fact_id": "fact_api_architecture_10_years",
        "type": "skill",
        "text": "API and application architecture experience for more than ten years.",
        "normalized_terms": ["10 years", "api architecture", "application architecture"],
        "verification_state": "imported",
        "metadata": {"fixture": "previous-schema", "years": "10+"},
    },
    {
        "fact_id": "fact_aws_6_years",
        "type": "skill",
        "text": "AWS experience across EC2, S3, Lambda, RDS, and IAM for about six years.",
        "normalized_terms": ["amazon web services", "aws", "ec2", "iam", "lambda", "rds", "s3"],
        "verification_state": "imported",
        "metadata": {"fixture": "previous-schema", "years": 6},
    },
    {
        "fact_id": "fact_graphql_5_years",
        "type": "skill",
        "text": "Built and maintained GraphQL APIs in production for around five years.",
        "normalized_terms": ["graphql", "graphql api", "production"],
        "verification_state": "source_stated",
        "metadata": {"fixture": "previous-schema", "years": 5},
    },
]

EVIDENCE = [
    {
        "evidence_id": "evidence_api_architecture_answer",
        "fact_id": "fact_api_architecture_10_years",
        "source": "user_answer",
        "source_id": "answer-architecture",
        "text": "I've designed APIs and application architecture for more than ten years, but I haven't had Staff Engineer as my formal title.",
        "source_span": {"start": 0, "end": 125},
        "observed_at": "2026-01-01T00:00:00Z",
        "metadata": {"fixture": "previous-schema"},
    },
    {
        "evidence_id": "evidence_aws_answer",
        "fact_id": "fact_aws_6_years",
        "source": "user_answer",
        "source_id": "answer-aws",
        "text": "Yes. I have about six years of AWS experience, mainly EC2, S3, Lambda, RDS, and IAM.",
        "source_span": {"start": 0, "end": 84},
        "observed_at": "2026-01-01T00:00:00Z",
        "metadata": {"fixture": "previous-schema"},
    },
    {
        "evidence_id": "evidence_graphql_answer",
        "fact_id": "fact_graphql_5_years",
        "source": "user_answer",
        "source_id": "answer-graphql",
        "text": "Yes, around five years. I've built and maintained GraphQL APIs in production.",
        "source_span": {"start": 0, "end": 77},
        "observed_at": "2026-01-01T00:00:00Z",
        "metadata": {"fixture": "previous-schema"},
    },
]


def create_database(path: Path) -> None:
    if path.exists():
        path.unlink()

    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA page_size = 4096")
        conn.execute("PRAGMA encoding = 'UTF-8'")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            CREATE TABLE migrations (
                migration_id TEXT PRIMARY KEY,
                schema_version TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE facts (
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
            CREATE TABLE evidence (
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
            "INSERT INTO migrations (migration_id, schema_version, applied_at) VALUES (?, ?, ?)",
            ("000_previous_schema_fixture", PREVIOUS_SCHEMA_VERSION, FIXED_TIMESTAMP),
        )
        for fact in FACTS:
            conn.execute(
                """
                INSERT INTO facts (
                    fact_id, type, text, normalized_terms_json, verification_state, created_at, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact["fact_id"],
                    fact["type"],
                    fact["text"],
                    canonical_json(fact["normalized_terms"]),
                    fact["verification_state"],
                    FIXED_TIMESTAMP,
                    FIXED_TIMESTAMP,
                    canonical_json(fact["metadata"]),
                ),
            )
        for evidence in EVIDENCE:
            conn.execute(
                """
                INSERT INTO evidence (
                    evidence_id, fact_id, source, source_id, text, source_span_json, observed_at, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence["evidence_id"],
                    evidence["fact_id"],
                    evidence["source"],
                    evidence["source_id"],
                    evidence["text"],
                    canonical_json(evidence["source_span"]),
                    evidence["observed_at"],
                    canonical_json(evidence["metadata"]),
                    FIXED_TIMESTAMP,
                ),
            )
        conn.execute("PRAGMA user_version = 0")
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    create_database(TEMP_DATABASE_PATH)
    os.replace(TEMP_DATABASE_PATH, DATABASE_PATH)
    print(f"wrote {DATABASE_PATH.relative_to(FIXTURE_DIR.parent.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
