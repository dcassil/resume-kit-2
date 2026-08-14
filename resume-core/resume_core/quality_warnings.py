"""Deterministic final-resume quality warning helpers for resume-core."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

from .schemas import JsonObject


def duplicate_warnings(resume: JsonObject) -> list[JsonObject]:
    warnings: list[JsonObject] = []
    seen_skills: set[str] = set()
    for item in _array(_item(resume, "skills", [])):
        key = _duplicate_normal_text(item)
        if not key:
            continue
        if key in seen_skills:
            warnings.append(_issue("duplicate_skill", "Duplicate skill detected.", "skills"))
        seen_skills.add(key)

    seen_entries: dict[str, str] = {}
    seen_bullets: dict[str, str] = {}
    for entry_index, entry in enumerate(_array(_item(resume, "experience", []))):
        entry_path = f"experience.{entry_index}"
        entry_key = _duplicate_normal_text(entry)
        if entry_key:
            if entry_key in seen_entries:
                warnings.append(
                    _issue(
                        "duplicate_experience_entry",
                        "Duplicate experience entry detected.",
                        entry_path,
                        {"duplicate_of": seen_entries[entry_key]},
                    )
                )
            else:
                seen_entries[entry_key] = entry_path
        if not isinstance(entry, dict):
            continue
        for bullet_index, bullet in enumerate(_array(_item(entry, "bullets", []))):
            bullet_path = f"experience.{entry_index}.bullets.{bullet_index}"
            bullet_key = _duplicate_normal_text(bullet)
            if not bullet_key:
                continue
            if bullet_key in seen_bullets:
                warnings.append(
                    _issue(
                        "duplicate_experience_bullet",
                        "Duplicate experience bullet detected.",
                        bullet_path,
                        {"duplicate_of": seen_bullets[bullet_key]},
                    )
                )
            else:
                seen_bullets[bullet_key] = bullet_path
    return warnings


def keyword_warnings(resume: JsonObject) -> list[JsonObject]:
    warnings: list[JsonObject] = []
    words = _normal_text(_text(resume)).split()
    if not words:
        return warnings
    threshold = max(8, len(words) // 5)
    for word in sorted(set(words)):
        count = words.count(word)
        if len(word) > 2 and count > threshold:
            warnings.append(
                _issue(
                    "possible_keyword_stuffing",
                    "Repeated term detected.",
                    "resume",
                    {"term": word, "count": count, "threshold": threshold},
                )
            )
    return warnings


def _duplicate_normal_text(value: Any) -> str:
    return _normal_text(_duplicate_text(value))


def _duplicate_text(value: Any) -> str:
    if isinstance(value, dict) and "value" in value and (
        "claim_id" in value or "provenance" in value or "verification_state" in value
    ):
        return _duplicate_text(value.get("value"))
    if isinstance(value, dict):
        skipped = {"claim_id", "id", "metadata", "provenance", "schema_version", "source", "verification_state"}
        return " ".join(_duplicate_text(item) for key, item in sorted(value.items()) if key not in skipped)
    if isinstance(value, list):
        return " ".join(_duplicate_text(item) for item in value)
    return _text(value)


def _issue(code: str, message: str, field_path: str | None = None, details: JsonObject | None = None) -> JsonObject:
    issue: JsonObject = {"code": code, "message": message, "severity": "error"}
    if field_path is not None:
        issue["field_path"] = field_path
    if details:
        issue["details"] = details
    return issue


def _item(mapping: Any, key: str, default: Any = None) -> Any:
    if isinstance(mapping, dict) and key in mapping:
        return mapping[key]
    return default


def _array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _normal_text(value: Any) -> str:
    text = str(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _text(value: Any) -> str:
    value = _to_json(value)
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_text(item) for key, item in sorted(value.items()) if key != "metadata")
    return str(value)


def _to_json(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_to_json(item) for item in value]
    if isinstance(value, tuple):
        return [_to_json(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_json(item) for key, item in value.items()}
    return value
