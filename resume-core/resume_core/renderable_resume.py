"""Deterministic derivation of renderer-safe resumes from canonical resumes."""

from __future__ import annotations

import copy
import re
from typing import Any

from .resume_config import resolve_resume_config
from .schemas import CANONICAL_RESUME_SCHEMA, RENDERABLE_RESUME_SCHEMA_VERSION, JsonObject, VerificationState, to_json_dict


RESULT_SCHEMA_VERSION = "resume-core.result.v1"
_INTERNAL_KEYS = {
    "claim_id",
    "metadata",
    "provenance",
    "source",
    "verification",
    "verification_state",
}
_SECTION_TITLES = {
    "summary": "Summary",
    "skills": "Skills",
    "experience": "Experience",
    "projects": "Projects",
    "education": "Education",
    "certifications": "Certifications",
    "awards": "Awards",
}
_CANONICAL_SECTION_FIELDS = ("summary", "skills", "experience", "projects", "education", "certifications", "awards")


def toRenderableResume(canonical_resume: Any, template: JsonObject | None = None) -> JsonObject:
    """Return a validated RenderableResume result derived from canonical input."""

    resume = _unwrap(canonical_resume, "canonical_resume")
    template_payload = _unwrap(template or {}, "template")
    errors = _canonical_errors(resume)
    config_result = resolve_resume_config(_template_resume_config(template_payload))
    errors.extend(config_result.errors)
    warnings = list(config_result.warnings)
    if errors:
        return _result("error", renderable_resume={}, errors=errors, warnings=warnings)

    renderable = _derive_renderable(resume, config_result.config.section_order)
    return _result("ok", renderable_resume=renderable, errors=[], warnings=warnings)


def _derive_renderable(resume: JsonObject, section_order: list[str]) -> JsonObject:
    known_sections = _known_sections(resume)
    ordered: list[JsonObject] = []
    emitted: set[str] = set()
    for section_id in section_order:
        section = known_sections.get(section_id)
        if section is not None:
            ordered.append(section)
            emitted.add(section_id)
    for section_id in _CANONICAL_SECTION_FIELDS:
        section = known_sections.get(section_id)
        if section is not None and section_id not in emitted:
            ordered.append(section)
            emitted.add(section_id)
    ordered.extend(_additional_sections(resume))

    summary = _summary_text(_field_value(_item(resume, "summary")))
    return {
        "schema_version": RENDERABLE_RESUME_SCHEMA_VERSION,
        "contact": _contact(resume),
        **({"summary": summary} if summary else {}),
        "sections": ordered,
    }


def _known_sections(resume: JsonObject) -> dict[str, JsonObject]:
    sections: dict[str, JsonObject] = {}

    summary_entries: list[Any] = []
    title = _field_value(_item(resume, "title"))
    if _has_content(title):
        summary_entries.extend(_entry_items(title))
    summary = _field_value(_item(resume, "summary"))
    if _has_content(summary):
        summary_entries.extend(_entry_items(summary))
    if summary_entries:
        sections["summary"] = _section("summary", "Summary", summary_entries)

    skills = _array(_item(resume, "skills", []))
    if skills:
        sections["skills"] = _section("skills", "Skills", _skill_entries(skills))

    for section_id in ("experience", "projects", "education", "certifications", "awards"):
        entries = [_entry(item) for item in _array(_item(resume, section_id, [])) if _has_content(item)]
        entries = [entry for entry in entries if _has_content(entry)]
        if entries:
            sections[section_id] = _section(section_id, _SECTION_TITLES[section_id], entries)

    for section in _array(_item(resume, "sections", [])):
        if not isinstance(section, dict):
            continue
        section_id = str(_item(section, "id") or _slug(_item(section, "title") or _item(section, "heading") or "section"))
        if section_id in sections:
            continue
        entries = _section_entries(section)
        if entries:
            sections[section_id] = _section(section_id, _section_title(section, section_id), entries)

    return sections


def _additional_sections(resume: JsonObject) -> list[JsonObject]:
    result: list[JsonObject] = []
    for index, section in enumerate(_array(_item(resume, "additionalSections", _item(resume, "additional_sections", [])))):
        if not isinstance(section, dict):
            if _has_content(section):
                result.append(_section(f"additional_{index}", f"Additional {index + 1}", _entry_items(section)))
            continue
        section_id = str(_item(section, "id") or _slug(_item(section, "title") or _item(section, "heading") or f"additional_{index}"))
        entries = _section_entries(section)
        if entries:
            result.append(_section(section_id, _section_title(section, section_id), entries))
    return result


def _section_entries(section: JsonObject) -> list[Any]:
    if isinstance(_item(section, "entries"), list):
        return [_entry(item) for item in _array(_item(section, "entries")) if _has_content(item)]
    if isinstance(_item(section, "items"), list):
        return [_entry(item) for item in _array(_item(section, "items")) if _has_content(item)]
    content = _field_value(_item(section, "content"))
    return _entry_items(content) if _has_content(content) else []


def _section(section_id: str, title: str, entries: list[Any]) -> JsonObject:
    return {"id": section_id, "title": title, "entries": copy.deepcopy(entries)}


def _section_title(section: JsonObject, section_id: str) -> str:
    return _text(_item(section, "title") or _item(section, "heading") or _SECTION_TITLES.get(section_id) or section_id.replace("_", " ").title())


def _skill_entries(skills: list[Any]) -> list[Any]:
    simple: list[str] = []
    grouped: list[Any] = []
    for item in skills:
        value = _field_value(item)
        if isinstance(value, dict):
            group_skills = _array(_item(value, "skills", _item(value, "items", [])))
            if group_skills:
                if simple:
                    grouped.append({"skills": simple})
                    simple = []
                group = _text(_item(value, "group") or _item(value, "category") or _item(value, "title"))
                entry = {"skills": [_text(_field_value(skill)) for skill in group_skills if _has_content(skill)]}
                if group:
                    entry["title"] = group
                grouped.append(entry)
            elif _has_content(value):
                simple.append(_text(value))
        elif _has_content(value):
            simple.append(_text(value))
    if simple:
        grouped.append({"skills": simple})
    return grouped


def _entry(item: Any) -> Any:
    value = _field_value(item)
    if isinstance(value, list):
        return [_entry(entry) for entry in value if _has_content(entry)]
    if not isinstance(value, dict):
        return _text(value)

    result: JsonObject = {}
    for source_key, target_key in (
        ("title", "title"),
        ("company", "company"),
        ("employer", "company"),
        ("organization", "organization"),
        ("institution", "organization"),
        ("start_date", "start_date"),
        ("startDate", "start_date"),
        ("end_date", "end_date"),
        ("endDate", "end_date"),
        ("date", "date"),
        ("dates", "date"),
        ("summary", "summary"),
        ("description", "description"),
        ("degree", "degree"),
        ("field", "field"),
        ("credential", "credential"),
        ("issuer", "issuer"),
    ):
        if source_key in value and _has_content(value[source_key]):
            result[target_key] = _field_value(value[source_key])

    for key in ("bullets", "highlights"):
        if isinstance(_item(value, key), list):
            result["bullets"] = [_field_value(entry) for entry in _array(_item(value, key)) if _has_content(entry)]
            break
    if isinstance(_item(value, "skills"), list):
        result["skills"] = [_field_value(entry) for entry in _array(_item(value, "skills")) if _has_content(entry)]

    for key in sorted(value):
        key_text = str(key)
        if key_text in result or key_text in _INTERNAL_KEYS or key_text in {"id", "startDate", "endDate", "highlights"}:
            continue
        if key_text in {
            "title",
            "company",
            "employer",
            "organization",
            "institution",
            "start_date",
            "end_date",
            "date",
            "dates",
            "summary",
            "description",
            "degree",
            "field",
            "credential",
            "issuer",
            "bullets",
            "skills",
        }:
            continue
        extra = _field_value(value[key])
        if _has_content(extra):
            result[key_text] = extra
    return result


def _entry_items(value: Any) -> list[Any]:
    value = _field_value(value)
    if isinstance(value, list):
        return [_entry(item) for item in value if _has_content(item)]
    if _has_content(value):
        return [_entry(value)]
    return []


def _contact(resume: JsonObject) -> JsonObject:
    raw = _item(resume, "contact")
    if not isinstance(raw, dict):
        raw = _item(resume, "basics", {})
    raw = raw if isinstance(raw, dict) else {}
    links = _links(raw)
    return {
        "name": _text(_item(raw, "name")),
        "email": _text(_item(raw, "email")),
        "phone": _text(_item(raw, "phone")),
        "links": links,
    }


def _links(contact: JsonObject) -> list[Any]:
    raw_links = _item(contact, "links")
    if isinstance(raw_links, list):
        return [_field_value(link) for link in raw_links if _has_content(link)]
    links: list[Any] = []
    for key in ("website", "url", "linkedin", "github", "portfolio"):
        value = _field_value(_item(contact, key))
        if _has_content(value):
            links.append(value)
    return links


def _summary_text(value: Any) -> str:
    value = _field_value(value)
    if isinstance(value, list):
        return "\n".join(_text(item) for item in value if _has_content(item))
    return _text(value)


def _template_resume_config(template: Any) -> JsonObject:
    if not isinstance(template, dict):
        return {}
    if isinstance(template.get("resume"), dict):
        return copy.deepcopy(template)
    if "section_order" in template:
        return {"resume": {"sectionOrder": copy.deepcopy(template.get("section_order"))}}
    if "sectionOrder" in template:
        return {"resume": {"sectionOrder": copy.deepcopy(template.get("sectionOrder"))}}
    return {}


def _canonical_errors(resume: Any) -> list[JsonObject]:
    if not isinstance(resume, dict):
        return [_issue("invalid_resume", "canonical_resume must be an object.")]
    if _legacy_sections_only(resume):
        return []
    errors: list[JsonObject] = []
    for field_name in CANONICAL_RESUME_SCHEMA["required"]:
        if field_name not in resume:
            errors.append(_issue("missing_field", f"CanonicalResume requires {field_name}.", str(field_name)))
    for field_name in ("experience", "skills", "education"):
        if field_name in resume and not isinstance(resume[field_name], list):
            errors.append(_issue("invalid_array", f"{field_name} must be an array.", field_name))
    state = _item(resume, "verification_state")
    if state is not None and state not in {item.value for item in VerificationState}:
        errors.append(_issue("invalid_verification_state", "Unknown verification state.", "verification_state"))
    return errors


def _legacy_sections_only(resume: JsonObject) -> bool:
    if not isinstance(resume.get("sections"), list):
        return False
    return not all(field_name in resume for field_name in CANONICAL_RESUME_SCHEMA["required"])


def _field_value(value: Any) -> Any:
    value = to_json_dict(value)
    if isinstance(value, dict) and "value" in value:
        return _field_value(value["value"])
    if isinstance(value, list):
        return [_field_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _field_value(item) for key, item in value.items() if str(key) not in _INTERNAL_KEYS}
    return value


def _has_content(value: Any) -> bool:
    value = _field_value(value)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_has_content(item) for item in value)
    if isinstance(value, dict):
        return any(_has_content(item) for item in value.values())
    return True


def _text(value: Any) -> str:
    value = _field_value(value)
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(_text(item) for item in value if _has_content(item)).strip()
    if isinstance(value, dict):
        return " ".join(_text(item) for key, item in sorted(value.items()) if str(key) not in _INTERNAL_KEYS).strip()
    return str(value).strip()


def _slug(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", _text(value).lower()).strip("_")
    return text or "section"


def _array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _item(mapping: Any, key: str, default: Any = None) -> Any:
    if isinstance(mapping, dict) and key in mapping:
        return mapping[key]
    return default


def _unwrap(value: Any, key: str) -> Any:
    payload = to_json_dict(value)
    if isinstance(payload, dict) and key in payload:
        return payload[key]
    return payload


def _issue(code: str, message: str, field_path: str | None = None, details: JsonObject | None = None) -> JsonObject:
    issue: JsonObject = {"code": code, "message": message, "severity": "error"}
    if field_path is not None:
        issue["field_path"] = field_path
    if details:
        issue["details"] = details
    return issue


def _result(status: str, **fields: Any) -> JsonObject:
    return {"schema_version": RESULT_SCHEMA_VERSION, "status": status, **to_json_dict(fields)}
