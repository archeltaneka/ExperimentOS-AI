# Uncertainty-aware business-impact scenarios

Date: 2026-09-18
Issue: https://github.com/archeltaneka/ExperimentOS-AI/issues/107
Branch: `107-uncertainty-aware-business-impact` (linked to issue #107)
Status: approved specification implemented and verified on the issue branch.

## Objective and boundary

Translate an eligible ExperimentOS treatment-effect result into a transparent,
bounded business-impact scenario using explicitly supplied operational inputs.
The live issue's objective, scope, acceptance criteria, tests, dependencies, and
exclusions are authoritative, together with the user's detailed requirements.

Keep four distinct layers: statistical/causal evidence, operational inputs,
business conversion and costs, and derived scenario values. No forecasting of
missing inputs, pricing optimization, allocation, FX, scalar ROI, automated
rollout recommendation, decision-agent invocation, or LLM/RAG inference belongs
in this service. A range is not a probability distribution.

## Repository findings and architectural choice

The repository already provides immutable, extra-forbidding `ContractModel`
contracts; structured metrics and direction; population definitions; provenance;
diagnostics; confidence and credible intervals; and several estimator-specific
result/status contracts. These are reused rather than replaced.

`analysis/business_impact.py` provides sourced scalar objects and a serializable
`BusinessImpactProjection`, but no computation service. Its mandatory baseline,
order value, and margin inputs do not suit every metric. Its population count
does not express the required unit, population, or time semantics; its result
cannot represent all required refusals. Keep these public contracts readable for
compatibility, document their legacy role, and do not treat them as eligible
effect sources or silently convert them into the new scenario contract.

The Phase 2 Business Impact Agent computes deterministic descriptive lift through
typed tools and creates template summaries. It also carries source-reported
annualized values and parses annualized text, defaulting absent currency to USD.
It is not a causal business-impact calculation service. Remove that currency
inference and clearly label descriptive lift and reported figures as such.
Preserve compatible legacy fields without representing them as new computed
scenarios. No automatic bridge from retrieval or those fields into the new
service is allowed. General decision/workflow redesign is outside this issue.

Implement a focused `packages/experiments/analysis/impact/` package:

- `inputs.py`: composable sourced inputs, ranges, exposure, conversion, and costs.
- `units.py`: restrained dimensional and temporal semantics.
- `sources.py` (split by estimator family if needed): owned-result adapters.
- `validation.py`: source eligibility and cross-input compatibility checks.
- `arithmetic.py`: pure deterministic bounded operations and formulas.
- `results.py`: owned scenario, refusal, uncertainty, and derivation contracts.
- `service.py`: source adaptation, validation, calculation, and result assembly.
- `__init__.py`: deliberately bounded public exports.

Extend analysis exports/serialization following existing conventions. Add Phase 4
usage documentation and focused tests. The service requires no estimator refit,
database, network, optional causal-library import, or live model call.

Alternatives considered: extending the Phase 2 retrieval agent would entangle
calculation with legacy evidence/confidence semantics; extending the old
projection model in place would retain inappropriate mandatory inputs and risk
breaking readers. A separate service with shared repository primitives is the
approved approach.

## Source boundary and supported capabilities

The public calculation accepts an existing owned result, not an effect float or
a caller-authored normalized effect summary. Adapters derive a compact immutable
effect view, preserving result identity/fingerprint, estimator and adapter
identity/version, estimand, target population, outcome, direction, scale, point
estimate, interval kind/level/method, native statuses, assumptions, limitations,
diagnostics, warnings, and provenance. Diagnostic records remain typed and
retain their source scope. Do not copy row-level IPW weights, memberships,
nuisance predictions, or fitted objects into scenario output or telemetry.

Revalidate supplied models at the boundary so unchecked copies cannot bypass
contract validation. Supplement structural validation with existing applicable
quality checks and semantic consistency checks; a `completed` label alone is
not sufficient evidence. Identification checks consume owned declarations and
results, without re-estimating treatment effects.

| Source | Handling |
| --- | --- |
| Baseline randomized | Absolute effect and its CI; require source request context or explicitly provenance-backed missing semantic bindings. |
| CUPED | Adjusted effect/CI; preserve CUPED identity, retention, parent diagnostics, and precision status. Never silently substitute unadjusted estimates. |
| Bayesian A/B | Posterior effect and credible interval, preserving prior and interval semantics. |
| DiD | Difference-in-differences effect and clustered CI; preserve treated target and assumptions, including pretrend limitations. |
| IPW ATE/ATT | Effect and CI with declared target, overlap/balance evidence, sensitivity flags, and conditional causal status. |
| Repository DML | Effect and CI with overlap, assumptions, and conditional interpretation. |
| EconML average effect | Owned advanced result, inference, adapter provenance, and existing advanced quality checks. |
| Repository/EconML HTE | Explicit subgroup selection from a complete owned parent result; subgroup inference, support, overlap, and applicable quality checks. |
| Sequential | Explicit refusal: ordinary look-level CIs are contextual, not sequentially adjusted effect intervals. Do not unwrap a sequential result as fixed-horizon evidence. |
| DoWhy estimation | Explicit refusal: current adapter disables interval estimation. Refuter outputs cannot substitute for uncertainty. |
| Identification or propensity only | Explicit refusal: neither provides a treatment-effect estimate. |
| Legacy descriptive/associational findings | Explicit refusal as causal impact evidence. |

Adapters never infer missing units, direction, population, or observed period
from metric names. A sourced binding can supply absent semantic metadata but
cannot override conflicting source metadata, effect values, statuses, or
uncertainty. Source request/estimand units determine compatibility.

Relative effects require an interval on the selected relative scale. Do not pair
the randomized `relative_effect` point with its absolute CI. Risk ratios, if
encountered in an eligible owned source, differ from relative lift: the explicit
transformation is `relative_lift = risk_ratio - 1`, including both endpoints.
Unsupported scales such as log odds abstain; this issue adds no estimator.

## Eligibility and status policy

Reuse `AnalysisStatus.COMPLETED`, `INCONCLUSIVE`, and `ABSTAINED`, and retain
`ConclusionType.PROJECTION` for calculable outputs. Do not introduce a second
causal-confidence or product-decision taxonomy.

- `COMPLETED`: eligible evidence and compatible measured inputs produce a
  scenario without additional conditional qualifications. This denotes a
  supported calculation, not certain gain or a rollout recommendation.
- `INCONCLUSIVE`: a calculable scenario remains conditional on declared business
  assumptions, permissible source warnings, or conditional causal interpretation.
  All observational causal scenarios preserve their declared causal assumptions.
- `ABSTAINED`: source failed, invalid, unsupported, abstained, advisory-only as
  causal evidence, insufficient, or lacks valid inference; required inputs are
  missing/incompatible; or a relevant safety check blocks computation.

Distinguish an otherwise valid result with advisory warnings from advisory-only
causal evidence. Preserve warnings in the former and abstain in the latter.
Insufficient-source `inconclusive` results do not become calculable merely by
mapping their status string. Assess each family's actual status semantics.
Non-significance or an interval crossing zero does not itself invalidate a
completed statistical estimate or justify hiding its numeric scenario.

Fatal/global safety diagnostics block. Failed error-severity diagnostics block
unless an existing source-specific policy explicitly establishes a compatible
nonblocking interpretation; no generic suppression of errors. Preserve original
diagnostics regardless of disposition. CUPED no-improvement/degraded-precision
statuses are evaluated through the adjusted result and retained as qualifications.

The service normalizes missing/malformed request fields and compatibility errors
into structured refusal diagnostics with input paths and an abstention reason;
it does not manufacture default business values. Strict leaf constructors can
still raise Pydantic validation errors when used directly. Refusal outputs have
no gross/net numeric estimates or partial totals presented as valid scenarios.

## Operational input contracts

Use fixed-value or bounded-range objects. A range has ordered finite endpoints
and an optional explicitly declared central value within its bounds. Never use
a midpoint as an unstated central assumption. Zero population/exposure is valid;
negative population, nonfinite values, and rates outside `[0, 1]` are invalid.

Every non-statistical input has a stable input reference and structured evidence:
user-supplied or repository-evidence origin, measured or assumed status, existing
provenance records, and source version/timestamp where supplied. These are
separate axes: repository origin does not imply measured or certain. A repository
input must explicitly reference the evidence record and field supporting it.
Retrieved prose, external references, or configuration defaults alone are not
automatic sources of business quantities.

Composable objects cover:

- Population: quantity, entity unit, population definition, total/per-period
  basis, eligible/already-exposed meaning, horizon, and provenance.
- Exposure: adoption/exposure/rollout meaning, fraction or range, horizon, and
  provenance. No implicit full rollout. Already-exposed population cannot have
  another exposure multiplier applied; any supplied declaration must explicitly
  agree with that basis.
- Horizon: duration or calendar-period convention, plus source observed period
  and observed/extrapolated classification. Missing observed time semantics
  require an explicit evidence-backed binding or abstention.
- Baseline event rate: explicit event/entity semantics and `[0, 1]` range for
  relative binary calculations. Absolute binary effects do not require it.
- Exposure conversion: sourced units such as orders/user when the outcome unit
  and supplied population differ. No executable expression strings.
- Monetary conversion: currency per specified incremental outcome, benefit
  meaning (for example revenue or contribution), and explicit added/avoided
  outcome orientation. No default conversion from metric direction to money.
- Persistence: explicit user assumption that the effect remains stable over
  the extrapolated horizon, separately from population/exposure assumptions.
- Costs: amount/range, currency, unit/basis, horizon, and evidence for every item.

Semantic declarations and numeric quantities stay together; a bare population
number or arbitrary `source_id` without a declared origin/binding is insufficient.

## Dimensional and horizon rules

Extend `MetricUnit` through bounded composition with entity numerator/denominator
and temporal basis rather than interpreting display symbols. Support users,
sessions, orders, conversions, events, monetary outcomes with explicit currency,
and measured continuous outcomes such as duration. Preserve metric identity for
continuous outcome units so unrelated measures cannot be substituted.

Require effect denominator compatibility with exposed units, and conversion
denominator compatibility with the resulting outcome. Normalize declared unit
scales, including percentage points, using existing conversion multipliers.
Do not treat a count of orders as a count of users or infer a conversion.

Population totals are used once for their declared horizon. Per-period volumes
can scale only under an explicit compatible repetition convention. Days and
calendar months are distinct; one year and twelve repeated monthly populations
are not interchangeable without a declaration. A declared year total cannot be
multiplied again by twelve. Record every normalization factor and its source.
Extrapolation requires explicit effect persistence and any assumptions about
repeated population opportunities; repeated exposure to the same individual
must not imply additive outcomes without such semantics.

Fixed implementation cost is charged once per scenario. Recurring fixed cost
uses its declared occurrence basis. Per-exposure/event costs use the compatible
derived quantity for the same horizon. Reject ambiguous prorating, misaligned
horizons, or cross-currency arithmetic. No locale-based currency or FX.

## Formulas and uncertainty decomposition

Let `N` be eligible population aligned to the horizon, `r` exposure fraction,
`e` effect, `b` baseline binary event rate, and `v` declared value per outcome.
Explicit exposure-unit conversions, where supplied, enter as sourced factors.

- Absolute binary: `Q = N * r * e`.
- Relative binary: `Q = N * r * b * e`.
- Continuous per-unit/count difference: `Q = N * r * e` in compatible units.
- Monetary conversion: `G = Q * v`, with the declared added/avoided orientation.
- Direct monetary outcome: aggregate in the source currency when its per-unit
  semantics match; do not add another monetary conversion by default.
- Net: `G - declared_costs`, preserving shared quantities in benefit and costs.

Raw incremental outcome retains statistical sign. Improvement direction is
reported separately. An explicit prevented-event conversion can turn fewer
cancellations into positive retained contribution; negative latency remains
non-monetary without a supplied compatible monetary conversion.

Each calculable quantity exposes separately:

1. Central calculation, only if every necessary input has an explicit central
   or fixed value. It is a plug-in calculation, not an expected-value claim.
2. Statistical-only transformed interval, holding business inputs at their
   explicit central/fixed values; absent with a reason when these are unavailable.
3. Business-input-only band, holding the effect at its source point estimate.
4. Combined bounded scenario envelope using effect interval and input ranges.

Preserve source CI/credible interval type and level. Combined/business bands
have no invented probability or confidence level. Statistical-only intervals
remain conditional on fixed business assumptions. Do not describe scenario
endpoints as best/worst cases or invent distributions/correlation assumptions.

Use deterministic endpoint interval arithmetic with sign-aware multiplication
and subtraction. Preserve shared input identity before net bounding; for example
per-incremental-event cost uses the same `Q` as gross monetary conversion, so
evaluate `Q * (v - cost_per_event)` rather than subtracting unrelated Q estimates.
Evaluate supported formulas over shared primitive bounds or an algebraically
equivalent safe factorization. Any conservative over-enclosure must be labeled
as such, never claimed to be a tight attainable interval. Refuse nonfinite
arithmetic. No simulation is needed.

Costs support fixed implementation, recurring fixed, per-exposure, and signed
incremental-event variable cost under explicitly declared semantics. A negative
event change can reduce an incremental variable cost; it cannot silently create
a negative fixed expense. Nonnegative cost rates/amounts are required. Avoided
cost as the benefit requires an explicit conversion rather than negative cost
inputs with ambiguous meaning.

Gross outcome is independently supported without money. Missing conversion
abstains when monetary output was requested; outcome-only requests do not need a
conversion. Gross monetary impact does not require a cost declaration. Net
requests require an explicit complete declared-cost set, including a sourced
zero-cost declaration if applicable. Omitted costs never mean zero. Label net
as net of declared costs, not total business profitability.

## HTE and target population safety

Require one subgroup ID selected from an owned HTE parent, matching subgroup
definition and explicitly supplied subgroup population. Validate parent and
selected subgroup status, support thresholds, overlap, uncertainty, identification,
pre-specification, and existing quality findings. Preserve all parent/subgroup
diagnostics; distinguish global and selected-subgroup blockers from diagnostics
scoped exclusively to other groups. Missing selected subgroup overlap abstains.

ATT and DiD ATT inputs must refer to the treated target; a full-population rollout
cannot be substituted. No transport to a different population is inferred.
Population compatibility uses structured definitions/bindings, not label matching.
No automatic summation or portfolio aggregation is exposed in this version.
Thus overlapping groups cannot be double-counted by this service.

## Result and derivation contract

Return analysis/scenario identity, original source reference and estimator,
estimand/native status, source diagnostics and limitations, metric and direction,
source effect scale and uncertainty, supplied business inputs and provenance,
population/exposure/horizon, conversions, currency, declared costs, requested
output scope, output quantities and bands, derivations, warnings, status, and
abstention reason where applicable.

Each derivation records field identity, versioned formula/method ID, ordered input
references, units, horizon, and result. The result distinguishes measured values,
causal estimates, user assumptions, repository evidence, and derived values as
structured categories. Do not flatten provenance into prose or place scenario
output in a `MeasuredValue` without its derived classification.

Serialize deterministically and round-trip through owned contracts. Reporting
uses the same serialized records, displays intervals crossing zero prominently,
and never describes the central number alone as expected gain. Standard
observability, if emitted, contains bounded status/code/count metadata rather
than operational amounts, source documents, or row-level data.

## Verification and acceptance mapping

Hand fixture: absolute effect `0.02`, CI `[0.01, 0.03]`, eligible population
`100000 users/month`, explicit exposure `0.5`, compatible one-month horizon.
Exposed population is `50000`; incremental conversions central `1000`, interval
`[500, 1500]`. At explicit `USD 10/conversion` contribution, gross is `USD 10000`,
interval `[5000, 15000]`. With explicit complete fixed cost `USD 1000` for the
same scenario, net of declared costs is `USD 9000`, interval `[4000, 14000]`.

Sign/range fixture: effect `[-0.01, 0.03]`, population `[90000, 110000]`, exposure
`[0.4, 0.6]`, value `[10, 12] USD/event`. Combined event bounds are `[-660, 1980]`;
combined gross monetary bounds are `[-7920, 23760]`. Central values are not
invented for these business ranges.

Tests cover:

- Each accepted source family and native status mapping; estimator identity and
  diagnostics survive, including CUPED degradation and conditional causal results.
- Sequential/DoWhy unsupported uncertainty, identification/propensity non-effects,
  malformed/failed/abstained/insufficient sources, and quality blockers.
- Binary absolute and relative calculations, relative baseline and matching
  uncertainty requirements, continuous/count and direct-money unit semantics.
- Explicit semantic bindings, missing provenance, source conflicts, malformed
  ranges, nonfinite inputs/results, rate boundaries, and zero exposure/population.
- Negative effects, zero-crossing intervals, avoided events, lower-is-better
  non-monetary metrics, mixed-sign interval products, and shared cost dependencies.
- Fixed versus recurring costs, exposure/event costs, complete zero-cost
  declaration, gross-only output, absent conversion, and currency mismatch.
- Multiple compatible horizons, incompatible calendar/duration bases, persistence
  refusal, annual population counted once, and implementation cost charged once.
- Valid HTE subgroup, sparse/invalid subgroup, missing/severe overlap, population
  mismatch, ATT target mismatch, and no automatic subgroup aggregation.
- Structured provenance/derivation references, separate uncertainty bands,
  deterministic repeats, serialization round trips, and no recommendation fields.
- Phase 2 compatibility and removal of missing-currency inference; reported
  historical figures and descriptive lift are not promoted to computed scenarios.

Run focused impact tests and affected source/serialization/legacy regression
tests, then the issue-required `uv run ruff check .`. Run appropriate typing
checks for the new strict analysis contracts. Offline fixtures must not require
database/network/live LLM or optional EconML/DoWhy installation to test consuming
their owned results. Existing advanced conformance remains the source of adapter
quality policy; business arithmetic cannot upgrade its verdicts.

## Review record

The user approved the conversational architecture and this written specification
on 2026-09-18. The implementation plan is recorded in
`docs/superpowers/plans/2026-09-18-business-impact.md`. Review strengthened the
repository-evidence boundary with resolved structured records, retained subgroup
diagnostic scope, and distinguished effect-independent inputs from statistical
intervals. No new estimator, forecast, or decision capability was introduced.
