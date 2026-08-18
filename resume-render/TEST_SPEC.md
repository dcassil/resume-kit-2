# resume-render Test Spec

## Contract

`resume-render` converts a validated `RenderableResume` DTO owned by `resume-core` into delivery formats without changing career truth. It may report layout pressure, page estimates, font/spacing details, and renderer-specific ATS issues. It must not rewrite semantic content, select relevance, add skills, change dates, or query career knowledge.

Relevant public surface:

- `renderMarkdown(resume, template)`
- `renderDocx(resume, template)`
- `renderPdf(resume, template)`
- `measureLayout(resume, template)`
- `validateRenderedOutput(file)`

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
- Preserve bullet content.
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
- Include target pages, estimated pages, and required reduction.
- Never silently shorten content to fit target pages.
- Ensure overflow routes back to selection/rewrite workflow.

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
