# Experiment Analysis Agent Design

## Objective

Add a deterministic Phase 2 `experiment_analysis` agent that runs after retrieval, reads retrieved evidence plus stored experiment metrics, and writes a structured analysis artifact into shared state without changing the existing `/ask` API behavior.

## Current Context

The current Phase 2 graph is:

`START -> planner -> retrieval -> END`

The planner already includes `experiment_analysis` in `required_agents` for higher-order intents such as decision support, risk assessment, business impact, and executive summary. Retrieval already writes `retrieved_chunks`, `citations`, `metrics`, and `trace` into the shared state. The `/ask` endpoint remains separate and continues to use `QuestionAnsweringService`.

Experiment metadata and metrics are already stored in Postgres:

- `Experiment.config` contains the ingested metadata payload, including `experiment_id`, `hypothesis`, `primary_metric`, `secondary_metrics`, `imperfections`, and `business_decision`.
- `ExperimentMetric.name` is stored as `<metric_name>:<variant>`.
- `ExperimentMetric.metric_metadata` preserves raw CSV fields such as `variant`, `unit`, `numerator`, `denominator`, `lift_vs_control`, `p_value`, and `notes`.

This makes deterministic, non-LLM analysis feasible without changing ingestion or retrieval contracts.

## Goals

- Add a dedicated experiment analysis implementation under `packages/agents/`.
- Extend the workflow to `START -> planner -> retrieval -> experiment_analysis -> END`.
- Run analysis only when `"experiment_analysis"` is present in `required_agents`.
- Produce a backward-compatible `experiment_analysis` state object that still contains `summary` and `findings`.
- Use existing stored experiment metadata and metric rows to compute simple transparent comparisons.
- Preserve retrieval evidence and citations inside the analysis output where relevant.
- Append trace entries and record analysis metrics.
- Handle missing retrieval context and missing metrics safely.

## Non-Goals

- No OpenAI or other LLM calls.
- No business impact, risk, decision, or executive summary implementations in this issue.
- No causal inference, revenue estimation, or rollout recommendation logic.
- No changes to `/ask`, `QuestionAnsweringService`, or the Phase 1 QA response contract.
- No new CLI surface.

## Proposed Architecture

### 1. Dedicated Analysis Module

Create a dedicated analysis module in `packages/agents/experiment_analysis_agent.py`.

Responsibilities:

- Accept the current `AgentState`.
- Resolve the experiment or experiments to analyze.
- Read experiment metadata and metrics from the database.
- Build a deterministic analysis artifact.
- Return an `AgentStateUpdate` for LangGraph consumption.

This keeps orchestration in `nodes.py` and keeps database read and analysis logic isolated and testable.

### 2. Thin Workflow Node

Add an `experiment_analysis_node` to `packages/agents/nodes.py`.

Responsibilities:

- Skip with a trace entry when analysis is not required.
- Delegate to the injected analysis agent when required.
- Merge metrics in the same style as the retrieval node.

### 3. Workflow Wiring

Update `packages/agents/workflow.py` to:

- accept an optional injected experiment analysis agent,
- register the `experiment_analysis` node,
- add edges `planner -> retrieval -> experiment_analysis -> END`.

Update `packages/agents/service.py` to accept optional agent injection and pass it through to the workflow builder.

## Analysis Resolution Rules

The agent should resolve target experiments in this order:

1. `state["experiment_context"]["experiment_ids"]`
2. experiment identifiers found in `state["citations"]`
3. experiment identifiers found in `state["retrieved_chunks"]`
4. experiment hints from `state["experiment_context"]["filters"]["experiment_hints"]`, matched against `Experiment.name` or stored config `experiment_id`

This order prefers explicit planner context, then retrieval-grounded evidence, then softer hint-based matching.

If multiple experiments are resolved, the agent should analyze the first deterministic match only for this issue and record the number of resolved candidates in metrics and trace. Later phases can support multi-experiment synthesis.

## Database Read Strategy

Use the existing async database helpers:

- `create_database_engine()`
- `create_async_session_factory()`

Within the analysis agent:

- open an async session,
- query the target `Experiment`,
- query all `ExperimentMetric` rows for that experiment,
- dispose the engine in a `finally` block.

The data access should remain read-only and use normal SQLAlchemy async `select()` patterns already used elsewhere in the codebase.

## State Contract Changes

Keep `experiment_analysis` backward-compatible by preserving:

- `summary`
- `findings`

Extend the `ExperimentAnalysis` TypedDict with additive optional fields:

- `status`
- `experiment_id`
- `experiment_name`
- `hypothesis`
- `primary_metric`
- `control`
- `treatment`
- `treatment_control_comparison`
- `observed_lift`
- `statistical_significance`
- `confidence_level`
- `guardrail_metrics`
- `limitations`
- `evidence_citations`
- `analysis_confidence`

Expected semantics:

- `status` is a simple machine-readable status such as `completed`, `insufficient_data`, or `not_applicable`.
- `control` and `treatment` hold the directly observed metric rows for the primary metric comparison.
- `treatment_control_comparison` is a short structured description of the comparison, not an LLM summary.
- `observed_lift` is only populated when present or directly derivable from stored rows.
- `statistical_significance` is only populated when the data explicitly provides a p-value or significance-like indicator.
- `confidence_level` is only populated when the data explicitly provides it; otherwise leave it unset.
- `guardrail_metrics` includes structured secondary metric comparisons when available.
- `evidence_citations` carries forward retrieval citations relevant to the analyzed experiment.
- `analysis_confidence` is a coarse deterministic label such as `high`, `medium`, or `low` based on evidence completeness rather than statistical inference.

## Analysis Logic

### Metadata Extraction

Read from `Experiment.config`:

- `experiment_id`
- `name`
- `hypothesis`
- `primary_metric`
- `secondary_metrics`
- `imperfections`

Use these to populate:

- experiment identity fields,
- hypothesis,
- primary metric name,
- limitations.

### Metric Reconstruction

Group `ExperimentMetric` rows by logical metric name using the `<metric_name>:<variant>` storage format.

For the primary metric:

- locate `control` and `treatment` rows,
- read `value`,
- read `unit`, `numerator`, `denominator`, `lift_vs_control`, `p_value`, and `notes` from `metric_metadata`,
- compute a simple absolute delta when both values exist,
- use stored `lift_vs_control` if present,
- never fabricate p-values, confidence intervals, revenue estimates, or causal claims.

For guardrail metrics:

- use non-primary metrics that have control and treatment rows,
- preserve direct stored values and metadata,
- include a compact list of structured comparisons.

### Retrieval Evidence Use

The analysis agent does not generate new narrative from retrieved text. Instead it uses retrieval to:

- identify the likely experiment when planner context is incomplete,
- carry forward citations for the analyzed experiment,
- surface evidence-backed limitations or contextual notes already retrieved.

If retrieval content is missing, analysis may still proceed from stored metadata and metrics.

### Missing Data Handling

Set `status` to `insufficient_data` when:

- no experiment can be resolved,
- the experiment exists but the primary metric is missing,
- the primary metric does not have both control and treatment rows,
- no usable metadata and no usable metrics are available.

In insufficient-data cases:

- keep `summary` explicit about what is missing,
- keep `findings` narrow and factual,
- preserve any existing citations,
- append limitations describing the data gap,
- record a deterministic `analysis_confidence` of `low`.

## Trace And Metrics

Append trace entries from the analysis node:

- `started`
- `completed`
- `skipped`
- `failed` when unexpected exceptions occur

Record a namespaced metrics block under `metrics["experiment_analysis"]` with:

- `status`
- `latency_ms`
- `resolved_experiment_count`
- `citation_count`
- `guardrail_metric_count`

On unexpected exceptions, the node should:

- return a structured error entry,
- preserve prior state,
- add a `failed` trace entry,
- avoid raising to the caller.

## Testing Strategy

Add or update tests to cover:

- successful analysis for a known experiment using deterministic fake database rows,
- no-op when analysis is not required,
- missing retrieval context,
- missing metrics leading to `insufficient_data`,
- citations preserved in `experiment_analysis`,
- trace entries for skip and completion,
- metrics update under `metrics["experiment_analysis"]`,
- workflow integration showing the new node between retrieval and end,
- service injection support for the analysis agent.

Existing `/ask` tests remain unchanged and serve as regression protection for the acceptance criterion that QA behavior is untouched.

## Files Expected To Change

Create:

- `packages/agents/experiment_analysis_agent.py`
- `tests/test_experiment_analysis_agent.py`

Modify:

- `packages/agents/state.py`
- `packages/agents/nodes.py`
- `packages/agents/workflow.py`
- `packages/agents/service.py`
- `packages/agents/__init__.py` if exports need updating
- `tests/test_agent_state.py`
- `tests/test_agent_nodes.py`
- `tests/test_agent_workflow.py`
- `tests/test_package_imports.py` if public exports change

## Risks And Constraints

- Retrieval uses UUID database identifiers, while synthetic metadata also contains domain IDs like `exp-001-payment-recommendation`; experiment resolution must distinguish these cleanly.
- Not all questions that require `experiment_analysis` will have retrieval hits, so the analysis agent must not depend on retrieval text to function.
- Metrics may contain only one variant for some rows or omit p-values; the analysis logic must treat missing statistical fields as absent rather than negative.
- The state schema must remain permissive enough for additive fields while preserving current tests and existing consumers.

## Recommended Next Issue After #26

Issue #16 should build the next downstream synthesis layer that consumes structured `experiment_analysis` without reparsing prose. It should not redo experiment metric interpretation; it should rely on the artifact produced here and focus on combining analysis, business impact, and risk into a higher-level decision surface.
