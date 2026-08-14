#!/usr/bin/env python3
"""Run deterministic career-store migration checks."""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


FIXTURE_CLOCK = "2026-01-01T00:00:00Z"
CASE_ORDER = (
    "fresh-migrate",
    "idempotent-rerun",
    "upgrade-from-previous",
    "destructive-without-policy",
)


JsonObject = dict[str, Any]


class CaseFailure(Exception):
    def __init__(self, case: str, message: str) -> None:
        super().__init__(message)
        self.case = case
        self.message = message


def add_package_paths(root: Path) -> None:
    for package_dir in ("resume-core", "career-store"):
        path = str(root / package_dir)
        if path not in sys.path:
            sys.path.insert(0, path)


def load_store(root: Path) -> Any:
    add_package_paths(root)
    try:
        return importlib.import_module("career_store")
    except ModuleNotFoundError as exc:
        raise CaseFailure("setup", f"career_store package is not importable: {exc}") from exc


def maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        raise CaseFailure("setup", "career_store migration API returned an awaitable; this tool expects the local sync surface.")
    return value


def open_store(module: Any, database_path: Path) -> Any:
    factory = getattr(module, "openCareerStore", None)
    if not callable(factory):
        raise CaseFailure("setup", "career_store.openCareerStore(database_path, clock=None) is missing.")
    return maybe_await(factory(str(database_path), clock=lambda: FIXTURE_CLOCK))


def normalize_json(value: str | None, fallback: Any) -> Any:
    if value is None:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise CaseFailure("database-observation", f"stored JSON is not parseable: {exc.msg}") from exc


def connection(database_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    return conn


def observed_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [str(row["name"]) for row in rows]


def observed_rows(database_path: Path) -> JsonObject:
    with connection(database_path) as conn:
        tables = observed_tables(conn)
        result: JsonObject = {"tables": tables}
        if "migrations" in tables:
            result["migrations"] = [
                {
                    "migration_id": str(row["migration_id"]),
                    "schema_version": str(row["schema_version"]),
                    "applied_at": str(row["applied_at"]),
                }
                for row in conn.execute(
                    "SELECT migration_id, schema_version, applied_at FROM migrations ORDER BY migration_id"
                ).fetchall()
            ]
        if "facts" in tables:
            result["facts"] = [
                {
                    "fact_id": str(row["fact_id"]),
                    "type": str(row["type"]),
                    "text": str(row["text"]),
                    "normalized_terms": normalize_json(row["normalized_terms_json"], []),
                    "verification_state": str(row["verification_state"]),
                    "created_at": str(row["created_at"]),
                    "updated_at": str(row["updated_at"]),
                    "metadata": normalize_json(row["metadata_json"], {}),
                }
                for row in conn.execute(
                    """
                    SELECT fact_id, type, text, normalized_terms_json, verification_state, created_at, updated_at, metadata_json
                    FROM facts
                    ORDER BY fact_id
                    """
                ).fetchall()
            ]
        if "evidence" in tables:
            result["evidence"] = [
                {
                    "evidence_id": str(row["evidence_id"]),
                    "fact_id": str(row["fact_id"]),
                    "source": str(row["source"]),
                    "source_id": row["source_id"],
                    "text": str(row["text"]),
                    "source_span": normalize_json(row["source_span_json"], None),
                    "observed_at": row["observed_at"],
                    "metadata": normalize_json(row["metadata_json"], {}),
                }
                for row in conn.execute(
                    """
                    SELECT evidence_id, fact_id, source, source_id, text, source_span_json, observed_at, metadata_json
                    FROM evidence
                    ORDER BY evidence_id
                    """
                ).fetchall()
            ]
        for table in ("relationships", "conflicts", "job_matches"):
            if table in tables:
                result[table] = []
        return result


def normalized_state(value: Any) -> JsonObject:
    if is_dataclass(value):
        raw = asdict(value)
    elif isinstance(value, dict):
        raw = dict(value)
    else:
        raw = {
            name: getattr(value, name)
            for name in ("schema_version", "database_path", "applied_migrations", "pending_migrations", "status", "metadata")
            if hasattr(value, name)
        }
    return {
        "schema_version": raw.get("schema_version"),
        "applied_migrations": list(raw.get("applied_migrations", [])),
        "pending_migrations": list(raw.get("pending_migrations", [])),
        "status": raw.get("status", "unknown"),
    }


def observed_state(store: Any, database_path: Path) -> JsonObject:
    getter = getattr(store, "getMigrationState", None)
    if callable(getter):
        return normalized_state(maybe_await(getter()))

    rows = observed_rows(database_path)
    applied = [row["migration_id"] for row in rows.get("migrations", [])]
    versions = [row["schema_version"] for row in rows.get("migrations", [])]
    schema_version = versions[-1] if versions else None
    return {
        "schema_version": schema_version,
        "applied_migrations": applied,
        "pending_migrations": [],
        "status": "observed",
    }


def require(condition: bool, case: str, message: str) -> None:
    if not condition:
        raise CaseFailure(case, message)


def load_expected(path: Path) -> JsonObject:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CaseFailure("setup", f"expected state fixture is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CaseFailure("setup", f"expected state fixture is invalid JSON: {exc.msg}") from exc


def check_fresh(module: Any, tmp: Path, current_version: str) -> tuple[Path, JsonObject, str]:
    case = "fresh-migrate"
    database_path = tmp / "fresh" / "career.db"
    store = open_store(module, database_path)
    state = observed_state(store, database_path)
    rows = observed_rows(database_path)
    require(state["schema_version"] == current_version, case, f"schema_version={state['schema_version']!r}, expected {current_version!r}.")
    require(state["pending_migrations"] == [], case, f"pending migrations remain: {state['pending_migrations']!r}.")
    require(state["applied_migrations"].count("001_initial") == 1, case, "expected exactly one 001_initial migration record.")
    require({"migrations", "facts", "evidence", "relationships", "conflicts", "job_matches"} <= set(rows["tables"]), case, "current tables are incomplete.")
    detail = f"schema_version={state['schema_version']}; applied={','.join(state['applied_migrations'])}"
    return database_path, state, detail


def check_idempotent(module: Any, database_path: Path, prior_state: JsonObject) -> str:
    case = "idempotent-rerun"
    before_rows = observed_rows(database_path)
    store = open_store(module, database_path)
    after_state = observed_state(store, database_path)
    after_rows = observed_rows(database_path)
    require(after_state == prior_state, case, "schema state changed on re-run.")
    require(after_rows == before_rows, case, "database state changed on re-run.")
    return f"schema_version={after_state['schema_version']}; applied={','.join(after_state['applied_migrations'])}"


def check_upgrade(module: Any, tmp: Path, previous_fixture: Path, expected_database: JsonObject) -> tuple[Path, str]:
    case = "upgrade-from-previous"
    database_path = tmp / "upgrade" / "career.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(previous_fixture, database_path)
    open_store(module, database_path)
    observed = observed_rows(database_path)
    require(observed == expected_database, case, "observed post-upgrade database state differs from fixture expectation.")
    migrations = [row["migration_id"] for row in observed["migrations"]]
    return database_path, f"tables={len(observed['tables'])}; applied={','.join(migrations)}"


def check_no_destructive_change(module: Any, tmp: Path, previous_fixture: Path) -> str:
    case = "destructive-without-policy"
    database_path = tmp / "destructive" / "career.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(previous_fixture, database_path)
    before = observed_rows(database_path)
    open_store(module, database_path)
    after = observed_rows(database_path)
    require(after.get("facts", []) == before.get("facts", []), case, "populated facts changed during migration without an audited policy.")
    require(after.get("evidence", []) == before.get("evidence", []), case, "populated evidence changed during migration without an audited policy.")
    require("001_initial" in [row["migration_id"] for row in after.get("migrations", [])], case, "current migration record was not applied.")
    return "populated facts/evidence preserved; no destructive action observed"


def run(root: Path, expected_path: Path, previous_path: Path) -> dict[str, str]:
    module = load_store(root)
    expected = load_expected(expected_path)
    expected_database = expected.get("expected_database")
    if not isinstance(expected_database, dict):
        raise CaseFailure("setup", "expected-post-migration fixture lacks expected_database object.")
    current_version = str(expected.get("current_schema_version", ""))
    if not current_version:
        raise CaseFailure("setup", "expected-post-migration fixture lacks current_schema_version.")
    if not previous_path.exists():
        raise CaseFailure("setup", f"previous schema fixture is missing: {previous_path}")

    with tempfile.TemporaryDirectory(prefix="rkit-migration-checks-") as directory:
        tmp = Path(directory)
        fresh_path, fresh_state, fresh_detail = check_fresh(module, tmp, current_version)
        return {
            "fresh-migrate": fresh_detail,
            "idempotent-rerun": check_idempotent(module, fresh_path, fresh_state),
            "upgrade-from-previous": check_upgrade(module, tmp, previous_path, expected_database)[1],
            "destructive-without-policy": check_no_destructive_change(module, tmp, previous_path),
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--expected-post-migration", help=argparse.SUPPRESS)
    parser.add_argument("--previous-schema-db", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    expected_path = Path(args.expected_post_migration).resolve() if args.expected_post_migration else root / "fixtures" / "migrations" / "expected-post-migration.json"
    previous_path = Path(args.previous_schema_db).resolve() if args.previous_schema_db else root / "fixtures" / "migrations" / "previous-schema-career.db"

    try:
        results = run(root, expected_path, previous_path)
    except CaseFailure as failure:
        print("migration checks failed.")
        print(f"- {failure.case}: fail - {failure.message}")
        return 1

    print("migration checks passed.")
    for case in CASE_ORDER:
        print(f"- {case}: pass - {results[case]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
