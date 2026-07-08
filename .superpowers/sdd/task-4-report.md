# Task 4 Report

## Outcome

Implemented Task 4 by routing risk scoring, evidence validation, and decision confidence
through the deterministic tools layer while preserving the existing agent-facing behavior.

## Changes Made

- Added a regression test for `RiskAssessmentAgent` to verify it records a
  `score_experiment_risk` tool call.
- Added regression tests for `DecisionAgent` to verify it records
  `validate_required_evidence` and `score_decision_confidence` tool calls and uses
  evidence validation to block incomplete states.
- Updated `packages/agents/risk_assessment_agent.py` to:
  - execute `score_experiment_risk` through `execute_tool`
  - append the resulting tool-call record to the state update
  - preserve conservative fallback scoring if the tool returns `output=None`
- Updated `packages/agents/decision_agent.py` to:
  - execute `validate_required_evidence` through `execute_tool`
  - execute `score_decision_confidence` through `execute_tool` on synthesized decision paths
  - append tool-call records to the state update
  - preserve conservative fallback confidence of `"low"` if confidence scoring returns
    `output=None`
  - use validation output to surface incomplete evidence as `needs_more_data`

## TDD Notes

1. Added the new task-specific tests first.
2. Ran:

   ```powershell
   uv run pytest tests/test_risk_assessment_agent.py tests/test_decision_agent.py -v
   ```

   Result: failed as expected because `tool_calls` were not present on the updates.

3. Implemented the agent changes.
4. Re-ran the same focused tests and fixed one regression in the rollback path.

## Verification

Ran:

```powershell
uv run pytest tests/test_risk_assessment_agent.py tests/test_decision_agent.py -v
uv run ruff check packages/agents/risk_assessment_agent.py packages/agents/decision_agent.py tests/test_risk_assessment_agent.py tests/test_decision_agent.py
```

Results:

- `14 passed` in the focused agent test set
- Ruff passed on the modified files

## Self-Review

- Scope stayed within the four owned files.
- `POST /ask` and `QuestionAnsweringService` were not touched.
- No model-driven tool calling, network-dependent behavior, plugin system, or LangGraph
  `ToolNode` was introduced.
- Existing public decision/risk outputs were kept stable aside from the intended addition of
  `tool_calls` and validation-driven blocking details.

## Commit

- `[Improvement] Route risk and decision logic through tool layer`

## Concerns

- None.
