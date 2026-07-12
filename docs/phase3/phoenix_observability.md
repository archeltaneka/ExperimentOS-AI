# Phoenix Observability

## Status

Phoenix tracing is integrated as an optional external observability sink for ExperimentOS AI.

- disabled by default
- optional dependency group: `observability`
- no Phoenix server, cloud account, or credentials required for normal tests
- internal ExperimentOS traces, metrics, ids, and reports remain authoritative
- when OpenTelemetry is also enabled, Phoenix export reuses the shared OpenTelemetry provider path
- LangSmith and Phoenix can run together through the composite provider

## Architecture

ExperimentOS internal traces are the source of truth.
Phoenix receives manually created spans through `packages/observability/`.
No application service imports Phoenix, OpenTelemetry, or OpenInference types directly.
Phoenix compatibility now shares the OpenTelemetry exporter foundation instead of introducing a
second competing SDK path when generic OpenTelemetry export is enabled.

Primary modules:

- `packages/observability/models.py`
- `packages/observability/base.py`
- `packages/observability/noop.py`
- `packages/observability/langsmith.py`
- `packages/observability/phoenix.py`
- `packages/observability/composite.py`
- `packages/observability/factory.py`
- `packages/observability/redaction.py`
- `packages/observability/cli.py`

Provider shapes:

- `NoOpObservabilityProvider`
- `LangSmithObservabilityProvider`
- `PhoenixObservabilityProvider`
- `CompositeObservabilityProvider`

## Responsibilities

ExperimentOS internal observability:

- source of truth for application traces, metrics, correlation ids, and reports

LangSmith:

- external trace inspection for the same logical manual spans

Phoenix:

- OpenTelemetry and OpenInference compatible export of the same logical manual spans
- retrieval, prompt, model, workflow, and evaluation trace analysis
- local or remote collector support

## Manual Instrumentation Strategy

- ExperimentOS-owned manual spans are exported to Phoenix through the provider adapter
- the existing trace hierarchy is preserved
- no direct Phoenix calls are scattered through business services
- no LangChain or LangGraph global instrumentor is initialized
- OpenTelemetry provider ownership stays singular when Phoenix and generic OTLP are both enabled
- auto-instrumentation remains a future extension point and is out of scope for this issue

## Instrumented Surfaces

- `POST /ask`
- `agent_workflow`
- `legacy_rag`
- retrieval operations
- prompt rendering and prompt provenance
- LLM generation spans for prompt-backed flows
- deterministic workflow node exports
- evaluation entrypoints:
  - `evaluation.rag`
  - `evaluation.agent`
  - `evaluation.agent_e2e`
  - `evaluation.ragas`
  - `evaluation.deepeval`
  - `evaluation.prompt_regression`
  - `evaluation.factuality`
  - `evaluation.baseline`

## Trace Hierarchy

### `/ask` with `agent_workflow`

`ask_request`

- `workflow`
- `planner`
- `retrieval`
- `experiment_analysis`
- `business_impact`
- `risk_assessment`
- `decision`
- `human_approval`
- `executive_summary`
- `response_serialization`

### `/ask` with `legacy_rag`

`ask_request`

- `legacy_rag`
- `retrieval`
- `prompt_rendering`
- `llm_generation`
- `response_serialization`

Span kinds follow the manual mapping in the Phoenix adapter:

- `ask_request`, `workflow`: `AGENT`
- `retrieval`: `RETRIEVER`
- `llm_generation`: `LLM`
- prompt-backed and deterministic child spans: `CHAIN`
- evaluation roots: `EVALUATOR`

## Configuration

Install optional dependencies when you want real Phoenix export:

```powershell
uv sync --group observability
```

Enable local Phoenix export:

```powershell
$env:EXPERIMENTOS_PHOENIX_ENABLED = "true"
$env:EXPERIMENTOS_PHOENIX_ENDPOINT = "http://127.0.0.1:6006/v1/traces"
$env:EXPERIMENTOS_PHOENIX_PROJECT = "experimentos-local"
```

Enable remote export:

```powershell
$env:EXPERIMENTOS_PHOENIX_ENABLED = "true"
$env:EXPERIMENTOS_PHOENIX_ENDPOINT = "https://your-collector.example.com/v1/traces"
$env:EXPERIMENTOS_PHOENIX_API_KEY = "..."
```

Keep metadata-only export:

```powershell
$env:EXPERIMENTOS_PHOENIX_TRACE_INPUTS = "false"
$env:EXPERIMENTOS_PHOENIX_TRACE_OUTPUTS = "false"
$env:EXPERIMENTOS_PHOENIX_TRACE_RETRIEVAL_CONTENT = "false"
$env:EXPERIMENTOS_PHOENIX_TRACE_PROMPT_CONTENT = "false"
```

Supported configuration fields include:

- `EXPERIMENTOS_PHOENIX_ENABLED`
- `EXPERIMENTOS_PHOENIX_ENDPOINT`
- `EXPERIMENTOS_PHOENIX_API_KEY`
- `EXPERIMENTOS_PHOENIX_PROJECT`
- `EXPERIMENTOS_PHOENIX_ENVIRONMENT`
- `EXPERIMENTOS_PHOENIX_TRANSPORT`
- `EXPERIMENTOS_PHOENIX_SAMPLING_RATE`
- `EXPERIMENTOS_PHOENIX_TRACE_INPUTS`
- `EXPERIMENTOS_PHOENIX_TRACE_OUTPUTS`
- `EXPERIMENTOS_PHOENIX_TRACE_RETRIEVAL_CONTENT`
- `EXPERIMENTOS_PHOENIX_TRACE_PROMPT_CONTENT`
- `EXPERIMENTOS_PHOENIX_REDACT_SENSITIVE_DATA`
- `EXPERIMENTOS_PHOENIX_HEADERS`
- `EXPERIMENTOS_PHOENIX_TAGS`

## Correlation

Phoenix spans preserve ExperimentOS correlation values, including:

- `experimentos.trace_id`
- `experimentos.metadata.experimentos_trace_id`
- `request_id` for `/ask`
- `workflow_execution_id` for `agent_workflow`
- execution mode and environment metadata

The same logical trace id can be exported to internal reports, LangSmith, and Phoenix without
making any external run id part of the application API.

## Retrieval, Prompt, And Model Metadata

Safe metadata recorded by manual spans includes:

- retrieval counts, latency, similarity summaries, experiment ids, and document ids
- prompt id and prompt version
- LLM provider label, model label, token counts, latency, and input or output lengths
- workflow intent, required agents, decision status, approval status, and citation counts
- evaluation scope, dataset identifiers, mode, and metric execution summaries

## Redaction And Payload Controls

The Phoenix adapter reuses the shared redaction policy.

Redacted or omitted by default:

- API keys, tokens, cookies, passwords, and DSNs
- prompt bodies
- response bodies
- unrestricted retrieved chunk text
- hidden reasoning

Payload controls:

- maximum string length
- maximum collection length
- maximum metadata depth
- maximum retrieval record count

## Sampling And Failure Behavior

- tracing is fully off by default
- error traces can still be exported when always-trace-errors is enabled
- provider failures do not break requests by default
- composite mode isolates failures between LangSmith and the OpenTelemetry or Phoenix export path

## Diagnostics

Status:

```powershell
uv run python -m packages.observability.cli status
```

Provider validation:

```powershell
uv run python -m packages.observability.cli validate --provider phoenix
```

Dry-run without network calls:

```powershell
uv run python -m packages.observability.cli dry-run --provider phoenix
```

Smoke test with explicit enablement:

```powershell
uv run python -m packages.observability.cli smoke-test --provider phoenix
```

## Limitations

- no Phoenix datasets, experiments, annotations, or hosted evaluations
- no LangChain or LangGraph auto-instrumentation
- no generic application-wide OpenTelemetry rollout
- no cross-service distributed tracing
- no production alerting
