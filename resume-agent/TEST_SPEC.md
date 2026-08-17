# resume-agent Test Spec

## Contract

`resume-agent` handles language and semantic proposal work only. It may extract semantics, phrase questions, interpret answers into structured proposals, suggest semantic equivalences, and propose rewrites. It must not own truth, scoring, persistence, validation, or mutation.

Relevant public surfaces:

- `extractResumeSemantics(rawText)`
- `extractJobSemantics(rawJobText)`
- `generateClarificationQuestion(context)`
- `interpretUserAnswer(answer, context)`
- `proposeRewrite(context)`

## Expected Structure

Tests should isolate the agent behind deterministic fixtures and schema validators:

- prompt/input builders
- structured output schemas
- extraction proposal adapters
- question generation
- answer interpretation
- rewrite proposal generation
- uncertainty/confidence handling
- forbidden-addition filters

## Contract Test Cases

### Resume semantic extraction

- Extract resume facts from noisy resume text into schema-constrained proposals.
- Preserve source evidence for extracted claims.
- Do not invent AWS, GraphQL, Staff title, metrics, or management scope when absent.
- Surface model-marked uncertainty explicitly; uncertain extracted items remain visible to validators.
- Return proposals rather than canonical final resume objects.

Golden matrix and covering tests:

- ML-engineer resume: realistic non-fixture resume with Python, TensorFlow, Kubernetes, GCP, Go, Spark, MLOps, experience, education, certification, project, and employment structure. `test_ml_engineer_resume_public_extraction_covers_every_populated_section` asserts every populated section appears; `test_ml_engineer_resume_fixture_represents_every_populated_section` asserts the pinned adapter payload covers those sections.
- Adapter failure path: `test_resume_extraction_adapter_missing_fixture_returns_typed_error_without_partial_proposals` and `test_resume_extraction_adapter_schema_invalid_returns_typed_error_without_partial_proposals` assert typed errors and no partial output when the adapter cannot provide a valid extraction.

### Job semantic extraction

- Extract job title, company if present, seniority, industries, domains, requirements, preferred items, and terminology.
- Preserve source text for every requirement.
- Distinguish required, preferred, and contextual requirements.
- Retain every named skill or requirement concept in each golden JD, including unknown terms that co-occur with known terms.
- Retain co-required concepts independently; one requirement must not delete another.
- Preserve model-sourced numeric confidence values on extraction proposals.
- Surface model-marked uncertain requirements with their uncertainty fields, never by filtering them out.
- Return schema-constrained proposal output for core validation.

Golden matrix and covering tests:

- Python+Spark JD: `test_job_extraction_public_goldens_keep_all_named_skills` asserts Python, Spark, and Kubernetes all appear in requirement proposals; `test_job_extraction_public_goldens_preserve_co_required_concepts` asserts Python and Spark are retained together; `test_job_extraction_preserves_model_sourced_confidence_values` asserts mapped proposal confidence remains the model numeric value; `test_job_extraction_surfaces_model_marked_uncertain_requirement` asserts the uncertain Kubernetes preferred requirement is surfaced with uncertainty fields.
- GraphQL+API JD: `test_job_extraction_public_goldens_keep_all_named_skills` asserts GraphQL, API design, and TypeScript all appear; `test_job_extraction_public_goldens_preserve_co_required_concepts` asserts GraphQL APIs and REST API design remain separate requirements.
- Adapter failure path: `test_job_extraction_adapter_missing_fixture_returns_typed_error_without_partial_proposals` and `test_job_extraction_adapter_schema_invalid_returns_typed_error_without_partial_proposals` assert typed errors and no partial output when the adapter cannot provide a valid extraction.

### Clarification questions

- Receive one code-selected unresolved requirement or tight cluster.
- Phrase a targeted question without choosing the requirement itself.
- Ask about AWS, GraphQL, or architecture only when the context selects those topics.
- Avoid broad fishing expeditions.
- Avoid asking again about facts already verified unless new specificity is required.

Persistence battery and covering tests:

- Partial verified-target filtering: `test_clarification_question_filters_verified_fact_targets_before_adapter_request` asserts verified fact ids are removed before the adapter request and never return in question proposals.
- Fully verified-target short-circuit: `test_clarification_question_returns_no_question_without_adapter_when_all_fact_targets_verified` asserts no adapter call and no question when the selected fact target is already verified.
- Adapter failure: `test_clarification_question_adapter_failure_returns_typed_error_without_canned_fallback` asserts a typed provider error and no fallback question.
- Deleted canned questions: `test_canned_clarification_question_literals_are_deleted_from_production_code` asserts the legacy string table is absent from production code.

### Answer interpretation

- Interpret answers through the answer-interpretation adapter request builder and section-8 schema (`polarity`, `requirementResolutions`, `factProposals`, `evidenceProposals`).
- Map adapter payloads into public proposal aliases while preserving canonical suggested states, model confidence, evidence links, `verification_state`, and `hedge_or_qualifier`.
- Denied answers produce zero positive fact proposals and an explicit-absence requirement resolution (`explicitly_missing`); absence is a resolution concern, not a verification state.
- A deterministic post-guard rejects a schema-valid adapter payload when `polarity == denied` still includes a positive fact proposal, returning a typed `schema_invalid` error with no partial interpretation.
- Qualified answers preserve hedges and remain partial/hedged; they are never flattened into unqualified positives.
- Arbitrary topics route through the adapter; production code must not reintroduce topic-substring interpretation or the hardcoded AWS service list.
- Do not directly persist anything.
- Do not mark verification final without store/core validation.

Negation battery and covering tests:

- Verified AWS defect regression: `test_verified_aws_denial_regression_emits_explicit_absence_without_positive_fact` covers fixture `resume-agent-answer-interpretation-aws-denial` for "No, I have never used AWS professionally".
- Multiple denial phrasings: `test_answer_interpretation_negation_battery_denials_are_explicit_absence_only` covers `resume-agent-answer-interpretation-graphql-denied-havent`, `resume-agent-answer-interpretation-kubernetes-denied-not-professionally`, and `resume-agent-answer-interpretation-terraform-denied-school-only`.
- Denied-positive post-guard: `test_answer_interpretation_denied_positive_fact_post_guard_blocks_payload` creates a deliberately inconsistent in-test fixture and asserts typed rejection.
- Qualified hedge preservation: `test_answer_interpretation_qualified_graphql_preserves_hedge_and_partial_resolution` covers fixture `resume-agent-answer-interpretation-graphql-qualified`.
- Non-fixture/arbitrary topic golden: `test_answer_interpretation_handles_arbitrary_terraform_topic_via_adapter` covers fixture `resume-agent-answer-interpretation-terraform-affirmed`.
- Adapter failure: `test_answer_interpretation_adapter_failure_returns_typed_error_without_partial_interpretation` asserts no partial proposals on fixture miss.
- Deleted legacy interpretation paths: `test_topic_substring_interpretation_and_service_list_are_deleted_from_production_code` asserts the old substring interpreter and AWS service-list snippets are absent.

Non-fixture interview goldens:

- ML-engineer resume and Python+Spark / GraphQL+API jobs exercise extraction with skills and requirements outside the original AWS/GraphQL/architecture canned set.
- Terraform question+answer fixtures (`resume-agent-question-generation-terraform`, `resume-agent-answer-interpretation-terraform-affirmed`) prove interview support for an arbitrary topic selected by code.
- The smoke AWS answer fixture `resume-agent-answer-interpretation-aws-affirmed-smoke` is pinned to the generated CLI question text used by `RESOLVE_GAPS`.

### Rewrite proposals

- Accept context containing original text, allowed facts, job terminology, requirements, prohibited additions, and length/voice constraints.
- Return `ResumeChangeOperation` proposals only.
- Include candidate text (`before`/`after`), facts used (`factIds`/`linked_fact_ids`), requirements targeted (`requirementIds`/`linked_requirement_ids`), non-empty `reason`, provenance, grounding map entries, model confidence, and uncertainty where applicable.
- Propose responsive terminology alignment without unsupported scope.
- Propose API-design emphasis only when verified facts support it.
- Propose AWS/GraphQL additions only where supplied verified facts and selection rules allow.

Grounding, DTO, and constraint battery:

- Rewrite DTO shape: `test_rewrite_proposals_are_resume_change_operations_grounded_in_allowed_facts` asserts emitted operations include in-enum verbs, target path, facts, requirements, provenance, `reason`, confidence, grounding, and proposed status. `test_rewrite_schema_enforces_operation_verb_reason_and_provenance_array` asserts malformed verbs, empty `reason`, and missing provenance fail schema validation.
- Fact-mapping grounding: `test_rewrite_golden_fixture_is_api_fact_only_with_full_grounding_map` asserts every added API term is mapped to an allowed fact. `test_rewrite_grounding_post_guard_rejects_missing_added_term_map_entry` rejects schema-valid output whose added GraphQL term lacks a grounding map entry. `test_rewrite_grounding_post_guard_rejects_out_of_allowed_fact_id` rejects output that cites a fact id outside the supplied allowed set.
- Audit counterexample: `test_api_fact_only_rewrite_never_adds_responsive_design` asserts an API-fact-only rewrite does not add responsive design.
- Voice constraints: `test_rewrite_constraint_fixture_carries_voice_and_length_inputs` asserts the constraint-carrying golden includes voice input, and `test_rewrite_voice_constraint_post_check_rejects_present_tense_fixture` asserts a past-tense request rejects a present-tense leading verb with a typed constraint error.
- Length constraints: `test_rewrite_constraint_fixture_carries_voice_and_length_inputs` asserts the passing golden stays within `max_chars`, and `test_rewrite_length_constraint_post_check_rejects_over_limit_fixture_without_truncation` asserts over-limit generated text is rejected with a typed constraint error rather than shortened.
- Prohibited additions: `test_rewrite_prompt_asset_uses_id_at_version_convention` asserts the prompt contract carries `prohibited_additions`; `test_rewrite_prohibited_addition_post_check_rejects_grounded_banned_term_fixture` asserts a grounded but prohibited added term is rejected with a typed constraint error naming the term.
- Deleted legacy generation paths: `test_topic_substring_interpretation_and_service_list_are_deleted_from_production_code` asserts the template concatenation, insert-everything, and truncation idioms remain absent from production rewrite code.

### Forbidden proposals

- Must not output a mutated full resume as the final authority.
- Must not update SQLite or files.
- Must not set official score.
- Must not silently upgrade inferred facts.
- Must not change actual employment title to match a target JD title.
- Must not inflate years, metrics, team size, user scale, or outcomes.

### Schema and validation handoff

- Every agent output validates against expected structured schema.
- Invalid JSON or malformed schema output is rejected before downstream use.
- Missing fact IDs, requirement IDs, target paths, or grounding metadata block operation use.
- Agent uncertainty is preserved and visible to validators.

### Call-audit records

- Every `ValidatingModelAdapter.complete` call emits one package-owned audit record with exactly `call_id`, `adapter_id`, `adapter_version`, `model_id`, `prompt_hash`, `schema_hash`, `config_hash`, `retry_count`, `outcome`, `timestamps`, and `usage`.
- Outcomes use the closed adapter taxonomy: `ok`, `timeout`, `schema_invalid`, `refused`, `provider_error`.
- Fake-adapter records are deterministic: no wall-clock or random ids enter the fake audit path; identical fake inputs on fresh adapters serialize to byte-identical full records, while distinct inputs produce distinct `call_id`s.
- Prompt hashes come from versioned prompt assets when available; schema hashes use canonical schema JSON; config hashes use `stable_agent_config_hash`.
- Audit emission is owned by the base validating adapter chokepoint so fake and live adapters cannot bypass it by overriding `_complete_unchecked`.

Call-audit covering tests:

- `test_every_adapter_call_emits_record_for_ok_and_all_failure_taxonomies`
- `test_identical_fake_inputs_on_fresh_adapters_yield_byte_identical_records`
- `test_distinct_fake_inputs_yield_distinct_call_ids`
- `test_complete_chokepoint_emits_when_subclass_overrides_unchecked_completion`
- `test_record_self_validation_reports_missing_field_as_typed_error`
- `test_hashes_use_prompt_asset_schema_and_stable_agent_config_hash`
- `test_fake_success_carries_metadata_and_seed_payload`
- `test_deliberately_broken_in_test_fixture_returns_schema_invalid`
- `test_success_uses_configured_model_client_options_output_config_and_metadata`
- `test_refusal_stop_reason_maps_to_refused`

## Determinism Strategy

Because language models may vary, official tests should stabilize behavior through:

- fixed model/config metadata in manifests,
- structured output schemas,
- golden fixture inputs,
- tolerant assertions on question wording,
- strict assertions on structured proposal fields,
- code-owned deterministic downstream decisions.

The agent may vary phrasing. It may not vary official score, fact verification state, mutation application, or workflow transition.

## Smoke Coverage

The smoke fixture must prove:

- agent extraction returns proposals,
- agent asks a targeted question when selected by code,
- user answer interpretation is structured,
- rewrite output is a change operation,
- hallucinated rewrite is rejected by core rather than trusted.

## E2E Coverage

The E2E fixture must prove:

- semantic equivalence proposals are validated before use,
- interview loop resolves AWS/GraphQL/architecture gaps,
- rewrite operations are grounded,
- invalid adversarial proposals enter audit as rejected,
- second-job run does not repeat questions for learned facts.
