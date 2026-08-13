"""Public runtime package for resume-render.

The renderer is deliberately semantic-neutral: it formats the resume data it is
given, reports layout pressure, and validates parse-back text without looking up
or changing career facts.
"""

from __future__ import annotations

import base64
import hashlib
import io
import math
import zipfile
from typing import Any
from xml.etree import ElementTree
from xml.sax.saxutils import escape


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
_DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_DOCX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
_DOCX_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""


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


def _docx_paragraph(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return "<w:p/>"

    style = ""
    text = stripped
    if stripped.startswith("## "):
        style = '<w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
        text = stripped[3:].strip()
    elif stripped.startswith("# "):
        style = '<w:pPr><w:pStyle w:val="Title"/></w:pPr>'
        text = stripped[2:].strip()
    elif stripped.startswith("- ") or stripped.startswith("* "):
        text = stripped[2:].strip()

    safe_text = escape(text, {'"': "&quot;"})
    return f"<w:p>{style}<w:r><w:t xml:space=\"preserve\">{safe_text}</w:t></w:r></w:p>"


def _build_docx_bytes(text: str) -> bytes:
    paragraphs = "\n".join(_docx_paragraph(line) for line in text.splitlines())
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {paragraphs}
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="360" w:footer="360" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _DOCX_CONTENT_TYPES)
        archive.writestr("_rels/.rels", _DOCX_ROOT_RELS)
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


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
    """Render a real DOCX artifact payload from canonical text."""

    if error := _validate_resume(resume):
        return _typed_error("validation_error", error, "docx")
    if error := _validate_template(template):
        return _typed_error("validation_error", error, "docx")

    content, sections = _render_markdown_text(resume, template)
    docx_bytes = _build_docx_bytes(content)
    result = _base_result("docx", template, content)
    result.update(
        {
            "artifact": {
                "kind": "docx",
                "media_type": _DOCX_MEDIA_TYPE,
                "content_base64": base64.b64encode(docx_bytes).decode("ascii"),
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


def _extract_docx_text(content_base64: Any) -> tuple[str | None, list[str]]:
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
            document_xml = archive.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError, OSError):
        return None, ["DOCX artifact is not a readable DOCX zip payload."]

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
        return "", ["DOCX artifact contains no readable document text."]
    return "\n".join(paragraphs), []


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
            docx_text, artifact_warnings = _extract_docx_text(artifact.get("content_base64"))
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
    if isinstance(expected_resume, dict):
        for section in expected_resume.get("sections", []):
            if not isinstance(section, dict):
                continue
            heading = str(section.get("heading") or section.get("id") or "").strip()
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
