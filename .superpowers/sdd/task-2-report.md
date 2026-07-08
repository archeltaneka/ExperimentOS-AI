# Task 2 Report: Human Approval Agent And Node

## Status

Completed.

## Scope Completed

- Added `packages/agents/human_approval_agent.py`.
- Added `HumanApprovalAgent.run(state)` with deterministic normalization of
  `human_approval_input` into canonical `human_approval`.
- Added `HumanApprovalAgentLike` to `packages/agents/nodes.py`.
- Added `human_approval_node(...)` to `packages/agents/nodes.py`.
- Added focused coverage in `tests/test_human_approval_agent.py`.
- Added node coverage in `tests/test_agent_nodes.py`.

## TDD Record

### Red

Added the approval-agent and node tests first:

- `tests/test_human_approval_agent.py`
- new human-approval node cases in `tests/test_agent_nodes.py`

Then ran:

```powershell
uv run pytest tests/test_human_approval_agent.py tests/test_agent_nodes.py -v
```

Observed expected failure during collection:

- `ModuleNotFoundError: No module named 'packages.agents.human_approval_agent'`

This confirmed the tests were failing for the intended missing implementation.

### Green

Implemented the minimal deterministic behavior:

- Missing or unreadable `decision.approval_required` returns canonical
  `human_approval` with `status="not_requested"` and records
  `human_approval_missing_decision`.
- `approval_required=False` returns `status="skipped"` and `required=False`.
- `approval_required=True` with missing or invalid input returns
  `status="pending"` and `required=True`.
- Valid normalized statuses are exactly:
  - `approved`
  - `rejected`
  - `revision_requested`
- The agent emits `started` and `completed` trace entries.
- The agent records deterministic metrics for status, latency, approval
  requirement, input presence, feedback presence, and error count.
- The node skips when `human_approval` is not required and delegates to the
  injected agent when it is required.
- The node merges returned metrics with existing state metrics, matching the
  established node pattern.

### Refactor

Kept refactoring minimal:

- Extracted `_build_human_approval(...)`.
- Extracted `_normalize_input(...)`.
- Extracted `_normalize_optional_string(...)`.

## Verification

Focused tests:

```powershell
uv run pytest tests/test_human_approval_agent.py tests/test_agent_nodes.py -v
```

Result:

- `24 passed`

Lint:

```powershell
uv run ruff check .
```

Result:

- `All checks passed!`

## Tests Added Or Updated

### `tests/test_human_approval_agent.py`

Covered:

- approval skipped when not required
- pending when required but no input provided
- approved normalization
- rejected normalization with feedback
- revision requested normalization with feedback
- missing decision error behavior
- trace and metrics behavior

### `tests/test_agent_nodes.py`

Covered:

- node skip behavior when `human_approval` is not in `required_agents`
- delegation to injected approval agent when required
- metrics merge behavior for approval node updates

## Self-Review

Checked the implementation against the task brief and constraints:

- Did not modify `POST /ask`.
- Did not change `QuestionAnsweringService`.
- Did not edit `workflow.py` or `service.py`.
- Did not add UI, frontend, interrupts, checkpointers, persistence, auth,
  tool calling, or new LLM calls.
- Kept the graph input schema unchanged as question-only.
- Kept implementation deterministic and testable.
- Limited code changes to the four owned files.

## Notes

- The approval agent intentionally only normalizes state and records status; it
  does not perform real human interaction or workflow orchestration. That
  remains deferred to Task 3.
- A transient Windows sandbox spawn issue occurred on one read-only Git
  inspection command after the commit, but it had no effect on the code,
  tests, or repository state.

## Commit

- `116067a` `[New Feature] Add deterministic human approval agent`

## Task 2 Focused Fix: Invalid Human Approval Input

### Additional Red-Green Cycle

Added focused failing tests first for the approved spec update:

- unknown human approval status should append `human_approval_invalid_input`
- malformed raw `human_approval_input` that is not a mapping should append
  `human_approval_invalid_input`

Red verification command:

```powershell
uv run pytest tests/test_human_approval_agent.py tests/test_agent_nodes.py -v
```

Observed expected failures:

- unknown status fell back to `pending` but returned no appended error
- malformed raw input raised `AttributeError` on `.get(...)`

### Fix Applied

Updated `packages/agents/human_approval_agent.py` so that:

- raw approval input is validated safely before field access
- non-mapping raw input appends a structured
  `human_approval_invalid_input` error with deterministic details
- present input with an unknown status appends the same structured error
- fallback behavior remains deterministic:
  - `approval_required=True` -> canonical status `pending`
  - `approval_required=False` -> canonical status `skipped`
- invalid-input errors are included in agent `errors` output and therefore in
  `error_count` metrics

### Tests Added

In `tests/test_human_approval_agent.py`:

- `test_human_approval_agent_appends_error_for_unknown_status`
- `test_human_approval_agent_appends_error_for_malformed_raw_input`

### Fresh Verification

Focused tests:

```powershell
uv run pytest tests/test_human_approval_agent.py tests/test_agent_nodes.py -v
```

Result:

- `26 passed`

Lint:

```powershell
uv run ruff check .
```

Result:

- `All checks passed!`
