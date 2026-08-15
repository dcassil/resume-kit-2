---
id: contract-test-rewrite-test-spec
level: task
title: "Contract-test rewrite, TEST_SPEC grounding obligations, skip-guardrail finding; I-0023 close-out"
short_code: "RKIT-T-0064"
created_at: 2026-08-15T03:11:05.482223+00:00
updated_at: 2026-08-15T03:30:29.250916+00:00
parent: workflow-deterministic-checkpoint
blocked_by: [RKIT-T-0063]
archived: false

tags:
  - "#task"
  - "#phase/active"


exit_criteria_met: false
strategy_id: RKIT-S-0001
initiative_id: RKIT-I-0023
---

# Contract-test rewrite, TEST_SPEC grounding obligations, skip-guardrail finding; I-0023 close-out

## Parent Initiative

[[RKIT-I-0023]]

## Objective

Close out RKIT-I-0023 (Requirement 5 + Testing Strategy): finish the strengthen-only contract-test rewrite, rephrase workflow/TEST_SPEC.md:50-61 state-machine cases as grounding obligations and add the :57 loop-termination case, produce the structural skip-guardrail replacement finding for the protected tools/workflow_guardrails.py keyword blocklist, and run the three-gate close-out with a mutation probe.

## Acceptance Criteria

## Acceptance Criteria

- [ ] Gap check: every Testing Strategy item has a named test — boolean-advance rejection + grounded-ref advances (T-0061), non-empty blocking_reasons naming unmet requirements (T-0061), loop-termination/BUILD_SELECTION_PLAN reachability (T-0062), hallucination-gate cases (T-0063); add anything missing.
- [ ] workflow/TEST_SPEC.md:50-61 rephrased as grounding obligations (evidence resolves against persisted artifacts/DTOs/run state, not presence-only); the :57 loop-termination case added — strengthen-only, guardrail-compatibility checked first.
- [ ] The protected tools/workflow_guardrails.py checkpoint-skip keyword blocklist (~:87-102) CANNOT be edited (approvals deferred): write the exact structural replacement (no path reaches a checkpoint's successor without a recorded grounded transition) as a ready-to-apply patch snippet in the task doc/report, AND add an UNPROTECTED unit test enforcing the same structural invariant so coverage exists now.
- [ ] Mutation probe documented: re-accepting bare-boolean evidence (or removing a required-evidence declaration) fails the suite; restored green.
- [ ] New workflow unit modules (if any) listed for the protected run_tests.py batch.
- [ ] Close-out gates ALL green: --pr, --smoke, --future-contract; counts reported; no weakening of any existing assertion.

## Implementation Notes

### Technical Approach

Established close-out pattern. The skip-guardrail structural check as an unprotected test: walk the state machine's transition recording and assert every reached checkpoint has a recorded grounded transition behind it.

### Dependencies

RKIT-T-0063 (all mechanisms final).

### Risk Considerations

workflow_guardrails.py parsing of TEST_SPEC — check before spec edits; deferral discipline with line refs.

### Execution profile

Recommended Agent: opus + medium

Rationale: consolidation with one protected-patch authoring piece.

## Status Updates

- 2026-08-15: Gap check found all initiative Testing Strategy requirements mapped to named tests: `test_valid_transition_sequence_requires_grounded_checkpoint_evidence`, `test_bare_boolean_checkpoint_evidence_is_typed_rejection`, `test_legacy_persisted_boolean_evidence_is_ungrounded`, `test_run_state_evidence_must_exist_in_persisted_checkpoint_result`, `test_invalid_transitions_are_blocked_with_reasons`, `test_deadlock_regression_verified_fact_reruns_match_then_reaches_complete_gate`, `test_completion_gate_blocks_hallucination_flagged_non_rejected_operation_from_persisted_state`, `test_completion_gate_allows_hallucination_flagged_persisted_rejected_operation`, and `test_completion_gate_hallucination_rejection_passes_vacuously_without_flagged_operations`. Added unprotected unit coverage `tests.unit.test_workflow_grounded_transition_invariant.WorkflowGroundedTransitionInvariantTests.test_reached_checkpoints_have_recorded_grounded_transitions`.
- 2026-08-15: Checked `tools/workflow_guardrails.py` read-only before editing spec; it validates `workflow/workflow_surface.json` and scans code under `workflow/`, with no parser over `workflow/TEST_SPEC.md`. `python3 tools/workflow_guardrails.py --root .` passed. Rephrased `workflow/TEST_SPEC.md:50-61` as grounded transition obligations and added the post-gap loop termination/BUILD_SELECTION_PLAN reachability case.
- 2026-08-15: Mutation probe temporarily re-accepted bare boolean EvidenceRefs in `workflow/__init__.py`; `tests.contract.test_workflow_contract` failed exactly at `test_bare_boolean_checkpoint_evidence_is_typed_rejection` (`ok` != `blocked`). Restored the verifier; the same 27-test workflow contract suite passed.
- 2026-08-15: Protected `tools/workflow_guardrails.py` was not edited. Ready-to-apply structural replacement patch:

```diff
*** Begin Patch
*** Update File: tools/workflow_guardrails.py
@@
 REQUIRED_CHECKPOINTS = [
@@
     "COMPLETE",
 ]
+CHECKPOINT_SUCCESSORS = dict(zip(REQUIRED_CHECKPOINTS, REQUIRED_CHECKPOINTS[1:]))
@@
     "rewrite_bullet": "Semantic rewrite belongs to agent proposal plus core validation, not workflow.",
     "truncate_to_fit": "Render overflow returns constraints; workflow must not silently truncate content.",
-    "agent_says_ok": "No checkpoint may be skipped because an agent output appears plausible.",
-    "looks_correct": "No checkpoint may be skipped because output looks plausible.",
-    "skip_checkpoint": "Workflow must not skip required checkpoints.",
-    "bypass_checkpoint": "Workflow must not bypass required checkpoints.",
 }
@@
 def validate_surface(root: Path, surface: dict) -> list[Failure]:
@@
     return failures
+
+
+def validate_grounded_transition_structure(root: Path) -> list[Failure]:
+    path = root / "workflow" / "__init__.py"
+    if not path.exists():
+        return [
+            Failure(
+                path,
+                "Missing workflow runtime implementation.",
+                "Restore workflow/__init__.py so transition recording can be structurally verified.",
+            )
+        ]
+    text = path.read_text(encoding="utf-8")
+    try:
+        tree = ast.parse(text, filename=str(path))
+    except SyntaxError as exc:
+        return [
+            Failure(
+                path,
+                f"Python source cannot be parsed: {exc.msg}.",
+                "Fix syntax before transition-recording guardrails can run.",
+                exc.lineno,
+            )
+        ]
+    failures: list[Failure] = []
+    requirements = _literal_assignment(tree, "_ADVANCE_REQUIREMENTS")
+    if not isinstance(requirements, dict):
+        failures.append(
+            Failure(
+                path,
+                "Workflow does not declare machine-readable transition evidence requirements.",
+                "Declare _ADVANCE_REQUIREMENTS with at least one grounded EvidenceRef requirement for every checkpoint successor.",
+            )
+        )
+    else:
+        missing = [
+            checkpoint
+            for checkpoint in REQUIRED_CHECKPOINTS[1:]
+            if checkpoint not in requirements or not requirements[checkpoint]
+        ]
+        if missing:
+            failures.append(
+                Failure(
+                    path,
+                    f"Checkpoint successors can be reached without declared grounded evidence: {missing}.",
+                    "Every successor checkpoint must have a required EvidenceRef declaration before advanceCheckpoint can accept it.",
+                )
+            )
+
+    advance = _function_node(tree, "advanceCheckpoint")
+    advance_source = ast.get_source_segment(text, advance) if advance else ""
+    required_snippets = {
+        "accepted audit transition": '_audit("advanceCheckpoint", current, target_checkpoint, True)',
+        "persisted current checkpoint": '"current_checkpoint": target_checkpoint',
+        "persisted stage evidence": '"stage_state": {**run_state.get("stage_state", {}), target_checkpoint: dict(verified_evidence)}',
+        "persisted verified evidence": "target_checkpoint: verified_evidence",
+        "run persistence": "_persist_run(updated)",
+    }
+    for label, snippet in required_snippets.items():
+        if snippet not in advance_source:
+            failures.append(
+                Failure(
+                    path,
+                    f"advanceCheckpoint is missing {label} for grounded transition recording.",
+                    "No path may reach a checkpoint successor unless the accepted transition, current checkpoint, and grounded evidence are recorded in persisted run state.",
+                )
+            )
+    return failures
+
+
+def _literal_assignment(tree: ast.AST, name: str) -> object | None:
+    for node in getattr(tree, "body", []):
+        if not isinstance(node, ast.Assign):
+            continue
+        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
+            try:
+                return ast.literal_eval(node.value)
+            except (SyntaxError, ValueError):
+                return None
+    return None
+
+
+def _function_node(tree: ast.AST, name: str) -> ast.FunctionDef | None:
+    for node in ast.walk(tree):
+        if isinstance(node, ast.FunctionDef) and node.name == name:
+            return node
+    return None
@@
-    if re.search(r"(agent says|agent output|looks correct|plausible)", lowered) and re.search(r"(skip|bypass|complete).*(checkpoint|validation|gate)", lowered):
-        failures.append(
-            Failure(
-                path,
-                "Workflow appears to skip a checkpoint/gate based on agent plausibility.",
-                "No checkpoint may be skipped because an agent output appears plausible. Require persisted deterministic evidence.",
-            )
-        )
     return failures
@@
     if surface:
         failures.extend(validate_surface(root, surface))
+    failures.extend(validate_grounded_transition_structure(root))
 
     for path in iter_code_files(root):
*** End Patch
```
- 2026-08-15: Close-out verification: `python3 tools/run_gate.py --pr --root .` passed with 368 tests; `python3 tools/run_gate.py --smoke --root .` passed the installed package smoke harness; `python3 tools/run_gate.py --future-contract --root .` passed with 375 tests; `python3 -m unittest discover -s tests/unit -v` passed with 190 tests. New unit module queued for protected `tools/run_tests.py` batch: `tests.unit.test_workflow_grounded_transition_invariant`. Final Straight Jacket readback remains blocked by pre-existing protected checksum mismatches in `tools/pre-commit-resume-cli-guardrails.sh`, `tools/run_smoke.py`, `tools/run_tests.py`, and `tools/TEST_SPEC.md`; none of those protected files were edited for this task.
