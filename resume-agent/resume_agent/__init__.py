"""Public proposal surface for resume-agent."""

from __future__ import annotations

import hashlib
import re
from typing import Any


SCHEMA_VERSION = "resume-agent.proposal.v1"

__all__ = [
    "extractResumeSemantics",
    "extractJobSemantics",
    "generateClarificationQuestion",
    "interpretUserAnswer",
    "proposeRewrite",
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


def _stable_id(prefix: str, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def _evidence(text: str, snippet: str, prefix: str) -> dict[str, Any]:
    start = text.lower().find(snippet.lower())
    end = start + len(snippet) if start >= 0 else None
    return {
        "evidence_id": _stable_id(prefix, snippet),
        "text": snippet,
        "span": {"start": start if start >= 0 else None, "end": end},
    }


def _contains(text: str, pattern: str) -> bool:
    return re.search(pattern, text, re.IGNORECASE) is not None


def _first_match(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(0) if match else None


def _proposal_fact(
    text: str,
    category: str,
    terms: list[str],
    evidence_id: str,
    confidence: str = "medium",
) -> dict[str, Any]:
    return {
        "fact_id": _stable_id("fact", f"{category}:{text}"),
        "category": category,
        "text": text,
        "normalized_terms": terms,
        "source_evidence_ids": [evidence_id],
        "confidence": confidence,
        "review_required": True,
    }


def _split_items(text: str) -> list[str]:
    parts = re.split(r",|\band\b", text)
    return [_clean_text(part.strip(" .;:")) for part in parts if _clean_text(part.strip(" .;:"))]


def _terms_for(text: str) -> list[str]:
    lowered = text.lower()
    terms: list[str] = []
    checks = [
        ("8+ years", r"8\+\s*years"),
        ("react", r"\breact\b"),
        ("typescript", r"\btypescript\b"),
        ("api", r"\bapis?\b|\bapi\b"),
        ("api architecture", r"\bapi architecture\b|\barchitecture/design\b"),
        ("api design", r"\bapi design\b|\barchitecture/design\b"),
        ("responsive design", r"\bresponsive\b"),
        ("saas", r"\bsaas\b"),
        ("aws", r"\baws\b"),
        ("graphql", r"\bgraphql\b"),
        ("technical leadership", r"\btechnical leadership\b|\bleadership\b"),
    ]
    for term, pattern in checks:
        if re.search(pattern, lowered, re.IGNORECASE):
            terms.append(term)
    return terms or [_clean_text(text).lower()]


def _safe_topic(value: Any) -> str:
    return _clean_text(value)


def _selected_ids(context: dict[str, Any]) -> list[str]:
    selected = context.get("selected_requirement_ids", [])
    if not isinstance(selected, list):
        return []
    return [str(item) for item in selected if _clean_text(str(item))]


def _years_phrase(answer: str) -> str | None:
    match = re.search(
        r"\b(?:about|around|more than|over|nearly|approximately)?\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:\+)?\s+years?\b",
        answer,
        re.IGNORECASE,
    )
    return _clean_text(match.group(0)) if match else None


def _mentioned_terms(text: str, terms: list[str]) -> list[str]:
    found: list[str] = []
    for term in terms:
        if re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE):
            found.append(term)
    return found


def _is_blocked(value: str, blocked: list[str]) -> bool:
    lowered = value.lower()
    return any(item and item.lower() in lowered for item in blocked)


def extractResumeSemantics(rawText: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract source-backed semantic proposals from plain resume text."""

    del context
    text = _clean_text(rawText)
    if not text:
        return _error("validation_error", "rawText must be a non-empty string.")

    result = _base("resume_semantic_extraction")
    evidence: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []

    patterns = [
        ("skill", "React", r"\bReact\b", ["react"]),
        ("skill", "TypeScript", r"\bTypeScript\b", ["typescript"]),
        ("skill", "REST APIs", r"\bREST APIs?\b", ["rest", "api"]),
        (
            "experience",
            "responsive web applications",
            r"\bresponsive web applications?\b",
            ["responsive design", "web applications"],
        ),
        (
            "experience",
            "API architecture",
            r"\bAPI architecture\b|\bDesigned API architecture\b",
            ["api", "api architecture", "api design"],
        ),
        ("domain", "SaaS products", r"\bSaaS products?\b|\bSaaS\b", ["saas"]),
    ]

    for category, label, pattern, terms in patterns:
        snippet = _first_match(text, pattern)
        if not snippet:
            continue
        source = _evidence(text, snippet, "ev")
        evidence.append(source)
        facts.append(_proposal_fact(label, category, terms, source["evidence_id"], "high"))

    if _contains(text, r"\bambiguous\b|\bvarious\b|\bseveral\b"):
        result["uncertainty"].append(
            {
                "type": "ambiguous_source",
                "message": "Some source wording is broad and should be reviewed before use.",
            }
        )

    result.update(
        {
            "proposals": facts,
            "fact_proposals": facts,
            "source_evidence": evidence,
        }
    )
    return result


def extractJobSemantics(rawJobText: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract job semantics as proposal data for downstream validation."""

    del context
    text = _clean_text(rawJobText)
    if not text:
        return _error("validation_error", "rawJobText must be a non-empty string.")

    result = _base("job_semantic_extraction")
    lines = [line.strip() for line in rawJobText.splitlines() if line.strip()]
    heading = lines[0] if lines else ""
    job_title = _clean_text(heading.split(",", 1)[0]) if heading else None
    company = _clean_text(heading.split(",", 1)[1]) if "," in heading else None

    requirements: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    terminology: list[str] = []

    for line in lines[1:]:
        label_match = re.match(r"^(required|preferred|contextual)\s*:\s*(.+)$", line, re.IGNORECASE)
        if not label_match:
            continue
        classification = label_match.group(1).lower()
        body = label_match.group(2)
        for item in _split_items(body):
            terms = _terms_for(item)
            source = _evidence(text, item, "job_ev")
            evidence.append(source)
            terminology.extend(term for term in terms if term not in terminology)
            requirements.append(
                {
                    "requirement_id": _stable_id("req", f"{classification}:{item}"),
                    "source_text": item,
                    "classification": classification,
                    "normalized_terms": terms,
                    "source_evidence_ids": [source["evidence_id"]],
                }
            )

    if not requirements:
        result["uncertainty"].append(
            {
                "type": "unstructured_job_text",
                "message": "No labeled requirement sections were found.",
            }
        )

    result.update(
        {
            "proposals": requirements,
            "job_title": job_title,
            "company": company,
            "seniority": _first_match(job_title or text, r"\b(senior|lead|principal|staff|junior|mid-level)\b"),
            "industries": ["SaaS"] if _contains(text, r"\bSaaS\b") else [],
            "domains": [term for term in ["API architecture", "responsive design"] if _contains(text, term)],
            "requirements": requirements,
            "terminology": terminology,
            "source_evidence": evidence,
        }
    )
    return result


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

    topic_lower = topic.lower()
    if "aws" in topic_lower:
        question = "What AWS services have you used professionally, and for roughly how many years?"
    elif "graphql" in topic_lower:
        question = "Have you built or maintained GraphQL APIs in production, and for roughly how many years?"
    elif "architecture" in topic_lower or "api" in topic_lower:
        question = "What API or application architecture have you designed, and what was your role in that work?"
    else:
        question = f"What direct experience do you have with {topic}, and what evidence should be considered?"

    result = _base("clarification_question")
    result.update(
        {
            "proposals": [{"question": question, "selected_requirement_ids": selected, "topic": topic}],
            "question": question,
            "selected_requirement_ids": selected,
            "topic": topic,
            "already_verified_fact_ids": [str(item) for item in already],
        }
    )
    return result


def interpretUserAnswer(answer: str, context: dict[str, Any]) -> dict[str, Any]:
    """Interpret a user answer into structured proposals."""

    text = _clean_text(answer)
    if not text:
        return _error("validation_error", "answer must be a non-empty string.")
    if not isinstance(context, dict):
        return _error("schema_error", "context must be an object.")

    selected = _selected_ids(context)
    topic = _safe_topic(context.get("topic"))
    if not selected or not topic:
        return _error("validation_error", "context must include requirement IDs and a topic.")

    result = _base("answer_interpretation")
    evidence_id = _stable_id("answer_ev", text)
    years = _years_phrase(text)
    topic_lower = topic.lower()

    evidence = [
        {
            "evidence_id": evidence_id,
            "kind": "user_answer",
            "text": text,
            "selected_requirement_ids": selected,
        }
    ]
    facts: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    resolutions: list[dict[str, Any]] = []
    negatives: list[dict[str, Any]] = []

    if "aws" in topic_lower:
        services = _mentioned_terms(text, ["EC2", "S3", "Lambda", "RDS", "IAM", "CloudFront", "DynamoDB"])
        fact_text = "AWS experience"
        if years:
            fact_text = f"{fact_text}, {years}"
        if services:
            fact_text = f"{fact_text}, including {', '.join(services)}"
        facts.append(_proposal_fact(fact_text, "skill", ["aws", *[service.lower() for service in services]], evidence_id))
    elif "graphql" in topic_lower:
        terms = ["graphql"]
        if _contains(text, r"\bproduction\b"):
            terms.append("production")
        fact_text = "GraphQL API experience"
        if years:
            fact_text = f"{fact_text}, {years}"
        if "production" in terms:
            fact_text = f"{fact_text}, production context"
        facts.append(_proposal_fact(fact_text, "skill", terms, evidence_id))
    elif "architecture" in topic_lower or "api" in topic_lower:
        terms = ["architecture"]
        if _contains(text, r"\bapis?\b"):
            terms.append("api")
        fact_text = "Architecture experience"
        if "api" in terms:
            fact_text = "API and application architecture experience"
        if years:
            fact_text = f"{fact_text}, {years}"
        facts.append(_proposal_fact(fact_text, "experience", terms, evidence_id))

    if _contains(text, r"\bnot\b|\bhaven't\b|\bhave not\b|\bno\b"):
        if _contains(text, r"\bstaff\b"):
            negatives.append(
                {
                    "fact_id": _stable_id("negative", "staff-title"),
                    "topic": "staff title",
                    "text": "not a formal title",
                    "source_evidence_ids": [evidence_id],
                    "review_required": True,
                }
            )

    for fact in facts:
        relationships.append(
            {
                "relationship_id": _stable_id("rel", fact["fact_id"] + ":" + ",".join(selected)),
                "fact_id": fact["fact_id"],
                "requirement_ids": selected,
                "relationship": "supports_review",
            }
        )

    for requirement_id in selected:
        resolutions.append(
            {
                "requirement_id": requirement_id,
                "supporting_fact_ids": [fact["fact_id"] for fact in facts],
                "suggested_state": "possible_match" if facts else "unknown",
                "review_required": True,
            }
        )

    result.update(
        {
            "proposals": facts + resolutions + negatives,
            "requirement_resolution_proposals": resolutions,
            "fact_proposals": facts,
            "evidence_proposals": evidence,
            "relationship_proposals": relationships,
            "explicit_negative_facts": negatives,
        }
    )
    return result


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
        if not any(term.lower() in fact_text.lower() for term in usable_terms):
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
        "status": "proposed",
    }
    result.update({"operations": [operation]})
    result["proposals"] = [operation]
    return result
