# Human Approval Workflow Design

**Date:** 2026-07-08
**Issue:** GitHub issue #31, "Human Approval Workflow"

## Goal

Add a deterministic human approval checkpoint to the internal Phase 2 LangGraph workflow after the Decision Agent and before the Executive Summary Agent.

The workflow must support approval-required and approval-not-required decisions without adding a UI, API integration, persistence, tool calling, or LLM behavior. The existing `/ask` endpoint and `QuestionAnsweringService` must remain unchanged.

## Constraints

- Do not modify `POST /ask`.
- Do not change `QuestionAnsweringService`.
- Do not add UI, frontend, or real human interaction surfaces.
- Do not add LangGraph `interrupt()` behavior in this issue.
- Do not add checkpointers, approval persistence, or authentication.
- Do not add tool calling or new LLM calls.
- Keep the implementation deterministic and testable.
- Keep the graph input schema as `question` only.

## Current Context

The current internal Phase 2 workflow is:

`START -> planner -> retrieval -> experiment_analysis -> business_impact -> risk_assessment -> decision -> executive_summary -> END`

The current shared state already contains a `human_approval` section, but it is only a placeholder and is not part of the executed graph. The current public runtime path remains separate:

`FastAPI /ask -> QuestionAnsweringService -> RetrievalService -> grounded prompt builder -> LLM client`

This issue extends only the internal Phase 2 workflow.

## LangGraph Decision

LangGraph documents human-in-the-loop support through `interrupt()` plus resume via `Command(resume=...)`. That pattern requires a checkpointer and a configured thread identifier so the graph can pause and later resume.

This issue should not use `interrupt()` yet.

Reason:

- the requested behavior is deterministic and test-oriented
- there is no UI or API surface yet to collect or resume human approval
- the issue explicitly excludes persistence and external integration

For this issue, human approval should be represented as ordinary shared state processed by a dedicated node. This keeps the implementation simple now and leaves a clean migration path to real LangGraph interrupt/resume behavior later.

## Target Workflow

The new graph becomes:

`START -> planner -> retrieval -> experiment_analysis -> business_impact -> risk_assessment -> decision -> human_approval -> executive_summary -> END`

The `human_approval` node must run after `decision` so it can read the decision recommendation and `approval_required` flag. It must run before `executive_summary` so the summary can reflect whether the recommendation was approved, rejected, pending, revision requested, or skipped.

## State Design

### Raw Input

Add a raw optional state field:

- `human_approval_input`

This field represents untrusted caller-provided data. It must not be treated as canonical state.

Suggested structure:

- `status`
- `feedback`
- `actor`
- `timestamp`

Every field is optional and should be treated as raw external input until normalized.

### Canonical Approval Record

Keep `human_approval` as the canonical normalized approval record and the single source of truth after the node runs.

Canonical fields:

- `status`
- `required`
- `feedback`
- `actor`
- `timestamp`

### Status Values

Canonical approval status must support:

- `not_requested`
- `skipped`
- `pending`
- `approved`
- `rejected`
- `revision_requested`

`not_requested` remains the initializer default before the workflow reaches the approval step.

## Normalization Rules

The Human Approval node reads `decision` and `human_approval_input`, validates the input, then writes normalized values to `human_approval`.

Rules:

1. If the decision is missing or malformed enough that `approval_required` cannot be read safely:
   - append a structured error such as `human_approval_missing_decision`
   - set canonical approval to a safe non-success state
   - use:
     - `status = "not_requested"`
     - `required = False`
     - `feedback = ""`
     - `actor = None`
     - `timestamp = None`

2. If `decision.approval_required` is `False`:
   - ignore approval input for canonical state
   - set:
     - `status = "skipped"`
     - `required = False`
   - preserve empty canonical feedback/actor/timestamp defaults

3. If `decision.approval_required` is `True` and no approval input is present:
   - set:
     - `status = "pending"`
     - `required = True`

4. If `decision.approval_required` is `True` and approval input is present with a valid status:
   - valid input statuses are:
     - `approved`
     - `rejected`
     - `revision_requested`
   - normalize optional `feedback`, `actor`, and `timestamp`
   - write the normalized result into `human_approval`

5. If approval input is present but invalid:
   - append a structured error such as `human_approval_invalid_input`
   - if approval is required, fall back to:
     - `status = "pending"`
     - `required = True`
   - if approval is not required, fall back to:
     - `status = "skipped"`
     - `required = False`

## Validation Behavior

Validation should remain deterministic and light.

Required normalization rules:

- `status` must be converted to lowercase string form before matching
- unknown statuses are invalid
- `feedback` should normalize to a string, defaulting to `""`
- `actor` should normalize to a string or `None`
- `timestamp` should normalize to a string or `None`

The node should never let raw input mutate the canonical `human_approval` record directly.

## Human Approval Module

Add a dedicated approval module:

- `packages/agents/human_approval_agent.py`

This module should own:

- the deterministic approval logic
- raw input normalization
- canonical record construction
- approval metrics payload creation

This satisfies the issue requirement that the Human Approval node exists as a dedicated module/function/class.

## Node And Workflow Integration

`packages/agents/nodes.py` should gain:

- `HumanApprovalAgentLike`
- `human_approval_node(...)`

The node should follow the same pattern as other nodes:

- skip only when `human_approval` is not in `required_agents`
- merge metrics into existing state metrics
- return partial updates

`packages/agents/workflow.py` should:

- inject a `HumanApprovalAgent`
- add the `human_approval` node
- connect `decision -> human_approval -> executive_summary`

`packages/agents/service.py` should allow dependency injection for the new approval agent just like the existing agent services.

## Planner And Required Agents

Decision-support and executive-summary flows should include the approval node in `required_agents` after `decision` and before `executive_summary`.

This affects planner outputs for any intent that currently includes both `decision` and `executive_summary`.

The node itself still decides whether approval is skipped or pending based on `decision.approval_required`.

## Metrics And Trace

The approval node must append trace entries and metrics in the same style as the other agents.

Trace should include:

- `started`
- `completed`

Completed trace details should include at minimum:

- normalized approval status
- whether approval was required
- whether raw approval input was present

Metrics should include at minimum:

- `status`
- `latency_ms`
- `approval_required`
- `input_present`
- `has_feedback`
- `error_count`

## Error Handling

The node should handle invalid or incomplete data safely and deterministically.

Expected structured errors:

- missing decision state
- invalid approval input status
- invalid approval input type where normalization cannot safely continue

The node should not raise in normal invalid-input cases. It should record errors in shared state and produce a safe canonical approval result.

## Executive Summary Behavior

The Executive Summary Agent should continue to summarize the decision recommendation, but it must also reflect approval state where appropriate.

Expected behavior:

- `skipped`
  - recommendation remains based on the decision
  - summary may note that approval was not required

- `pending`
  - summary should indicate the recommendation is awaiting human approval
  - recommendation text can remain the decision recommendation, but the headline and rationale should not imply final approval

- `approved`
  - summary can treat the recommendation as approved

- `rejected`
  - summary should clearly state that the recommendation was not approved
  - the decision recommendation should remain visible as the workflow’s recommendation, but the summary must distinguish recommendation from approval outcome

- `revision_requested`
  - summary should state that revision was requested
  - reviewer feedback should be reflected where appropriate

The executive summary should not generate a new recommendation. It should report the decision plus approval outcome.

## `/ask` Non-Impact

This issue must not modify:

- `apps/api/main.py`
- `packages/qa/question_answering_service.py`
- `/ask` request or response models
- existing QA retrieval and LLM behavior

Phase 1 and Phase 2 remain separate.

## Testing Strategy

Add focused tests for approval behavior and update existing workflow tests.

Required new or updated coverage:

1. state defaults include raw and canonical approval fields
2. approval skipped when decision does not require approval
3. approval pending when decision requires approval and no input exists
4. approved decision when valid approval input is present
5. rejected decision when valid approval input is present
6. revision requested with reviewer feedback preserved
7. missing decision behavior records an error safely
8. trace entries are appended
9. metrics are updated
10. workflow order includes `human_approval` before `executive_summary`
11. executive summary reflects approval outcome
12. existing `/ask` tests still pass unchanged

Suggested test files:

- `tests/test_human_approval_agent.py`
- updates to `tests/test_agent_state.py`
- updates to `tests/test_agent_nodes.py`
- updates to `tests/test_agent_workflow.py`
- updates to `tests/test_executive_summary_agent.py`

## Non-Goals

This issue must not introduce:

- real LangGraph interrupt/resume behavior
- UI or frontend work
- FastAPI approval endpoints
- authentication or authorization
- persistent approval storage
- tool calling
- new LLM interactions
- replacement of `QuestionAnsweringService`

## Acceptance Mapping

1. A dedicated human approval module exists.
2. Workflow order becomes `decision -> human_approval -> executive_summary`.
3. Shared state supports raw approval input and canonical approval output.
4. Approval is skipped when not required.
5. Approval becomes pending when required and no approval input exists.
6. Approval records approved, rejected, or revision requested when valid input is provided.
7. Executive summary reflects approval status where appropriate.
8. Existing tests continue to pass.
9. New tests cover approval outcomes, missing decision behavior, trace, and metrics.
10. `/ask` remains unchanged.
11. No UI is added.
12. No API integration is added.
13. No tool calling is implemented.
14. No LLM calls are added.

## Follow-Up For Issue #31

After this issue lands, the next logical build-out should be real human-in-the-loop workflow integration:

- introduce LangGraph `interrupt()` plus resume semantics
- add a checkpointer and thread identity strategy
- define how approval requests are surfaced to a user or operator
- decide where approval events are persisted
- add validation and authorization around who can approve or reject
- decide whether rejected or revision-requested outcomes should route back to an earlier node rather than only annotating state
