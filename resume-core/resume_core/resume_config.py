"""Validated resume selection configuration resolution for resume-core."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .matching_config import _issue


JsonObject = dict[str, Any]

RESUME_CONFIG_VERSION = "resume-config.v1"
RESUME_KEYS = ("targetPages", "skills", "experience", "bulletsPerRole", "sectionOrder")
RESUME_RANGE_KEYS = ("min", "max")
REMOVED_FLAT_KEYS = ("max_" + "skills",)
KNOWN_SECTION_ORDER = ("summary", "skills", "experience", "projects", "education")

DEFAULT_SECTION_ORDER = ["summary", "skills", "experience", "projects", "education"]
DEFAULT_TARGET_PAGES: float | None = None
DEFAULT_MIN_COUNT = 0
DEFAULT_MAX_COUNT: int | None = None


@dataclass(frozen=True)
class ResumeCountRange:
    min: int
    max: int | None

    def to_dict(self) -> JsonObject:
        return {"min": self.min, "max": self.max}


@dataclass(frozen=True)
class ResumeConfig:
    skills: ResumeCountRange
    experience: ResumeCountRange
    bullets_per_role: ResumeCountRange
    section_order: list[str]
    target_pages: float | None

    def to_dict(self) -> JsonObject:
        return {
            "targetPages": self.target_pages,
            "skills": self.skills.to_dict(),
            "experience": self.experience.to_dict(),
            "bulletsPerRole": self.bullets_per_role.to_dict(),
            "sectionOrder": copy.deepcopy(self.section_order),
        }


@dataclass(frozen=True)
class ResumeConfigResult:
    config: ResumeConfig
    errors: list[JsonObject]
    warnings: list[JsonObject]

    @property
    def ok(self) -> bool:
        return not self.errors


def resolve_resume_config(config: JsonObject | None) -> ResumeConfigResult:
    """Resolve section-13 resume config with defaults and typed validation."""

    raw = config if isinstance(config, dict) else {}
    errors: list[JsonObject] = []
    warnings: list[JsonObject] = []

    resume = _resume_payload(raw, errors)
    values: JsonObject = {}
    if isinstance(resume, dict):
        values.update(resume)
        _reject_unknown_resume_keys(values, errors)

    _reject_removed_flat_keys(raw, errors)

    skills = _range_value(values.get("skills"), "resume.skills", errors)
    experience = _range_value(values.get("experience"), "resume.experience", errors)
    bullets_per_role = _range_value(values.get("bulletsPerRole"), "resume.bulletsPerRole", errors)
    section_order = _section_order_value(values.get("sectionOrder"), errors)
    target_pages = (
        _positive_number_value(values["targetPages"], DEFAULT_TARGET_PAGES, "resume.targetPages", errors)
        if "targetPages" in values
        else DEFAULT_TARGET_PAGES
    )

    return ResumeConfigResult(
        config=ResumeConfig(
            skills=skills,
            experience=experience,
            bullets_per_role=bullets_per_role,
            section_order=section_order,
            target_pages=target_pages,
        ),
        errors=errors,
        warnings=warnings,
    )


def _resume_payload(raw: JsonObject, errors: list[JsonObject]) -> JsonObject:
    if "resume" not in raw:
        return {}
    resume = raw.get("resume")
    if not isinstance(resume, dict):
        errors.append(_issue("invalid_resume_config_type", "resume must be an object.", "resume"))
        return {}
    return resume


def _reject_unknown_resume_keys(values: JsonObject, errors: list[JsonObject]) -> None:
    allowed = set(RESUME_KEYS)
    for key in sorted(set(values) - allowed):
        errors.append(
            _issue(
                "unknown_resume_config_key",
                "Unknown resume config key.",
                f"resume.{key}",
                {"allowed": sorted(allowed)},
            )
        )


def _reject_removed_flat_keys(raw: JsonObject, errors: list[JsonObject]) -> None:
    allowed = ["resume"]
    for key in REMOVED_FLAT_KEYS:
        if key in raw:
            errors.append(_issue("unknown_resume_config_key", "Unknown resume config key.", key, {"allowed": allowed}))



def _range_value(raw: Any, field_path: str, errors: list[JsonObject]) -> ResumeCountRange:
    if raw is None:
        return ResumeCountRange(min=DEFAULT_MIN_COUNT, max=DEFAULT_MAX_COUNT)
    if not isinstance(raw, dict):
        errors.append(_issue("invalid_resume_config_type", f"{field_path} must be an object.", field_path))
        return ResumeCountRange(min=DEFAULT_MIN_COUNT, max=DEFAULT_MAX_COUNT)

    for key in sorted(set(raw) - set(RESUME_RANGE_KEYS)):
        errors.append(
            _issue(
                "unknown_resume_config_key",
                "Unknown resume count range key.",
                f"{field_path}.{key}",
                {"allowed": list(RESUME_RANGE_KEYS)},
            )
        )

    min_value = _count_value(raw.get("min", DEFAULT_MIN_COUNT), DEFAULT_MIN_COUNT, f"{field_path}.min", errors)
    max_value = _count_value(raw["max"], DEFAULT_MIN_COUNT, f"{field_path}.max", errors) if "max" in raw else DEFAULT_MAX_COUNT
    if max_value is not None and min_value > max_value:
        errors.append(
            _issue(
                "invalid_resume_config_value",
                "Resume config min must be less than or equal to max.",
                field_path,
            )
        )
    return ResumeCountRange(min=min_value, max=max_value)


def _section_order_value(raw: Any, errors: list[JsonObject]) -> list[str]:
    if raw is None:
        return copy.deepcopy(DEFAULT_SECTION_ORDER)
    if not isinstance(raw, list):
        errors.append(_issue("invalid_resume_config_type", "resume.sectionOrder must be a list.", "resume.sectionOrder"))
        return copy.deepcopy(DEFAULT_SECTION_ORDER)
    allowed = set(KNOWN_SECTION_ORDER)
    result: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        field_path = f"resume.sectionOrder.{index}"
        if not isinstance(item, str):
            errors.append(_issue("invalid_resume_config_value", "resume.sectionOrder entries must be strings.", field_path))
            continue
        if item not in allowed:
            errors.append(
                _issue(
                    "invalid_resume_config_value",
                    "resume.sectionOrder contains an unknown section.",
                    field_path,
                    {"allowed": list(KNOWN_SECTION_ORDER)},
                )
            )
            continue
        if item in seen:
            errors.append(_issue("invalid_resume_config_value", "resume.sectionOrder contains a duplicate section.", field_path))
            continue
        seen.add(item)
        result.append(item)
    return result or copy.deepcopy(DEFAULT_SECTION_ORDER)


def _count_value(value: Any, default: int, field_path: str, errors: list[JsonObject]) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(_issue("invalid_resume_config_value", "Resume config count must be an integer.", field_path))
        return int(default)
    if value < 0:
        errors.append(_issue("invalid_resume_config_value", "Resume config count must be non-negative.", field_path))
        return int(default)
    return int(value)


def _positive_number_value(
    value: Any,
    default: float | None,
    field_path: str,
    errors: list[JsonObject],
) -> float | None:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(_issue("invalid_resume_config_value", "Resume config value must be a number.", field_path))
        return default
    if float(value) <= 0:
        errors.append(_issue("invalid_resume_config_value", "Resume config value must be positive.", field_path))
        return default
    return float(value)
