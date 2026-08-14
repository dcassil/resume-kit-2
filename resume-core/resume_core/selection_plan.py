"""Deterministic content selection plan construction."""

from __future__ import annotations

import re
from typing import Any

from .schemas import JsonObject, to_json_dict


def build_content_selection_plan(resume: JsonObject, terms: list[str], config: JsonObject) -> tuple[JsonObject, list[JsonObject]]:
    """Return the ContentSelectionPlan DTO and legacy ranked content."""

    experience = _array(_item(resume, "experience", []))
    skills = _array(_item(resume, "skills", []))
    section_order = list(_item(config, "section_order", ["basics", "summary", "skills", "experience", "education"]))
    experience_limit = int(_item(config, "max_experience", _item(config, "experience_max", len(experience))))
    skills_limit = int(_item(config, "max_skills", _item(config, "skills_max", len(skills))))
    bullet_limit = int(_item(config, "max_bullets_per_role", _item(config, "bullets_per_role_max", 999)))
    target_pages = _item(config, "target_pages", _item(config, "targetPages", None))
    effective_config = {
        "section_order": section_order,
        "max_experience": max(experience_limit, 0),
        "max_skills": max(skills_limit, 0),
        "max_bullets_per_role": max(bullet_limit, 0),
        "target_pages": target_pages,
    }
    ranked: list[JsonObject] = []

    for index, item in enumerate(experience):
        item_id = _item(item, "id", f"experience_{index}") if isinstance(item, dict) else f"experience_{index}"
        ranked.append({"kind": "experience", "id": item_id, "source_index": index, "score": _relevance(_text(item), terms)})
    for index, item in enumerate(skills):
        ranked.append({"kind": "skill", "id": f"skill_{index}", "source_index": index, "score": _relevance(_text(item), terms)})

    ranked.sort(key=lambda item: (-item["score"], item["kind"], item["source_index"]))
    selected_experience_ids = [item["id"] for item in ranked if item["kind"] == "experience"][: max(experience_limit, 0)]
    selected_skill_indices = [item["source_index"] for item in ranked if item["kind"] == "skill"][: max(skills_limit, 0)]
    selected_experience = set(selected_experience_ids)
    selected_skills = set(selected_skill_indices)
    entries = _selection_entries(ranked, experience, selected_experience, selected_skills)
    skills_status = "satisfied" if len(skills) <= max(skills_limit, 0) else "violated"
    return (
        {
            "schema_version": "content-selection-plan.v1",
            "sections": section_order,
            "entries": entries,
            "constraint_report": [
                {
                    "constraint": "max_skills",
                    "limit": max(skills_limit, 0),
                    "actual": len(skills),
                    "status": skills_status,
                }
            ],
            "metadata": {"target_pages": target_pages, "config_snapshot": effective_config},
        },
        ranked,
    )


def _selection_entries(
    ranked: list[JsonObject],
    experience: list[Any],
    selected_experience: set[Any],
    selected_skills: set[Any],
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
            entries.append(_bullet_entry(source_index, bullet_index, relevance, role_selected))
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


def _bullet_entry(source_index: int, bullet_index: int, relevance: int, selected: bool) -> JsonObject:
    return {
        "path": f"/experience/{source_index}/bullets/{bullet_index}",
        "action": "keep" if selected else "drop",
        "relevance": relevance,
        "reason": (
            "Selected with parent role by deterministic relevance ranking within max_experience."
            if selected
            else "Dropped with parent role by deterministic relevance ranking beyond max_experience."
        ),
        "requirement_ids": [],
        "fact_ids": [],
    }


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
