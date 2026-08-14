"""Deterministic content selection plan construction."""

from __future__ import annotations

import re
from typing import Any

from .resume_config import ResumeConfig
from .schemas import JsonObject, to_json_dict


def build_content_selection_plan(resume: JsonObject, terms: list[str], config: ResumeConfig) -> tuple[JsonObject, list[JsonObject]]:
    """Return the ContentSelectionPlan DTO and legacy ranked content."""

    experience = _array(_item(resume, "experience", []))
    skills = _array(_item(resume, "skills", []))
    section_order = list(config.section_order)
    experience_limit = _effective_limit(config.experience.max, len(experience))
    skills_limit = _effective_limit(config.skills.max, len(skills))
    bullet_limit = config.bullets_per_role.max
    target_pages = config.target_pages
    ranked: list[JsonObject] = []

    for index, item in enumerate(experience):
        item_id = _item(item, "id", f"experience_{index}") if isinstance(item, dict) else f"experience_{index}"
        ranked.append({"kind": "experience", "id": item_id, "source_index": index, "score": _relevance(_text(item), terms)})
    for index, item in enumerate(skills):
        ranked.append({"kind": "skill", "id": f"skill_{index}", "source_index": index, "score": _relevance(_text(item), terms)})

    ranked.sort(key=lambda item: (-item["score"], item["kind"], item["source_index"]))
    selected_experience_ids = [item["id"] for item in ranked if item["kind"] == "experience"][:experience_limit]
    selected_skill_indices = [item["source_index"] for item in ranked if item["kind"] == "skill"][:skills_limit]
    selected_experience = set(selected_experience_ids)
    selected_skills = set(selected_skill_indices)
    entries = _selection_entries(ranked, experience, selected_experience, selected_skills, bullet_limit)
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
) -> list[JsonObject]:
    entries: list[JsonObject] = []
    for item in ranked:
        kind = item["kind"]
        source_index = int(item["source_index"])
        relevance = item["score"]
        if kind == "skill":
            selected = source_index in selected_skills
            entries.append(
                {
                    "path": f"/skills/{source_index}",
                    "action": "keep" if selected else "drop",
                    "relevance": relevance,
                    "reason": (
                        "Selected by deterministic relevance ranking within max_skills."
                        if selected
                        else "Dropped by deterministic relevance ranking beyond max_skills."
                    ),
                    "requirement_ids": [],
                    "fact_ids": [],
                }
            )
            continue

        role_selected = item["id"] in selected_experience
        role = experience[source_index] if source_index < len(experience) else {}
        bullets = _array(_item(role, "bullets", [])) if isinstance(role, dict) else []
        if not bullets:
            entries.append(_role_entry(source_index, relevance, role_selected))
            continue
        for bullet_index, _bullet in enumerate(bullets):
            bullet_selected = role_selected and (bullet_limit is None or bullet_index < bullet_limit)
            entries.append(_bullet_entry(source_index, bullet_index, relevance, bullet_selected, role_selected))
    return entries


def _role_entry(source_index: int, relevance: int, selected: bool) -> JsonObject:
    return {
        "path": f"/experience/{source_index}",
        "action": "keep" if selected else "drop",
        "relevance": relevance,
        "reason": (
            "Selected by deterministic relevance ranking within max_experience."
            if selected
            else "Dropped by deterministic relevance ranking beyond max_experience."
        ),
        "requirement_ids": [],
        "fact_ids": [],
    }


def _bullet_entry(source_index: int, bullet_index: int, relevance: int, selected: bool, parent_selected: bool) -> JsonObject:
    if selected:
        reason = "Selected with parent role by deterministic relevance ranking within max_experience."
    elif parent_selected:
        reason = "Dropped by deterministic relevance ranking beyond max_bullets_per_role."
    else:
        reason = "Dropped with parent role by deterministic relevance ranking beyond max_experience."
    return {
        "path": f"/experience/{source_index}/bullets/{bullet_index}",
        "action": "keep" if selected else "drop",
        "relevance": relevance,
        "reason": reason,
        "requirement_ids": [],
        "fact_ids": [],
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
        len(_array(_item(role, "bullets", []))) if isinstance(role, dict) else 0
        for _index, role in selected_roles
    ]
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


def _item(mapping: Any, key: str, default: Any = None) -> Any:
    if isinstance(mapping, dict) and key in mapping:
        return mapping[key]
    return default


def _array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    value = to_json_dict(value)
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


def _normal_text(value: Any) -> str:
    text = str(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _term_in_text(term: Any, text: str) -> bool:
    normalized = _normal_text(term)
    normalized_text = _normal_text(text)
    if not normalized or not normalized_text:
        return False
    if " " in normalized:
        return normalized in normalized_text
    words = normalized_text.split()
    return normalized in words or f"{normalized}s" in words or (normalized.endswith("s") and normalized[:-1] in words)


def _relevance(text: Any, terms: list[str]) -> int:
    normalized = _normal_text(text)
    return sum(1 for term in terms if _term_in_text(term, normalized))
