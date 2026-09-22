# Product intelligence workflow integration — issue #108

Status: architecture approved in conversation; written design and implementation plan awaiting review. No product implementation is authorized by this document alone.

Issue: https://github.com/archeltaneka/ExperimentOS-AI/issues/108

Branch: `108-integrate-product-intelligence`, created through `gh issue develop 108 --name 108-integrate-product-intelligence --checkout`; GitHub issue linkage verified.

Inspected base: `cacb99c`, including merged uncertainty-aware business impact (#107) and advanced causal conformance (#106). Date: 2026-09-21.

## 1. Intent and constraints

Expose the validated Phase 4 statistical, causal, and business-impact stack through the existing ExperimentOS workflow and `/ask`. The supported path is an explicit request, deterministic routing, an independently callable analysis service, an existing analyzer, typed evidence, gated downstream processing, existing human approval where required, and a grounded response.

The issue body and the user's detailed implementation requirements are authoritative. The user approved the recommended architecture and explicitly requested both this spec and the implementation plan before product changes.

Project-wide constraints:

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

## 2. Current implementation and consequences

| Area | Observed implementation | Integration consequence |
| --- | --- | --- |
| Workflow | `packages/agents/workflow.py` builds a linear graph with eight nodes. Nodes in `nodes.py` skip according to `required_agents`. | Keep graph order and explicit node gates. |
| Planner | `plan_question` uses deterministic terms. `planner_node` rebuilds defaults. | Structured intent takes precedence; explicitly preserve analysis input during reconstruction. |
| Shared state | `AgentState`/`AgentStateUpdate` are TypedDicts. Input state is frozen Pydantic with a custom question-only public schema. State version is 10. | Add optional structured fields with compatible defaults; retain old graph input schema behavior for ordinary clients. |
| Question/context | `question`, `request`, `intent`, `required_agents`, `experiment_context`. | Keep these; do not encode the authoritative method in `planner_notes`. |
| Evidence | `retrieved_chunks`, `citations`, experiment metadata/metrics and legacy `experiment_analysis`. | Keep text evidence separate from analysis artifacts. |
| Downstream state | `business_impact`, `risk_assessment`, `risks`, `decision`, `human_approval_input`, `human_approval`, `executive_summary`. | Extend consumers, not estimator contracts inside every node. |
| Operational state | `tool_calls`, `metrics`, `errors`, `trace`, timestamps, run metadata. | Preserve reducers and tracing; expected abstentions do not become generic errors. |
| Experiment agent | Loads database experiment aggregates; computes descriptive differences/lifts; reads stored p-values and applies legacy significance interpretation. | Retain ordinary behavior. Phase 4 branch delegates exclusively to the new service. |
| Business agent | Uses deterministic lift tools and source-reported annualized values. | Retain legacy behavior. Never feed these source-reported amounts into a Phase 4 scenario as inferred inputs. |
| Decision/approval | Deterministic evidence checks, guardrail handling, risk checks, approval-required decisions; approval node records pending/approved/rejected/revision states. | Preserve legacy rules; add a conservative Phase 4 evidence branch without manufacturing legacy significance fields. |
| Summary | Deterministic state-based templates; no live LLM is currently needed. | Use deterministic Phase 4 rendering; defend against injected/future generated prose. |
| API | `AskRequest`: required question/experiment_id, optional top_k. `AskResponse`: existing text, citations, retrieval/LLM metrics, agent fields. | Optional nested analysis input/output; no required-field removals or changed defaults. |
| Mode/fallback | `ASK_MODE=legacy_rag` explicitly selects `QuestionAnsweringService`; workflow errors map to 502. | Preserve mode selection and infrastructure errors; no new automatic RAG or estimator fallback. |
| RAG | Retrieval → versioned `rag.answer` → generation → document citations. | Do not automatically run Phase 4 from this path. |
| Data | Analyzers accept `AnalysisTable`; `/ask` has no analysis dataset resolver. | Add a small request-scoped resolver; do not synthesize rows from stored aggregates. |
| Capabilities | Eligibility `MethodCapabilityRegistry.default()` recognizes contracts but declares no implementations. Concrete services declare their own support. | Add an execution registry tied to real owned services; do not equate enum membership with executability. |
| Evaluation | Agent evaluator executes injected agents; API E2E evaluator currently stubs returned workflow state. Policy consumes agent Markdown and statistical JSON. | Extend existing evaluators to run real analysis paths and add structured JSON policy ingestion for new checks. |
| Observability | Owned buffered spans isolate ordinary export failures; strict providers may raise. Services already emit safe aggregates. | Add an analysis-specific safe facade and allowlisted metadata; test provider failure at every boundary. |

Baseline before implementation: API, shared-state, and graph tests yielded **44 passed, 1 warning in 1.18s**. The initial sandbox run stalled and was interrupted; the bounded run outside the sandbox passed. The warning is the existing Starlette HTTPX deprecation. This is not a full reliability baseline.

## 3. Alternatives and selected architecture

1. **Selected: one owned analysis service consumed by existing nodes.** Smallest change to orchestration boundaries. Dispatch and result projection stay independently testable.
2. A separate Phase 4 subgraph would make internal stages visible but duplicate graph/state plumbing before needed.
3. Estimator-specific graph nodes would scatter method support and gating across LangGraph and couple independent estimators to workflow details.

```text
POST /ask or direct workflow caller
  ├─ optional request-scoped datasets → AnalysisDataResolver (outside graph)
  └─ typed method intent → planner → experiment_analysis
                                   → AnalysisService
                                     → explicit owned dispatch
                                     → existing validation/identification + analyzer
                                     → private native result + public typed envelope
                                   → shared-state analysis_result
                                   → business_impact (explicit gated request)
                                   → risk → decision → human_approval → summary
                                   → protected API serialization
```

One `AnalysisService` instance belongs to one workflow run. It holds private native evidence needed by business impact and the sealed public result. No raw rows or private result handles enter graph state, LangGraph configuration, trace metadata, or API results. Dependency injection supplies this instance to existing agent boundaries; never mutate a singleton service's dataset map per request.

## 4. Request normalization and data ownership

### 4.1 Public input

Add optional `AskRequest.analysis` and `AskRequest.analysis_datasets`. The outer analysis input has schema version `1`, request ID, requested method, data reference(s), method parameters, and optional business-impact input. JSON at the ingress is untrusted; normalize it once into a discriminated union of owned typed requests before planning. The JSON ingress allowance exists to turn unknown methods and malformed statistical parameters into safe structured refusals. It is not an untyped internal request or result contract.

Missing/blank/list-valued method selection is ambiguous; unknown strings are unsupported. An explicit method inconsistent with the nested study design, estimand, backend, or configuration is invalid. All three paths prohibit estimator invocation. Keep standard 422 behavior for malformed outer HTTP contracts, such as a missing question. Valid outer requests with invalid analysis content return a structured invalid/abstained analysis response and safe diagnostic paths, with no echoed rejected data.

`WorkflowAnalysisRequest` is the typed normalized union. `AnalysisRoutingRefusal` holds safe diagnostics and the explicitly supplied method identity, when valid as a scalar. Graph state holds this union, never the original JSON mapping. Method parameters reuse Phase 4 contracts and binding/configuration types; their fields are not repeated at the top level.

Each dataset reference names both its ID and expected version. The resolver returns an immutable snapshot and actual version; the service rejects a mismatch before dispatch. Normalized common fields are schema version, request ID, experiment ID, method, and typed business input/refusal. Native execution IDs must agree with the outer request ID. Method-specific fields are held under `parameters` at HTTP ingress and flattened only into the selected typed internal wrapper. The plan's Task 1 fixes the exact wrapper/type inventory.

Observational requests carry `ObservationalAnalysisRequest`, bindings, and method configuration. The service obtains identification itself through existing `CausalIdentificationService` or the estimator's existing identification gate. Do not trust caller-supplied successful `IdentificationResult` or propensity arrays from the public API. For IPW, compute identification and propensity through the declared owned pipeline, then form the existing `IPWExecutionRequest` internally.

### 4.2 Dataset transport

`AnalysisDatasetInput`: reference ID, experiment ID, version, explicit columns, scalar rows, and non-empty typed provenance. It is accepted only as an optional request-scoped input. Table shape and provenance are validated before numerical work. The service converts it into immutable `AnalysisTable` snapshots. Scalar values are JSON scalar types only; no arbitrary Python objects, URL fetching, filesystem paths, or table discovery.

`AnalysisDataResolver.resolve(reference, experiment_id)` returns an immutable `ResolvedAnalysisDataset(table, provenance, version)` or a typed resolution failure. The default runtime implementation resolves only the request's supplied dataset map. Other application callers may inject a resolver; this issue adds no persistent dataset catalog or database schema.

Reject duplicate IDs, ambiguous versions, mismatched experiment ownership, and absent required provenance. Same reference strings in different concurrent requests resolve independently. Data supplied without an analysis request is invalid, not implicitly analyzed. In `legacy_rag`, analysis extensions do not execute and are not forwarded to the QA service; legacy output remains unchanged.

The dataset map is constructed outside graph invocation and discarded when the request ends. Sequential requests use explicit references for each declared cumulative look; the service constructs existing `SequentialLookExecution` objects without persisting look rows. Identification-only DoWhy requests need no table unless existing requested operations require it.

## 5. AnalysisService and registry

Location: `packages/experiments/analysis/orchestration/`, re-export `AnalysisService` from the owned analysis package. This avoids collision with estimator-specific `service.py` modules and keeps strict type checking in its existing scope.

Public service operations:

```python
normalize_analysis_input(payload: JsonValue, *, experiment_id: str) -> AnalysisInput
AnalysisService.analyze(request: AnalysisInput) -> AnalysisResultEnvelope
AnalysisService.analyze_business(analysis_id: str) -> AnalysisResultEnvelope
AnalysisService.authoritative_result(analysis_id: str) -> AnalysisResultEnvelope
```

`AnalysisInput` is `WorkflowAnalysisRequest | AnalysisRoutingRefusal`. The service constructor takes a resolver, an optional explicit registry for tests, and an observability provider. Its request-scoped store holds validated native results and the parsed business request or a safe business-input refusal. `analyze_business` uses only these stored inputs; downstream nodes cannot replace the statistical source or supply invented business inputs.

The registry is immutable, rejects duplicate entries, and records method ID, capability, supported design/estimand, parameter model, required inputs, adapter factory, optional dependency, version, and workflow eligibility. Registry factories instantiate ExperimentOS services only. Imports of optional dependency packages remain lazy inside existing adapters.

| Public method ID | Existing owned implementation | Required semantics |
| --- | --- | --- |
| `randomized_fixed_horizon` | `RandomizedAnalysisService` | Explicit fixed-horizon design, execution request, table/binding, provenance. Maps only to existing fixed-horizon method. |
| `cuped` | `CupedAnalysisService` | Existing CUPED request, declared pre-treatment covariates and binding. |
| `sequential` | `SequentialAnalysisService` | Registered plan, fingerprint, complete declared look history. Monitoring output is not a stopping action. |
| `bayesian_ab` | `BayesianAnalysisService` | Explicit supported likelihood/prior configuration and provenance. |
| `did` | `DifferenceInDifferencesService` | Existing two-group/two-period ATT scope, identification declarations and binding. |
| `propensity_diagnostics` | `DeterministicLogisticPropensityEstimator` | Identification plus explicit propensity binding/configuration; diagnostics only, no treatment-effect claim. |
| `ipw_ate`, `ipw_att` | `IPWTreatmentEffectEstimator` | Declared estimand matches method; owned identification → declared propensity model → IPW pipeline. |
| `dml` | `DoubleMachineLearningEstimator` | Existing repository partialling-out scope; explicit fold/seed configuration. |
| `hte` | `HeterogeneousEffectEstimator` | Existing prespecified modifier/subgroup scope, no subgroup search. |
| `econml_dml` | `EconMLDMLAdapter` | Existing supported adapter configuration; dependency absence remains explicit. |
| `econml_hte` | `EconMLHTEAdapter` | Existing supported subgroup adapter configuration and modifiers. |
| `dowhy` | `DoWhyAdapter` | Existing identification/estimation/refutation options, individually explicit in `DoWhyConfig`. |

The workflow IDs are stable aliases for exactly these owned implementations, not aliases between competing estimators. No workflow-level fallback option is introduced. Required missing dependencies yield unavailable evidence with the adapter's native reason and status preserved, never substitution. Capability-specific validation remains in existing services. The orchestration service rejects routing/binding errors before adapter dispatch; estimator-owned eligibility gates must still prevent numerical engines from running on invalid data.

Catch unexpected estimator exceptions at the service boundary and return a typed failed result with a safe error code/type, not exception text or data. Do not catch a returned abstention and recast it as failure. Missing provenance is never repaired with a fabricated dataset source. A real request artifact can document the refusal but cannot stand in for absent dataset provenance.

## 6. Public result envelope and artifacts

`AnalysisResultEnvelope` uses the existing frozen `ContractModel` conventions and schema version `1`. It contains:

- `analysis_id`, `request_id`, `method` (nullable only for ambiguous routing), `capability`;
- normalized execution `status`, plus native status inside the typed evidence;
- `evidence`: discriminated method-family evidence union, or absent on routing failure;
- routing/normalization diagnostics and typed abstention/failure information;
- `business_impact`: optional safe typed business result/refusal;
- `artifacts`: typed request/analysis/business source references and versions;
- `integrity_findings`: safe machine-readable invariant violations, separate from estimator quality.

Evidence families are randomized, sequential, Bayesian, causal effect, propensity diagnostics, heterogeneous effects, and DoWhy. Reuse existing estimate, interval, assumption, diagnostic, limitation, and provenance types. Keep inapplicable fields absent: identification-only output has no fabricated point estimate; subgroup results retain subgroup-level abstentions; sequential history retains monitoring semantics. Do not use `dict[str, object]` as the public evidence payload.

Create explicit typed projections from native results. Strip nested requests/graphs, row identifiers, fitted scores/weights, CATE arrays, posterior draws, fold memberships, and third-party objects. Preserve all applicable public inference and safety evidence exactly, including interval type/level, scales, assumption status, diagnostic severity/outcome, limitations, provenance, adapter state, and versions. Do not round authoritative values during projection. Rendering may format numbers but must label units correctly.

`AnalysisArtifactReference`: artifact ID, kind (`request`, `analysis`, `business_impact`, `dataset`, `evaluation`), version, optional supporting provenance, and result fingerprint where applicable. Only cite evaluation artifacts that actually exist. The response itself carries the referenced in-memory analysis evidence; no fake persistence URL. Analysis citations extend the existing loose citation structure with `source_type`, `artifact_id`, and `schema_version`, without fabricated quote, similarity, document ID, or chunk ID. Retain legacy citation shapes unchanged.

Use a stable canonical evidence fingerprint for integrity checks and an actual UTC creation timestamp following repository conventions. The fingerprint excludes timestamps and execution duration and never requires serializing raw rows. Full data-integrity fingerprints already produced by existing services retain their own meanings.

Keep normalized execution statuses (`completed`, `inconclusive`, `invalid`, `abstained`, `unavailable`, `failed`) separate from quality statuses (`pass`, `warning`, `fail`, `skipped`) and native estimator statuses. Unsupported/ambiguous routing is abstained with a diagnostic. Known missing optional dependency is unavailable; preserve any native abstention in evidence. Non-significance and negative effects remain valid outcomes.

## 7. State transitions, presentation, and gating

Add `analysis_request` and `analysis_result` as optional state/update fields. Defaults are absent/None; old TypedDict construction remains accepted. Extend `create_initial_state`, `AgentWorkflowService.run`, and input-schema handling with optional parameters without changing existing positional arguments. Increment state metadata version for the extended schema, while tests for legacy construction continue to pass.

For an explicit analysis request, deterministic planning adds experiment analysis and summary; business is scheduled only when requested (including business-intent questions with missing inputs, which yield a refusal). Risk/decision/approval follow existing requested intent. Retrieval is optional context and not a statistical prerequisite when explicit datasets are complete. Unsupported routing still reaches safe summary rendering; it never falls through to a successful legacy experiment analysis.

The experiment agent delegates to the run's service. Legacy `experiment_analysis` remains for ordinary questions; do not populate its significance dictionary by reverse-engineering Bayesian/sequential/causal evidence.

The business node has an explicit gate before service invocation. Invalid/abstained/unavailable/failed statistical analysis prevents calculation. A valid analysis plus malformed/missing business inputs produces a business-only abstention; the statistical result stays valid. Eligible native evidence passes through existing `impact.sources.adapt_source`, existing runtime quality checks, and `BusinessImpactService`. Sequential results and DoWhy estimates without owned effect intervals remain ineligible. HTE requires an explicit eligible subgroup. Missing population, exposure, conversion, costs for net output, alignment, persistence where needed, or provenance never receives a default. Business assumptions, statistical uncertainty, and derived scenario bands retain separate fields.

For Phase 4 decision intent, emit evidence and limitations with `needs_more_data`/human-review language unless the existing complete decision prerequisites are independently satisfied. Phase 4 alone does not supply rollout/guardrail/operational readiness evidence. Do not invent a new p-value-based decision policy. Preserve a required human approval flag on any decision-producing path; retain the existing approval node and all legacy approval behavior. A failed statistical prerequisite cannot produce a conclusive decision or subgroup recommendation.

Risk consumes existing diagnostic codes/severity and limitations; it adds no overlap or significance thresholds. Advisory evidence remains advisory. A business refusal cannot turn a valid statistical result into failed analysis.

Downstream agents receive defensive copies. A shared update guard validates proposed updates against the service's sealed result. Only the experiment node may publish its service result; only the business node may publish the service's business extension. No node may change underlying statistical evidence. Detect replacement, nested mutation, deleted uncertainty/provenance, changed method, and artifact mismatch; restore canonical evidence and record a blocking integrity finding. The API adapter repeats the canonical comparison before serialization, so an injected summary agent cannot bypass it. This protects supported component boundaries, not arbitrary malicious Python code with access to process memory.

Keep Phase 4 prose deterministic by default. A generated/injected candidate is publishable only if it conforms to the canonical structured rendering; otherwise replace the candidate with canonical text and record `analysis.prose_conflict`. A plain numeric allowlist is insufficient: a valid number could be assigned to the wrong quantity. Apply the guard to `answer`, executive-summary fields, and decision/risk/business narrative fields that could carry claims. Preserve structured input assumptions as attributed assumptions, not measured facts. Existing factuality evaluation consumes the same canonical evidence; it is not used as a statistical calculator.

## 8. API compatibility and failure behavior

Add optional `AskResponse.analysis` containing the public envelope. Artifacts are nested there and cited through existing `citations`. Do not echo `analysis_datasets`, raw parameter payloads, or native results. Existing answer, citations, retrieval metrics, LLM metrics, decision, summary, trace, and approval fields retain their meanings. Keep existing question/experiment validation and unknown-experiment 404 behavior.

Ordinary requests retain their current call signature to injected test doubles; pass new keywords only when analysis is present. Preserve `legacy_rag` QA calls and prompt metadata. Explicit analysis in legacy mode is not executed or automatically routed elsewhere; document this mode constraint. Infrastructure failures retain 502. Expected method/input/eligibility refusals are structured analysis responses, not 502. No estimator fallback is added.

At HTTP validation boundaries, exclude input values and exception context from errors for the newly introduced data/analysis fields; preserve ordinary field-location and error-type information. Never expose raw rows through a validation response or trace exception.

## 9. Observability and privacy

Extend existing owned spans with analysis orchestration, validation/identification, estimator dispatch, business impact, and serialization metadata where those stages execute. Retain existing graph trace order and metric compatibility. Allowed metadata: method, capability, normalized/native status, estimand, diagnostic/assumption codes, estimator/adapter versions, dependency availability, duration, artifact IDs, and aggregate counts already permitted by Phase 4.

Never serialize state/request/native result wholesale into telemetry. Raw rows, outcomes, covariates, treatment records, propensity/CATE arrays, posterior samples, raw graphs, and row-level business records are prohibited even when content tracing is enabled. Use allowlisting at emission and redaction as defense in depth. Safe errors contain code/type and fixed text.

Provider failure at root span creation, activation, child creation, metadata, config construction, finish, or export cannot change analysis/workflow/API results. Use a narrow non-throwing observability wrapper on this integration path, falling back to owned no-op spans. Do not change strict behavior of unrelated standalone observability commands. Test fake LangSmith/Phoenix/OTel/composite failures offline.

## 10. Evaluation, CI, and acceptance evidence

Extend existing `AgentWorkflowEvaluator` and `AgentE2EEvaluator` with optional analysis cases and structured expectations. Ordinary cases retain their current behavior. New E2E cases use real planner/graph/service/analyzers, injected local dataset resolvers, fake retrieval/embeddings when requested, and no live LLM. Compare direct analyzer evidence with service → state → API evidence using typed projections and exact preservation checks. Numerical golden/reference tests remain in Phase 4.

Extend existing JSON reports with per-case routing, execution, preservation, gating, provenance, prose, privacy, and adapter-identity findings. Add JSON policy readers for agent and agent E2E reports, keeping Markdown rendering for humans and legacy reader compatibility. Use existing centralized policy categories and severities; new integration-invariant counters belong in `config/evaluation/quality_policy.yaml`, never Actions YAML. Preserve native quality output without recomputing statistical thresholds.

Required regression matrix:

| Cases | Assertions |
| --- | --- |
| Fixed-horizon and DiD real E2E | Exact method/estimand/estimate/uncertainty/assumptions/diagnostics/limitations/provenance/status through state and response; DiD identification retained. |
| CUPED, sequential, Bayesian, propensity, IPW, DML, HTE, optional dispatch | Supported registry points to implemented service; explicit method/backend survives; unsupported configuration refuses. |
| Valid business scenario | Explicit sourced population/exposure/conversion/costs, aligned units/horizon; deterministic derivation; statistical evidence unchanged; no automatic recommendation. |
| Unsupported/ambiguous/conflicting/malformed request | No dispatch on routing rejection, no numerical engine after eligibility rejection, safe refusal. |
| Post-treatment adjustment, invalid prior/plan/graph | Existing blocking diagnostics retained; no downstream business computation. |
| Insufficient sample, poor overlap, sparse subgroup | Abstention reaches API; invalid subgroups do not gain recommendations. |
| Missing business provenance/inputs | Business abstains independently; no ROI or invented input. |
| Optional unavailable/incompatible | Explicit adapter identity and native diagnostic retained; no substitution or false success. |
| Conflicting/invented prose | Fake summaries alter effect/p-value/revenue/population or reuse a number for the wrong quantity; canonical output replaces them and preserves evidence. |
| State mutation | Nested mutation, replacement, removed interval/provenance, and artifact mismatch rejected. |
| Backward compatibility | Ordinary RAG, deterministic agent flow, legacy mode, approval states, 404/422/502, old serialization and test doubles. |
| Privacy/isolation | No prohibited data in API/errors/telemetry; provider failures isolated; concurrent requests cannot resolve one another's data. |
| Outcome versus quality | Negative/non-significant/cross-zero outcomes and advisory-only diagnostics do not become blocking software failures. |

Extend existing unit/offline/optional CI jobs. Retain the statistical-baseline command, randomized/observational reliability tests, advanced conformance, and Phase 3 commands. Strict Phase 3 closeout requires its existing local PostgreSQL/fixture prerequisites; `--offline-only` is a diagnostic and must never be described as equivalent strict closeout. Missing prerequisites must be reported, not hidden by changing thresholds, skipping required checks, or using `--warn-only` as proof of success.

## 11. Documentation examples to ship

`docs/phase4/workflow_analysis.md` will include runnable requests drawn from checked-in JSON fixtures under `data/eval/workflow_analysis/`, so full native contracts are validated rather than abbreviated into invalid examples.

1. `randomized.json`: question plus `analysis.method=randomized_fixed_horizon`, explicit native execution request/binding, one dataset reference and supplied dataset. Response cites analysis artifact and retains the frequentist interval.
2. `did.json`: `analysis.method=did`, full observational declarations, two-period binding and local panel rows. Response retains ATT, identification assumptions, cluster diagnostics, and uncertainty.
3. `business.json`: randomized evidence plus the existing typed business request with population, exposure, horizon, conversion, and net-output costs with provenance. Show statistical interval, operational assumptions, and derived scenario separately.
4. `insufficient.json`: fixed-horizon request with genuinely insufficient data. Response abstains with existing diagnostic; there is no point estimate or conclusive impact.
5. `optional_unavailable.json`: explicit `econml_dml` with valid declarations; fake unavailable runtime for the deterministic example. Response remains `econml_dml`, status unavailable, no repository-DML fallback.
6. `prose_conflict.json`: test-only candidate presentation claiming an effect of 9.5% against a structured 2.1% fixture, plus separate invented p-value/revenue/population variants. The candidate is injected through a fake presenter in tests, never accepted as authoritative API input. Output is canonical 2.1% evidence with an integrity finding. Real-analyzer E2E fixtures do not overwrite analyzer outputs to manufacture this illustrative value.

Explain direct service calls outside LangGraph; unsupported methods; structured citations and request-scoped lifetime; sequential/DoWhy business restrictions; human approval; mode/fallback distinctions; optional dependencies; observability; and execution versus quality statuses.

## 12. Approval and completion

The user explicitly authorized drafting both documents together, overriding the default intermediate spec-only writing pause. Review of these documents and selection of implementation execution method remain outstanding. Product code starts only after that review.

Implementation completion requires all required focused/full offline tests, Phase 4 reliability/conformance, lint, configured typing, configuration validation, and applicable Phase 3 quality commands to pass. Report exact commands and results, skips/prerequisites, compatibility evidence, final security/integrity diff review, and limitations. Do not claim the issue complete with outstanding required verification.
