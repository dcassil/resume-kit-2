"""Unit coverage for the non-gating resume-agent eval harness."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = ROOT / "resume-agent"
HARNESS_PATH = PACKAGE_ROOT / "tools" / "eval_harness.py"
EVAL_FIXTURES = ROOT / "fixtures" / "resume-agent" / "eval"

if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from resume_agent._adapters import AdapterCompletion, AdapterRequest, AdapterResult, ValidatingModelAdapter
from resume_agent._interview_schemas import QUESTION_GENERATION_SCHEMA_ID


class StaticQuestionAdapter(ValidatingModelAdapter):
    def __init__(self, *, output_schemas, call_audit_sink):
        super().__init__(
            adapter_id="resume-agent-eval-static",
            adapter_version="0.0.1",
            model_id="static-eval-model",
            runtime_config={"mode": "unit"},
            output_schemas=output_schemas,
            call_audit_sink=call_audit_sink,
        )

    def _complete_unchecked(self, _request):
        return AdapterCompletion(
            payload={
                "schema_version": QUESTION_GENERATION_SCHEMA_ID,
                "proposal_type": "question_generation",
                "requires_validation": True,
                "question": "What Terraform infrastructure-as-code experience do you have?",
                "target_ids": {"requirement_ids": ["req_terraform"], "fact_ids": ["fact_iac"]},
                "rationale": "The selected requirement asks for Terraform experience.",
                "confidence": 0.91,
            }
        )


class ResumeAgentEvalHarnessUnitTests(unittest.TestCase):
    def test_eval_fixtures_cover_each_landed_surface_with_machine_checkable_rubrics(self):
        harness = _load_harness_module()
        fixtures = harness.load_eval_fixtures(EVAL_FIXTURES)

        self.assertEqual(
            {fixture["surface"] for fixture in fixtures},
            {
                "resume-extraction",
                "job-extraction",
                "question-generation",
                "answer-interpretation",
                "rewrite-proposal",
            },
        )
        for fixture in fixtures:
            for field in ["fixture_id", "surface", "prompt_template_id", "output_schema_id", "input", "rubric"]:
                self.assertIn(field, fixture)
            self.assertIsInstance(fixture["input"], dict)
            self.assertTrue(fixture["rubric"])
            for criterion in fixture["rubric"]:
                self.assertIn(criterion["check"], harness.SUPPORTED_RUBRIC_CHECKS)
                self.assertIsInstance(criterion["points"], int)
                self.assertGreater(criterion["points"], 0)

    def test_gate_profile_blocks_entrypoint_and_capture_wrapper_before_adapter_construction(self):
        harness = _load_harness_module()
        constructions = []

        def adapter_factory(**_kwargs):
            constructions.append("constructed")
            raise AssertionError("adapter should not be constructed under gate profile")

        env = {
            "RESUME_AGENT_GATE_PROFILE": "1",
            "RESUME_AGENT_LIVE_SMOKE": "1",
            "RESUME_AGENT_ALLOW_LIVE": "1",
            "ANTHROPIC_API_KEY": "test-key",
        }
        with self.assertRaises(harness.EvalHarnessBlockedError):
            harness.run_eval(env=env, adapter_factory=adapter_factory)
        with self.assertRaises(harness.EvalHarnessBlockedError):
            harness.create_capturing_live_adapter(env=env, adapter_factory=adapter_factory)
        self.assertEqual(constructions, [])

    def test_capture_writes_only_under_quarantine(self):
        harness = _load_harness_module()
        with tempfile.TemporaryDirectory(prefix="resume-agent-capture-") as temp:
            root = Path(temp)
            request = _capture_request()
            result = AdapterResult.ok(
                payload={"schema_version": "capture.payload.v1"},
                adapter_id="static-live",
                adapter_version="0.0.1",
                model_id="static-model",
                runtime_config={},
                retries=0,
                usage={},
            )

            path = harness.write_quarantine_candidate(request, result, project_root=root)

            self.assertEqual(path.parent, root / "fixtures" / "resume-agent" / "quarantine")
            self.assertTrue(path.exists())
            self.assertNotIn("fake-adapter", path.parts)
            candidate = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(candidate["candidate_schema_version"], harness.CAPTURE_CANDIDATE_SCHEMA_VERSION)
            self.assertFalse(candidate["reviewed"])

    def test_promote_refuses_overwrite_without_replace(self):
        harness = _load_harness_module()
        with tempfile.TemporaryDirectory(prefix="resume-agent-promote-") as temp:
            root = Path(temp)
            request = _capture_request()
            result = AdapterResult.ok(
                payload={"schema_version": "capture.payload.v1"},
                adapter_id="static-live",
                adapter_version="0.0.1",
                model_id="static-model",
                runtime_config={},
                retries=0,
                usage={},
            )
            quarantine_path = harness.write_quarantine_candidate(request, result, project_root=root)
            key = quarantine_path.stem

            promoted = harness.promote_fixture(key, project_root=root)

            self.assertEqual(promoted.parent, root / "fixtures" / "resume-agent" / "fake-adapter")
            self.assertTrue(promoted.exists())
            with self.assertRaises(FileExistsError):
                harness.promote_fixture(key, project_root=root)

    def test_eval_report_references_call_audit_records(self):
        harness = _load_harness_module()
        with tempfile.TemporaryDirectory(prefix="resume-agent-eval-") as temp:
            root = Path(temp)
            fixtures_dir = root / "fixtures"
            fixtures_dir.mkdir()
            fixture = {
                "fixture_id": "unit-question-eval",
                "surface": "question-generation",
                "prompt_template_id": "resume-agent.question-generation@v1",
                "output_schema_id": QUESTION_GENERATION_SCHEMA_ID,
                "input": {
                    "schema_id": QUESTION_GENERATION_SCHEMA_ID,
                    "topic": "Terraform",
                    "target_ids": {"requirement_ids": ["req_terraform"], "fact_ids": ["fact_iac"]},
                    "context_snippets": ["Preferred: Terraform infrastructure-as-code experience."],
                },
                "rubric": [
                    {"id": "field-check", "check": "schema_fields_populated", "points": 1, "paths": ["/question"]},
                    {"id": "term-check", "check": "required_terms", "points": 1, "terms": ["terraform"]},
                ],
            }
            (fixtures_dir / "question.json").write_text(json.dumps(fixture), encoding="utf-8")
            report_path = root / "reports" / "eval-report.json"

            def adapter_factory(**kwargs):
                return StaticQuestionAdapter(
                    output_schemas=kwargs["output_schemas"],
                    call_audit_sink=kwargs["call_audit_sink"],
                )

            report = harness.run_eval(
                fixtures_dir=fixtures_dir,
                report_path=report_path,
                env={
                    "RESUME_AGENT_LIVE_SMOKE": "1",
                    "RESUME_AGENT_ALLOW_LIVE": "1",
                    "ANTHROPIC_API_KEY": "test-key",
                },
                adapter_factory=adapter_factory,
            )

            self.assertTrue(report_path.exists())
            self.assertEqual(report["summary"]["earned_points"], 2)
            self.assertEqual(len(report["call_audit_records"]), 1)
            audit_ref = report["results"][0]["call_audit_records"][0]
            self.assertTrue(Path(audit_ref["path"]).exists())
            self.assertEqual(audit_ref["call_id"], report["call_audit_records"][0]["call_id"])

    def test_eval_harness_import_isolated_from_gate_modules_and_has_no_side_effects(self):
        before_modules = set(sys.modules)
        default_report_path = ROOT / "build" / "resume-agent" / "eval-report.json"
        report_existed_before = default_report_path.exists()
        harness = _load_harness_module()
        new_modules = set(sys.modules) - before_modules

        self.assertTrue(hasattr(harness, "main"))
        self.assertNotIn("resume_agent._anthropic_adapter", new_modules)
        self.assertEqual(harness.DEFAULT_REPORT_PATH.exists(), report_existed_before)
        for path in [
            ROOT / "tools" / "run_gate.py",
            ROOT / "tools" / "run_tests.py",
            ROOT / "tools" / "run_smoke.py",
            ROOT / "tests" / "suite_manifest.json",
        ]:
            self.assertNotIn("eval_harness", path.read_text(encoding="utf-8"))

    def test_default_report_path_is_outside_fixtures(self):
        harness = _load_harness_module()

        self.assertNotIn("fixtures", harness.DEFAULT_REPORT_PATH.parts)


def _load_harness_module():
    module_name = "resume_agent_eval_harness_under_test"
    spec = importlib.util.spec_from_file_location(module_name, HARNESS_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load eval harness module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _capture_request() -> AdapterRequest:
    return AdapterRequest(
        prompt_template_id="capture-template@v1",
        prompt="Return capture payload.",
        input_payload={"subject": "capture"},
        output_schema_id="capture.payload.v1",
    )


__all__ = ["ResumeAgentEvalHarnessUnitTests"]
