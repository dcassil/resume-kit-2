---
id: resume-extraction-through
level: task
title: "Resume extraction through ModelAdapter; delete resume_patterns/lexicon recall paths"
short_code: "RKIT-T-0092"
created_at: 2026-08-17T16:26:26.986828+00:00
updated_at: 2026-08-17T16:43:57.910294+00:00
parent: resume-agent-model-based-resume
blocked_by: [RKIT-T-0091]
archived: false

tags:
  - "#task"
  - "#phase/completed"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0017
---

# Resume extraction through ModelAdapter; delete regex/lexicon recall paths

## Parent Initiative

[[RKIT-I-0017]]

## Objective **[REQUIRED]**

Rewire `extractResumeSemantics` to real extraction through the RKIT-I-0016 `ModelAdapter` and DELETE the fixture regex engine: `resume_patterns` with its hardcoded fixture phrase "Led a small team of three developers" and fixture labels (audit refs __init__.py:362-394), the "software development experience" years regex (:337-341), `_years_phrase` one..ten word numerals (:286-290), the `_terms_for` 14-entry lexicon (:100-125 — as a RECALL mechanism), and comma-split title parsing (:434-441). No silent deterministic fallback — provider failure surfaces as the typed taxonomy; deterministic code keeps only validation/mapping.

## Acceptance Criteria

## Acceptance Criteria

## Acceptance Criteria **[REQUIRED]**

- [ ] `extractResumeSemantics` builds an AdapterRequest via the T-0091 builders and maps the adapter's schema-validated payload into the existing proposal DTO envelopes (requires_validation, deterministic sha1-derived IDs, verification_state emission from T-0090 preserved).
- [ ] The named regex/lexicon recall paths are DELETED (not dead-coded, not fallbacks); grep proves the fixture phrase and years-regex literals are gone from production code.
- [ ] Golden test: the ML-engineer probe resume (T-0091 fake fixture) yields structured proposals for EVERY populated section — skills, experience, education, certifications, projects, employment structure — the audit's only-the-title failure has a named regression test.
- [ ] Legacy fixture inputs still produce complete proposals (via their pinned fake outputs); existing contract tests stay green or are strengthened (fixture-token assertions may be REPLACED by golden-based assertions per the initiative's spec-strengthening mandate — strengthen-only in coverage).
- [ ] Adapter failure (schema_invalid/provider_error from the fake) → typed error result from the public function; NEVER partial silent extraction; test proves it.
- [ ] Evidence links present on every extracted item (source span/line); confidence model-sourced from the payload.
- [ ] `--pr` and `--smoke` green; verify clean; resume_agent_guardrails passes.

## Implementation Notes **[CONDITIONAL: Technical Task]**

### Technical Approach
- The public function needs an adapter instance: default to the DeterministicFakeAdapter (gates) with construction via the validated agent config; an injectable seam consistent with the guardrail's surface (no new public names if the guardrail pins them — check first).
- Watch resume-cli smoke: it drives extraction — run --smoke and update the smoke-workspace fake fixtures if the CLI's inputs need pinned outputs (add fixtures, do NOT weaken smoke).
- Recommended Agent: opus + high

### Dependencies
RKIT-T-0091. Serial.

### Risk Considerations
- PROTECTED read-only: tools/*, tests/boundary/*. resume_agent_guardrails is text-based (T-0090 surprise) — keep proposal framing wording in docstrings.
- Smoke drives the CLI extraction path — new fake fixtures for smoke inputs may be required; keep the smoke honest.

## Status Updates **[REQUIRED]**

- 2026-08-17: T-0091 committed (schemas v1 w/ mandatory evidence+confidence, prompt assets id@vN convention, deterministic builders, 5 complete pinned fixtures incl. ML-engineer/Python-Spark/GraphQL+API goldens; gates 473/smoke/verify green). Codex launched: extractResumeSemantics rewire through the adapter, regex-engine deletion (grep-proof), typed-error-on-failure, smoke-input fixture pinning if needed.