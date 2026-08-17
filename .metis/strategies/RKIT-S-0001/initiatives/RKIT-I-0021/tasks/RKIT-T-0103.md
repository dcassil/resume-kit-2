---
id: golden-eval-fixtures-opt-in-eval
level: task
title: "Golden eval fixtures, opt-in eval harness, capture/quarantine/promotion"
short_code: "RKIT-T-0103"
created_at: 2026-08-17T18:37:55.952646+00:00
updated_at: 2026-08-17T18:58:03.832678+00:00
parent: resume-agent-auditability
blocked_by: [RKIT-T-0102]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0021
---

# Golden eval fixtures, opt-in eval harness, capture/quarantine/promotion

## Parent Initiative

[[RKIT-I-0021]]

## Objective

Build the opt-in, NON-GATING live eval tier per RKIT-A-0003 item 4: golden eval fixtures (inputs + expected-output rubrics) for the extraction, interview, and rewrite surfaces (equivalences deepens when I-0020 lands), an eval harness runner that scores the live adapter against the rubrics and emits a report artifact, and a record/replay capture path where live outputs land in QUARANTINE and become pinned `DeterministicFakeAdapter` fixtures only through explicit human promotion.

## Acceptance Criteria

## Acceptance Criteria

- [ ] Golden eval fixture format defined and documented (resume-agent/TEST_SPEC.md section, not protected): each fixture = `{fixture_id, surface, prompt_template_id, output_schema_id, input, rubric}` where rubric items are graded, machine-checkable criteria (e.g. required terms present, schema fields populated, grounding constraints held) — no free-prose-only rubrics. At least one fixture per landed surface: resume-extraction, job-extraction, question-generation, answer-interpretation, rewrite-proposal. Live under `fixtures/resume-agent/eval/` (distinct from `fake-adapter/`).
- [ ] Eval harness at `resume-agent/tools/eval_harness.py` (beside live_smoke.py, NOT under tools/ at repo root — that dir is protected): runs golden fixtures against the LIVE adapter, scores per rubric, writes a report artifact (JSON) — never a pass/fail exit that any gate consumes. Requires the SAME triple env opt-in discipline as live_smoke.py, and is hard-blocked under `RESUME_AGENT_GATE_PROFILE=1` regardless of other flags.
- [ ] Capture mode: a wrapper around the live adapter writing candidate fixtures keyed by the same `deterministic_fake_key(template_id, schema_id, canonical_input)` the fake uses, into a quarantine dir (`fixtures/resume-agent/quarantine/`) — NEVER directly into `fake-adapter/`. Promotion is a separate explicit tool command (e.g. `eval_harness.py promote <key>`) that copies quarantine → fake-adapter fixture format; it must refuse to overwrite an existing pinned fixture without an explicit `--replace` flag, so promotion is always a visible, reviewed diff.
- [ ] Gate-safety tests (in normal non-protected unit/contract tiers, running WITHOUT any live calls): (a) under `RESUME_AGENT_GATE_PROFILE=1` the harness entrypoint and capture wrapper raise/refuse before any adapter construction; (b) capture writes only under quarantine (path assertion); (c) promotion refuses overwrite without `--replace`; (d) the harness module import has no side effects and is imported by NO gate-run module (grep-proof assertion mirroring the live_smoke isolation pattern).
- [ ] All adapter calls made by the harness/capture path emit T-0101 call-audit records (the eval report references them), so live eval runs are themselves reconstructable.
- [ ] Quarantine dir is gitignored or clearly non-fixture (decide and document; pinned gate fixtures must remain the only fixture source the fake adapter reads).
- [ ] Gates green: `--pr`, `--smoke`, `--future-contract`. No protected file edits. resume-agent/TEST_SPEC.md eval section names every covering test.

## Implementation Notes

### Technical Approach
Reuse live_smoke.py's opt-in/gate-block pattern verbatim for the harness entry. Rubric scoring is deterministic code over the model output (term presence, schema completeness, grounding-map checks reusing the I-0019 post-guard helpers where applicable) — the harness never asks a model to judge. Report artifact goes to a caller-specified output path (default under scratch/build dir, not fixtures/).

### Dependencies
RKIT-T-0101 (audit records), RKIT-T-0102 (metadata/reconstruction — eval reports reference audit records the same way).

### Risk Considerations
The failure class to design against: the eval loop quietly rewriting gate truth. Every safeguard (quarantine, explicit promote, --replace, gate-profile hard block) exists for that; mutation-probe each one (remove safeguard → named test fails).

Recommended Agent: opus + medium

## Status Updates

- 2026-08-17: Added `resume-agent/tools/eval_harness.py`, five golden eval fixtures under `fixtures/resume-agent/eval/`, quarantine gitignore, bridged unit coverage in `tests/unit/test_resume_agent_eval_harness_unit.py`, and TEST_SPEC eval documentation. Next: run focused tests and required gates.
