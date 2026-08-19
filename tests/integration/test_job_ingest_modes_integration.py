"""Integration coverage for CLI job ingest input modes and core normalization."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import resume_cli


JOB_TEXT = "Senior Engineer\nRequired: React.\nPreferred: AWS.\n"


def run_cli(argv: list[str], cwd: Path) -> dict:
    result = resume_cli.main(argv=argv, cwd=cwd)
    if isinstance(result, int):
        return {"exit_code": result}
    return result


def extraction_payload() -> dict:
    return {
        "schema_version": "resume-agent.proposal.v1",
        "proposal_type": "job_semantic_extraction",
        "job_id": "job_test",
        "title": {"value": "Senior Engineer"},
        "company": None,
        "source": {"kind": "raw_text", "source_id": "test"},
        "requirements": [
            {
                "requirement_id": "req_react",
                "classification": "required",
                "concept": "React",
                "importance": "high",
                "weight": 1.0,
                "source_text": "Required: React.",
                "normalized_terms": ["react"],
                "years": None,
            }
        ],
        "preferred": [
            {
                "requirement_id": "req_aws",
                "classification": "preferred",
                "concept": "AWS",
                "importance": "medium",
                "weight": 1.0,
                "source_text": "Preferred: AWS.",
                "normalized_terms": ["aws"],
                "years": None,
            }
        ],
        "requirement_proposals": [],
        "requirement_classification_proposals": [],
        "terminology": [],
        "source_evidence": [],
        "uncertainty": [],
    }


def requirement_keys(job: dict) -> set[str]:
    return set().union(*(set(item) for item in [*job.get("requirements", []), *job.get("preferred", [])]))


class JobIngestModesIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        self.job_file = self.workspace / "job.txt"
        self.job_file.write_text(JOB_TEXT, encoding="utf-8")
        run_cli(["init"], self.workspace)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def ingest_with(self, arg: str) -> tuple[dict, dict]:
        with mock.patch.object(resume_cli, "extractJobSemantics", return_value=copy.deepcopy(extraction_payload())):
            result = run_cli(["job", "ingest", arg], self.workspace)
        job = json.loads((self.workspace / "job" / "current.json").read_text(encoding="utf-8"))
        return result, job

    def test_file_url_and_pasted_text_inputs_share_validated_artifact_shape(self):
        file_result, file_job = self.ingest_with(str(self.job_file))
        with mock.patch.object(resume_cli, "_fetch_url_text", return_value=JOB_TEXT):
            url_result, url_job = self.ingest_with("https://example.test/jobs/1")
        pasted_result, pasted_job = self.ingest_with(JOB_TEXT)

        self.assertEqual(file_result["status"], "ok")
        self.assertEqual(url_result["status"], "ok")
        self.assertEqual(pasted_result["status"], "ok")
        self.assertEqual(set(file_job), set(url_job))
        self.assertEqual(set(file_job), set(pasted_job))
        self.assertEqual(requirement_keys(file_job), {"requirement_id", "classification", "concept", "importance", "weight", "source_text", "normalized_terms", "years"})
        for job in [file_job, url_job, pasted_job]:
            self.assertTrue({"required", "preferred"} <= {item["classification"] for item in job["requirements"]})
            self.assertEqual({item["requirement_id"] for item in job["preferred"]}, {"req_aws"})

    def test_path_precedence_reads_existing_http_named_file_before_url_detection(self):
        http_named = self.workspace / "https:example.test-job"
        http_named.write_text(JOB_TEXT, encoding="utf-8")
        with mock.patch.object(resume_cli, "_fetch_url_text", side_effect=AssertionError("fetcher must not be called")):
            result, job = self.ingest_with(str(http_named))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(job["source"]["kind"], "raw_text")

    def test_url_fetch_failure_returns_typed_error_without_fallback_artifact(self):
        with mock.patch.object(
            resume_cli,
            "_fetch_url_text",
            side_effect=resume_cli.JobInputResolutionError("job_url_fetch_failed", "network unavailable", "job_url"),
        ):
            result = run_cli(["job", "ingest", "https://example.test/fail"], self.workspace)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(result["errors"][0]["code"], "job_url_fetch_failed")
        self.assertEqual(json.loads((self.workspace / "job" / "current.json").read_text(encoding="utf-8")), {})

    def test_empty_and_error_extraction_return_typed_failure_without_fallback_content(self):
        empty = {"schema_version": "resume-agent.proposal.v1", "proposal_type": "job_semantic_extraction", "requirements": [], "preferred": []}
        with mock.patch.object(resume_cli, "extractJobSemantics", return_value=empty):
            empty_result = run_cli(["job", "ingest", str(self.job_file)], self.workspace)
        self.assertEqual(empty_result["status"], "error")
        self.assertEqual(empty_result["errors"][0]["code"], "empty_job_extraction")
        self.assertEqual(json.loads((self.workspace / "job" / "current.json").read_text(encoding="utf-8")), {})

        failed = {"status": "error", "error": {"type": "provider_error", "message": "adapter failed"}}
        with mock.patch.object(resume_cli, "extractJobSemantics", return_value=failed):
            failed_result = run_cli(["job", "ingest", str(self.job_file)], self.workspace)
        self.assertEqual(failed_result["status"], "error")
        self.assertEqual(failed_result["errors"][0]["code"], "provider_error")

    def test_persisted_requirement_dto_and_weights_are_core_config_driven(self):
        config_path = self.workspace / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["matching"]["weights"]["requiredSkills"] = 0.6
        config["matching"]["weights"]["preferredSkills"] = 0.2
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

        _, job = self.ingest_with(str(self.job_file))
        requirements = {item["requirement_id"]: item for item in job["requirements"]}
        self.assertEqual(set(requirements["req_react"]), {"requirement_id", "classification", "concept", "importance", "weight", "source_text", "normalized_terms", "years"})
        self.assertEqual(requirements["req_react"]["weight"], 20.0)
        self.assertEqual(requirements["req_aws"]["weight"], 6.0)
        self.assertNotEqual(requirements["req_react"]["weight"], extraction_payload()["requirements"][0]["weight"])


if __name__ == "__main__":
    unittest.main()
