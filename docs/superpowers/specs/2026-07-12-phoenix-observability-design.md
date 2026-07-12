# Phoenix Observability Integration Design

**Date:** 2026-07-12  
**Requested issue:** `#61`  
**Branch:** `feature/issue-61-phoenix-observability`

## Goal

Add optional Arize Phoenix tracing for `/ask`, `agent_workflow`, `legacy_rag`,
retrieval, prompt/model usage, decisions, and evaluation runs without replacing
ExperimentOS-owned traces, metrics, reports, or response contracts.

## Current Context

The repository already has an internal observability seam and authoritative local
execution artifacts:

- request routing and `/ask` entrypoints in `apps/api/main.py` and
  `apps/api/ask_service.py`
- a shared observability abstraction in `packages/observability`
- buffered root and child spans in `packages/observability/base.py`
- a no-op provider in `packages/observability/noop.py`
- an optional LangSmith provider in `packages/observability/langsmith.py`
- centralized redaction in `packages/observability/redaction.py`
- retrieval instrumentation in `packages/retrieval/service.py`
- prompt and model instrumentation in `packages/qa/question_answering_service.py`
- deterministic LangGraph workflow orchestration in `packages/agents/service.py`
- workflow observation extraction in `packages/agents/observability.py`
- evaluation entrypoints and reports in `packages/evals`

The Phoenix integration must extend these seams, not create a second tracing
architecture inside application services.

## Goals

- Keep Phoenix fully optional and disabled by default.
- Preserve ExperimentOS internal traces as the source of truth.
- Export only ExperimentOS-owned manual spans to Phoenix in this issue.
- Preserve the existing trace hierarchy for `agent_workflow`, `legacy_rag`, and
  evaluation runs.
- Preserve `agent_workflow` as the default `/ask` mode.
- Preserve `legacy_rag` compatibility.
- Preserve fake and mock provider compatibility.
- Reuse the internal observability abstraction already used by LangSmith.
- Support LangSmith and Phoenix together through the same logical spans.
- Keep tests deterministic and network-free by default.
- Redact sensitive content and omit unrestricted prompts, outputs, and retrieval
  content by default.

## Non-Goals

- No LangChain or LangGraph auto-instrumentation.
- No LangChain or LangGraph global instrumentor initialization.
- No direct Phoenix, OpenTelemetry, or OpenInference calls scattered through
  business services.
- No Phoenix datasets, experiments, annotations, or hosted evaluations.
- No generic application-wide OpenTelemetry rollout beyond what the Phoenix
  adapter minimally requires.
- No replacement of RAGAS, DeepEval, prompt regression, factuality evaluation,
  or local Markdown/JSON reports.
- No workflow behavior changes to improve observability.
- No chain-of-thought or hidden reasoning capture.

## Context7 Findings That Shape The Design

From current Phoenix docs:

- `phoenix.otel.register(...)` is the current helper for registering a tracer
  provider with Phoenix-oriented defaults.
- Phoenix registration supports `project_name`, `endpoint`, `protocol`,
  `headers`, and `batch` configuration.
- Phoenix guidance for existing tracing setups is to add Phoenix as an
  additional exporter instead of replacing an existing tracing system.

From current OpenInference docs:

- `TraceConfig` provides current masking controls for prompts, inputs, outputs,
  tools, and embedding vectors.
- OpenInference semantic span kinds include `AGENT`, `CHAIN`, `LLM`,
  `RETRIEVER`, `PROMPT`, `TOOL`, and `EVALUATOR`.
- Manual spans can be created with explicit attributes instead of relying on
  auto-instrumentation.

From current OpenTelemetry Python docs:

- `TracerProvider` should be configured with a `Resource` for stable service and
  environment metadata.
- `BatchSpanProcessor` is the normal export path, while explicit flush/shutdown
  hooks are available for diagnostics and tests.
- `TraceIdRatioBased` is the current ratio sampler pattern.
- in-memory exporters are appropriate for tests and smoke-test isolation.

These findings favor a manual adapter that translates ExperimentOS spans to
Phoenix-compatible OpenTelemetry spans at emit time, keeps provider imports
isolated, and avoids global instrumentor side effects.

## Architecture Decision

Keep ExperimentOS internal traces authoritative and extend the provider layer
into a multi-sink design:

- `NoOpObservabilityProvider`
- `LangSmithObservabilityProvider`
- `PhoenixObservabilityProvider`
- `CompositeObservabilityProvider`

Application services continue to depend only on the internal provider
abstraction. They create root and child spans exactly once. Providers translate
those `BufferedSpanRecord` trees to sink-specific exports after the logical
trace completes.

`CompositeObservabilityProvider` will:

- fan out the same logical trace tree to each enabled sink
- preserve the same ExperimentOS trace ID across sinks
- isolate provider failures so one sink cannot break another
- avoid double-emitting spans simply because multiple sinks are enabled

Phoenix must receive manually created ExperimentOS spans through the provider
layer. An optional auto-instrumentation mode may be added behind the provider
abstraction in a separate issue, but it is explicitly out of scope here.

## Configuration Design

Refactor observability settings from a single LangSmith-shaped dataclass into
provider-aware settings with safe defaults.

Top-level behavior:

- all external observability remains disabled by default
- provider creation succeeds without optional dependencies when providers are
  disabled
- provider validation happens explicitly when a provider is enabled
- credentials are never printed in CLI output or error messages

Phoenix-specific settings should include:

- `EXPERIMENTOS_PHOENIX_ENABLED=false`
- `EXPERIMENTOS_PHOENIX_ENDPOINT=`
- `EXPERIMENTOS_PHOENIX_API_KEY=`
- `EXPERIMENTOS_PHOENIX_PROJECT=experimentos-local`
- `EXPERIMENTOS_PHOENIX_ENVIRONMENT=development`
- `EXPERIMENTOS_PHOENIX_PROTOCOL=http/protobuf`
- `EXPERIMENTOS_PHOENIX_SAMPLING_RATE=0.0`
- `EXPERIMENTOS_PHOENIX_TRACE_INPUTS=false`
- `EXPERIMENTOS_PHOENIX_TRACE_OUTPUTS=false`
- `EXPERIMENTOS_PHOENIX_TRACE_RETRIEVAL_CONTENT=false`
- `EXPERIMENTOS_PHOENIX_TRACE_PROMPT_CONTENT=false`
- `EXPERIMENTOS_PHOENIX_REDACT_SENSITIVE_DATA=true`
- `EXPERIMENTOS_PHOENIX_STRICT=false`
- `EXPERIMENTOS_PHOENIX_ALWAYS_TRACE_ERRORS=true`
- `EXPERIMENTOS_PHOENIX_MAX_STRING_LENGTH=512`
- `EXPERIMENTOS_PHOENIX_MAX_COLLECTION_LENGTH=25`
- `EXPERIMENTOS_PHOENIX_MAX_METADATA_DEPTH=5`
- `EXPERIMENTOS_PHOENIX_MAX_RETRIEVAL_RECORDS=10`
- `EXPERIMENTOS_PHOENIX_TAGS=`
- `EXPERIMENTOS_PHOENIX_HEADERS=`

Validation requirements:

- local or self-hosted endpoints may omit an API key
- remote configurations that require an API key must fail explicitly if missing
- project and endpoint values must be validated when Phoenix is enabled
- unsupported protocol values must fail validation
- sampling rates must remain within `0.0` to `1.0`

## Dependency Strategy

Add Phoenix support to the existing optional `observability` dependency group
using the smallest correct set of packages.

Requirements:

- production imports succeed when Phoenix dependencies are absent and Phoenix is
  disabled
- missing optional dependencies become an error only when Phoenix is enabled
- Phoenix imports remain isolated to the Phoenix adapter and its tests
- tests do not require a live Phoenix server

The expected package set is:

- `arize-phoenix-otel`
- minimal OpenTelemetry exporter/sdk packages only if not already supplied
  transitively in a reliable way

Do not add LangChain or LangGraph instrumentors in this issue.

## Trace Hierarchy

Phoenix must receive the same logical hierarchy already emitted by the internal
observability system.

### `/ask` in `agent_workflow`

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

### `/ask` in `legacy_rag`

`ask_request`

- `legacy_rag`
- `retrieval`
- `prompt_rendering`
- `llm_generation`
- `response_serialization`

### Evaluations

- `evaluation.rag`
- `evaluation.agent`
- `evaluation.agent_e2e`
- `evaluation.ragas`
- `evaluation.deepeval`
- `evaluation.prompt_regression`
- `evaluation.factuality`
- `evaluation.baseline`

## Span Semantics

Map existing logical spans to OpenInference-compatible attributes only where the
semantics are correct:

- request and workflow roots: `CHAIN` or `AGENT`
- retrieval spans: `RETRIEVER`
- prompt rendering spans: `PROMPT`
- model generation spans: `LLM`
- evaluation roots: `EVALUATOR`
- deterministic business nodes such as `decision` and `risk_assessment`:
  `CHAIN`

Do not fabricate LLM spans for deterministic logic. Do not create provider-only
wrapper spans that change the hierarchy.

## Metadata Policy

Allowlisted metadata should include:

- ExperimentOS trace ID
- request ID
- workflow execution ID
- `/ask` mode
- endpoint name
- workflow name
- experiment ID
- `top_k`
- planner intent
- required agents
- decision status
- approval status
- summary status
- citation counts
- retrieval result counts and score summaries
- embedding provider and safe model labels
- prompt ID and prompt version
- rendered prompt length
- LLM provider/model labels
- token counts when available
- latency summaries
- evaluation case IDs, dataset IDs, and report targets
- environment and execution mode

Do not send by default:

- full prompt bodies
- full response bodies
- full retrieved chunks
- unrestricted document text
- embedding vectors
- database records
- authorization headers, cookies, API keys, or DSNs
- hidden reasoning or chain-of-thought

## Redaction And Payload Controls

Keep redaction centralized in `packages/observability/redaction.py` and extend
it so LangSmith and Phoenix share the same privacy rules.

Rules:

- recursively redact known secret keys
- suppress prompt, output, and retrieval content by default
- support opt-in content tracing with the same centralized redaction policy
- truncate long strings
- cap collection size
- cap metadata nesting depth
- cap the number of retrieval records serialized externally
- preserve safe counts, ids, statuses, and lengths

Phoenix-specific payload shaping should happen in the provider adapter without
duplicating redaction policy.

## Integration Points

### Provider Layer

Extend `packages/observability/factory.py` so it can resolve:

- neither sink enabled -> `NoOpObservabilityProvider`
- LangSmith only
- Phoenix only
- LangSmith and Phoenix together via `CompositeObservabilityProvider`

### API Boundary

Keep request-root instrumentation at the `/ask` boundary so both modes share:

- root trace correlation
- request IDs
- mode metadata
- response status
- provider-agnostic export behavior

### Agent Workflow

Keep `AgentWorkflowService.run(...)` as the owner of the workflow span and keep
node spans sourced from the final ExperimentOS workflow observation. Do not add
LangGraph global instrumentation.

### Legacy RAG

Keep `QuestionAnsweringService.answer_question(...)` as the owner of the
`legacy_rag` trace and retain manual spans for retrieval, prompt rendering, and
LLM generation.

### Retrieval

Keep `RetrievalService` instrumentation as the retrieval span owner and export
safe retrieval metadata only.

### Evaluations

Keep evaluation entrypoints responsible for evaluation roots so Phoenix export
follows the same evaluation naming and correlation already used internally.

## Failure Policy

Observability failures must be non-fatal by default.

Behavior:

- application requests continue
- internal traces and metrics remain authoritative
- LangSmith continues if Phoenix fails
- Phoenix continues if LangSmith fails
- provider failure counts are incremented per sink
- failure logs exclude secrets and full payloads

Strict mode may exist per provider for diagnostics but must remain opt-in.

## Diagnostics And CLI

Extend the observability CLI to support provider-aware commands:

- `status`
- `validate`
- `dry-run`
- `smoke-test`

Requirements:

- `status` and `dry-run` perform no network calls
- `validate` checks enabled provider configuration and dependency availability
- `smoke-test` requires explicit enablement
- credentials are never printed
- output should report enabled state, endpoint type, project, provider
  availability, redaction state, and sampling rate

## Testing Strategy

Add deterministic tests for:

- Phoenix disabled resolving to no-op or non-Phoenix providers as expected
- Phoenix optional dependency absent while disabled
- Phoenix optional dependency absent while enabled
- provider-specific validation errors
- Phoenix provider creation with local and remote endpoint settings
- composite fan-out with LangSmith and Phoenix together
- provider failure isolation
- request/workflow trace correlation IDs
- `agent_workflow` hierarchy export
- `legacy_rag` hierarchy export
- retrieval metadata export
- prompt provenance export
- LLM metadata export
- deterministic node metadata export
- decision and approval metadata export
- evaluation root tagging
- centralized redaction and payload limits
- sampling and always-trace-errors behavior
- flush and shutdown behavior
- CLI `status`, `validate`, `dry-run`, and `smoke-test`

Use fake exporters or in-memory exporters only. No live Phoenix server or cloud
service is required in the normal suite.

## Documentation Updates

Add:

- `docs/phase3/phoenix_observability.md`

Update:

- `.env.example`
- `docs/phase3/reliability_baseline.md`
- observability CLI help or README references where relevant

Documentation must state clearly:

- ExperimentOS internal traces are the source of truth
- LangSmith and Phoenix are optional external sinks
- Phoenix receives only manually created ExperimentOS spans in this issue
- LangChain or LangGraph auto-instrumentation is out of scope
- Phoenix is useful for local or remote trace inspection, not as required
  infrastructure

## Open Questions Resolved For This Issue

- Manual spans only: approved
- No LangChain or LangGraph global instrumentor initialization: approved
- Composite-provider fan-out from the same logical spans: approved
- Future optional auto-instrumentation seam allowed behind the provider layer:
  approved, but not implemented here
