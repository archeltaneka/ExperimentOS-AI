# OpenTelemetry Observability

## Status

OpenTelemetry is integrated as an optional vendor-neutral tracing and metrics foundation for
ExperimentOS AI.

- disabled by default
- optional dependency group: `observability`
- no OpenTelemetry Collector, backend, or network connection required for normal tests
- ExperimentOS internal traces, ids, metrics, and reports remain the source of truth
- LangSmith remains a separate specialized provider
- Phoenix remains compatible through the same OpenTelemetry exporter foundation

## Responsibilities

ExperimentOS internal observability:

- application-owned logical spans
- application-owned request ids and workflow ids
- application-owned markdown and JSON reports
- application-owned evaluation surfaces

OpenTelemetry:

- propagation
- vendor-neutral SDK ownership
- trace export
- metric export
- transport-level FastAPI HTTP spans when enabled

LangSmith:

- specialized LangGraph and AI workflow inspection

Phoenix:

- OTLP-compatible OpenInference backend for the same logical spans

## Architecture

Application services still talk only to `packages/observability/`.

```text
Application services
    ↓
ExperimentOS observability interface
    ↓
ExperimentOS logical spans and metrics
    ├── internal traces and reports
    ├── LangSmith provider
    └── OpenTelemetry provider
         ├── generic OTLP or console export
         └── Phoenix OTLP export
```

Primary modules:

- `packages/observability/models.py`
- `packages/observability/base.py`
- `packages/observability/opentelemetry.py`
- `packages/observability/langsmith.py`
- `packages/observability/composite.py`
- `packages/observability/factory.py`
- `packages/observability/redaction.py`
- `packages/observability/cli.py`

## Provider Ownership

- one OpenTelemetry `TracerProvider` initialization path
- one OpenTelemetry `MeterProvider` initialization path
- explicit provider ownership instead of global provider installation
- FastAPI instrumentation receives the owned tracer and meter providers explicitly
- Phoenix does not install a competing global provider
- when OpenTelemetry and Phoenix are both enabled, the shared OpenTelemetry provider owns export

## Trace Hierarchy

### `/ask` with `agent_workflow`

`POST /ask` transport span when FastAPI instrumentation is enabled

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

`POST /ask` transport span when FastAPI instrumentation is enabled

`ask_request`

- `legacy_rag`
- `retrieval`
- `prompt_rendering`
- `llm_generation`
- `response_serialization`

### Evaluation Roots

- `evaluation.rag`
- `evaluation.agent`
- `evaluation.agent_e2e`
- `evaluation.ragas`
- `evaluation.deepeval`
- `evaluation.prompt_regression`
- `evaluation.factuality`
- `evaluation.baseline`

## Span Attributes

Stable semantic conventions are used where available:

- `http.route`
- `http.response.status_code`
- `service.name`
- `service.namespace`
- `service.version`
- `deployment.environment`

ExperimentOS-specific attributes stay namespaced:

- `experimentos.trace_id`
- `experimentos.request_id`
- `experimentos.workflow_id`
- `experimentos.execution_mode`
- `experimentos.workflow_mode`
- `experimentos.workflow_name`
- `experimentos.intent`
- `experimentos.prompt_id`
- `experimentos.prompt_version`
- `experimentos.experiment_id`

Phoenix-compatible OpenInference span kind is also attached:

- `openinference.span.kind`

GenAI semantic conventions are intentionally not treated as the primary contract in this issue
because the maturity and churn risk is higher than the current repository needs.

## Metrics

Implemented metrics:

- `ask_requests_total`
- `ask_failures_total`
- `workflow_executions_total`
- `agent_executions_total`
- `retrieval_requests_total`
- `empty_retrieval_total`
- `evaluation_runs_total`
- `ask_request_duration_ms`
- `workflow_duration_ms`
- `agent_duration_ms`
- `retrieval_duration_ms`
- `llm_duration_ms`
- `evaluation_duration_ms`
- `retrieved_result_count`
- `citation_count`

Metrics are derived from the existing ExperimentOS logical span tree rather than from scattered
OpenTelemetry calls in services.

## Cardinality Policy

Allowed metric attributes are deliberately narrow:

- `surface`
- `execution_mode`
- `workflow_mode`
- `environment`
- `status`
- `agent_name`
- `evaluation_type`
- `provider`

Disallowed metric attributes include:

- request ids
- trace ids
- prompt text
- questions
- arbitrary query text
- raw document ids
- arbitrary user input
- exception messages

## Propagation

- W3C Trace Context is accepted when FastAPI instrumentation is enabled
- a new trace is created when no valid incoming context exists
- ExperimentOS request ids and workflow ids remain separate internal correlation ids
- async request handling preserves parent-child relationships through the OpenTelemetry context
- baggage is not used for prompts, retrieved content, or other sensitive payloads

## FastAPI Strategy

- FastAPI auto-instrumentation is limited to transport-level HTTP spans
- `receive` and `send` child spans are excluded to avoid noise
- request and response bodies are not captured
- manual ExperimentOS spans still represent the business workflow
- duplicate `ask_request` spans are avoided

## Sampling

- OpenTelemetry export is disabled by default
- metrics remain enabled only when OpenTelemetry itself is enabled
- traces are sampled by the owned OpenTelemetry tracer provider
- LangSmith remains independent but carries the same ExperimentOS correlation metadata
- Phoenix shares the OpenTelemetry sampling path when both are enabled

## Exporters

Supported modes:

- `none`
- `console`
- `in_memory`
- `otlp_http`

Phoenix OTLP export can be enabled alongside generic OpenTelemetry export through the shared
provider.

Normal tests use in-memory readers and exporters only.

## Redaction And Privacy

Redacted or omitted by default:

- API keys
- authorization headers
- cookies
- DSNs and database URLs
- prompt bodies
- answer bodies
- retrieved chunk content
- unrestricted user text
- hidden reasoning

## CLI

Inspect status:

```powershell
uv run python -m packages.observability.cli status --provider opentelemetry
```

Validate configuration:

```powershell
uv run python -m packages.observability.cli validate --provider opentelemetry
```

Dry-run without network export:

```powershell
uv run python -m packages.observability.cli dry-run --provider opentelemetry
```

Emit a local smoke-test trace:

```powershell
uv run python -m packages.observability.cli smoke-test --provider opentelemetry
```

## Known Limitations

- no log signal export
- no production collector deployment
- no Grafana, Prometheus, Tempo, or Jaeger stack
- no database auto-instrumentation
- no queue or Redis instrumentation
- no cross-service tracing rollout beyond this application boundary
