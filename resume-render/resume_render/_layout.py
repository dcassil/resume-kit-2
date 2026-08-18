"""Deterministic layout-pressure estimation for ``measureLayout``.

This module intentionally uses a small, explicit glyph-width table instead of
hidden wrap constants. The values are average Latin glyph widths expressed as
thousandths of the font size (em). ``glyph-widths.v1`` was seeded from common
ASCII advance-width summaries for the renderer-supported font families and then
rounded to whole thousandths so the stdlib-only estimator stays deterministic
and auditable. Unknown families use the documented fallback width.

Rounding points:
- page geometry, margins, font sizes, spacing, and glyph widths are represented
  as ``Fraction`` values before arithmetic;
- line capacity per page and character capacity per line are floored to the
  number of complete lines/characters that fit;
- wrapped paragraph height is rounded up to body-line equivalents.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any

from ._ooxml import LayoutMetrics, layout_from_template


GLYPH_WIDTH_TABLE_VERSION = "glyph-widths.v1"
AVERAGE_GLYPH_WIDTHS_PER_EM: dict[str, int] = {
    "Aptos": 515,
    "Aptos Display": 525,
    "Arial": 520,
    "Calibri": 510,
    "Helvetica": 520,
    "Times New Roman": 500,
}
FALLBACK_GLYPH_WIDTH_PER_EM = 520

_POINTS_PER_INCH = Fraction(72, 1)
_DEFAULT_PAGE_WIDTH_IN = Fraction(17, 2)
_DEFAULT_PAGE_HEIGHT_IN = Fraction(11, 1)
_TITLE_SIZE_MULTIPLIER = Fraction(27, 20)


@dataclass(frozen=True)
class SectionEstimate:
    id: str
    estimated_lines: int
    overflow_chars: int
    character_count: int


@dataclass(frozen=True)
class LayoutEstimate:
    status: str
    estimated_pages: int
    estimated_lines: int
    target_pages: int
    required_reduction: int
    overflow_lines: int
    lines_per_page: int
    body_chars_per_line: int
    metrics_version: str
    per_section: tuple[SectionEstimate, ...]

    @property
    def offending_sections(self) -> list[str]:
        return [section.id for section in self.per_section if section.overflow_chars > 0]


@dataclass(frozen=True)
class _CapacityModel:
    layout: LayoutMetrics
    lines_per_page: int
    usable_width_pt: Fraction
    body_line_height_pt: Fraction
    body_chars_per_line: int


@dataclass(frozen=True)
class _MeasuredLine:
    section_id: str
    role: str
    text: str
    chars_per_line: int
    font_size_pt: Fraction
    line_spacing: Fraction
    para_after_pt: Fraction

    @property
    def character_count(self) -> int:
        return len(self.text)


def estimate_layout(section_blocks: list[tuple[str, str]], template: dict[str, Any], target_pages: int) -> LayoutEstimate:
    """Estimate pages and overflow from RenderableResume-shaped section blocks."""

    layout = layout_from_template(template)
    model = _capacity_model(layout)
    lines = tuple(_measured_lines(section_blocks, model))
    section_order = tuple(section_id for section_id, _block in section_blocks)
    section_lines = {section_id: 0 for section_id in section_order}
    section_chars = {section_id: 0 for section_id in section_order}

    total_lines = 0
    for line in lines:
        line_units = _line_units(line, model, line.character_count)
        total_lines += line_units
        section_lines[line.section_id] = section_lines.get(line.section_id, 0) + line_units
        section_chars[line.section_id] = section_chars.get(line.section_id, 0) + line.character_count

    target_capacity = target_pages * model.lines_per_page
    overflow_lines = max(0, total_lines - target_capacity)
    required_reduction = _required_suffix_reduction(lines, model, target_capacity) if overflow_lines else 0
    overflow_by_section = _suffix_reduction_by_section(lines, required_reduction)
    per_section = tuple(
        SectionEstimate(
            id=section_id,
            estimated_lines=section_lines.get(section_id, 0),
            overflow_chars=overflow_by_section.get(section_id, 0),
            character_count=section_chars.get(section_id, 0),
        )
        for section_id in section_order
    )

    estimated_pages = max(1, _ceil_fraction(Fraction(total_lines, model.lines_per_page)))
    status = "overflow" if required_reduction else "fits"
    return LayoutEstimate(
        status=status,
        estimated_pages=estimated_pages,
        estimated_lines=total_lines,
        target_pages=target_pages,
        required_reduction=required_reduction,
        overflow_lines=overflow_lines,
        lines_per_page=model.lines_per_page,
        body_chars_per_line=model.body_chars_per_line,
        metrics_version=f"{layout.version}+{GLYPH_WIDTH_TABLE_VERSION}",
        per_section=per_section,
    )


def _capacity_model(layout: LayoutMetrics) -> _CapacityModel:
    usable_height_in = _DEFAULT_PAGE_HEIGHT_IN - _fraction(layout.margins.top) - _fraction(layout.margins.bottom)
    usable_width_in = _DEFAULT_PAGE_WIDTH_IN - _fraction(layout.margins.left) - _fraction(layout.margins.right)
    usable_height_pt = max(Fraction(1, 1), usable_height_in * _POINTS_PER_INCH)
    usable_width_pt = max(Fraction(1, 1), usable_width_in * _POINTS_PER_INCH)
    body_line_height_pt = _font_size(layout, "body") * _fraction(layout.spacing.line)
    lines_per_page = max(1, _floor_fraction(usable_height_pt / body_line_height_pt))
    body_chars_per_line = _chars_per_line(usable_width_pt, layout.body_font.family, _font_size(layout, "body"))
    return _CapacityModel(
        layout=layout,
        lines_per_page=lines_per_page,
        usable_width_pt=usable_width_pt,
        body_line_height_pt=body_line_height_pt,
        body_chars_per_line=body_chars_per_line,
    )


def _measured_lines(section_blocks: list[tuple[str, str]], model: _CapacityModel) -> list[_MeasuredLine]:
    lines: list[_MeasuredLine] = []
    for section_id, block in section_blocks:
        for raw_line in block.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            role, text = _line_role_and_text(stripped)
            font_size = _font_size(model.layout, role)
            width = model.usable_width_pt
            if role == "bullet":
                width -= _fraction(model.layout.bullet.indent_in) * _POINTS_PER_INCH
                width = max(Fraction(1, 1), width)
            lines.append(
                _MeasuredLine(
                    section_id=section_id,
                    role=role,
                    text=text,
                    chars_per_line=_chars_per_line(width, _font_family(model.layout, role), font_size),
                    font_size_pt=font_size,
                    line_spacing=_fraction(model.layout.spacing.line),
                    para_after_pt=_fraction(model.layout.spacing.para_after_pt),
                )
            )
    return lines


def _line_role_and_text(line: str) -> tuple[str, str]:
    if line.startswith("# "):
        return "title", line[2:].strip()
    if line.startswith("### "):
        return "heading", line[4:].strip()
    if line.startswith("## "):
        return "heading", line[3:].strip()
    if line.startswith("- ") or line.startswith("* "):
        return "bullet", line[2:].strip()
    return "body", line


def _line_units(line: _MeasuredLine, model: _CapacityModel, character_count: int) -> int:
    if character_count <= 0:
        return 0
    wrapped_lines = max(1, _ceil_fraction(Fraction(character_count, line.chars_per_line)))
    physical_height = (line.font_size_pt * line.line_spacing * wrapped_lines) + line.para_after_pt
    return max(1, _ceil_fraction(physical_height / model.body_line_height_pt))


def _required_suffix_reduction(lines: tuple[_MeasuredLine, ...], model: _CapacityModel, target_capacity: int) -> int:
    total_chars = sum(line.character_count for line in lines)
    low = 0
    high = total_chars
    while low < high:
        midpoint = (low + high) // 2
        if _line_units_after_suffix_reduction(lines, model, midpoint) <= target_capacity:
            high = midpoint
        else:
            low = midpoint + 1
    return low


def _line_units_after_suffix_reduction(lines: tuple[_MeasuredLine, ...], model: _CapacityModel, reduction: int) -> int:
    remaining = reduction
    total = 0
    for line in reversed(lines):
        removed = min(remaining, line.character_count)
        remaining -= removed
        total += _line_units(line, model, line.character_count - removed)
    return total


def _suffix_reduction_by_section(lines: tuple[_MeasuredLine, ...], reduction: int) -> dict[str, int]:
    remaining = reduction
    by_section: dict[str, int] = {}
    for line in reversed(lines):
        if remaining <= 0:
            break
        removed = min(remaining, line.character_count)
        remaining -= removed
        if removed:
            by_section[line.section_id] = by_section.get(line.section_id, 0) + removed
    return by_section


def _font_size(layout: LayoutMetrics, role: str) -> Fraction:
    if role == "title":
        return _fraction(layout.heading_font.size_pt) * _TITLE_SIZE_MULTIPLIER
    if role == "heading":
        return _fraction(layout.heading_font.size_pt)
    return _fraction(layout.body_font.size_pt)


def _font_family(layout: LayoutMetrics, role: str) -> str:
    if role in {"title", "heading"}:
        return layout.heading_font.family
    return layout.body_font.family


def _chars_per_line(width_pt: Fraction, family: str, font_size_pt: Fraction) -> int:
    glyph_width = font_size_pt * Fraction(_glyph_width_per_em(family), 1000)
    return max(1, _floor_fraction(width_pt / glyph_width))


def _glyph_width_per_em(family: str) -> int:
    return AVERAGE_GLYPH_WIDTHS_PER_EM.get(family, FALLBACK_GLYPH_WIDTH_PER_EM)


def _fraction(value: float) -> Fraction:
    return Fraction(str(value))


def _ceil_fraction(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def _floor_fraction(value: Fraction) -> int:
    return value.numerator // value.denominator
