"""Public runtime package for resume-render.

The renderer is deliberately semantic-neutral: it formats the resume data it is
given, reports layout pressure, and validates parse-back text without looking up
or changing career facts.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any


RenderDict = dict[str, Any]

_SKIP_KEYS = {
    "id",
    "schema_version",
    "metadata",
    "verification",
}
_HEADING_PREFIXES = ("#", "##", "###")
_UNSUPPORTED_CHARACTERS = {
    "\u2018": "left single quote",
    "\u2019": "right single quote",
    "\u201c": "left double quote",
    "\u201d": "right double quote",
    "\u2022": "bullet character",
    "\u00a0": "non-breaking space",
}


def _typed_error(kind: str, message: str, fmt: str | None = None) -> RenderDict:
    result: RenderDict = {
        "status": "error",
        "error": {"type": kind, "message": message},
        "warnings": [],
    }
    if fmt is not None:
        result["format"] = fmt
        result["template_version"] = "unknown"
        result["semantic_fingerprint"] = _fingerprint("")
    return result


def _fingerprint(text: str) -> str:
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _is_internal_key(key: str) -> bool:
    lowered = key.lower()
    return lowered.startswith("_") or lowered.startswith("internal") or "provenance" in lowered


def _validate_resume(resume: Any) -> str | None:
    if not isinstance(resume, dict):
        return "Resume must be an object."
    sections = resume.get("sections")
    if not isinstance(sections, list) or not sections:
        return "Resume must include a non-empty sections list."
    return None


def _validate_template(template: Any, *, require_version: bool = True) -> str | None:
    if not isinstance(template, dict):
        return "Template must be an object."
    if require_version and not template.get("template_version"):
        return "Template must include template_version."
    section_order = template.get("section_order")
    if section_order is not None and not isinstance(section_order, list):
        return "Template section_order must be a list when provided."
    return None


def _template_version(template: dict[str, Any]) -> str:
    version = template.get("template_version")
    return str(version) if version is not None else "unknown"


def _ordered_sections(resume: dict[str, Any], template: dict[str, Any]) -> list[dict[str, Any]]:
    sections = [section for section in resume.get("sections", []) if isinstance(section, dict)]
    by_id = {str(section.get("id")): section for section in sections if section.get("id") is not None}
    order = template.get("section_order")
    if not isinstance(order, list):
        return sections

    ordered: list[dict[str, Any]] = []
    seen: set[int] = set()
    for section_id in order:
        section = by_id.get(str(section_id))
        if section is not None:
            ordered.append(section)
            seen.add(id(section))
    ordered.extend(section for section in sections if id(section) not in seen)
    return ordered


def _section_ids(sections: list[dict[str, Any]]) -> list[str]:
    result: list[str] = []
    for section in sections:
        value = section.get("id") or section.get("heading")
        if value is not None:
            result.append(str(value))
    return result


def _clean_scalar(value: Any) -> str:
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(part.strip() for part in text.splitlines()).strip()


def _collect_scalar_lines(value: Any) -> list[str]:
    if isinstance(value, (str, int, float, bool)):
        text = _clean_scalar(value)
        return [text] if text else []
    if isinstance(value, list):
        lines: list[str] = []
        for entry in value:
            lines.extend(_collect_scalar_lines(entry))
        return lines
    if isinstance(value, dict):
        lines = []
        for key, entry in value.items():
            if _is_internal_key(str(key)) or str(key) in _SKIP_KEYS:
                continue
            lines.extend(_collect_scalar_lines(entry))
        return lines
    return []


def _render_basics(resume: dict[str, Any]) -> list[str]:
    basics = resume.get("basics")
    if not isinstance(basics, dict):
        return []

    lines: list[str] = []
    name = basics.get("name")
    if name:
        lines.append(f"# {_clean_scalar(name)}")

    contact_parts: list[str] = []
    for key in ("email", "phone", "location", "website", "linkedin", "github"):
        value = basics.get(key)
        if value:
            contact_parts.append(_clean_scalar(value))
    if contact_parts:
        lines.append(" | ".join(contact_parts))
    return lines


def _render_item(item: Any) -> list[str]:
    if isinstance(item, (str, int, float, bool)):
        text = _clean_scalar(item)
        return [text] if text else []

    if isinstance(item, list):
        lines: list[str] = []
        for entry in item:
            lines.extend(_render_item(entry))
        return lines

    if not isinstance(item, dict):
        return []

    lines: list[str] = []
    title = _clean_scalar(item.get("title", "")) if item.get("title") else ""
    company = _clean_scalar(item.get("company", "")) if item.get("company") else ""
    start = _clean_scalar(item.get("start_date", "")) if item.get("start_date") else ""
    end = _clean_scalar(item.get("end_date", "")) if item.get("end_date") else ""

    heading_parts = [part for part in (title, company) if part]
    date_parts = [part for part in (start, end) if part]
    if heading_parts or date_parts:
        heading = " - ".join(heading_parts)
        if date_parts:
            heading = f"{heading} ({' to '.join(date_parts)})" if heading else " to ".join(date_parts)
        lines.append(heading)

    for key in ("summary", "description"):
        value = item.get(key)
        if value:
            lines.extend(_collect_scalar_lines(value))

    bullets = item.get("bullets")
    if isinstance(bullets, list):
        for bullet in bullets:
            for line in _collect_scalar_lines(bullet):
                lines.append(f"- {line}")

    consumed = {
        "title",
        "company",
        "start_date",
        "end_date",
        "summary",
        "description",
        "bullets",
    }
    for key, value in item.items():
        key_text = str(key)
        if key_text in consumed or key_text in _SKIP_KEYS or _is_internal_key(key_text):
            continue
        for line in _collect_scalar_lines(value):
            lines.append(line)
    return lines


def _render_section(section: dict[str, Any]) -> list[str]:
    heading = _clean_scalar(section.get("heading") or section.get("id") or "Section")
    lines = [f"## {heading}"]
    items = section.get("items", [])

    if section.get("id") == "skills" and isinstance(items, list):
        skills = [_clean_scalar(item) for item in items if isinstance(item, (str, int, float, bool))]
        if skills:
            lines.append(", ".join(skill for skill in skills if skill))
            return lines

    if isinstance(items, list):
        for item in items:
            rendered = _render_item(item)
            if rendered:
                lines.extend(rendered)
    else:
        lines.extend(_render_item(items))
    return lines


def _render_markdown_text(resume: dict[str, Any], template: dict[str, Any]) -> tuple[str, list[str]]:
    sections = _ordered_sections(resume, template)
    blocks: list[str] = []

    basics = _render_basics(resume)
    if basics:
        blocks.append("\n".join(basics))

    for section in sections:
        rendered = _render_section(section)
        if rendered:
            blocks.append("\n".join(rendered))

    return "\n\n".join(blocks).strip() + "\n", _section_ids(sections)


def _base_result(fmt: str, template: dict[str, Any], content: str) -> RenderDict:
    return {
        "status": "ok",
        "format": fmt,
        "template_version": _template_version(template),
        "semantic_fingerprint": _fingerprint(content),
        "warnings": [],
    }


def renderMarkdown(resume: Any, template: Any) -> RenderDict:
    """Render a canonical resume to Markdown without changing semantic content."""

    if error := _validate_resume(resume):
        return _typed_error("validation_error", error, "markdown")
    if error := _validate_template(template):
        return _typed_error("validation_error", error, "markdown")

    content, sections = _render_markdown_text(resume, template)
    result = _base_result("markdown", template, content)
    result.update({"content": content, "sections": sections})
    return result


def renderDocx(resume: Any, template: Any) -> RenderDict:
    """Render a DOCX-compatible artifact description from canonical text."""

    if error := _validate_resume(resume):
        return _typed_error("validation_error", error, "docx")
    if error := _validate_template(template):
        return _typed_error("validation_error", error, "docx")

    content, sections = _render_markdown_text(resume, template)
    result = _base_result("docx", template, content)
    result.update(
        {
            "artifact": {
                "kind": "docx",
                "media_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "text": content,
            },
            "sections": sections,
        }
    )
    return result


def renderPdf(resume: Any, template: Any) -> RenderDict:
    """Render a PDF artifact when the template declares PDF support."""

    if error := _validate_resume(resume):
        return _typed_error("validation_error", error, "pdf")
    if error := _validate_template(template):
        return _typed_error("validation_error", error, "pdf")

    content, sections = _render_markdown_text(resume, template)
    result = _base_result("pdf", template, content)
    targets = template.get("format_targets")
    if isinstance(targets, list) and "pdf" not in {str(target).lower() for target in targets}:
        result["status"] = "unsupported"
        result["warnings"] = ["Template does not declare PDF as a format target."]
        result["sections"] = sections
        return result

    result.update(
        {
            "artifact": {
                "kind": "pdf",
                "media_type": "application/pdf",
                "text": content,
            },
            "sections": sections,
        }
    )
    return result


def measureLayout(resume: Any, template: Any) -> RenderDict:
    """Estimate layout pressure without removing or changing content."""

    if error := _validate_resume(resume):
        return _typed_error("validation_error", error)
    if error := _validate_template(template, require_version=False):
        return _typed_error("validation_error", error)

    try:
        target_pages = int(template.get("target_pages", 1))
    except (TypeError, ValueError):
        return _typed_error("validation_error", "Template target_pages must be an integer.")
    if target_pages < 1:
        return _typed_error("validation_error", "Template target_pages must be at least 1.")

    content, _sections = _render_markdown_text(resume, template)
    non_empty_lines = [line for line in content.splitlines() if line.strip()]
    estimated_lines = 0
    for line in non_empty_lines:
        estimated_lines += max(1, math.ceil(len(line) / 90))
    estimated_pages = max(1, math.ceil(estimated_lines / 45))
    required_reduction = max(0, estimated_pages - target_pages)
    status = "overflow" if required_reduction else "fits"

    return {
        "status": status,
        "estimated_pages": estimated_pages,
        "target_pages": target_pages,
        "required_reduction": required_reduction,
        "constraints": {
            "line_capacity_per_page": 45,
            "character_wrap_width": 90,
            "content_lines": estimated_lines,
        },
        "warnings": ["Content exceeds target page estimate."] if status == "overflow" else [],
    }


def _extract_text(file: Any) -> tuple[str | None, str | None, dict[str, Any]]:
    if isinstance(file, str):
        return file, "markdown", {}
    if not isinstance(file, dict):
        return None, None, {}

    fmt = str(file.get("format") or "unknown")
    if isinstance(file.get("content"), str):
        return file["content"], fmt, file

    artifact = file.get("artifact")
    if isinstance(artifact, dict) and isinstance(artifact.get("text"), str):
        return artifact["text"], str(artifact.get("kind") or fmt), file

    if isinstance(file.get("text"), str):
        return file["text"], fmt, file

    return None, fmt, file


def _heading_names(text: str) -> set[str]:
    headings: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(_HEADING_PREFIXES):
            headings.add(stripped.lstrip("#").strip().lower())
    return headings


def _expected_terms(expected_resume: Any) -> list[str]:
    if not isinstance(expected_resume, dict):
        return []
    terms: list[str] = []
    for section in expected_resume.get("sections", []):
        if not isinstance(section, dict):
            continue
        for line in _render_section(section):
            stripped = line.lstrip("-").strip()
            if stripped and not stripped.startswith("#"):
                terms.append(stripped)
    return terms


def validateRenderedOutput(file: Any) -> RenderDict:
    """Validate parse-back text and renderer-specific ATS concerns."""

    text, fmt, payload = _extract_text(file)
    if text is None or fmt is None or fmt == "unknown":
        return {
            "status": "error",
            "format": fmt or "unknown",
            "error": {"type": "validation_error", "message": "Rendered output must include readable text."},
            "text_extracted": "",
            "missing_sections": [],
            "unsupported_characters": [],
            "semantic_differences": [],
            "warnings": [],
        }

    expected_resume = payload.get("expected_resume") if isinstance(payload, dict) else None
    headings = _heading_names(text)
    missing_sections: list[str] = []
    if isinstance(expected_resume, dict):
        for section in expected_resume.get("sections", []):
            if not isinstance(section, dict):
                continue
            heading = str(section.get("heading") or section.get("id") or "").strip()
            if heading and heading.lower() not in headings:
                missing_sections.append(heading)

    lowered_text = text.lower()
    semantic_differences = [
        term
        for term in _expected_terms(expected_resume)
        if term.lower() not in lowered_text
    ]
    unsupported_characters = [
        {"character": character, "description": description}
        for character, description in _UNSUPPORTED_CHARACTERS.items()
        if character in text
    ]
    warnings: list[str] = []
    if not text.strip():
        warnings.append("Rendered output is empty.")
    if missing_sections:
        warnings.append("Rendered output is missing section headings.")
    if semantic_differences:
        warnings.append("Rendered output is missing expected text.")
    if unsupported_characters:
        warnings.append("Rendered output contains unsupported characters.")

    return {
        "status": "fail" if warnings else "pass",
        "format": fmt,
        "text_extracted": text,
        "missing_sections": missing_sections,
        "unsupported_characters": unsupported_characters,
        "semantic_differences": semantic_differences,
        "warnings": warnings,
    }


__all__ = [
    "renderMarkdown",
    "renderDocx",
    "renderPdf",
    "measureLayout",
    "validateRenderedOutput",
]
