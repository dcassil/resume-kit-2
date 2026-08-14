---
id: resume-core-selection-planning-and
level: initiative
title: "Resume-Core Selection Planning And Structural Constraints"
short_code: "RKIT-I-0003"
created_at: 2026-08-13T20:41:36.874684+00:00
updated_at: 2026-08-14T21:14:43.182776+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: [RKIT-I-0002]
archived: false

tags:
  - "#initiative"
  - "#phase/decompose"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: resume-core-selection-planning-and
---

# Resume-Core Selection Planning And Structural Constraints Initiative

## Context **[REQUIRED]**

Package: `resume-core`. Selection planning. `rankResumeContent` exists and passes gates, but it is a stub relative to this initiative's outcome: it explicitly discards its `match_result` input (`del match_result`, domain.py:402), so relevance ranking against the job — the core of the outcome — has no substrate; it enforces only a `max_skills` cap read from an ad-hoc flat key while every section 13 `resume.*` min constraint is ignored (domain.py:410-412); its default section order `['basics','summary','skills','experience','education']` diverges from section 13's `['summary','skills','experience','projects','education']` (domain.py:423); and there is no bullet-level content selection (domain.py:399-432). The TEST_SPEC selection-planning cases (respect skills/experience/bullets min/max, honor configured section order) sit unimplemented in the empty tests/unit directory, and the base-immutability promise in the outcome has had no corresponding requirement or test. Calling this state a passing scaffold hid that relevance-improving, constraint-enforcing selection planning is essentially unstarted despite the package work log claiming completeness.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Make the section 13 `resume.*` config authoritative for selection: min AND max for skills, experience entries, and bulletsPerRole; `sectionOrder` (resolving the projects divergence); `targetPages`.
- Replace the discard-the-input stub with real relevance ranking that consumes `MatchResult` requirement rows and dimensions.
- Plan at bullet granularity with requirement/fact traceability on every keep/drop decision.
- Guarantee base immutability: planning never mutates the input resume; the plan is a separate artifact.

**Non-Goals:**
- No match scoring or threshold policy — RKIT-I-0002 produces the MatchResult this initiative consumes.
- No change application, grounding, or final validation (RKIT-I-0004).
- No pagination or overflow measurement — resume-render owns page estimation; `targetPages` here is a plan budget signal only.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
1. `rankResumeContent` consumes `match_result`: content linked to resolved or required requirements outranks unlinked content; the `del match_result` discard (domain.py:402) is removed, and a sensitivity test proves ranking changes when requirement resolution changes.
2. `resume.skills`/`resume.experience`/`resume.bulletsPerRole` min and max are enforced from section 13 keys via the config layer wired under A-0006 item 6, replacing the ad-hoc `max_skills` flat key (domain.py:410-412). Max overflows drop the lowest-relevance items; min deficits are flagged in the plan, never satisfied by fabrication.
3. Default `sectionOrder` becomes section 13's `['summary','skills','experience','projects','education']` (fixes domain.py:423); a configured order wins over the default.
4. Selection is bullet-level: plan entries address individual experience bullets by JSON path, not whole sections only (domain.py:399-432).
5. Every plan entry carries a reason plus requirementIds/factIds when derived from the match result — tightening the old "when supplied" wording into an unconditional traceability rule for match-derived decisions.
6. Base immutability: `rankResumeContent` is a pure function over its inputs; a test asserts the input resume is unchanged after planning.
7. `targetPages` is read and recorded in the plan as the budget the selection targeted.
8. Agent output cannot override structural maxima (retained from the original requirements; still correct and regression-guarded).

### Dependencies
- RKIT-I-0002 — the completed `MatchResult` (dimensions and requirement rows) is the ranking input; transitively RKIT-I-0001 for DTOs and the section 13 config layer.
- RKIT-A-0006 (decided) — settles the `resume.*` config vocabulary (item 6); no open ADR blockers remain.

### Blocked Status
- Blocked by RKIT-I-0002 (frontmatter `blocked_by: ["RKIT-I-0002"]`).

## Detailed Design **[REQUIRED]**

**ContentSelectionPlan DTO.** Ordered sections per the effective `sectionOrder`; per-section entries referencing content by JSON path at bullet granularity, each with `action` (keep/drop/reorder), `relevance` score, `reason`, `requirementIds`, `factIds`; a constraint report recording each min/max constraint as satisfied or violated with counts; and plan metadata (`targetPages`, snapshot of the config used). The plan is an artifact separate from the resume — applying any change remains RKIT-I-0004's `applyChanges` territory.

**Ranking.** Relevance per item derives deterministically from the MatchResult: items tied to `exact_match`/`alias_match`/`verified_fact_match` requirement rows rank above `related_match`/`possible_match`, which rank above unlinked content; unlinked content orders by stable defaults (recency, then source order) with deterministic tie-breaking so repeated runs produce identical plans.

**Constraint semantics.** Max constraints truncate lowest-relevance first. Min constraints never invent content: a below-min section yields a `constraint_deficit` flag in the plan so upstream flows (gap resolution) can act — honesty is preserved by refusing to pad.

**Migration note.** Callers using the flat `max_skills` key migrate to the section 13 `resume.*` keys; the flat key is removed after migration per A-0006 item 6.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Implement the TEST_SPEC selection-planning unit cases currently sitting in the empty tests/unit: respect skills/experience/bullets min and max, honor configured section order, and projects placement per section 13.
- Add the match-result sensitivity test (changed resolution changes ranking) as the standing guard against a `del match_result`-style regression.
- Add the immutability test (input resume unchanged after planning) and a determinism test (identical inputs produce identical plans across runs).
- Strengthen TEST_SPEC: it currently never asserts min constraints or the section-order divergence — the looseness that certified a max-only stub; add explicit cases for both plus the constraint-deficit flagging behavior.

## Alternatives Considered **[REQUIRED]**

- **Let the agent propose selection and have resume-core only validate.** Rejected: the CONTRACT_SURFACE_ALIGNMENT.md responsibility matrix puts deterministic selection planning in resume-core; agents propose wording while deterministic code owns constraints and selection — agent-side planning would make relevance non-reproducible.
- **Satisfy min constraints by automatically pulling in low-relevance or generated content.** Rejected: padding to a min is a truth hazard and hides real gaps; flagging deficits keeps the plan honest and routes the gap to the resolve-gaps flow.
- **Estimate pages inside resume-core to enforce targetPages directly.** Rejected: page measurement is render-owned (section 9); resume-core would duplicate layout logic and drift from the renderer's ground truth.

## Implementation Plan **[REQUIRED]**

Decomposition guidance (dependency-ordered chunks; actual Metis task decomposition happens later):
1. `ContentSelectionPlan` DTO with the constraint report and the immutability/determinism guarantees.
2. Section 13 `resume.*` config wiring (min/max/sectionOrder/targetPages) through the A-0006 config layer.
3. Match-result-driven relevance ranking replacing the discard stub.
4. Bullet-level selection with unconditional traceability on match-derived decisions.
5. Unit suites plus TEST_SPEC strengthening for mins, order, and deficit flagging.