"""Public proposal surface for resume-agent."""

from __future__ import annotations

import hashlib
import re
from typing import Any

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
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    proposal = {
        "fact_id": _stable_id("fact", f"{category}:{text}"),
        "category": category,
        "text": text,
        "normalized_terms": terms,
        "source_evidence_ids": [evidence_id],
        "confidence": confidence,
        "review_required": True,
    }
    if extra:
        proposal.update(extra)
    return proposal


def _split_items(text: str) -> list[str]:
    parts = re.split(r",|\band\b", text)
    return [_clean_text(part.strip(" .;:")) for part in parts if _clean_text(part.strip(" .;:"))]


def _terms_for(text: str) -> list[str]:
    lowered = text.lower()
    terms: list[str] = []
    years = re.search(r"\b\d+\s*\+?\s*years?\b", text, re.IGNORECASE)
    if years:
        terms.append(_clean_text(years.group(0)))
    checks = [
        ("software engineering", r"\bsoftware engineering\b"),
        ("react", r"\breact\b"),
        ("typescript", r"\btypescript\b"),
        ("node.js", r"\bnode(?:\.js|js)?\b"),
        ("postgresql", r"\bpostgres(?:ql)?\b"),
        ("api", r"\bapis?\b|\bapi\b"),
        ("api architecture", r"\bapi architecture\b|\barchitecture/design\b"),
        ("api design", r"\bapi design\b|\barchitecture/design\b|\bdesign\b"),
        ("responsive design", r"\bresponsive\b"),
        ("responsive web applications", r"\bresponsive\b.*\bweb\b|\bweb\b.*\bresponsive\b"),
        ("saas", r"\bsaas\b"),
        ("aws", r"\baws\b"),
        ("graphql", r"\bgraphql\b"),
        ("technical leadership", r"\btechnical leadership\b|\bleadership\b"),
    ]
    for term, pattern in checks:
        if re.search(pattern, lowered, re.IGNORECASE):
            terms.append(term)
    return terms or [_clean_text(text).lower()]


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


def _line_records(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    offset = 0
    for raw_line in text.splitlines(keepends=True):
        line = raw_line.rstrip("\r\n")
        stripped = line.strip()
        if stripped:
            start = offset + line.find(stripped)
            records.append({"text": stripped, "start": start, "end": start + len(stripped)})
        offset += len(raw_line)
    return records


def _evidence_from_span(text: str, snippet: str, start: int, end: int, prefix: str) -> dict[str, Any]:
    return {
        "evidence_id": _stable_id(prefix, f"{start}:{snippet}"),
        "text": snippet,
        "snippet": snippet,
        "span": {"start": start, "end": end},
    }


def _add_resume_fact(
    raw_text: str,
    facts: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    category: str,
    label: str,
    pattern: str,
    terms: list[str],
    confidence: str = "high",
    extra: dict[str, Any] | None = None,
) -> None:
    match = re.search(pattern, raw_text, re.IGNORECASE | re.MULTILINE)
    if not match:
        return
    snippet = _clean_text(match.group(0))
    source = _evidence(raw_text, snippet, "resume_ev")
    evidence.append(source)
    facts.append(_proposal_fact(label, category, terms, source["evidence_id"], confidence, extra))


def _looks_like_title(line: str) -> bool:
    return bool(
        re.search(
            r"\b(software|engineer|developer|architect|lead|principal|senior|full[- ]stack)\b",
            line,
            re.IGNORECASE,
        )
    )


def _is_section_heading(line: str) -> bool:
    cleaned = line.strip().rstrip(":").lower()
    return cleaned in {
        "required",
        "requirements",
        "required qualifications",
        "minimum qualifications",
        "preferred",
        "preferred qualifications",
        "nice to have",
        "nice-to-have",
        "context",
        "about",
        "responsibilities",
        "qualifications",
    }


def _job_heading_classification(line: str) -> tuple[str | None, str]:
    match = re.match(
        r"^\s*(required(?:\s+qualifications?)?|requirements?|minimum qualifications?|preferred(?:\s+qualifications?)?|nice[- ]to[- ]have|contextual|responsibilities|about)\s*:?\s*(.*)$",
        line,
        re.IGNORECASE,
    )
    if not match:
        return None, ""
    heading = match.group(1).lower()
    if "preferred" in heading or "nice" in heading:
        return "preferred", match.group(2).strip()
    if "required" in heading or "requirement" in heading or "minimum" in heading:
        return "required", match.group(2).strip()
    return "contextual", match.group(2).strip()


def _strip_bullet(line: str) -> str:
    return re.sub(r"^\s*[-*•◦]\s*", "", line).strip()


def _requirement_items(body: str) -> list[str]:
    cleaned = _clean_text(body.strip(" .;"))
    if not cleaned:
        return []
    if "," not in cleaned:
        return [cleaned]
    parts = re.split(r",|\band\b", cleaned)
    return [_clean_text(part.strip(" .;:")) for part in parts if _clean_text(part.strip(" .;:"))]


def _years_detail(text: str) -> dict[str, Any] | None:
    match = re.search(r"\b(\d+)\s*\+?\s*years?\b", text, re.IGNORECASE)
    if not match:
        return None
    return {"minimum": int(match.group(1)), "source_text": _clean_text(match.group(0))}


def _requirement_concepts(source_text: str) -> list[tuple[str, list[str]]]:
    lowered = source_text.lower()
    concepts: list[tuple[str, list[str]]] = []
    checks = [
        ("req_years", ["years", "software engineering"], r"\b\d+\s*\+?\s*years?\b"),
        ("req_react", ["react"], r"\breact\b"),
        ("req_typescript", ["typescript"], r"\btypescript\b"),
        ("req_node", ["node.js"], r"\bnode(?:\.js|js)?\b"),
        ("req_postgresql", ["postgresql"], r"\bpostgres(?:ql)?\b"),
        ("req_aws", ["aws"], r"\baws\b"),
        ("req_graphql", ["graphql"], r"\bgraphql\b"),
        ("req_responsive", ["responsive design"], r"\bresponsive\b"),
        ("req_saas", ["saas"], r"\bsaas\b"),
        ("req_leadership", ["technical leadership"], r"\btechnical leadership\b|\bleadership\b|\bmentoring\b|\bdesign review\b|\bcross-team architecture\b"),
        ("req_api", ["api", "api architecture", "api design"], r"\bapi architecture\b|\barchitecture/design\b|\bapi design\b|\bapis?\b"),
    ]
    for requirement_id, terms, pattern in checks:
        if re.search(pattern, lowered, re.IGNORECASE):
            concepts.append((requirement_id, terms))
    if any(requirement_id == "req_graphql" for requirement_id, _ in concepts):
        concepts = [(requirement_id, terms) for requirement_id, terms in concepts if requirement_id != "req_api"]
    if not concepts:
        concepts.append((_stable_id("req", source_text), _terms_for(source_text)))
    return concepts


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
    if not _clean_text(rawText):
        return _error("validation_error", "rawText must be a non-empty string.")

    result = _base("resume_semantic_extraction")
    evidence: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []

    lines = _line_records(rawText)
    possible_titles = [
        line
        for line in lines[:4]
        if _looks_like_title(str(line["text"])) and not _is_section_heading(str(line["text"]))
    ]
    if possible_titles:
        title = possible_titles[0]
        source = _evidence_from_span(rawText, str(title["text"]), int(title["start"]), int(title["end"]), "resume_ev")
        evidence.append(source)
        facts.append(
            _proposal_fact(
                str(title["text"]),
                "title",
                [str(title["text"]).lower()],
                source["evidence_id"],
                "high",
            )
        )

    years_match = re.search(
        r"\b\d+\s*\+?\s+years?\s+of\s+(?:full[- ]stack\s+)?software development experience\b",
        rawText,
        re.IGNORECASE,
    )
    if years_match:
        snippet = _clean_text(years_match.group(0))
        source = _evidence(rawText, snippet, "resume_ev")
        evidence.append(source)
        terms = _terms_for(snippet)
        if "full-stack" not in terms and re.search(r"full[- ]stack", snippet, re.IGNORECASE):
            terms.append("full-stack")
        if "software development" not in terms:
            terms.append("software development")
        facts.append(
            _proposal_fact(
                snippet,
                "experience",
                _unique(terms),
                source["evidence_id"],
                "high",
                {"years": _years_detail(snippet)},
            )
        )

    resume_patterns = [
        ("domain", "SaaS products", r"\bmulti-tenant\s+SaaS products?\b|\bSaaS products?\b|\bSaaS\b", ["saas"]),
        ("skill", "React", r"\bReact\b", ["react"]),
        ("skill", "TypeScript", r"\bTypeScript\b", ["typescript"]),
        ("skill", "Node.js", r"\bNode\.js\b|\bNodeJS\b", ["node.js"]),
        ("skill", "PostgreSQL", r"\bPostgreSQL\b|\bPostgres\b", ["postgresql"]),
        ("skill", "Azure", r"\bAzure\b", ["azure"]),
        ("skill", "REST APIs", r"\bREST APIs?\b", ["rest", "api"]),
        (
            "experience",
            "API design and integration work",
            r"\bDesigned\s+REST APIs?\b|\bREST APIs?\b|\bAPI architecture\b|\bAPI design\b|\bintegration patterns\b",
            ["rest", "api", "api design"],
        ),
        (
            "experience",
            "responsive web apps",
            r"\bresponsive web apps?\b|\bresponsive web applications?\b",
            ["responsive design", "responsive web applications"],
        ),
        (
            "experience",
            "workflow automation",
            r"\bworkflow automation\b",
            ["workflow automation"],
        ),
        (
            "leadership",
            "team leadership",
            r"\bLed a small team of three developers\b|\bteam leadership\b|\bdelivery planning\b|\bcode review\b|\brelease coordination\b",
            ["team leadership", "delivery planning", "code review", "release coordination"],
        ),
    ]

    seen_facts = {fact["fact_id"] for fact in facts}
    for category, label, pattern, terms in resume_patterns:
        before = len(facts)
        _add_resume_fact(rawText, facts, evidence, category, label, pattern, terms)
        if len(facts) > before and facts[-1]["fact_id"] in seen_facts:
            facts.pop()
            evidence.pop()
        elif len(facts) > before:
            seen_facts.add(facts[-1]["fact_id"])

    text = _clean_text(rawText)
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
    lines = _line_records(rawJobText)
    heading = str(lines[0]["text"]) if lines else ""
    job_title = _clean_text(heading.split(",", 1)[0]) if heading else None
    company = _clean_text(heading.split(",", 1)[1]) if "," in heading else None
    if company is None and len(lines) > 1:
        second = str(lines[1]["text"])
        if not _is_section_heading(second) and not _job_heading_classification(second)[0] and not re.match(r"^\s*[-*•◦]", second):
            company = second

    requirements: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    terminology: list[str] = []
    seen_requirements: set[tuple[str, str]] = set()
    current_classification: str | None = None

    def append_requirement(source_text: str, classification: str, start: int | None = None, end: int | None = None) -> None:
        cleaned = _clean_text(source_text.strip(" .;"))
        if not cleaned:
            return
        source = (
            _evidence_from_span(rawJobText, cleaned, start, end, "job_ev")
            if start is not None and end is not None
            else _evidence(rawJobText, cleaned, "job_ev")
        )
        evidence.append(source)
        for requirement_id, concept_terms in _requirement_concepts(cleaned):
            key = (requirement_id, classification)
            if key in seen_requirements:
                continue
            seen_requirements.add(key)
            terms = _unique([*concept_terms, *_terms_for(cleaned)])
            terminology.extend(term for term in terms if term not in terminology)
            requirement: dict[str, Any] = {
                "requirement_id": requirement_id,
                "source_text": cleaned,
                "classification": classification,
                "normalized_terms": terms,
                "source_evidence_ids": [source["evidence_id"]],
            }
            years = _years_detail(cleaned)
            if years:
                requirement["years"] = years
            requirements.append(requirement)

    start_index = 1
    if company and len(lines) > 1 and str(lines[1]["text"]) == company:
        start_index = 2

    for record in lines[start_index:]:
        line = str(record["text"])
        heading_classification, heading_body = _job_heading_classification(line)
        if heading_classification:
            current_classification = heading_classification
            if heading_body:
                for item in _requirement_items(heading_body):
                    append_requirement(item, current_classification)
            continue

        body = _strip_bullet(line)
        if not body or _is_section_heading(body):
            continue
        classification = current_classification or "contextual"
        line_start = int(record["start"]) + line.find(body)
        line_end = line_start + len(body)
        append_requirement(body, classification, line_start, line_end)

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
            "outcome": _answer_outcome(text),
            "proposals": facts + resolutions + negatives,
            "requirement_resolution_proposals": resolutions,
            "fact_proposals": facts,
            "evidence_proposals": evidence,
            "relationship_proposals": relationships,
            "explicit_negative_facts": negatives,
        }
    )
    return result


def _answer_outcome(text: str) -> str:
    affirmative = _contains(text, r"\b(yes|i have|i've|i used|built|designed|maintained|worked)\b")
    denied = _contains(text, r"\b(incorrect|no|not|never|haven't|have not|did nothing|did not|don't|do not)\b")
    if affirmative:
        return "affirmed"
    if denied:
        return "denied"
    return "unclear"


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
