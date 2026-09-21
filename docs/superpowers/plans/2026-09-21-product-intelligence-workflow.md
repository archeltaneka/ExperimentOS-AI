# Product Intelligence Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose validated Phase 4 analysis through the existing ExperimentOS workflow and `/ask` without compromising deterministic evidence, approval, privacy, or legacy compatibility.

**Architecture:** One request-scoped ExperimentOS `AnalysisService` validates explicit methods and dispatches existing analyzers. Existing graph nodes consume typed, protected evidence; raw data and native intermediate results remain outside graph state. Existing evaluation and centralized policy gain structured integration checks.

**Tech Stack:** Python 3.12+, Pydantic, LangGraph, FastAPI, existing NumPy/SciPy/scikit-learn services, pytest, Ruff, mypy; existing optional EconML/DoWhy dependency groups.

**Spec:** [Product intelligence workflow design](../specs/2026-09-21-product-intelligence-workflow-design.md). Read it before execution; this plan implements its boundaries and acceptance matrix.

**Stage:** Documents drafted together at the user's explicit request. Implementation has not started. Review and execution-method selection remain required.

## Global Constraints

- The LLM does not calculate statistics or business impact.
- Method selection is explicit and validated; no automatic method search or substitution.
- Existing estimators and adapters remain independently callable outside LangGraph.
- Business inputs are never invented or inferred from generated prose.
- Structured analysis is authoritative over generated prose.
- Positive statistical or business results do not automatically trigger rollout.
- Reuse existing statistical validation, quality policy, and thresholds; do not duplicate statistical thresholds in workflow nodes or CI YAML.
- Keep EconML and DoWhy optional; importing the workflow must not require either dependency.
- Preserve `agent_workflow` as default and preserve the explicit `legacy_rag` mode.
- Preserve existing required API fields; add optional versioned structures.
- No new estimators, adapters, frontend, database tables, autonomous launch/stopping, allocation, or rollout automation.
- Verification is deterministic and offline, using repository-local fixtures and fake/mock providers.
- Do not merge or alter branch protection.

## Review Focus

1. Concurrent requests reuse the same dataset reference: never resolve data or native evidence from another request (Tasks 1, 7).
2. A caller fabricates an already-successful identification result: ingress refuses it; identification is computed from declarations (Tasks 2, 3).
3. A candidate summary uses a real number for the wrong quantity/unit: numeric membership alone must not approve it (Task 6).
4. Strict observability providers throw before export, including activation/config construction: computation and serialization still succeed (Task 8).
5. Nested public validation errors contain raw submitted rows: reject safely without echoing input or exception context (Tasks 1, 7).

## File ownership map

New implementation files under `packages/experiments/analysis/orchestration/`:

| Files | Responsibility |
| --- | --- |
| `__init__.py`, `requests.py` | Public typed analysis inputs, normalization and refusal contracts. |
| `datasets.py` | Request-scoped input snapshots and resolver protocol/implementation. |
| `registry.py` | Immutable method metadata, typed owned handler registration, duplicate/unknown checks. |
| `dispatch_randomized.py`, `dispatch_causal.py`, `dispatch_optional.py` | Adapt owned requests to existing services; no formulas. |
| `results.py` | Public result envelope, status and artifact reference contracts. |
| `evidence_randomized.py`, `evidence_causal.py` | Typed safe evidence views and explicit native-result projection. |
| `service.py` | Orchestration, private native-result storage, authoritative result access and failure normalization. |
| `business.py` | Eligibility composition with existing impact source adapters/service; safe business projection. |
| `integrity.py`, `rendering.py` | Exact evidence preservation and deterministic presentation. |
| `observability.py` | Non-throwing facade and allowlisted metadata for the integration path. |

Existing integration files: `packages/experiments/analysis/__init__.py`; `packages/agents/{state,planner,nodes,workflow,service,experiment_analysis_agent,business_impact_agent,risk_assessment_agent,decision_agent,executive_summary_agent,observability}.py`; `apps/api/{ask_service,main}.py`.

Evaluation: extend `packages/evals/{agent_dataset,agent_evaluator,agent_metrics,agent_report,agent_e2e,agent_e2e_report,factuality/runner,factuality/deterministic,policy/models,policy/adapters}.py`. Add `packages/evals/agent_analysis_cases.py` for shared local integration fixtures/checks, not another evaluation framework. Change `config/evaluation/quality_policy.yaml`, `.github/workflows/ci.yml`, and existing CI report/verification consumers only where report compatibility requires it.

Fixtures/documentation: `data/eval/workflow_analysis/`, `docs/phase4/workflow_analysis.md`, `docs/phase4/statistical_analysis_contracts.md`, `docs/phase3/quality_policy.md`, `docs/phase3/ci_quality_gates.md`, and the existing top-level documentation index if linked there. Never import `tests` from production code.

## Execution conventions

After approval, read the TDD and execution skills and verify the branch/worktree before edits. Use the current dedicated issue branch; do not move or discard user changes. No agent delegation until the execution method is selected. All commands below run at the repository root. Set `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, and use the existing network-blocking test fixture. Record actual red/green outcomes, not expected outcomes as if executed. Use `apply_patch` for files and explicit file lists for commits.

Each task's listed test cases are mandatory in addition to its representative code example. Code blocks define intended interfaces and executable assertions; complete field inventories come from the spec and native types, not invented statistical formulas. Complete tasks sequentially because their interfaces are dependent. Within a task, run a narrow failing test before each behavior increment.

Baseline already observed at `cacb99c`: `tests/test_api_ask.py tests/test_agent_state.py tests/test_agent_workflow.py`: **44 passed, 1 warning in 1.18s**. Repeat before code if the branch base changes.

## Task 1: Typed input and isolated datasets

**Files:** Create `orchestration/requests.py`, `orchestration/datasets.py`, `orchestration/__init__.py`; tests `tests/test_analysis_orchestration_requests.py`, `tests/test_analysis_datasets.py`.

**Interfaces:**

- `AnalysisDatasetInput`: frozen fields `reference: str`, `experiment_id: str`, `version: str`, `columns: tuple[str, ...]`, `rows: tuple[tuple[JsonScalar, ...], ...]`, `provenance: ProvenanceRecords`; `JsonScalar = str | int | float | bool | None` with finite numbers and strict scalar validation.
- `ResolvedAnalysisDataset`: frozen `table: AnalysisTable`, `provenance: ProvenanceRecords`, `version: str`.
- `DatasetResolutionFailure`: safe `code: str`, no raw input.
- `AnalysisDataResolver.resolve(reference: str, experiment_id: str) -> ResolvedAnalysisDataset | DatasetResolutionFailure`.
- `RequestDatasetResolver(datasets: tuple[AnalysisDatasetInput, ...])` implements the protocol.
- `normalize_analysis_input(payload: JsonValue, *, experiment_id: str) -> AnalysisInput` returns a frozen typed request or `AnalysisRoutingRefusal`, never the raw mapping.

Normalized request layout is fixed here for the following tasks. Each wrapper has `schema_version: Literal["1"]`, `request_id: NonEmptyStr`, `experiment_id: NonEmptyStr`, a literal `method`, and `business: BusinessImpactRequest | BusinessInputRefusal | None`. `BusinessInputRefusal` contains a tuple of owned safe `Diagnostic` records and a typed abstention reason. Request identity must agree with the native execution identity. Each ordinary data reference uses `DatasetReference(reference: NonEmptyStr, version: NonEmptyStr)`; the resolver looks up its reference string and the service verifies the returned version before dispatch. Versions are explicit, never inferred from row contents.

| Wrapper in `requests.py` | Method | Method-specific fields reusing existing types |
| --- | --- | --- |
| `FixedHorizonWorkflowRequest` | `randomized_fixed_horizon` | `execution: RandomizedAnalysisExecutionRequest`, `binding: AnalysisDataBinding`, `dataset: DatasetReference` |
| `CupedWorkflowRequest` | `cuped` | `execution: CupedAnalysisExecutionRequest`, `binding: AnalysisDataBinding`, `dataset: DatasetReference` |
| `BayesianWorkflowRequest` | `bayesian_ab` | `execution: BayesianAnalysisExecutionRequest`, `binding: AnalysisDataBinding`, `dataset: DatasetReference` |
| `SequentialWorkflowRequest` | `sequential` | `plan: SequentialAnalysisPlan`, `looks: tuple[SequentialLookInput, ...]` |
| `DidWorkflowRequest` | `did` | `execution: DifferenceInDifferencesExecutionRequest`, `dataset: DatasetReference` |
| `PropensityWorkflowRequest` | `propensity_diagnostics` | `execution: PropensityExecutionRequest`, `dataset: DatasetReference` |
| `IPWWorkflowRequest` | `ipw_ate` or `ipw_att` | `analysis_request: ObservationalAnalysisRequest`, `propensity_binding: PropensityDataBinding`, `propensity_configuration: PropensityConfig`, `binding: IPWOutcomeBinding`, `configuration: IPWConfig`, `dataset: DatasetReference` |
| `DMLWorkflowRequest` | `dml` | `analysis_request: ObservationalAnalysisRequest`, `binding: DMLDataBinding`, `configuration: DMLConfig`, `dataset: DatasetReference` |
| `HTEWorkflowRequest` | `hte` | `analysis_request: ObservationalAnalysisRequest`, `binding: HTEDataBinding`, `configuration: HTEConfig`, `modifier: EffectModifierDefinition`, `dataset: DatasetReference` |
| `EconMLDMLWorkflowRequest` | `econml_dml` | DML fields above plus `adapter_configuration: AdvancedEstimatorConfig` |
| `EconMLHTEWorkflowRequest` | `econml_hte` | HTE fields above plus `adapter_configuration: AdvancedEstimatorConfig` |
| `DoWhyWorkflowRequest` | `dowhy` | `analysis_request: ObservationalAnalysisRequest`, `binding: DoWhyDataBinding`, `configuration: DoWhyConfig`, `dataset: DatasetReference | None` |

`SequentialLookInput` reuses `look_index`, `information_time`, `plan_fingerprint`, `analysis_request`, `binding`, and `executed_at` from `SequentialLookExecution`, replacing its `table` field with `dataset: DatasetReference`. This is a transport wrapper, not another statistical plan. `WorkflowAnalysisRequest` is a Pydantic discriminated union of these wrappers by `method`. `AnalysisRoutingRefusal` has safe method/request identity, normalized invalid/abstained status, diagnostics and abstention; normalization never retains malformed parameter values. The public ingress uses `parameters` for the wrapper's method-specific fields; normalization merges only validated common fields into the selected wrapper. Unknown keys are rejected.

- [ ] Write tests for successful immutable resolution, duplicate references, ownership/version mismatch, missing provenance, invalid row widths/types/nonfinite numbers, and independent resolvers sharing a reference. Representative test:

```python
def test_missing_reference_is_a_typed_refusal():
    resolver = RequestDatasetResolver(())
    result = resolver.resolve("absent", "experiment-a")
    assert isinstance(result, DatasetResolutionFailure)
    assert result.code == "analysis.dataset_missing"
```

- [ ] Run `uv run pytest -q tests/test_analysis_datasets.py tests/test_analysis_orchestration_requests.py`; expect missing imports/behavior, not an environment failure.
- [ ] Implement immutable snapshots and keyed lookup. Use exact ownership checks and fixed safe error codes:

```python
table = AnalysisTable(columns=dataset.columns, rows=dataset.rows)
resolved = ResolvedAnalysisDataset(
    table=table,
    provenance=dataset.provenance,
    version=dataset.version,
)
```

  No global registry or arbitrary path resolution. Malformed public datasets are converted at the boundary to a refusal that exposes only safe field locations.
- [ ] Define normalized method wrappers by reusing native requests/bindings/configuration. Randomized wrappers contain execution+binding+reference; sequential wraps plan and table-free look declarations; observational wrappers contain declarations+binding+config, never caller-certified identification. IPW adds declared propensity binding/configuration and the requested estimand. Business input normalization stores either `BusinessImpactRequest` or a typed business refusal, so malformed business fields cannot erase a valid statistical request.
- [ ] Add red/green parameterized normalization tests for all registry method IDs, missing/blank/list-valued/unknown method, wrong design/backend/estimand, malformed prior/plan, forged `identification_result`, and business-only invalidity. Unsupported/ambiguous means abstained; conflicting known parameters means invalid.
- [ ] Rerun both files and existing `tests/test_analysis_requests.py tests/test_analysis_contract_serialization.py`; commit as `feat(analysis): define explicit workflow inputs and dataset isolation`.

## Task 2: Registry, safe result contracts, and fixed-horizon dispatch

**Files:** Create `orchestration/{registry,results,evidence_randomized,dispatch_randomized,service}.py`; extend package exports; tests `tests/test_analysis_dispatch.py`, `tests/test_analysis_envelope.py`, `tests/test_analysis_service.py`.

**Interfaces:**

- `MethodRegistration`: immutable ID/capability/design/estimand/input-type/dependency/version metadata plus an owned handler.
- `AnalysisMethodRegistry(entries: tuple[MethodRegistration, ...])`; `.method_ids -> tuple[str, ...]`; `.resolve(method: str) -> MethodRegistration | None`; `default_registry() -> AnalysisMethodRegistry`.
- `AnalysisResultEnvelope`: spec §6, immutable, discriminated evidence union, typed refusal and integrity findings; `.evidence_fingerprint: str` canonical safe statistical evidence digest.
- `AnalysisService(*, resolver: AnalysisDataResolver, registry: AnalysisMethodRegistry | None = None, observability_provider: BaseObservabilityProvider | None = None)`.
- `.analyze(request: AnalysisInput) -> AnalysisResultEnvelope`; `.authoritative_result(analysis_id: str) -> AnalysisResultEnvelope` returns a defensive copy.
- `project_evidence(native: OwnedAnalysisResult) -> AnalysisEvidence`; `OwnedAnalysisResult` is an explicit union of existing result classes, never `Any` or a third-party class.

- [ ] Write registry tests: unique IDs, explicit resolution, no best-method search, unknown/ambiguous method never invokes a handler. Use mock owned handlers, not mock calculations, to assert dispatch call counts.

```python
def test_unknown_method_does_not_resolve():
    registry = default_registry()
    assert registry.resolve("choose_largest_effect") is None
    assert "randomized_fixed_horizon" in registry.method_ids
```

- [ ] Run `uv run pytest -q tests/test_analysis_dispatch.py tests/test_analysis_envelope.py tests/test_analysis_service.py` and observe the missing behavior.
- [ ] Implement the fixed-horizon handler using the existing service:

```python
native = RandomizedAnalysisService(observability_provider=provider).analyze(
    request.execution,
    dataset.table,
    request.binding,
    provenance=dataset.provenance,
)
```

  Validate outer method/native fixed-horizon agreement before this call. Preserve estimator-owned eligibility; spy on the numerical function to prove invalid data does not reach it. Store the native result privately; publish a typed projection with unchanged inferential values, assumption status, diagnostics and provenance.
- [ ] Add complete-envelope serialization tests: disallowed extra object rejected; native request/raw data absent; intervals retain type/level; timestamps excluded from stable fingerprints; round trip retains all public evidence. Use native result fixtures from existing randomized service tests; do not assert only copied output against itself.
- [ ] Add service tests for insufficient sample, missing data, malformed request, unexpected estimator exception (safe typed failed result), and refusal artifact provenance. Assert missing dataset provenance is not fabricated from request metadata.
- [ ] Rerun new tests plus `tests/test_randomized*.py`; commit as `feat(analysis): orchestrate explicit fixed-horizon analysis`.

## Task 3: Remaining implemented dispatch and optional adapters

**Files:** Extend `dispatch_randomized.py`, `registry.py`, `requests.py`, `evidence_randomized.py`, `results.py`, `service.py`; create `dispatch_causal.py`, `dispatch_optional.py`, `evidence_causal.py`; tests `tests/test_analysis_dispatch_randomized.py`, `tests/test_analysis_dispatch_causal.py`, `tests/test_analysis_dispatch_optional.py`.

**Interfaces:** Keep Task 2 service/projection signatures. Add typed evidence variants and handlers for every spec §5 method. Each handler returns only existing owned native results. Optional adapter factories import the owned adapter lazily; adapter dependency discovery stays inside existing dependency modules.

- [ ] Write tests for every registry entry reaching exactly the requested service. Cover CUPED request semantics, Bayesian priors/likelihood, and sequential declared-look reconstruction. Check invalid plans and priors stop before numerical work.
- [ ] Run `uv run pytest -q tests/test_analysis_dispatch_randomized.py` and observe failure; implement wrappers that call `CupedAnalysisService.analyze`, `BayesianAnalysisService.analyze`, and `SequentialAnalysisService.analyze` with existing argument contracts. Sequential reconstruction uses `SequentialLookExecution` and resolved snapshots; never rerun as fixed horizon on plan failure. Rerun to green.
- [ ] Write causal red tests for valid DiD, propensity diagnostics, IPW ATE/ATT, repository DML and HTE; also post-treatment adjustment, no overlap, sparse subgroup and invalid graph. Validate that causal declarations run through identification before estimation.

```python
identification = CausalIdentificationService().identify(request.analysis_request)
# The existing identification status gate determines whether an execution
# request may be assembled; the workflow does not revise identification.
```

  DiD already owns identification in `validate_did_input`; preserve that path instead of calculating it twice. For IPW, fit the explicitly declared propensity specification, retain its diagnostics internally, and construct `IPWExecutionRequest` only after prerequisite gates. Do not accept raw propensity arrays over `/ask`.
- [ ] Run `uv run pytest -q tests/test_analysis_dispatch_causal.py`; implement adapters and typed aggregate evidence projections. Do not serialize `PropensityResult` wholesale: project diagnostic summaries and provenance, not scores/weights/row IDs. Rerun to green.
- [ ] Write optional-unavailable tests by patching existing dependency loaders. Example expected contract:

```python
assert result.method == "econml_dml"
assert result.status == "unavailable"
assert repository_dml_spy.call_count == 0
assert result.evidence is not None
```

  Test unavailable and incompatible runtimes, unsupported inference, explicit DoWhy operations, and package import without optional dependencies. Preserve native status/reasons alongside normalized unavailable status.
- [ ] Run `uv run pytest -q tests/test_analysis_dispatch_optional.py`; implement existing adapters and safe projections, including graph fingerprints in place of graph payloads. No new adapters. Rerun new dispatch tests plus `tests/test_advanced*.py tests/test_dml*.py tests/test_hte*.py tests/test_econml*.py tests/test_dowhy*.py`; commit as `feat(analysis): dispatch implemented causal and optional methods explicitly`.

## Task 4: State, planner, and experiment-analysis integration

**Files:** Modify `packages/agents/{state,planner,nodes,workflow,service,experiment_analysis_agent}.py`; tests `tests/test_agent_state.py`, `tests/test_agent_workflow.py`, `tests/test_agent_analysis_workflow.py`, `tests/test_experiment_analysis_agent.py`.

**Interfaces:**

- `AgentState.analysis_request: NotRequired[AnalysisInput | None]`, `analysis_result: NotRequired[AnalysisResultEnvelope | None]`; compatible update/input fields.
- `AgentWorkflowService.run` adds optional `analysis_request: AnalysisInput | None` and `analysis_datasets: tuple[AnalysisDatasetInput, ...]` keyword parameters; it constructs one resolver/service/graph dependency context per analysis run.
- Existing experiment agent accepts an optional `analysis_service: AnalysisService`; ordinary repository interface remains unchanged.
- `plan_analysis(request: AnalysisInput, legacy_plan: PlannerPlan) -> PlannerPlan`, using the existing `PlannerPlan` from `packages/agents/planner.py`.

- [ ] Write failing tests for new fields surviving planner reconstruction, old state construction, JSON validation, direct graph question-only compatibility, method retention and refusal routing.

```python
def test_legacy_initial_state_needs_no_analysis_fields():
    state = create_initial_state("Tell me about checkout")
    assert state.get("analysis_request") is None
    assert state.get("analysis_result") is None
    assert validate_state_shape(state)["question"] == state["question"]
```

- [ ] Run `uv run pytest -q tests/test_agent_state.py tests/test_agent_analysis_workflow.py`; observe failures for new behavior.
- [ ] Preserve the existing planner defaults and reducers; structured intent takes priority. Explicit analysis schedules experiment analysis and summary without requiring retrieval when data is complete. Retain ordinary planner intent decisions and trace order.

```python
if state.get("analysis_request") is not None:
    envelope = self.analysis_service.analyze(state["analysis_request"])
    return {"analysis_result": envelope}
```

  Complete this branch with existing node metrics/traces; the branch returns before legacy aggregate calculations. It never writes a fabricated legacy `statistical_significance` field.
- [ ] Test valid fixed-horizon and DiD through the real graph with local data, no database retrieval, and a direct-analyzer reference comparison. Test unsupported selection cannot fall back to the legacy experiment agent.
- [ ] Rerun `uv run pytest -q tests/test_agent_state.py tests/test_agent_workflow.py tests/test_agent_analysis_workflow.py tests/test_experiment_analysis_agent.py`; commit as `feat(agents): route typed analysis through the existing workflow`.

## Task 5: Business, risk, decision, and approval gates

**Files:** Create `orchestration/business.py`; modify `service.py`, result types, `packages/agents/{business_impact_agent,risk_assessment_agent,decision_agent,nodes}.py`; tests `tests/test_analysis_business_gating.py`, `tests/test_agent_analysis_decision.py`, existing business/decision/approval tests.

**Interfaces:** `AnalysisService.analyze_business(analysis_id: str) -> AnalysisResultEnvelope` uses stored native evidence and stored parsed business inputs/refusal. `business_preconditions` returns an owned typed gate outcome using native statuses and existing source adapter/quality results. It does not calculate thresholds. `BusinessImpactEvidence` is a typed safe projection preserving `inputs`, effect evidence, assumptions, derivations, scenario bands, diagnostics and provenance while excluding any raw source internals.

- [ ] Write failing spy tests showing blocked upstream evidence never calls `BusinessImpactService.analyze`; missing business inputs/provenance generate business-only abstention; invalid subgroup, sequential and unsupported DoWhy sources refuse. Include negative and cross-zero valid scenarios.
- [ ] Run `uv run pytest -q tests/test_analysis_business_gating.py tests/test_agent_analysis_decision.py`.
- [ ] Compose existing source validation and the existing service; do not rewrite arithmetic:

```python
impact = BusinessImpactService().analyze(native_result, business_request)
```

  This call executes only after the outer prerequisite gate. Use existing `adapt_source` for source eligibility, and let existing business validation enforce sourced fields, units/horizons and arithmetic. Business-invalid input cannot replace valid statistical evidence.
- [ ] Assert exact equality of the statistical evidence fingerprint before/after business processing. Compare business results to a direct call on the same native result and to the existing hand-calculable business fixture expectations. Never force an E2E analyzer interval to an invented value to make arithmetic easier.
- [ ] Add Phase 4 risk/decision consumers. Preserve diagnostic severities and missing readiness evidence; no rollout from p-value/revenue alone. A request for analysis alone leaves decision not required. Decision intent with incomplete readiness returns needs-more-data. Existing conclusive legacy paths and approval requirements remain intact.
- [ ] Add approval regressions for pending, approved, rejected, revision requested, and no required approval; verify Phase 4 evidence cannot clear an existing required flag. Rerun `uv run pytest -q tests/test_analysis_business_gating.py tests/test_agent_analysis_decision.py tests/test_business_impact_agent.py tests/test_decision_agent.py tests/test_human_approval_agent.py tests/test_impact*.py`; commit as `feat(agents): gate business and decision processing on validated evidence`.

## Task 6: Protected evidence, artifacts, and deterministic prose

**Files:** Create `orchestration/{integrity,rendering}.py`; modify result/service types, `packages/agents/{nodes,executive_summary_agent}.py`; tests `tests/test_analysis_integrity.py`, `tests/test_analysis_rendering.py`, `tests/test_analysis_artifacts.py`.

**Interfaces:**

- `render_analysis(envelope: AnalysisResultEnvelope) -> str` formats existing typed values; no numerical estimation.
- `protect_update(*, node: str, current: AgentState, proposed: AgentStateUpdate, analysis_service: AnalysisService) -> AgentStateUpdate` restores canonical evidence and canonical statistical prose on violation.
- `protect_response(state: AgentState, analysis_service: AnalysisService) -> AgentState` performs final canonical comparison before mapping.
- `AnalysisIntegrityFinding`: code, node, severity, fixed safe message; no rejected prose/data payload.

- [ ] Add red tests for replaced envelope, nested mutation through a defensive-copy breach attempt, omitted uncertainty/assumptions/diagnostics/provenance, changed method/artifacts, and forbidden business-source replacement. Test legitimate business augmentation does not alter the statistical fingerprint.
- [ ] Run `uv run pytest -q tests/test_analysis_integrity.py tests/test_analysis_rendering.py tests/test_analysis_artifacts.py`.
- [ ] Implement exact projection comparison against the service's sealed copy and role-based update rules. The business node may publish only the current service-returned envelope. Other nodes cannot write analysis evidence. Copy state defensively before calling injected agents.
- [ ] Add typed artifact references and citations. Stable fingerprint excludes request timestamp/duration; artifact reference points to returned in-memory evidence. Refusal artifacts cite the actual request and explain absent sources; no fake text citations.
- [ ] Implement deterministic per-family rendering of method/status/estimand, estimate and correct units, interval type/level, assumptions, diagnostic limitations, business scenario and abstention. Guard every presentation field that could carry statistical/business claims, not only the top-level answer.

```python
canonical_text = render_analysis(analysis_service.authoritative_result(analysis_id))
if candidate_text != canonical_text:
    published_text = canonical_text
else:
    published_text = candidate_text
```

  Record conflicts with fixed diagnostic codes. Exact canonical matching is deliberately conservative and does not claim general natural-language entailment. Keep ordinary non-analysis summary behavior unchanged.
- [ ] Use a fake presenter returning 9.5% versus a structured 2.1% fixture, invented p-value, revenue, population, and a correct number attached to the wrong unit. Assert canonical values unchanged and rejected values absent from every public narrative. Correct canonical candidate passes. Add summary tests to ensure unavailable/abstained output has no fabricated inference.
- [ ] Rerun the three new files and `tests/test_executive_summary_agent.py`; commit as `feat(analysis): protect structured evidence and ground workflow presentation`.

## Task 7: Backward-compatible API and real E2E fixtures

**Files:** Modify `apps/api/{ask_service,main}.py`; create `packages/evals/agent_analysis_cases.py`, `data/eval/workflow_analysis/{randomized,did,business,insufficient,optional_unavailable,prose_conflict}.json`; tests `tests/test_api_analysis.py`, `tests/test_analysis_e2e.py`; extend `tests/test_api_ask.py`.

**Interfaces:**

- Optional `AskRequest.analysis: JsonValue | None` ingress, normalized before the graph; optional `analysis_datasets` inputs validated without leaking data.
- Optional `AskResponse.analysis: AnalysisResultEnvelope | None`.
- `AnalysisWorkflowCase`: frozen `case_id: str`, `ask_payload: dict[str, JsonValue]`, `expected_method: str | None`, `expected_status: str`, `presenter_candidate: str | None`, and structured expected evidence/checks. Raw fixture payloads stay local to evaluation execution and never enter evaluation result reports.
- `load_analysis_workflow_cases() -> tuple[AnalysisWorkflowCase, ...]` reads checked-in JSON. `build_analysis_case_service(case) -> AgentWorkflowService` uses real analyzers and deterministic injected context. `run_direct_reference(case) -> AnalysisEvidence | None` invokes the relevant native analyzer independently of the orchestration service.

- [ ] Write failing API tests for existing request/response deserialization, optional field absence, new response round trip, 404/422/502 preservation, and analysis refusals returning structured 200. Verify new kwargs are not sent to legacy three-argument workflow test doubles when no analysis input exists.
- [ ] Run `uv run pytest -q tests/test_api_ask.py tests/test_api_analysis.py tests/test_analysis_e2e.py`.
- [ ] Add ingress normalization, request-scoped resolver creation, typed output mapping and final integrity check. Keep dataset objects out of state and returned traces. Add safe validation-error conversion for new fields; retain ordinary FastAPI behavior elsewhere. Explicit legacy mode ignores new analysis extensions without invoking them, as specified.
- [ ] Build local real-analyzer JSON fixtures from existing randomized and DiD fixture construction patterns; preserve native contracts and seeds. Include explicit sourced business inputs. Fixture loading must validate all known method request shapes. Do not import test helper modules from `packages/evals`.
- [ ] Add randomized, DiD and business real E2E tests and compare direct native projection → service evidence → state → API exactly. Add invalid/abstained/optional-unavailable cases and fake conflicting summaries.
- [ ] Add concurrent requests with identical dataset IDs and different data, identical request IDs, mismatched dataset experiment IDs, malformed scalar rows and malicious exception content. Assert no cross-request data and no raw row sentinel in API JSON or errors. Preserve legacy API/QA tests.
- [ ] Rerun all Task 7 tests plus `tests/test_agent_analysis_workflow.py`; commit as `feat(api): expose optional typed workflow analysis with offline end-to-end coverage`.

## Task 8: Trace integration and provider failure isolation

**Files:** Create `orchestration/observability.py`; modify `orchestration/service.py`, `packages/agents/{service,observability}.py`, `apps/api/{main,ask_service}.py`, and `packages/observability/redaction.py` only for additive analysis-sensitive keys; tests `tests/test_analysis_workflow_observability.py` and existing observability integration tests.

**Interfaces:** `safe_analysis_provider(provider: BaseObservabilityProvider) -> BaseObservabilityProvider` wraps this integration path, preserving owned span semantics with no-op fallback. `analysis_metadata(envelope: AnalysisResultEnvelope) -> dict[str, object]` constructs an explicit allowlist; it never dumps an arbitrary model.

- [ ] Write failing tests capturing root/analysis/validation/estimator/business/serialization events and method/status codes. Include content tracing enabled; search captured payloads recursively for unique raw-row/outcome/covariate/graph/propensity/CATE/posterior sentinels.
- [ ] Run `uv run pytest -q tests/test_analysis_workflow_observability.py`.
- [ ] Implement explicit metadata construction:

```python
metadata = {
    "method": envelope.method or "ambiguous",
    "capability": envelope.capability,
    "status": envelope.status,
    "analysis_id": envelope.analysis_id,
}
```

  Add safe native codes/versions/duration, never envelope/request/raw-result serialization. Use existing analyzer spans for internal validation where available; do not fabricate events for stages skipped by gates.
- [ ] Add parameterized fake-provider exceptions at start-root/start-child/current-span/activation/build-config/metadata/finish/export, including strict mode and composite providers. The same canonical result must return. Safe diagnostic counters may report provider failures, without changing estimator status or erroring the API.
- [ ] Rerun new tests and `tests/test_observability*.py tests/test_randomized_observability.py tests/test_cuped_observability.py tests/test_bayesian_observability.py tests/test_dowhy_observability.py`; commit as `feat(observability): trace workflow analysis without exposing private data`.

## Task 9: Extend agent evaluation and centralized policy

**Files:** Modify the evaluation files in the ownership map, `config/evaluation/quality_policy.yaml`, and existing CI report readers if required; tests `tests/test_agent_analysis_evaluation.py`, `tests/test_analysis_policy.py`, existing agent/factuality/policy/CI-report tests.

**Interfaces:** Add optional structured analysis expectations to existing case models and `analysis_checks` to existing sample reports. Each check records code, pass/warning/fail/skipped quality status, method, execution status, applicability, and safe expected/actual public evidence. Add `agent_json` and `agent_e2e_json` policy source formats; keep legacy Markdown readers supported. Add no standalone analysis evaluator or quality CLI.

- [ ] Write red tests proving the existing evaluator executes a real analysis graph, not `StubWorkflowService` state, for new cases. Assert dispatch and downstream call counts through spies at existing injectable service boundaries. Test method, estimand, numerical evidence, uncertainty, assumptions, diagnostics, limitations, provenance, status and abstention preservation.
- [ ] Run `uv run pytest -q tests/test_agent_analysis_evaluation.py tests/test_analysis_policy.py`.
- [ ] Wire Task 7 case loader into default existing agent/E2E case assembly, preserving old cases. Agent cases carry optional analysis payloads into the real service; E2E cases use real `/ask` mapping. Serialize public evidence/checks only, not raw fixture payloads. Update known-limitations text to distinguish legacy stub cases from real-analyzer cases.
- [ ] Extend existing factuality evidence construction with structured artifacts. Grounding checks assert unsupported prose was withheld; analysis correctness checks operate on typed evidence, never Markdown parsing. Deliberately corrupt a result/interval/provenance/backend and require a blocking report finding.
- [ ] Add JSON policy adapters for existing aggregate metrics plus `analysis` counters. Keep statistical thresholds unchanged. Integration counters include wrong routing/substitution, invoked-after-block, lost evidence, unsourced business, unsupported prose, unavailable-reported-success, raw-data/object leakage and mutation. Expected refusal is a passing software case, not a failed analysis test.

```python
assert negative_effect_case.analysis_checks["result_integrity"].status == "pass"
assert missing_interval_case.analysis_checks["uncertainty_preserved"].status == "fail"
assert unavailable_case.analysis_checks["adapter_identity"].status == "pass"
```

  Use the existing policy model/status vocabulary; these attributes describe the new structured check mapping defined in this task. Tests must also cover advisory-only evidence and expected skipped optional capabilities.
- [ ] Switch agent/E2E source paths to JSON in central policy, retain old reader regression tests, and update fixture/report consumers that depended on Markdown source format. Assert missing required JSON is blocking; do not silently fall back to stale Markdown.
- [ ] Rerun new tests plus `tests/test_agent_evaluation.py tests/test_agent_e2e_evaluation.py tests/test_factuality.py tests/test_quality_policy.py tests/test_ci_reporting.py tests/test_ci_quality_gate.py`; commit as `feat(evals): evaluate workflow analysis integrity through existing quality policy`.

## Task 10: CI coverage and documentation

**Files:** Modify `.github/workflows/ci.yml`, documentation files in the map, and existing verification/report inventory only where new required artifacts apply; tests `tests/test_analysis_workflow_documentation.py`, `tests/test_github_actions_ci.py`, `tests/test_phase3_verification.py`.

**Interfaces:** Existing CI jobs and commands remain entry points. Existing agent/E2E JSON artifacts become the authoritative source for workflow integration checks. The existing optional advanced job continues to verify actual installed adapters.

- [ ] Add red CI tests requiring new service/state/E2E/prose/privacy/API suites in the deterministic unit job and existing statistical baseline in the offline job. Assert no OpenAI/Ollama/hosted judge dependency, no copied numerical policy threshold in YAML, and the new JSON reports are uploaded/consumed.
- [ ] Run `uv run pytest -q tests/test_github_actions_ci.py tests/test_analysis_workflow_documentation.py`.
- [ ] Add commands for existing `run_agent` and `run_agent_e2e` to the offline job; these now include the real analysis cases. Keep optional installation and actual optional-adapter conformance in the existing optional job; the default job verifies explicit unavailable behavior.
- [ ] Write `docs/phase4/workflow_analysis.md` with the six runnable fixture-based examples from spec §11. Include a full request-loading example:

```python
import json
from pathlib import Path
import httpx

payload = json.loads(Path("data/eval/workflow_analysis/randomized.json").read_text())
response = httpx.post("http://localhost:8000/ask", json=payload["ask_payload"])
response.raise_for_status()
analysis = response.json()["analysis"]
print(analysis["method"], analysis["status"], analysis["evidence"])
```

  Explain that this API example requires the existing experiment record; tests override existence checks with local fixtures. Add a direct-service example using the same native contracts and resolver without LangGraph. Explain every responsibility/safety/mode/status point in spec §§4–11 and link the artifact lifetime and method support table.
- [ ] Validate documentation fixture examples against request normalization and API response types in tests. Check all required six examples exist; the conflict example is explicitly a test-only fake presenter, never a raw presentation field trusted by `/ask`.
- [ ] Rerun Task 10 tests plus `tests/test_analysis_e2e.py`; commit as `docs(ci): document and verify deterministic workflow analysis integration`.

## Task 11: Verification, review, and handoff

**Files:** Product changes only if a failing check reveals an in-scope defect; rerun the owning red/green cycle. Store command logs under `artifacts/issue108/` and final handoff evidence under `docs/phase4/workflow_analysis.md` only if appropriate. Never commit sensitive logs or regenerated unrelated reports.

- [ ] Read `superpowers:verification-before-completion`. Review the final diff for every prohibited behavior listed below before claiming success.
- [ ] Run focused contracts/services, then graph/API/business suites:

```bash
uv run pytest -q tests/test_analysis_orchestration_requests.py tests/test_analysis_datasets.py tests/test_analysis_dispatch*.py tests/test_analysis_envelope.py tests/test_analysis_service.py
uv run pytest -q tests/test_agent_state.py tests/test_agent_workflow.py tests/test_agent_analysis*.py tests/test_analysis_integrity.py tests/test_analysis_rendering.py tests/test_analysis_artifacts.py
uv run pytest -q tests/test_api_ask.py tests/test_api_analysis.py tests/test_analysis_e2e.py tests/test_analysis_business_gating.py tests/test_impact*.py tests/test_business_impact*.py
uv run pytest -q tests/test_analysis_workflow_observability.py tests/test_agent_analysis_evaluation.py tests/test_analysis_policy.py tests/test_analysis_workflow_documentation.py
```

- [ ] Run current randomized/observational/advanced reliability coverage and business regressions:

```bash
uv run pytest -q tests/test_randomized*.py tests/test_cuped*.py tests/test_sequential*.py tests/test_bayesian*.py
uv run pytest -q tests/test_observational_reliability*.py tests/test_causal*.py tests/test_did*.py tests/test_propensity*.py tests/test_ipw*.py
uv run pytest -q tests/test_advanced*.py tests/test_dml*.py tests/test_hte*.py tests/test_econml*.py tests/test_dowhy*.py
uv run python -m packages.evals.cli statistical-baseline --json-output artifacts/issue108/reports/phase4/statistical_baseline.json --output artifacts/issue108/reports/phase4/statistical_baseline.md
```

  Run the existing optional job's locked environment commands as well if dependencies are available; the command with `--require-optional econml --require-optional dowhy` is required to claim actual optional-runtime success. Never call unavailable tests proof of installed-adapter conformance.
- [ ] Run lint, configured typing, lock/configuration checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv lock --check
uv run python -m packages.llm.prompt_registry_cli validate
uv run python -m packages.evals.run_prompt_experiment validate --experiment rag-answer-abstention-v1-v2
uv run python -m packages.observability.cli validate --provider all
```

  `uv run mypy` uses the existing configured `packages/experiments/analysis` scope. New orchestration code is inside that scope. Do not broaden type checking to unrelated legacy packages as incidental cleanup.
- [ ] Set the existing offline quality environment and validate it. No API keys should be present; do not print their values:

```bash
ASK_MODE=agent_workflow EMBEDDING_PROVIDER=fake LLM_PROVIDER=mock PROMPT_EXPERIMENTS_ENABLED=false RAGAS_JUDGE_LLM_PROVIDER=none RAGAS_JUDGE_EMBEDDING_PROVIDER=none DEEPEVAL_JUDGE_PROVIDER=none uv run python scripts/validate_ci_environment.py --no-database --output artifacts/issue108/ci_environment.json
```

  Use the same fake/mock/no-hosted-provider environment for following evaluation commands. Ensure observability uses no-op/dry-run behavior via existing configuration; no telemetry credentials or exports.
- [ ] Run the full offline pytest suite and existing agent evaluators:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run pytest -q --tb=short
uv run python -m packages.evals.run_agent --output artifacts/issue108/reports/agent_evaluation.md --json-output artifacts/issue108/reports/agent_evaluation.json
uv run python -m packages.evals.run_agent_e2e --output artifacts/issue108/reports/agent_e2e_evaluation.md --json-output artifacts/issue108/reports/agent_e2e_evaluation.json
```

  Record database-dependent skips separately. Inspect JSON pass/fail counts: existing evaluation CLIs may write reports without a failing process exit for failed cases. Exit zero alone is insufficient.
- [ ] Run existing Phase 3 diagnostic/quality commands and inspect their reports:

```bash
uv run python scripts/verify_phase3.py --offline-only --artifact-root artifacts/issue108/phase3-diagnostic --report-root artifacts/issue108/phase3-diagnostic-reports
```

  This runs prompt regression, factuality, prompt experiments, observability dry runs and focused reliability checks. It is explicitly non-closeout. For complete Phase 3 regression, use an isolated local test database and the repository's existing synthetic fixture workflow, then run:

```bash
uv run python scripts/verify_phase3.py --artifact-root artifacts/issue108/phase3-strict --report-root artifacts/issue108/phase3-strict-reports
```

  Strict verification runs migrations/fixture ingestion against the configured database: verify it is an isolated disposable test database first; never point it at user/production data. It runs the existing full AI quality gate and policy against fresh reports. If the prerequisite cannot be supplied within authorization/environment, report the blocker and do not claim completion. Do not relax central thresholds or cite `--warn-only` as passing verification.
- [ ] Run the statistical baseline with required optional dependencies in the existing optional environment and inspect explicit per-capability availability/conformance results. Record exact versions and all skips; optional absence is a valid default-workflow outcome, but cannot conceal missing optional CI coverage.
- [ ] Inspect `git diff --check`, complete diff and status. Specifically audit: LLM arithmetic; copied formulas/thresholds; automatic selection/substitution; unchecked caller identification; data retention/leakage; result mutation; invented business assumptions; missing gates; approval bypass; API/legacy regressions; observability failure leakage; unstructured evaluation checks.
- [ ] Obtain whole-branch code review using the approved execution method. Resolve in-scope findings with tests and repeat affected checks; broaden tests only after changes/failures warrant it.
- [ ] Report branch and issue link, changed files and architecture, dispatch support, state/agent/API changes, business gates, abstention/status semantics, prose/integrity safeguards, tracing/privacy, evaluation/policy/CI changes, all added tests and exact executed command results, compatibility, skipped prerequisites and limitations. No merge or branch-protection changes.

## Acceptance traceability

| Spec requirement | Owning tasks |
| --- | --- |
| Explicit selection, typed normalization, datasets and no invented inputs | 1–3, 7 |
| Supported methods and optional identity | 2–3 |
| Safe typed envelope and artifact provenance | 2–3, 6 |
| Minimal state changes and real deterministic workflow | 4, 7 |
| Business, risk, decision and human approval gates | 5 |
| Exact evidence/prose protection | 6–7 |
| API/legacy/fallback compatibility | 4, 7 |
| Safe isolated telemetry | 8 |
| Existing evaluation/policy integration | 9 |
| Existing CI and six documentation examples | 10 |
| Full regression, reliability and final audit | 11 |

## Review and execution handoff

Review this plan and the linked spec together. Recommended execution is **native**: the tasks share request/envelope/service interfaces, and implementing them in one session reduces interface drift; finish with an independent whole-branch review. **Subagent-driven** execution is also available, with a fresh implementer and reviewer per task at higher coordination/context cost. Implementation begins only after the user approves the documents and selects the execution approach.
