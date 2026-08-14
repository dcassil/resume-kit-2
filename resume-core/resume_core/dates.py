"""Deterministic resume date parsing helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


PRESENT_DATE_SENTINELS = {"present", "current"}
MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


@dataclass(frozen=True)
class DateParseResult:
    key: tuple[int, int] | None
    canonical: str | None
    ambiguous_normalization: bool = False
    invalid_month: bool = False


def is_present_date_sentinel(value: Any) -> bool:
    return str(value).strip().lower() in PRESENT_DATE_SENTINELS


def record_date_result(
    entry: dict[str, Any],
    field_name: str,
    value: Any,
    result: DateParseResult,
    field_path: str,
    label: str,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    issue_factory: Any,
    invalid_date_code: str,
) -> None:
    if value is None or str(value).strip() == "":
        return
    if field_name == "end_date" and is_present_date_sentinel(value):
        return
    if result.invalid_month:
        errors.append(
            issue_factory(
                invalid_date_code,
                f"{label.title()} date has an impossible month.",
                field_path,
                {"value": str(value).strip()},
            )
        )
        return
    if result.key is None:
        warnings.append(issue_factory(f"ambiguous_{label}_date", f"{label.title()} date is ambiguous.", field_path))
        return
    if result.canonical is not None:
        entry[field_name] = result.canonical
    if result.ambiguous_normalization:
        warnings.append(
            issue_factory(
                f"ambiguous_{label}_date",
                f"{label.title()} date format was normalized.",
                field_path,
                {"canonical": result.canonical},
            )
        )


def date_key(value: Any) -> DateParseResult:
    if value is None:
        return DateParseResult(None, None)
    raw = str(value).strip()
    if is_present_date_sentinel(raw):
        return DateParseResult(None, None)

    year_month = re.fullmatch(r"(\d{4})(?:-(\d{1,2}))?", raw)
    if year_month:
        year = int(year_month.group(1))
        month_text = year_month.group(2)
        month = int(month_text or "1")
        if month < 1 or month > 12:
            return DateParseResult(None, None, invalid_month=True)
        if year < 1900:
            return DateParseResult(None, None)
        canonical = f"{year:04d}" if month_text is None else f"{year:04d}-{month:02d}"
        return DateParseResult((year, month), canonical)

    month_year = re.fullmatch(r"([A-Za-z]{3})\s+(\d{4})", raw)
    if month_year:
        month = MONTHS.get(month_year.group(1).lower())
        year = int(month_year.group(2))
        if month is None or year < 1900:
            return DateParseResult(None, None)
        return DateParseResult((year, month), f"{year:04d}-{month:02d}", ambiguous_normalization=True)

    slash_month_year = re.fullmatch(r"(\d{1,2})/(\d{4})", raw)
    if slash_month_year:
        month = int(slash_month_year.group(1))
        year = int(slash_month_year.group(2))
        if month < 1 or month > 12:
            return DateParseResult(None, None, invalid_month=True)
        if year < 1900:
            return DateParseResult(None, None)
        return DateParseResult((year, month), f"{year:04d}-{month:02d}", ambiguous_normalization=True)

    return DateParseResult(None, None)
