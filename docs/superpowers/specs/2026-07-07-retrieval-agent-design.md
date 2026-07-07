# Retrieval Agent Design

**Date:** 2026-07-07
**Issue:** GitHub issue #25, "Retrieval Agent"

## Goal

Add a dedicated Retrieval Agent to the Phase 2 LangGraph workflow that reuses the existing Phase 1 `RetrievalService`, stores evidence and citations into shared state, records retrieval metrics and trace events, and fails safely without changing the existing `/ask` behavior.

## Constraints

- Keep `/ask` and `QuestionAnsweringService` unchanged.
- Reuse `packages/retrieval/service.py` instead of duplicating retrieval logic.
- Do not call OpenAI or any LLM from the Retrieval Agent.
- Keep routing simple: retrieval runs only when the planner includes `"retrieval"` in `required_agents`; otherwise it safely no-ops.
- Keep tests deterministic and compatible with fake embeddings or stubs.
- Do not implement any analysis, business-impact, risk, decision, or summary agent in this issue.

## Current Context

The current Phase 2 graph is:

`START -> planner -> END`

The current Phase 1 retrieval path is:

`QuestionAnsweringService -> RetrievalService`

The planner already writes these fields into shared state:

- `request`
- `intent`
- `required_agents`
- `planner_notes`
- `experiment_context`
- `metrics`
- `trace`

The shared state already reserves:

- `retrieved_chunks`
- `citations`
- `metrics`
- `errors`
- `trace`

That means the new work should extend the graph with a retrieval step rather than redesigning state or moving `/ask`.

## Chosen Approach

Create a dedicated `packages/agents/retrieval_agent.py` module that wraps the existing `RetrievalService` and converts its outputs into the Phase 2 shared-state contract.

Keep `packages/agents/nodes.py` thin by making the retrieval node responsible only for:

- checking whether retrieval is required
- calling the Retrieval Agent wrapper
- returning a partial state update

Update `packages/agents/workflow.py` so the graph becomes:

`START -> planner -> retrieval -> END`

This preserves the current LangGraph foundation while giving future downstream agents a stable evidence boundary.

## Module Boundaries

### `packages/agents/retrieval_agent.py`

This module becomes the Phase 2 retrieval boundary.

Responsibilities:

- read the relevant retrieval inputs from shared state
- decide whether to call `RetrievalService.search(...)` or `RetrievalService.search_by_experiment(...)`
- normalize `RetrievalResult` values into shared-state `retrieved_chunks`
- derive `citations` from retrieval results
- normalize `RetrievalMetrics` into `metrics["retrieval"]`
- emit retrieval trace entries
- translate exceptions into structured error payloads

This module must not:

- duplicate vector-search logic
- call `QuestionAnsweringService`
- call any LLM
- summarize or analyze retrieved content

### `packages/agents/nodes.py`

Add a retrieval node function that delegates to the dedicated Retrieval Agent module.

Responsibilities:

- inspect `required_agents`
- no-op if retrieval is not required
- invoke the retrieval wrapper when required
- return a graph-compatible partial update

### `packages/agents/workflow.py`

Extend the graph with a retrieval node after the planner.

Responsibilities:

- add the `retrieval` node
- connect `planner -> retrieval`
- connect `retrieval -> END`

### `packages/agents/service.py`

Keep the public workflow service shape unchanged unless a tiny compatibility adjustment is needed to support dependency injection for tests. No `/ask` integration is added here.

### `packages/agents/state.py`

Keep the shared contract stable. Only make changes if a small compatibility improvement is needed for retrieval-specific metrics or typed helper shapes.

## Retrieval Inputs

The Retrieval Agent reads only from shared state:

- `request.normalized_question`
- `required_agents`
- `experiment_context.experiment_ids`
- `experiment_context.filters`

### Routing Rule

For this issue:

- if `"retrieval"` is present in `required_agents`, execute retrieval
- otherwise, no-op and append a trace entry

No dynamic LangGraph routing is required beyond this node-level decision.

### Retrieval Service Call Strategy

Use the existing `RetrievalService` methods directly.

- if `experiment_context.experiment_ids` contains exactly one experiment ID, call `search_by_experiment(...)`
- otherwise, call `search(...)`

Pass `experiment_context.filters` as `metadata_filter` when the mapping is non-empty.

This keeps the Retrieval Agent compatible with the current planner output and leaves room for future experiment scoping without redesigning the interface.

## Shared State Output Mapping

### `retrieved_chunks`

Each `RetrievalResult` should be converted into the shared-state chunk shape:

- `document_id` from `result.document_id`
- `experiment_id` from `result.experiment_id`
- `content` from `result.chunk_text`
- `score` from `result.similarity`
- `metadata` from `result.metadata`

`RetrievedChunk.chunk_id` may be omitted for now because `RetrievalResult` does not currently expose a chunk identifier. A compatibility adjustment to Phase 1 retrieval should remain optional and minimal; do not add it unless implementation pressure proves it necessary.

### `citations`

Each retrieval result should also produce a citation record that preserves:

- `document_id`
- `experiment_id`
- `quote` as the retrieved chunk text
- `section` from `result.metadata["section"]` when present
- `metadata` copied from `result.metadata`

`Citation.chunk_id` may be omitted for the same reason as above.

### `metrics["retrieval"]`

Store retrieval metrics as a nested dictionary derived from `RetrievalMetrics`:

- `embedding_time_ms`
- `vector_search_time_ms`
- `retrieved_chunks`
- `average_similarity`

If `RetrievalService.last_metrics` is unexpectedly `None`, store a zeroed fallback payload with the observed retrieved chunk count so the state remains complete and deterministic.

### `trace`

Append trace entries for retrieval execution:

- `started`
- `skipped`
- `completed`
- `failed`

Each trace entry should identify the `retrieval` node and include small, useful details such as:

- whether retrieval was required
- selected experiment scope
- retrieved chunk count
- error code on failure

## Error Handling

The Retrieval Agent must fail safely.

### No-op behavior

If retrieval is not required:

- do not call the retrieval service
- do not append an error
- append a `skipped` trace entry
- leave retrieval outputs unchanged

### Failure behavior

If retrieval raises an exception:

- catch the exception inside the retrieval node or dedicated Retrieval Agent wrapper
- append a structured error record with:
  - `code`
  - `message`
  - `node`
  - optional `details`
- append a `failed` trace entry
- preserve existing state written by the planner
- leave `retrieved_chunks` and `citations` unchanged unless partial output handling is explicitly needed

The workflow should not crash for normal retrieval failures that can be represented as structured state.

## Testing Strategy

Tests should stay deterministic and focus on the agent boundary.

### New unit coverage

Add tests covering:

1. retrieval required and successful
2. retrieval not required and safely skipped
3. retrieval error handling
4. citations stored in state
5. retrieval metrics stored in state
6. trace entries appended

Use stubs or fake retrieval wrappers for graph-level tests rather than the database for the default path.

### Compatibility coverage

Existing tests should continue to protect:

- shared state behavior
- planner behavior
- workflow invocation
- retrieval service behavior
- question-answering behavior
- `/ask` behavior indirectly through unchanged Phase 1 code

### Optional integration-style coverage

If implementation remains small and clear, add one integration-style test around the Retrieval Agent boundary with a fake retrieval service or lightweight stub to prove `RetrievalResult` to shared-state conversion. Database-backed tests are not required for the core acceptance criteria.

## Expected File Changes

Create:

- `packages/agents/retrieval_agent.py`

Modify:

- `packages/agents/nodes.py`
- `packages/agents/workflow.py`
- `packages/agents/service.py` only if small testability support is needed
- `packages/agents/state.py` only if a minor compatibility improvement is required
- `tests/test_agent_nodes.py`
- `tests/test_agent_workflow.py`
- add a dedicated retrieval-agent test module if that keeps tests cleaner

Do not modify:

- `packages/qa/question_answering_service.py`
- FastAPI `/ask` behavior

## Non-Goals

- no Experiment Analysis Agent
- no Business Impact Agent
- no Decision Agent
- no executive summary generation
- no tool calling
- no human approval
- no document summarization
- no replacement of `QuestionAnsweringService`
- no retrieval algorithm rewrite
- no CLI addition unless absolutely necessary

## Acceptance Mapping

1. A dedicated Retrieval Agent module exists.
2. The LangGraph workflow includes a retrieval step after planner.
3. Retrieval runs only when required by planner, otherwise it safely no-ops.
4. Retrieved results are converted into shared state.
5. Citations are preserved in shared state.
6. Retrieval metrics are recorded in shared state.
7. Errors are captured without crashing the whole workflow where appropriate.
8. `/ask` behavior remains unchanged.
9. Existing tests continue to pass.
10. New tests cover success, no-op, failure, citations, metrics, and trace behavior.

## Follow-Up For Issue #15

Issue #15 should build the next downstream agent layer on top of retrieval output rather than revisiting retrieval orchestration.

The next issue should:

- consume `retrieved_chunks`, `citations`, and `metrics["retrieval"]` from shared state
- add a dedicated analysis-oriented node after retrieval
- keep planner and retrieval boundaries stable
- continue leaving `/ask` untouched until the full Phase 2 path is intentionally integrated

The main design rule for Issue #15 is to treat retrieval as the evidence-producing boundary and build downstream reasoning on top of that evidence rather than mixing retrieval and analysis responsibilities together.
