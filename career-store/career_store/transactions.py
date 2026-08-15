"""Private transaction helpers for career-store."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from .schemas import TransactionResult


JsonObject = dict[str, Any]


class TransactionScope:
    def __init__(
        self,
        database_path: str,
        schema_version: str,
        clock: Callable[[], str],
        operation: str,
        mutation_status: str,
        result_recorder: Callable[[TransactionResult], None],
    ) -> None:
        self._database_path = database_path
        self._schema_version = schema_version
        self._clock = clock
        self._operation = operation
        self._mutation_status = mutation_status
        self._result_recorder = result_recorder
        self._ids: dict[str, str] = {}
        self.connection: sqlite3.Connection | None = None
        self.result: TransactionResult | None = None

    def __enter__(self) -> "TransactionScope":
        conn = sqlite3.connect(self._database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        self.connection = conn
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_value: BaseException | None, traceback: Any) -> bool:
        conn = self.connection
        if conn is None:
            return False
        try:
            if exc_type is None:
                conn.commit()
                self.result = self._result("committed", self._mutation_status)
            else:
                conn.rollback()
                errors = [
                    {
                        "code": "transaction_rolled_back",
                        "message": str(exc_value) if exc_value else "transaction rolled back",
                    }
                ]
                self.result = self._result("rolled_back", "rolled_back", errors=errors)
                if exc_value is not None:
                    setattr(exc_value, "transaction_result", self.result)
            self._result_recorder(self.result)
        finally:
            conn.close()
        return False

    def set_mutation_status(self, mutation_status: str) -> None:
        self._mutation_status = mutation_status

    def touch(self, key: str, value: Any) -> None:
        if value is not None and str(value):
            self._ids[key] = str(value)

    def _result(self, status: str, mutation_status: str, errors: list[JsonObject] | None = None) -> TransactionResult:
        ids = dict(sorted(self._ids.items()))
        return TransactionResult(
            schema_version=self._schema_version,
            status=status,
            mutation_status=mutation_status,
            ids=ids,
            errors=errors or [],
            audit={
                "operation": self._operation,
                "schema_version": self._schema_version,
                "mutated": status == "committed",
                "observed_at": self._clock(),
                "ids": ids,
            },
        )


def transaction_result_payload(result: TransactionResult | None) -> JsonObject | None:
    return asdict(result) if result is not None else None
