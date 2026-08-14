"""Deterministic adapters from operation fixtures to validateChange inputs."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OPERATION_FIXTURES = ROOT / "fixtures" / "operations"

HONESTY_FIXTURE_FILES = (
    "invalid-unsupported-scale.json",
    "invalid-unsupported-management.json",
    "invalid-title-inflation.json",
    "invalid-years-inflation.json",
    "invalid-related-skill-overreach.json",
)

REJECTION_STATUSES = {"rejected", "error"}


BASE_RESUME = {
    "schema_version": "canonical-resume.v1",
    "resume_id": "resume_honesty_fixture_validate_change",
    "source": {"kind": "test_fixture"},
    "basics": {"name": "Daniel Candidate", "email": "candidate@example.com"},
    "experience": [
        {
            "id": "exp_1",
            "company": "Example SaaS",
            "title": "Senior Software Developer",
            "start_date": "2013-01",
            "end_date": "2017-12",
            "bullets": [
                "Built React applications.",
                "Led a small team of three developers.",
            ],
        }
    ],
    "skills": ["React", "TypeScript", "Node.js", "PostgreSQL", "Azure", "REST APIs"],
    "education": [],
    "provenance": [{"claim_id": "title_senior_developer", "source": "resume", "text": "Senior Software Developer"}],
    "verification_state": "source_stated",
}

JOB_MODEL = {
    "schema_version": "job-model.v1",
    "job_id": "job_honesty_fixture_validate_change",
    "requirements": [
        {
            "requirement_id": "req_react",
            "classification": "required",
            "concept": "React",
            "importance": "high",
            "weight": 10,
            "source_text": "Required React experience",
            "normalized_terms": ["react"],
        },
        {
            "requirement_id": "req_leadership",
            "classification": "preferred",
            "concept": "technical leadership",
            "importance": "medium",
            "weight": 3,
            "source_text": "Preferred technical leadership",
            "normalized_terms": ["leadership"],
        },
        {
            "requirement_id": "req_staff_title",
            "classification": "required",
            "concept": "Staff Software Engineer",
            "importance": "high",
            "weight": 10,
            "source_text": "Staff Software Engineer title",
            "normalized_terms": ["staff software engineer"],
        },
        {
            "requirement_id": "req_aws",
            "classification": "preferred",
            "concept": "AWS",
            "importance": "medium",
            "weight": 3,
            "source_text": "Preferred AWS experience",
            "normalized_terms": ["aws"],
        },
    ],
    "preferred": [],
    "industries": [],
    "domains": [],
    "terminology": [],
}

CAREER_FACTS = [
    {
        "fact_id": "fact_react_applications",
        "text": "Built React applications.",
        "verification_state": "source_stated",
        "evidence": [{"source": "resume", "text": "Built React applications."}],
    },
    {
        "fact_id": "fact_small_team",
        "text": "Led a small team of three developers.",
        "verification_state": "user_verified",
        "evidence": [{"source": "resume", "text": "Led a small team of three developers."}],
    },
    {
        "fact_id": "fact_actual_title",
        "text": "Formal employment title was Senior Software Developer, not Staff Software Engineer.",
        "verification_state": "source_stated",
        "evidence": [{"source": "resume", "text": "Senior Software Developer"}],
    },
    {
        "fact_id": "fact_aws_six_years",
        "text": "AWS experience, six years",
        "verification_state": "user_verified",
        "evidence": [{"source": "answer", "text": "about six years of AWS experience"}],
    },
    {
        "fact_id": "fact_azure",
        "text": "Azure cloud services experience.",
        "verification_state": "source_stated",
        "evidence": [{"source": "resume", "text": "Azure"}],
    },
]

_LINKS_BY_REASON = {
    "unsupported_scale": (["req_react"], ["fact_react_applications"]),
    "unsupported_management_scope": (["req_leadership"], ["fact_small_team"]),
    "title_inflation": (["req_staff_title"], ["fact_actual_title"]),
    "years_inflation": (["req_aws"], ["fact_aws_six_years"]),
    "related_skill_overreach": (["req_aws"], ["fact_azure"]),
}


def load_honesty_fixtures() -> list[dict[str, Any]]:
    return [load_operation_fixture(name) for name in HONESTY_FIXTURE_FILES]


def load_operation_fixture(filename: str) -> dict[str, Any]:
    path = OPERATION_FIXTURES / filename
    return json.loads(path.read_text(encoding="utf-8"))


def adapt_operation_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    requirement_ids, fact_ids = _LINKS_BY_REASON[fixture["expected_reason"]]
    return {
        "schema_version": "resume-change-operation.v1",
        "operation_id": f"op_{fixture['fixture_id'].replace('-', '_')}",
        "status": "proposed",
        "op": "replace",
        "path": fixture["target_path"],
        "reason": f"Run honesty fixture {fixture['fixture_id']} through validateChange.",
        "before": fixture["before"],
        "after": fixture["after"],
        "linked_requirement_ids": requirement_ids,
        "linked_fact_ids": fact_ids,
        "provenance": [{"source": "fixture", "fixture_id": fixture["fixture_id"]}],
    }


def build_validate_change_case(fixture: dict[str, Any]) -> dict[str, Any]:
    resume = copy.deepcopy(BASE_RESUME)
    _set_json_pointer(resume, fixture["target_path"], fixture["before"])
    return {
        "fixture": fixture,
        "canonical_resume": resume,
        "operation": adapt_operation_fixture(fixture),
        "job_model": copy.deepcopy(JOB_MODEL),
        "career_facts": copy.deepcopy(CAREER_FACTS),
        "policy": {"require_verified": True},
    }


def expected_reason_observed(fixture: dict[str, Any], validation_result: dict[str, Any]) -> bool:
    expected_reason = fixture["expected_reason"]
    for error in validation_result.get("errors", []):
        if error.get("code") == expected_reason:
            return True
        if expected_reason == "years_inflation" and error.get("code") == "unsupported_years_claim":
            return True
        if error.get("code") == "unsupported_guarded_claim":
            claims = set(error.get("details", {}).get("claims", []))
            if expected_reason == "unsupported_scale" and "unsupported_scale" in claims:
                return True
            if expected_reason == "unsupported_management_scope" and "unsupported_management" in claims:
                return True
            if expected_reason == "related_skill_overreach" and "aws" in claims:
                return True
    return False


def _set_json_pointer(document: dict[str, Any], pointer: str, value: Any) -> None:
    if not pointer.startswith("/"):
        raise ValueError(f"Expected JSON pointer path, got {pointer!r}")
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.lstrip("/").split("/")]
    current: Any = document
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    last = parts[-1]
    if isinstance(current, list):
        current[int(last)] = value
    else:
        current[last] = value
