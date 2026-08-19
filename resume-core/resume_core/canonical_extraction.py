"""Build canonical resume input from source-backed extraction proposals."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .dates import date_key, is_present_date_sentinel
from .schemas import CANONICAL_RESUME_SCHEMA_VERSION, JsonObject, VerificationState, to_json_dict


SCHEMA_VERSION = "resume-core.v1"
_BASICS_KEYS = {
    "name",
    "email",
    "phone",
    "location",
    "address",
    "city",
    "region",
    "country",
    "postal_code",
    "website",
    "linkedin",
    "github",
    "portfolio",
}


def canonicalResumeFromExtraction(extraction: Any, source: JsonObject | None = None, config: JsonObject | None = None) -> JsonObject:
    """Construct canonical resume input from extraction proposals."""

    del config
    payload = to_json_dict(extraction)
    if not isinstance(payload, dict):
        return _result("error", canonical_resume={}, errors=[_issue("invalid_extraction", "extraction must be an object.")], warnings=[])
    if payload.get("status") == "error" or isinstance(payload.get("error"), dict):
        error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        message = str(error.get("message") or "resume extraction failed.")
        return _result(
            "error",
            canonical_resume={},
            errors=[_issue("resume_extraction_failed", message, "extraction", {"extraction_error": copy.deepcopy(error)})],
            warnings=[],
        )

    proposals = _fact_proposals(payload)
    if not proposals:
        return _result(
            "error",
            canonical_resume={},
            errors=[_issue("empty_resume_extraction", "resume extraction produced no fact proposals.", "fact_proposals")],
            warnings=[],
        )

    source_payload = _source_payload(payload, source)
    evidence_by_id = _evidence_by_id(payload)
    provenance: list[JsonObject] = []
    warnings: list[JsonObject] = []
    resume: JsonObject = {
        "schema_version": CANONICAL_RESUME_SCHEMA_VERSION,
        "resume_id": _resume_id(payload, source_payload, proposals),
        "source": source_payload,
        "basics": {},
        "contact": {},
        "experience": [],
        "skills": [],
        "education": [],
        "certifications": [],
        "projects": [],
        "provenance": provenance,
        "verification_state": VerificationState.SOURCE_STATED.value,
        "ingest_warnings": warnings,
        "metadata": {"extraction_schema_version": payload.get("schema_version"), "proposal_type": payload.get("proposal_type")},
    }
    provenance.extend(_source_evidence_entries(evidence_by_id))

    experience_by_key: dict[tuple[str, str], JsonObject] = {}
    for proposal in proposals:
        category = _clean_text(proposal.get("category")).lower()
        if not category:
            warnings.append(_issue("missing_proposal_category", "Ignored fact proposal without a category.", "fact_proposals"))
            continue
        _apply_proposal(resume, experience_by_key, proposal, category, evidence_by_id, warnings)

    resume["experience"] = list(experience_by_key.values())
    if not resume["contact"]:
        del resume["contact"]
    return _result("warning" if warnings else "ok", canonical_resume=resume, errors=[], warnings=warnings)


def _apply_proposal(
    resume: JsonObject,
    experience_by_key: dict[tuple[str, str], JsonObject],
    proposal: JsonObject,
    category: str,
    evidence_by_id: dict[str, JsonObject],
    warnings: list[JsonObject],
) -> None:
    if category in _BASICS_KEYS:
        _add_basic(resume, proposal, category, evidence_by_id)
    elif category in {"title", "headline"}:
        _add_field(resume, "title", proposal, evidence_by_id)
    elif category == "summary":
        _add_field(resume, "summary", proposal, evidence_by_id)
    elif category == "skill" or category.endswith("_skill"):
        _add_skill(resume, proposal, evidence_by_id)
    elif category == "experience":
        _add_experience(experience_by_key, proposal, evidence_by_id)
    elif category == "employment":
        _add_employment(experience_by_key, proposal, evidence_by_id)
    elif category == "experience_highlight":
        _add_highlight(experience_by_key, proposal, evidence_by_id)
    elif category in {"education", "certification", "project"}:
        _add_section_item(resume, category, proposal, evidence_by_id)
    else:
        warnings.append(_issue("unsupported_proposal_category", "Ignored unsupported fact proposal category.", f"category/{category}"))


def _fact_proposals(payload: JsonObject) -> list[JsonObject]:
    proposals = payload.get("fact_proposals", payload.get("proposals", []))
    return [item for item in proposals if isinstance(item, dict)]


def _add_basic(resume: JsonObject, proposal: JsonObject, category: str, evidence_by_id: dict[str, JsonObject]) -> None:
    field = _field(proposal, f"basics/{category}", evidence_by_id)
    if not field:
        return
    resume["basics"][category] = field
    if category in {"name", "email", "phone", "website", "linkedin", "github", "portfolio"}:
        resume["contact"][category] = field["value"]


def _add_field(resume: JsonObject, field_name: str, proposal: JsonObject, evidence_by_id: dict[str, JsonObject]) -> None:
    field = _field(proposal, field_name, evidence_by_id)
    if field:
        resume[field_name] = field


def _add_skill(resume: JsonObject, proposal: JsonObject, evidence_by_id: dict[str, JsonObject]) -> None:
    field = _field(proposal, f"skills/{len(resume['skills'])}", evidence_by_id)
    if not field:
        return
    if proposal.get("skill_category") is not None:
        field["category"] = proposal.get("skill_category")
    resume["skills"].append(field)


def _add_experience(experience_by_key: dict[tuple[str, str], JsonObject], proposal: JsonObject, evidence_by_id: dict[str, JsonObject]) -> None:
    entry = _experience_entry(proposal, len(experience_by_key), evidence_by_id)
    if entry:
        experience_by_key[_experience_key(entry)] = entry


def _add_employment(experience_by_key: dict[tuple[str, str], JsonObject], proposal: JsonObject, evidence_by_id: dict[str, JsonObject]) -> None:
    entry = _employment_entry(proposal, len(experience_by_key), evidence_by_id)
    if not entry:
        return
    key = _experience_key(entry)
    existing = experience_by_key.get(key)
    if existing:
        existing.update({field: value for field, value in entry.items() if field not in {"bullets"} and value is not None})
    else:
        experience_by_key[key] = entry


def _add_highlight(experience_by_key: dict[tuple[str, str], JsonObject], proposal: JsonObject, evidence_by_id: dict[str, JsonObject]) -> None:
    field = _field(proposal, "experience_highlight", evidence_by_id)
    if not field:
        return
    entry = _highlight_entry(experience_by_key, len(experience_by_key))
    field["claim_id"] = _claim_id(f"{entry['id']}/bullets/{len(entry['bullets'])}", proposal)
    entry.setdefault("bullets", []).append(field)


def _add_section_item(resume: JsonObject, category: str, proposal: JsonObject, evidence_by_id: dict[str, JsonObject]) -> None:
    key_by_category = {"education": "education", "certification": "certifications", "project": "projects"}
    prefix_by_category = {"education": "edu", "certification": "cert", "project": "project"}
    key = key_by_category[category]
    item = _section_item(proposal, category, prefix_by_category[category], len(resume[key]), evidence_by_id)
    if item:
        resume[key].append(item)


def _source_payload(payload: JsonObject, source: JsonObject | None) -> JsonObject:
    result = copy.deepcopy(source) if isinstance(source, dict) else {}
    extracted_source = payload.get("source")
    if isinstance(extracted_source, dict):
        result.setdefault("extraction_source", copy.deepcopy(extracted_source))
    result.setdefault("kind", "extraction")
    return result


def _evidence_by_id(payload: JsonObject) -> dict[str, JsonObject]:
    evidence: dict[str, JsonObject] = {}
    for item in payload.get("source_evidence", []):
        if isinstance(item, dict):
            evidence_id = _clean_text(item.get("evidence_id"))
            if evidence_id:
                evidence[evidence_id] = copy.deepcopy(item)
    for proposal in _fact_proposals(payload):
        for item in proposal.get("evidence", []):
            if isinstance(item, dict):
                evidence_id = _clean_text(item.get("evidence_id"))
                if evidence_id:
                    evidence.setdefault(evidence_id, copy.deepcopy(item))
    return evidence


def _field(proposal: JsonObject, path: str, evidence_by_id: dict[str, JsonObject]) -> JsonObject:
    text = _clean_text(proposal.get("text"))
    if not text:
        return {}
    claim_id = _claim_id(path, proposal)
    field: JsonObject = {
        "value": text,
        "claim_id": claim_id,
        "provenance": _provenance_entries(proposal, claim_id, evidence_by_id),
        "verification_state": VerificationState.SOURCE_STATED.value,
    }
    if proposal.get("normalized_terms"):
        field["normalized_terms"] = [str(term) for term in proposal.get("normalized_terms", []) if _clean_text(term)]
    return field


def _experience_entry(
    proposal: JsonObject,
    index: int,
    evidence_by_id: dict[str, JsonObject],
) -> JsonObject:
    text = _clean_text(proposal.get("text"))
    employment = proposal.get("employment") if isinstance(proposal.get("employment"), dict) else {}
    organization = _clean_text(employment.get("organization"))
    role = _clean_text(employment.get("role"))
    entry: JsonObject = {
        "id": _proposal_id("exp", index, proposal),
        "bullets": [],
    }
    if organization:
        entry["company"] = _field_from_text(organization, proposal, f"experience/{index}/company", evidence_by_id)
    if role:
        entry["title"] = _field_from_text(role, proposal, f"experience/{index}/title", evidence_by_id)
    _assign_dates(entry, proposal, employment)
    if text and (text != " at ".join(part for part in [role, organization] if part) or not (role or organization)):
        entry["bullets"].append(_field(proposal, f"experience/{index}/bullets/0", evidence_by_id))
    return entry if entry.get("company") or entry.get("title") or entry.get("bullets") or entry.get("start_date") or entry.get("end_date") else {}


def _employment_entry(
    proposal: JsonObject,
    index: int,
    evidence_by_id: dict[str, JsonObject],
) -> JsonObject:
    text = _clean_text(proposal.get("text"))
    terms = [_clean_text(term) for term in proposal.get("normalized_terms", []) if _clean_text(term)]
    role = terms[0] if terms else ""
    organization = terms[1] if len(terms) > 1 else ""
    if " at " in text and not (role and organization):
        role, organization = [part.strip() for part in text.split(" at ", 1)]
    entry: JsonObject = {"id": _proposal_id("exp", index, proposal), "bullets": []}
    if organization:
        entry["company"] = _field_from_text(organization, proposal, f"experience/{index}/company", evidence_by_id)
    if role:
        entry["title"] = _field_from_text(role, proposal, f"experience/{index}/title", evidence_by_id)
    _assign_dates(entry, proposal, proposal)
    return entry if entry.get("company") or entry.get("title") or entry.get("start_date") or entry.get("end_date") else {}


def _field_from_text(
    value: str,
    proposal: JsonObject,
    path: str,
    evidence_by_id: dict[str, JsonObject],
) -> JsonObject:
    claim_id = _claim_id(path, {"fact_id": proposal.get("fact_id"), "text": value})
    field = {
        "value": value,
        "claim_id": claim_id,
        "provenance": _provenance_entries(proposal, claim_id, evidence_by_id),
        "verification_state": VerificationState.SOURCE_STATED.value,
    }
    return field


def _section_item(
    proposal: JsonObject,
    category: str,
    prefix: str,
    index: int,
    evidence_by_id: dict[str, JsonObject],
) -> JsonObject:
    item: JsonObject = {"id": _proposal_id(prefix, index, proposal)}
    terms = [_clean_text(term) for term in proposal.get("normalized_terms", []) if _clean_text(term)]
    if category == "education" and terms:
        if len(terms) >= 1:
            item["degree"] = _field_from_text(terms[0], proposal, f"{prefix}/{index}/degree", evidence_by_id)
        if len(terms) >= 2:
            item["field"] = _field_from_text(terms[1], proposal, f"{prefix}/{index}/field", evidence_by_id)
    elif category == "certification" and terms:
        item["credential"] = _field_from_text(terms[0], proposal, f"{prefix}/{index}/credential", evidence_by_id)
        if len(terms) >= 2:
            item["issuer"] = _field_from_text(terms[1], proposal, f"{prefix}/{index}/issuer", evidence_by_id)
    elif category == "project" and terms:
        item["title"] = _field_from_text(_clean_text(proposal.get("text")), proposal, f"{prefix}/{index}/title", evidence_by_id)
        item["skills"] = [_field_from_text(term, proposal, f"{prefix}/{index}/skills/{term_index}", evidence_by_id) for term_index, term in enumerate(terms)]
    else:
        item["description"] = _field(proposal, f"{prefix}/{index}/description", evidence_by_id)
    return item if any(key != "id" and _has_content(value) for key, value in item.items()) else {}


def _highlight_entry(experience_by_key: dict[tuple[str, str], JsonObject], index: int) -> JsonObject:
    if experience_by_key:
        return next(reversed(experience_by_key.values()))
    entry: JsonObject = {"id": f"exp_{index + 1}", "bullets": []}
    experience_by_key[("", "")] = entry
    return entry


def _assign_dates(entry: JsonObject, proposal: JsonObject, values: JsonObject) -> None:
    start_date = _canonical_date(values.get("start_date"))
    end_date = _canonical_date(values.get("end_date"))
    if start_date:
        entry["start_date"] = start_date
    if end_date:
        entry["end_date"] = end_date
    elif values.get("current") is True:
        entry["end_date"] = "present"
    elif proposal.get("current") is True:
        entry["end_date"] = "present"


def _canonical_date(value: Any) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    if is_present_date_sentinel(value):
        return str(value).strip().lower()
    result = date_key(value)
    return result.canonical or str(value).strip()


def _provenance_entries(proposal: JsonObject, claim_id: str, evidence_by_id: dict[str, JsonObject]) -> list[JsonObject]:
    entries: list[JsonObject] = []
    for evidence_id in proposal.get("source_evidence_ids", []):
        evidence = evidence_by_id.get(str(evidence_id))
        if not evidence:
            continue
        text = _clean_text(evidence.get("text") or evidence.get("source_text") or evidence.get("snippet"))
        if not text:
            continue
        entry: JsonObject = {
            "claim_id": claim_id,
            "source": "resume",
            "text": text,
            "evidence_id": str(evidence_id),
            "verification_state": VerificationState.SOURCE_STATED.value,
        }
        if evidence.get("span") is not None:
            entry["source_span"] = copy.deepcopy(evidence.get("span"))
        if evidence.get("lines") is not None:
            entry["lines"] = copy.deepcopy(evidence.get("lines"))
        entries.append(entry)
    return entries


def _source_evidence_entries(evidence_by_id: dict[str, JsonObject]) -> list[JsonObject]:
    entries: list[JsonObject] = []
    for evidence_id in sorted(evidence_by_id):
        evidence = evidence_by_id[evidence_id]
        text = _clean_text(evidence.get("text") or evidence.get("source_text") or evidence.get("snippet"))
        if not text:
            continue
        entry: JsonObject = {"source": "resume", "text": text, "evidence_id": evidence_id}
        if evidence.get("span") is not None:
            entry["source_span"] = copy.deepcopy(evidence.get("span"))
        if evidence.get("lines") is not None:
            entry["lines"] = copy.deepcopy(evidence.get("lines"))
        entries.append(entry)
    return entries


def _experience_key(entry: JsonObject) -> tuple[str, str]:
    return (_field_text(entry.get("company")), _field_text(entry.get("title")))


def _field_text(value: Any) -> str:
    if isinstance(value, dict) and "value" in value:
        return _clean_text(value.get("value")).lower()
    return _clean_text(value).lower()


def _has_content(value: Any) -> bool:
    if isinstance(value, dict) and "value" in value:
        return _has_content(value.get("value"))
    if isinstance(value, dict):
        return any(_has_content(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_content(item) for item in value)
    return _clean_text(value) != ""


def _resume_id(payload: JsonObject, source: JsonObject, proposals: list[JsonObject]) -> str:
    explicit = _clean_text(payload.get("resume_id"))
    if explicit:
        return explicit
    source_id = _clean_text(source.get("source_id") or source.get("path"))
    if source_id:
        return _stable_id("resume", source_id)
    return _stable_id("resume", proposals)


def _proposal_id(prefix: str, index: int, proposal: JsonObject) -> str:
    explicit = _clean_text(proposal.get("fact_id"))
    if explicit:
        return explicit.replace("fact_", f"{prefix}_", 1) if explicit.startswith("fact_") else f"{prefix}_{explicit}"
    return f"{prefix}_{index + 1}"


def _claim_id(path: str, proposal: JsonObject) -> str:
    explicit = _clean_text(proposal.get("fact_id"))
    if explicit:
        return explicit
    return _stable_id("claim", {"path": path, "text": proposal.get("text")})


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _stable_id(prefix: str, value: Any) -> str:
    material = json.dumps(to_json_dict(value), sort_keys=True, separators=(",", ":"), default=str)
    return f"{prefix}_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:12]}"


def _result(status: str, **fields: Any) -> JsonObject:
    return {"schema_version": SCHEMA_VERSION, "status": status, **to_json_dict(fields)}


def _issue(code: str, message: str, field_path: str | None = None, details: JsonObject | None = None) -> JsonObject:
    issue: JsonObject = {"code": code, "message": message, "severity": "error"}
    if field_path is not None:
        issue["field_path"] = field_path
    if details:
        issue["details"] = details
    return issue
