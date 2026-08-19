"""Failure-path coverage for resume-cli ingest-domain guardrails."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GUARDRAIL = ROOT / "tools" / "resume_cli_guardrails.py"


def run_guardrail(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GUARDRAIL), "--root", str(root)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def make_temp_repo() -> Path:
    temp = Path(tempfile.mkdtemp(prefix="resume-cli-domain-regrowth-"))
    (temp / "resume-cli" / "resume_cli").mkdir(parents=True)
    shutil.copy2(ROOT / "resume-cli" / "cli_surface.json", temp / "resume-cli" / "cli_surface.json")
    return temp


class ResumeCliDomainRegrowthGuardrailTests(unittest.TestCase):
    def test_month_table_and_date_regex_are_hard_blocked_with_core_owner_message(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-cli" / "resume_cli" / "bad_dates.py").write_text(
                "import re\n"
                "MONTH_NAMES = ['January', 'February', 'March']\n"
                "DATE_RE = re.compile(r'January \\d{4}')\n",
                encoding="utf-8",
            )

            result = run_guardrail(temp)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("month-name/date parsing table", result.stdout)
            self.assertIn("date-parsing regular expression", result.stdout)
            self.assertIn("resume-core dates.py", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_requirement_keyword_vocabulary_lists_are_hard_blocked_with_agent_core_message(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-cli" / "resume_cli" / "bad_requirements.py").write_text(
                "topic_keywords = ['React', 'TypeScript', 'Azure']\n",
                encoding="utf-8",
            )

            result = run_guardrail(temp)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requirement-keyword vocabulary list", result.stdout)
            self.assertIn("resume-agent proposals", result.stdout)
            self.assertIn("resume-core normalization", result.stdout)
        finally:
            shutil.rmtree(temp)

    def test_canonical_schema_version_construction_is_hard_blocked_but_surface_metadata_reads_remain_allowed(self):
        temp = make_temp_repo()
        try:
            (temp / "resume-cli" / "resume_cli" / "bad_schema.py").write_text(
                "job = {'schema_version': 'job-model.v1', 'requirements': []}\n"
                "resume = {'schema_version': 'canonical-resume.v1', 'experience': []}\n",
                encoding="utf-8",
            )

            result = run_guardrail(temp)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("canonical resume/job schema_version literal", result.stdout)
            self.assertIn("schema construction belongs to resume-core", result.stdout)

            surface = json.loads((temp / "resume-cli" / "cli_surface.json").read_text(encoding="utf-8"))
            self.assertIn("required_commands", surface)
        finally:
            shutil.rmtree(temp)


if __name__ == "__main__":
    unittest.main()
