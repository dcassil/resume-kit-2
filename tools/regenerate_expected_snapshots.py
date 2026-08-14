#!/usr/bin/env python3
"""Regenerate canonical data blocks for the 13 expected snapshot fixtures.

This script is intentionally read-only by default: it prints canonicalized data
blocks to stdout and does not overwrite files in fixtures/expected.
"""

from __future__ import annotations

import argparse
import copy
import importlib
import inspect
import json
from pathlib import Path
import sys
from typing import Any


CONFIG_HASH = "fixture-config-v1"
SNAPSHOT_SCHEMA_VERSION = "expected-snapshot-data-blocks.v1"
FIXTURE_CONFIG = {
    "policy": "strict",
    "requirement_id_prefix": "fixture_req",
    "section_order": ["basics", "summary", "skills", "experience", "education"],
    "max_experience": 2,
    "max_skills": 12,
    "max_bullets_per_role": 4,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root. Defaults to the current directory.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    _install_import_paths(root)

    from tests.support.snapshot_compare import canonical_json, canonicalize

    snapshots = generate_snapshots(root)
    payload = {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "config_hash": CONFIG_HASH,
        "snapshot_count": len(snapshots),
        "snapshots": snapshots,
    }
    print(canonical_json(canonicalize(payload)))
    return 0


def generate_snapshots(root: Path) -> dict[str, Any]:
    resume_core = importlib.import_module("resume_core")

    source_resume = _source_resume(root)
    source_job_a = _source_job(root, "job-a-staff-software-engineer.txt", "job-a")
    source_job_b = _source_job(root, "job-b-senior-full-stack-engineer.txt", "job-b")

    normalized_resume = _call(resume_core.normalizeResume, source_resume, FIXTURE_CONFIG)
    normalized_job_a = _call(resume_core.normalizeJobModel, source_job_a, FIXTURE_CONFIG)
    normalized_job_b = _call(resume_core.normalizeJobModel, source_job_b, FIXTURE_CONFIG)

    resume = normalized_resume["canonical_resume"]
    job_a = normalized_job_a["job_model"]
    job_b = normalized_job_b["job_model"]
    facts = _career_facts(root)
    aws_facts = [facts["fact_aws"]]
    aws_graphql_facts = [facts["fact_aws"], facts["fact_graphql"]]
    all_facts = [facts["fact_aws"], facts["fact_graphql"], facts["fact_architecture"]]

    initial_job_a_match = _call(resume_core.scoreMatch, resume, job_a, [], FIXTURE_CONFIG)
    post_aws_match = _call(resume_core.scoreMatch, resume, job_a, aws_facts, FIXTURE_CONFIG)
    post_graphql_match = _call(resume_core.scoreMatch, resume, job_a, aws_graphql_facts, FIXTURE_CONFIG)

    valid_operations = _valid_operations(resume_core, resume, job_a, all_facts)
    working_resume = copy.deepcopy(resume)
    applied_operations: list[dict[str, Any]] = []
    application_results: list[dict[str, Any]] = []
    for validation in valid_operations:
        validated = validation["validation_result"].get("validated_operation")
        if validated:
            applied = _call(resume_core.applyChange, working_resume, validated)
            application_results.append(applied)
            working_resume = applied["working_resume"]
            if applied.get("applied_operation"):
                applied_operations.append(applied["applied_operation"])

    final_job_a_match = _call(resume_core.scoreMatch, working_resume, job_a, all_facts, FIXTURE_CONFIG)
    job_b_initial_match = _call(resume_core.scoreMatch, resume, job_b, aws_graphql_facts, FIXTURE_CONFIG)
    selection_plan = _call(resume_core.rankResumeContent, working_resume, job_a, final_job_a_match["match_result"], FIXTURE_CONFIG)
    rejected_operations = _rejected_operations(resume_core, root, resume, job_a, all_facts)
    final_validation = _call(resume_core.validateFinalResume, working_resume, job_a, all_facts, FIXTURE_CONFIG, applied_operations)

    run_manifest = _run_manifest(
        resume,
        job_a,
        initial_job_a_match,
        final_job_a_match,
        valid_operations,
        rejected_operations,
        final_validation,
    )
    audit_report = _audit_report(
        root,
        normalized_resume,
        normalized_job_a,
        normalized_job_b,
        valid_operations,
        rejected_operations,
        final_validation,
        run_manifest,
    )

    return {
        "audit-report": audit_report,
        "final-job-a-match": final_job_a_match,
        "initial-job-a-match": initial_job_a_match,
        "job-b-initial-match": job_b_initial_match,
        "normalized-job-a": normalized_job_a,
        "normalized-job-b": normalized_job_b,
        "normalized-resume": normalized_resume,
        "post-aws-match": post_aws_match,
        "post-graphql-match": post_graphql_match,
        "rejected-operations": {
            "schema_version": "snapshot.rejected-operations.v1",
            "operations": rejected_operations,
        },
        "run-manifest": run_manifest,
        "selection-plan": selection_plan,
        "valid-operations": {
            "schema_version": "snapshot.valid-operations.v1",
            "operations": valid_operations,
            "application_results": application_results,
            "applied_operation_ids": [item.get("operation_id") for item in applied_operations],
            "working_resume": working_resume,
        },
    }


def _install_import_paths(root: Path) -> None:
    for relative in ("", "resume-core"):
        path = str(root / relative) if relative else str(root)
        if path not in sys.path:
            sys.path.insert(0, path)


def _call(function: Any, *args: Any) -> Any:
    result = function(*args)
    if inspect.isawaitable(result):
        import asyncio

        return asyncio.run(result)
    return result


def _source_resume(root: Path) -> dict[str, Any]:
    text = (root / "fixtures" / "resumes" / "resume-main.txt").read_text(encoding="utf-8")
    lines = [line.rstrip() for line in text.splitlines()]
    summary = _section(lines, "Summary", "Experience").strip()
    experience_text = _section(lines, "Experience", "Skills")
    skills_text = _section(lines, "Skills", "Education").strip()
    education_text = _section(lines, "Education", None).strip()

    experiences = _parse_experience(experience_text)
    skills = [
        _claim_field(f"skill_{_slug(skill)}", skill, "resume")
        for skill in [item.strip() for item in skills_text.split(",") if item.strip()]
    ]
    return {
        "schema_version": "canonical-resume.v1",
        "resume_id": "resume-main",
        "source": {"kind": "fixture", "path": "fixtures/resumes/resume-main.txt"},
        "basics": {"name": lines[0], "headline": lines[1]},
        "summary": _claim_field("summary_main", summary, "resume"),
        "experience": experiences,
        "skills": skills,
        "education": [{"id": "education_1", "text": education_text}],
        "provenance": [{"claim_id": "summary_main", "source": "resume", "text": summary}],
        "verification_state": "source_stated",
    }


def _parse_experience(text: str) -> list[dict[str, Any]]:
    lines = [item.rstrip() for item in text.splitlines() if item.strip()]
    parsed: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        company, title = lines[index].split(" - ", 1)
        start_date, end_date = _split_date_range(lines[index + 1])
        index += 2
        bullets: list[dict[str, Any]] = []
        while index < len(lines) and not _is_role_header(lines, index):
            bullet_text = lines[index].lstrip("*-\u25e6 ").strip()
            if bullet_text:
                bullets.append(_claim_field(f"experience_{len(parsed) + 1}_bullet_{len(bullets) + 1}", bullet_text, "resume"))
            index += 1
        parsed.append(
            {
                "id": f"experience_{len(parsed) + 1}",
                "company": company,
                "title": title,
                "start_date": start_date,
                "end_date": end_date,
                "bullets": bullets,
            }
        )
    return parsed


def _is_role_header(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines) or " - " not in lines[index]:
        return False
    marker = lines[index].lstrip()[:1]
    if marker in {"*", "-", "\u25e6"}:
        return False
    return bool(_split_date_range(lines[index + 1])[1])


def _split_date_range(value: str) -> tuple[str, str]:
    if " - " in value:
        start, end = value.split(" - ", 1)
        return start.strip(), end.strip()
    if " to " in value:
        start, end = value.split(" to ", 1)
        return start.strip(), end.strip()
    return value.strip(), ""


def _source_job(root: Path, filename: str, job_id: str) -> dict[str, Any]:
    text = (root / "fixtures" / "jobs" / filename).read_text(encoding="utf-8")
    lines = [line.rstrip() for line in text.splitlines()]
    requirement_start = next(index for index, line in enumerate(lines) if line.lower().startswith("required"))
    return {
        "schema_version": "job-model.v1",
        "job_id": job_id,
        "title": lines[0],
        "company": lines[1],
        "source": {"kind": "fixture", "path": f"fixtures/jobs/{filename}"},
        "raw_description": "\n".join(lines),
        "requirements": "\n".join(lines[requirement_start:]),
    }


def _career_facts(root: Path) -> dict[str, dict[str, Any]]:
    answers = {
        "aws": (root / "fixtures" / "answers" / "aws.txt").read_text(encoding="utf-8").strip(),
        "graphql": (root / "fixtures" / "answers" / "graphql.txt").read_text(encoding="utf-8").strip(),
        "architecture": (root / "fixtures" / "answers" / "architecture.txt").read_text(encoding="utf-8").strip(),
    }
    return {
        "fact_aws": {
            "fact_id": "fact_aws",
            "text": "AWS experience, about six years, mainly EC2, S3, Lambda, RDS, and IAM.",
            "normalized_terms": ["aws", "amazon web services", "six years", "ec2", "s3", "lambda", "rds", "iam"],
            "verification_state": "user_verified",
            "evidence": [{"source": "answer_fixture", "source_id": "answer-aws", "text": answers["aws"]}],
        },
        "fact_graphql": {
            "fact_id": "fact_graphql",
            "text": "GraphQL APIs in production, around five years.",
            "normalized_terms": ["graphql", "graphql api", "five years", "production"],
            "verification_state": "user_verified",
            "evidence": [{"source": "answer_fixture", "source_id": "answer-graphql", "text": answers["graphql"]}],
        },
        "fact_architecture": {
            "fact_id": "fact_architecture",
            "text": "Designed APIs and application architecture for more than ten years; no formal Staff Engineer title.",
            "normalized_terms": ["api architecture", "application architecture", "ten years", "staff title absent"],
            "verification_state": "user_verified",
            "evidence": [{"source": "answer_fixture", "source_id": "answer-architecture", "text": answers["architecture"]}],
        },
    }


def _valid_operations(resume_core: Any, resume: dict[str, Any], job_model: dict[str, Any], facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    operations = [
        {
            "schema_version": "resume-change-operation.v1",
            "operation_id": "op_add_aws_skill",
            "status": "proposed",
            "op": "insert",
            "path": "/skills/-",
            "reason": "Add AWS only from the user-verified AWS answer fixture.",
            "before": None,
            "after": "AWS",
            "linked_requirement_ids": _requirement_ids(job_model, "aws"),
            "linked_fact_ids": ["fact_aws"],
            "provenance": [{"source": "fixture_generator", "text": "answer-aws"}],
        },
        {
            "schema_version": "resume-change-operation.v1",
            "operation_id": "op_add_graphql_skill",
            "status": "proposed",
            "op": "insert",
            "path": "/skills/-",
            "reason": "Add GraphQL only from the user-verified GraphQL answer fixture.",
            "before": None,
            "after": "GraphQL",
            "linked_requirement_ids": _requirement_ids(job_model, "graphql"),
            "linked_fact_ids": ["fact_graphql"],
            "provenance": [{"source": "fixture_generator", "text": "answer-graphql"}],
        },
        {
            "schema_version": "resume-change-operation.v1",
            "operation_id": "op_rewrite_api_architecture",
            "status": "proposed",
            "op": "rewrite",
            "path": "/experience/0/bullets/1",
            "reason": "Clarify architecture wording from the user-verified architecture answer fixture.",
            "before": resume["experience"][0]["bullets"][1],
            "after": {
                **resume["experience"][0]["bullets"][1],
                "value": "Designed REST APIs and application architecture for distributed product systems.",
            },
            "linked_requirement_ids": _requirement_ids(job_model, "api architecture"),
            "linked_fact_ids": ["fact_architecture"],
            "provenance": [{"source": "fixture_generator", "text": "answer-architecture"}],
        },
    ]
    return [
        {
            "operation": operation,
            "validation_result": _call(resume_core.validateChange, resume, operation, job_model, facts, FIXTURE_CONFIG),
        }
        for operation in operations
    ]


def _rejected_operations(
    resume_core: Any,
    root: Path,
    resume: dict[str, Any],
    job_model: dict[str, Any],
    facts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rejected: list[dict[str, Any]] = []
    for path in sorted((root / "fixtures" / "operations").glob("*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        target_path = fixture["target_path"]
        operation_path = "/skills/-" if target_path == "/skills" else target_path
        operation = {
            "schema_version": "resume-change-operation.v1",
            "operation_id": fixture["fixture_id"],
            "status": "proposed",
            "op": "insert" if operation_path.endswith("/-") else "rewrite",
            "path": operation_path,
            "reason": fixture["notes"],
            "before": None if operation_path.endswith("/-") else fixture["before"],
            "after": fixture["after"],
            "linked_requirement_ids": _requirement_ids(job_model, fixture["after"]),
            "linked_fact_ids": [],
            "provenance": [{"source": "operation_fixture", "source_id": fixture["fixture_id"], "text": fixture["notes"]}],
        }
        rejected.append(
            {
                "operation_fixture": fixture,
                "operation": operation,
                "validation_result": _call(resume_core.validateChange, resume, operation, job_model, facts, FIXTURE_CONFIG),
            }
        )
    return rejected


def _run_manifest(
    resume: dict[str, Any],
    job_model: dict[str, Any],
    initial_match: dict[str, Any],
    final_match: dict[str, Any],
    valid_operations: list[dict[str, Any]],
    rejected_operations: list[dict[str, Any]],
    final_validation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "run-manifest.fixture.v1",
        "run_id": "fixture-run-job-a",
        "config_hash": CONFIG_HASH,
        "base_resume_id": resume.get("resume_id"),
        "job_id": job_model.get("job_id"),
        "schema_versions": {
            "canonical_resume": resume.get("schema_version"),
            "job": job_model.get("schema_version"),
            "match": final_match.get("match_result", {}).get("schema_version"),
        },
        "matching_algorithm_version": final_match.get("match_result", {}).get("algorithm_version"),
        "initial_score": initial_match.get("match_result", {}).get("score_percent"),
        "final_score": final_match.get("match_result", {}).get("score_percent"),
        "facts_verified": ["fact_aws", "fact_graphql", "fact_architecture"],
        "operations_applied": [
            item["operation"]["operation_id"]
            for item in valid_operations
            if item["validation_result"].get("status") == "ok"
        ],
        "operations_rejected": [item["operation"]["operation_id"] for item in rejected_operations],
        "validation_status": final_validation.get("status"),
        "output_artifact_paths": [],
    }


def _audit_report(
    root: Path,
    normalized_resume: dict[str, Any],
    normalized_job_a: dict[str, Any],
    normalized_job_b: dict[str, Any],
    valid_operations: list[dict[str, Any]],
    rejected_operations: list[dict[str, Any]],
    final_validation: dict[str, Any],
    run_manifest: dict[str, Any],
) -> dict[str, Any]:
    fixture_manifest = json.loads((root / "fixtures" / "fixture_manifest.json").read_text(encoding="utf-8"))
    return {
        "schema_version": "audit-report.fixture.v1",
        "run_identity": run_manifest["run_id"],
        "config_hash": CONFIG_HASH,
        "fixture_set_id": fixture_manifest["fixture_set_id"],
        "source_refs": {
            "resume": "fixtures/resumes/resume-main.txt",
            "jobs": ["fixtures/jobs/job-a-staff-software-engineer.txt", "fixtures/jobs/job-b-senior-full-stack-engineer.txt"],
            "answers": ["fixtures/answers/aws.txt", "fixtures/answers/graphql.txt", "fixtures/answers/architecture.txt"],
        },
        "normalized_refs": {
            "resume_id": normalized_resume.get("canonical_resume", {}).get("resume_id"),
            "job_ids": [
                normalized_job_a.get("job_model", {}).get("job_id"),
                normalized_job_b.get("job_model", {}).get("job_id"),
            ],
        },
        "operation_validation": {
            "accepted": [item["operation"]["operation_id"] for item in valid_operations if item["validation_result"].get("status") == "ok"],
            "rejected": [item["operation"]["operation_id"] for item in rejected_operations],
        },
        "final_validation_status": final_validation.get("status"),
        "sensitive_raw_data_omitted": True,
    }


def _requirement_ids(job_model: dict[str, Any], text: str) -> list[str]:
    normalized = _normalize_text(text)
    ids = []
    for requirement in [*job_model.get("requirements", []), *job_model.get("preferred", [])]:
        haystack = _normalize_text(
            " ".join(
                [
                    str(requirement.get("concept", "")),
                    str(requirement.get("source_text", "")),
                    " ".join(str(item) for item in requirement.get("normalized_terms", [])),
                ]
            )
        )
        if normalized and normalized in haystack:
            ids.append(requirement["requirement_id"])
    return sorted(set(ids))


def _section(lines: list[str], start: str, end: str | None) -> str:
    start_index = lines.index(start) + 1
    if end is None:
        end_index = len(lines)
    else:
        end_index = lines.index(end)
    return "\n".join(lines[start_index:end_index]).strip()


def _claim_field(claim_id: str, value: str, source: str) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "value": value,
        "provenance": [{"claim_id": claim_id, "source": source, "text": value}],
        "verification_state": "source_stated",
    }


def _slug(value: str) -> str:
    return "_".join(part for part in _normalize_text(value).split() if part)


def _normalize_text(value: str) -> str:
    return " ".join("".join(char.lower() if char.isalnum() else " " for char in str(value)).split())


if __name__ == "__main__":
    raise SystemExit(main())
