"""Deterministic data-only domain functions for the resume-core public API."""

from __future__ import annotations

import copy
import hashlib
import re
from typing import Any
from unicodedata import category as _unicode_category
from unicodedata import normalize as _unicode_normalize

from .dates import date_key as _parse_date_key, record_date_result as _record_date_result
from .pointers import _append_already_present, _pointer_parent_exists, _pointer_value, _set_pointer
from .schemas import (
    CANONICAL_RESUME_SCHEMA,
    ChangeOperationStatus,
    JsonObject,
    RESUME_CHANGE_OPERATION_SCHEMA,
    RequirementClassification,
    ResolutionState,
    VerificationState,
    to_json_dict,
)


SCHEMA_VERSION = "resume-core.result.v1"
ALGORITHM_VERSION = "resume-core.match.v1"

_RESOLVED = {
    ResolutionState.EXACT_MATCH.value,
    ResolutionState.ALIAS_MATCH.value,
    ResolutionState.VERIFIED_FACT_MATCH.value,
}
_VERIFIED_FACT_STATES = {
    VerificationState.SOURCE_STATED.value,
    VerificationState.USER_VERIFIED.value,
    VerificationState.IMPORTED.value,
}
_CHANGE_OPERATION_OPS = {"replace", "rewrite", "insert", "remove", "move"}
_CHANGE_OPERATION_STATUSES = {status.value for status in ChangeOperationStatus}
_CONTROL_WHITELIST = {"\n", "\r", "\t"}
_INVALID_DATE_CODE = "invalid_date"
_REVERSED_RANGE_CODE = "reversed_range"
_SMART_TRANSLATION = str.maketrans(
    {
        "\u00a0": " ",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u2023": "-",
        "\u2043": "-",
        "\u2219": "-",
        "\u25e6": "-",
        "\uf0b7": "-",
    }
)
_GUARDED_TERMS = {
    "aws": ("aws", "amazon web services"),
    "graphql": ("graphql", "graph ql"),
    "staff_title": ("staff software engineer", "staff engineer"),
    "unsupported_scale": ("20 million", "20m users"),
    "unsupported_management": ("30 engineers", "managed 30"),
}
_NUMBER_WORDS = {
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
}
_YEARS_RE = re.compile(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\+?\s+years?\b", re.IGNORECASE)
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
    "distributed",
    "experience",
    "for",
    "in",
    "of",
    "operating",
    "or",
    "preferred",
    "production",
    "product",
    "products",
    "qualifications",
    "required",
    "strong",
    "systems",
    "the",
    "through",
    "with",
}
_TERM_VARIANTS = {
    "api": ("api", "apis", "rest api", "rest apis"),
    "api architecture": (
        "api architecture",
        "api architecture design",
        "api design",
        "application architecture",
        "designed apis",
        "designed rest apis",
        "rest api design",
        "rest apis",
    ),
    "aws": ("aws", "amazon web services"),
    "graphql": ("graphql", "graph ql"),
    "leadership": (
        "code review",
        "cross team architecture",
        "delivery planning",
        "design review",
        "led a small team",
        "mentoring",
        "team leadership",
        "technical leadership",
    ),
    "node js": ("node", "node js", "nodejs"),
    "postgresql": ("postgres", "postgresql"),
    "react": ("react",),
    "responsive design": (
        "desktop and mobile",
        "responsive apps",
        "responsive design",
        "responsive web applications",
        "responsive web apps",
    ),
    "saas": ("multi tenant saas", "saas", "software as a service"),
    "software engineering": (
        "full stack software development",
        "software development",
        "software engineering",
        "software engineering experience",
    ),
    "typescript": ("typescript", "type script"),
}
_RELATED_REQUIREMENT_TERMS = {
    "aws": ("azure", "cloud infrastructure", "cloud services"),
    "graphql": ("rest api", "rest apis", "api design"),
}
_SENIORITY_HINTS = (
    ("junior", re.compile(r"\b(junior|jr\.?)\b", re.IGNORECASE)),
    ("mid-level", re.compile(r"\b(mid[- ]level|midlevel)\b", re.IGNORECASE)),
    ("senior", re.compile(r"\b(senior|sr\.?)\b", re.IGNORECASE)),
    ("staff", re.compile(r"\bstaff\b", re.IGNORECASE)),
    ("principal", re.compile(r"\bprincipal\b", re.IGNORECASE)),
    ("lead", re.compile(r"\blead\b", re.IGNORECASE)),
    ("manager", re.compile(r"\bmanager\b", re.IGNORECASE)),
    ("director", re.compile(r"\bdirector\b", re.IGNORECASE)),
    ("executive", re.compile(r"\b(vp|vice president|head of|chief)\b", re.IGNORECASE)),
)
_INDUSTRY_HINTS = (
    ("SaaS", re.compile(r"\b(saas|software as a service)\b", re.IGNORECASE)),
    ("FinTech", re.compile(r"\b(fintech|financial technology|payments?|banking)\b", re.IGNORECASE)),
    ("Healthcare", re.compile(r"\b(healthcare|health care|medical|clinical)\b", re.IGNORECASE)),
    ("E-commerce", re.compile(r"\b(e[- ]?commerce|marketplace|retail)\b", re.IGNORECASE)),
    ("Education", re.compile(r"\b(edtech|education|learning platform)\b", re.IGNORECASE)),
)
_DOMAIN_HINTS = (
    ("API architecture", re.compile(r"\b(api architecture|api design|rest apis?|graphql)\b", re.IGNORECASE)),
    ("Cloud infrastructure", re.compile(r"\b(cloud infrastructure|aws|azure|gcp|kubernetes)\b", re.IGNORECASE)),
    ("Responsive design", re.compile(r"\b(responsive design|responsive web|mobile)\b", re.IGNORECASE)),
    ("Data engineering", re.compile(r"\b(data engineering|etl|analytics pipeline)\b", re.IGNORECASE)),
    ("Full-stack software development", re.compile(r"\b(full[- ]stack|frontend|backend)\b", re.IGNORECASE)),
)


def sanitizeText(text: Any, rules: JsonObject | None = None) -> JsonObject:
    """Normalize ATS-hostile characters and report unsupported controls."""

    del rules
    if text is None:
        return _result("error", text="", warnings=[_issue("invalid_text", "text is required.")])

    warnings: list[JsonObject] = []
    normalized_chars: list[str] = []
    for index, char in enumerate(str(text).translate(_SMART_TRANSLATION)):
        if _unicode_category(char) == "Cc" and char not in _CONTROL_WHITELIST:
            warnings.append(
                _issue(
                    "unsupported_control_character",
                    "Removed unsupported control character.",
                    f"text/{index}",
                    {"codepoint": f"U+{ord(char):04X}"},
                )
            )
        else:
            normalized_chars.append(char)

    cleaned = _unicode_normalize("NFKC", "".join(normalized_chars))
    return _result("warning" if warnings else "ok", text=cleaned, warnings=warnings)


def normalizeResume(source_resume: Any, config: JsonObject | None = None) -> JsonObject:
    """Normalize supplied structured resume data without adding unsupported claims."""

    del config
    resume = _unwrap(source_resume, "source_resume")
    if not isinstance(resume, dict):
        return _result(
            "error",
            canonical_resume={},
            warnings=[_issue("invalid_resume", "source_resume must be an object.")],
            provenance_map={},
        )

    warnings: list[JsonObject] = []
    normalized = _clean_copy(resume, warnings)
    for field_name in ("experience", "skills", "education"):
        if field_name not in normalized:
            normalized[field_name] = []
            warnings.append(_issue("missing_array_normalized", f"Added empty {field_name} array.", field_name))
    if "schema_version" not in normalized:
        normalized["schema_version"] = "canonical-resume.v1"
    if "resume_id" not in normalized:
        normalized["resume_id"] = _stable_id("resume", _text(normalized))
    if "source" not in normalized:
        normalized["source"] = {"kind": "structured"}
    if "provenance" not in normalized:
        normalized["provenance"] = []
    if "verification_state" not in normalized:
        normalized["verification_state"] = VerificationState.SOURCE_STATED.value

    provenance_map = {}
    for entry in _array(_item(normalized, "provenance", [])):
        if isinstance(entry, dict) and "claim_id" in entry:
            provenance_map[str(entry["claim_id"])] = copy.deepcopy(entry)

    return _result(
        "warning" if warnings else "ok",
        canonical_resume=normalized,
        warnings=warnings,
        provenance_map=provenance_map,
    )


def validateResume(canonical_resume: Any) -> JsonObject:
    """Validate canonical resume shape, required arrays, dates, and truth states."""

    resume = _unwrap(canonical_resume, "canonical_resume")
    errors: list[JsonObject] = []
    warnings: list[JsonObject] = []
    if not isinstance(resume, dict):
        return _result("error", errors=[_issue("invalid_resume", "canonical_resume must be an object.")], warnings=warnings)

    errors.extend(_schema_required_field_errors(resume, CANONICAL_RESUME_SCHEMA, "CanonicalResume"))
    for field_name in ("experience", "skills", "education"):
        if field_name in resume and not isinstance(resume[field_name], list):
            errors.append(_issue("invalid_array", f"{field_name} must be an array.", field_name))

    state = _item(resume, "verification_state")
    valid_states = {item.value for item in VerificationState}
    if state is not None and state not in valid_states:
        errors.append(_issue("invalid_verification_state", "Unknown verification state.", "verification_state"))

    provenance = _item(resume, "provenance", [])
    if provenance is not None and not isinstance(provenance, list):
        errors.append(_issue("invalid_provenance", "provenance must be an array.", "provenance"))
    else:
        for index, entry in enumerate(_array(provenance)):
            if not isinstance(entry, dict) or "source" not in entry or "text" not in entry:
                errors.append(_issue("malformed_provenance", "Provenance entries require source and text.", f"provenance/{index}"))

    for index, entry in enumerate(_array(_item(resume, "experience", []))):
        if isinstance(entry, dict):
            _check_dates(entry, f"experience/{index}", errors, warnings)

    return _result("error" if errors else "ok", canonical_resume=resume, errors=errors, warnings=warnings)


def normalizeJobModel(source_job: Any, config: JsonObject | None = None) -> JsonObject:
    """Normalize job requirements with deterministic requirement IDs."""

    job = _unwrap(source_job, "source_job")
    config = config or {}
    if not isinstance(job, dict):
        return _result("error", job_model={}, warnings=[_issue("invalid_job", "source_job must be an object.")])

    warnings: list[JsonObject] = []
    raw_requirements = _item(job, "requirements", [])
    if isinstance(raw_requirements, str):
        raw_requirements = _requirements_from_text(raw_requirements)
    if not isinstance(raw_requirements, list):
        raw_requirements = []
        warnings.append(_issue("invalid_requirements", "requirements must be an array.", "requirements"))

    raw_preferred = _item(job, "preferred", [])
    if isinstance(raw_preferred, str):
        raw_preferred = _requirements_from_text(raw_preferred)
    if raw_preferred is None:
        raw_preferred = []
    if not isinstance(raw_preferred, list):
        raw_preferred = []
        warnings.append(_issue("invalid_preferred", "preferred must be an array.", "preferred"))

    normalized_requirements = [_requirement(item, index, config) for index, item in enumerate(raw_requirements)]
    preferred_start = len(normalized_requirements)
    normalized_preferred = [
        _requirement(_preferred_source(item), preferred_start + index, config) for index, item in enumerate(raw_preferred)
    ]
    all_requirements = _dedupe_requirements([*normalized_requirements, *normalized_preferred])
    requirements = [item for item in all_requirements if _classification(item) != RequirementClassification.PREFERRED.value]
    preferred = [item for item in all_requirements if _classification(item) == RequirementClassification.PREFERRED.value]
    title = _optional_text(_item(job, "title"))
    company = _optional_text(_item(job, "company"))
    description = _job_description(job)
    job_text = " ".join(part for part in [title or "", company or "", description, _text(all_requirements)] if part)
    model = {
        "schema_version": _item(job, "schema_version", "job-model.v1"),
        "job_id": _item(job, "job_id") or _stable_id("job", _text(job)),
        "title": title,
        "company": company,
        "seniority": _optional_text(_item(job, "seniority")) or _seniority_from_title(title),
        "industries": _concepts(_item(job, "industries"), _INDUSTRY_HINTS, job_text),
        "domains": _concepts(_item(job, "domains"), _DOMAIN_HINTS, job_text),
        "source": copy.deepcopy(_item(job, "source", {"kind": "structured"})),
        "metadata": copy.deepcopy(_item(job, "metadata", {})),
        "requirements": requirements,
        "preferred": preferred,
        "terminology": _job_terms(title, requirements, preferred, description),
    }
    return _result("warning" if warnings else "ok", job_model=model, warnings=warnings)


def scoreMatch(
    canonical_resume: Any,
    job_model: Any,
    career_fact_dtos: list[JsonObject] | None = None,
    config: JsonObject | None = None,
) -> JsonObject:
    """Score resume and job fit from supplied resume, job, fact DTO, and config data."""

    resume = _unwrap(canonical_resume, "canonical_resume")
    job = _unwrap(job_model, "job_model")
    config = config or {}
    facts = [item for item in career_fact_dtos or [] if isinstance(item, dict)]
    if not isinstance(resume, dict) or not isinstance(job, dict):
        return _result("error", match_result=_empty_match())

    resume_text = _normal_text(_text(resume))
    aliases = _alias_map(config)
    fact_index = _fact_index(facts)
    requirement_results: list[JsonObject] = []
    unresolved: list[str] = []
    preferred_unresolved: list[str] = []
    score = 0.0
    max_score = 0.0

    for requirement in _requirements(job):
        requirement_id = str(_item(requirement, "requirement_id") or _stable_id("req", _text(requirement)))
        classification = _classification(requirement)
        weight = _number(_item(requirement, "weight"), 1.0)
        terms = _terms(requirement)
        max_score += max(weight, 0.0)
        state, matched_fact_ids, evidence = _resolve_requirement(requirement, terms, resume_text, aliases, fact_index, config)

        requirement_score = weight if state in _RESOLVED else 0.0
        blocking = classification == RequirementClassification.REQUIRED.value and state not in _RESOLVED
        if blocking:
            unresolved.append(requirement_id)
        elif classification == RequirementClassification.PREFERRED.value and state not in _RESOLVED:
            preferred_unresolved.append(requirement_id)
        score += requirement_score
        requirement_results.append(
            {
                "requirement_id": requirement_id,
                "classification": classification,
                "concept": _item(requirement, "concept"),
                "source_text": _item(requirement, "source_text"),
                "normalized_terms": terms,
                "resolution_state": state,
                "score": round(requirement_score, 4),
                "max_score": round(max(weight, 0.0), 4),
                "matched_fact_ids": matched_fact_ids,
                "blocking": blocking,
                "unresolved": state not in _RESOLVED,
                "evidence": evidence,
            }
        )

    strict = _strict_policy(config)
    match = {
        "schema_version": "match-result.v1",
        "match_id": _stable_id("match", f"{_item(resume, 'resume_id', '')}:{_item(job, 'job_id', '')}:{score}:{unresolved}"),
        "job_id": str(_item(job, "job_id", "")),
        "resume_id": str(_item(resume, "resume_id", "")),
        "score": round(score, 4),
        "max_score": round(max_score, 4),
        "score_percent": round(score * 100 / max_score, 2) if max_score else 0.0,
        "requirement_results": requirement_results,
        "unresolved_requirement_ids": unresolved,
        "preferred_unresolved_requirement_ids": preferred_unresolved,
        "can_continue": not unresolved or not strict,
        "explanations": ["Required unresolved requirements block continuation." if unresolved and strict else "No required hard gate is blocking continuation."],
        "algorithm_version": ALGORITHM_VERSION,
    }
    return _result("ok", match_result=match)


def getUnresolvedRequirements(match_result: Any, policy: JsonObject | None = None) -> JsonObject:
    """Return unresolved requirement DTOs and continuation gate state."""

    match = _unwrap(match_result, "match_result")
    policy = policy or {}
    if not isinstance(match, dict):
        return _result("error", unresolved_requirements=[], can_continue=False)

    unresolved_ids = {str(item) for item in _array(_item(match, "unresolved_requirement_ids", []))}
    preferred_ids = {str(item) for item in _array(_item(match, "preferred_unresolved_requirement_ids", []))}
    all_results = [item for item in _array(_item(match, "requirement_results", [])) if isinstance(item, dict)]
    required_unresolved = [
        _unresolved_copy(item)
        for item in all_results
        if _item(item, "requirement_id") in unresolved_ids
        or (_item(item, "classification") == RequirementClassification.REQUIRED.value and _item(item, "resolution_state") not in _RESOLVED)
    ]
    preferred_unresolved = [
        _unresolved_copy(item)
        for item in all_results
        if _item(item, "requirement_id") in preferred_ids
        or (_item(item, "classification") == RequirementClassification.PREFERRED.value and _item(item, "resolution_state") not in _RESOLVED)
    ]
    contextual_unresolved = [
        _unresolved_copy(item)
        for item in all_results
        if _item(item, "classification") == RequirementClassification.CONTEXTUAL.value and _item(item, "resolution_state") not in _RESOLVED
    ]
    include_contextual = bool(_item(policy, "include_contextual"))
    unresolved = _rank_unresolved(required_unresolved + preferred_unresolved + (contextual_unresolved if include_contextual else []))
    blocking = _rank_unresolved(required_unresolved)
    require_resolution = bool(_item(policy, "require_hard_resolution") or _item(policy, "require_resolution") or _item(policy, "policy") == "strict")
    can_continue = not blocking if require_resolution else bool(_item(match, "can_continue", True))
    return _result(
        "ok",
        unresolved_requirements=unresolved,
        required_unresolved_requirements=blocking,
        preferred_unresolved_requirements=_rank_unresolved(preferred_unresolved),
        blocking_requirements=blocking,
        ranked_unresolved_requirements=unresolved,
        selected_requirement=copy.deepcopy(unresolved[0]) if unresolved else None,
        can_continue=can_continue,
    )


def rankResumeContent(canonical_resume: Any, job_model: Any, match_result: Any, config: JsonObject | None = None) -> JsonObject:
    """Build a deterministic content ranking while preserving the base resume."""

    del match_result
    resume = _unwrap(canonical_resume, "canonical_resume")
    job = _unwrap(job_model, "job_model")
    config = config or {}
    if not isinstance(resume, dict) or not isinstance(job, dict):
        return _result("error", selection_plan={}, ranked_content=[])

    terms = sorted({term for requirement in _requirements(job) for term in _terms(requirement)})
    experience_limit = int(_item(config, "max_experience", _item(config, "experience_max", len(_array(_item(resume, "experience", []))))))
    skills_limit = int(_item(config, "max_skills", _item(config, "skills_max", len(_array(_item(resume, "skills", []))))))
    bullet_limit = int(_item(config, "max_bullets_per_role", _item(config, "bullets_per_role_max", 999)))
    ranked: list[JsonObject] = []

    for index, item in enumerate(_array(_item(resume, "experience", []))):
        item_id = _item(item, "id", f"experience_{index}") if isinstance(item, dict) else f"experience_{index}"
        ranked.append({"kind": "experience", "id": item_id, "source_index": index, "score": _relevance(_text(item), terms)})
    for index, item in enumerate(_array(_item(resume, "skills", []))):
        ranked.append({"kind": "skill", "id": f"skill_{index}", "source_index": index, "score": _relevance(_text(item), terms)})

    ranked.sort(key=lambda item: (-item["score"], item["kind"], item["source_index"]))
    plan = {
        "section_order": list(_item(config, "section_order", ["basics", "summary", "skills", "experience", "education"])),
        "experience_ids": [item["id"] for item in ranked if item["kind"] == "experience"][: max(experience_limit, 0)],
        "skill_indices": [item["source_index"] for item in ranked if item["kind"] == "skill"][: max(skills_limit, 0)],
        "limits": {
            "max_experience": max(experience_limit, 0),
            "max_skills": max(skills_limit, 0),
            "max_bullets_per_role": max(bullet_limit, 0),
        },
    }
    return _result("ok", selection_plan=plan, ranked_content=ranked)


def validateChange(
    canonical_resume: Any,
    operation: Any,
    job_model: Any,
    career_fact_dtos: list[JsonObject] | None = None,
    policy: JsonObject | None = None,
) -> JsonObject:
    """Validate a proposed resume change against current content and supplied facts."""

    resume = _unwrap(canonical_resume, "canonical_resume")
    op = _unwrap(operation, "operation")
    job = _unwrap(job_model, "job_model")
    policy = policy or {}
    facts = [item for item in career_fact_dtos or [] if isinstance(item, dict)]
    grounding = {"supported": False, "supporting_fact_ids": [], "supporting_requirement_ids": [], "guarded_claims": []}
    if not isinstance(resume, dict) or not isinstance(op, dict):
        return _result("error", operation_id="", validation_state="rejected", errors=[_issue("invalid_operation", "operation and canonical_resume must be objects.")], grounding=grounding)

    errors: list[JsonObject] = []
    required_fields = set(RESUME_CHANGE_OPERATION_SCHEMA["required"])
    for field_name in sorted(required_fields - set(op)):
        errors.append(_issue("missing_field", f"ResumeChangeOperation requires {field_name}.", field_name))

    operation_id = str(_item(op, "operation_id", ""))
    operation_status = str(_item(op, "status", ""))
    if "status" in op and operation_status not in _CHANGE_OPERATION_STATUSES:
        errors.append(_issue("invalid_status", "Operation status must be proposed, validated, rejected, applied, accepted, or modified.", "status"))
    path = _operation_path(op)
    if not path.startswith("/"):
        errors.append(_issue("invalid_path", "Operation path must be a JSON pointer.", "path"))

    path_exists, current_value = _pointer_value(resume, path)
    parent_exists = _pointer_parent_exists(resume, path)
    operation_kind = str(_item(op, "op", "replace" if path_exists else "insert"))
    if "op" in op and operation_kind not in _CHANGE_OPERATION_OPS:
        errors.append(_issue("invalid_op", "Operation op must be insert, move, remove, replace, or rewrite.", "op"))
    if not parent_exists:
        errors.append(_issue("invalid_path", "Operation path parent does not exist in the canonical resume.", "path"))
    if operation_kind == "replace" and not path_exists:
        errors.append(_issue("missing_target", "Replace operations require an existing target path.", "path"))
    if operation_kind == "insert" and path_exists and not path.endswith("/-"):
        errors.append(_issue("target_exists", "Insert operations require a new object member or array append path.", "path"))
    if "before" in op and _item(op, "before") != current_value and not (_item(op, "before") is None and not path_exists):
        errors.append(_issue("before_mismatch", "Operation before value does not match current content.", "before"))

    requirements = {str(_item(item, "requirement_id")): item for item in _requirements(job) if isinstance(item, dict)}
    linked_requirement_ids = [str(item) for item in _array(_item(op, "linked_requirement_ids", []))]
    missing_requirements = [item for item in linked_requirement_ids if item not in requirements]
    if missing_requirements:
        errors.append(_issue("missing_requirement", "Operation references missing requirement IDs.", "linked_requirement_ids", {"requirement_ids": missing_requirements}))

    fact_index = _fact_index(facts)
    linked_fact_ids = [str(item) for item in _array(_item(op, "linked_fact_ids", []))]
    missing_fact_ids = [item for item in linked_fact_ids if item not in fact_index]
    if missing_fact_ids:
        errors.append(_issue("missing_fact", "Operation references missing fact IDs.", "linked_fact_ids", {"fact_ids": missing_fact_ids}))

    after_text = _normal_text(_text(_item(op, "after")))
    guarded = _guarded_claims(after_text)
    support_by_claim = _claim_support(guarded, fact_index, linked_fact_ids, bool(_item(policy, "allow_inferred_facts", False)))
    supported_claims = set(support_by_claim)
    supporting_fact_ids = sorted({fact_id for ids in support_by_claim.values() for fact_id in ids})
    grounding = {
        "supported": False,
        "supporting_fact_ids": supporting_fact_ids,
        "supporting_requirement_ids": linked_requirement_ids,
        "guarded_claims": sorted(guarded),
    }

    unsupported_guarded = guarded - supported_claims
    if unsupported_guarded:
        errors.append(_issue("unsupported_guarded_claim", "Guarded claims require exact supplied verified fact DTO support.", "after", {"claims": sorted(unsupported_guarded)}))
    if _years(after_text) and not _facts_support_terms(_years(after_text), fact_index, linked_fact_ids, bool(_item(policy, "allow_inferred_facts", False))):
        errors.append(_issue("unsupported_years_claim", "Years-of-experience claims require matching verified fact support.", "after"))
    if guarded and not linked_fact_ids:
        errors.append(_issue("missing_linked_fact", "Guarded changes must link supporting fact IDs.", "linked_fact_ids"))
    if guarded and not linked_requirement_ids:
        errors.append(_issue("missing_linked_requirement", "Guarded changes must link the requirement IDs they resolve.", "linked_requirement_ids"))
    if _title_inflation(path, current_value, _item(op, "after"), support_by_claim):
        errors.append(_issue("title_inflation", "Employment title changes require exact user-verified title fact support.", "after"))

    grounding["supported"] = not errors
    validation_state = "validated" if not errors else "rejected"
    result = _result("ok" if not errors else "rejected", operation_id=operation_id, validation_state=validation_state, errors=errors, grounding=grounding)
    if not errors:
        validated = copy.deepcopy(op)
        validated["status"] = ChangeOperationStatus.VALIDATED.value
        validated["validation_state"] = validation_state
        result["validated_operation"] = to_json_dict(validated)
    return result


def applyChange(working_resume: Any, validated_operation: Any) -> JsonObject:
    """Apply only validated operations to a copied working resume."""

    resume = _unwrap(working_resume, "working_resume")
    op = _unwrap(validated_operation, "validated_operation")
    operation_id = str(_item(op, "operation_id", "")) if isinstance(op, dict) else ""
    if not isinstance(resume, dict) or not isinstance(op, dict):
        return _result("error", working_resume=copy.deepcopy(resume) if isinstance(resume, dict) else {}, operation_id=operation_id, audit={"applied": False})
    if _item(op, "status") != ChangeOperationStatus.VALIDATED.value and _item(op, "validation_state") != "validated":
        return _result("rejected", working_resume=copy.deepcopy(resume), operation_id=operation_id, audit={"applied": False, "reason": "operation_not_validated"})

    result_resume = copy.deepcopy(resume)
    path = _operation_path(op)
    before = _item(op, "before")
    after = copy.deepcopy(_item(op, "after"))
    path_exists, current = _pointer_value(result_resume, path)
    if not _pointer_parent_exists(result_resume, path):
        return _result("error", working_resume=result_resume, operation_id=operation_id, audit={"applied": False, "reason": "invalid_path"})
    if _append_already_present(result_resume, path, after):
        return _result("ok", working_resume=result_resume, operation_id=operation_id, audit={"applied": False, "already_applied": True, "path": path})
    if current == after:
        return _result("ok", working_resume=result_resume, operation_id=operation_id, audit={"applied": False, "already_applied": True})
    if before != current and not (before is None and not path_exists):
        return _result("rejected", working_resume=result_resume, operation_id=operation_id, audit={"applied": False, "reason": "before_mismatch"})
    applied = _set_pointer(result_resume, path, after)
    applied_operation = copy.deepcopy(op)
    if applied:
        applied_operation["status"] = ChangeOperationStatus.APPLIED.value
    return _result(
        "ok" if applied else "error",
        working_resume=result_resume,
        operation_id=operation_id,
        applied_operation=applied_operation if applied else None,
        audit={
            "applied": applied,
            "path": path,
            "before": before,
            "after": after if applied else None,
            "linked_fact_ids": _array(_item(op, "linked_fact_ids", [])),
            "linked_requirement_ids": _array(_item(op, "linked_requirement_ids", [])),
            "status_transition": "validated->applied" if applied else "not_applied",
        },
    )


def validateGrounding(
    working_resume: Any,
    career_fact_dtos: list[JsonObject] | None = None,
    applied_operations: list[JsonObject] | None = None,
    policy: JsonObject | None = None,
) -> JsonObject:
    """Check final resume claims against supplied facts and operation provenance."""

    resume = _unwrap(working_resume, "working_resume")
    policy = policy or {}
    facts = [item for item in career_fact_dtos or [] if isinstance(item, dict)]
    if not isinstance(resume, dict):
        return _result("error", unsupported_claims=[], missing_provenance=[], warnings=[])

    fact_index = _fact_index(facts)
    linked_fact_ids = [
        str(fact_id)
        for operation in applied_operations or []
        if isinstance(operation, dict)
        for fact_id in _array(_item(operation, "linked_fact_ids", []))
    ]
    text = _normal_text(_text(resume))
    guarded = _guarded_claims(text)
    supported = set(_claim_support(guarded, fact_index, linked_fact_ids, bool(_item(policy, "allow_inferred_facts", False))))
    unsupported = [{"claim": claim, "reason": "missing_verified_fact"} for claim in sorted(guarded - supported)]
    if not _item(policy, "allow_inferred_facts", False):
        for fact in facts:
            if _item(fact, "verification_state") == VerificationState.INFERRED.value and _term_in_text(_fact_text(fact), text):
                unsupported.append({"claim": str(_item(fact, "fact_id", "")), "reason": "inferred_fact_not_allowed"})
    missing_provenance = _missing_provenance(resume)
    return _result("fail" if unsupported or missing_provenance else "pass", unsupported_claims=unsupported, missing_provenance=missing_provenance, warnings=[])


def validateFinalResume(
    working_resume: Any,
    job_model: Any,
    career_fact_dtos: list[JsonObject] | None = None,
    config: JsonObject | None = None,
    applied_operations: list[JsonObject] | None = None,
) -> JsonObject:
    """Run final deterministic validation and scoring before rendering/export."""

    resume = _unwrap(working_resume, "working_resume")
    config = config or {}
    validation = validateResume(resume)
    grounding = validateGrounding(resume, career_fact_dtos or [], applied_operations or [], config)
    scoring = scoreMatch(resume, job_model, career_fact_dtos or [], config)
    errors = list(_item(validation, "errors", []))
    if _item(grounding, "status") == "fail":
        errors.extend(_item(grounding, "unsupported_claims", []))
        errors.extend(_item(grounding, "missing_provenance", []))
    warnings = list(_item(validation, "warnings", [])) + list(_item(grounding, "warnings", []))
    warnings.extend(_duplicate_warnings(resume if isinstance(resume, dict) else {}))
    warnings.extend(_keyword_warnings(resume if isinstance(resume, dict) else {}))
    return _result(
        "pass" if not errors else "fail",
        final_resume=copy.deepcopy(resume) if isinstance(resume, dict) else {},
        match_result=_item(scoring, "match_result", _empty_match()),
        errors=errors,
        warnings=warnings,
    )


def _result(status: str, **fields: Any) -> JsonObject:
    return {"schema_version": SCHEMA_VERSION, "status": status, **to_json_dict(fields)}


def _issue(code: str, message: str, field_path: str | None = None, details: JsonObject | None = None) -> JsonObject:
    issue: JsonObject = {"code": code, "message": message, "severity": "error"}
    if field_path is not None:
        issue["field_path"] = field_path
    if details:
        issue["details"] = details
    return issue


def _item(mapping: Any, key: str, default: Any = None) -> Any:
    if isinstance(mapping, dict) and key in mapping:
        return mapping[key]
    return default


def _unwrap(value: Any, key: str) -> Any:
    payload = to_json_dict(value)
    if isinstance(payload, dict) and key in payload:
        return payload[key]
    return payload


def _schema_required_field_errors(payload: JsonObject, schema: JsonObject, schema_name: str) -> list[JsonObject]:
    errors: list[JsonObject] = []
    for field_name in schema.get("required", []):
        if isinstance(field_name, str) and field_name not in payload:
            errors.append(_issue("missing_field", f"{schema_name} requires {field_name}.", field_name))
    return errors


def _array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _clean_copy(value: Any, warnings: list[JsonObject]) -> Any:
    if isinstance(value, str):
        sanitized = sanitizeText(value)
        warnings.extend(_item(sanitized, "warnings", []))
        return sanitized["text"]
    if isinstance(value, list):
        return [_clean_copy(item, warnings) for item in value]
    if isinstance(value, dict):
        return {str(key): _clean_copy(item, warnings) for key, item in value.items()}
    return copy.deepcopy(value)


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


def _stable_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(_text(value).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def _check_dates(entry: JsonObject, path: str, errors: list[JsonObject], warnings: list[JsonObject]) -> None:
    start_value = _item(entry, "start_date")
    start = _parse_date_key(start_value)
    end_value = _item(entry, "end_date")
    end = _parse_date_key(end_value)
    _record_date_result(
        entry, "start_date", start_value, start, f"{path}/start_date", "start", errors, warnings, _issue, _INVALID_DATE_CODE
    )
    _record_date_result(
        entry, "end_date", end_value, end, f"{path}/end_date", "end", errors, warnings, _issue, _INVALID_DATE_CODE
    )
    if start.key and end.key and start.key > end.key:
        errors.append(_issue(_REVERSED_RANGE_CODE, "Start date is after end date.", path))


def _requirements_from_text(text: str) -> list[JsonObject]:
    requirements: list[JsonObject] = []
    current_classification = RequirementClassification.CONTEXTUAL.value
    for line in str(text).splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if "required qualification" in lowered or lowered.startswith("required"):
            current_classification = RequirementClassification.REQUIRED.value
            continue
        if "preferred qualification" in lowered or lowered.startswith("preferred") or "nice to have" in lowered:
            current_classification = RequirementClassification.PREFERRED.value
            continue
        cleaned = cleaned.lstrip("-*•◦ ").strip()
        if not cleaned:
            continue
        requirements.append({"source_text": cleaned, "concept": cleaned, "classification": current_classification})
    return requirements


def _requirement(raw: Any, index: int, config: JsonObject) -> JsonObject:
    if isinstance(raw, str):
        source_text = raw
        concept = raw
        classification = _infer_classification(raw)
        terms = _terms_for(raw)
        importance = _default_importance(classification)
        weight = _default_weight(classification, importance)
        requirement_id = _stable_requirement_id(index, concept, config)
        years = _extract_years(raw)
    elif isinstance(raw, dict):
        source_text = str(_item(raw, "source_text") or _item(raw, "concept") or "")
        concept = str(_item(raw, "concept") or source_text)
        classification = str(_item(raw, "classification") or _infer_classification(source_text))
        raw_terms = _item(raw, "normalized_terms")
        terms = [str(term).lower() for term in raw_terms] if isinstance(raw_terms, list) else _terms_for(concept)
        importance = str(_item(raw, "importance") or _default_importance(classification))
        weight = _number(_item(raw, "weight"), _default_weight(classification, importance))
        requirement_id = str(_item(raw, "requirement_id") or _stable_requirement_id(index, concept, config))
        years = _item(raw, "years") or _extract_years(source_text)
    else:
        source_text = str(raw)
        concept = source_text
        classification = RequirementClassification.CONTEXTUAL.value
        terms = _terms_for(source_text)
        importance = "low"
        weight = 1.0
        requirement_id = _stable_requirement_id(index, concept, config)
        years = None
    if classification not in {item.value for item in RequirementClassification}:
        classification = RequirementClassification.CONTEXTUAL.value
    return {
        "requirement_id": requirement_id,
        "classification": classification,
        "concept": concept,
        "importance": importance,
        "weight": weight,
        "source_text": source_text,
        "normalized_terms": terms,
        "years": years,
    }


def _preferred_source(raw: Any) -> Any:
    if isinstance(raw, dict):
        preferred = copy.deepcopy(raw)
        preferred["classification"] = RequirementClassification.PREFERRED.value
        return preferred
    return {"source_text": str(raw), "concept": str(raw), "classification": RequirementClassification.PREFERRED.value}


def _dedupe_requirements(requirements: list[JsonObject]) -> list[JsonObject]:
    seen: set[str] = set()
    unique: list[JsonObject] = []
    for requirement in requirements:
        requirement_id = str(_item(requirement, "requirement_id", ""))
        key = requirement_id or _stable_id("req", _text(requirement))
        if key in seen:
            continue
        seen.add(key)
        unique.append(requirement)
    return unique


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _job_description(job: JsonObject) -> str:
    for key in ("description", "job_description", "raw_description", "raw_text"):
        value = _item(job, key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _seniority_from_title(title: str | None) -> str | None:
    if not title:
        return None
    for seniority, pattern in _SENIORITY_HINTS:
        if pattern.search(title):
            return seniority
    return None


def _concepts(raw: Any, hints: tuple[tuple[str, re.Pattern[str]], ...], source_text: str) -> list[Any]:
    if isinstance(raw, list):
        concepts: list[Any] = []
        seen: set[str] = set()
        for item in raw:
            if isinstance(item, dict):
                copied = copy.deepcopy(item)
                key = _normal_text(copied)
            else:
                copied = str(item).strip()
                key = _normal_text(copied)
            if copied and key and key not in seen:
                seen.add(key)
                concepts.append(copied)
        return concepts
    return [label for label, pattern in hints if pattern.search(source_text)]


def _job_terms(
    title: str | None,
    requirements: list[JsonObject],
    preferred: list[JsonObject],
    description: str,
) -> list[JsonObject]:
    terms: list[JsonObject] = []
    seen: set[tuple[str, str]] = set()

    def add(surface: Any, canonical: Any, source: str, weight: Any = 1.0) -> None:
        surface_text = str(surface).strip()
        canonical_text = _normal_text(canonical)
        if not surface_text or not canonical_text:
            return
        key = (source, canonical_text)
        if key in seen:
            return
        seen.add(key)
        terms.append(
            {
                "surface": surface_text,
                "canonical": canonical_text,
                "source": source,
                "weight": round(_number(weight, 1.0), 4),
            }
        )

    if title:
        for token in _ordered_term_surfaces(title, include_full_text=False):
            add(token, token, "title", 1.0)

    for requirement in [*requirements, *preferred]:
        source_text = str(_item(requirement, "source_text") or _item(requirement, "concept") or "").strip()
        weight = _item(requirement, "weight", 1.0)
        if source_text:
            add(source_text, source_text, "requirement", weight)
        for term in _terms(requirement):
            add(_requirement_term_surface(source_text, term), term, "requirement", weight)

    if description:
        for token in _ordered_term_surfaces(description, include_full_text=True):
            add(token, token, "description", 1.0)

    return terms


def _ordered_term_surfaces(text: str, include_full_text: bool) -> list[str]:
    surfaces: list[str] = []
    if include_full_text and _normal_text(text):
        surfaces.append(text.strip())
    for match in re.finditer(r"[A-Za-z][A-Za-z0-9.+#-]*", text):
        surface = match.group(0).strip(" .;:,")
        if _specific_term(surface) and surface not in surfaces:
            surfaces.append(surface)
    for term in _terms_for(text):
        surface = _literal_surface(text, term)
        if surface not in surfaces:
            surfaces.append(surface)
    return surfaces


def _literal_surface(text: str, canonical: Any) -> str:
    canonical_text = _normal_text(canonical)
    if not text or not canonical_text:
        return str(canonical).strip()
    pattern = r"\b" + r"[\W_]+".join(re.escape(part) for part in canonical_text.split()) + r"\b"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return text[match.start() : match.end()]
    return str(canonical).strip()


def _requirement_term_surface(source_text: str, canonical: Any) -> str:
    surface = _literal_surface(source_text, canonical)
    if _normal_text(surface) == _normal_text(canonical):
        return surface
    return source_text.strip() or surface


def _resolve_requirement(
    requirement: JsonObject,
    terms: list[str],
    resume_text: str,
    aliases: dict[str, set[str]],
    fact_index: dict[str, JsonObject],
    config: JsonObject,
) -> tuple[str, list[str], list[JsonObject]]:
    allow_inferred = bool(_item(config, "allow_inferred_facts", False))
    required_years = _minimum_required_years(_item(requirement, "years") or _item(requirement, "source_text") or _item(requirement, "concept"))
    non_year_terms = [term for term in terms if _minimum_required_years(term) is None]

    if required_years is not None:
        years_met, years_evidence = _years_met(resume_text, required_years)
        if years_met and (not non_year_terms or _terms_in_text(non_year_terms, resume_text)):
            evidence = [{"source": "resume", "terms": non_year_terms, "required_years": required_years, "matched_years": years_evidence}]
            return ResolutionState.EXACT_MATCH.value, [], evidence
    elif _terms_in_text(terms, resume_text):
        return ResolutionState.EXACT_MATCH.value, [], [{"source": "resume", "terms": _matched_terms(terms, resume_text)}]

    alias_terms = _aliases_for_terms(terms, aliases)
    if required_years is not None:
        years_met, years_evidence = _years_met(resume_text, required_years)
        if years_met and alias_terms and _terms_in_text(alias_terms, resume_text):
            evidence = [{"source": "alias", "terms": _matched_terms(alias_terms, resume_text), "required_years": required_years, "matched_years": years_evidence}]
            return ResolutionState.ALIAS_MATCH.value, [], evidence
    elif alias_terms and _terms_in_text(alias_terms, resume_text):
        return ResolutionState.ALIAS_MATCH.value, [], [{"source": "alias", "terms": _matched_terms(alias_terms, resume_text)}]

    fact_state, fact_ids, fact_evidence = _fact_resolution(terms, required_years, fact_index, allow_inferred)
    if fact_state:
        return fact_state, fact_ids, fact_evidence

    related_terms = _related_terms_for(terms)
    if related_terms and _terms_in_text(related_terms, resume_text):
        return ResolutionState.RELATED_MATCH.value, [], [{"source": "resume", "terms": _matched_terms(related_terms, resume_text), "reason": "related_not_equivalent"}]

    possible_terms = _possible_terms(terms)
    if possible_terms and _terms_in_text(possible_terms, resume_text):
        return ResolutionState.POSSIBLE_MATCH.value, [], [{"source": "resume", "terms": _matched_terms(possible_terms, resume_text), "reason": "partial_overlap"}]

    return ResolutionState.UNKNOWN.value, [], []


def _stable_requirement_id(index: int, concept: str, config: JsonObject) -> str:
    prefix = str(_item(config, "requirement_id_prefix", "req"))
    return f"{prefix}_{index}_{hashlib.sha256(concept.lower().encode('utf-8')).hexdigest()[:8]}"


def _infer_classification(text: str) -> str:
    lowered = text.lower()
    if "preferred" in lowered or "nice to have" in lowered:
        return RequirementClassification.PREFERRED.value
    if "required" in lowered or "must" in lowered or "8+" in lowered or "requirement" in lowered:
        return RequirementClassification.REQUIRED.value
    return RequirementClassification.CONTEXTUAL.value


def _default_importance(classification: str) -> str:
    if classification == RequirementClassification.REQUIRED.value:
        return "high"
    if classification == RequirementClassification.PREFERRED.value:
        return "medium"
    return "low"


def _default_weight(classification: str, importance: Any) -> float:
    if classification == RequirementClassification.REQUIRED.value:
        return 10.0
    if classification == RequirementClassification.PREFERRED.value:
        return 3.0
    return 2.0 if str(importance) == "medium" else 1.0


def _requirements(job: Any) -> list[JsonObject]:
    if not isinstance(job, dict):
        return []
    unique: dict[str, JsonObject] = {}
    for item in [*_array(_item(job, "requirements", [])), *_array(_item(job, "preferred", []))]:
        if isinstance(item, dict):
            unique.setdefault(str(_item(item, "requirement_id", _stable_id("req", item))), item)
    return list(unique.values())


def _classification(requirement: JsonObject) -> str:
    value = str(_item(requirement, "classification", RequirementClassification.CONTEXTUAL.value))
    if value == RequirementClassification.CONTEXTUAL.value and _item(requirement, "required") is True:
        return RequirementClassification.REQUIRED.value
    return value if value in {item.value for item in RequirementClassification} else RequirementClassification.CONTEXTUAL.value


def _terms(requirement: JsonObject) -> list[str]:
    raw = _item(requirement, "normalized_terms")
    if isinstance(raw, list) and raw:
        return sorted({_normal_text(item) for item in raw if _normal_text(item)})
    return _terms_for(_item(requirement, "concept") or _item(requirement, "source_text") or "")


def _terms_for(value: Any) -> list[str]:
    text = _normal_text(value)
    if not text:
        return []
    terms = set(_domain_terms(text))
    years = _extract_years(text)
    if years:
        terms.add(_normal_text(years))
    terms.update(part for part in text.split() if _specific_term(part))
    if not terms and len(text) > 1:
        terms.add(text)
    return sorted(terms)


def _domain_terms(text: str) -> list[str]:
    normalized = _normal_text(text)
    terms: set[str] = set()
    for canonical, variants in _TERM_VARIANTS.items():
        if any(_term_in_text(variant, normalized) for variant in variants):
            terms.add(_normal_text(canonical))
            terms.update(_normal_text(variant) for variant in variants if _normal_text(variant))
    return sorted(terms)


def _specific_term(term: Any) -> bool:
    normalized = _normal_text(term)
    if not normalized or normalized in _GENERIC_TERMS:
        return False
    if " " in normalized:
        words = [word for word in normalized.split() if word not in _GENERIC_TERMS]
        return bool(words)
    return len(normalized) > 1


def _specific_terms(terms: list[str]) -> list[str]:
    expanded: set[str] = set()
    for term in terms:
        normalized = _normal_text(term)
        if not normalized:
            continue
        if normalized in _TERM_VARIANTS:
            expanded.add(normalized)
            expanded.update(_normal_text(item) for item in _TERM_VARIANTS[normalized])
            continue
        variant_group = _variant_group(normalized)
        if variant_group:
            expanded.add(_normal_text(variant_group[0]))
            expanded.update(_normal_text(item) for item in variant_group[1])
            continue
        if _specific_term(normalized):
            expanded.add(normalized)
    return sorted(expanded)


def _variant_group(term: str) -> tuple[str, tuple[str, ...]] | None:
    for canonical, variants in _TERM_VARIANTS.items():
        normalized_variants = {_normal_text(item) for item in variants}
        if term in normalized_variants:
            return canonical, variants
    return None


def _aliases_for_terms(terms: list[str], aliases: dict[str, set[str]]) -> list[str]:
    alias_terms: set[str] = set()
    for term in _specific_terms(terms):
        alias_terms.update(_item(aliases, term, set()))
    return sorted(term for term in alias_terms if _specific_term(term))


def _matched_terms(terms: list[str], text: str) -> list[str]:
    return sorted({term for term in _specific_terms(terms) if _term_in_text(term, text)})


def _terms_in_text(terms: list[str], text: str) -> bool:
    return any(_term_in_text(term, text) for term in _specific_terms(terms))


def _term_in_text(term: Any, text: str) -> bool:
    normalized = _normal_text(term)
    normalized_text = _normal_text(text)
    if not normalized or not normalized_text:
        return False
    if " " in normalized:
        return normalized in normalized_text
    words = normalized_text.split()
    return normalized in words or f"{normalized}s" in words or (normalized.endswith("s") and normalized[:-1] in words)


def _alias_map(config: JsonObject) -> dict[str, set[str]]:
    raw = _item(config, "aliases", _item(config, "alias_map", {}))
    aliases: dict[str, set[str]] = {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            alias_values = value if isinstance(value, list) else [value]
            aliases[_normal_text(key)] = {_normal_text(item) for item in alias_values if _normal_text(item)}
    return aliases


def _minimum_required_years(value: Any) -> int | None:
    matches = _YEARS_RE.findall(str(value))
    if not matches:
        return None
    raw = matches[0].lower()
    if raw.isdigit():
        return int(raw)
    return _NUMBER_WORDS.get(raw)


def _years_met(text: str, required_years: int) -> tuple[bool, int | None]:
    values = [_minimum_required_years(match.group(0)) for match in _YEARS_RE.finditer(str(text))]
    numeric_values = [value for value in values if value is not None]
    if not numeric_values:
        return False, None
    best = max(numeric_values)
    return best >= required_years, best


def _fact_resolution(
    terms: list[str],
    required_years: int | None,
    fact_index: dict[str, JsonObject],
    allow_inferred: bool,
) -> tuple[str | None, list[str], list[JsonObject]]:
    explicit_missing: list[str] = []
    verified: list[str] = []
    related: list[str] = []
    evidence: list[JsonObject] = []
    for fact_id, fact in sorted(fact_index.items()):
        fact_text = _fact_text(fact)
        if not _fact_relevant(terms, required_years, fact_text):
            continue
        state = str(_item(fact, "verification_state", VerificationState.UNKNOWN.value))
        fact_evidence = {"source": "career_fact", "fact_id": fact_id, "terms": _matched_terms(terms, fact_text)}
        if required_years is not None:
            met, matched_years = _years_met(fact_text, required_years)
            fact_evidence["required_years"] = required_years
            fact_evidence["matched_years"] = matched_years
            if not met:
                continue
        resolution_state = str(_item(fact, "resolution_state", ""))
        if resolution_state == ResolutionState.EXPLICITLY_MISSING.value:
            explicit_missing.append(fact_id)
            evidence.append({**fact_evidence, "resolution_state": ResolutionState.EXPLICITLY_MISSING.value})
        elif _fact_allowed(fact, allow_inferred):
            verified.append(fact_id)
            evidence.append(fact_evidence)
        elif resolution_state == ResolutionState.RELATED_MATCH.value:
            related.append(fact_id)
            evidence.append({**fact_evidence, "resolution_state": ResolutionState.RELATED_MATCH.value})
    if explicit_missing:
        return ResolutionState.EXPLICITLY_MISSING.value, explicit_missing, evidence
    if verified:
        return ResolutionState.VERIFIED_FACT_MATCH.value, verified, evidence
    if related:
        return ResolutionState.RELATED_MATCH.value, related, evidence
    return None, [], []


def _fact_relevant(terms: list[str], required_years: int | None, fact_text: str) -> bool:
    non_year_terms = [term for term in terms if _minimum_required_years(term) is None]
    if non_year_terms and _terms_in_text(non_year_terms, fact_text):
        return True
    return required_years is not None and _years_met(fact_text, required_years)[0]


def _related_terms_for(terms: list[str]) -> list[str]:
    related: set[str] = set()
    for term in _specific_terms(terms):
        related.update(_RELATED_REQUIREMENT_TERMS.get(term, ()))
    return sorted(related)


def _possible_terms(terms: list[str]) -> list[str]:
    possible: set[str] = set()
    for term in terms:
        for part in _normal_text(term).split():
            if _specific_term(part):
                possible.add(part)
    return sorted(possible - set(_specific_terms(terms)))


def _fact_index(facts: list[JsonObject]) -> dict[str, JsonObject]:
    index: dict[str, JsonObject] = {}
    for fact in facts:
        fact_id = _item(fact, "fact_id")
        if fact_id:
            index[str(fact_id)] = fact
    return index


def _fact_text(fact: JsonObject) -> str:
    pieces = [_item(fact, "text", "")]
    pieces.extend(_array(_item(fact, "normalized_terms", [])))
    for entry in _array(_item(fact, "evidence", [])):
        if isinstance(entry, dict):
            pieces.append(_item(entry, "text", ""))
    return _normal_text(" ".join(_text(item) for item in pieces))


def _fact_allowed(fact: JsonObject, allow_inferred: bool) -> bool:
    state = _item(fact, "verification_state", VerificationState.UNKNOWN.value)
    return state in _VERIFIED_FACT_STATES or (allow_inferred and state == VerificationState.INFERRED.value)


def _fact_matches(terms: list[str], fact_index: dict[str, JsonObject], allow_inferred: bool) -> list[str]:
    matches = []
    for fact_id, fact in sorted(fact_index.items()):
        if _fact_allowed(fact, allow_inferred) and _terms_in_text(terms, _fact_text(fact)):
            matches.append(fact_id)
    return matches


def _strict_policy(config: JsonObject) -> bool:
    return bool(_item(config, "require_hard_resolution") or _item(config, "policy") == "strict")


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _guarded_claims(text: str) -> set[str]:
    normalized = _normal_text(text)
    return {claim for claim, terms in _GUARDED_TERMS.items() if any(_term_in_text(term, normalized) for term in terms)}


def _claim_support(guarded: set[str], fact_index: dict[str, JsonObject], linked_fact_ids: list[str], allow_inferred: bool) -> dict[str, list[str]]:
    supported: dict[str, list[str]] = {}
    for claim in guarded:
        terms = _GUARDED_TERMS[claim]
        for fact_id in linked_fact_ids:
            fact = _item(fact_index, str(fact_id))
            if (
                isinstance(fact, dict)
                and _fact_allowed(fact, allow_inferred)
                and not _fact_negates_claim(claim, fact)
                and any(_term_in_text(term, _fact_text(fact)) for term in terms)
            ):
                if claim not in supported:
                    supported[claim] = []
                supported[claim].append(str(fact_id))
    return supported


def _fact_negates_claim(claim: str, fact: JsonObject) -> bool:
    text = _fact_text(fact)
    if claim == "staff_title" and any(phrase in text for phrase in ("not had staff", "haven t had staff", "not staff engineer", "not staff software engineer")):
        return True
    if any(phrase in text for phrase in ("no ", "not ", "never ", "haven t ", "hasn t ", "without ")):
        claim_terms = _GUARDED_TERMS.get(claim, ())
        return any(_term_in_text(term, text) for term in claim_terms)
    return False


def _title_inflation(path: str, before: Any, after: Any, support_by_claim: dict[str, list[str]]) -> bool:
    if not path.endswith("/title"):
        return False
    after_text = _normal_text(after)
    before_text = _normal_text(before)
    if "staff" not in after_text or "staff" in before_text:
        return False
    return not support_by_claim.get("staff_title")


def _years(text: str) -> list[str]:
    return [match.group(0).lower() for match in _YEARS_RE.finditer(text)]


def _extract_years(text: str) -> str | None:
    matches = _years(text)
    return matches[0] if matches else None


def _facts_support_terms(terms: list[str], fact_index: dict[str, JsonObject], linked_fact_ids: list[str], allow_inferred: bool) -> bool:
    for term in terms:
        for fact_id in linked_fact_ids:
            fact = _item(fact_index, str(fact_id))
            if isinstance(fact, dict) and _fact_allowed(fact, allow_inferred) and _term_in_text(term, _fact_text(fact)):
                return True
    return False


def _operation_path(operation: JsonObject) -> str:
    return str(_item(operation, "path") or _item(operation, "target_path") or "")


def _unresolved_copy(requirement_result: JsonObject) -> JsonObject:
    copied = copy.deepcopy(requirement_result)
    copied["resolution_state"] = str(_item(copied, "resolution_state", ResolutionState.UNKNOWN.value))
    copied["resolution_state_group"] = _resolution_group(copied["resolution_state"])
    copied["blocking"] = bool(_item(copied, "blocking", False))
    copied["unresolved"] = copied["resolution_state"] not in _RESOLVED
    return copied


def _rank_unresolved(requirements: list[JsonObject]) -> list[JsonObject]:
    unique: dict[str, JsonObject] = {}
    for item in requirements:
        requirement_id = str(_item(item, "requirement_id", ""))
        if requirement_id and requirement_id not in unique:
            unique[requirement_id] = item
    return sorted(
        unique.values(),
        key=lambda item: (
            0 if _item(item, "blocking") else 1,
            _classification_rank(str(_item(item, "classification", ""))),
            _resolution_rank(str(_item(item, "resolution_state", ""))),
            -_number(_item(item, "max_score", _item(item, "weight", 0.0)), 0.0),
            str(_item(item, "requirement_id", "")),
        ),
    )


def _classification_rank(value: str) -> int:
    return {
        RequirementClassification.REQUIRED.value: 0,
        RequirementClassification.PREFERRED.value: 1,
        RequirementClassification.CONTEXTUAL.value: 2,
    }.get(value, 3)


def _resolution_rank(value: str) -> int:
    return {
        ResolutionState.EXPLICITLY_MISSING.value: 0,
        ResolutionState.UNKNOWN.value: 1,
        ResolutionState.POSSIBLE_MATCH.value: 2,
        ResolutionState.RELATED_MATCH.value: 3,
    }.get(value, 4)


def _resolution_group(value: str) -> str:
    if value in _RESOLVED:
        return "resolved"
    if value == ResolutionState.RELATED_MATCH.value:
        return "related_not_resolved"
    if value == ResolutionState.POSSIBLE_MATCH.value:
        return "possible_not_resolved"
    if value == ResolutionState.EXPLICITLY_MISSING.value:
        return "missing"
    return "unknown"


def _missing_provenance(resume: JsonObject) -> list[JsonObject]:
    provenance = _array(_item(resume, "provenance", []))
    if provenance:
        return []
    claims = []
    for field_name in ("summary", "skills", "experience", "projects"):
        if _item(resume, field_name):
            claims.append({"field_path": field_name, "reason": "missing_provenance"})
    return claims


def _duplicate_warnings(resume: JsonObject) -> list[JsonObject]:
    warnings: list[JsonObject] = []
    seen: set[str] = set()
    for item in _array(_item(resume, "skills", [])):
        key = _normal_text(item)
        if key in seen:
            warnings.append(_issue("duplicate_skill", "Duplicate skill detected.", "skills"))
        seen.add(key)
    return warnings


def _keyword_warnings(resume: JsonObject) -> list[JsonObject]:
    warnings: list[JsonObject] = []
    words = _normal_text(_text(resume)).split()
    if not words:
        return warnings
    for word in sorted(set(words)):
        if len(word) > 2 and words.count(word) > max(8, len(words) // 5):
            warnings.append(_issue("possible_keyword_stuffing", "Repeated term detected.", "resume", {"term": word}))
            break
    return warnings


def _relevance(text: Any, terms: list[str]) -> int:
    normalized = _normal_text(text)
    return sum(1 for term in terms if _term_in_text(term, normalized))


def _empty_match() -> JsonObject:
    return {
        "schema_version": "match-result.v1",
        "match_id": "match_empty",
        "job_id": "",
        "resume_id": "",
        "score": 0.0,
        "max_score": 0.0,
        "requirement_results": [],
        "unresolved_requirement_ids": [],
        "can_continue": False,
        "algorithm_version": ALGORITHM_VERSION,
    }
