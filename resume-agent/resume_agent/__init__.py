"""Public proposal surface for resume-agent.

Extraction, clarification-question, and answer-interpretation confidence and
uncertainty are adapter-sourced. Rewrite helpers remain deterministic
placeholders until RKIT-I-0019 adapter backing lands; any confidence they emit is
explicitly marked unscored.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from ._adapters import ModelAdapter
from ._agent_config import (
    AGENT_CONFIG_DEFAULTS,
    AGENT_CONFIG_SCHEMA,
    AgentConfig,
    AgentConfigResult,
    AgentConfigValidationError,
    require_agent_config,
    resolve_agent_config,
    stable_agent_config_hash,
)
from ._extraction_requests import build_job_extraction_request, build_resume_extraction_request
from ._fake_adapter import DeterministicFakeAdapter
from ._interview_requests import build_answer_interpretation_request, build_question_request


SCHEMA_VERSION = "resume-agent.proposal.v1"

_TERM_SUPPORT_VARIANTS = {
    "api architecture": ("api architecture", "api design", "rest api design", "rest apis"),
    "responsive design": ("responsive design", "responsive web applications", "responsive web apps"),
    "technical leadership": ("technical leadership", "team leadership", "led a small team", "code review", "delivery planning"),
    "leadership": ("leadership", "team leadership", "led a small team", "code review", "delivery planning"),
    "node.js": ("node", "node js", "nodejs"),
    "postgresql": ("postgres", "postgresql"),
}

__all__ = [
    "AGENT_CONFIG_DEFAULTS",
    "AGENT_CONFIG_SCHEMA",
    "AgentConfig",
    "AgentConfigResult",
    "AgentConfigValidationError",
    "extractResumeSemantics",
    "extractJobSemantics",
    "generateClarificationQuestion",
    "interpretUserAnswer",
    "proposeRewrite",
    "require_agent_config",
    "resolve_agent_config",
    "stable_agent_config_hash",
]


def _base(proposal_type: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "proposal_type": proposal_type,
        "proposals": [],
        "uncertainty": [],
        "requires_validation": True,
    }


def _error(kind: str, message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "error": {
            "type": kind,
            "message": message,
        },
    }


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _match_text(value: Any) -> str:
    return " ".join("".join(char if char.isalnum() else " " for char in str(value).casefold()).split())


def _term_in_text(term: str, text: str) -> bool:
    needle = _match_text(term)
    return bool(needle and f" {needle} " in f" {_match_text(text)} ")


def _stable_id(prefix: str, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def _evidence(text: str, snippet: str, prefix: str) -> dict[str, Any]:
    start = text.lower().find(snippet.lower())
    end = start + len(snippet) if start >= 0 else None
    evidence_key = f"{start}:{snippet}" if start >= 0 else snippet
    return {
        "evidence_id": _stable_id(prefix, evidence_key),
        "text": snippet,
        "snippet": snippet,
        "span": {"start": start if start >= 0 else None, "end": end},
    }


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        cleaned = _clean_text(value)
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            unique_values.append(cleaned)
    return unique_values


def _safe_topic(value: Any) -> str:
    return _clean_text(value)


def _selected_ids(context: dict[str, Any]) -> list[str]:
    selected = context.get("selected_requirement_ids", [])
    if not isinstance(selected, list):
        return []
    return [str(item) for item in selected if _clean_text(str(item))]


def _selected_fact_ids(context: dict[str, Any]) -> list[str]:
    target_ids = context.get("target_ids")
    if isinstance(target_ids, dict):
        explicit = target_ids.get("fact_ids", [])
    else:
        explicit = context.get("target_fact_ids", context.get("selected_fact_ids", []))
    if not isinstance(explicit, list):
        return []
    return [str(item) for item in explicit if _clean_text(str(item))]


def _context_snippets(context: dict[str, Any]) -> list[str]:
    snippets = context.get("context_snippets", [])
    if not isinstance(snippets, list):
        return []
    return [_clean_text(str(item)) for item in snippets if _clean_text(str(item))]


def _is_blocked(value: str, blocked: list[str]) -> bool:
    lowered = value.lower()
    return any(item and item.lower() in lowered for item in blocked)


def extractResumeSemantics(rawText: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract source-backed semantic proposals from plain resume text."""

    if not _clean_text(rawText):
        return _error("validation_error", "rawText must be a non-empty string.")

    ctx = context if isinstance(context, dict) else {}
    try:
        adapter = _resume_extraction_adapter(ctx)
        request = build_resume_extraction_request(rawText, source_id=_resume_source_id(ctx))
    except AgentConfigValidationError as exc:
        return {"status": "error", "error": {"type": "schema_error", "message": str(exc), "violations": exc.errors}}

    completion = adapter.complete(request)
    if completion.status != "ok":
        return _adapter_error(completion)
    payload = completion.payload or {}
    return _resume_extraction_payload_to_proposals(payload)


def _resume_extraction_adapter(context: dict[str, Any]) -> ModelAdapter:
    injected = context.get("_adapter")
    if injected is not None:
        return injected
    return DeterministicFakeAdapter(agent_config=require_agent_config(context))


def _resume_source_id(context: dict[str, Any]) -> str:
    explicit = _clean_text(context.get("source_id"))
    if explicit:
        return explicit
    source_path = _clean_text(context.get("source_path"))
    if source_path:
        return Path(source_path).name or "inline"
    return "inline"


def _adapter_error(completion: Any) -> dict[str, Any]:
    error = completion.error.to_error() if getattr(completion, "error", None) is not None else {
        "type": "provider_error",
        "message": "Adapter failed without a structured error.",
    }
    result = {"status": "error", "error": error}
    for field in ["adapter_id", "adapter_version", "model_id", "runtime_config", "retries", "usage"]:
        if hasattr(completion, field):
            result[field] = getattr(completion, field)
    return result


def _resume_extraction_payload_to_proposals(payload: dict[str, Any]) -> dict[str, Any]:
    result = _base("resume_semantic_extraction")
    source_evidence = _dedupe_evidence([_model_evidence_to_source(item) for item in payload.get("source_evidence", [])])
    facts: list[dict[str, Any]] = []

    for key, item in (payload.get("basics") or {}).items():
        if isinstance(item, dict):
            _append_model_fact(facts, str(key), _clean_text(item.get("value")), [_clean_text(item.get("normalized"))], item)

    for item in payload.get("skills", []):
        if isinstance(item, dict):
            terms = [str(term) for term in item.get("normalized_terms", []) if _clean_text(term)]
            _append_model_fact(facts, "skill", _clean_text(item.get("name")), terms, item, {"skill_category": item.get("category")})

    for item in payload.get("experience", []):
        if not isinstance(item, dict):
            continue
        role = _clean_text(item.get("role"))
        organization = _clean_text(item.get("organization"))
        text = " at ".join(part for part in [role, organization] if part)
        _append_model_fact(
            facts,
            "experience",
            text,
            [role, organization, *[str(skill) for skill in item.get("skills", []) if _clean_text(skill)]],
            item,
            {"employment": item.get("employment")},
        )
        for highlight in item.get("highlights", []):
            if isinstance(highlight, dict):
                _append_model_fact(
                    facts,
                    "experience_highlight",
                    _clean_text(highlight.get("text")),
                    [str(term) for term in highlight.get("normalized_terms", []) if _clean_text(term)],
                    highlight,
                )

    for item in payload.get("education", []):
        if isinstance(item, dict):
            text = ", ".join(_clean_text(item.get(key)) for key in ["degree", "field", "institution"] if _clean_text(item.get(key)))
            _append_model_fact(facts, "education", text, [_clean_text(item.get("degree")), _clean_text(item.get("field"))], item)

    for item in payload.get("certifications", []):
        if isinstance(item, dict):
            text = ", ".join(_clean_text(item.get(key)) for key in ["name", "issuer"] if _clean_text(item.get(key)))
            _append_model_fact(facts, "certification", text, [_clean_text(item.get("name")), _clean_text(item.get("issuer"))], item)

    for item in payload.get("projects", []):
        if isinstance(item, dict):
            text = ": ".join(part for part in [_clean_text(item.get("name")), _clean_text(item.get("description"))] if part)
            _append_model_fact(
                facts,
                "project",
                text,
                [str(skill) for skill in item.get("skills", []) if _clean_text(skill)],
                item,
            )

    for item in payload.get("employment", []):
        if isinstance(item, dict):
            text = " at ".join(_clean_text(item.get(key)) for key in ["role", "organization"] if _clean_text(item.get(key)))
            _append_model_fact(
                facts,
                "employment",
                text,
                [_clean_text(item.get("role")), _clean_text(item.get("organization"))],
                item,
                {
                    "start_date": item.get("start_date"),
                    "end_date": item.get("end_date"),
                    "current": item.get("current"),
                },
            )

    for fact in facts:
        source_evidence.extend(_model_evidence_to_source(item) for item in fact.get("evidence", []))
    source_evidence = _dedupe_evidence(source_evidence)

    result.update(
        {
            "proposals": facts,
            "fact_proposals": facts,
            "source_evidence": source_evidence,
            "uncertainty": payload.get("uncertainty", []),
            "model_metadata": payload.get("metadata", {}),
        }
    )
    return result


def _append_model_fact(
    facts: list[dict[str, Any]],
    category: str,
    text: str,
    terms: list[str],
    item: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> None:
    cleaned = _clean_text(text)
    evidence = [_model_evidence_to_source(entry) for entry in item.get("evidence", []) if isinstance(entry, dict)]
    evidence = [entry for entry in evidence if _clean_text(entry.get("evidence_id"))]
    if not cleaned or not evidence:
        return
    confidence = item.get("confidence")
    proposal = {
        "fact_id": _stable_id("fact", f"{category}:{cleaned}"),
        "category": category,
        "text": cleaned,
        "normalized_terms": _unique([term for term in terms if _clean_text(term)] or [cleaned.lower()]),
        "source_evidence_ids": [str(entry["evidence_id"]) for entry in evidence],
        "evidence": evidence,
        "verification_state": "inferred",
        "confidence": confidence,
        "model_confidence": confidence,
        "review_required": True,
    }
    if extra:
        proposal.update({key: value for key, value in extra.items() if value is not None})
    _copy_model_uncertainty(proposal, item)
    facts.append(proposal)


def _model_evidence_to_source(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    source_text = _clean_text(item.get("source_text") or item.get("text") or item.get("snippet"))
    evidence_id = _clean_text(item.get("evidence_id"))
    return {
        "evidence_id": evidence_id,
        "text": source_text,
        "snippet": source_text,
        "source_text": source_text,
        "span": item.get("span"),
        "lines": item.get("lines"),
    }


def _dedupe_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        evidence_id = _clean_text(item.get("evidence_id"))
        if not evidence_id or evidence_id in seen:
            continue
        seen.add(evidence_id)
        deduped.append(item)
    return deduped


def extractJobSemantics(rawJobText: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract job semantics as proposal data for downstream validation."""

    if not _clean_text(rawJobText):
        return _error("validation_error", "rawJobText must be a non-empty string.")

    ctx = context if isinstance(context, dict) else {}
    try:
        adapter = _job_extraction_adapter(ctx)
        request = build_job_extraction_request(rawJobText, source_id=_job_source_id(ctx))
    except AgentConfigValidationError as exc:
        return {"status": "error", "error": {"type": "schema_error", "message": str(exc), "violations": exc.errors}}

    completion = adapter.complete(request)
    if completion.status != "ok":
        return _adapter_error(completion)
    payload = completion.payload or {}
    return _job_extraction_payload_to_proposals(payload)


def _job_extraction_adapter(context: dict[str, Any]) -> ModelAdapter:
    injected = context.get("_adapter")
    if injected is not None:
        return injected
    return DeterministicFakeAdapter(agent_config=require_agent_config(context))


def _job_source_id(context: dict[str, Any]) -> str:
    return _resume_source_id(context)


def _job_extraction_payload_to_proposals(payload: dict[str, Any]) -> dict[str, Any]:
    result = _base("job_semantic_extraction")
    required = [_model_requirement_to_proposal(item) for item in payload.get("requirements", []) if isinstance(item, dict)]
    preferred = [_model_requirement_to_proposal(item) for item in payload.get("preferred", []) if isinstance(item, dict)]
    requirements = [item for item in [*required, *preferred] if item]
    classification_proposals = [_requirement_classification_proposal(item) for item in requirements]
    source_evidence = _job_source_evidence(payload, requirements)
    terminology = [_model_term_to_proposal(item) for item in payload.get("terminology", []) if isinstance(item, dict)]
    terminology = [item for item in terminology if item]
    result.update(
        {
            "job_id": payload.get("job_id"),
            "source": payload.get("source", {}),
            "title": payload.get("title"),
            "job_title": _extracted_value(payload.get("title")),
            "company": _extracted_value(payload.get("company")),
            "company_proposal": payload.get("company"),
            "seniority": payload.get("seniority", []),
            "industries": payload.get("industries", []),
            "domains": payload.get("domains", []),
            "requirements": required,
            "preferred": preferred,
            "requirement_proposals": requirements,
            "requirement_classification_proposals": classification_proposals,
            "terminology": terminology,
            "source_evidence": source_evidence,
            "uncertainty": payload.get("uncertainty", []),
            "model_metadata": payload.get("metadata", {}),
            "proposals": requirements,
        }
    )
    return result


def _model_requirement_to_proposal(item: dict[str, Any]) -> dict[str, Any]:
    evidence = [_model_evidence_to_source(entry) for entry in item.get("evidence", []) if isinstance(entry, dict)]
    evidence = [entry for entry in evidence if _clean_text(entry.get("evidence_id"))]
    requirement_id = _clean_text(item.get("requirement_id"))
    source_text = _clean_text(item.get("source_text") or item.get("concept"))
    if not requirement_id or not source_text or not evidence:
        return {}
    confidence = item.get("confidence")
    proposal = {
        "requirement_id": requirement_id,
        "classification": item.get("classification"),
        "concept": _clean_text(item.get("concept")) or source_text,
        "importance": item.get("importance"),
        "weight": item.get("weight"),
        "source_text": source_text,
        "normalized_terms": _unique([str(term) for term in item.get("normalized_terms", []) if _clean_text(term)]),
        "years": item.get("years"),
        "seniority": item.get("seniority", []),
        "industries": item.get("industries", []),
        "domains": item.get("domains", []),
        "source_evidence_ids": [str(entry["evidence_id"]) for entry in evidence],
        "evidence": evidence,
        "confidence": confidence,
        "model_confidence": confidence,
        "review_required": True,
    }
    _copy_model_uncertainty(proposal, item)
    return proposal


def _requirement_classification_proposal(requirement: dict[str, Any]) -> dict[str, Any]:
    confidence = requirement.get("model_confidence")
    proposal = {
        "proposal_id": _stable_id(
            "req_class",
            ":".join(
                [
                    _clean_text(requirement.get("requirement_id")),
                    _clean_text(requirement.get("classification")),
                    _clean_text(requirement.get("source_text")),
                ]
            ),
        ),
        "requirement_id": requirement.get("requirement_id"),
        "classification": requirement.get("classification"),
        "source_text": requirement.get("source_text"),
        "source_evidence_ids": requirement.get("source_evidence_ids", []),
        "evidence": requirement.get("evidence", []),
        "confidence": confidence,
        "model_confidence": confidence,
        "requires_validation": True,
    }
    _copy_model_uncertainty(proposal, requirement)
    return proposal


def _model_term_to_proposal(item: dict[str, Any]) -> dict[str, Any]:
    evidence = [_model_evidence_to_source(entry) for entry in item.get("evidence", []) if isinstance(entry, dict)]
    evidence = [entry for entry in evidence if _clean_text(entry.get("evidence_id"))]
    surface = _clean_text(item.get("surface"))
    canonical = _clean_text(item.get("canonical"))
    if not surface or not canonical or not evidence:
        return {}
    confidence = item.get("confidence")
    proposal = {
        "surface": surface,
        "canonical": canonical,
        "source": item.get("source"),
        "weight": item.get("weight"),
        "evidence": evidence,
        "source_evidence_ids": [str(entry["evidence_id"]) for entry in evidence],
        "confidence": confidence,
        "model_confidence": confidence,
    }
    _copy_model_uncertainty(proposal, item)
    return proposal


def _copy_model_uncertainty(proposal: dict[str, Any], item: dict[str, Any]) -> None:
    if "uncertainty" in item:
        proposal["uncertainty"] = item["uncertainty"]


def _job_source_evidence(payload: dict[str, Any], requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence = [_model_evidence_to_source(item) for item in payload.get("source_evidence", []) if isinstance(item, dict)]
    for field in ["title", "company"]:
        value = payload.get(field)
        if isinstance(value, dict):
            evidence.extend(_model_evidence_to_source(item) for item in value.get("evidence", []) if isinstance(item, dict))
    for field in ["seniority", "industries", "domains"]:
        for item in payload.get(field, []):
            if isinstance(item, dict):
                evidence.extend(_model_evidence_to_source(entry) for entry in item.get("evidence", []) if isinstance(entry, dict))
    for requirement in requirements:
        evidence.extend(requirement.get("evidence", []))
        for field in ["seniority", "industries", "domains"]:
            for item in requirement.get(field, []):
                if isinstance(item, dict):
                    evidence.extend(_model_evidence_to_source(entry) for entry in item.get("evidence", []) if isinstance(entry, dict))
    return _dedupe_evidence(evidence)


def _extracted_value(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    value = _clean_text(item.get("value"))
    return value or None


def generateClarificationQuestion(context: dict[str, Any]) -> dict[str, Any]:
    """Phrase a targeted question for a code-selected topic."""

    if not isinstance(context, dict):
        return _error("schema_error", "context must be an object.")

    selected = _selected_ids(context)
    topic = _safe_topic(context.get("topic"))
    if not selected or not topic:
        return _error("validation_error", "context must include requirement IDs and a topic.")

    already = context.get("already_verified_fact_ids", [])
    if not isinstance(already, list):
        already = []
    verified_ids = {str(item) for item in already if _clean_text(str(item))}

    fact_targets = _selected_fact_ids(context)
    filtered_requirement_ids = [requirement_id for requirement_id in selected if requirement_id not in verified_ids]
    filtered_fact_ids = [fact_id for fact_id in fact_targets if fact_id not in verified_ids]
    if fact_targets and not filtered_fact_ids:
        result = _base("clarification_question")
        result.update(
            {
                "status": "ok",
                "question_needed": False,
                "selected_requirement_ids": filtered_requirement_ids,
                "target_ids": {"requirement_ids": filtered_requirement_ids, "fact_ids": []},
                "target_fact_ids": [],
                "topic": topic,
                "already_verified_fact_ids": [str(item) for item in already],
                "rationale": "All selected fact targets are already verified.",
            }
        )
        return result

    target_ids = {"requirement_ids": filtered_requirement_ids, "fact_ids": filtered_fact_ids}
    try:
        request = build_question_request(topic, target_ids, _context_snippets(context))
        adapter = _question_generation_adapter(context)
    except AgentConfigValidationError as exc:
        return {"status": "error", "error": {"type": "schema_error", "message": str(exc), "violations": exc.errors}}

    completion = adapter.complete(request)
    if completion.status != "ok":
        return _adapter_error(completion)

    payload = completion.payload or {}
    question = _clean_text(payload.get("question"))
    payload_targets = payload.get("target_ids") if isinstance(payload.get("target_ids"), dict) else target_ids
    question_id = _stable_id("question", f"{topic}:{payload_targets}:{question}")
    result = _base("clarification_question")
    result.update(
        {
            "status": "ok",
            "question_needed": True,
            "proposals": [
                {
                    "proposal_id": question_id,
                    "question_id": question_id,
                    "question": question,
                    "selected_requirement_ids": list(payload_targets.get("requirement_ids", [])),
                    "target_ids": payload_targets,
                    "topic": topic,
                    "rationale": payload.get("rationale"),
                    "requires_validation": payload.get("requires_validation", True),
                    "confidence": payload.get("confidence"),
                }
            ],
            "question_id": question_id,
            "question": question,
            "selected_requirement_ids": list(payload_targets.get("requirement_ids", [])),
            "target_ids": payload_targets,
            "target_fact_ids": list(payload_targets.get("fact_ids", [])),
            "topic": topic,
            "already_verified_fact_ids": [str(item) for item in already],
            "rationale": payload.get("rationale"),
            "confidence": payload.get("confidence"),
        }
    )
    return result


def _question_generation_adapter(context: dict[str, Any]) -> ModelAdapter:
    injected = context.get("_adapter")
    if injected is not None:
        return injected
    return DeterministicFakeAdapter(agent_config=require_agent_config(context))


def interpretUserAnswer(answer: str, context: dict[str, Any]) -> dict[str, Any]:
    """Interpret a user answer into adapter-sourced structured proposals."""

    text = _clean_text(answer)
    if not text:
        return _error("validation_error", "answer must be a non-empty string.")
    if not isinstance(context, dict):
        return _error("schema_error", "context must be an object.")

    selected = _selected_ids(context)
    topic = _safe_topic(context.get("topic"))
    if not selected or not topic:
        return _error("validation_error", "context must include requirement IDs and a topic.")

    question = _interpretation_question(context, topic)
    try:
        request = build_answer_interpretation_request(question, text, topic)
        adapter = _answer_interpretation_adapter(context)
    except AgentConfigValidationError as exc:
        return {"status": "error", "error": {"type": "schema_error", "message": str(exc), "violations": exc.errors}}

    completion = adapter.complete(request)
    if completion.status != "ok":
        return _adapter_error(completion)

    payload = completion.payload or {}
    guard_error = _denied_positive_fact_guard_error(payload, topic, selected, completion)
    if guard_error is not None:
        return guard_error

    return _answer_interpretation_payload_to_proposals(payload, selected, topic, question, completion)


def _interpretation_question(context: dict[str, Any], topic: str) -> str:
    for key in ("question", "question_text", "prompt"):
        question = _clean_text(context.get(key))
        if question:
            return question
    return f"What can you confirm about {topic}?"


def _answer_interpretation_adapter(context: dict[str, Any]) -> ModelAdapter:
    injected = context.get("_adapter")
    if injected is not None:
        return injected
    return DeterministicFakeAdapter(agent_config=require_agent_config(context))


def _denied_positive_fact_guard_error(
    payload: dict[str, Any],
    topic: str,
    selected_requirement_ids: list[str],
    completion: Any,
) -> dict[str, Any] | None:
    if payload.get("polarity") != "denied":
        return None
    fact_proposals = [item for item in payload.get("factProposals", []) if isinstance(item, dict)]
    if not fact_proposals:
        return None
    violations = [
        {
            "code": "denied_positive_fact_proposal",
            "field_path": f"factProposals/{index}",
            "message": "Denied answer interpretation emitted a positive fact proposal.",
            "severity": "error",
            "details": {
                "topic": topic,
                "selected_requirement_ids": selected_requirement_ids,
                "fact_id": fact.get("fact_id"),
            },
        }
        for index, fact in enumerate(fact_proposals)
    ]
    result = {
        "status": "error",
        "error": {
            "type": "schema_invalid",
            "message": "Denied answer interpretation failed the positive-claim guard.",
            "violations": violations,
            "details": {"reason": "denied_positive_fact_guard", "topic": topic},
        },
    }
    _copy_adapter_metadata(result, completion)
    return result


def _answer_interpretation_payload_to_proposals(
    payload: dict[str, Any],
    selected_requirement_ids: list[str],
    topic: str,
    question: str,
    completion: Any,
) -> dict[str, Any]:
    result = _base("answer_interpretation")
    facts = [_mapped_interpretation_fact(item) for item in payload.get("factProposals", []) if isinstance(item, dict)]
    facts = [item for item in facts if item]
    fact_ids = [str(fact["fact_id"]) for fact in facts if _clean_text(fact.get("fact_id"))]
    resolutions = [
        _mapped_requirement_resolution(item, fact_ids)
        for item in payload.get("requirementResolutions", [])
        if isinstance(item, dict)
    ]
    resolutions = [item for item in resolutions if item]
    evidence = [
        _mapped_answer_evidence(item, selected_requirement_ids)
        for item in payload.get("evidenceProposals", [])
        if isinstance(item, dict)
    ]
    evidence = [item for item in evidence if item]
    relationships = [
        {
            "relationship_id": _stable_id("rel", f"{fact_id}:{','.join(selected_requirement_ids)}"),
            "fact_id": fact_id,
            "requirement_ids": selected_requirement_ids,
            "relationship": "supports_review",
        }
        for fact_id in fact_ids
    ]
    result.update(
        {
            "status": "ok",
            "outcome": payload.get("polarity"),
            "polarity": payload.get("polarity"),
            "question": question,
            "topic": topic,
            "proposals": facts + resolutions,
            "requirement_resolution_proposals": resolutions,
            "fact_proposals": facts,
            "evidence_proposals": evidence,
            "relationship_proposals": relationships,
            "explicit_negative_facts": [],
            "requirementResolutions": payload.get("requirementResolutions", []),
            "factProposals": payload.get("factProposals", []),
            "evidenceProposals": payload.get("evidenceProposals", []),
            "uncertainty": payload.get("uncertainty", []),
            "model_metadata": {
                "adapter_id": getattr(completion, "adapter_id", None),
                "adapter_version": getattr(completion, "adapter_version", None),
                "model_id": getattr(completion, "model_id", None),
            },
        }
    )
    _copy_adapter_metadata(result, completion)
    return result


def _mapped_interpretation_fact(item: dict[str, Any]) -> dict[str, Any]:
    fact_id = _clean_text(item.get("fact_id"))
    text = _clean_text(item.get("text"))
    if not fact_id or not text:
        return {}
    confidence = item.get("confidence")
    proposal = {
        "fact_id": fact_id,
        "category": _clean_text(item.get("category")) or "experience",
        "text": text,
        "normalized_terms": _unique([str(term) for term in item.get("normalized_terms", []) if _clean_text(str(term))]),
        "source_evidence_ids": [str(evidence_id) for evidence_id in item.get("source_evidence_ids", []) if _clean_text(str(evidence_id))],
        "evidence": [_answer_evidence_ref(evidence) for evidence in item.get("evidence", []) if isinstance(evidence, dict)],
        "verification_state": item.get("verification_state"),
        "confidence": confidence,
        "model_confidence": confidence,
        "hedge_or_qualifier": item.get("hedge_or_qualifier"),
        "review_required": True,
    }
    return proposal


def _mapped_requirement_resolution(item: dict[str, Any], supporting_fact_ids: list[str]) -> dict[str, Any]:
    requirement_id = _clean_text(item.get("requirement_id"))
    if not requirement_id:
        return {}
    confidence = item.get("confidence")
    return {
        "requirement_id": requirement_id,
        "supporting_fact_ids": list(supporting_fact_ids),
        "suggested_state": item.get("suggested_state"),
        "confidence": confidence,
        "model_confidence": confidence,
        "hedge_or_qualifier": item.get("hedge_or_qualifier"),
        "evidence": [_answer_evidence_ref(evidence) for evidence in item.get("evidence", []) if isinstance(evidence, dict)],
        "review_required": True,
    }


def _mapped_answer_evidence(item: dict[str, Any], selected_requirement_ids: list[str]) -> dict[str, Any]:
    evidence_id = _clean_text(item.get("evidence_id"))
    text = _clean_text(item.get("text"))
    if not evidence_id or not text:
        return {}
    return {
        "evidence_id": evidence_id,
        "kind": item.get("kind"),
        "text": text,
        "snippet": text,
        "span": item.get("span"),
        "confidence": item.get("confidence"),
        "selected_requirement_ids": selected_requirement_ids,
    }


def _answer_evidence_ref(item: dict[str, Any]) -> dict[str, Any]:
    source_text = _clean_text(item.get("source_text"))
    return {
        "evidence_id": _clean_text(item.get("evidence_id")),
        "source_text": source_text,
        "text": source_text,
        "snippet": source_text,
        "span": item.get("span"),
    }


def _copy_adapter_metadata(result: dict[str, Any], completion: Any) -> None:
    for field in ["adapter_id", "adapter_version", "model_id", "runtime_config", "retries", "usage"]:
        if hasattr(completion, field):
            result[field] = getattr(completion, field)


def proposeRewrite(context: dict[str, Any]) -> dict[str, Any]:
    """Return grounded text replacement operations as proposals."""

    if not isinstance(context, dict):
        return _error("schema_error", "context must be an object.")

    required = {
        "original_text",
        "allowed_facts",
        "job_terminology",
        "requirements",
        "prohibited_additions",
        "length_constraints",
        "voice_constraints",
    }
    missing = sorted(name for name in required if name not in context)
    if missing:
        return _error("schema_error", f"context is missing required fields: {', '.join(missing)}.")

    original = _clean_text(context.get("original_text"))
    allowed_facts = context.get("allowed_facts")
    job_terms = context.get("job_terminology")
    requirements = context.get("requirements")
    blocked = context.get("prohibited_additions")
    length_constraints = context.get("length_constraints")

    if not original or not isinstance(allowed_facts, list) or not isinstance(job_terms, list) or not isinstance(requirements, list):
        return _error("validation_error", "context fields have invalid proposal input shapes.")
    if not isinstance(blocked, list):
        blocked = []
    if not isinstance(length_constraints, dict):
        length_constraints = {}

    blocked_text = [_clean_text(item) for item in blocked if _clean_text(item)]
    usable_terms = [
        _clean_text(term)
        for term in job_terms
        if _clean_text(term) and not _is_blocked(_clean_text(term), blocked_text)
    ]
    usable_facts = [
        fact
        for fact in allowed_facts
        if isinstance(fact, dict)
        and _clean_text(fact.get("fact_id"))
        and _clean_text(fact.get("text"))
        and not _is_blocked(_clean_text(fact.get("text")), blocked_text)
    ]
    usable_terms = [term for term in usable_terms if _term_supported_by_facts(term, usable_facts)]

    fact_ids = [str(fact["fact_id"]) for fact in usable_facts]
    requirement_ids = [
        str(requirement.get("requirement_id"))
        for requirement in requirements
        if isinstance(requirement, dict) and _clean_text(requirement.get("requirement_id"))
    ]

    phrases: list[str] = []
    lowered_original = original.lower()
    for term in usable_terms:
        if term.lower() not in lowered_original:
            phrases.append(term)
    for fact in usable_facts:
        fact_text = _clean_text(fact.get("text"))
        if not _contains_years(fact_text) and not any(term.lower() in fact_text.lower() for term in usable_terms):
            phrases.append(fact_text)

    unique_phrases: list[str] = []
    for phrase in phrases:
        if phrase and phrase.lower() not in {item.lower() for item in unique_phrases}:
            unique_phrases.append(phrase)

    if unique_phrases:
        after = f"Built {', '.join(unique_phrases)}."
    else:
        after = original

    max_chars = length_constraints.get("max_chars")
    if isinstance(max_chars, int) and max_chars > 20 and len(after) > max_chars:
        after = after[: max_chars - 1].rsplit(" ", 1)[0].rstrip(" ,.;") + "."

    result = _base("rewrite_proposal")
    if after == original:
        result["uncertainty"].append(
            {
                "type": "no_safe_change",
                "message": "No grounded terminology change was available from the supplied facts.",
            }
        )

    operation = {
        "operation_id": _stable_id("op", original + "=>" + after),
        "operation_type": "replace_text",
        "target_path": context.get("target_path", "experience[0].bullets[0]"),
        "before": original,
        "after": after,
        "facts_used": fact_ids,
        "requirements_targeted": requirement_ids,
        "terminology_changes": [
            {"term": term, "action": "include"} for term in usable_terms if term.lower() in after.lower()
        ],
        "provenance": {
            "source": "resume-agent",
            "grounding": "allowed_facts",
            "review_required": True,
        },
        "reason": "Use supplied allowed facts and selected terminology to propose a reviewable replacement.",
        "status": "proposed",
    }
    result.update({"operations": [operation]})
    result["proposals"] = [operation]
    return result


def _term_supported_by_facts(term: str, facts: list[dict[str, Any]]) -> bool:
    variants = _TERM_SUPPORT_VARIANTS.get(term.casefold(), (term,))
    return any(_fact_supports_term(fact, variants) for fact in facts)


def _fact_supports_term(fact: dict[str, Any], variants: tuple[str, ...]) -> bool:
    segments = [_clean_text(fact.get("text"))]
    terms = fact.get("normalized_terms")
    if isinstance(terms, list):
        segments.extend(_clean_text(term) for term in terms if isinstance(term, str))
    evidence = fact.get("evidence")
    if isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, dict):
                segments.append(_clean_text(item.get("text")))
    text = " ".join(segment for segment in segments if segment)
    return any(_term_in_text(variant, text) for variant in variants)


def _contains_years(text: str) -> bool:
    return bool(re.search(r"\b\d+\+?\s*years?\b|\b(one|two|three|four|five|six|seven|eight|nine|ten)\s+years?\b", text, re.IGNORECASE))
