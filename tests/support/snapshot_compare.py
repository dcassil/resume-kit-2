"""Canonical snapshot comparison helpers for fixture data snapshots.

The volatile field allowlist intentionally covers only per-invocation identity
and wall-clock fields: run IDs from RKIT-I-0022, request/trace/call/session IDs,
process/thread IDs, and timestamp-like audit fields. Domain IDs such as
resume_id, job_id, fact_id, requirement_id, and operation_id are not dropped
because they are part of the contract surface.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable


VOLATILE_FIELD_NAMES = frozenset(
    {
        "call_id",
        "completed_at",
        "created_at",
        "deleted_at",
        "finished_at",
        "generated_at",
        "invocation_id",
        "observed_at",
        "pid",
        "process_id",
        "recorded_at",
        "request_id",
        "run_id",
        "run_identity",
        "session_id",
        "span_id",
        "started_at",
        "thread_id",
        "timestamp",
        "timestamps",
        "trace_id",
        "updated_at",
    }
)


@dataclass(frozen=True)
class SnapshotDifference:
    """One canonicalized JSON mismatch."""

    pointer: str
    expected: Any
    live: Any
    message: str


@dataclass(frozen=True)
class SnapshotComparison:
    """Structured snapshot comparison result."""

    equal: bool
    differences: tuple[SnapshotDifference, ...]

    def __bool__(self) -> bool:
        return self.equal


_MISSING = object()


def canonicalize(value: Any, volatile_fields: Iterable[str] | None = None) -> Any:
    """Return a deterministic JSON-compatible projection of ``value``.

    Object keys are stringified, sorted, and recursively canonicalized. Fields
    named in ``volatile_fields`` are dropped at any object depth.
    """

    dropped = set(VOLATILE_FIELD_NAMES if volatile_fields is None else volatile_fields)
    if isinstance(value, dict):
        return {
            str(key): canonicalize(value[key], dropped)
            for key in sorted(value, key=lambda item: str(item))
            if str(key) not in dropped
        }
    if isinstance(value, (list, tuple)):
        return [canonicalize(item, dropped) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """Serialize a value after canonicalization with byte-stable formatting."""

    return json.dumps(canonicalize(value), ensure_ascii=False, indent=2, sort_keys=True)


def compare(expected_data: Any, live_data: Any, *, max_differences: int = 20) -> SnapshotComparison:
    """Canonicalize and deeply compare expected and live snapshot data."""

    expected = canonicalize(expected_data)
    live = canonicalize(live_data)
    differences = tuple(_diff(expected, live, "", max_differences))
    return SnapshotComparison(equal=not differences, differences=differences)


def _diff(expected: Any, live: Any, pointer: str, limit: int) -> list[SnapshotDifference]:
    if limit <= 0 or expected == live:
        return []

    location = pointer or "/"
    if isinstance(expected, dict) and isinstance(live, dict):
        differences: list[SnapshotDifference] = []
        for key in sorted(set(expected) | set(live)):
            child_pointer = _join_pointer(pointer, key)
            if key not in expected:
                differences.append(
                    _difference(child_pointer, _MISSING, live[key], f"Unexpected key at {child_pointer}")
                )
            elif key not in live:
                differences.append(
                    _difference(child_pointer, expected[key], _MISSING, f"Missing key at {child_pointer}")
                )
            else:
                differences.extend(_diff(expected[key], live[key], child_pointer, limit - len(differences)))
            if len(differences) >= limit:
                return differences[:limit]
        return differences

    if isinstance(expected, list) and isinstance(live, list):
        differences = []
        for index in range(min(len(expected), len(live))):
            differences.extend(_diff(expected[index], live[index], _join_pointer(pointer, str(index)), limit - len(differences)))
            if len(differences) >= limit:
                return differences[:limit]
        if len(expected) != len(live):
            differences.append(
                _difference(location, expected, live, f"Array length differs at {location}: {len(expected)} != {len(live)}")
            )
        return differences

    if type(expected) is not type(live):
        return [
            _difference(
                location,
                expected,
                live,
                f"Type differs at {location}: {type(expected).__name__} != {type(live).__name__}",
            )
        ]

    return [_difference(location, expected, live, f"Value differs at {location}")]


def _difference(pointer: str, expected: Any, live: Any, message: str) -> SnapshotDifference:
    return SnapshotDifference(
        pointer=pointer,
        expected="<missing>" if expected is _MISSING else expected,
        live="<missing>" if live is _MISSING else live,
        message=message,
    )


def _join_pointer(pointer: str, token: str) -> str:
    escaped = token.replace("~", "~0").replace("/", "~1")
    return f"{pointer}/{escaped}" if pointer else f"/{escaped}"
