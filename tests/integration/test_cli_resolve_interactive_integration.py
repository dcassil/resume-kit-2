"""Interactive resolve-loop coverage for resume-cli."""

from __future__ import annotations

import importlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from career_store import openCareerStore


ROOT = Path(__file__).resolve().parents[2]
RESUME_FIXTURE_TEXT = (ROOT / "fixtures" / "resumes" / "resume-main.txt").read_text(encoding="utf-8")
JOB_FIXTURE_TEXT = (ROOT / "fixtures" / "jobs" / "job-a-staff-software-engineer.txt").read_text(encoding="utf-8")


class RecordingTerminalIO:
    def __init__(self, answers: list[str], confirmations: list[bool]) -> None:
        self.answers = list(answers)
        self.confirmations = list(confirmations)
        self.questions: list[str] = []
        self.confirmation_summaries: list[str] = []

    def ask(self, question: str) -> str:
        self.questions.append(question)
        return self.answers.pop(0) if self.answers else ""

    def confirm(self, summary: str) -> bool:
        self.confirmation_summaries.append(summary)
        return self.confirmations.pop(0) if self.confirmations else False


class CliResolveInteractiveIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cli = importlib.import_module("resume_cli")
        self.resolve_module = importlib.import_module("resume_cli._resolve")
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_scripted_terminal_exchange_persists_store_verified_fact_and_interactions(self) -> None:
        resume_file = self.workspace / "resume-main.txt"
        job_file = self.workspace / "job-a-staff-software-engineer.txt"
        resume_file.write_text(RESUME_FIXTURE_TEXT, encoding="utf-8")
        job_file.write_text(JOB_FIXTURE_TEXT, encoding="utf-8")
        self.cli.main(argv=["init"], cwd=self.workspace)
        self.cli.main(argv=["ingest", str(resume_file)], cwd=self.workspace)
        self.cli.main(argv=["job", "ingest", str(job_file)], cwd=self.workspace)

        result = self.cli.main(
            argv=["resolve"],
            cwd=self.workspace,
            stdin="Yes. I have about six years of AWS experience, mainly EC2, S3, Lambda, RDS, and IAM.\nyes\n",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["fact"]["fact_id"], "fact_aws_six_years_services")
        self.assertEqual(result["fact"]["verification_state"], "user_verified")
        store = openCareerStore(str(self.workspace / "data" / "career.db"))
        persisted = store.getFact(result["fact"]["fact_id"])["fact"]
        self.assertEqual(persisted["verification_state"], "user_verified")
        interactions = store.listInteractions()["interactions"]
        interaction_types = {item["interaction_type"] for item in interactions}
        self.assertTrue({"question_asked", "answer_recorded", "fact_confirmed"} <= interaction_types)
        self.assertTrue(result["question_answer_log_refs"])
        self.assertIn("stored_facts", result)

    def test_declined_confirmation_persists_no_fact_and_records_outcome(self) -> None:
        io = RecordingTerminalIO(["Yes, I have used Terraform for four years."], [False])
        result = self._run_direct_resolve(io)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["facts"], [])
        self.assertEqual(result["resolution_outcomes"][0]["status"], "declined")
        self.assertIn("Used Terraform for four years", io.confirmation_summaries[0])
        store = openCareerStore(str(self.workspace / "data" / "career.db"))
        self.assertEqual(store.searchFacts("Terraform")["facts"], [])
        interactions = store.listInteractions()["interactions"]
        self.assertIn("fact_confirmed", {item["interaction_type"] for item in interactions})

    def test_negative_answer_records_requirement_resolution_without_verification_state(self) -> None:
        io = RecordingTerminalIO(["Only in school"], [])
        result = self._run_direct_resolve(io)

        self.assertEqual(result["facts"], [])
        outcomes = [item for item in result["resolution_outcomes"] if item["kind"] == "requirement_resolution"]
        self.assertEqual(outcomes[0]["requirement_id"], "req_terraform")
        self.assertEqual(outcomes[0]["resolution_state"], "explicitly_missing")
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn('"verification_state": "user_verified"', serialized)
        store = openCareerStore(str(self.workspace / "data" / "career.db"))
        self.assertEqual(store.searchFacts("Terraform")["facts"], [])
        self.assertTrue({"question_asked", "answer_recorded"} <= {item["interaction_type"] for item in store.listInteractions()["interactions"]})

    def test_terraform_affirmative_off_fixture_answer_persists_fact(self) -> None:
        io = RecordingTerminalIO(["Yes, I have used Terraform for four years."], [True])
        result = self._run_direct_resolve(io)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["fact"]["fact_id"], "fact_terraform_four_years")
        self.assertEqual(result["fact"]["verification_state"], "user_verified")
        self.assertIn("Used Terraform for four years", io.confirmation_summaries[0])
        store = openCareerStore(str(self.workspace / "data" / "career.db"))
        persisted = store.getFact("fact_terraform_four_years")["fact"]
        self.assertEqual(persisted["verification_state"], "user_verified")
        self.assertEqual(persisted["text"], "Used Terraform for four years")

    def _run_direct_resolve(self, io: RecordingTerminalIO) -> dict:
        question = {
            "status": "ok",
            "question_needed": True,
            "question_id": "question_terraform",
            "question": "What Terraform infrastructure-as-code experience do you have?",
            "target_ids": {"requirement_ids": ["req_terraform"], "fact_ids": []},
        }
        with mock.patch.object(self.resolve_module, "generateClarificationQuestion", return_value=question):
            return self.resolve_module.resolve(
                self.workspace,
                io,
                init_workspace=self._init_workspace,
                run_match=self._run_match,
                load_facts=self._load_facts,
                load_config=lambda workspace: {},
                paths_for_workspace=self._paths,
                record_latest_run_snapshot=lambda workspace, checkpoint, result: None,
                current_job_id=lambda workspace: "job_terraform",
            )

    def _init_workspace(self, workspace: Path) -> dict:
        self._paths(workspace)["data_dir"].mkdir(parents=True, exist_ok=True)
        openCareerStore(str(self._paths(workspace)["career_db"]))
        return {"status": "ok"}

    def _load_facts(self, workspace: Path) -> list[dict]:
        return list(openCareerStore(str(self._paths(workspace)["career_db"])).searchFacts("", include_evidence=True).get("facts", []))

    def _paths(self, workspace: Path) -> dict[str, Path]:
        return {"data_dir": workspace / "data", "career_db": workspace / "data" / "career.db"}

    def _run_match(self, workspace: Path) -> dict:
        del workspace
        requirement = {
            "requirement_id": "req_terraform",
            "classification": "required",
            "concept": "Terraform",
            "source_text": "Terraform infrastructure-as-code experience.",
            "normalized_terms": ["terraform"],
            "resolution_state": "unknown",
            "unresolved": True,
            "blocking": True,
            "score": 0,
            "max_score": 10,
            "evidence": [],
        }
        return {
            "status": "ok",
            "match_result": {
                "schema_version": "match-result.v1",
                "decision": "resolve_gaps",
                "can_continue": False,
                "requirement_results": [requirement],
                "unresolved_requirement_ids": ["req_terraform"],
                "preferred_unresolved_requirement_ids": [],
            },
        }


if __name__ == "__main__":
    unittest.main()
