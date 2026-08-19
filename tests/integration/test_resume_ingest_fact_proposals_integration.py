"""Integration coverage for resume ingest fact proposal persistence."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
for package in ["resume-cli", "resume-core", "career-store", "resume-agent", "resume-render", "workflow"]:
    package_path = ROOT / package
    if str(package_path) not in sys.path:
        sys.path.insert(0, str(package_path))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import resume_cli  # noqa: E402
from career_store import openCareerStore  # noqa: E402


OFF_FIXTURE_RESUME = "Jordan Lee\nData Platform Engineer\nBuilt Python Spark pipelines and Kafka streaming jobs for analytics.\n"
EXPECTED_FACT_IDS = {
    "fact_offfixture_name",
    "fact_offfixture_title",
    "fact_python",
    "fact_spark",
    "fact_kafka",
}


class ResumeIngestFactProposalPersistenceTests(unittest.TestCase):
    def test_off_fixture_resume_persists_exact_extraction_proposal_facts(self):
        with tempfile.TemporaryDirectory(prefix="resume-ingest-facts-") as temp_name:
            workspace = Path(temp_name)
            resume_file = workspace / "off-fixture-resume.txt"
            resume_file.write_text(OFF_FIXTURE_RESUME, encoding="utf-8")

            resume_cli.main(argv=["init"], cwd=workspace)
            result = resume_cli.main(argv=["ingest", str(resume_file)], cwd=workspace)

            self.assertEqual(result.get("status"), "ok", result)
            self.assertEqual(set(result.get("career_facts", [])), EXPECTED_FACT_IDS)

            store = openCareerStore(str(workspace / "data" / "career.db"))
            facts = store.searchFacts("", include_evidence=True).get("facts", [])
            facts_by_id = {fact["fact_id"]: fact for fact in facts}

            self.assertEqual(set(facts_by_id), EXPECTED_FACT_IDS)
            self.assertNotIn("fact_azure", facts_by_id)
            for fact_id in EXPECTED_FACT_IDS:
                with self.subTest(fact_id=fact_id):
                    fact = facts_by_id[fact_id]
                    self.assertEqual(fact["verification_state"], "source_stated")
                    self.assertTrue(fact.get("evidence"))
                    self.assertIn("source_span", fact["evidence"][0])

            base = json.loads((workspace / "resume" / "base.json").read_text(encoding="utf-8"))
            serialized_base = json.dumps(base, sort_keys=True).lower()
            for expected in ["python", "spark", "kafka"]:
                self.assertIn(expected, serialized_base)
            self.assertNotIn("azure", serialized_base)


if __name__ == "__main__":
    unittest.main()
