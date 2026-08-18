"""Small stdlib-only OOXML builders for resume DOCX artifacts."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

LAYOUT_METRICS_VERSION = "layout-metrics.v1"


@dataclass(frozen=True)
class FontMetric:
    family: str
    size_pt: float


@dataclass(frozen=True)
class SpacingMetric:
    line: float
    para_after_pt: float


@dataclass(frozen=True)
class MarginsMetric:
    top: float
    bottom: float
    left: float
    right: float


@dataclass(frozen=True)
class BulletMetric:
    style: str
    indent_in: float


@dataclass(frozen=True)
class LayoutMetrics:
    version: str
    body_font: FontMetric
    heading_font: FontMetric
    spacing: SpacingMetric
    margins: MarginsMetric
    bullet: BulletMetric


DEFAULT_LAYOUT = LayoutMetrics(
    version=LAYOUT_METRICS_VERSION,
    body_font=FontMetric(family="Aptos", size_pt=11.0),
    heading_font=FontMetric(family="Aptos Display", size_pt=14.0),
    spacing=SpacingMetric(line=1.0, para_after_pt=0.0),
    margins=MarginsMetric(top=0.5, bottom=0.5, left=0.5, right=0.5),
    bullet=BulletMetric(style="bullet", indent_in=0.25),
)

CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
</Types>
"""

ROOT_RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

DOCUMENT_RELS_XML = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{REL_NS}">
  <Relationship Id="rId1" Type="{DOC_REL_NS}/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="{DOC_REL_NS}/numbering" Target="numbering.xml"/>
</Relationships>
"""

_LAYOUT_KEYS = {"version", "fonts", "spacing", "margins_in", "bullet"}
_FONT_KEYS = {"family", "size_pt"}
_FONTS_KEYS = {"body", "heading"}
_SPACING_KEYS = {"line", "para_after_pt"}
_MARGIN_KEYS = {"top", "bottom", "left", "right"}
_BULLET_KEYS = {"style", "indent_in"}
_FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def layout_validation_error(template: dict[str, Any]) -> str | None:
    """Return a typed validation message for invalid layout blocks."""

    layout = template.get("layout")
    if layout is None:
        return None
    try:
        _parse_layout(layout)
    except ValueError as exc:
        return str(exc)
    return None


def layout_from_template(template: dict[str, Any]) -> LayoutMetrics:
    layout = template.get("layout")
    if layout is None:
        return DEFAULT_LAYOUT
    return _parse_layout(layout)


def build_docx(text: str, layout: LayoutMetrics) -> bytes:
    paragraphs = "\n".join(_paragraph(line) for line in text.splitlines())
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{W_NS}">
  <w:body>
    {paragraphs}
    <w:sectPr>
      <w:pgSz w:w="12240" w:h="15840"/>
      <w:pgMar w:top="{_inches_to_twips(layout.margins.top)}" w:right="{_inches_to_twips(layout.margins.right)}" w:bottom="{_inches_to_twips(layout.margins.bottom)}" w:left="{_inches_to_twips(layout.margins.left)}" w:header="360" w:footer="360" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
"""
    parts = (
        ("[Content_Types].xml", CONTENT_TYPES_XML),
        ("_rels/.rels", ROOT_RELS_XML),
        ("word/_rels/document.xml.rels", DOCUMENT_RELS_XML),
        ("word/document.xml", document_xml),
        ("word/styles.xml", _styles_xml(layout)),
        ("word/numbering.xml", _numbering_xml(layout)),
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in parts:
            info = zipfile.ZipInfo(filename=name, date_time=_FIXED_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, content.encode("utf-8"))
    return buffer.getvalue()


def _parse_layout(layout: Any) -> LayoutMetrics:
    if not isinstance(layout, dict):
        raise ValueError("Template layout must be an object.")
    _reject_unknown("layout", layout, _LAYOUT_KEYS)
    version = layout.get("version", LAYOUT_METRICS_VERSION)
    if version != LAYOUT_METRICS_VERSION:
        raise ValueError(f"Template layout.version must be {LAYOUT_METRICS_VERSION}.")

    fonts = layout.get("fonts", {})
    if not isinstance(fonts, dict):
        raise ValueError("Template layout.fonts must be an object.")
    _reject_unknown("layout.fonts", fonts, _FONTS_KEYS)
    body_font = _font_metric("layout.fonts.body", fonts.get("body"), DEFAULT_LAYOUT.body_font)
    heading_font = _font_metric("layout.fonts.heading", fonts.get("heading"), DEFAULT_LAYOUT.heading_font)

    spacing = layout.get("spacing", {})
    if not isinstance(spacing, dict):
        raise ValueError("Template layout.spacing must be an object.")
    _reject_unknown("layout.spacing", spacing, _SPACING_KEYS)
    spacing_metric = SpacingMetric(
        line=_positive_float("layout.spacing.line", spacing.get("line", DEFAULT_LAYOUT.spacing.line)),
        para_after_pt=_nonnegative_float(
            "layout.spacing.para_after_pt",
            spacing.get("para_after_pt", DEFAULT_LAYOUT.spacing.para_after_pt),
        ),
    )

    margins = layout.get("margins_in", {})
    if not isinstance(margins, dict):
        raise ValueError("Template layout.margins_in must be an object.")
    _reject_unknown("layout.margins_in", margins, _MARGIN_KEYS)
    margins_metric = MarginsMetric(
        top=_nonnegative_float("layout.margins_in.top", margins.get("top", DEFAULT_LAYOUT.margins.top)),
        bottom=_nonnegative_float("layout.margins_in.bottom", margins.get("bottom", DEFAULT_LAYOUT.margins.bottom)),
        left=_nonnegative_float("layout.margins_in.left", margins.get("left", DEFAULT_LAYOUT.margins.left)),
        right=_nonnegative_float("layout.margins_in.right", margins.get("right", DEFAULT_LAYOUT.margins.right)),
    )

    bullet = layout.get("bullet", {})
    if not isinstance(bullet, dict):
        raise ValueError("Template layout.bullet must be an object.")
    _reject_unknown("layout.bullet", bullet, _BULLET_KEYS)
    bullet_style = bullet.get("style", DEFAULT_LAYOUT.bullet.style)
    if not isinstance(bullet_style, str) or not bullet_style.strip():
        raise ValueError("Template layout.bullet.style must be a non-empty string.")
    bullet_metric = BulletMetric(
        style=bullet_style.strip(),
        indent_in=_nonnegative_float("layout.bullet.indent_in", bullet.get("indent_in", DEFAULT_LAYOUT.bullet.indent_in)),
    )

    return LayoutMetrics(
        version=version,
        body_font=body_font,
        heading_font=heading_font,
        spacing=spacing_metric,
        margins=margins_metric,
        bullet=bullet_metric,
    )


def _reject_unknown(path: str, value: dict[str, Any], allowed: set[str]) -> None:
    unknown = sorted(str(key) for key in value if key not in allowed)
    if unknown:
        raise ValueError(f"Template {path} contains unknown key(s): {', '.join(unknown)}.")


def _font_metric(path: str, value: Any, default: FontMetric) -> FontMetric:
    if value is None:
        return default
    if not isinstance(value, dict):
        raise ValueError(f"Template {path} must be an object.")
    _reject_unknown(path, value, _FONT_KEYS)
    family = value.get("family", default.family)
    if not isinstance(family, str) or not family.strip():
        raise ValueError(f"Template {path}.family must be a non-empty string.")
    return FontMetric(
        family=family.strip(),
        size_pt=_positive_float(f"{path}.size_pt", value.get("size_pt", default.size_pt)),
    )


def _positive_float(path: str, value: Any) -> float:
    number = _number(path, value)
    if number <= 0:
        raise ValueError(f"Template {path} must be greater than 0.")
    return number


def _nonnegative_float(path: str, value: Any) -> float:
    number = _number(path, value)
    if number < 0:
        raise ValueError(f"Template {path} must be greater than or equal to 0.")
    return number


def _number(path: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Template {path} must be numeric.")
    return float(value)


def _paragraph(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return "<w:p/>"

    style_id = "body"
    text = stripped
    num_pr = ""
    if stripped.startswith("### "):
        style_id = "Heading2"
        text = stripped[4:].strip()
    elif stripped.startswith("## "):
        style_id = "Heading2"
        text = stripped[3:].strip()
    elif stripped.startswith("# "):
        style_id = "Title"
        text = stripped[2:].strip()
    elif stripped.startswith("- ") or stripped.startswith("* "):
        style_id = "ListParagraph"
        text = stripped[2:].strip()
        num_pr = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'

    safe_text = escape(text, {'"': "&quot;"})
    p_pr = f'<w:pPr><w:pStyle w:val="{style_id}"/>{num_pr}</w:pPr>'
    return f'<w:p>{p_pr}<w:r><w:t xml:space="preserve">{safe_text}</w:t></w:r></w:p>'


def _styles_xml(layout: LayoutMetrics) -> str:
    body_rpr = _run_properties(layout.body_font)
    heading_rpr = _run_properties(layout.heading_font, bold=True)
    body_ppr = _paragraph_properties(layout)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W_NS}">
  <w:style w:type="paragraph" w:default="1" w:styleId="body">
    <w:name w:val="Body"/>
    <w:qFormat/>
    {body_ppr}
    {body_rpr}
  </w:style>
  <w:style w:type="paragraph" w:styleId="Title">
    <w:name w:val="Title"/>
    <w:basedOn w:val="body"/>
    <w:qFormat/>
    {body_ppr}
    {_run_properties(layout.heading_font, bold=True, size_multiplier=1.35)}
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="Heading 1"/>
    <w:basedOn w:val="body"/>
    <w:qFormat/>
    {body_ppr}
    {heading_rpr}
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="Heading 2"/>
    <w:basedOn w:val="body"/>
    <w:qFormat/>
    {body_ppr}
    {heading_rpr}
  </w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph">
    <w:name w:val="List Paragraph"/>
    <w:basedOn w:val="body"/>
    <w:qFormat/>
    <w:pPr>
      <w:spacing w:after="{_points_to_twips(layout.spacing.para_after_pt)}" w:line="{_line_to_twips(layout.spacing.line)}" w:lineRule="auto"/>
      <w:ind w:left="{_inches_to_twips(layout.bullet.indent_in)}" w:hanging="360"/>
    </w:pPr>
    {body_rpr}
  </w:style>
</w:styles>
"""


def _numbering_xml(layout: LayoutMetrics) -> str:
    bullet_text = _bullet_text(layout.bullet.style)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="{W_NS}">
  <w:abstractNum w:abstractNumId="0">
    <w:multiLevelType w:val="singleLevel"/>
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="{escape(bullet_text, {'"': '&quot;'})}"/>
      <w:pPr><w:ind w:left="{_inches_to_twips(layout.bullet.indent_in)}" w:hanging="360"/></w:pPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
</w:numbering>
"""


def _run_properties(font: FontMetric, *, bold: bool = False, size_multiplier: float = 1.0) -> str:
    family = escape(font.family, {'"': "&quot;"})
    size = _points_to_half_points(font.size_pt * size_multiplier)
    bold_xml = "<w:b/>" if bold else ""
    return f'<w:rPr>{bold_xml}<w:rFonts w:ascii="{family}" w:hAnsi="{family}"/><w:sz w:val="{size}"/></w:rPr>'


def _paragraph_properties(layout: LayoutMetrics) -> str:
    return (
        '<w:pPr>'
        f'<w:spacing w:after="{_points_to_twips(layout.spacing.para_after_pt)}" '
        f'w:line="{_line_to_twips(layout.spacing.line)}" w:lineRule="auto"/>'
        '</w:pPr>'
    )


def _points_to_half_points(value: float) -> int:
    return int(round(value * 2))


def _points_to_twips(value: float) -> int:
    return int(round(value * 20))


def _line_to_twips(value: float) -> int:
    return int(round(value * 240))


def _inches_to_twips(value: float) -> int:
    return int(round(value * 1440))


def _bullet_text(style: str) -> str:
    normalized = style.strip().lower()
    if normalized in {"bullet", "disc", "dot"}:
        return "\u2022"
    if normalized in {"hyphen", "dash"}:
        return "-"
    return style.strip()[0]
