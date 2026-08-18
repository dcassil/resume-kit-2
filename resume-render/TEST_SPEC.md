# resume-render Test Spec

## Contract

`resume-render` converts a validated `RenderableResume` DTO owned by `resume-core` into delivery formats without changing career truth. It may report layout pressure, page estimates, font/spacing details, and renderer-specific ATS issues. It must not rewrite semantic content, select relevance, add skills, change dates, or query career knowledge.

Relevant public surface:

- `renderMarkdown(resume, template)`
- `renderDocx(resume, template)`
- `renderPdf(resume, template)`
- `measureLayout(resume, template)`
- `validateRenderedOutput(file)`

## Status Vocabulary

`resume-render/render_surface.json` owns the per-function status table. `tests.contract.test_resume_render_contract.ResumeRenderSurfaceManifestTests.test_manifest_status_table_matches_reachable_function_statuses` drives each public function across reachable fixtures and asserts the rows marked `implemented: true` match emitted statuses exactly. Rows marked `implemented: false` are asserted not to emit yet, so future work must flip the marker when it lands.

- `renderMarkdown`: `ok` for valid RenderableResume/template markdown content; `error` for typed validation/render errors. Covered by `test_markdown_render_preserves_semantic_content_and_excludes_provenance`, `test_schema_driven_provenance_stripping_removes_sources_evidence_and_arbitrary_keys`, `test_render_time_ats_sanitation_replaces_named_unsupported_characters`, `test_render_time_ats_sanitation_clean_pass_has_no_sanitation_warning`, `test_markdown_respects_configured_section_order_and_bullets`, `test_malformed_inputs_return_typed_errors_without_tracebacks`, and the status-table parity test.
- `renderDocx`: `ok` for a DOCX artifact with genuine DOCX bytes and the DOCX media type; smoke DOCX coverage targets the real `output/resume.docx` bytes, not the `.docx.json` metadata wrapper; `error` for typed validation/render errors. Covered by `test_docx_render_reports_artifact_template_version_and_preserves_sections`, `test_docx_ok_artifact_has_media_type_matching_real_docx_bytes`, `test_skills_formatting_uses_section_metadata_not_section_id`, `test_non_skills_section_never_gets_skills_formatting_without_metadata`, `test_malformed_inputs_return_typed_errors_without_tracebacks`, and the status-table parity test.
- `renderPdf`: `unsupported` with one of the manifest-owned reasons `format_targets_missing`, `not_in_format_targets`, or `pdf_not_supported_in_mvp`; `error` for validation errors. Future `ok` is specified but `implemented: false` until a real PDF runtime emits bytes beginning with `%PDF`. Covered by `test_manifest_enumerates_pdf_unsupported_reasons`, `test_pdf_render_policy_contracts_return_exact_unsupported_reasons_without_artifacts`, `test_pdf_render_status_artifact_invariant`, and the status-table parity test.
- `measureLayout`: `fits` when estimated pages are within `target_pages`; `overflow` when estimated pages exceed `target_pages`; `error` for typed validation errors. Covered by `test_layout_measurement_reports_overflow_constraints_without_shortening_content`, `test_layout_measurement_uses_template_metrics_for_page_estimates_by_name`, `test_layout_measurement_required_reduction_is_same_model_character_count_by_name`, `test_layout_measurement_itemizes_per_section_overflow_and_is_byte_deterministic_by_name`, `tests.contract.test_workflow_contract.WorkflowContractTests.test_render_overflow_routes_back_with_character_count_constraint_evidence`, and the status-table parity test.
- `validateRenderedOutput`: `pass` when bytes-derived parse-back/ATS validation finds no warnings; `fail` when readable output has validation warnings or material semantic additions/omissions; `failed` when a parse-back-capable artifact is corrupt or unreadable and returns a machine-readable cause; `unsupported` when the artifact kind has no bytes parse-back path, including pdf-kind artifacts under MVP parse-back policy; `error` when the input lacks a recognizable artifact/text payload. Covered by `test_validate_rendered_output_reports_parse_back_and_ats_findings`, `test_validate_rendered_output_structural_checks_clean_pass_by_name`, `test_validate_rendered_output_docx_tamper_added_inflated_claim_fails_by_name`, `test_validate_rendered_output_docx_tamper_removed_content_fails_by_name`, `test_validate_rendered_output_lie_sidecar_honest_bytes_passes_by_name`, `test_validate_rendered_output_honest_sidecar_tampered_bytes_fails_by_name`, `test_validate_rendered_output_artifact_text_inert_to_verdict_by_name`, `test_validate_rendered_output_pdf_kind_unsupported_by_name`, `test_validate_rendered_output_corrupt_docx_failed_with_cause_by_name`, `test_validate_rendered_output_detects_declared_encoding_decode_failure_by_name`, `test_validate_rendered_output_detects_tables_by_name`, `test_validate_rendered_output_detects_text_boxes_by_name`, `test_validate_rendered_output_detects_fonts_outside_layout_metrics_by_name`, `test_validate_rendered_output_detects_template_heading_mismatch_by_name`, `test_malformed_inputs_return_typed_errors_without_tracebacks`, `test_manifest_status_table_represents_unsupported_reason_contracts_across_functions`, and the status-table parity test.

`unsupported` means the requested format or artifact kind is not supported under current policy, template targets, or MVP runtime, and the result must carry a machine-readable `reason`. The manifest references the existing `renderPdf.output_contract.unsupported_reasons` enum instead of duplicating it in the status table. Schema-level unsupported+reason representability across functions is covered by `test_manifest_status_table_represents_unsupported_reason_contracts_across_functions`; the concrete renderPdf invariant is covered by `test_pdf_render_policy_contracts_return_exact_unsupported_reasons_without_artifacts`.

`ok` requires a genuine output payload. Artifact results that claim `media_type` must include bytes matching that media type; markdown `ok` is text content with no media type claim. Covered by `test_docx_ok_artifact_has_media_type_matching_real_docx_bytes`, `test_pdf_render_status_artifact_invariant`, and the status-table parity test.

## Expected Structure

Tests should expect renderer internals around:

- templates
- Markdown rendering
- DOCX rendering
- optional PDF rendering
- layout measurement
- parse-back validation
- renderer-specific ATS validation
- overflow reporting

## Unit Test Cases

### Semantic neutrality

- Render all validated canonical resume sections without changing text meaning.
- Validate renderer input against the core-owned `RENDERABLE_RESUME_SCHEMA`.
- Strip renderer input recursively according to the core-owned `RENDERABLE_RESUME_SCHEMA`: fields absent from the schema, including provenance under `sources`, `evidence`, or arbitrary names, must not render; legitimate schema fields must survive verbatim.
- Preserve employment titles and dates.
- Preserve skill names and ordering according to canonical input/template rules.
- Select skills-section formatting from core-owned section metadata such as `section.format == "skills"`, not from a hardcoded `section.id`.
- Do not add AWS, GraphQL, Staff title, metrics, management scope, or outcomes.
- Do not remove semantic claims silently.
- Do not include internal provenance metadata in exported resume outputs.

### Markdown rendering

- Produce an output file/string with expected sections.
- Validate Markdown by treating the text content itself as the bytes-derived artifact text; Markdown results do not need an external parser, but renderer sidecar-only `text` fields must not certify non-Markdown artifacts.
- Respect configured section order.
- Render bullets consistently.
- Preserve ATS-safe characters after sanitation.
- Validate output by parsing text back and comparing semantic content.

### DOCX rendering

- Produce a DOCX artifact.
- Preserve expected sections/order.
- Preserve bullet content as real DOCX list paragraphs: bullet paragraphs must use `w:numPr` with the `ListParagraph` style and a `word/numbering.xml` relationship, not flattened text-only paragraphs.
- Generate `word/styles.xml` defining every paragraph style referenced by `word/document.xml`, including `Title`, `Heading1`, `Heading2`, `body`, and `ListParagraph`.
- Apply template layout metrics to DOCX XML: default `layout-metrics.v1` uses Aptos 11 pt body text, Aptos Display 14 pt heading text, single line spacing, 0 pt paragraph-after spacing, 0.5 inch margins, and bullet indent 0.25 inch. Template `layout` may override `fonts.body`, `fonts.heading`, `spacing`, `margins_in`, and `bullet`; unknown layout keys are typed validation errors. Markdown treats layout metrics as a typographic no-op.
- Preserve factual fields.
- Pass renderer validation.
- Support template version reporting.
- Validate DOCX verdicts exclusively from `content_base64` decoded as a DOCX zip and parsed from `word/document.xml`; renderer-reported sidecar text may appear only as `renderer_reported_text` diagnostics and must not affect status, warnings, missing sections, semantic differences, or ATS findings.
- Detect material semantic additions and omissions with a bidirectional, casefolded, whitespace-collapsed, punctuation-stable token multiset comparison against the expected `RenderableResume`. Formatting markers, heading/bullet glyphs, and template-permitted within-section ordering are cosmetic; claim-bearing tokens such as numbers, titles, technologies, employers, and dates are material. When classification is uncertain, treat the difference as material and fail closed.
- Construct adversarial DOCX tamper fixtures deterministically in tests by rendering DOCX, unzipping, modifying `word/document.xml`, and re-zipping. Required fixture tests are `test_validate_rendered_output_docx_tamper_added_inflated_claim_fails_by_name`, `test_validate_rendered_output_docx_tamper_removed_content_fails_by_name`, `test_validate_rendered_output_lie_sidecar_honest_bytes_passes_by_name`, `test_validate_rendered_output_honest_sidecar_tampered_bytes_fails_by_name`, and `test_validate_rendered_output_artifact_text_inert_to_verdict_by_name`.

### PDF rendering, where supported

- Producing a PDF means emitting actual PDF bytes; an `ok` PDF result must carry bytes beginning with `%PDF`.
- Produce PDF only when supported by environment/template and runtime policy.
- Validate text extraction from PDF.
- Detect rendering failures or missing text.
- Report PDF as unsupported without failing non-PDF release targets when policy allows; covered by `test_pdf_render_policy_contracts_return_exact_unsupported_reasons_without_artifacts`, `test_pdf_render_status_artifact_invariant`, and `test_pdf_export_skips_with_notice_without_fabricated_artifact_or_pipeline_error`.

### Layout measurement

- Return page estimate and status.
- Return overflow status when target pages are exceeded.
- Estimate capacity from `layout-metrics.v1` page geometry, margins, font sizes, line spacing, paragraph spacing, bullet indent, and the renderer's documented glyph-width table; two templates with materially different metrics must produce different estimates for the same content.
- Include target pages, estimated pages, and `required_reduction`/`requiredReduction` as integer character counts, not page deltas.
- Assert exact-fit and known-excess boundary fixtures at value level, including that removing exactly the reported `requiredReduction` characters fits under the same model.
- Include additive `constraints.per_section = [{id, estimated_lines, overflow_chars}]` and `constraints.metrics_version` so downstream workflow can reconstruct the estimate.
- Never silently shorten content to fit target pages.
- Routing overflow back to selection/rewrite is cross-package behavior, not renderer unit scope; it is owned by workflow/resume-cli E2E coverage under RKIT-I-0034 with RKIT-I-0027/RKIT-I-0039. Renderer-side respecification landed in RKIT-T-0117, and the relocated E2E overflow-routing case landed in RKIT-T-0119. Renderer tests only prove the constraint report that those workflows consume.
- Character-count unit is covered by `test_layout_measurement_reports_overflow_constraints_without_shortening_content`, `test_layout_measurement_required_reduction_is_same_model_character_count_by_name`, and `tests.contract.test_workflow_contract.WorkflowContractTests.test_render_overflow_routes_back_with_character_count_constraint_evidence`.

### Renderer-specific ATS checks

- Render-time sanitation replaces ATS-hostile characters covered by the legacy deny list (`smart quotes`, bullet character, NBSP) and reports the named `ats_unsupported_character_sanitized` warning when replacements occur.
- Validate artifact bytes decode as their declared XML encoding and report `ats_encoding_decode:<part>:<encoding>` when a part fails.
- Detect ATS-hostile DOCX constructs by name: `w:tbl` tables report `ats_hostile_construct:w:tbl`, and `w:txbxContent` text boxes report `ats_hostile_construct:w:txbxContent`.
- Detect fonts outside the template layout metrics' declared body/heading families and report `ats_exotic_font:<family>`.
- Detect template heading breakage using the same section-title derivation as rendering; missing or mismatched section headings report `ats_template_heading_mismatch`.
- Detect unreadable or empty output.
- Detect if parse-back loses material content or gains material content not present in the expected resume.
- Preserve corruption diagnostics: unreadable DOCX zip/base64/XML returns `failed` with a machine-readable `cause`, never a sidecar-based pass.

## Boundary Tests

- Fail if renderer imports career-store or MCP tools.
- Fail if renderer computes match scores.
- Fail if renderer semantically rewrites bullets.
- Fail if renderer applies `ResumeChangeOperation`.
- Fail if renderer mutates `resume/base.json` or `resume/working.json`.

## Smoke Coverage

The smoke fixture must prove:

- Markdown and DOCX export can be created,
- DOCX export is validated from real `output/resume.docx` artifact bytes that begin with ZIP magic and contain `word/document.xml`, not from the `.docx.json` wrapper,
- renderer does not modify semantic content,
- render validation passes,
- `tools/run_smoke.py`'s measureLayout overflow smoke step reports overflow rather than silently deleting content, with positive required reduction, constraints, and unchanged input content length.

## E2E Coverage

The E2E fixture must prove:

- Job A render output matches canonical working resume semantics,
- employment titles and dates remain truthful,
- page/layout status is reported,
- overflow causes orchestration to re-run content reduction and final validation,
- final artifacts are included in audit reports.
