# /ask Agent Workflow Integration Design

**Date:** 2026-07-09  
**Requested issue:** `#34`  
**Tracking issue used:** `#48` (`#34` is already occupied by a closed pull request)  
**Branch:** `feature/issue-48-agent-workflow-integration-ask`

## Goal

Integrate the Phase 2 LangGraph `AgentWorkflowService` into the public `POST /ask` API and make it the default runtime path, while preserving the existing request contract and keeping the legacy RAG implementation available as a configuration fallback.

## Current Context

The current public `/ask` flow is:

`POST /ask -> QuestionAnsweringService -> RetrievalService -> grounded prompt builder -> LLM client`

The current internal Phase 2 flow is:

`AgentWorkflowService -> LangGraph workflow -> planner -> retrieval -> experiment_analysis -> business_impact -> risk_assessment -> decision -> human_approval -> executive_summary`

Today these two paths are separate. `/ask` still exposes the Phase 1 QA response contract, while the Phase 2 workflow is available only as an internal service.

## Product Direction

`/ask` should now represent the main Phase 2 direction of the project.

Chosen mode policy:

- default `/ask` mode: `agent_workflow`
- fallback mode: `legacy_rag`
- switching mode should happen through configuration, not a second public endpoint

`QuestionAnsweringService` must remain in the repository and remain runnable through configuration.

## Goals

- Keep the current `POST /ask` request body compatible.
- Default `/ask` to the agent workflow.
- Preserve backward-compatible response fields where practical.
- Add optional agent-oriented response fields that expose workflow output cleanly.
- Keep the legacy QA path available through configuration.
- Update tests and docs so the default public behavior is explicit.

## Non-Goals

- No streaming
- No authentication
- No persistent conversation memory
- No frontend work
- No deployment work
- No OpenAI calls in tests
- No deletion of Phase 1 evaluation or `QuestionAnsweringService`
- No API versioning unless strictly required

## Public API Contract

### Request

Keep the existing request schema unchanged:

- `question: str`
- `experiment_id: str`
- `top_k: int = 5`

This preserves current clients and preserves the experiment-scoped semantics already documented for `/ask`.

### Response

Replace the current QA-only response model with a backward-compatible superset.

Keep existing fields:

- `answer`
- `citations`
- `retrieved_chunks`
- `retrieval_metrics`
- `llm_metrics`

Add optional agent fields:

- `intent`
- `required_agents`
- `decision`
- `executive_summary`
- `agent_trace`
- `agent_metrics`
- `approval_status`

### Response Semantics

In `agent_workflow` mode:

- `answer` is populated from `executive_summary.summary` first
- if executive summary text is unavailable, fall back to `decision.rationale`
- if both are unavailable, return a conservative best-effort fallback answer
- `citations` come from shared workflow state
- `retrieved_chunks` are mapped from workflow retrieval state into the existing API-compatible chunk shape where possible
- `retrieval_metrics` come from workflow metrics when available
- `llm_metrics` remain present for compatibility, but this path should return a deterministic placeholder or null-equivalent values because the current workflow is not LLM-backed
- new agent fields expose structured workflow outputs directly

In `legacy_rag` mode:

- preserve existing behavior fully
- keep the new agent fields present as `null`, empty lists, or empty dictionaries as appropriate

## Configuration Design

Add a new runtime setting:

- `ASK_MODE`

Supported values:

- `agent_workflow`
- `legacy_rag`

Default value:

- `agent_workflow`

Behavior:

- invalid values should fall back to `agent_workflow` or fail fast during configuration parsing; implementation should choose the stricter behavior only if it does not complicate tests or startup unnecessarily
- documentation must explicitly show how to switch back:
  - `ASK_MODE=legacy_rag`

## API Layer Design

### Routing Strategy

Keep a single `POST /ask` route.

Introduce a higher-level API service abstraction for the route, for example an `AskService` protocol or equivalent dependency, that returns the new superset response model. The route should no longer depend directly on `QuestionAnsweringService`.

The route becomes:

`POST /ask -> config-selected AskService -> agent workflow or legacy QA -> unified API response`

### Service Selection

Selection happens inside the dependency wiring:

- `agent_workflow` -> API-facing adapter around `AgentWorkflowService`
- `legacy_rag` -> adapter around the existing `QuestionAnsweringService`

This keeps mode handling out of the route body and avoids duplicating HTTP exception mapping.

## Agent Workflow Integration Design

### API Adapter Layer

Do not reshape the core agent modules to match the API contract directly. Add a small API adapter layer that:

- translates `AskRequest` into workflow input
- injects `experiment_id`
- injects `top_k`
- invokes the workflow service
- maps `AgentState` into the API response model

This isolates public API compatibility logic from the internal agent package.

### Workflow Service Inputs

Extend `AgentWorkflowService.run(...)` to accept optional runtime request context needed by `/ask`, such as:

- `question`
- `experiment_id`
- `top_k`
- optional human approval input for future compatibility

This is the cleanest place to preserve the current `/ask` semantics because the workflow can then receive experiment scope directly instead of inferring it only from planner hints.

### Shared State Seeding

When `/ask` provides an `experiment_id`, seed shared state so retrieval runs experiment-scoped search:

- add the API-supplied experiment identifier to `experiment_context.experiment_ids`
- preserve planner-produced experiment filters and hints
- carry `top_k` into workflow execution through shared state or the retrieval agent boundary

This ensures Phase 2 `/ask` remains compatible with the documented contract that the request targets a single ingested experiment.

### Downstream Agent Behavior

Planner behavior remains intact:

- planner still selects `intent`
- planner still selects `required_agents`

Retrieval behavior changes only in how it receives explicit scope:

- if `experiment_context.experiment_ids` contains one experiment, retrieval should prefer `search_by_experiment`
- otherwise retrieval may continue using the broader search path

Other downstream agents should continue consuming shared state as they do today.

## Legacy Compatibility Design

### Preserve Existing Request Contract

No public request field changes are needed for this issue.

### Preserve Existing Response Fields

Existing response fields should remain available even in agent mode. If an exact Phase 1 equivalent is not available:

- prefer empty lists over removing list fields
- prefer `null` or placeholder-compatible objects over removing object fields
- do not silently drop existing top-level fields from the response schema

### Keep Legacy QA Path

The current `QuestionAnsweringService` path should remain available and testable.

Implementation should preserve:

- existing QA service implementation
- existing QA service dependency factory
- existing legacy behavior under `ASK_MODE=legacy_rag`

## Error Handling Design

### HTTP Statuses

Preserve the current external behavior where practical:

- `422` for request validation failures
- `404` for unknown experiment
- `502` for execution failures

### Workflow Error Policy

Do not convert every internal agent-state error into a hard HTTP failure.

If the workflow completes and can still produce a coherent response:

- return `200`
- include best available `answer`
- include `agent_trace`
- include `agent_metrics`
- include normalized citations

Only return `502` when the route cannot produce a coherent API response at all, such as:

- service-level execution exception
- unrecoverable adapter failure
- response mapping failure that leaves no safe fallback

This preserves graceful degradation and matches the requirement for graceful error behavior.

### Unknown Experiment Handling

If `/ask` supplies an explicit `experiment_id` and the workflow cannot resolve it, the API should still return `404` instead of silently degrading to a broad retrieval search.

That preserves the current documented contract for experiment-scoped `/ask`.

## Testing Strategy

### Keep Existing Coverage

Preserve current tests for:

- health endpoint
- QA service
- retrieval service
- existing agent workflow
- evaluation harnesses

Where API behavior now depends on configuration, legacy API tests should explicitly run in `legacy_rag` mode when they assert the old exact shape.

### New API Tests

Add tests for default `agent_workflow` mode covering:

- `/ask` agent workflow success
- `/ask` with a decision-support query
- `/ask` with an experiment-lookup query
- citations included
- agent metrics included
- agent trace included
- graceful partial-error behavior
- compatibility with the previous request schema
- config fallback to `legacy_rag`

### New Service-Level Tests

Add focused tests for:

- API adapter mapping from `AgentState` to response model
- fallback answer selection order
- experiment-id propagation into workflow input
- unknown-experiment translation to `404`
- deterministic placeholder `llm_metrics` behavior in agent mode

### Test Infrastructure

Use:

- injected stub workflow services
- existing deterministic agents
- no OpenAI calls
- no database dependency unless a test explicitly targets the runtime retrieval path

## Documentation Updates

Update:

- `docs/api.md`
  - describe `agent_workflow` as the default `/ask` mode
  - document the response superset and optional agent fields
  - document `ASK_MODE=legacy_rag`

- `README.md`
  - note that `/ask` now defaults to the Phase 2 agent workflow
  - document how to switch back to legacy RAG

- `docs/architecture.md`
  - update the public runtime path to reflect config-driven routing instead of QA-only routing

## Implementation Boundaries

Files likely to change:

- `apps/api/main.py`
- API response/request models in the API layer
- agent service input/state plumbing needed to accept experiment scope and top-k
- retrieval-agent wiring if top-k or experiment context propagation requires it
- `/ask` API tests
- docs for API and architecture

Files that should remain in place:

- `packages/qa/question_answering_service.py`
- legacy QA service logic
- existing Phase 1 evaluation path

## Acceptance Mapping

1. `/ask` executes the LangGraph workflow by default.
2. `legacy_rag` remains available through configuration.
3. Existing request behavior remains compatible.
4. Existing response fields remain available where practical.
5. Response includes useful answer text from workflow outputs.
6. Response includes citations where available.
7. Response includes structured trace and metrics.
8. Existing tests continue to pass or are intentionally updated.
9. New tests cover workflow success, decision support, experiment lookup, citations, metrics, trace, graceful errors, and request compatibility.
10. API documentation is updated.
11. README or equivalent docs mention the default workflow mode and fallback switch.
12. `QuestionAnsweringService` is retained.

## Recommended Follow-Up For Issue #35

Issue `#35` should validate the integrated `/ask` behavior end-to-end rather than building new agent features.

It should focus on:

- response-contract stability for real consumers
- experiment-scoped retrieval correctness under agent mode
- whether placeholder `llm_metrics` should remain, become nullable, or evolve into a richer runtime-metrics contract
- whether human approval input should be surfaced through API request extensions in a later compatible change
- whether `agent_trace` and `agent_metrics` need redaction, summarization, or a debug-mode gate before wider use
