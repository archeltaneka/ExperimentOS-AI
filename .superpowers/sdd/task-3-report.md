# Task 3 Report: Route Business Impact Through The Tools Layer

## Status

Completed.

## What Changed

- Updated `packages/agents/business_impact_agent.py` so business-impact lift calculations run through the deterministic tool layer via `execute_tool`.
- Appended tool execution records to the agent update as `tool_calls`.
- Preserved existing business-impact output behavior, including the zero-baseline limitation and `relative_lift=None`.
- Added integration tests in `tests/test_business_impact_agent.py` covering normal lift tool-call recording and zero-baseline relative-lift tool output recording.

## TDD Record

1. Added failing tests:
   - `test_business_impact_agent_records_lift_tool_calls`
   - `test_business_impact_agent_records_zero_baseline_relative_lift_tool_result`
2. Ran `uv run pytest tests\test_business_impact_agent.py -v`
   - Observed expected failures: `KeyError: 'tool_calls'`
3. Implemented the minimal production change to route lift calculations through tools and return `tool_calls`.
4. Re-ran the focused test file and confirmed all tests passed.

## Verification

- `uv run pytest tests\test_business_impact_agent.py -v`
- `uv run ruff check packages\agents\business_impact_agent.py tests\test_business_impact_agent.py`

## Self-Review

- Scope stayed within the allowed files for implementation and tests.
- No changes were made to `POST /ask`, `QuestionAnsweringService`, or model-driven tool calling.
- The implementation reuses the existing deterministic tools package rather than re-implementing lift math.
- Zero-baseline behavior remains intact while now recording the relative-lift tool call.
- If a tool execution returns `output=None`, the workflow continues without crashing and leaves the derived lift unset.

## Concerns

- None.
