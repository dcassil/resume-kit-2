---
id: deterministicfakeadapter-gate
level: task
title: "DeterministicFakeAdapter, gate wiring, gate-isolation test"
short_code: "RKIT-T-0088"
created_at: 2026-08-16T19:46:40.531655+00:00
updated_at: 2026-08-17T16:06:37.281422+00:00
parent: resume-agent-proposal-model
blocked_by: [RKIT-T-0087]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0016
---

# DeterministicFakeAdapter, gate wiring, gate-isolation test

## Parent Initiative

[[RKIT-I-0016]]

## Objective **[REQUIRED]**

Ship the `DeterministicFakeAdapter` that backs every official gate (RKIT-A-0003 item 4): fixture-pinned outputs keyed by a stable hash of (prompt template id, schema id, canonical input); unknown keys raise a typed error rather than improvising — a fake that fails loudly keeps gates honest. Official suites construct only the fake; a gate-profile test asserts the live adapter cannot be constructed under the gate profile.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] `DeterministicFakeAdapter` implements the T-0087 protocol; outputs come from fixture files (fixtures/ area consistent with the repo's data-envelope convention from I-0051) keyed by stable hash of (prompt_template_id, schema_id, canonical input JSON); same inputs → byte-identical result across runs.
- [ ] Unknown key → typed error (taxonomy: refused or a dedicated fake-specific typed error mapping to provider_error — pick one, document it); NEVER a synthesized/improvised output.
- [ ] Fake outputs pass the shared schema validators — a fixture failing its schema fails the suite (fixtures cannot rot silently).
- [ ] Gate-profile mechanism: an explicit profile signal (e.g. env/config flag the gates set, or default-safe construction API) under which constructing the live adapter raises a typed error; gate-isolation contract test asserts it. Constructing the fake requires no API key and no network.
- [ ] Contract tests: metadata on every fake result; schema_invalid on a deliberately broken fixture; unknown-key typed failure; determinism (two identical calls → identical results).
- [ ] `--pr` and `--smoke` green; verify clean; resume_agent_guardrails passes.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- Check tools/fixtures_guardrails.py (READ-ONLY) for the required fixture data-envelope shape before writing fixture files.
- The five public functions do NOT need to route through the adapter yet (RKIT-I-0017..0019 own that migration); this task delivers the adapter + gate wiring substrate. If a minimal integration point helps prove the seam, add it without changing the public functions' current outputs.
- Recommended Agent: opus + high

### Dependencies
RKIT-T-0087. Serial.

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*. Fixture guardrails are protected — conform, don't edit.

## Status Updates **[REQUIRED]**

- 2026-08-16: T-0087 committed (protocol/DTOs/taxonomy/validators in _adapters.py + _schema_validation.py, ValidatingModelAdapter base; gates 451/smoke/verify green). Codex launched: fixture-pinned fake via ValidatingModelAdapter, sha256 keying, unknown-key→provider_error, fixture self-validation walk, gate-safe default (live construction requires RESUME_AGENT_ALLOW_LIVE=1 opt-in so protected gate scripts need no edits).