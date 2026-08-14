"""Deterministic content selection plan construction."""

from __future__ import annotations

from typing import Any

from .resume_config import ResumeConfig
from .selection_ranking import UNLINKED_RELEVANCE
from .schemas import JsonObject


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
                    "reason": (
                        "Selected by deterministic relevance ranking within max_skills."
                        if selected
                        else "Dropped by deterministic relevance ranking beyond max_skills."
                    ),
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
        "reason": (
            "Selected by deterministic relevance ranking within max_experience."
            if selected
            else "Dropped by deterministic relevance ranking beyond max_experience."
        ),
        "requirement_ids": relevance["requirement_ids"],
        "fact_ids": relevance["fact_ids"],
    }


def _bullet_entry(source_index: int, bullet_index: int, relevance: JsonObject, selected: bool, parent_selected: bool) -> JsonObject:
    if selected:
        reason = "Selected with parent role by deterministic relevance ranking within max_experience."
    elif parent_selected:
        reason = "Dropped by deterministic relevance ranking beyond max_bullets_per_role."
    else:
        reason = "Dropped with parent role by deterministic relevance ranking beyond max_experience."
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
    selected_bullet_counts = [_selected_bullet_count(role, config.bullets_per_role.max) for _index, role in selected_roles]
    max_selected_bullet_count = max(selected_bullet_counts, default=0)
    min_selected_bullet_count = min(selected_bullet_counts, default=0)
    return [
        _max_report("max_skills", config.skills.max, len(skills)),
        _min_report("min_skills", config.skills.min, len(skills)),
        _max_report("max_experience", config.experience.max, len(experience)),
        _min_report("min_experience", config.experience.min, len(experience)),
        _max_report("max_bullets_per_role", config.bullets_per_role.max, max_selected_bullet_count),
        _min_report("min_bullets_per_role", config.bullets_per_role.min, min_selected_bullet_count),
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


def _item(mapping: Any, key: str, default: Any = None) -> Any:
    if isinstance(mapping, dict) and key in mapping:
        return mapping[key]
    return default


def _array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
