---
id: guardrails-config-wiring-plus
level: task
title: "guardrails.* config wiring plus duplicate/stuffing generalization"
short_code: "RKIT-T-0037"
created_at: 2026-08-14T22:54:23.908642+00:00
updated_at: 2026-08-14T22:54:23.908642+00:00
parent: resume-core-grounded-change
blocked_by: ["RKIT-T-0036"]
archived: false

tags:
  - "#task"
  - "#phase/todo"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0004
---

# guardrails.* config wiring plus duplicate/stuffing generalization

## Parent Initiative

[[RKIT-I-0004]]

## Objective

Wire the section 13 `guardrails.*` config namespace through the shared config layer per RKIT-A-0006 item 6 (migrating and removing the flat `allow_inferred_facts` key), and generalize the duplicate/keyword-stuffing checks (RKIT-I-0004 Requirements 7's config half and 8's duplicate/stuffing half; domain.py:1306-1326).

## Acceptance Criteria

- [ ] `guardrails.*` keys are parsed and validated through the same section 13 config layer that `matching.*`/`resume.*` use; unknown `guardrails.*` keys fail validation with a typed error (matching the established namespace-config behavior from I-0002/I-0003).
- [ ] The flat `allow_inferred_facts` key is migrated to its `guardrails.*` home and the flat key is REMOVED — supplying it is a typed config error (same removal pattern as the flat matching keys in I-0002 and `max_skills` in I-0003).
- [ ] The `allow_inferred_facts` semantics compose with T-0035's verification rule: even when inferred facts are allowed to assist, `inferred` never silently grounds a claim requiring verification.
- [ ] Duplicate detection generalizes beyond skills-only: repeated experience entries/bullets are detected and reported.
- [ ] Keyword-stuffing counts ALL repeated terms (fixes the break-after-first defect at domain.py:1306-1326); a resume with two distinct stuffed terms reports both.
- [ ] Relevant honesty/validation behaviors honor their `guardrails.*` toggles/thresholds where section 13 defines them; defaults preserve current (post-T-0036) strictness — config can tighten or configure, never silently weaken below documented defaults.
- [ ] Unit tests in `tests/unit/` cover config validation (valid, unknown-key, removed-flat-key), inferred-compose rule, generalized duplicates, multi-term stuffing; PR + smoke gates green; snapshot no-drift proof run (FIXTURE_CONFIG may need `guardrails.*` migration — flat keys are typed errors).
- [ ] No weakening of any existing assertion; protected edits strengthen-only under RKIT-A-0006 and reported.

## Implementation Notes

### Technical Approach

Follow the exact namespace-config pattern I-0002 (`matching.*`) and I-0003 (`resume.*`) established in the shared section 13 config layer — schema declaration, validation, typed unknown-key/removed-key errors, and threading into the honesty/duplicate checks. Duplicate generalization: normalize-and-compare across experience bullets and entries (reuse existing term normalization); stuffing: count occurrences per normalized term across the resume, report every term over threshold instead of returning after the first.

### Dependencies

RKIT-T-0036 (the checks being configured must exist in final form first). I-0002/I-0003 config-layer pattern (done).

### Risk Considerations

Removing the flat `allow_inferred_facts` key breaks any caller still passing it — sweep resume-cli/workflow/fixture configs (`git grep allow_inferred_facts`) and migrate them in the same change; check `--smoke`, not just `--pr` (the I-0001 lesson). FIXTURE_CONFIG churn drives snapshot regeneration — run the ×2 no-drift proof.

### Execution profile

Recommended Agent: opus + medium

Rationale: substantive multi-file work but follows the twice-proven namespace-config pattern; the design decisions are already made by precedent and the initiative doc.

## Status Updates

*To be added during implementation*
