# Business-impact scenarios

Issue #107 adds `BusinessImpactService` under `packages.experiments.analysis.impact`.
It transforms an existing owned treatment-effect result using explicit sourced
operational inputs. It does not forecast inputs, fit an estimator, call retrieval
or an LLM, convert currencies, compute ROI, or recommend rollout.

## Evidence boundary

Four layers remain separate in JSON and `render_scenario(result)`:

1. `source`: estimator, estimand, native status, metric/direction, target population,
   effect scale, uncertainty and retained diagnostics/assumptions/provenance.
2. `inputs`: declared operational quantities and their provenance.
3. `inputs.conversion` and `inputs.costs`: explicit business valuation and expenses.
4. Derived quantities and `derivations`: formula, input references, units, horizon,
   central plug-in value where supplied, and separately labeled uncertainty bands.

`AnalysisStatus.COMPLETED` means a supported scenario calculation, never certainty
of gain. `INCONCLUSIVE` retains conditional source evidence, source warnings and
user assumptions. `ABSTAINED` suppresses all numeric impact and provides structured
reasons. A completed effect with a CI crossing zero remains calculable; its band
must display both signs. Invalid/failed/insufficient/advisory-only causal evidence
cannot become conclusive through business arithmetic.

Supported sources are owned fixed-horizon randomized, CUPED adjusted, Bayesian,
DiD, IPW ATE/ATT, repository DML, EconML average-effect, and selected supported HTE
subgroup results. Adapters retain their original identities. Conditional causal
interpretation remains conditional. Identification and propensity results alone
are not effects. Sequential results currently have no sequentially adjusted effect
interval, and the DoWhy adapter currently supplies no effect interval: both refuse.
No external library objects or effect floats are accepted.

The current source estimators return absolute differences, not valid relative-effect
intervals. A relative-lift point paired with an absolute CI is rejected. The bounded
formula layer represents relative binary effects only with an explicit baseline
and uncertainty on the relative scale; it does not manufacture a new estimator.

## Explicit inputs

Every sourced input has an `InputEvidence` with independent `origin` and `status`
axes: `user_supplied` or `repository_evidence`, and `measured` or `assumed`.
User supply requires a `USER_SUPPLIED` provenance record. Repository supply requires
an explicit `source_id:field` reference and a matching `RepositoryInputRecord` in
`request.repository_evidence`. That record contains the input's exact JSON value
and semantic fields (excluding its outer `evidence`), status and provenance.
The service resolves and compares those records offline; it never searches prose
or supplies a missing field. The upstream repository evidence boundary owns record
authenticity. A pointer alone, retrieved prose, or a configuration default does not
qualify as a measured business input.

`InputRange` has lower/upper bounds and an optional explicit central value.
`InputRange.fixed(value)` supplies all three. A range without a central value
produces no midpoint or expected-value claim.

Population has an entity, structured population definition, full/treated/conditioned
target, total/per-period basis, time basis, and eligible/already-exposed designation.
Exposure has a meaning and fraction in `[0,1]`; it is never implicitly 100%.
Already-exposed population requires an explicit identity exposure declaration,
not another rollout multiplier. Population and source targets must agree. Entity
conversion, such as orders per user, must be explicitly supplied and sourced.

The metric binding connects the business entity to the source analysis unit and
metric. Binary/count effects require an explicit event entity. Unit compatibility
uses dimensions, scale, currency, metric and entity semantics, never display labels.
Continuous unit values remain in the declared source scale. Absolute probability
points normalize using the source unit multiplier before producing event counts.

## Time and costs

`TimeHorizon` pairs an actual timezone-aware period with a `TimeBasis`. Calendar
months/quarters/years use calendar arithmetic (end-of-month clamping); days use
elapsed calendar-day offsets. Thirty days do not equal one month. The declared
basis must reproduce the supplied period endpoint.

A population total already covering the horizon is multiplied once. Scaling a
per-period volume requires `PopulationRepetition`, with explicit compatible source
and target periods, count, statement and provenance. The count must match exact
calendar subdivisions or exact day subdivisions; there is no day/month exchange.
A longer or later scenario requires a user-supplied `PersistenceAssumption` covering
its full period. Missing source observation periods need an explicit measured
period binding; the persistence assumption cannot establish the observed period.

All monetary inputs declare currency; no FX is performed. Gross outcome can remain
nonmonetary. `output='outcome'`, `'gross'`, or `'net'` controls returned quantities.
Gross-only needs no costs. Net requires an explicit complete `CostDeclaration`;
an empty, sourced complete declaration means explicitly zero declared cost.
Missing cost declaration never means zero. Net is net of declared costs, not a
claim of total business profitability.

Costs support implementation (once), recurring fixed (exact calendar occurrences),
per-exposure, and per-incremental-outcome bases. Rates/amounts are nonnegative;
per-incremental-outcome costs follow the signed outcome change, so fewer events can
reduce variable cost. Fixed expenses are not made negative by a negative effect.
All costs must share gross currency and compatible units/horizon.

A monetary conversion states whether value attaches to added or avoided outcomes.
For example a negative cancellation effect with an avoided-event value can produce
positive retained contribution. Lower latency is never implicitly monetary.

## Arithmetic and uncertainty

Let `A` be eligible exposures after declared population repetition and any unit
conversion. Absolute binary/continuous differences yield `Q=A*effect`; relative
binary lift requires `Q=A*baseline_rate*relative_effect`. Monetary value is
`G=Q*signed_value_per_outcome`.

Each output has a central plug-in value only where all needed central inputs are
explicit, a source-type-preserving statistical interval conditional on fixed
business values, a business-input band at the point effect, and a combined scenario
envelope. Business and combined bands have no probability distribution or invented
confidence level. Outputs independent of the effect, such as exposure counts and
fixed setup costs, explicitly have no statistical interval.

Interval operations consider all endpoint signs. Net arithmetic preserves shared
quantities: `A * (effect * (value - per_event_cost) - per_exposure_cost) - fixed`.
The binary relative/scale factors enter the effect term when applicable. This
avoids subtracting independently varied copies of the same outcome. There is no
simulation, random seed, probability assigned to input ranges, or midpoint default.

HTE scenarios select one subgroup with valid support, overlap and uncertainty,
and explicitly matching subgroup rule/population. ATT requires the treated target.
No multi-group summation is provided, so overlapping segments cannot be combined
accidentally by this service.

## Example

Given an existing `RandomizedAnalysisResult` named `source_result` for a binary
metric over July 2026, the following constructs a declared scenario. It deliberately
supplies population, exposure, contribution, setup cost, currency and entity binding
instead of taking them from the experimental sample size or metric name.

```python
from packages.experiments.analysis.impact import (
    BusinessImpactService, InputRange, render_scenario,
)

assert source_result.analysis_request is not None
analysis = source_result.analysis_request
fixed = lambda value: InputRange.fixed(value).model_dump(mode="json")
evidence = {
    "origin": "user_supplied", "status": "assumed",
    "provenance": [{"source_type": "user_supplied", "source_id": "scenario-owner-v1"}],
}
month = {"count": 1, "unit": "months"}
count = {"dimension": "count", "value_scale": "raw", "symbol": "events",
         "scale_to_base_unit": 1.0}
request = {
    "request_id": "july-contribution", "output": "net",
    "horizon": {"period": {"start": "2026-07-01T00:00:00Z",
                           "end": "2026-08-01T00:00:00Z"},
                "basis": month, "evidence": evidence},
    "population": {"value": fixed(100000), "entity": "users",
                   "definition": analysis.population.model_dump(mode="json"),
                   "target_kind": "full", "basis": "per_period", "time_basis": month,
                   "exposure_basis": "eligible", "evidence": evidence},
    "exposure": {"value": fixed(.5), "meaning": "rollout", "horizon": month,
                 "evidence": evidence},
    "binding": {"analysis_unit": analysis.unit_of_analysis.model_dump(mode="json"),
                "entity": "users", "metric_id": analysis.outcome.metric.metric_id,
                "outcome_unit": analysis.outcome.metric.unit.model_dump(mode="json"),
                "event": "conversions", "evidence": evidence},
    "conversion": {"value": fixed(10), "currency": "USD",
                   "metric_id": analysis.outcome.metric.metric_id,
                   "per_unit": count, "event": "conversions", "orientation": "added",
                   "meaning": "contribution", "horizon": month, "evidence": evidence},
    "costs": {"complete": True, "evidence": evidence, "items": [
        {"cost_id": "setup", "value": fixed(1000), "currency": "USD",
         "basis": "implementation", "horizon": month, "evidence": evidence},
    ]},
}
result = BusinessImpactService().analyze(source_result, request)
print(render_scenario(result))
```

For source effect `0.02` with CI `[0.01,0.03]`, this gives 50,000 exposed users,
1,000 central incremental conversions with bounds `[500,1500]`, gross contribution
USD `[5000,15000]`, and net of declared cost USD `[4000,14000]`. The assumptions
remain visible and the scenario is conditional.

For effect `[-.01,.03]`, population `[90000,110000]`, exposure `[.4,.6]`, and value
`[10,12]`, the combined gross envelope is USD `[-7920,23760]`. No central business
values were supplied, so none are invented.

## Compatibility and verification

The earlier `BusinessImpactProjection` remains readable for compatibility and
is not accepted as evidence for new scenarios. Phase 2 lift tools remain
descriptive. Source-reported annualized amounts remain explicitly reported,
not recomputed; a missing currency in prose no longer defaults to USD.

Focused checks: `pytest -q tests/test_impact_*.py tests/test_business_impact_agent.py
 tests/test_business_impact_contracts.py`, strict analysis mypy, and the issue-required
`uv run ruff check .`. Tests use deterministic local owned fixtures, with no
network, database, live LLM, or optional adapter fitting dependency.

## Verification record (2026-09-18)

- Focused impact and legacy tests: **143 passed**.
- Repository regression: **1,880 passed, 36 skipped, 8 deselected**; two existing
  dependency deprecation warnings.
- `uv run ruff check .`: passed.
- `.venv/bin/mypy packages/experiments/analysis`: passed (138 source files).
- Independent follow-up review confirmed all seven safety findings resolved.

Tests ran with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`. The broad run required sandbox-external local
API test sockets. PostgreSQL was unavailable on localhost:5433; the eight existing
database tests in `test_api_ask_db_integration.py`,
`test_ingestion_load_experiment.py`, and `test_retrieval_service.py` were explicitly
deselected after confirming that connection failure. No business-impact test
requires those services. The final report-only provenance/reference additions were
verified again with all four reporting tests and targeted typing/lint checks.
