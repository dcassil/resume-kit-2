"""Unit checks for core-owned resume construction from extraction proposals."""

from __future__ import annotations

import json
import unittest

from tests.unit.resume_core_test_utils import load_resume_core


resume_core = load_resume_core()


def _extraction() -> dict:
    return {
        "schema_version": "resume-agent.proposal.v1",
        "proposal_type": "resume_semantic_extraction",
        "requires_validation": True,
        "fact_proposals": [
            {
                "fact_id": "fact_name",
                "category": "name",
                "text": "Alex Rivera",
                "normalized_terms": ["alex rivera"],
                "source_evidence_ids": ["ev_name"],
                "verification_state": "inferred",
                "confidence": 0.98,
                "review_required": True,
            },
            {
                "fact_id": "fact_title",
                "category": "title",
                "text": "Data Engineer",
                "normalized_terms": ["data engineer"],
                "source_evidence_ids": ["ev_title"],
                "verification_state": "inferred",
                "confidence": 0.95,
                "review_required": True,
            },
            {
                "fact_id": "fact_python",
                "category": "skill",
                "text": "Python",
                "normalized_terms": ["python"],
                "source_evidence_ids": ["ev_skills"],
                "verification_state": "inferred",
                "confidence": 0.94,
                "review_required": True,
                "skill_category": "language",
            },
            {
                "fact_id": "fact_employment",
                "category": "employment",
                "text": "Data Engineer at Example Analytics",
                "normalized_terms": ["Data Engineer", "Example Analytics"],
                "source_evidence_ids": ["ev_role"],
                "verification_state": "inferred",
                "confidence": 0.93,
                "review_required": True,
                "start_date": "Jan 2021",
                "end_date": "current",
            },
            {
                "fact_id": "fact_highlight",
                "category": "experience_highlight",
                "text": "Built Spark pipelines for billing analytics.",
                "normalized_terms": ["spark", "billing analytics"],
                "source_evidence_ids": ["ev_highlight"],
                "verification_state": "inferred",
                "confidence": 0.91,
                "review_required": True,
            },
        ],
        "source_evidence": [
            {"evidence_id": "ev_name", "text": "Alex Rivera", "span": {"start": 0, "end": 12}},
            {"evidence_id": "ev_title", "text": "Data Engineer", "span": {"start": 13, "end": 26}},
            {"evidence_id": "ev_skills", "text": "Skills: Python", "span": {"start": 28, "end": 42}},
            {"evidence_id": "ev_role", "text": "Data Engineer at Example Analytics, Jan 2021 - current", "span": {"start": 43, "end": 98}},
            {"evidence_id": "ev_highlight", "text": "Built Spark pipelines for billing analytics.", "span": {"start": 99, "end": 140}},
        ],
        "uncertainty": [],
    }


class CanonicalResumeFromExtractionTests(unittest.TestCase):
    def test_constructs_canonical_input_with_source_stated_field_provenance(self):
        result = resume_core.canonicalResumeFromExtraction(_extraction(), {"kind": "file", "path": "resume.txt"}, {})

        self.assertEqual(result.get("status"), "ok", result)
        canonical = result["canonical_resume"]
        normalized = resume_core.normalizeResume(canonical)["canonical_resume"]

        self.assertEqual(normalized["contact"]["name"], "Alex Rivera")
        self.assertEqual(normalized["basics"]["name"]["verification_state"], "source_stated")
        self.assertEqual(normalized["title"]["value"], "Data Engineer")
        self.assertEqual(normalized["skills"][0]["value"], "Python")
        self.assertEqual(normalized["skills"][0]["verification_state"], "source_stated")
        self.assertEqual(normalized["skills"][0]["provenance"][0]["evidence_id"], "ev_skills")
        self.assertEqual(normalized["experience"][0]["start_date"], "2021-01")
        self.assertEqual(normalized["experience"][0]["end_date"], "current")
        self.assertEqual(normalized["experience"][0]["bullets"][0]["value"], "Built Spark pipelines for billing analytics.")
        self.assertEqual(normalized["experience"][0]["bullets"][0]["verification_state"], "source_stated")

    def test_omits_absent_title_and_experience_without_fabricated_defaults(self):
        extraction = {
            "schema_version": "resume-agent.proposal.v1",
            "proposal_type": "resume_semantic_extraction",
            "fact_proposals": [
                {
                    "fact_id": "fact_name_only",
                    "category": "name",
                    "text": "Sam No Defaults",
                    "normalized_terms": ["sam no defaults"],
                    "source_evidence_ids": ["ev_name_only"],
                    "verification_state": "inferred",
                    "confidence": 0.9,
                    "review_required": True,
                }
            ],
            "source_evidence": [{"evidence_id": "ev_name_only", "text": "Sam No Defaults", "span": {"start": 0, "end": 15}}],
        }

        canonical = resume_core.canonicalResumeFromExtraction(extraction, {"kind": "file", "path": "minimal.txt"})["canonical_resume"]
        normalized = resume_core.normalizeResume(canonical)["canonical_resume"]
        serialized = json.dumps(normalized, sort_keys=True)

        self.assertNotIn("title", normalized)
        self.assertEqual(normalized["experience"], [])
        self.assertNotIn("Software Engineer", serialized)
        self.assertNotIn("Source Resume", serialized)
        self.assertNotIn("Software Developer", serialized)

    def test_empty_extraction_returns_typed_error(self):
        result = resume_core.canonicalResumeFromExtraction(
            {"schema_version": "resume-agent.proposal.v1", "proposal_type": "resume_semantic_extraction", "fact_proposals": [], "source_evidence": []},
            {"kind": "file", "path": "empty.txt"},
        )

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("canonical_resume"), {})
        self.assertIn("empty_resume_extraction", {error.get("code") for error in result.get("errors", [])})

    def test_output_conforms_to_canonical_resume_schema_required_fields(self):
        canonical = resume_core.canonicalResumeFromExtraction(_extraction(), {"kind": "file", "path": "resume.txt"})["canonical_resume"]
        required = set(resume_core.CANONICAL_RESUME_SCHEMA["required"])

        self.assertEqual(set(canonical) & required, required)
        self.assertEqual(resume_core.validateResume(canonical).get("status"), "ok")


if __name__ == "__main__":
    unittest.main()
