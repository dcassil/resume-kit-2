"""Deterministic honesty heuristics for resume-core."""

from __future__ import annotations

import re
from typing import Any

from .schemas import JsonObject, ResolutionState, VerificationState


_VERIFIED_FACT_STATES = {
    VerificationState.SOURCE_STATED.value,
    VerificationState.USER_VERIFIED.value,
    VerificationState.IMPORTED.value,
}
_GUARDED_TERMS = {
    "aws": ("aws", "amazon web services"),
    "graphql": ("graphql", "graph ql"),
    "staff_title": ("staff software engineer", "staff engineer"),
    "unsupported_scale": ("20 million", "20m users"),
    "unsupported_management": ("30 engineers", "managed 30"),
}
_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}
_NUMBER_SCALES = {
    "hundred": 100,
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
}
_SHORT_NUMBER_SCALES = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
_NUMBER_WORD_PATTERN = "|".join(sorted([*_NUMBER_WORDS, *_NUMBER_SCALES], key=len, reverse=True))
_YEARS_RE = re.compile(rf"\b(?P<number>\d+|{_NUMBER_WORD_PATTERN})\+?\s+years?\b", re.IGNORECASE)
_QUANTITY_SUBJECT_STOPWORDS = {
    "across",
    "and",
    "at",
    "by",
    "daily",
    "for",
    "globally",
    "in",
    "monthly",
    "of",
    "per",
    "through",
    "to",
    "weekly",
    "with",
    "yearly",
}
_SINGULAR_SUBJECTS = {
    "developers": "developer",
    "engineers": "engineer",
    "people": "person",
    "users": "user",
}
_QUANTITY_COUNT_SUBJECTS = {"developer", "engineer", "percent", "percentage", "person", "user"}
_GROUNDED_SKILL_TERMS = {
    "aws": ("aws", "amazon web services"),
    "graphql": ("graphql", "graph ql"),
    "kubernetes": ("kubernetes", "k8s"),
}
_TITLE_RANKS = {
    "engineer": 0,
    "senior": 1,
    "staff": 2,
    "principal": 3,
    "distinguished": 4,
}
_TITLE_RANK_LABELS = {rank: label for label, rank in _TITLE_RANKS.items()}
_TITLE_RE = re.compile(
    r"\b(?:(senior|sr|staff|principal|distinguished)\s+)?(?:software\s+)?(?:engineer|developer)\b",
    re.IGNORECASE,
)
_GENERIC_TERMS = {
    "a",
    "an",
    "and",
    "applications",
    "background",
    "building",
    "design",
    "delivering",
    "development",
    "experience",
    "for",
    "in",
    "of",
    "or",
    "preferred",
    "production",
    "required",
    "strong",
    "systems",
    "the",
    "through",
    "with",
}


def _guarded_claims(text: str, skill_terms: list[str] | None = None) -> set[str]:
    normalized = _normal_text(text)
    claims: set[str] = set()
    claims.update(_quantity_claims(normalized))
    claims.update(_title_claims(normalized))
    claims.update(_year_claims(normalized))
    claims.update(_skill_claims(normalized, skill_terms))
    return claims


def _claim_support(guarded: set[str], fact_index: dict[str, JsonObject], linked_fact_ids: list[str], allow_inferred: bool) -> dict[str, list[str]]:
    supported: dict[str, list[str]] = {}
    for claim in sorted(guarded):
        for fact_id in linked_fact_ids:
            fact = _item(fact_index, str(fact_id))
            if (
                isinstance(fact, dict)
                and _fact_allowed(fact, allow_inferred)
                and not _fact_negates_claim(claim, fact)
                and _fact_supports_claim(claim, fact)
            ):
                supported.setdefault(claim, []).append(str(fact_id))
    return supported


def _title_inflation(path: str, before: Any, after: Any, support_by_claim: dict[str, list[str]]) -> bool:
    if not path.endswith("/title"):
        return False
    after_rank = _title_rank(after)
    before_rank = _title_rank(before)
    floor = before_rank if before_rank is not None else _TITLE_RANKS["engineer"]
    if after_rank is None or after_rank <= floor:
        return False
    return not support_by_claim.get(f"title:{_TITLE_RANK_LABELS[after_rank]}")


def _minimum_required_years(value: Any) -> int | None:
    match = _YEARS_RE.search(_normal_text(value))
    if not match:
        return None
    return _number_value(match.group("number"))


def _years_met(text: str, required_years: int, subject_terms: list[str] | None = None) -> tuple[bool, int | None]:
    normalized = _normal_text(text)
    subject_terms = _specific_terms(subject_terms or [])
    values: list[int] = []
    for match in _YEARS_RE.finditer(normalized):
        value = _number_value(match.group("number"))
        if value is None:
            continue
        if subject_terms and not _year_match_scoped_to_subject(normalized, match.start(), match.end(), subject_terms):
            continue
        values.append(value)
    if not values:
        return False, None
    best = max(values)
    return best >= required_years, best


def _fact_years_met(fact: JsonObject, required_years: int, subject_terms: list[str]) -> tuple[bool, int | None]:
    matches: list[int] = []
    for segment in _fact_text_segments(fact):
        met, matched_years = _years_met(segment, required_years, subject_terms)
        if met and matched_years is not None:
            matches.append(matched_years)
    if not matches:
        return False, None
    return True, max(matches)


def _title_rank(value: Any) -> int | None:
    text = _normal_text(value)
    ranks: list[int] = []
    for match in _TITLE_RE.finditer(text):
        seniority = match.group(1)
        if seniority:
            seniority = "senior" if seniority == "sr" else seniority
            ranks.append(_TITLE_RANKS[seniority])
        else:
            ranks.append(_TITLE_RANKS["engineer"])
    for label in ("distinguished", "principal", "staff", "senior"):
        if _term_in_text(label, text):
            ranks.append(_TITLE_RANKS[label])
    return max(ranks) if ranks else None


def _years(text: str) -> list[str]:
    return [match.group(0).lower() for match in _YEARS_RE.finditer(str(text))]


def _extract_years(text: str) -> str | None:
    matches = _years(text)
    return matches[0] if matches else None


def _quantity_claims(text: str) -> set[str]:
    tokens = text.split()
    claims: set[str] = set()
    for value, _start, end in _number_spans(text):
        if end < len(tokens) and tokens[end] in {"year", "years"}:
            continue
        subject = _quantity_subject(tokens, end)
        if subject:
            claims.add(f"quantity:{value}:{subject}")
    return claims


def _title_claims(text: str) -> set[str]:
    rank = _title_rank(text)
    if rank is None or rank < _TITLE_RANKS["staff"]:
        return set()
    return {f"title:{_TITLE_RANK_LABELS[rank]}"}


def _year_claims(text: str) -> set[str]:
    claims: set[str] = set()
    subjects = _claim_subject_terms(text)
    for match in _YEARS_RE.finditer(text):
        years = _number_value(match.group("number"))
        if years is None:
            continue
        scoped_subjects = [subject for subject in subjects if _year_match_scoped_to_subject(text, match.start(), match.end(), [subject])]
        for subject in scoped_subjects:
            claims.add(f"years:{years}:{subject}")
    return claims


def _skill_claims(text: str, skill_terms: list[str] | None = None) -> set[str]:
    claims: set[str] = set()
    for canonical, variants in _GROUNDED_SKILL_TERMS.items():
        if any(_term_in_text(variant, text) for variant in variants):
            claims.add(f"skill:{canonical}")
    for term in _specific_terms(skill_terms or []):
        if _term_in_text(term, text):
            claims.add(f"skill:{term}")
    return claims


def _fact_supports_claim(claim: str, fact: JsonObject) -> bool:
    kind, first, second = _split_claim(claim)
    fact_text = _fact_text(fact)
    if kind == "skill" and first:
        return any(_term_in_text(term, fact_text) for term in _GROUNDED_SKILL_TERMS.get(first, (first,)))
    if kind == "title" and first:
        claim_rank = _TITLE_RANKS.get(first)
        fact_rank = _fact_title_rank(fact)
        return claim_rank is not None and fact_rank is not None and fact_rank >= claim_rank
    if kind == "years" and first and second:
        required_years = _number_value(first)
        return required_years is not None and _fact_years_met(fact, required_years, [second])[0]
    if kind == "quantity" and first and second:
        required_quantity = _number_value(first)
        return required_quantity is not None and _fact_has_quantity(fact, required_quantity, second)
    return False


def _fact_negates_claim(claim: str, fact: JsonObject) -> bool:
    claim_terms = _claim_terms(claim)
    if not claim_terms:
        return False
    if str(_item(fact, "resolution_state", "")) == ResolutionState.EXPLICITLY_MISSING.value:
        return _fact_overlaps_terms(fact, claim_terms)
    if bool(_item(fact, "negated", False) or _item(fact, "is_negated", False) or _item(fact, "explicit_negative", False)):
        return _fact_overlaps_terms(fact, claim_terms)
    if str(_item(fact, "polarity", "")).lower() in {"negative", "negated", "absent"}:
        return _fact_overlaps_terms(fact, claim_terms)
    negated_terms = _structured_terms(fact, ("negated_terms", "absent_terms", "denied_terms", "contradicted_terms"))
    metadata = _item(fact, "metadata", {})
    if isinstance(metadata, dict):
        negated_terms.extend(_structured_terms(metadata, ("negated_terms", "absent_terms", "denied_terms", "contradicted_terms")))
    return bool(negated_terms and _terms_overlap(claim_terms, negated_terms))


def _fact_has_quantity(fact: JsonObject, required_quantity: int, subject: str) -> bool:
    structured_quantity = _item(fact, "quantity", _item(fact, "count"))
    structured_subject = _normal_text(_item(fact, "quantity_subject", _item(fact, "subject", "")))
    if isinstance(structured_quantity, int) and structured_quantity == required_quantity and (not structured_subject or _term_in_text(subject, structured_subject)):
        return True
    fact_text = _fact_text(fact)
    for value, _start, end in _number_spans(fact_text):
        fact_subject = _quantity_subject(fact_text.split(), end)
        if value == required_quantity and fact_subject and _terms_overlap([subject], [fact_subject]):
            return True
    return False


def _fact_title_rank(fact: JsonObject) -> int | None:
    ranks = [
        rank
        for rank in (_title_rank(_item(fact, key)) for key in ("title", "role", "position") if _item(fact, key))
        if rank is not None
    ]
    if ranks:
        return max(ranks)
    raw_text = _raw_fact_text(fact)
    title_match = re.search(r"\b(?:formal\s+employment\s+)?title\s+(?:was|is)\s+([^,.]+)", raw_text, re.IGNORECASE)
    if title_match:
        rank = _title_rank(title_match.group(1))
        if rank is not None:
            return rank
    return _title_rank(_fact_text(fact))


def _year_match_scoped_to_subject(text: str, start: int, end: int, subject_terms: list[str]) -> bool:
    tokens = text.split()
    year_start = len(text[:start].split())
    year_end = len(text[:end].split())
    for subject in _specific_terms(subject_terms):
        subject_tokens = subject.split()
        if not subject_tokens:
            continue
        for position in _token_positions(tokens, subject_tokens):
            if position <= year_start and year_start - position <= 4:
                return True
            if year_end < len(tokens) and tokens[year_end] in {"of", "in", "with"}:
                first_subject_position = year_end + 1
                if first_subject_position < len(tokens) and first_subject_position <= position <= first_subject_position + 4:
                    if subject in _GROUNDED_SKILL_TERMS and position != first_subject_position:
                        continue
                    return True
    return False


def _number_spans(text: str) -> list[tuple[int, int, int]]:
    tokens = text.split()
    spans: list[tuple[int, int, int]] = []
    for index, token in enumerate(tokens):
        digit = re.match(r"^(\d+)([kmb])?$", token)
        if digit:
            value = int(digit.group(1))
            suffix = digit.group(2)
            if suffix:
                spans.append((value * _SHORT_NUMBER_SCALES[suffix], index, index + 1))
                continue
            if index + 1 < len(tokens) and tokens[index + 1] in _NUMBER_SCALES:
                spans.append((value * _NUMBER_SCALES[tokens[index + 1]], index, index + 2))
            else:
                spans.append((value, index, index + 1))
            continue
        best: tuple[int, int, int] | None = None
        if token in _NUMBER_WORDS or token in _NUMBER_SCALES:
            for end in range(index + 1, min(len(tokens), index + 6) + 1):
                phrase = tokens[index:end]
                if any(part not in _NUMBER_WORDS and part not in _NUMBER_SCALES for part in phrase):
                    break
                value = _number_words_value(phrase)
                if value is not None:
                    best = (value, index, end)
            if best:
                spans.append(best)
    return _dedupe_number_spans(spans)


def _number_value(value: Any) -> int | None:
    text = _normal_text(value)
    if not text:
        return None
    if text.isdigit():
        return int(text)
    return _number_words_value(text.split())


def _number_words_value(tokens: list[str]) -> int | None:
    total = 0
    current = 0
    seen = False
    for token in tokens:
        if token in _NUMBER_WORDS:
            current += _NUMBER_WORDS[token]
            seen = True
        elif token == "hundred":
            current = max(1, current) * 100
            seen = True
        elif token in {"thousand", "million", "billion"}:
            total += max(1, current) * _NUMBER_SCALES[token]
            current = 0
            seen = True
        else:
            return None
    if not seen:
        return None
    return total + current


def _dedupe_number_spans(spans: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    deduped: list[tuple[int, int, int]] = []
    for span in sorted(spans, key=lambda item: (item[1], -(item[2] - item[1]), item[0])):
        _value, start, end = span
        if any(start >= existing_start and end <= existing_end for _existing_value, existing_start, existing_end in deduped):
            continue
        deduped.append(span)
    return sorted(deduped, key=lambda item: (item[1], item[2], item[0]))


def _quantity_subject(tokens: list[str], start: int) -> str:
    if start >= len(tokens):
        return ""
    token = tokens[start]
    if token in {"year", "years"} or token in _QUANTITY_SUBJECT_STOPWORDS or token in _NUMBER_WORDS or token in _NUMBER_SCALES:
        return ""
    normalized = _SINGULAR_SUBJECTS.get(token, token[:-1] if token.endswith("s") and len(token) > 3 else token)
    return normalized if normalized in _QUANTITY_COUNT_SUBJECTS else ""


def _claim_subject_terms(text: str) -> list[str]:
    terms: set[str] = set()
    if _term_in_text("software", text):
        terms.add("software")
    for canonical, variants in _GROUNDED_SKILL_TERMS.items():
        if any(_term_in_text(variant, text) for variant in variants):
            terms.add(canonical)
    return sorted(terms)


def _claim_terms(claim: str) -> list[str]:
    kind, first, second = _split_claim(claim)
    if kind == "skill" and first:
        return list(_GROUNDED_SKILL_TERMS.get(first, (first,)))
    if kind == "title" and first:
        return [first, f"{first} engineer", f"{first} software engineer"]
    if kind in {"quantity", "years"}:
        terms = [term for term in (first, second) if term]
        if kind == "quantity" and first and second:
            terms.append(f"{first} {second}")
        return terms
    return []


def _split_claim(claim: str) -> tuple[str, str, str]:
    parts = claim.split(":", 2)
    if len(parts) == 1:
        return parts[0], "", ""
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return parts[0], parts[1], parts[2]


def _fact_text(fact: JsonObject) -> str:
    return _normal_text(_raw_fact_text(fact))


def _raw_fact_text(fact: JsonObject) -> str:
    pieces = [_item(fact, "text", "")]
    pieces.extend(_array(_item(fact, "normalized_terms", [])))
    for entry in _array(_item(fact, "evidence", [])):
        if isinstance(entry, dict):
            pieces.append(_item(entry, "text", ""))
    return " ".join(_text(item) for item in pieces)


def _fact_text_segments(fact: JsonObject) -> list[str]:
    segments = [_normal_text(_item(fact, "text", ""))]
    segments.extend(_normal_text(item) for item in _array(_item(fact, "normalized_terms", [])))
    for entry in _array(_item(fact, "evidence", [])):
        if isinstance(entry, dict):
            segments.append(_normal_text(_item(entry, "text", "")))
    return [segment for segment in segments if segment]


def _fact_allowed(fact: JsonObject, allow_inferred: bool) -> bool:
    state = _item(fact, "verification_state", VerificationState.UNKNOWN.value)
    return state in _VERIFIED_FACT_STATES or (allow_inferred and state == VerificationState.INFERRED.value)


def _fact_overlaps_terms(fact: JsonObject, terms: list[str]) -> bool:
    return any(_term_in_text(term, _fact_text(fact)) for term in terms)


def _structured_terms(mapping: JsonObject, keys: tuple[str, ...]) -> list[str]:
    terms: list[str] = []
    for key in keys:
        value = _item(mapping, key)
        if isinstance(value, list):
            terms.extend(_normal_text(item) for item in value if _normal_text(item))
        elif isinstance(value, str) and _normal_text(value):
            terms.append(_normal_text(value))
    return terms


def _terms_overlap(left: list[str], right: list[str]) -> bool:
    return any(_term_in_text(left_term, right_term) or _term_in_text(right_term, left_term) for left_term in left for right_term in right)


def _specific_terms(terms: list[str]) -> list[str]:
    expanded: set[str] = set()
    for term in terms:
        normalized = _normal_text(term)
        if not normalized or normalized in _GENERIC_TERMS:
            continue
        expanded.add(normalized)
        for canonical, variants in _GROUNDED_SKILL_TERMS.items():
            if normalized == canonical or any(_term_in_text(normalized, variant) for variant in variants):
                expanded.add(canonical)
                expanded.update(_normal_text(variant) for variant in variants)
    return sorted(expanded)


def _term_in_text(term: Any, text: str) -> bool:
    normalized = _normal_text(term)
    normalized_text = _normal_text(text)
    if not normalized or not normalized_text:
        return False
    if " " in normalized:
        return normalized in normalized_text
    words = normalized_text.split()
    return normalized in words or f"{normalized}s" in words or (normalized.endswith("s") and normalized[:-1] in words)


def _token_positions(tokens: list[str], needle: list[str]) -> list[int]:
    if not needle:
        return []
    return [
        index
        for index in range(0, len(tokens) - len(needle) + 1)
        if tokens[index : index + len(needle)] == needle
    ]


def _normal_text(value: Any) -> str:
    text = str(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _text(value: Any) -> str:
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


def _item(mapping: Any, key: str, default: Any = None) -> Any:
    if isinstance(mapping, dict) and key in mapping:
        return mapping[key]
    return default


def _array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
