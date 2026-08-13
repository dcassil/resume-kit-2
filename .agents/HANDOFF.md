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
