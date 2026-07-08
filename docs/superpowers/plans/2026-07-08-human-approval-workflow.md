# Human Approval Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic human approval checkpoint after the decision agent and before the executive summary agent, using raw approval input normalized into canonical workflow state without changing `/ask`.

**Architecture:** Extend the shared LangGraph state with a raw `human_approval_input` field and an expanded canonical `human_approval` record, then add a dedicated `HumanApprovalAgent` plus a graph node between `decision` and `executive_summary`. Keep all approval behavior state-driven and deterministic, and update the executive summary to report approval outcomes without changing recommendation generation.

**Tech Stack:** Python 3.12, LangGraph `StateGraph`, Pydantic `TypeAdapter`, pytest, Ruff

## Global Constraints

- Do not modify `POST /ask`.
- Do not change `QuestionAnsweringService`.
- Do not add UI, frontend, or real human interaction surfaces.
- Do not add LangGraph `interrupt()` behavior in this issue.
- Do not add checkpointers, approval persistence, or authentication.
- Do not add tool calling or new LLM calls.
- Keep the implementation deterministic and testable.
- Keep the graph input schema as `question` only.

---

### Task 1: Extend Shared State And Planner Conventions

**Files:**
- Modify: `packages/agents/state.py`
- Modify: `packages/agents/planner.py`
- Modify: `tests/test_agent_state.py`
- Modify: `tests/test_agent_nodes.py`
- Modify: `tests/test_planner.py`

**Interfaces:**
- Consumes: existing `AgentState`, `AgentStateUpdate`, `RequiredAgent`, `create_initial_state(question: str) -> AgentState`
- Produces:
  - `HumanApprovalStatus = Literal["not_requested", "skipped", "pending", "approved", "rejected", "revision_requested"]`
  - `HumanApprovalInputRecord(TypedDict, total=False)`
  - `HumanApprovalRecord(TypedDict)` with `status: HumanApprovalStatus`, `required: bool`, `feedback: str`, `actor: str | None`, `timestamp: str | None`
  - planner-required agent lists that include `"human_approval"` whenever both `"decision"` and `"executive_summary"` are present

- [ ] **Step 1: Write the failing state and planner tests**

```python
def test_create_initial_state_sets_human_approval_defaults() -> None:
    state = create_initial_state("Should we roll out the payment recommendation experiment?")

    assert state["human_approval_input"] == {}
    assert state["human_approval"] == {
        "status": "not_requested",
        "required": False,
        "feedback": "",
        "actor": None,
        "timestamp": None,
    }
    assert state["run_metadata"]["state_version"] == 9


def test_plan_question_includes_human_approval_for_decision_support() -> None:
    plan = plan_question("Should we roll out the payment recommendation experiment?")

    assert plan.required_agents == [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "human_approval",
        "executive_summary",
    ]
```

- [ ] **Step 2: Run the narrow tests to verify they fail**

Run: `uv run pytest tests/test_agent_state.py tests/test_agent_nodes.py tests/test_planner.py -v`

Expected: FAIL because `human_approval_input` is missing, `human_approval` still uses the old shape, and planner outputs do not yet include `human_approval`.

- [ ] **Step 3: Implement the state and planner changes**

```python
HumanApprovalStatus = Literal[
    "not_requested",
    "skipped",
    "pending",
    "approved",
    "rejected",
    "revision_requested",
]


class HumanApprovalInputRecord(TypedDict, total=False):
    status: str
    feedback: object
    actor: object
    timestamp: object


class HumanApprovalRecord(TypedDict):
    status: HumanApprovalStatus
    required: bool
    feedback: str
    actor: str | None
    timestamp: str | None


class AgentState(TypedDict):
    ...
    human_approval_input: HumanApprovalInputRecord
    human_approval: HumanApprovalRecord
    ...


def create_initial_state(question: str) -> AgentState:
    ...
    "human_approval_input": {},
    "human_approval": {
        "status": "not_requested",
        "required": False,
        "feedback": "",
        "actor": None,
        "timestamp": None,
    },
    ...
    "run_metadata": {
        "run_id": str(uuid4()),
        "workflow": "phase2_shared_state",
        "state_version": 9,
    },
```

```python
_REQUIRED_AGENTS: dict[AgentIntent, list[RequiredAgent]] = {
    "decision_support": [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "human_approval",
        "executive_summary",
    ],
    "executive_summary": [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "human_approval",
        "executive_summary",
    ],
    ...
}
```

- [ ] **Step 4: Run the narrow tests to verify they pass**

Run: `uv run pytest tests/test_agent_state.py tests/test_agent_nodes.py tests/test_planner.py -v`

Expected: PASS with updated defaults and planner-required agent ordering.

- [ ] **Step 5: Commit**

```bash
git add packages/agents/state.py packages/agents/planner.py tests/test_agent_state.py tests/test_agent_nodes.py tests/test_planner.py
git commit -m "[Improvement] Extend agent state for human approval"
```

### Task 2: Add The Human Approval Agent And Node

**Files:**
- Create: `packages/agents/human_approval_agent.py`
- Modify: `packages/agents/nodes.py`
- Modify: `tests/test_agent_nodes.py`
- Create: `tests/test_human_approval_agent.py`

**Interfaces:**
- Consumes:
  - `state["decision"]`
  - `state["human_approval_input"]`
  - `state["human_approval"]`
  - `state["metrics"]`
  - `state["errors"]`
- Produces:
  - `class HumanApprovalAgent`
  - `def run(self, state: AgentState) -> AgentStateUpdate`
  - `class HumanApprovalAgentLike(Protocol)`
  - `def human_approval_node(state: AgentState, *, human_approval_agent: HumanApprovalAgentLike) -> AgentStateUpdate`

- [ ] **Step 1: Write the failing approval-agent and node tests**

```python
def test_human_approval_agent_skips_when_approval_not_required() -> None:
    state = build_human_approval_state()
    state["decision"]["approval_required"] = False

    update = HumanApprovalAgent().run(state)

    assert update["human_approval"]["status"] == "skipped"
    assert update["human_approval"]["required"] is False


def test_human_approval_agent_marks_pending_when_required_but_missing_input() -> None:
    state = build_human_approval_state()
    state["decision"]["approval_required"] = True
    state["human_approval_input"] = {}

    update = HumanApprovalAgent().run(state)

    assert update["human_approval"]["status"] == "pending"
    assert update["human_approval"]["required"] is True


def test_human_approval_agent_records_rejected_with_feedback() -> None:
    state = build_human_approval_state()
    state["decision"]["approval_required"] = True
    state["human_approval_input"] = {
        "status": "rejected",
        "feedback": "Do not proceed until JP telemetry is fixed.",
        "actor": "director@example.com",
        "timestamp": "2026-07-08T01:02:03Z",
    }

    update = HumanApprovalAgent().run(state)

    assert update["human_approval"]["status"] == "rejected"
    assert update["human_approval"]["feedback"] == (
        "Do not proceed until JP telemetry is fixed."
    )
```

```python
def test_human_approval_node_delegates_to_injected_agent_when_required() -> None:
    state = create_initial_state("Summarize for executives.")
    state["required_agents"] = [
        "retrieval",
        "experiment_analysis",
        "business_impact",
        "risk_assessment",
        "decision",
        "human_approval",
        "executive_summary",
    ]
    agent = RecordingHumanApprovalAgent()

    update = human_approval_node(state, human_approval_agent=agent)

    assert agent.calls == 1
    assert update["human_approval"]["status"] == "pending"
```

- [ ] **Step 2: Run the narrow tests to verify they fail**

Run: `uv run pytest tests/test_human_approval_agent.py tests/test_agent_nodes.py -v`

Expected: FAIL because the approval agent module and approval node do not exist yet.

- [ ] **Step 3: Implement the approval agent module**

```python
HUMAN_APPROVAL_NODE = "human_approval"
_VALID_APPROVAL_STATUSES = {"approved", "rejected", "revision_requested"}


@dataclass
class HumanApprovalAgent:
    def run(self, state: AgentState) -> AgentStateUpdate:
        started_at = perf_counter()
        trace = [create_trace_entry(node=HUMAN_APPROVAL_NODE, event="started")]
        approval, errors, details = _build_human_approval(state)
        return {
            "human_approval": approval,
            "errors": errors,
            "trace": [
                *trace,
                create_trace_entry(
                    node=HUMAN_APPROVAL_NODE,
                    event="completed",
                    details=details,
                ),
            ],
            "metrics": {
                **state["metrics"],
                "human_approval": {
                    "status": approval["status"],
                    "latency_ms": (perf_counter() - started_at) * 1000.0,
                    "approval_required": approval["required"],
                    "input_present": bool(state["human_approval_input"]),
                    "has_feedback": bool(approval["feedback"]),
                    "error_count": len(errors),
                },
            },
        }
```

```python
def _build_human_approval(
    state: AgentState,
) -> tuple[HumanApprovalRecord, list[ErrorRecord], dict[str, object]]:
    decision = state.get("decision")
    if not isinstance(decision, dict) or "approval_required" not in decision:
        return (
            {
                "status": "not_requested",
                "required": False,
                "feedback": "",
                "actor": None,
                "timestamp": None,
            },
            [
                create_error_entry(
                    code="human_approval_missing_decision",
                    message="Human approval could not read decision.approval_required.",
                    node=HUMAN_APPROVAL_NODE,
                )
            ],
            {
                "status": "not_requested",
                "approval_required": False,
                "input_present": bool(state["human_approval_input"]),
            },
        )
    ...
```

```python
def human_approval_node(
    state: AgentState,
    *,
    human_approval_agent: HumanApprovalAgentLike,
) -> AgentStateUpdate:
    required_agents: list[RequiredAgent] = state["required_agents"]
    if "human_approval" not in required_agents:
        return {
            "trace": [
                create_trace_entry(
                    node="human_approval",
                    event="skipped",
                    details={"reason": "not_required"},
                )
            ],
        }
    update = human_approval_agent.run(state)
    if "metrics" in update:
        update = {
            **update,
            "metrics": {
                **state["metrics"],
                **update["metrics"],
            },
        }
    return update
```

- [ ] **Step 4: Run the narrow tests to verify they pass**

Run: `uv run pytest tests/test_human_approval_agent.py tests/test_agent_nodes.py -v`

Expected: PASS with coverage for skipped, pending, approved, rejected, revision requested, missing decision, trace, and metrics behavior.

- [ ] **Step 5: Commit**

```bash
git add packages/agents/human_approval_agent.py packages/agents/nodes.py tests/test_human_approval_agent.py tests/test_agent_nodes.py
git commit -m "[New Feature] Add deterministic human approval agent"
```

### Task 3: Integrate Workflow And Executive Summary Behavior

**Files:**
- Modify: `packages/agents/workflow.py`
- Modify: `packages/agents/service.py`
- Modify: `packages/agents/executive_summary_agent.py`
- Modify: `packages/agents/__init__.py`
- Modify: `tests/test_agent_workflow.py`
- Modify: `tests/test_executive_summary_agent.py`

**Interfaces:**
- Consumes:
  - `HumanApprovalAgent`
  - `human_approval_node(...)`
  - `state["human_approval"]`
  - existing decision and executive summary structures
- Produces:
  - `build_agent_workflow(..., human_approval_agent: HumanApprovalAgentLike | None = None)`
  - `AgentWorkflowService(..., human_approval_agent: HumanApprovalAgentLike | None = None)`
  - executive summary text/headline/limitations updates that reflect approval state

- [ ] **Step 1: Write the failing workflow and executive summary tests**

```python
def test_build_agent_workflow_runs_human_approval_before_executive_summary() -> None:
    graph = build_agent_workflow(
        retrieval_agent=StubGraphRetrievalAgent(),
        experiment_analysis_agent=StubGraphExperimentAnalysisAgent(),
        business_impact_agent=StubGraphBusinessImpactAgent(),
        risk_assessment_agent=StubGraphRiskAssessmentAgent(),
        decision_agent=StubGraphDecisionAgent(),
        human_approval_agent=StubGraphHumanApprovalAgent(),
        executive_summary_agent=StubGraphExecutiveSummaryAgent(),
    )

    result = graph.invoke({"question": "Summarize the checkout UX experiment for executives."})

    assert [entry["node"] for entry in result["trace"]] == [
        "planner",
        "retrieval",
        "retrieval",
        "experiment_analysis",
        "experiment_analysis",
        "business_impact",
        "business_impact",
        "risk_assessment",
        "risk_assessment",
        "decision",
        "decision",
        "human_approval",
        "human_approval",
        "executive_summary",
        "executive_summary",
    ]
```

```python
def test_executive_summary_agent_reflects_rejected_approval() -> None:
    state = build_executive_summary_state()
    state["human_approval"] = {
        "status": "rejected",
        "required": True,
        "feedback": "Do not proceed until tracking is corrected.",
        "actor": "director@example.com",
        "timestamp": "2026-07-08T01:02:03Z",
    }

    update = ExecutiveSummaryAgent().run(state)

    assert "not approved" in update["executive_summary"]["headline"].lower()
    assert "tracking is corrected" in update["executive_summary"]["summary"].lower()
```

- [ ] **Step 2: Run the narrow tests to verify they fail**

Run: `uv run pytest tests/test_agent_workflow.py tests/test_executive_summary_agent.py -v`

Expected: FAIL because workflow injection and summary behavior do not yet include human approval.

- [ ] **Step 3: Implement workflow, service, and summary integration**

```python
def build_agent_workflow(
    *,
    retrieval_agent: RetrievalAgentLike | None = None,
    experiment_analysis_agent: ExperimentAnalysisAgentLike | None = None,
    business_impact_agent: BusinessImpactAgentLike | None = None,
    risk_assessment_agent: RiskAssessmentAgentLike | None = None,
    decision_agent: DecisionAgentLike | None = None,
    human_approval_agent: HumanApprovalAgentLike | None = None,
    executive_summary_agent: ExecutiveSummaryAgentLike | None = None,
):
    ...
    if human_approval_agent is None:
        human_approval_agent = HumanApprovalAgent()
    ...
    builder.add_node(
        "human_approval",
        partial(
            human_approval_node,
            human_approval_agent=human_approval_agent,
        ),
    )
    ...
    builder.add_edge("decision", "human_approval")
    builder.add_edge("human_approval", "executive_summary")
```

```python
class AgentWorkflowService:
    def __init__(
        self,
        retrieval_agent: RetrievalAgentLike | None = None,
        experiment_analysis_agent: ExperimentAnalysisAgentLike | None = None,
        business_impact_agent: BusinessImpactAgentLike | None = None,
        risk_assessment_agent: RiskAssessmentAgentLike | None = None,
        decision_agent: DecisionAgentLike | None = None,
        human_approval_agent: HumanApprovalAgentLike | None = None,
        executive_summary_agent: ExecutiveSummaryAgentLike | None = None,
    ) -> None:
        ...
```

```python
def _headline(
    *,
    summary_status: ExecutiveSummaryStatus,
    decision_status: str,
    recommendation: str,
    approval_status: str,
) -> str:
    if approval_status == "rejected":
        return "The recommendation was not approved."
    if approval_status == "revision_requested":
        return "Revision was requested before approval."
    if approval_status == "pending":
        return "Recommendation is awaiting human approval."
    if approval_status == "approved" and recommendation == "rollout":
        return "Rollout is supported and approved."
    ...
```

```python
def _approval_summary(state: AgentState) -> str:
    approval = state["human_approval"]
    if approval["status"] == "skipped":
        return "Approval was not required for this recommendation."
    if approval["status"] == "pending":
        return "The recommendation is awaiting human approval."
    if approval["status"] == "approved":
        return "The recommendation was approved."
    if approval["status"] == "rejected":
        return "The recommendation was not approved."
    if approval["status"] == "revision_requested":
        return "Revision was requested before approval."
    return ""
```

- [ ] **Step 4: Run the narrow tests to verify they pass**

Run: `uv run pytest tests/test_agent_workflow.py tests/test_executive_summary_agent.py -v`

Expected: PASS with workflow ordering and approval-aware summary wording.

- [ ] **Step 5: Commit**

```bash
git add packages/agents/workflow.py packages/agents/service.py packages/agents/executive_summary_agent.py packages/agents/__init__.py tests/test_agent_workflow.py tests/test_executive_summary_agent.py
git commit -m "[New Feature] Integrate approval checkpoint into agent workflow"
```

### Task 4: Final Verification And Cleanup

**Files:**
- Review: `packages/agents/state.py`
- Review: `packages/agents/human_approval_agent.py`
- Review: `packages/agents/nodes.py`
- Review: `packages/agents/workflow.py`
- Review: `packages/agents/service.py`
- Review: `packages/agents/executive_summary_agent.py`
- Review: `tests/test_agent_state.py`
- Review: `tests/test_human_approval_agent.py`
- Review: `tests/test_agent_nodes.py`
- Review: `tests/test_agent_workflow.py`
- Review: `tests/test_executive_summary_agent.py`

**Interfaces:**
- Consumes: all code and tests from Tasks 1-3
- Produces: verified implementation with lint and full test evidence

- [ ] **Step 1: Run Ruff**

Run: `uv run ruff check .`

Expected: PASS with no lint errors.

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest`

Expected: PASS. If database-backed tests are skipped because `DATABASE_URL` is unset, record that explicitly in the completion summary.

- [ ] **Step 3: Inspect changed files**

Run: `git diff --stat`

Expected: a focused diff covering the approval workflow files and tests only, with `/ask` unchanged.

- [ ] **Step 4: Commit the final implementation**

```bash
git add packages/agents tests docs/superpowers/plans/2026-07-08-human-approval-workflow.md
git commit -m "[New Feature] Add human approval workflow"
```

- [ ] **Step 5: Prepare the closeout summary**

Include:

```text
- files changed
- approval flow behavior
- lint/test commands run
- whether /ask stayed unchanged
- what Issue #31 should build next:
  - LangGraph interrupt/resume with checkpointer and thread IDs
  - approval input surface and persistence strategy
  - routing behavior for rejected or revision-requested outcomes
```
