---
id: harden-career-mcp-tool-argument
level: initiative
title: "Harden Career-MCP Tool Argument Validation and Response Normalization"
short_code: "RKIT-I-0010"
created_at: 2026-08-13T20:41:37.034250+00:00
updated_at: 2026-08-16T19:24:32.274713+00:00
parent: resume-kit-2-full-product-buildout
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: M
strategy_id: RKIT-S-0001
initiative_id: harden-career-mcp-tool-argument
---

# Harden Career-MCP Tool Argument Validation and Response Normalization Initiative

## Context **[REQUIRED]**

Package: `career-mcp`. Argument validation and response normalization are substantively implemented on the fake-tested path: JSON-schema-subset validation (`career_mcp/__init__.py:207-269`), DTO normalization with sensitive-field stripping (`:284-322`), and an error envelope with SQL scrubbing (`:355-373`). The original outcome ("all career.* tools validate inputs, normalize outputs, and map errors") is therefore mostly satisfied as tested — but the alignment audit verified specific defects on the production path that the FakeCareerStore-only contract tests never reach:

- Rejected mutations break the typed-error contract: `_mutation` (`career_mcp/__init__.py:312-322`) passes through status `rejected`/`error` with no `error: {type, message}` object. Empirically, `career.verify_fact` with `imported` returned status `error` with no `error` key — an agent checking `result['error']['type']` crashes. The tests never hit this because the fake raises exceptions instead of returning rejected dicts.
- Exception-to-error-type classification keyword-matches exception message text (`'confirmation'` → `policy_error`, `'not found'` → `not_found`, else `validation_error`) at `:359-365` — fragile classification that only works for the exact wording of the test double's ValueErrors.
- First-element-only filter mapping: `arguments['verification'][0]` and `arguments['types'][0]` (`:66-69`) silently discard all but the first requested value; a search for `['user_verified','source_stated']` empirically drops all `source_stated` facts.
- The SQL-leak scrub is a blunt keyword blocklist (`:368-373`) that masks any message containing "update" or "delete", including legitimate validation messages.
- `dedupe_key` is accepted by the `career.propose_fact` schema (`tool_surface.json:195-197`) but silently discarded on the real-store path (`:106-114`); `include_conflicts` is likewise dropped in the `career.get_fact` fallback (`:85`).
- The MCP layer does not enforce TEST_SPEC.md:53 "Reject missing evidence for verification operations that require evidence": `evidence_id` is optional in the schema and silently dropped on the real-store path (`:129-133`). Ownership of this requirement is assigned HERE (validation mechanics), not to RKIT-I-0012.

Re-baselined 2026-08-13 against the alignment audit and decided ADRs.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Every non-`ok` result carries a typed `error: {type, message}` object — no envelope-less rejections on any path.
- Error classification is structural (typed store rejection results / exception classes), never message-text keyword matching.
- Multi-valued `verification` and `types` filters are honored in full; no argument accepted by a schema is ever silently dropped (`dedupe_key`, `include_conflicts`, `evidence_id` included).
- Persistence-leak scrubbing is precise: SQL/persistence details never leak, legitimate validation messages pass through.
- Evidence is required and forwarded for verification operations that require it (TEST_SPEC.md:53).

**Non-Goals:**
- Removing the snake_case store dialect and rewriting contract tests against the real store surface — RKIT-I-0011. Fixes here land on the real-store code path and must survive that rewrite.
- Deciding when a mutation requires confirmation or what policy means — RKIT-I-0012 owns policy semantics; this initiative owns the mechanics that carry policy rejections.
- Audit event content — RKIT-I-0013 (it consumes the typed envelopes built here).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- R1: `_mutation` (`career_mcp/__init__.py:312-322`) converts store rejections into `{status, error: {type, message}}`; invariant: `status != 'ok'` implies a well-formed `error` object. Fixes the confirmed envelope-less `verify_fact('imported')` failure.
- R2: The keyword classifier at `:359-365` is replaced by mapping from typed store rejection results and exception classes to the taxonomy `validation_error | policy_error | not_found | store_error`; unknown failures map to `store_error` with a scrubbed generic message — never classified by guessing from message text.
- R3: `career.search_facts` maps the full `verification` and `types` lists (`:66-69` today keeps only element 0); results implement the union semantics the manifest schema implies. Where the store cannot filter multi-valued server-side, the adapter post-filters — it never silently narrows.
- R4: `dedupe_key` (`:106-114`) and `include_conflicts` (`:85`) are forwarded to the store; if a call cannot honor one, the tool returns a typed `validation_error` naming the unsupported argument rather than silently dropping it.
- R5: `career.verify_fact` requires `evidence_id` whenever the requested verification state requires evidence, rejects with `validation_error` when absent, and forwards it (`:129-133` today drops it). Satisfies TEST_SPEC.md:53.
- R6: Scrubbing (`:368-373`) redacts persistence artifacts (SQL fragments, table/column identifiers) without blanking ordinary messages that merely contain verbs like "update" or "delete".
- Package boundary unchanged: no raw SQL, scoring, resume mutation, or plugin presentation behavior.

### Dependencies
- None; this hardening applies to the current adapter and carries into RKIT-I-0011's surface rewrite.

### Blocked Status
- No (blocked_by: []).

## Detailed Design **[REQUIRED]**

**Error envelope.** One result-construction helper builds every tool response with shape `{"tool", "status": "ok" | "rejected" | "error", "data"?, "error"?: {"type", "message"}}`, enforcing the `status != ok ⇒ error present` invariant inside the helper so no code path can emit a rejection without a typed error. Store-returned rejection dicts map their reason codes to taxonomy types; raised exceptions map by exception class (store validation → `validation_error`, missing entity → `not_found`, confirmation/policy signals → `policy_error`, anything else → `store_error`). Message text is used only as the human-readable `message`, post-scrub — never for classification.

**Filter mapping.** `search_facts` passes `verification` and `types` through as lists. Coordination note: `store.searchFacts` currently ignores a `type` filter entirely (`career-store/career_store/store.py:176-178`); until store-side filtering lands (career-store scope), the adapter post-filters returned facts by type and verification state so MCP results are correct regardless, with a contract test pinning union semantics.

**Argument fidelity.** A per-tool accepted-arguments table drives forwarding; an assertion fails any tool call whose validated arguments contain keys the dispatch does not consume. This turns future silently-dropped-argument bugs into test failures instead of quiet data loss.

**Scrub precision.** Replace the substring blocklist with redaction targeted at persistence shapes: patterns for SQL statements (e.g. `INSERT INTO`, `UPDATE <identifier> SET`) and store-internal identifiers, applied to `message` only. Matches are replaced with a generic store-error message; everything else passes through verbatim.

**Migration note.** All fixes target the real-store code path; RKIT-I-0011 later deletes the snake_case branch, so new tests are written against store-shaped results (dict rejections, camelCase calls), not against the fake's exception style.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- Contract tests that drive rejection via store-shaped rejected dicts, not only raised exceptions — the exact blind spot that let the envelope defect ship: assert `error.type`/`error.message` present for every rejected mutation.
- Multi-value filter tests: `verification=['user_verified','source_stated']` and multi-entry `types` return the union (regression for the confirmed first-element-only drop).
- Argument-fidelity tests: `dedupe_key` round-trip (same key twice yields one fact or a typed error), `include_conflicts=true` observably changes `get_fact` output, `verify_fact` without required `evidence_id` yields `validation_error` (TEST_SPEC.md:53).
- Scrub tests: SQL fragments redacted; a validation message containing the word "update" survives intact (regression for the blocklist masking).
- TEST_SPEC strengthening for this scope: add explicit spec items requiring typed error envelopes on rejection paths and forbidding silently dropped schema-accepted arguments — the current spec's looseness is what certified the shallow paths as done.

## Alternatives Considered **[REQUIRED]**

- **Extend the keyword classifier with more phrases.** Rejected: it remains coupled to message wording (it only ever worked for the fake's ValueError strings) and misclassifies as store messages evolve; structural mapping costs barely more.
- **Remove `dedupe_key`/`include_conflicts` from the manifest schemas instead of wiring them.** Rejected: they are contract surface agents rely on (`dedupe_key` enables idempotent retries); shrinking the advertised contract to match a shortcut inverts the authority order RKIT-A-0006 established.
- **Do scrubbing in career-store so MCP never sees SQL text.** Rejected: the no-persistence-leak boundary is a career-mcp responsibility (vision section 7); the store legitimately reports internals to its direct consumers, and MCP must be safe regardless of store message hygiene.

## Implementation Plan **[REQUIRED]**

1. Centralize response construction; enforce the `status != ok ⇒ error` invariant and structural classification (R1, R2).
2. Full-list filter mapping with adapter-side post-filtering and union-semantics tests (R3).
3. Argument-fidelity pass: forward `dedupe_key`, `include_conflicts`, `evidence_id`; add the consumed-arguments assertion (R4, R5).
4. Precise scrubbing with regression tests for masked-message and leaked-SQL cases (R6).
5. TEST_SPEC additions for envelope and argument-fidelity requirements; run the canonical package gate.