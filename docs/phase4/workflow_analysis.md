# Product intelligence in the analysis workflow

The [complete causal quality gate](end_to_end_causal_quality_gates.md) verifies these
boundaries through `statistical-baseline`, including every implemented method,
optional adapters, business refusals, trace linkage, privacy, and backward compatibility.
Incompatible installed runtimes are failures, not optional absence.

Issue #108 exposes the existing validated Phase 4 services through `agent_workflow`.
The LLM does not calculate statistics. It can classify intent or explain evidence;
method selection is validated, business inputs are never invented, and structured
analysis is authoritative over generated prose. Positive effects or positive revenue
do not automatically trigger rollout.

## Architecture and ownership

```text
POST /ask: question + optional analysis + request-local datasets
  → typed normalization → existing deterministic planner
  → experiment-analysis node → AnalysisService → explicitly registered native analyzer
  → typed public evidence → gated business/risk/decision → existing human approval
  → protected executive summary → backward-compatible AskResponse
```

`packages/experiments/analysis/orchestration/` owns this boundary. The service validates
the declaration, resolves the requested dataset/version/experiment, invokes exactly
one registered method, projects safe typed evidence and preserves native refusal.
It does not search estimators, choose an effect, repair missing inputs or duplicate
statistical formulas. Native quality policy and estimator validation remain authoritative.
All estimators and AnalysisService remain independently callable without LangGraph.

An immutable ExperimentOS registry maps method IDs to owned handlers, capability,
design, estimands, required inputs, implementation version, optional dependency and
workflow eligibility. No third-party estimator class is exposed. The registry is
dispatch metadata, not automatic model selection.

## Supported methods

| Explicit method | Existing implementation | Main input contract |
| --- | --- | --- |
| `randomized_fixed_horizon` | Unadjusted randomized inference | execution, binding, dataset |
| `cuped` | CUPED adjustment | execution, dataset |
| `sequential` | Planned sequential analysis | plan and explicitly referenced looks |
| `bayesian_ab` | Bayesian A/B | execution, binding, dataset |
| `did` | Difference-in-differences | execution, dataset |
| `propensity_diagnostics` | Propensity diagnostics, not a causal effect | execution, dataset |
| `ipw_ate` / `ipw_att` | Explicit ATE / ATT weighting | analysis request, binding, configurations, dataset |
| `dml` | Repository DML | analysis request, binding, configuration, dataset |
| `hte` | Repository subgroup effects | analysis request, binding, configuration, dataset |
| `econml_dml` / `econml_hte` | Existing optional EconML adapters | native adapter configuration, analysis request, dataset |
| `dowhy` | Existing optional identification/refutation adapter | analysis request and native configuration |

See the discriminated wrappers in
[`requests.py`](../../packages/experiments/analysis/orchestration/requests.py)
for exact family-specific parameters. They reuse native Phase 4 contracts; graph
state does not duplicate estimator fields. Optional configurations and versions must
be explicitly valid for the requested adapter. Missing EconML/DoWhy is `unavailable`,
never an implicit switch to repository DML or another backend. Missing or ambiguous
method and unsupported method produce structured abstention. Malformed supported
requests produce `invalid`; no estimator runs after blocking validation.

## Requests, state and response compatibility

Existing `question`, `experiment_id`, `top_k` and response fields retain their meaning.
`AskRequest.analysis` and `analysis_datasets` are optional. The analysis declaration
contains `method`, `request_id`, `parameters` and optional `business`. Parameters carry
the native request and a dataset reference, not generated prose as method selection.
Request-local scalar tables require explicit columns, experiment ownership, version
and provenance. There is no new database table or arbitrary filesystem data loader.
Supplying datasets without an analysis declaration explicitly abstains in agent mode;
it never silently answers an ordinary question from different evidence.
DiD converts ISO timestamps only in its explicitly bound time columns; invalid/naive
timestamps remain invalid rather than being repaired.

Shared state adds only optional `analysis_request` and `analysis_result`. Old state
construction remains valid. Each structured workflow gets its own resolver/service;
raw rows live outside graph state. The experiment-analysis node is a thin service
consumer. Ordinary requests retain its legacy deterministic aggregate behavior.

`AskResponse.analysis` is an optional versioned `AnalysisResultEnvelope`: method,
capability, execution status, request/analysis IDs, timestamp, discriminated typed
`evidence`, fingerprint, diagnostics, abstention/failure, artifacts, integrity findings
and optional business evidence. Evidence families preserve applicable estimates,
uncertainty, estimands, assumptions, diagnostics, limitations and provenance, without
forcing every estimator into a p-value/CI schema. Raw rows, row-aligned weights,
propensity/CATE arrays, posterior samples, graphs and estimator objects are excluded.
Causal evidence includes declared outcome/units/population/time context, safe propensity
fit/ESS/trimming/capping summaries, IPW score-model provenance and aggregate DML/HTE
fold-fit provenance. Fold memberships and unit-level scores remain private.

`agent_workflow` remains the default. `legacy_rag` retains retrieval → versioned
`rag.answer` → generation → text citations; optional analysis inputs do not activate
Phase 4 in that mode. Ordinary workflow infrastructure fallback/error handling stays
separate from estimator abstention. Statistical methods are never substituted by
workflow fallback. Analysis infrastructure failures have safe error messages.

## Business, risk, decisions and abstention

Business execution requires eligible native upstream evidence and explicit sourced
inputs. The existing uncertainty-aware business estimator validates population,
exposure/adoption, conversion, rollout/persistence, costs where applicable, units and
horizon. Missing business inputs/provenance abstains before calculation. The result
separates statistical source estimate/interval, operational input evidence, monetary
conversion/cost assumptions, derived scenario intervals and provenance. These are
scenario assumptions, not a newly estimated causal effect. The statistical fingerprint
does not change when business evidence is attached.

Blocking/abstained analysis prevents business calculation and conclusive decision
evidence. Poor overlap, insufficient sample, sparse subgroups, invalid priors/plans
and unavailable adapters remain visible refusals, not generic internal errors.
Risk consumes native diagnostics without recalculating them or introducing new
thresholds. The structured decision path remains conservative (`needs_more_data` or
blocked), never an autonomous launch. Existing human approval requirements and
pending/approved/rejected/revision states are preserved.

Execution statuses (`completed`, `inconclusive`, `invalid`, `abstained`, `unavailable`,
`failed`) are distinct from quality statuses (`pass`, `warning`, `fail`, `skipped`).
Negative/non-significant effects, uncertain posteriors, no CUPED improvement and
intervals crossing zero are outcomes, not software-quality failures. Native blocking
diagnostics/advisories are surfaced unchanged, not recategorized by workflow thresholds.

## Authoritative evidence, presentation and artifact lifetime

The request-scoped service holds defensive copies of native and public results.
Downstream candidates run against copied state. A protected graph boundary accepts
only owned deterministic consumer updates; conflicting evidence or prose is rejected,
recorded as a safe integrity finding, and replaced by canonical rendering. The current
renderer includes labeled typed evidence JSON, business scenarios and artifact IDs;
it makes no new numerical claims. Rejected candidate text is not echoed into errors,
traces or responses. Structured results cannot be mutated by generated summaries.

Artifacts are request-lifetime references, not persisted downloadable objects. They
carry an analysis ID, kind, version, evidence fingerprint and provenance; the response
envelope supplies timestamp and typed result. Citation objects reference these artifacts
with explicit `artifact_id` and `schema_version` plus source-type/version/fingerprint
metadata. They do not put artifact IDs in database `document_id` fields or fake
document quotations. Dataset/business provenance remains distinct from text retrieval.
Clients needing durable artifacts must store the safe response themselves; no new
database persistence is introduced.

## Six runnable examples

All fixtures below live in `data/eval/workflow_analysis/` and contain an `ask_payload`.
The API requires the existing experiment record identified by `experiment_id`.
Offline tests use repository-local fixtures and bypass the database existence check
at the existing service/test boundary; no live LLM or embedding provider is required.

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

1. `randomized.json`: explicitly requested fixed-horizon inference, typed uncertainty
   and provenance, compared exactly with the native analyzer in tests.
2. `did.json`: observational DiD with declared design, time bindings and identification
   assumptions. No observational estimator is chosen by an LLM.
3. `business.json`: valid binary evidence plus explicit population, exposure, monetary
   conversion and costs. The fixture's net central scenario is 9,000 currency units;
   its interval and assumptions remain separate from statistical evidence. No launch.
4. `insufficient.json`: insufficient sample produces abstention and no fabricated statistic.
5. `optional_unavailable.json`: explicitly requested EconML remains EconML. The offline
   evaluation injects an unavailable owned dependency loader; `/ask` reports actual
   installed dependency availability instead of trusting that test flag.
6. `prose_conflict.json`: a test-only fake presenter attempts a conflicting claim.
   The candidate is rejected and the canonical result is retained. `presenter_candidate`
   belongs to the evaluation fixture, not a trusted `/ask` field.

Run these real graph/API-mapping cases without a server:

```bash
uv run pytest -q tests/test_analysis_e2e.py tests/test_analysis_integrity.py
uv run python -m packages.evals.run_agent --json-output artifacts/agent_evaluation.json
uv run python -m packages.evals.run_agent_e2e --json-output artifacts/agent_e2e_evaluation.json
```

For direct service use without LangGraph:

```python
import json
from pathlib import Path
from apps.api.ask_service import AskRequest
from packages.experiments.analysis.orchestration.datasets import RequestDatasetResolver
from packages.experiments.analysis.orchestration.requests import normalize_analysis_input
from packages.experiments.analysis.orchestration.service import AnalysisService

fixture = json.loads(Path("data/eval/workflow_analysis/randomized.json").read_text())
request = AskRequest.model_validate(fixture["ask_payload"])
intent = normalize_analysis_input(request.analysis, experiment_id=request.experiment_id)
service = AnalysisService(resolver=RequestDatasetResolver(request.analysis_datasets))
result = service.analyze(intent)
print(result.model_dump_json())
```

## Observability, evaluation and CI

Existing traces add analysis, validation, estimator and business-impact spans. Owned
allowlists export method/capability/status, diagnostic codes, safe identifiers and
duration, never rows, outcomes, covariates, graphs, arrays or candidate prose. Provider
hooks cannot capture raw graph state; providers receive only safe owned span export.
LangSmith/Phoenix/OTel transport or activation failures cannot break analysis or API
serialization. Provider-specific live callbacks are intentionally disabled on this path.

Existing agent and end-to-end evaluation now run real native randomized/DiD/business
fixtures plus refusal, negative-effect, missing-provenance and prose-conflict cases.
Structured `analysis_checks` compare native reference evidence, uncertainty,
assumptions, diagnostics, estimand, limitations, provenance, status, gating, adapter
identity, privacy and canonical presentation. Reports exclude raw fixture requests.
Existing factuality evaluation consumes structured artifact citations. No Markdown
parsing determines statistical correctness and no external judge is needed.

Central quality policy consumes `agent_evaluation.json` and `agent_e2e_evaluation.json`;
legacy Markdown readers remain available but missing required JSON does not fall back
to stale Markdown. Missing checks and violated integration invariants block; correctly
handled refusal passes. Existing Phase 4 quality thresholds are reused, never copied
into graph nodes or GitHub Actions. The current unit/offline/optional/AI-quality jobs
run the coverage; optional installed-adapter conformance remains a separate existing
job from default unavailable-path coverage. The offline smoke policy command is
diagnostic; the existing database-backed AI-quality gate is the blocking gate.
Required case identities must be unique and complete; applicable checks cannot be
skipped. Missing business outputs, optional refusal evidence, or changed public summary
and decision narratives block evaluation. Agent dataset versions fingerprint every
executed case, including analysis fixtures; absolute and relative default paths agree.
