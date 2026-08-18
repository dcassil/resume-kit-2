"""Public runtime package for resume-render.

The renderer is deliberately semantic-neutral: it formats the resume data it is
given, reports layout pressure, and validates parse-back text without looking up
or changing career facts.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import io
import math
import re
import zipfile
from typing import Any
from xml.etree import ElementTree

from resume_core import RENDERABLE_RESUME_SCHEMA

from ._ooxml import DEFAULT_LAYOUT, W_NS, build_docx, layout_from_template, layout_validation_error


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
_SANITATION_REPLACEMENTS = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2022": "-",
    "\u00a0": " ",
}
_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_XML_DECL_RE = re.compile(br"<\?xml[^>]*encoding=[\"']([^\"']+)[\"']", re.IGNORECASE)


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


def _schema_types(schema: dict[str, Any]) -> set[str]:
    raw = schema.get("type")
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {str(item) for item in raw}
    return set()


def _schema_matches_value(schema: dict[str, Any], value: Any) -> bool:
    types = _schema_types(schema)
    if not types:
        return True
    if isinstance(value, dict):
        return "object" in types
    if isinstance(value, list):
        return "array" in types
    if isinstance(value, str):
        return "string" in types
    if isinstance(value, bool):
        return "boolean" in types
    if isinstance(value, (int, float)):
        return bool({"number", "integer"} & types)
    if value is None:
        return "null" in types
    return False


def _strip_to_schema(value: Any, schema: dict[str, Any]) -> Any:
    for variants_key in ("oneOf", "anyOf"):
        variants = schema.get(variants_key)
        if isinstance(variants, list):
            for variant in variants:
                if isinstance(variant, dict) and _schema_matches_value(variant, value):
                    return _strip_to_schema(value, variant)
            return None

    types = _schema_types(schema)
    if not types:
        return copy.deepcopy(value)

    if "object" in types:
        if not isinstance(value, dict):
            return None
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            return copy.deepcopy(value)
        stripped: dict[str, Any] = {}
        for key, nested_schema in properties.items():
            if key not in value:
                continue
            nested = _strip_to_schema(value[key], nested_schema if isinstance(nested_schema, dict) else {})
            if nested is not None:
                stripped[str(key)] = nested
        return stripped

    if "array" in types:
        if not isinstance(value, list):
            return None
        item_schema = schema.get("items")
        if not isinstance(item_schema, dict):
            return copy.deepcopy(value)
        stripped_items = []
        for item in value:
            stripped = _strip_to_schema(item, item_schema)
            if stripped is not None:
                stripped_items.append(stripped)
        return stripped_items

    return copy.deepcopy(value) if _schema_matches_value(schema, value) else None


def _renderable_resume(resume: dict[str, Any]) -> dict[str, Any]:
    stripped = _strip_to_schema(resume, RENDERABLE_RESUME_SCHEMA)
    return stripped if isinstance(stripped, dict) else {}


def _validate_resume(resume: Any) -> str | None:
    if not isinstance(resume, dict):
        return "Resume must be an object."
    for field_name in RENDERABLE_RESUME_SCHEMA.get("required", []):
        if field_name not in resume:
            return f"RenderableResume requires {field_name}."
    contact = resume.get("contact")
    if not isinstance(contact, dict):
        return "RenderableResume contact must be an object."
    for field_name in RENDERABLE_RESUME_SCHEMA["properties"]["contact"].get("required", []):
        if field_name not in contact:
            return f"RenderableResume contact requires {field_name}."
    if not isinstance(contact.get("links"), list):
        return "RenderableResume contact.links must be a list."
    sections = resume.get("sections")
    if not isinstance(sections, list):
        return "RenderableResume sections must be a list."
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            return f"RenderableResume sections.{index} must be an object."
        for field_name in RENDERABLE_RESUME_SCHEMA["properties"]["sections"]["items"].get("required", []):
            if field_name not in section:
                return f"RenderableResume sections.{index} requires {field_name}."
        if not isinstance(section.get("entries"), list):
            return f"RenderableResume sections.{index}.entries must be a list."
    return None


def _validate_template(template: Any, *, require_version: bool = True) -> str | None:
    if not isinstance(template, dict):
        return "Template must be an object."
    if require_version and not template.get("template_version"):
        return "Template must include template_version."
    section_order = template.get("section_order")
    if section_order is not None and not isinstance(section_order, list):
        return "Template section_order must be a list when provided."
    if error := layout_validation_error(template):
        return error
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


def _section_text_blocks(resume: dict[str, Any], template: dict[str, Any]) -> list[tuple[str, str]]:
    sections = _ordered_sections(resume, template)
    blocks: list[tuple[str, str]] = []

    basics = _render_basics(resume)
    if basics:
        blocks.append(("basics", "\n".join(basics)))

    for section in sections:
        rendered = _render_section(section)
        if rendered:
            section_id = str(section.get("id") or section.get("heading") or "section")
            blocks.append((section_id, "\n".join(rendered)))
    return blocks


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
            if str(key) in _SKIP_KEYS:
                continue
            lines.extend(_collect_scalar_lines(entry))
        return lines
    return []


def _render_basics(resume: dict[str, Any]) -> list[str]:
    basics = resume.get("contact") or resume.get("basics")
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
    links = basics.get("links")
    if isinstance(links, list):
        for link in links:
            if isinstance(link, dict):
                value = link.get("url") or link.get("href") or link.get("label")
            else:
                value = link
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
    organization = _clean_scalar(item.get("organization", "")) if item.get("organization") else ""
    start = _clean_scalar(item.get("start_date", "")) if item.get("start_date") else ""
    end = _clean_scalar(item.get("end_date", "")) if item.get("end_date") else ""
    date = _clean_scalar(item.get("date", "")) if item.get("date") else ""

    heading_parts = [part for part in (title, company or organization) if part]
    date_parts = [part for part in (start, end) if part] or ([date] if date else [])
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

    skills = item.get("skills")
    if isinstance(skills, list):
        rendered_skills = [_clean_scalar(skill) for skill in skills if isinstance(skill, (str, int, float, bool))]
        if rendered_skills:
            prefix = f"{title}: " if title and not (heading_parts or date_parts) else ""
            lines.append(prefix + ", ".join(skill for skill in rendered_skills if skill))

    consumed = {
        "title",
        "company",
        "organization",
        "start_date",
        "end_date",
        "date",
        "summary",
        "description",
        "bullets",
        "skills",
    }
    for key, value in item.items():
        key_text = str(key)
        if key_text in consumed or key_text in _SKIP_KEYS:
            continue
        for line in _collect_scalar_lines(value):
            lines.append(line)
    return lines


def _section_heading(section: dict[str, Any]) -> str:
    return _clean_scalar(section.get("title") or section.get("heading") or section.get("id") or "Section")


def _section_format(section: dict[str, Any]) -> str:
    value = section.get("format") or section.get("kind")
    return _clean_scalar(value).lower() if isinstance(value, str) and value.strip() else "default"


def _render_section(section: dict[str, Any]) -> list[str]:
    heading = _section_heading(section)
    lines = [f"## {heading}"]
    items = section.get("entries") if "entries" in section else section.get("items", [])

    if _section_format(section) == "skills" and isinstance(items, list):
        skills: list[str] = []
        grouped: list[str] = []
        for item in items:
            if isinstance(item, (str, int, float, bool)):
                skills.append(_clean_scalar(item))
            elif isinstance(item, dict) and isinstance(item.get("skills"), list):
                rendered = [_clean_scalar(skill) for skill in item["skills"] if isinstance(skill, (str, int, float, bool))]
                if rendered:
                    group = _clean_scalar(item.get("title", "")) if item.get("title") else ""
                    grouped.append(f"{group}: {', '.join(rendered)}" if group else ", ".join(rendered))
        if skills or grouped:
            lines.extend(grouped)
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
    blocks = [block for _section_id, block in _section_text_blocks(resume, template)]
    return "\n\n".join(blocks).strip() + "\n", _section_ids(sections)


def _expected_headings(resume: dict[str, Any], template: dict[str, Any]) -> list[str]:
    return [_section_heading(section) for section in _ordered_sections(resume, template)]


def _sanitize_rendered_text(text: str) -> tuple[str, list[str]]:
    sanitized = text
    replaced = []
    for character, replacement in _SANITATION_REPLACEMENTS.items():
        if character in sanitized:
            sanitized = sanitized.replace(character, replacement)
            replaced.append(character)
    if not replaced:
        return sanitized, []
    names = ", ".join(_UNSUPPORTED_CHARACTERS[character] for character in sorted(replaced))
    return sanitized, [f"ats_unsupported_character_sanitized:{names}"]


def _base_result(fmt: str, template: dict[str, Any], content: str) -> RenderDict:
    return {
        "status": "ok",
        "format": fmt,
        "template_version": _template_version(template),
        "semantic_fingerprint": _fingerprint(content),
        "warnings": [],
    }


def _unsupported_pdf_result(template: dict[str, Any], reason: str) -> RenderDict:
    return {
        "status": "unsupported",
        "reason": reason,
        "format": "pdf",
        "template_version": _template_version(template),
    }


def renderMarkdown(resume: Any, template: Any) -> RenderDict:
    """Render a canonical resume to Markdown without changing semantic content."""

    if error := _validate_resume(resume):
        return _typed_error("validation_error", error, "markdown")
    if error := _validate_template(template):
        return _typed_error("validation_error", error, "markdown")

    renderable = _renderable_resume(resume)
    content, sections = _render_markdown_text(renderable, template)
    content, sanitation_warnings = _sanitize_rendered_text(content)
    result = _base_result("markdown", template, content)
    result.update({"content": content, "sections": sections, "expected_headings": _expected_headings(renderable, template)})
    result["warnings"].extend(sanitation_warnings)
    return result


def renderDocx(resume: Any, template: Any) -> RenderDict:
    """Render a real DOCX artifact payload from canonical text."""

    if error := _validate_resume(resume):
        return _typed_error("validation_error", error, "docx")
    if error := _validate_template(template):
        return _typed_error("validation_error", error, "docx")

    renderable = _renderable_resume(resume)
    content, sections = _render_markdown_text(renderable, template)
    content, sanitation_warnings = _sanitize_rendered_text(content)
    layout = layout_from_template(template)
    docx_bytes = build_docx(content, layout)
    result = _base_result("docx", template, content)
    result.update(
        {
            "artifact": {
                "kind": "docx",
                "media_type": _DOCX_MEDIA_TYPE,
                "encoding": "utf-8",
                "declared_font_families": sorted({layout.body_font.family, layout.heading_font.family}),
                "content_base64": base64.b64encode(docx_bytes).decode("ascii"),
                "text": content,
            },
            "sections": sections,
            "expected_headings": _expected_headings(renderable, template),
        }
    )
    result["warnings"].extend(sanitation_warnings)
    return result


def renderPdf(resume: Any, template: Any) -> RenderDict:
    """Report PDF output as unsupported until a real PDF runtime exists."""

    if error := _validate_resume(resume):
        return _typed_error("validation_error", error, "pdf")
    if error := _validate_template(template):
        return _typed_error("validation_error", error, "pdf")

    if "format_targets" not in template:
        return _unsupported_pdf_result(template, "format_targets_missing")

    targets = template.get("format_targets")
    target_names = {str(target).lower() for target in targets} if isinstance(targets, list) else set()
    if "pdf" not in target_names:
        return _unsupported_pdf_result(template, "not_in_format_targets")

    return _unsupported_pdf_result(template, "pdf_not_supported_in_mvp")


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

    section_blocks = _section_text_blocks(_renderable_resume(resume), template)
    content = "\n\n".join(block for _section_id, block in section_blocks).strip() + "\n"
    non_empty_lines = [line for line in content.splitlines() if line.strip()]
    estimated_lines = 0
    for line in non_empty_lines:
        estimated_lines += max(1, math.ceil(len(line) / 90))
    estimated_pages = max(1, math.ceil(estimated_lines / 45))
    target_line_capacity = target_pages * 45
    overflow_lines = max(0, estimated_lines - target_line_capacity)
    required_reduction = overflow_lines * 90
    status = "overflow" if required_reduction else "fits"
    section_lengths = [
        {"section_id": section_id, "character_count": len(block)}
        for section_id, block in section_blocks
    ]
    offending_sections = [
        entry["section_id"]
        for entry in sorted(section_lengths, key=lambda item: (-int(item["character_count"]), str(item["section_id"])))[:3]
        if required_reduction > 0
    ]

    return {
        "status": status,
        "estimated_pages": estimated_pages,
        "target_pages": target_pages,
        "required_reduction": required_reduction,
        "requiredReduction": required_reduction,
        "offending_sections": offending_sections,
        "constraints": {
            "requiredReduction": required_reduction,
            "offending_sections": offending_sections,
            "line_capacity_per_page": 45,
            "character_wrap_width": 90,
            "content_lines": estimated_lines,
            "overflow_lines": overflow_lines,
            "section_character_counts": section_lengths,
        },
        "warnings": ["Content exceeds target page estimate."] if status == "overflow" else [],
    }


def _declared_xml_encoding(payload: bytes) -> str:
    match = _XML_DECL_RE.search(payload[:128])
    if not match:
        return "utf-8"
    try:
        return match.group(1).decode("ascii").lower()
    except UnicodeDecodeError:
        return "utf-8"


def _encoding_warnings(parts: dict[str, bytes]) -> list[str]:
    warnings: list[str] = []
    for name, payload in sorted(parts.items()):
        if not name.endswith(".xml"):
            continue
        encoding = _declared_xml_encoding(payload)
        try:
            payload.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            warnings.append(f"ats_encoding_decode:{name}:{encoding}")
    return warnings


def _docx_structural_warnings(parts: dict[str, bytes], declared_fonts: set[str]) -> list[str]:
    warnings: list[str] = []
    namespace = {"w": W_NS}
    document_payload = parts.get("word/document.xml")
    if document_payload is None:
        return warnings

    try:
        document = ElementTree.fromstring(document_payload)
    except ElementTree.ParseError:
        return warnings

    if document.findall(".//w:tbl", namespace):
        warnings.append("ats_hostile_construct:w:tbl")
    if document.findall(".//w:txbxContent", namespace):
        warnings.append("ats_hostile_construct:w:txbxContent")

    if declared_fonts and "word/styles.xml" in parts:
        try:
            styles = ElementTree.fromstring(parts["word/styles.xml"])
        except ElementTree.ParseError:
            styles = None
        if styles is not None:
            seen_fonts: set[str] = set()
            for node in styles.findall(".//w:rFonts", namespace):
                for attr_name in ("ascii", "hAnsi"):
                    value = node.get(f"{{{W_NS}}}{attr_name}")
                    if value:
                        seen_fonts.add(value)
            for font in sorted(seen_fonts - declared_fonts):
                warnings.append(f"ats_exotic_font:{font}")
    return warnings


def _extract_docx_text(content_base64: Any, declared_fonts: set[str] | None = None) -> tuple[str | None, list[str]]:
    if not isinstance(content_base64, str) or not content_base64:
        return None, ["DOCX artifact is missing content_base64."]

    try:
        docx_bytes = base64.b64decode(content_base64, validate=True)
    except (ValueError, TypeError):
        return None, ["DOCX artifact content_base64 is not valid base64."]

    try:
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as archive:
            names = set(archive.namelist())
            required = {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}
            missing = sorted(required - names)
            if missing:
                return None, [f"DOCX artifact is missing required parts: {', '.join(missing)}."]
            parts = {name: archive.read(name) for name in names if name.endswith(".xml")}
            document_xml = parts["word/document.xml"]
    except (zipfile.BadZipFile, KeyError, OSError):
        return None, ["DOCX artifact is not a readable DOCX zip payload."]

    artifact_warnings = _encoding_warnings(parts)
    artifact_warnings.extend(_docx_structural_warnings(parts, declared_fonts or set()))

    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError:
        return None, ["DOCX artifact word/document.xml is not readable XML."]

    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        text_parts = [
            node.text or ""
            for node in paragraph.findall(".//w:t", namespace)
        ]
        paragraph_text = "".join(text_parts).strip()
        if paragraph_text:
            paragraphs.append(paragraph_text)
    if not paragraphs:
        artifact_warnings.append("DOCX artifact contains no readable document text.")
        return "", artifact_warnings
    return "\n".join(paragraphs), artifact_warnings


def _text_contains_material_lines(haystack: str, needle: str) -> bool:
    lowered_haystack = haystack.lower()
    for raw_line in needle.splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        if line.startswith("- ") or line.startswith("* "):
            line = line[2:].strip()
        if line and line.lower() not in lowered_haystack:
            return False
    return True


def _extract_text(file: Any) -> tuple[str | None, str | None, dict[str, Any], list[str]]:
    if isinstance(file, str):
        return file, "markdown", {}, []
    if not isinstance(file, dict):
        return None, None, {}, []

    fmt = str(file.get("format") or "unknown")
    if isinstance(file.get("content"), str):
        return file["content"], fmt, file, []

    artifact = file.get("artifact")
    if isinstance(artifact, dict):
        artifact_format = str(artifact.get("kind") or fmt)
        artifact_text = artifact.get("text") if isinstance(artifact.get("text"), str) else None
        artifact_warnings: list[str] = []
        if artifact_format == "docx" or artifact.get("media_type") == _DOCX_MEDIA_TYPE:
            declared_fonts = artifact.get("declared_font_families") or file.get("declared_font_families")
            font_set = {str(font) for font in declared_fonts} if isinstance(declared_fonts, list) else set()
            if not font_set:
                font_set = {DEFAULT_LAYOUT.body_font.family, DEFAULT_LAYOUT.heading_font.family}
            docx_text, artifact_warnings = _extract_docx_text(artifact.get("content_base64"), font_set)
            if artifact_text and docx_text is not None and not _text_contains_material_lines(docx_text, artifact_text):
                artifact_warnings.append("DOCX artifact payload is missing text from the parse-back sidecar.")
            return artifact_text or docx_text, "docx", file, artifact_warnings
        if artifact_text is not None:
            return artifact_text, artifact_format, file, []

    if isinstance(file.get("text"), str):
        return file["text"], fmt, file, []

    return None, fmt, file, []


def _heading_names(text: str) -> set[str]:
    headings: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(_HEADING_PREFIXES):
            headings.add(stripped.lstrip("#").strip().lower())
    return headings


def _section_heading_names(text: str) -> set[str]:
    headings: set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            headings.add(stripped[3:].strip().lower())
    return headings


def _has_heading(text: str, heading: str, headings: set[str]) -> bool:
    lowered_heading = heading.lower()
    if lowered_heading in headings:
        return True
    return any(line.strip().lower() == lowered_heading for line in text.splitlines())


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


def _payload_expected_headings(payload: dict[str, Any], expected_resume: Any) -> list[str]:
    headings = payload.get("expected_headings")
    if isinstance(headings, list):
        return [str(heading).strip() for heading in headings if str(heading).strip()]
    if not isinstance(expected_resume, dict):
        return []
    template = payload.get("template") if isinstance(payload.get("template"), dict) else {}
    return _expected_headings(expected_resume, template)


def validateRenderedOutput(file: Any) -> RenderDict:
    """Validate parse-back text and renderer-specific ATS concerns."""

    text, fmt, payload, artifact_warnings = _extract_text(file)
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
    expected_headings = _payload_expected_headings(payload, expected_resume)
    for heading in expected_headings:
        if heading and not _has_heading(text, heading, headings):
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
    warnings: list[str] = list(artifact_warnings)
    if not text.strip():
        warnings.append("Rendered output is empty.")
    if missing_sections:
        warnings.append("Rendered output is missing section headings.")
    if semantic_differences:
        warnings.append("Rendered output is missing expected text.")
    if unsupported_characters:
        warnings.append("Rendered output contains unsupported characters.")
    if missing_sections:
        warnings.append("ats_template_heading_mismatch")

    rendered_section_headings = _section_heading_names(text)
    if expected_headings and rendered_section_headings:
        expected_heading_set = {heading.lower() for heading in expected_headings}
        if rendered_section_headings != expected_heading_set and "ats_template_heading_mismatch" not in warnings:
            warnings.append("ats_template_heading_mismatch")

    return {
        "status": "fail" if warnings else "pass",
        "format": fmt,
        "text_extracted": text,
        "missing_sections": missing_sections,
        "unsupported_characters": unsupported_characters,
        "semantic_differences": semantic_differences,
        "ats_findings": [warning for warning in warnings if warning.startswith("ats_")],
        "warnings": warnings,
    }


__all__ = [
    "renderMarkdown",
    "renderDocx",
    "renderPdf",
    "measureLayout",
    "validateRenderedOutput",
]
