"""Deterministic content selection plan construction.

Experience bullets are selected per role by relevance first, then original
bullet order. Structural maxima are applied after ranking and before entries
are emitted, so caller-proposed rankings cannot force over-max keep actions.
"""

from __future__ import annotations

from typing import Any

from .resume_config import ResumeConfig
from .selection_ranking import UNLINKED_RELEVANCE
from .schemas import JsonObject


MATCH_RELEVANCE_KEEP = "match_relevance_keep"
UNLINKED_FILL = "unlinked_fill"
MAX_CONSTRAINT_OVERFLOW = "max_constraint_overflow"
UNLINKED_LOW_RELEVANCE = "unlinked_low_relevance"


def build_content_selection_plan(
    resume: JsonObject,
    ranked: list[JsonObject],
    entry_relevance: dict[str, JsonObject],
    config: ResumeConfig,
) -> tuple[JsonObject, list[JsonObject]]:
    """Return the ContentSelectionPlan DTO and legacy ranked content."""

    experience = _array(_item(resume, "experience", []))
    skills = _array(_item(resume, "skills", []))
    section_order = list(config.section_order)
    experience_limit = _effective_limit(config.experience.max, len(experience))
    skills_limit = _effective_limit(config.skills.max, len(skills))
    bullet_limit = config.bullets_per_role.max
    target_pages = config.target_pages
    selected_experience_ids = [item["id"] for item in ranked if item["kind"] == "experience"][:experience_limit]
    selected_skill_indices = [item["source_index"] for item in ranked if item["kind"] == "skill"][:skills_limit]
    selected_experience = set(selected_experience_ids)
    selected_skills = set(selected_skill_indices)
    entries = _selection_entries(ranked, experience, selected_experience, selected_skills, bullet_limit, entry_relevance)
    return (
        {
            "schema_version": "content-selection-plan.v1",
            "sections": section_order,
            "entries": entries,
            "constraint_report": _constraint_report(experience, skills, selected_experience, config),
            "metadata": {"target_pages": target_pages, "config_snapshot": config.to_dict()},
        },
        ranked,
    )


def _selection_entries(
    ranked: list[JsonObject],
    experience: list[Any],
    selected_experience: set[Any],
    selected_skills: set[Any],
    bullet_limit: int | None,
    entry_relevance: dict[str, JsonObject],
) -> list[JsonObject]:
    entries: list[JsonObject] = []
    for item in ranked:
        kind = item["kind"]
        source_index = int(item["source_index"])
        if kind == "skill":
            selected = source_index in selected_skills
            relevance = _path_relevance(entry_relevance, f"/skills/{source_index}")
            entries.append(
                {
                    "path": f"/skills/{source_index}",
                    "action": "keep" if selected else "drop",
                    "relevance": relevance["relevance"],
                    "reason": _ranked_reason(relevance, selected),
                    "requirement_ids": relevance["requirement_ids"],
                    "fact_ids": relevance["fact_ids"],
                }
            )
            continue

        role_selected = item["id"] in selected_experience
        role = experience[source_index] if source_index < len(experience) else {}
        bullets = _array(_item(role, "bullets", [])) if isinstance(role, dict) else []
        if not bullets:
            entries.append(_role_entry(source_index, _path_relevance(entry_relevance, f"/experience/{source_index}"), role_selected))
            continue
        ranked_bullets = sorted(
            range(len(bullets)),
            key=lambda bullet_index: tuple(
                _path_relevance(entry_relevance, f"/experience/{source_index}/bullets/{bullet_index}")["rank_key"]
            ),
        )
        selected_bullets = set(ranked_bullets if bullet_limit is None else ranked_bullets[:bullet_limit])
        for bullet_index in ranked_bullets:
            bullet_selected = role_selected and bullet_index in selected_bullets
            entries.append(
                _bullet_entry(
                    source_index,
                    bullet_index,
                    _path_relevance(entry_relevance, f"/experience/{source_index}/bullets/{bullet_index}"),
                    bullet_selected,
                    role_selected,
                )
            )
    return entries


def _role_entry(source_index: int, relevance: JsonObject, selected: bool) -> JsonObject:
    return {
        "path": f"/experience/{source_index}",
        "action": "keep" if selected else "drop",
        "relevance": relevance["relevance"],
        "reason": _ranked_reason(relevance, selected),
        "requirement_ids": relevance["requirement_ids"],
        "fact_ids": relevance["fact_ids"],
    }


def _bullet_entry(source_index: int, bullet_index: int, relevance: JsonObject, selected: bool, parent_selected: bool) -> JsonObject:
    if selected:
        reason = MATCH_RELEVANCE_KEEP if _match_derived(relevance) else UNLINKED_FILL
    elif parent_selected:
        reason = MAX_CONSTRAINT_OVERFLOW if _match_derived(relevance) else UNLINKED_LOW_RELEVANCE
    else:
        reason = MAX_CONSTRAINT_OVERFLOW
    return {
        "path": f"/experience/{source_index}/bullets/{bullet_index}",
        "action": "keep" if selected else "drop",
        "relevance": relevance["relevance"],
        "reason": reason,
        "requirement_ids": relevance["requirement_ids"],
        "fact_ids": relevance["fact_ids"],
    }


def _constraint_report(
    experience: list[Any],
    skills: list[Any],
    selected_experience: set[Any],
    config: ResumeConfig,
) -> list[JsonObject]:
    selected_roles = [
        (index, role)
        for index, role in enumerate(experience)
        if (_item(role, "id", f"experience_{index}") if isinstance(role, dict) else f"experience_{index}") in selected_experience
    ]
    selected_bullet_counts = [
        {
            "role_index": index,
            "role_id": _item(role, "id", f"experience_{index}") if isinstance(role, dict) else f"experience_{index}",
            "path": f"/experience/{index}/bullets",
            "actual": _selected_bullet_count(role, config.bullets_per_role.max),
        }
        for index, role in selected_roles
    ]
    count_values = [row["actual"] for row in selected_bullet_counts]
    max_selected_bullet_count = max(count_values, default=0)
    min_selected_bullet_count = min(count_values, default=0)
    min_bullets_report = _min_report("min_bullets_per_role", config.bullets_per_role.min, min_selected_bullet_count)
    role_deficits = [
        {
            "role_index": row["role_index"],
            "role_id": row["role_id"],
            "path": row["path"],
            "limit": config.bullets_per_role.min,
            "actual": row["actual"],
        }
        for row in selected_bullet_counts
        if row["actual"] < config.bullets_per_role.min
    ]
    if role_deficits:
        min_bullets_report["role_deficits"] = role_deficits
    return [
        _max_report("max_skills", config.skills.max, len(skills)),
        _min_report("min_skills", config.skills.min, len(skills)),
        _max_report("max_experience", config.experience.max, len(experience)),
        _min_report("min_experience", config.experience.min, len(experience)),
        _max_report("max_bullets_per_role", config.bullets_per_role.max, max_selected_bullet_count),
        min_bullets_report,
    ]


def _max_report(constraint: str, limit: int | None, actual: int) -> JsonObject:
    return {
        "constraint": constraint,
        "limit": limit,
        "actual": actual,
        "status": "satisfied" if limit is None or actual <= limit else "violated",
    }


def _min_report(constraint: str, limit: int, actual: int) -> JsonObject:
    return {
        "constraint": constraint,
        "limit": limit,
        "actual": actual,
        "status": "satisfied" if actual >= limit else "deficit",
    }


def _effective_limit(limit: int | None, actual: int) -> int:
    if limit is None:
        return actual
    return max(limit, 0)


def _selected_bullet_count(role: Any, limit: int | None) -> int:
    count = len(_array(_item(role, "bullets", []))) if isinstance(role, dict) else 0
    if limit is None:
        return count
    return min(count, max(limit, 0))


def _path_relevance(entry_relevance: dict[str, JsonObject], path: str) -> JsonObject:
    return _item(
        entry_relevance,
        path,
        {
            "relevance": UNLINKED_RELEVANCE,
            "requirement_ids": [],
            "fact_ids": [],
            "rank_key": (-UNLINKED_RELEVANCE, 0, 0, 0, -1, path),
        },
    )


def _ranked_reason(relevance: JsonObject, selected: bool) -> str:
    if selected:
        return MATCH_RELEVANCE_KEEP if _match_derived(relevance) else UNLINKED_FILL
    return MAX_CONSTRAINT_OVERFLOW if _match_derived(relevance) else UNLINKED_LOW_RELEVANCE


def _match_derived(relevance: JsonObject) -> bool:
    return bool(_array(_item(relevance, "requirement_ids", []))) and float(_item(relevance, "relevance", UNLINKED_RELEVANCE)) > UNLINKED_RELEVANCE


def _item(mapping: Any, key: str, default: Any = None) -> Any:
    if isinstance(mapping, dict) and key in mapping:
        return mapping[key]
    return default


def _array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
