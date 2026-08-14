# Handoff — 2026-08-14 EVENING (I-0051 W1 + I-0002 + I-0003 COMPLETE, continuous codex mode)

Read this first. Supersedes the two handoffs below (kept for the defect table, ADR summaries, depth caveats, straight-jacket details).

## 1. State right now (everything on develop, PUSHED through `60de793`)

- **DONE + pushed today**: RKIT-I-0051 Wave 1 (12 tasks, incl. the password lane `84503f9`), **RKIT-I-0002** (matching: MatchResult 4.3 w/ threshold+hardRequirementsResolved+tri-state decision, gating defect FIXED and behaviorally probed, MatchDimension weighted breakdown, TermRelationship-driven resolution w/ Azure≠AWS invariant, live terminology dimension, flat matching keys REMOVED, v0.2.0), **RKIT-I-0003** (selection: ContentSelectionPlan DTO, resume.* config w/ §13 sectionOrder + basics pinned as render header, match-result-driven ranking — `del match_result` gone — bullet-level selection w/ unconditional traceability, max_skills removed, v0.3.0).
- Gates at head: `--pr` 258 green, `--future-contract` 265 green, `--smoke` green, straight-jacket verify clean.
- Daniel merged develop→main via PR #8 mid-session; local/remote reconciled (merge commit `df36379`).

## 2. Standing instructions from Daniel (this session)

**Continuous mode authorized**: decompose next initiative → orchestrate codex agents per task → review + run BOTH gates → commit per task → complete initiative → bump version → push develop → repeat. Do NOT ask unless a genuinely unanswerable question. Stop only past ~75% context at a good stopping point with a handoff (this doc).

**Pre-commit hook**: Daniel said he will change straight-jacket pre-commit to WARN (not block) so protected files can be edited during work, with a **single approve/update-locks commit at the end before a PR to main passes**. NOT yet verified in this session — test with a protected edit before relying on it.

## 3. PENDING: run_tests.py wiring batch (do this when hook warns, or via Daniel password)

New `tests/unit` modules created in I-0002/I-0003 that are mapped in suite_manifest but NOT yet in protected `tools/run_tests.py` CURRENT_TEST_MODULES (they run standalone; behaviors covered indirectly by contract/snapshot tests):
`test_matching_config_unit, test_match_decision_unit, test_match_dimensions_unit, test_term_relationship_resolution_unit, test_infer_classification_unit, test_terminology_dimension_unit, test_selection_plan_shape_unit, test_resume_config_unit, test_selection_ranking_unit, test_bullet_selection_unit` (~60 tests). Add-only edit; then the single re-register/approve commit.

## 4. The proven loop (reuse verbatim)

Per task: (1) Metis task → active; (2) write tight prompt file to scratchpad — task-doc path + binding decisions + FORBIDDEN protected list + verify commands incl. snapshot regenerate ×2 no-drift; (3) `cat prompt | codex exec --cd <repo> -o out.txt - > full.log 2>&1` in background (flag-free — flags get classifier-blocked); (4) review report + diff, independently probe anything load-bearing (e.g. the T-0024 gating probe), review snapshot diffs YOURSELF (Daniel delegated baseline review in continuous mode); (5) run `--pr` AND `--smoke` (add `--future-contract` on close-out chunks); (6) commit per task w/ trailer, Metis → completed. Initiative close: version bump in pyproject.toml (minor per initiative), push develop, update memory + this handoff.

Codex quality has been high (11 tasks today, zero rejects; two driver interventions: float-noise rounding in matching_config `default_requirement_weight`, and independent gating verification). Snapshot churn is normal for scoring changes — review the per-snapshot summary codex reports.

## 5. Next work

- **RKIT-I-0004** (grounded change lifecycle + final validation) — NOW UNBLOCKED (I-0002 done). Owns the honesty-gate defect (5-entry fixture lookup at domain.py:47-53,1103-1105) and applied-operations threading. Its chunk-1 (validateFinalResume fix) was already done 08-13. Same decompose→execute flow; it consumes MatchResult/plan/claim-provenance substrates that are all now real.
- After I-0004: resume-core is done; next tier = career-store (I-0005..0008) or the CLI/workflow initiatives; check `blocked_by` frontmatter.
- Wave 2 of I-0051 stays blocked on RKIT-I-0041.

## 6. Gotchas rediscovered today

- MCP metis `create_document` still fails parent resolution — use `metis create task --initiative RKIT-I-00NN "title"`; task files then need Read-before-Write to populate (frontmatter regenerates `blocked_by: []` — set the chain in the file body write).
- Every resume-core initiative is a SERIAL chain (all tasks touch domain.py) — do not parallelize codex agents in one worktree.
- `git add resume-core` sweeps `__pycache__` — `.gitignore` now covers it (added today) but stay alert.
- Metis phase transitions rewrite task files (duplicate "## Acceptance Criteria" headers appear — harmless).
- `python3 tools/regenerate_expected_snapshots.py --root . --write` twice + `git diff --stat fixtures/expected/` is the no-drift proof; FIXTURE_CONFIG now uses `matching.*`/`resume.*` namespaces (flat keys are typed errors).

---

# Handoff — 2026-08-14 (RKIT-I-0001 COMPLETE, codex-driven execution)

Read this first. It supersedes the "next steps" of the 2026-08-13 handoff below (design review + decomposition are DONE). Everything else below (defect table, ADRs, depth caveats, command caveats) still applies.

## 1. What shipped this session (all on `develop`, UNPUSHED)

**RKIT-I-0001 "Resume-Core Canonical Contracts" is COMPLETE** — 8 tasks (RKIT-T-0003..0010), decomposed + implemented + committed, PR gate **198 tests green + smoke green**. Commits: `9adf305` (decomposition), `d044de0` (front four T-0003/0005/0008/0004), `e33233c` (T-0006), `8d522ce` (T-0007), `653cca1` (T-0009), `740a185` (T-0010), `0e60781` (Metis state). Initiative + all 8 tasks are in Metis `completed`.

What that delivered: canonical `VerificationState`={source_stated,user_verified,imported,inferred,unknown} / `ResolutionState`={…,explicitly_missing,not_applicable} (dropped `conflicted`); career-store first-class **conflict-record** path replacing the removed enum member; `ResumeChangeOperation` shape (6 statuses, 5 verbs, mandatory reason/linked_*_ids/provenance, structural validateChange); JobModel §4.2 + **JobTerm** substrate (deterministic); schema-backed validateResume (stdlib walker, enforces resume_id/source); typed date rejection (`invalid_date`/`reversed_range`, new `dates.py`); claim-level ResumeField provenance weaving (honest empty/unknown defaults, new `claim_fields.py`) — the substrate RKIT-I-0004 consumes; realigned shared-DTO contract test (whole-set assertEqual, strengthen-only); resume-core unit tier (25 tests in `tests/unit`) + TEST_SPEC.

**RKIT-I-0051 Wave 1 is decomposed but NOT started** — 12 tasks RKIT-T-0011..0022 exist in Metis (`todo`), fully populated with acceptance criteria + `blocked_by` DAG.

## 2. How execution ran — the codex driving setup (REUSE THIS)

"Teamwork with codex agents": Daniel's `~/.codex/config.toml` is set to `sandbox_mode="danger-full-access"` + `approval_policy="never"`, and a Claude Code permission rule `Bash(codex exec:*)` is added. So the driver launches codex FLAG-FREE (adding `--approve-for-me`/`--dangerously-*` gets blocked by the auto-mode classifier — do NOT add them):

```sh
cat <promptfile> | codex exec --cd /Users/danielcassil/Code/resume-kit-2 -o <out.txt> - > <full.log> 2>&1
```

Per-task loop that worked: (1) transition the Metis task to `active`; (2) write a tight prompt file that points codex at the task doc `.metis/…/tasks/RKIT-T-00NN.md`, states the approved decisions, forbids protected-file edits + commits ("report only"), and gives PYTHONPATH verify commands; (3) launch codex in background; (4) review the diff + run `python3 tools/run_gate.py --pr --root .` AND `--smoke`; (5) commit per task with the trailer block; (6) transition task → `completed`. Codex is reliable and caught real issues (e.g. the protected-guardrail conflict on T-0003) — trust it but always review + run BOTH gates before committing.

## 3. THE STRAIGHT-JACKET PASSWORD GATE (human-in-the-loop, unavoidable)

Pre-commit hook runs `straight-jacket verify` (protected-file integrity, NOT the test gate). Editing any protected file blocks ALL commits until re-registered, and `straight-jacket update <path>` prompts for Daniel's LOCAL PASSWORD interactively — it CANNOT be automated (refuses env/flag/file). Protected set: `tools/tool_manifest.json`, `run_gate.py`/`run_smoke.py`/`run_tests.py`, `tools/TEST_SPEC.md`, all `tools/*_guardrails.py`, all `tests/boundary/test_*_guardrails.py`. (Contract tests in `tests/contract/` are NOT protected.) A-0006 authorizes realigning protected guardrails/manifests to documented contracts, but the re-registration is still Daniel's password. In I-0001 only `tools/career_store_guardrails.py` needed it (once).

## 4. Next work (nothing started; needs Daniel for design review + passwords)

- **RKIT-I-0002** (Deterministic Requirement Resolution & Match Scoring) is now UNBLOCKED (its only blocker was I-0001). It is the natural next resume-core initiative — needs the human-in-the-loop design-review + decompose flow (same as I-0001 got). RKIT-I-0004 (grounded change lifecycle) is unblocked from I-0001 but still `blocked_by` I-0002; RKIT-I-0003 blocked_by I-0002.
- **RKIT-I-0051 Wave 1** is ready to execute (already decomposed). Lane split: AUTONOMOUS (codex + commit, no password) = T-0011, T-0012, T-0015, T-0019, T-0020; NEEDS-PASSWORD (protected files) = T-0014, T-0016, T-0017, T-0018, T-0022, and T-0021/T-0013 if they must edit protected `run_tests.py`. **RKIT-T-0021 (REQ-009) wires `tests/unit` into the gate's module list (protected `run_tests.py`)** — until it lands, the 25 I-0001 unit tests exist but aren't gate-run (their behaviors ARE covered by discovered contract assertions, so no gate gap).

## 5. Tech-debt created this session (documented, owned elsewhere — don't lose these)

- **resume-cli compatibility shims** in `resume-cli/resume_cli/__init__.py` (both commented): (a) `_ingest_job` folds `preferred[]` into the `requirements` superset so ingest is lossless under the new JobModel split; (b) `_core_operation`/`_hallucinated_operation` now emit `schema_version/op/reason/provenance` so grounded ops validate and the hallucinated op is rejected on GROUNDING (not missing fields). These are minimal shims to keep smoke green; proper `preferred[]` handling + agent-emitted reason/provenance are owned by RKIT-I-0016/0036/0038. **Lesson: T-0005/T-0008 contract tightening breaks downstream operation/job producers — check `--smoke` (not just `--pr`) after any resume-core DTO change.**
- New resume-core internal modules `dates.py`, `claim_fields.py`, `pointers.py` (stdlib-only helpers).

## 6. Metis tooling quirks (do NOT re-fight)

MCP `create_document` fails to resolve these parents ("not found at expected path"); use the `metis` CLI: `metis create task --initiative RKIT-I-00NN "title"` (auto-syncs). Task-parent resolution keys off `strategy_id` + physical dir. RKIT-I-0051 was relocated to `strategies/RKIT-S-0001/initiatives/` with `strategy_id: RKIT-S-0001` so creation resolves (supersedes the old "don't move I-0051 dir" note). Everything is UNPUSHED — Daniel says "push" when ready.

---

# Handoff — 2026-08-13 (post-audit, post-ADR, post-re-baseline)

Read this first when resuming work on resume-kit-2. It supersedes any impression the work-log "complete" claims or the green gates give you.

## 1. The one thing you must internalize

**All gates are green (PR: 188 tests, smoke, future-contract) and green does NOT mean done.** A full 18-agent alignment audit on 2026-08-13 (report: `.agents/audit-2026-08-13.md`) verified by execution that actual product depth is ~25-55% per package. The tests are fixture-tuned; several are vacuous; a few product paths are gamed to satisfy them. Do not trust `.agents/work-log.md` "complete" claims — they describe gate-passing, not contract completeness.

Depth estimates from the audit: resume-agent ~25%, workflow ~30%, resume-plugin ~30%, resume-cli ~35%, resume-core ~40%, career-store ~40%, career-mcp ~45%, resume-render ~50%, test-infra ~55%.

## 2. What was done on 2026-08-13 (this session)

1. **Alignment audit** of code vs `PRODUCT_VISION_AND_CONTRACTS.md` / `CONTRACT_SURFACE_ALIGNMENT.md` / TEST_SPECs / Metis docs. Polished report at `.agents/audit-2026-08-13.md`; the full raw per-document findings were delivered to Daniel as `audit_summary.txt` (not in repo).
2. **All six ADRs decided** (RKIT-A-0001..0006, `decision_maker: Daniel Cassil`, `decision_date: 2026-08-13`). RKIT-A-0006 is new and is the keystone — read it before touching any protected test.
3. **All 49 initiatives re-baselined**: accurate current-state deltas, known defects with file:line in Requirements, machine-readable `blocked_by` dependency graphs, artificial serializations removed, boilerplate replaced with real design content. Every doc contains "Re-baselined 2026-08-13".
4. **RKIT-I-0051 created** (Executable Release Gate, complexity L) — owns the previously-unowned release tier (E2E, Job B persistence, recovery, migration fixtures, data snapshots, release runner). Two waves; Wave 1 is startable now, Wave 2 blocked on RKIT-I-0041.
5. **Rescopes**: RKIT-I-0009 → manifest canonicalization + closure (its original outcome is already implemented; sized S). RKIT-I-0033 → "PDF Support Policy: Honest Unsupported Status" per RKIT-A-0004 (sized S).
6. Vision Current State and strategy change log updated to match reality.

## 3. The six decided ADRs (one line each)

- **RKIT-A-0001** career-store: public `getMigrationState()`; `interactions` table required now, append-only, structurally unable to alter verification state.
- **RKIT-A-0002** career-mcp: stdio JSON-RPC server first; single-user local; store by DB path (server) / injection (in-process); camelCase `store_surface.json` is the ONLY store interface; package `tool_surface.json` is the single canonical manifest; nine mandatory mutation-audit fields.
- **RKIT-A-0003** resume-agent: provider-neutral `ModelAdapter`; first live runtime = Anthropic Claude API; official gates ALWAYS use the deterministic fake adapter; new public `proposeEquivalences()`; model-call audit metadata defined.
- **RKIT-A-0004** render: PDF is NOT an MVP release target; `renderPdf` must report honest `unsupported` (immediate fix, no deps); future candidate fpdf2/ReportLab+pypdf via ADR amendment.
- **RKIT-A-0005** plugin: first host = Claude Code plugin bundle; tools invoke public Python APIs; mapped commands must exist in `cli_surface.json`; presenters bind to resume-core-owned DTO shapes; local-files+career-DB-only permissions.
- **RKIT-A-0006** ★ Documented contracts are authoritative over implementation drift. Restores contract enums (`imported`, `not_applicable`), mandatory op `reason`/`provenance`, §4.3 MatchResult fields, §13 config vocabulary, char-based `required_reduction`, impossible-date rejection, surface authority. **Grants express permission to edit protected contract tests / boundary tests / surface manifests SOLELY to realign them to documented contracts, strengthen-only.** Any other protected-surface edit still requires Daniel's explicit permission.

## 4. Highest-severity verified code defects (all have owning initiatives now)

| Defect | Where | Owning initiative |
|---|---|---|
| `validateFinalResume` hardcodes `applied_operations=[]` → legitimately applied grounded changes FAIL final validation (breaks DoD 10-14) | `resume-core/resume_core/domain.py:611` | RKIT-I-0004 (its chunk 1) |
| Honesty gate = 5-entry fixture lookup; any other fabrication validates ungrounded | `domain.py:47-53, 1103-1105` | RKIT-I-0004 |
| "incorrect"/"yesterday I did nothing" count as user confirmation (substring match) → inferred promoted to user_verified | `career-store/career_store/store.py:51-76, 1243-1254` | RKIT-I-0006 |
| Related Azure→AWS relationship resolves AWS as `exact_match` (term pollution) even with allow_related_as_equivalent=False | `store.py:975, 812-820` | RKIT-I-0007 |
| Workflow run-ID = config hash → same-config runs collide/overwrite | `workflow/__init__.py:41` | RKIT-I-0022 |
| RESOLVE_GAPS→MATCH_BASE loop never terminates; CLI never drives checkpoints at all (`resume run` echoes the list) | `workflow/__init__.py:76-77`; `resume-cli/resume_cli/__init__.py:316-324` | RKIT-I-0023 / RKIT-I-0040 |
| CLI `validate` can never fail; `inspect` fabricates exact_match; CLI self-injects the hallucination it "rejects" | `resume_cli/__init__.py:269-284, 338, 250-252` | RKIT-I-0039 / 0037 / 0038 |
| DOCX parse-back trusts renderer sidecar, detects only omissions (tampered additions pass) | `resume-render/resume_render/__init__.py:493-497, 563-567` | RKIT-I-0032 |

## 5. Metis state & how to proceed

- 58 active docs: vision (draft), strategy RKIT-S-0001 (shaping), 50 initiatives (all `discovery`), 6 ADRs (all `decided`). Zero tasks exist yet.
- **Unblocked initiatives (blocked_by: [])**: RKIT-I-0001, 0005, 0009, 0010, 0016, 0022, 0029, 0033, 0035, 0047, and 0051 (Wave 1). Everything else declares its blockers in frontmatter — trust the graph, it was set deliberately (some old serializations were removed on purpose; don't re-add them).
- Initiatives must go discovery → design → ready → decompose before tasks. **Human-in-the-loop rule: check with Daniel before phase transitions, decomposition, or directional changes.** When decomposing, every task must carry a `Recommended Agent: <model> + <effort>` line per Daniel's global rubric (decomposition itself: opus + high).
- Quirks (do NOT "fix"): `metis lint_workspace` reports ~62 placeholder errors that are FALSE POSITIVES (naive brace-matching on legitimate inline DTO-shape examples). RKIT-I-0051 lives at `.metis/strategies/NULL/initiatives/RKIT-I-0051/` by metis's own doing (frontmatter parent is correct); RKIT-I-0050 was a mis-parented duplicate, archived.

## 6. Remaining follow-ups Daniel has NOT yet commissioned (proposed order)

1. **Critical code fixes** (table above) with strengthened tests in the same change — the A-0006 authorization covers the test realignment. ~~Natural first target: the `validateFinalResume` one-line-class fix + DoD 10-14 regression test (RKIT-I-0004 chunk 1).~~ **DONE 2026-08-13** (same day, follow-on session): fix + 6-test E2E suite at `tests/e2e/test_grounded_tailoring_final_validation.py`, adversarially verified, gates green, uncommitted — see the work-log entry and RKIT-I-0004's progress notes. Remaining rows of the defect table are still open.
2. **Root-doc bug fixes** (these actively mislead implementing agents):
   - `IMPLEMENTATION_PLAN.md:70,79,119` + `.agents/README.md:15`: the focused worker command is broken as written (unittest doesn't glob dotted names; `python` doesn't exist here — use `python3 -m unittest tests.contract.test_<pkg>_contract tests.boundary.test_<pkg>_guardrails` with explicit names). Even corrected it fails on fresh checkout unless you `pip install -e .` first — no doc says so.
   - `PROJECT_STRUCTURE_AND_TEST_STRATEGY.md` folder table: career-store is product section 6 (not 5), career-mcp is 7 (not 6); resume-core row omits its own section 5.
   - Canonical-command ambiguity: `run_tests.py --root .` vs `run_gate.py --pr --root .` (both work; pick one).
   - `PRODUCT_VISION_AND_CONTRACTS.md` §3: "resume-agent/render may live inside the CLI" contradicts the frozen layout; package list omits `workflow`.
   - `SMOKE_TEST.md` fixture set diverges from what the harness uses (incl. SaaS preferred-vs-required) — owned by RKIT-I-0051 REQ-011.
3. **Design review + decomposition** of the unblocked initiatives, starting with RKIT-I-0001 (everything in resume-core hangs off it) and RKIT-I-0051 Wave 1 (its red baselines feed the package initiatives' TDD).

## 7. Commands

```sh
python3 tools/run_gate.py --pr --root .      # PR gate (188 tests, green at handoff)
python3 tools/run_gate.py --smoke --root .   # smoke gate (green at handoff)
pip install -e .                             # required before running focused unittest commands directly
```

Authority order (per IMPLEMENTATION_PLAN): user instructions → CONTRACT_SURFACE_ALIGNMENT.md → package TEST_SPEC.md → surface manifest → PRODUCT_VISION_AND_CONTRACTS.md/SMOKE/E2E. Guardrails and non-A-0006 protected surfaces remain untouchable without Daniel's explicit permission.
