# Tool Calling Layer Design

**Date:** 2026-07-08  
**Issue:** GitHub issue #32, "Tool Calling Layer"

## Goal

Add a deterministic internal tool-calling layer for the Phase 2 LangGraph workflow so agents can reuse typed calculations and validation logic through explicit contracts instead of embedding those operations directly in each agent.

This layer must remain internal, synchronous, deterministic, and fully testable. It must not add LLM tool calling, external APIs, LangGraph `ToolNode` orchestration, or changes to `/ask`.

## Constraints

- Do not modify `POST /ask`.
- Do not change `QuestionAnsweringService`.
- Do not add OpenAI function calling or any other model-driven tool calling.
- Do not add external API tools or network-dependent behavior.
- Do not add LangGraph `ToolNode` unless it is clearly necessary. It is not necessary for this issue.
- Keep the implementation deterministic and unit-test friendly.
- Do not introduce a generic plugin framework.
- Preserve current public API behavior.
- Follow the current Phase 2 deterministic-agent conventions for state, trace, metrics, and structured errors.

## Current Context

The current Phase 2 workflow is:

`START -> planner -> retrieval -> experiment_analysis -> business_impact -> risk_assessment -> decision -> human_approval -> executive_summary -> END`

Current agents are already deterministic and write structured artifacts into shared state, but reusable calculations still live as local helper logic inside agent modules. That creates three problems:

1. the same business or scoring logic can drift across agents
2. tool usage is not recorded consistently in shared state
3. typed reusable operations do not have a clean discovery surface

The shared state already contains a `tool_calls` append-only log, but it is still too generic and is not used by the business-impact, risk, or decision agents.

## LangGraph Decision

LangGraph supports model-driven tool usage and `ToolNode`, but that pattern is aimed at tool calls emitted by an LLM or message-driven agent loop.

This issue should not use `ToolNode`.

Reason:

- the requested tools are deterministic internal functions
- the current workflow is a fixed graph of typed state transforms, not a tool-selection loop
- adding `ToolNode` would introduce message-oriented orchestration that the current workflow does not need
- the acceptance criteria explicitly exclude LLM tool calling

For this issue, tools should be plain Python functions invoked directly by the existing agent modules through a small internal registry and execution helper.

## Target Design

### Package Structure

Add a focused tools package:

```text
packages/agents/tools/
    __init__.py
    registry.py
    schemas.py
    business.py
    risk.py
    decision.py
```

Responsibilities:

- `schemas.py`
  - typed request/response models for tool inputs and outputs
  - tool call summary shaping helpers where useful
- `registry.py`
  - a narrow registry of internal tools
  - lookup and execution helpers
- `business.py`
  - lift calculation tools
- `risk.py`
  - deterministic risk scoring tool
- `decision.py`
  - deterministic evidence validation and confidence scoring tools
- `__init__.py`
  - exports the stable internal API used by agents and tests

This should stay intentionally small. The goal is reuse and consistency, not a future-proof plugin system.

### Tool Set

The first version should include at least these tools:

- `calculate_absolute_lift`
- `calculate_relative_lift`
- `score_experiment_risk`
- `score_decision_confidence`
- `validate_required_evidence`

Each tool should:

- accept typed input
- return typed output
- be deterministic
- avoid mutating shared state directly
- avoid reading environment variables
- avoid network or model calls

## Typed Tool Contracts

Use small Pydantic models or typed dataclasses for tool inputs and outputs. Pydantic is slightly preferred here because the shared state already uses Pydantic validation and it gives predictable validation errors for bad inputs.

Representative contract shapes:

- `AbsoluteLiftInput`
  - `baseline_value: float`
  - `treatment_value: float`
- `AbsoluteLiftOutput`
  - `absolute_lift: float`

- `RelativeLiftInput`
  - `baseline_value: float`
  - `treatment_value: float | None = None`
  - `absolute_lift: float | None = None`
- `RelativeLiftOutput`
  - `relative_lift: float | None`
  - `status: Literal["computed", "undefined_zero_baseline"]`

- `RiskScoringInput`
  - `risk_factors: list[RiskFactorLike]`
- `RiskScoringOutput`
  - `risk_score: int`
  - `overall_risk_level: Literal["low", "medium", "high"]`

- `EvidenceValidationInput`
  - booleans and counts required by decision rules, such as:
    - `has_experiment_analysis`
    - `has_business_impact`
    - `has_risk_assessment`
    - `has_statistical_significance`
    - `citation_count`
- `EvidenceValidationOutput`
  - `is_valid: bool`
  - `missing_requirements: list[str]`

- `DecisionConfidenceInput`
  - `analysis_confidence`
  - `business_confidence`
  - `risk_confidence`
  - `overall_risk_level`
  - `has_statistical_support`
  - `has_citations`
- `DecisionConfidenceOutput`
  - `confidence: Literal["high", "medium", "low", "unknown"]`

The contracts should be simple enough that the tests can assert exact behavior without needing mocks.

## Registry Design

The registry should be simple and static.

Recommended structure:

- a `ToolSpec` dataclass with:
  - `name`
  - `input_model`
  - `output_model`
  - `handler`
- a module-level dictionary keyed by tool name
- helpers:
  - `register_tool(spec: ToolSpec) -> None`
  - `get_tool(name: str) -> ToolSpec`
  - `list_tools() -> list[str]`

Do not implement dynamic loading, entry points, plugin discovery, or user-defined tool registration. Registration can happen at import time inside the package.

The main value of the registry is:

- a single lookup path for tests and agents
- consistent validation
- consistent execution logging

## Execution And State Recording

Add a small execution helper in `registry.py` or a closely related helper in the same package.

Responsibilities:

1. resolve a tool by name
2. validate raw input against the tool input model
3. execute the deterministic handler
4. validate the output against the output model
5. measure latency
6. produce:
   - typed output for the caller
   - a structured `ToolCallRecord`

The helper should not mutate graph state. Agents remain responsible for appending returned records into `AgentStateUpdate`.

### Tool Call Record

Expand the shared `ToolCallRecord` contract in `packages/agents/state.py` so it captures the information required by this issue while remaining append-only and JSON-serializable.

Recommended fields:

- `tool_name`
- `status`
- `input_summary`
- `output_summary`
- `latency_ms`
- `error`
- `node`
- `at`

Optional compatibility fields can remain if useful, but agents should prefer compact summaries rather than storing large raw payloads.

Recommended behavior:

- `input_summary`
  - compact, human-readable, deterministic dictionary such as:
    - `{"baseline_value": 0.676, "treatment_value": 0.731}`
- `output_summary`
  - compact dictionary such as:
    - `{"absolute_lift": 0.055}`
    - `{"relative_lift": null, "status": "undefined_zero_baseline"}`
- `error`
  - structured string describing the validation or execution failure

### Failure Semantics

Tool failures should always be recorded in `tool_calls`.

Whether they also become workflow `errors` depends on impact:

- benign or expected conditions:
  - zero baseline in relative lift
  - evidence missing for validation
  - conservative scoring fallback
  - these should usually not append a workflow error
- actual tool execution or validation failures:
  - malformed inputs
  - missing tool registration
  - unexpected exceptions
  - these should usually append a structured workflow error when the agent cannot proceed normally

The graph should not crash for normal business edge cases.

## Agent Integration

### Business Impact Agent

Refactor `BusinessImpactAgent` to use the tools layer for:

- `calculate_absolute_lift`
- `calculate_relative_lift`

Expected behavior:

- compute absolute lift through the tool whenever baseline and treatment exist
- compute relative lift through the tool whenever possible
- if the relative-lift tool returns `undefined_zero_baseline`, preserve current conservative behavior:
  - `relative_lift = None`
  - add a limitation about zero baseline
- append successful or failed tool call records to `tool_calls`

The rest of the agent remains responsible for:

- source evidence carry-through
- annualized impact parsing
- summary construction
- final `impact_status`

### Risk Assessment Agent

Refactor `RiskAssessmentAgent` to use the tools layer for:

- `score_experiment_risk`

Expected behavior:

- keep the current logic that constructs `risk_factors`
- move numeric score aggregation and overall-risk-level derivation into the tool
- append the tool call record to `tool_calls`

The risk agent still owns:

- factor generation
- assumptions and limitations
- mitigation actions
- partial versus insufficient assessment policy

### Decision Agent

Refactor `DecisionAgent` to use the tools layer for:

- `validate_required_evidence`
- `score_decision_confidence`

Expected behavior:

- evidence validation should replace the current ad hoc “insufficient data” gate where useful
- confidence scoring should replace the current inline confidence helper
- tool failure should produce conservative behavior:
  - missing evidence remains `needs_more_data` or `insufficient_data`
  - confidence should fall back to `low` or `unknown`

The decision agent still owns:

- recommendation policy
- rationale text
- blocking issues
- next actions
- approval requirement

## Shared State And Conventions

This issue should preserve the current shared-state design principles:

- agents return partial updates
- append-only logs are:
  - `trace`
  - `errors`
  - `tool_calls`
- all tool records remain JSON-serializable
- the workflow input schema remains `question` only

No graph routing changes are required for this issue.

No changes should be made to the public `/ask` path in:

- `apps/api/main.py`
- `packages/qa/question_answering_service.py`

## Testing Strategy

Add dedicated tests for the new tool layer and update at least one agent-level test to prove integration.

Required coverage:

1. absolute lift calculation
2. relative lift calculation
3. zero baseline handling
4. risk scoring tool
5. decision confidence scoring or evidence validation
6. registry lookup
7. tool call recording in state
8. tool error handling
9. one agent using a tool successfully
10. existing `/ask` tests still pass unchanged

Suggested test files:

- `tests/test_agent_tools.py`
- updates to `tests/test_agent_state.py`
- updates to `tests/test_business_impact_agent.py`
- updates to `tests/test_risk_assessment_agent.py`
- updates to `tests/test_decision_agent.py`
- updates to `tests/test_agent_workflow.py`

Testing should stay deterministic and not require the database for the new tool-layer unit tests.

## Non-Goals

This issue must not introduce:

- OpenAI function calling
- LangGraph `ToolNode`
- retrieval-tool wrappers for external invocation
- experiment repository tool adapters
- external services
- a CLI for tool execution
- causal inference or advanced statistical modeling
- changes to `QuestionAnsweringService`
- changes to `/ask`

## Acceptance Mapping

1. A dedicated tool layer exists in `packages/agents/tools/`.
2. Tools are registered or discoverable through a simple registry.
3. Tool inputs and outputs are typed and validated.
4. Business Impact Agent uses calculation tools.
5. Risk Assessment Agent or Decision Agent uses scoring or validation tools.
6. Shared state records tool calls.
7. Tool failures are captured as structured errors without crashing the workflow where appropriate.
8. Existing tests still pass.
9. New tests cover calculations, zero baseline, scoring or validation, registry lookup, state recording, error handling, and real agent usage.
10. `/ask` remains unchanged.
11. No LLM tool calling is added.
12. No external API tools are added.
13. No CLI is added.

## Follow-Up For Issue #33

Issue `#33` should build on this layer by widening internal tool coverage rather than changing the execution model.

Recommended next scope:

- add retrieval-oriented internal tools where explicit typed contracts help downstream agents
- add experiment-data tools that wrap repository reads only if an agent now needs them through a stable contract
- standardize reusable summary helpers for tool-call state recording
- decide whether some tool failures should become first-class observability metrics in shared state

Issue `#33` should still avoid LLM tool calling unless that issue explicitly changes the graph interaction model and requirements.
