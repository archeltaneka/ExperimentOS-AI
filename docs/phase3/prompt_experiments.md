# Phase 3 Prompt Experiments

Phase 3 now includes a repository-owned prompt experimentation layer for `rag.answer`.
It is offline-first, reproducible, and disabled for runtime traffic by default.

## Scope

- primary deliverable: offline comparison of immutable prompt versions over the frozen QA dataset
- supported prompt surface: `rag.answer`
- preserved defaults:
  - `POST /ask` behavior is unchanged unless an internal experiment context is passed explicitly
  - `agent_workflow` remains the default ask mode
  - `legacy_rag` remains prompt-backed and compatible
- out of scope:
  - automatic prompt optimization
  - automatic winner promotion
  - uncontrolled traffic splitting
  - public production rollout

## Architecture

The framework reuses existing ExperimentOS components instead of creating a second execution path:

- prompt registry:
  - immutable prompt versions remain the source of truth
  - `rag.answer@1` stays active
  - `rag.answer@2` is an experimental candidate only
- prompt execution:
  - `packages.llm.prompts.build_grounded_prompt` now resolves prompt versions with explicit precedence
  - resolution order:
    1. explicit evaluation version
    2. matching prompt experiment context
    3. active registry version
- evaluation reuse:
  - offline QA evaluation uses `QuestionAnsweringService`
  - prompt regression remains the pairwise comparison engine
  - factuality checks remain authoritative guardrails
  - RAGAS and DeepEval remain supplementary through the existing prompt regression path
- observability:
  - experiment metadata is attached to ExperimentOS-owned spans
  - assignment-key hashes are never exported as trace or metric attributes

## Definition Schema

Definitions live in `config/prompt_experiments/` and are version controlled.

Current sample:

- `config/prompt_experiments/rag_answer_abstention_v1_vs_v2.yaml`

Definition fields:

- `experiment_id`
- `name`
- `description`
- `prompt_id`
- `control_version`
- `treatment_versions`
- `hypothesis`
- `primary_metric`
- `secondary_metrics`
- `guardrail_metrics`
- `dataset_id`
- `assignment_strategy`
- `allocation`
- `randomization_unit`
- `seed`
- `status`
- `allow_deprecated_versions`
- `metadata`

Definitions are validated before execution:

- prompt ID must be experimentable
- prompt versions must exist
- control and treatment versions must be distinct
- allocations must be complete and sum to `1.0`
- dataset IDs and metrics must be supported
- seeds must be present
- deprecated prompts require explicit opt-in

## Assignment And Exposure

Runtime assignment exists as a foundation only.
It does not activate public experimentation on its own.

- supported strategies:
  - `fixed`
  - `deterministic_hash`
  - `dataset_alternating`
- runtime activation:
  - disabled by default
  - requires explicit experiment context injection
- hashing:
  - stable SHA-256 truncation
  - no Python `hash()`
  - raw assignment keys are never stored in records or exported in telemetry

An exposure is recorded only when the assigned prompt is actually rendered.
Assignments without prompt use do not count as exposures.
Duplicate exposures for the same execution are suppressed by the in-memory recorder.

## Offline Execution

`PromptExperimentRunner` compares control and treatment variants over the same evaluation dataset and
reuses frozen retrieval results across variants.

Current offline defaults:

- mode: `offline`
- LLM provider: mock
- retrieval source: repository fixture retrieval derived from the QA dataset
- production traffic involved: no

Reports are written to:

- `reports/phase3/prompt_experiments/<experiment_id>.md`
- `reports/phase3/prompt_experiments/<experiment_id>.json`

Every report states:

- experiment definition and hypothesis
- versions under test
- dataset identifier
- assignment strategy
- per-variant metrics
- factuality and regression findings
- recommendation
- limitations
- explicit note that offline results do not prove production causal impact

## Metrics And Guardrails

Implemented offline-safe metrics include:

- `factuality_pass_rate`
- `citation_coverage`
- `regression_pass_rate`
- `prompt_rendering_success`
- `response_availability`
- `latency_ms`

Current guardrails include:

- `critical_factuality_violations`
- `fabricated_revenue_or_roi`
- `fabricated_significance`
- `citation_coverage_non_regression`
- `structured_output_validity_non_regression`
- `latency_tolerance`
- `failure_rate_tolerance`

Critical factuality guardrails block treatment recommendations even when a primary metric improves.

## CLI

Validate a definition:

```powershell
uv run python -m packages.evals.run_prompt_experiment validate --experiment rag-answer-abstention-v1-v2
```

Assign a deterministic runtime variant:

```powershell
uv run python -m packages.evals.run_prompt_experiment assign --experiment rag-answer-abstention-v1-v2 --key safe-test-key
```

Run the offline experiment:

```powershell
uv run python -m packages.evals.run_prompt_experiment run --experiment rag-answer-abstention-v1-v2 --mode offline --report-dir reports/phase3/prompt_experiments
```

Re-render the Markdown report from the stored JSON artifact:

```powershell
uv run python -m packages.evals.run_prompt_experiment report --experiment rag-answer-abstention-v1-v2 --report-dir reports/phase3/prompt_experiments
```

The shared evaluation entry point also exposes the same command group:

```powershell
uv run python -m packages.evals.cli prompt-experiment validate --experiment rag-answer-abstention-v1-v2
```

## Privacy And Safety

- no raw secrets are stored in experiment definitions or artifacts
- no prompt bodies are stored in experiment records
- no retrieved document bodies are persisted in experiment artifacts
- no hidden reasoning is recorded
- no production traffic is split automatically

## Promotion Policy

Winning prompts are not promoted automatically.
Experiment reports are advisory only and are intended to support later manual review.
