Implemented RKIT-T-0080 test coverage. No commit, no version bump, no protected files edited.

**Files Changed**
- +172 / -0: [test_career_mcp_manifest_parity.py](/Users/danielcassil/Code/resume-kit-2/tests/contract/test_career_mcp_manifest_parity.py:1)
- +5 / -0: [test_career_mcp_contract.py](/Users/danielcassil/Code/resume-kit-2/tests/contract/test_career_mcp_contract.py:416)

Pre-existing dirty Metis files remain untouched: `.metis/.index-dirty`, `.metis/metis.db`, T-0079 doc, T-0080 doc.

**Coverage Added**
- Manifest ↔ `list_tools()` parity on names and `input_schema`.
- Independent registered-handler parity via `CareerMcpAdapter.call_tool` branch names, needed because `list_tools()` is manifest-backed.
- In-memory failure proofs for manifest-only, runtime-only, and schema drift.
- Relationship-type enum subset walk against `career-store/store_surface.json`.
- In-memory `parent` re-add failure proof.
- Byte identity test for `career-mcp/tool_surface.json` == `career-mcp/career_mcp/tool_surface.json`, with failure text naming `career-mcp/tools/sync_tool_surface.py`.
- Bridge import into static gate module with deferred `tools/run_tests.py` wiring comment.

**Mutation Probes**
- Removed `career.get_unverified` from package manifest: `test_package_manifest_matches_runtime_list_tools_names_and_input_schemas` failed with `runtime-only tools: ['career.get_unverified']`; restored.
- Re-added `parent`: `test_manifest_relationship_types_are_store_contract_subset` failed with unsupported `['parent']`; restored.
- Altered generated copy: `test_generated_tool_surface_is_byte_identical_to_package_manifest` failed and named `career-mcp/tools/sync_tool_surface.py`; restored.

**Verification**
- `python3 tools/career_mcp_guardrails.py`: passed
- `python3 tools/run_gate.py --pr --root .`: passed, 414 tests
- `python3 tools/run_gate.py --smoke --root .`: passed
- `python3 tools/run_gate.py --future-contract --root .`: passed, 421 tests
- `straight-jacket verify`: ok
- Snapshot regeneration twice: wrote 13 blocks each pass; `git diff --stat fixtures/expected/` empty
- Focused: `test_career_mcp_contract` ran 22 tests; direct new module ran 7 tests

**Deferred Guardrail Patch**
```diff
diff --git a/tools/career_mcp_guardrails.py b/tools/career_mcp_guardrails.py
--- a/tools/career_mcp_guardrails.py
+++ b/tools/career_mcp_guardrails.py
@@ -69,17 +69,31 @@ def dotted_import_root(name: str) -> str:
 
 
 def load_surface(root: Path) -> tuple[dict, list[Failure]]:
-    path = root / "career-mcp" / "tool_surface.json"
+    path = root / "career-mcp" / "career_mcp" / "tool_surface.json"
+    generated_path = root / "career-mcp" / "tool_surface.json"
     if not path.exists():
         return {}, [
             Failure(
                 path,
                 "Missing machine-readable MCP surface contract.",
-                "Restore career-mcp/tool_surface.json and update it before changing exposed tools.",
+                "Restore career-mcp/career_mcp/tool_surface.json and update it before changing exposed tools.",
             )
         ]
     try:
-        return json.loads(path.read_text(encoding="utf-8")), []
+        failures: list[Failure] = []
+        if generated_path.exists() and generated_path.read_bytes() != path.read_bytes():
+            failures.append(
+                Failure(
+                    generated_path,
+                    "Generated MCP surface copy is not byte-identical to the canonical package manifest.",
+                    "Run career-mcp/tools/sync_tool_surface.py to regenerate career-mcp/tool_surface.json from the package manifest.",
+                )
+            )
+        return json.loads(path.read_text(encoding="utf-8")), failures
     except json.JSONDecodeError as exc:
         return {}, [
             Failure(
@@ -92,7 +106,7 @@ def load_surface(root: Path) -> tuple[dict, list[Failure]]:
 
 
 def validate_surface(root: Path, surface: dict) -> list[Failure]:
-    path = root / "career-mcp" / "tool_surface.json"
+    path = root / "career-mcp" / "career_mcp" / "tool_surface.json"
     failures: list[Failure] = []
```

**Deferred run_smoke.py Patch**
```diff
diff --git a/tools/run_smoke.py b/tools/run_smoke.py
--- a/tools/run_smoke.py
+++ b/tools/run_smoke.py
@@ -136,8 +136,20 @@ def run_smoke(root: Path, workspace: Path, keep_workspace: bool) -> None:
     assert_store_fact(store, "api")
 
     adapter = career_mcp.create_career_mcp(store)
-    tool_names = {tool.get("name") for tool in adapter.list_tools()}
+    listed_tools = {tool.get("name"): tool for tool in adapter.list_tools() if isinstance(tool, dict)}
+    canonical_surface = require_json(
+        root / "career-mcp" / "career_mcp" / "tool_surface.json",
+        "career-mcp/career_mcp/tool_surface.json",
+    )
+    canonical_tools = {tool.get("name"): tool for tool in canonical_surface.get("tools", []) if isinstance(tool, dict)}
+    require(canonical_tools, "canonical package MCP manifest did not declare tools")
+    require(set(listed_tools) == set(canonical_tools), "MCP tool registry did not match canonical package manifest")
+    for name in sorted(canonical_tools):
+        require(
+            listed_tools[name].get("input_schema") == canonical_tools[name].get("input_schema"),
+            f"MCP tool schema drifted from canonical package manifest: {name}",
+        )
+    tool_names = set(listed_tools)
     require("career.search_facts" in tool_names and "career.get_fact" in tool_names, "MCP search/detail tools must be exposed")
```

**Deferred run_tests.py Module List**
```diff
diff --git a/tools/run_tests.py b/tools/run_tests.py
--- a/tools/run_tests.py
+++ b/tools/run_tests.py
@@ -18,6 +18,7 @@ CONTRACT_TEST_MODULES = [
     "tests.contract.test_resume_core_contract",
     "tests.contract.test_career_store_contract",
     "tests.contract.test_career_mcp_contract",
+    "tests.contract.test_career_mcp_manifest_parity",
     "tests.contract.test_workflow_contract",
```

**Surprises**
- The task’s “existing 19 career-mcp contract tests” did not match current discovery; the bridged module now runs 22 total in `test_career_mcp_contract` on this tree.
- Because `list_tools()` loads the same manifest, manifest removal would drift manifest and list output together. The new test also compares registered `call_tool` handler branches to catch that failure shape.
- PR/future gates still emit non-fatal SQLite `ResourceWarning` noise.