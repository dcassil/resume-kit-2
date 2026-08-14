"""Contract-first tests for the future resume_core package."""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SURFACE = json.loads((ROOT / "resume-core" / "core_surface.json").read_text(encoding="utf-8"))
PUBLIC_FUNCTIONS = tuple(SURFACE["public_api"]["functions"])
PUBLIC_TYPES = tuple(SURFACE["public_api"]["types"])


CANONICAL_RESUME = {
    "schema_version": "test-1",
    "resume_id": "resume_contract_1",
    "source": {"kind": "test_fixture"},
    "basics": {"name": "Daniel Candidate", "email": "candidate@example.com"},
    "experience": [
        {
            "id": "exp_1",
            "company": "Example SaaS",
            "title": "Software Engineer",
            "start_date": "2019-01",
            "end_date": "2024-06",
            "bullets": [
                "Built React and TypeScript interfaces for multi-tenant SaaS workflows.",
                "Designed REST APIs and integration patterns.",
            ],
        }
    ],
    "skills": ["React", "TypeScript", "Node.js", "PostgreSQL", "Azure", "REST APIs", "Responsive web apps"],
    "education": [],
    "provenance": [{"claim_id": "skill_react", "source": "resume", "text": "React"}],
    "verification_state": "source_stated",
}

JOB_MODEL = {
    "schema_version": "test-1",
    "requirements": [
        {
            "requirement_id": "req_react",
            "classification": "required",
            "concept": "React",
            "importance": "high",
            "weight": 10,
            "source_text": "React",
            "normalized_terms": ["react"],
        },
        {
            "requirement_id": "req_aws",
            "classification": "preferred",
            "concept": "AWS",
            "importance": "medium",
            "weight": 3,
            "source_text": "AWS",
            "normalized_terms": ["aws"],
        },
    ],
}

CAREER_FACTS = [
    {
        "fact_id": "fact_react",
        "text": "React",
        "verification_state": "source_stated",
        "evidence": [{"source": "resume", "text": "React"}],
    }
]


def maybe_await(value):
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def load_core_module(test_case: unittest.TestCase):
    try:
        module = importlib.import_module("resume_core")
    except ModuleNotFoundError as exc:
        test_case.fail(
            "Expected importable package 'resume_core'. Implement the deterministic surfaces from "
            "resume-core/TEST_SPEC.md and resume-core/core_surface.json."
        )
        raise exc
    for function_name in PUBLIC_FUNCTIONS:
        test_case.assertTrue(callable(getattr(module, function_name, None)), f"resume_core must expose {function_name}().")
    for type_name in PUBLIC_TYPES:
        test_case.assertTrue(hasattr(module, type_name), f"resume_core must expose {type_name}.")
    return module


def serialized(result: dict) -> str:
    return json.dumps(result, sort_keys=True).lower()


class ResumeCoreSurfaceManifestTests(unittest.TestCase):
    def test_manifest_declares_exact_public_functions_and_types(self):
        self.assertEqual(
            PUBLIC_FUNCTIONS,
            (
                "normalizeResume",
                "validateResume",
                "sanitizeText",
                "normalizeJobModel",
                "scoreMatch",
                "getUnresolvedRequirements",
                "rankResumeContent",
                "validateChange",
                "applyChange",
                "validateGrounding",
                "validateFinalResume",
            ),
        )
        self.assertEqual(
            set(PUBLIC_TYPES),
            {
                "CanonicalResume",
                "ResumeField",
                "JobModel",
                "JobRequirement",
                "MatchResult",
                "ResolutionState",
                "ResumeChangeOperation",
                "VerificationState",
            },
        )

    def test_manifest_defines_contracts_for_every_surface(self):
        surfaces = {surface["name"]: surface for surface in SURFACE["surfaces"]}
        self.assertEqual(set(surfaces), set(PUBLIC_FUNCTIONS))
        for name, surface in surfaces.items():
            with self.subTest(surface=name):
                self.assertIn("input_contract", surface)
                self.assertIn("output_contract", surface)
                required_fields = set(surface["output_contract"]["required_fields"])
                self.assertTrue({"schema_version", "status"} <= required_fields)
                self.assertIn("must_not_include", surface["output_contract"])


class ResumeCoreDomainContractTests(unittest.TestCase):
    def setUp(self):
        self.core = load_core_module(self)

    def test_sanitization_is_deterministic_and_reports_without_changing_meaning(self):
        text = "Built\u00a0React interfaces with \u201cclean\u201d APIs.\x07"
        first = maybe_await(self.core.sanitizeText(text))
        second = maybe_await(self.core.sanitizeText(text))
        self.assertEqual(first, second)
        self.assertIn(first.get("status"), {"ok", "warning", "error"})
        self.assertIn("text", first)
        self.assertIn("warnings", first)
        self.assertIn("React", first.get("text", ""))

    def test_scoring_is_deterministic_and_keeps_missing_preferred_distinct(self):
        first = maybe_await(self.core.scoreMatch(CANONICAL_RESUME, JOB_MODEL, CAREER_FACTS, {"policy": "strict"}))
        second = maybe_await(self.core.scoreMatch(CANONICAL_RESUME, JOB_MODEL, CAREER_FACTS, {"policy": "strict"}))
        self.assertEqual(first, second)
        self.assertIn("match_result", first)
        match = first["match_result"]
        self.assertEqual(match["threshold"], 7.5)
        self.assertIn(match["decision"], {"continue", "resolve_gaps", "blocked"})
        self.assertEqual(match["can_continue"], match["decision"] == "continue")
        self.assertTrue(match["hardRequirementsResolved"])
        text = serialized(first)
        self.assertIn("req_react", text)
        self.assertIn("req_aws", text)
        self.assertNotIn("staff software engineer", text)
        self.assertNotRegex(text, r"\b20 million\b|\b30 engineers\b")

    def test_job_model_section_4_2_fields_are_deterministically_populated(self):
        source_job = {
            "title": "Senior Platform Engineer",
            "company": "Example SaaS",
            "requirements": [
                {
                    "requirement_id": "req_react",
                    "classification": "required",
                    "concept": "React",
                    "source_text": "Required React experience",
                    "normalized_terms": ["react"],
                },
                {
                    "requirement_id": "req_aws",
                    "classification": "preferred",
                    "concept": "AWS",
                    "source_text": "Preferred AWS experience",
                    "normalized_terms": ["aws"],
                },
            ],
        }
        first = maybe_await(self.core.normalizeJobModel(source_job))
        second = maybe_await(self.core.normalizeJobModel(source_job))
        self.assertEqual(first, second)
        self.assertEqual(first.get("status"), "ok", first)

        job_model = first["job_model"]
        self.assertEqual(job_model["seniority"], "senior")
        self.assertEqual(job_model["industries"], ["SaaS"])
        self.assertEqual(len(job_model["requirements"]), 1)
        self.assertEqual(len(job_model["preferred"]), 1)
        self.assertEqual(job_model["requirements"][0]["requirement_id"], "req_react")
        self.assertEqual(job_model["preferred"][0]["requirement_id"], "req_aws")
        self.assertTrue(job_model["terminology"])
        for term in job_model["terminology"]:
            self.assertTrue(term.get("surface"))
            self.assertTrue(term.get("canonical"))
            self.assertIn(term.get("source"), {"title", "requirement", "description"})

    def test_discovered_enum_membership_matches_restored_contract_sets(self):
        self.assertEqual(
            {state.value for state in self.core.VerificationState},
            {"source_stated", "user_verified", "imported", "inferred", "unknown"},
        )
        self.assertEqual(
            {state.value for state in self.core.ResolutionState},
            {
                "exact_match",
                "alias_match",
                "verified_fact_match",
                "related_match",
                "possible_match",
                "unknown",
                "explicitly_missing",
                "not_applicable",
            },
        )

        imported_resume = dict(CANONICAL_RESUME, verification_state="imported")
        imported = maybe_await(self.core.validateResume(imported_resume))
        self.assertEqual(imported.get("status"), "ok", imported)

        explicit_absence_resume = dict(CANONICAL_RESUME, verification_state="explicitly_missing")
        explicit_absence = maybe_await(self.core.validateResume(explicit_absence_resume))
        self.assertEqual(explicit_absence.get("status"), "error", explicit_absence)
        self.assertIn("invalid_verification_state", {error.get("code") for error in explicit_absence.get("errors", [])})
        self.assertNotIn("conflicted", {state.value for state in self.core.VerificationState})
        self.assertNotIn("conflicted", {state.value for state in self.core.ResolutionState})

    def test_discovered_validate_resume_enforces_schema_required_identity_fields(self):
        self.assertEqual(
            set(self.core.CANONICAL_RESUME_SCHEMA["required"]),
            {"schema_version", "resume_id", "source", "experience", "skills", "education"},
        )
        for field_name in ("resume_id", "source"):
            with self.subTest(field_name=field_name):
                resume = dict(CANONICAL_RESUME)
                del resume[field_name]
                result = maybe_await(self.core.validateResume(resume))
                missing_fields = {
                    error.get("field_path")
                    for error in result.get("errors", [])
                    if error.get("code") == "missing_field"
                }
                self.assertEqual(result.get("status"), "error", result)
                self.assertIn(field_name, missing_fields)

    def test_discovered_dates_canonicalize_and_reject_typed_failures(self):
        canonicalizing_resume = dict(
            CANONICAL_RESUME,
            experience=[
                {
                    "id": "exp_date_contract",
                    "company": "Example SaaS",
                    "title": "Software Engineer",
                    "start_date": "01/2019",
                    "end_date": "present",
                    "bullets": [],
                }
            ],
        )
        canonicalized = maybe_await(self.core.validateResume(canonicalizing_resume))
        self.assertEqual(canonicalized.get("status"), "ok", canonicalized)
        self.assertEqual(canonicalized["canonical_resume"]["experience"][0]["start_date"], "2019-01")
        self.assertIn("ambiguous_start_date", {warning.get("code") for warning in canonicalized.get("warnings", [])})

        invalid_resume = dict(
            CANONICAL_RESUME,
            experience=[
                {
                    "id": "exp_invalid_date_contract",
                    "company": "Example SaaS",
                    "title": "Software Engineer",
                    "start_date": "2019-13",
                    "bullets": [],
                }
            ],
        )
        invalid = maybe_await(self.core.validateResume(invalid_resume))
        self.assertEqual(invalid.get("status"), "error", invalid)
        self.assertIn("invalid_date", {error.get("code") for error in invalid.get("errors", [])})

        reversed_resume = dict(
            CANONICAL_RESUME,
            experience=[
                {
                    "id": "exp_reversed_date_contract",
                    "company": "Example SaaS",
                    "title": "Software Engineer",
                    "start_date": "2020-02",
                    "end_date": "2020-01",
                    "bullets": [],
                }
            ],
        )
        reversed_result = maybe_await(self.core.validateResume(reversed_resume))
        self.assertEqual(reversed_result.get("status"), "error", reversed_result)
        self.assertIn("reversed_range", {error.get("code") for error in reversed_result.get("errors", [])})

    def test_discovered_normalize_resume_sourceless_claims_stay_unknown(self):
        source_resume = {
            "schema_version": "canonical-resume.v1",
            "resume_id": "resume_contract_claim_default",
            "source": {"kind": "test_fixture"},
            "experience": [
                {
                    "id": "exp_contract_claim",
                    "company": "Example SaaS",
                    "title": "Software Engineer",
                    "bullets": ["Built React workflows."],
                }
            ],
            "skills": ["React"],
            "education": [],
            "provenance": [],
        }

        result = maybe_await(self.core.normalizeResume(source_resume))
        self.assertEqual(result.get("status"), "ok", result)
        bullet = result["canonical_resume"]["experience"][0]["bullets"][0]
        skill = result["canonical_resume"]["skills"][0]
        for field in (bullet, skill):
            self.assertEqual(field["provenance"], [])
            self.assertEqual(field["verification_state"], "unknown")
            self.assertNotEqual(field["verification_state"], "source_stated")

    def test_unverified_or_related_facts_do_not_validate_unsupported_change(self):
        operation = {
            "schema_version": "resume-change-operation.v1",
            "operation_id": "op_aws_inflation",
            "status": "proposed",
            "op": "insert",
            "path": "/skills/-",
            "reason": "Prefer AWS only when it is grounded in supplied facts.",
            "before": None,
            "after": "AWS, ten years",
            "linked_requirement_ids": ["req_aws"],
            "linked_fact_ids": ["fact_react"],
            "provenance": [{"source": "test"}],
        }
        result = maybe_await(self.core.validateChange(CANONICAL_RESUME, operation, JOB_MODEL, CAREER_FACTS, {"require_verified": True}))
        self.assertIn(result.get("status"), {"rejected", "error"})
        text = serialized(result)
        self.assertIn("aws", text)
        self.assertNotIn("validation_state\": \"validated", text)

    def test_change_operation_verbs_are_structurally_validated(self):
        def operation_for(verb):
            if verb == "insert":
                return {
                    "schema_version": "resume-change-operation.v1",
                    "operation_id": f"op_{verb}",
                    "status": "proposed",
                    "op": verb,
                    "path": "/skills/-",
                    "reason": "Exercise the canonical change operation verb set.",
                    "before": None,
                    "after": "React",
                    "linked_requirement_ids": ["req_react"],
                    "linked_fact_ids": ["fact_react"],
                    "provenance": [{"source": "test"}],
                }
            return {
                "schema_version": "resume-change-operation.v1",
                "operation_id": f"op_{verb}",
                "status": "proposed",
                "op": verb,
                "path": "/skills/0",
                "reason": "Exercise the canonical change operation verb set.",
                "before": "React",
                "after": "React",
                "linked_requirement_ids": ["req_react"],
                "linked_fact_ids": ["fact_react"],
                "provenance": [{"source": "test"}],
            }

        for verb in ("rewrite", "insert", "move"):
            with self.subTest(verb=verb):
                result = maybe_await(self.core.validateChange(CANONICAL_RESUME, operation_for(verb), JOB_MODEL, CAREER_FACTS, {}))
                self.assertEqual(result.get("status"), "ok", result)
                self.assertEqual(result["validated_operation"].get("op"), verb)

        for verb in ("add", "foo"):
            with self.subTest(verb=verb):
                operation = operation_for("insert")
                operation["op"] = verb
                result = maybe_await(self.core.validateChange(CANONICAL_RESUME, operation, JOB_MODEL, CAREER_FACTS, {}))
                self.assertEqual(result.get("status"), "rejected", result)
                error_codes = {error.get("code") for error in result.get("errors", [])}
                self.assertIn("invalid_op", error_codes)

    def test_change_operation_required_fields_and_status_are_structurally_validated(self):
        operation = {
            "schema_version": "resume-change-operation.v1",
            "operation_id": "op_missing_reason",
            "status": "proposed",
            "op": "insert",
            "path": "/skills/-",
            "before": None,
            "after": "React",
            "linked_requirement_ids": ["req_react"],
            "linked_fact_ids": ["fact_react"],
            "provenance": [{"source": "test"}],
        }
        result = maybe_await(self.core.validateChange(CANONICAL_RESUME, operation, JOB_MODEL, CAREER_FACTS, {}))
        self.assertEqual(result.get("status"), "rejected", result)
        missing_fields = {
            error.get("field_path")
            for error in result.get("errors", [])
            if error.get("code") == "missing_field"
        }
        self.assertIn("reason", missing_fields)

        operation["reason"] = "Exercise invalid status structural validation."
        operation["status"] = "done"
        result = maybe_await(self.core.validateChange(CANONICAL_RESUME, operation, JOB_MODEL, CAREER_FACTS, {}))
        self.assertEqual(result.get("status"), "rejected", result)
        error_codes = {error.get("code") for error in result.get("errors", [])}
        self.assertIn("invalid_status", error_codes)

    def test_apply_change_requires_validated_operation_and_preserves_base_resume(self):
        operation = {
            "operation_id": "op_bad",
            "status": "proposed",
            "path": "/summary",
            "before": None,
            "after": "Staff Software Engineer",
        }
        result = maybe_await(self.core.applyChange(CANONICAL_RESUME, operation))
        self.assertIn(result.get("status"), {"rejected", "error"})
        text = serialized(result)
        self.assertNotIn("base_resume_mutated", text)
        self.assertNotIn("staff software engineer", serialized(CANONICAL_RESUME))

    def test_final_validation_reports_grounding_and_match_result_without_rendering(self):
        result = maybe_await(self.core.validateFinalResume(CANONICAL_RESUME, JOB_MODEL, CAREER_FACTS, {"policy": "strict"}))
        self.assertIn(result.get("status"), {"pass", "fail", "error"})
        self.assertIn("match_result", result)
        text = serialized(result)
        self.assertNotRegex(text, r"\b(rendered_output|docx|pdf|sqlite|traceback)\b")


if __name__ == "__main__":
    unittest.main()
