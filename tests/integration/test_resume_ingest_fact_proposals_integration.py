"""Integration coverage for fixture-backed ingest, DTOs, and no fabrication."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
for package in ["resume-cli", "resume-core", "career-store", "resume-agent", "resume-render", "workflow"]:
    package_path = ROOT / package
    if str(package_path) not in sys.path:
        sys.path.insert(0, str(package_path))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import resume_cli  # noqa: E402
from career_store import openCareerStore  # noqa: E402
from resume_agent._schema_validation import validate_json_schema  # noqa: E402
from resume_core import CANONICAL_RESUME_SCHEMA, JOB_REQUIREMENT_SCHEMA  # noqa: E402


FIXTURES = ROOT / "fixtures"
MANIFEST = json.loads((FIXTURES / "fixture_manifest.json").read_text(encoding="utf-8"))
OFF_FIXTURE = MANIFEST["off_fixture_ingest_fixture"]
REQUIREMENT_KEYS = {
    "requirement_id",
    "classification",
    "concept",
    "importance",
    "weight",
    "source_text",
    "normalized_terms",
    "years",
}
FORBIDDEN_FABRICATION_STRINGS = {"Software Engineer", "Source Resume", "Software Developer"}


def run_cli(argv: list[str], cwd: Path) -> dict:
    result = resume_cli.main(argv=argv, cwd=cwd)
    if isinstance(result, int):
        return {"exit_code": result}
    return result


def field_value(value):
    return value.get("value") if isinstance(value, dict) else value


def expected_data(rel_path: str) -> dict:
    return json.loads((FIXTURES / rel_path).read_text(encoding="utf-8"))["data"]


def base_subset(base: dict, facts: list[dict]) -> dict:
    return {
        "title": field_value(base.get("title")),
        "basics": {key: field_value(value) for key, value in base.get("basics", {}).items()},
        "skills": [field_value(item) for item in base.get("skills", [])],
        "experience": [
            {
                "title": field_value(item.get("title")),
                "company": field_value(item.get("company")),
                "start_date": item.get("start_date"),
                "end_date": item.get("end_date"),
                "bullets": [field_value(bullet) for bullet in item.get("bullets", [])],
            }
            for item in base.get("experience", [])
        ],
        "education": [
            {
                "degree": field_value(item.get("degree")),
                "field": field_value(item.get("field")),
            }
            for item in base.get("education", [])
        ],
        "persisted_fact_ids": sorted(fact.get("fact_id") for fact in facts),
    }


def job_subset(job: dict) -> dict:
    return {
        "job_id": job.get("job_id"),
        "title": job.get("title"),
        "company": job.get("company"),
        "requirements": [{key: requirement.get(key) for key in REQUIREMENT_KEYS} for requirement in job.get("requirements", [])],
    }


def assert_resume_field(testcase: unittest.TestCase, value: object, path: str) -> None:
    testcase.assertIsInstance(value, dict, path)
    field = value if isinstance(value, dict) else {}
    testcase.assertIn("value", field, path)
    testcase.assertTrue(field.get("claim_id"), path)
    testcase.assertEqual(field.get("verification_state"), "source_stated", path)
    testcase.assertIsInstance(field.get("provenance"), list, path)
    testcase.assertTrue(field.get("provenance"), path)


def extraction_for_no_title_resume() -> dict:
    evidence = {
        "evidence_id": "ev_minimal_name",
        "text": "Taylor Morgan",
        "source_text": "Taylor Morgan",
        "span": {"start": 0, "end": 13},
        "lines": {"start": 1, "end": 1},
    }
    skill_evidence = {
        "evidence_id": "ev_minimal_skill",
        "text": "Skills: Documentation, QA triage.",
        "source_text": "Skills: Documentation, QA triage.",
        "span": {"start": 14, "end": 47},
        "lines": {"start": 2, "end": 2},
    }
    return {
        "schema_version": "resume-agent.proposal.v1",
        "proposal_type": "resume_semantic_extraction",
        "fact_proposals": [
            {
                "fact_id": "fact_minimal_name",
                "category": "name",
                "text": "Taylor Morgan",
                "normalized_terms": ["taylor morgan"],
                "source_evidence_ids": ["ev_minimal_name"],
                "evidence": [evidence],
                "verification_state": "source_stated",
                "confidence": 0.98,
                "review_required": True,
            },
            {
                "fact_id": "fact_minimal_documentation",
                "category": "skill",
                "text": "Documentation",
                "normalized_terms": ["documentation"],
                "source_evidence_ids": ["ev_minimal_skill"],
                "evidence": [skill_evidence],
                "verification_state": "source_stated",
                "confidence": 0.94,
                "review_required": True,
            },
        ],
        "source_evidence": [evidence, skill_evidence],
        "uncertainty": [],
    }


def user_visible_resume_strings(base: dict) -> list[str]:
    values: list[str] = []
    for item in base.get("basics", {}).values():
        if field_value(item):
            values.append(str(field_value(item)))
    for field in ["title", "summary"]:
        if field_value(base.get(field)):
            values.append(str(field_value(base.get(field))))
    for item in base.get("skills", []):
        if field_value(item):
            values.append(str(field_value(item)))
    for entry in base.get("experience", []):
        for key in ["title", "company"]:
            if field_value(entry.get(key)):
                values.append(str(field_value(entry.get(key))))
        for bullet in entry.get("bullets", []):
            if field_value(bullet):
                values.append(str(field_value(bullet)))
    return values


class ResumeIngestFactProposalPersistenceTests(unittest.TestCase):
    def test_off_fixture_resume_and_job_ingest_persist_fixture_defined_facts_and_artifacts(self):
        with tempfile.TemporaryDirectory(prefix="resume-ingest-facts-") as temp_name:
            workspace = Path(temp_name)

            run_cli(["init"], workspace)
            resume_result = run_cli(["ingest", str(FIXTURES / OFF_FIXTURE["resume_path"])], workspace)
            job_result = run_cli(["job", "ingest", str(FIXTURES / OFF_FIXTURE["job_path"])], workspace)

            self.assertEqual(resume_result.get("status"), "ok", resume_result)
            self.assertEqual(job_result.get("status"), "ok", job_result)
            self.assertEqual(set(resume_result.get("career_facts", [])), set(OFF_FIXTURE["required_fact_ids"]))

            store = openCareerStore(str(workspace / "data" / "career.db"))
            facts = store.searchFacts("", include_evidence=True).get("facts", [])
            facts_by_id = {fact["fact_id"]: fact for fact in facts}
            self.assertEqual(set(facts_by_id), set(OFF_FIXTURE["required_fact_ids"]))
            for fact_id in OFF_FIXTURE["required_fact_ids"]:
                with self.subTest(fact_id=fact_id):
                    fact = facts_by_id[fact_id]
                    self.assertEqual(fact["verification_state"], "source_stated")
                    self.assertTrue(fact.get("evidence"))
                    self.assertIn("source_span", fact["evidence"][0])

            base = json.loads((workspace / "resume" / "base.json").read_text(encoding="utf-8"))
            job = json.loads((workspace / "job" / "current.json").read_text(encoding="utf-8"))
            self.assertEqual(base_subset(base, facts), expected_data(OFF_FIXTURE["expected_base_path"]))
            self.assertEqual(job_subset(job), expected_data(OFF_FIXTURE["expected_job_path"]))

            serialized_outputs = json.dumps({"base": base, "job": job}, sort_keys=True).lower()
            for forbidden in OFF_FIXTURE["must_not_depend_on_terms"]:
                self.assertNotIn(forbidden.lower(), serialized_outputs)

    def test_persisted_base_and_job_requirements_conform_to_shared_dtos(self):
        with tempfile.TemporaryDirectory(prefix="resume-ingest-dto-") as temp_name:
            workspace = Path(temp_name)
            run_cli(["init"], workspace)
            run_cli(["ingest", str(FIXTURES / OFF_FIXTURE["resume_path"])], workspace)
            run_cli(["job", "ingest", str(FIXTURES / OFF_FIXTURE["job_path"])], workspace)

            base = json.loads((workspace / "resume" / "base.json").read_text(encoding="utf-8"))
            job = json.loads((workspace / "job" / "current.json").read_text(encoding="utf-8"))

            self.assertEqual(validate_json_schema(base, CANONICAL_RESUME_SCHEMA), [])
            assert_resume_field(self, base["basics"]["name"], "basics/name")
            assert_resume_field(self, base["title"], "title")
            for index, skill in enumerate(base["skills"]):
                assert_resume_field(self, skill, f"skills/{index}")
            for index, entry in enumerate(base["experience"]):
                assert_resume_field(self, entry["title"], f"experience/{index}/title")
                assert_resume_field(self, entry["company"], f"experience/{index}/company")
                for bullet_index, bullet in enumerate(entry["bullets"]):
                    assert_resume_field(self, bullet, f"experience/{index}/bullets/{bullet_index}")

            for requirement in job["requirements"]:
                with self.subTest(requirement=requirement["requirement_id"]):
                    self.assertEqual(set(requirement), REQUIREMENT_KEYS)
                    self.assertEqual(validate_json_schema(requirement, JOB_REQUIREMENT_SCHEMA), [])
                    self.assertNotIn("id", requirement)
                    self.assertNotIn("type", requirement)

    def test_resume_without_stated_title_or_experience_does_not_fabricate_base_content(self):
        source_text = "Taylor Morgan\nSkills: Documentation, QA triage.\nVolunteer\nCoordinated community workshops.\n"
        with tempfile.TemporaryDirectory(prefix="resume-ingest-no-fabrication-") as temp_name:
            workspace = Path(temp_name)
            resume_file = workspace / "minimal-resume.txt"
            resume_file.write_text(source_text, encoding="utf-8")
            run_cli(["init"], workspace)

            extraction = extraction_for_no_title_resume()
            with mock.patch.object(resume_cli, "extractResumeSemantics", return_value=extraction):
                result = run_cli(["ingest", str(resume_file)], workspace)

            self.assertEqual(result.get("status"), "ok", result)
            base = json.loads((workspace / "resume" / "base.json").read_text(encoding="utf-8"))
            serialized_base = json.dumps(base, sort_keys=True)
            for forbidden in FORBIDDEN_FABRICATION_STRINGS:
                self.assertNotIn(forbidden, serialized_base)
            self.assertNotIn("title", base)
            self.assertEqual(base.get("experience"), [])

            support_text = source_text + json.dumps(extraction, sort_keys=True)
            for value in user_visible_resume_strings(base):
                with self.subTest(value=value):
                    self.assertIn(value, support_text)


if __name__ == "__main__":
    unittest.main()
