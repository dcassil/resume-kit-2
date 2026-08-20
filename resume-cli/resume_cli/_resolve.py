"""Interactive requirement resolution for resume-cli."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from career_store import openCareerStore
from resume_agent import generateClarificationQuestion, interpretUserAnswer
from resume_core import getUnresolvedRequirements


JsonObject = dict[str, Any]

SUCCESS_EXIT = 0
DOMAIN_VALIDATION_EXIT = 1


class ResolveTerminalIO(Protocol):
    def ask(self, question: str) -> str:
        """Ask a terminal question and return the answer."""

    def confirm(self, summary: str) -> bool:
        """Ask for confirmation and return the user's decision."""


def resolve(
    workspace: Path,
    terminal_io: ResolveTerminalIO,
    *,
    init_workspace: Callable[[Path], JsonObject],
    run_match: Callable[[Path], JsonObject],
    load_facts: Callable[[Path], list[JsonObject]],
    load_config: Callable[[Path], JsonObject],
    paths_for_workspace: Callable[[Path], dict[str, Path]],
    record_latest_run_snapshot: Callable[[Path, str, JsonObject], None],
    current_job_id: Callable[[Path], str],
) -> JsonObject:
    init_workspace(workspace)
    match = run_match(workspace)
    match_result = match.get("match_result", {}) if isinstance(match, dict) else {}
    context = resolution_context(match_result, load_facts(workspace), load_config(workspace))
    if context.get("status") != "ok":
        return context

    question = generateClarificationQuestion(context)
    if question.get("status") == "error":
        return _agent_error(question, "question")
    question_text = str(question.get("question") or "")
    question_subject_id = str(question.get("question_id") or _stable_short_id("question", question_text))
    store = openCareerStore(str(paths_for_workspace(workspace)["career_db"]))
    interactions: list[JsonObject] = []
    interactions.append(
        store.recordInteraction(
            "question_asked",
            question_subject_id,
            {
                "question": question_text,
                "topic": context.get("topic"),
                "selected_requirement_ids": context.get("selected_requirement_ids", []),
                "requirement": context.get("requirement"),
            },
            {
                "question_id": question_subject_id,
                "target_ids": question.get("target_ids", {}),
            },
        )
    )

    answer = terminal_io.ask(question_text)
    interpretation_context = {**context, "question": question_text, "question_id": question_subject_id}
    interpretation = interpretUserAnswer(answer, interpretation_context)
    if interpretation.get("status") == "error":
        interactions.append(_record_answer(store, question_subject_id, question_text, answer, interpretation))
        return _agent_error(interpretation, "answer")
    interactions.append(_record_answer(store, question_subject_id, question_text, answer, interpretation))

    stored_facts: list[JsonObject] = []
    outcomes: list[JsonObject] = []
    for proposal in _fact_proposals(interpretation, context):
        exact_fact_text = str(proposal["text"])
        confirmed = terminal_io.confirm(f"Persist fact: {exact_fact_text}")
        interactions.append(
            store.recordInteraction(
                "fact_confirmed",
                question_subject_id,
                {
                    "fact_id": proposal.get("fact_id"),
                    "fact_text": exact_fact_text,
                    "selected_requirement_ids": context.get("selected_requirement_ids", []),
                },
                {"confirmed": confirmed},
            )
        )
        if not confirmed:
            outcomes.append(
                {
                    "kind": "fact_confirmation",
                    "status": "declined",
                    "fact_id": proposal.get("fact_id"),
                    "text": exact_fact_text,
                }
            )
            continue

        evidence = _answer_evidence(answer, interpretation, context, question_subject_id)
        stored = store.upsertFact(proposal, evidence, source="user_answer", policy={})
        if stored.get("status") == "rejected":
            outcomes.append({"kind": "fact_persistence", "status": "rejected", "fact_id": stored.get("fact_id"), "result": stored})
            continue
        confirmation = _interpretation_proposal(stored["fact_id"], interpretation, context, answer, question_subject_id, exact_fact_text)
        verified = store.verifyFact(
            stored["fact_id"],
            confirmation=confirmation,
            source="user_confirmation",
        )
        stored_fact = {"fact_id": stored["fact_id"], "verification_state": verified["verification_state"], "text": exact_fact_text}
        stored_facts.append(stored_fact)
        outcomes.append({"kind": "fact_confirmation", "status": "persisted", "fact_id": stored["fact_id"], "verification_state": verified["verification_state"]})
        if verified["verification_state"] == "user_verified":
            for requirement_id in context["selected_requirement_ids"]:
                store.recordJobMatch(
                    current_job_id(workspace),
                    requirement_id,
                    [stored["fact_id"]],
                    "verified_fact_match",
                    {"source": "resume_cli.resolve", "question_id": question_subject_id, "user_confirmed": True},
                )

    outcomes.extend(_record_requirement_resolution_outcomes(store, current_job_id(workspace), interpretation, context, question_subject_id))
    refreshed_match = run_match(workspace).get("match_result", {})
    interaction_refs = _interaction_refs(interactions)
    record_latest_run_snapshot(
        workspace,
        "RESOLVE_GAPS",
        {
            "facts_verified": [fact["fact_id"] for fact in stored_facts if fact.get("verification_state") == "user_verified"],
            "question_answer_log_refs": interaction_refs,
        },
    )
    return {
        "status": "ok",
        "exit_code": 0,
        "question": question_text,
        "interpretation": interpretation,
        "fact": stored_facts[0] if stored_facts else {},
        "facts": stored_facts,
        "stored_facts": stored_facts,
        "resolution_outcomes": outcomes,
        "interactions": [item.get("interaction", {}) for item in interactions if isinstance(item, dict)],
        "question_answer_log_refs": interaction_refs,
        "match_result": refreshed_match,
    }


def resolution_context(match_result: JsonObject, facts: list[JsonObject], config: JsonObject) -> JsonObject:
    selection = getUnresolvedRequirements(match_result, config)
    if selection.get("status") != "ok":
        return {
            "status": "error",
            "exit_code": DOMAIN_VALIDATION_EXIT,
            "errors": _core_errors_or_default(selection, "unresolved_selection_failed", "core unresolved requirement selection failed", "match.requirements"),
        }
    ranked = selection.get("ranked_unresolved_requirements") or selection.get("unresolved_requirements") or []
    selected = selection.get("selected_requirement") if isinstance(selection.get("selected_requirement"), dict) else None
    if selected is None and ranked:
        selected = ranked[0]
    if not isinstance(selected, dict):
        return {
            "status": "no_unresolved",
            "exit_code": SUCCESS_EXIT,
            "selected_requirement_ids": [],
            "requirement": None,
            "selection": selection,
            "already_verified_fact_ids": [str(fact.get("fact_id")) for fact in facts if fact.get("fact_id")],
        }
    requirement_id = str(selected.get("requirement_id") or "")
    topic = selected.get("topic") if selected.get("topic") else selected.get("concept")
    if not requirement_id or not topic:
        return _error("validation_error", "core selected requirement must include requirement_id and topic or concept", ref="match.requirements")
    return {
        "status": "ok",
        "exit_code": SUCCESS_EXIT,
        "selected_requirement_ids": [requirement_id],
        "topic": topic,
        "concept": selected.get("concept"),
        "requirement": selected,
        "selection": selection,
        "unresolved_requirements": ranked,
        "already_verified_fact_ids": [str(fact.get("fact_id")) for fact in facts if fact.get("fact_id")],
    }


def _record_answer(store: Any, question_subject_id: str, question_text: str, answer: str, interpretation: JsonObject) -> JsonObject:
    return store.recordInteraction(
        "answer_recorded",
        question_subject_id,
        {"question": question_text, "answer": answer},
        {
            "outcome": interpretation.get("outcome") or interpretation.get("polarity"),
            "fact_proposal_count": len(interpretation.get("fact_proposals", [])) if isinstance(interpretation.get("fact_proposals"), list) else 0,
            "requirement_resolution_proposals": interpretation.get("requirement_resolution_proposals", []),
        },
    )


def _record_requirement_resolution_outcomes(
    store: Any,
    job_id: str,
    interpretation: JsonObject,
    context: JsonObject,
    question_subject_id: str,
) -> list[JsonObject]:
    outcomes: list[JsonObject] = []
    for resolution in interpretation.get("requirement_resolution_proposals", []):
        if not isinstance(resolution, dict):
            continue
        state = str(resolution.get("suggested_state") or "")
        requirement_id = str(resolution.get("requirement_id") or "")
        if state not in {"explicitly_missing", "unknown", "not_applicable"} or not requirement_id:
            continue
        recorded = store.recordJobMatch(
            job_id,
            requirement_id,
            [],
            state,
            {
                "source": "resume_cli.resolve",
                "question_id": question_subject_id,
                "answer_outcome": interpretation.get("outcome") or interpretation.get("polarity"),
                "selected_requirement_ids": context.get("selected_requirement_ids", []),
                "confidence": resolution.get("confidence"),
                "user_confirmed": state == "explicitly_missing",
            },
        )
        outcomes.append(
            {
                "kind": "requirement_resolution",
                "status": "recorded",
                "requirement_id": requirement_id,
                "resolution_state": recorded.get("resolution_state", state),
                "job_match_id": recorded.get("job_match_id"),
            }
        )
    return outcomes


def _fact_proposals(interpretation: JsonObject, context: JsonObject) -> list[JsonObject]:
    proposals = []
    for proposal in interpretation.get("fact_proposals", []):
        if not isinstance(proposal, dict):
            continue
        text = str(proposal.get("text") or context.get("topic") or "")
        normalized_terms = [str(term).lower() for term in proposal.get("normalized_terms", []) if str(term).strip()]
        if not normalized_terms and context.get("topic"):
            normalized_terms = [str(context["topic"]).lower()]
        proposals.append(
            {
                "fact_id": str(proposal.get("fact_id") or _stable_short_id("fact", text)),
                "type": str(proposal.get("category") or proposal.get("type") or "experience"),
                "text": text,
                "normalized_terms": normalized_terms,
                "metadata": {"agent_proposal": proposal, "selected_requirement_ids": context.get("selected_requirement_ids", [])},
            }
        )
    return proposals


def _answer_evidence(answer: str, interpretation: JsonObject, context: JsonObject, question_subject_id: str) -> JsonObject:
    return {
        "source": "user_answer",
        "text": answer,
        "metadata": {
            "question_id": question_subject_id,
            "selected_requirement_ids": context.get("selected_requirement_ids", []),
            "evidence_proposals": interpretation.get("evidence_proposals", []),
        },
    }


def _interpretation_proposal(
    fact_id: str,
    interpretation: JsonObject,
    context: JsonObject,
    answer: str,
    question_subject_id: str,
    fact_text: str,
) -> JsonObject:
    evidence = interpretation.get("evidence_proposals", [])
    source_id = None
    if evidence and isinstance(evidence[0], dict):
        source_id = evidence[0].get("evidence_id")
    return {
        "factId": fact_id,
        "questionId": question_subject_id,
        "outcome": "affirmed",
        "confirmedValue": {"text": fact_text},
        "provenance": [
            {
                "source": "user_answer",
                "source_id": source_id,
                "text": answer,
                "metadata": {"selected_requirement_ids": context.get("selected_requirement_ids", [])},
            },
            {
                "source": "user_confirmation",
                "source_id": question_subject_id,
                "text": fact_text,
                "metadata": {"confirmed": True, "selected_requirement_ids": context.get("selected_requirement_ids", [])},
            },
        ],
    }


def _interaction_refs(interactions: list[JsonObject]) -> list[str]:
    refs = []
    for interaction in interactions:
        interaction_id = interaction.get("interaction_id") if isinstance(interaction, dict) else None
        if interaction_id:
            refs.append(f"career-store/interactions/{interaction_id}")
    return refs


def _agent_error(result: JsonObject, ref: str) -> JsonObject:
    return {
        "status": "error",
        "exit_code": DOMAIN_VALIDATION_EXIT,
        "errors": _core_errors_or_default(result, "agent_resolution_failed", "agent resolution step failed", ref),
        "agent_result": result,
    }


def _core_errors_or_default(result: JsonObject, code: str, message: str, ref: str) -> list[JsonObject]:
    errors = result.get("errors")
    if isinstance(errors, list) and errors:
        return [error for error in errors if isinstance(error, dict)]
    error = result.get("error")
    if isinstance(error, dict):
        return [{"code": str(error.get("code") or error.get("type") or code), "message": str(error.get("message") or message), "ref": str(error.get("ref") or error.get("field_path") or ref)}]
    return [{"code": code, "message": message, "ref": ref}]


def _error(code: str, message: str, *, ref: str) -> JsonObject:
    error = {"code": code, "message": message, "ref": ref, "offending_input_ref": ref}
    return {"status": "error", "exit_code": DOMAIN_VALIDATION_EXIT, "errors": [error], "error": {"type": code, "message": message}}


def _stable_short_id(prefix: str, text: str) -> str:
    digest = hashlib.sha256(json.dumps(text, sort_keys=True).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"
