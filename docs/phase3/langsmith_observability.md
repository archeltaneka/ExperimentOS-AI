# LangSmith Observability

## Status

LangSmith tracing is integrated as an optional external observability sink for ExperimentOS AI.

- disabled by default
- optional dependency group: `observability`
- no credentials required for normal local development or tests
- internal ExperimentOS traces, metrics, and reports remain authoritative

## Architecture

ExperimentOS owns the trace model and redaction policy through `packages/observability/`.
LangSmith is behind an adapter rather than imported directly by core workflow code.

Primary modules:

- `packages/observability/models.py`
- `packages/observability/base.py`
- `packages/observability/noop.py`
- `packages/observability/langsmith.py`
- `packages/observability/factory.py`
- `packages/observability/redaction.py`
- `packages/observability/cli.py`

## Instrumented Surfaces

- `POST /ask`
- `agent_workflow` execution
- `legacy_rag` execution
- retrieval operations
- prompt rendering and prompt provenance for prompt-backed surfaces
- deterministic agent node exports from workflow state
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

## Configuration

Install the optional dependency group when you want real LangSmith export:

```powershell
uv sync --group observability
```

Enable tracing locally:

```powershell
$env:EXPERIMENTOS_LANGSMITH_ENABLED = "true"
$env:LANGSMITH_API_KEY = "..."
$env:LANGSMITH_PROJECT = "experimentos-local"
```

Keep metadata-only export:

```powershell
$env:EXPERIMENTOS_LANGSMITH_TRACE_INPUTS = "false"
$env:EXPERIMENTOS_LANGSMITH_TRACE_OUTPUTS = "false"
```

## LangGraph Integration

The workflow still relies on ExperimentOS-owned state as the source of truth.
When tracing is enabled, the workflow invoke boundary passes LangGraph metadata and tags through
the `config` argument so native graph tracing can stay coherent with the repository trace id.
Business metadata that is not represented natively is exported from the final workflow state.

## Redaction And Privacy

The adapter redacts or suppresses:

- API keys
- authorization headers and tokens
- cookies
- passwords
- database URLs and DSNs
- full prompt bodies by default
- full response bodies by default
- full retrieved document chunks by default
- hidden reasoning and chain-of-thought

Allowed trace data is intentionally narrow:

- ids
- counts
- statuses
- tags
- model labels
- prompt ids and versions
- durations
- similarity and coverage summaries

## Sampling

- tracing remains fully off by default
- when enabled, sampling is deterministic per trace id
- sampling rate is configurable with `EXPERIMENTOS_LANGSMITH_SAMPLING_RATE`
- errors can still be exported even when the sampling rate is `0.0`

## Correlation

Every traced workflow includes the ExperimentOS trace id in metadata as
`experimentos_trace_id`.

For `agent_workflow`, that value is the preserved internal `run_metadata.run_id`.
For request-level tracing, the `/ask` boundary also carries a request correlation id.

## Failure Behavior

LangSmith failures do not break normal requests by default.

- the primary `/ask` response continues
- deterministic workflow state remains available
- local reports are still written
- provider failures are counted internally on the adapter

Strict mode exists for diagnostics through `EXPERIMENTOS_LANGSMITH_STRICT`, but it is opt-in.

## CLI

Inspect local status:

```powershell
uv run python -m packages.observability.cli status
```

Validate config without sending a trace:

```powershell
uv run python -m packages.observability.cli validate
```

Run a dry-run smoke test:

```powershell
uv run python -m packages.observability.cli smoke-test --dry-run
```

## Limitations

- LangSmith prompt hub is not integrated
- LangSmith datasets and hosted evaluation are not integrated
- Phoenix and OpenTelemetry are still out of scope
- cross-service distributed tracing is still out of scope
- production alerting is not implemented
- agent node spans are exported from final workflow state summaries rather than live node callbacks
