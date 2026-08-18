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

- `renderMarkdown`: `ok` for valid RenderableResume/template markdown content; `error` for typed validation/render errors. Covered by `test_markdown_render_preserves_semantic_content_and_excludes_provenance`, `test_markdown_respects_configured_section_order_and_bullets`, `test_malformed_inputs_return_typed_errors_without_tracebacks`, and the status-table parity test.
- `renderDocx`: `ok` for a DOCX artifact with genuine DOCX bytes and the DOCX media type; `error` for typed validation/render errors. Covered by `test_docx_render_reports_artifact_template_version_and_preserves_sections`, `test_docx_ok_artifact_has_media_type_matching_real_docx_bytes`, `test_malformed_inputs_return_typed_errors_without_tracebacks`, and the status-table parity test.
- `renderPdf`: `unsupported` with one of the manifest-owned reasons `format_targets_missing`, `not_in_format_targets`, or `pdf_not_supported_in_mvp`; `error` for validation errors. Future `ok` is specified but `implemented: false` until a real PDF runtime emits bytes beginning with `%PDF`. Covered by `test_manifest_enumerates_pdf_unsupported_reasons`, `test_pdf_render_policy_contracts_return_exact_unsupported_reasons_without_artifacts`, `test_pdf_render_status_artifact_invariant`, and the status-table parity test.
- `measureLayout`: `fits` when estimated pages are within `target_pages`; `overflow` when estimated pages exceed `target_pages`; `error` for typed validation errors. Covered by `test_layout_measurement_reports_overflow_constraints_without_shortening_content`, `tests.contract.test_workflow_contract.WorkflowContractTests.test_render_overflow_routes_back_with_character_count_constraint_evidence`, and the status-table parity test.
- `validateRenderedOutput`: `pass` when parse-back/ATS validation finds no warnings; `fail` when readable output has validation warnings; `error` when readable text cannot be extracted. `unsupported` for pdf-kind artifacts under MVP parse-back policy is specified for RKIT-I-0032 with `implemented: false`. Covered by `test_validate_rendered_output_reports_parse_back_and_ats_findings`, `test_malformed_inputs_return_typed_errors_without_tracebacks`, `test_manifest_status_table_represents_unsupported_reason_contracts_across_functions`, and the status-table parity test.

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
- Preserve employment titles and dates.
- Preserve skill names and ordering according to canonical input/template rules.
- Do not add AWS, GraphQL, Staff title, metrics, management scope, or outcomes.
- Do not remove semantic claims silently.
- Do not include internal provenance metadata in exported resume outputs.

### Markdown rendering

- Produce an output file/string with expected sections.
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

### PDF rendering, where supported

- Producing a PDF means emitting actual PDF bytes; an `ok` PDF result must carry bytes beginning with `%PDF`.
- Produce PDF only when supported by environment/template and runtime policy.
- Validate text extraction from PDF.
- Detect rendering failures or missing text.
- Report PDF as unsupported without failing non-PDF release targets when policy allows; covered by `test_pdf_render_policy_contracts_return_exact_unsupported_reasons_without_artifacts`, `test_pdf_render_status_artifact_invariant`, and `test_pdf_export_skips_with_notice_without_fabricated_artifact_or_pipeline_error`.

### Layout measurement

- Return page estimate and status.
- Return overflow status when target pages are exceeded.
- Include target pages, estimated pages, and `required_reduction`/`requiredReduction` as integer character counts, not page deltas.
- Never silently shorten content to fit target pages.
- Ensure overflow routes back to selection/rewrite workflow.
- Character-count unit is covered by `test_layout_measurement_reports_overflow_constraints_without_shortening_content` and `tests.contract.test_workflow_contract.WorkflowContractTests.test_render_overflow_routes_back_with_character_count_constraint_evidence`.

### Renderer-specific ATS checks

- Detect unsupported characters introduced by template/rendering.
- Detect missing section headings if template breaks them.
- Detect unreadable or empty output.
- Detect if parse-back loses material content.

## Boundary Tests

- Fail if renderer imports career-store or MCP tools.
- Fail if renderer computes match scores.
- Fail if renderer semantically rewrites bullets.
- Fail if renderer applies `ResumeChangeOperation`.
- Fail if renderer mutates `resume/base.json` or `resume/working.json`.

## Smoke Coverage

The smoke fixture must prove:

- Markdown and DOCX export can be created,
- renderer does not modify semantic content,
- render validation passes,
- overflow is reported rather than silently deleted.

## E2E Coverage

The E2E fixture must prove:

- Job A render output matches canonical working resume semantics,
- employment titles and dates remain truthful,
- page/layout status is reported,
- overflow causes orchestration to re-run content reduction and final validation,
- final artifacts are included in audit reports.
