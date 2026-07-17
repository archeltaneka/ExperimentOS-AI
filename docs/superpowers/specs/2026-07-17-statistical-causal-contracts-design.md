# Statistical and Causal Analysis Contracts Design

## Purpose

Issue #88 establishes the ExperimentOS-owned statistical and causal domain language for Phase 4
before any estimator, eligibility policy, workflow integration, or public API expansion is built.
The contracts must preserve statistical meaning across services, reports, persistence, evaluation,
observability, and quality-policy boundaries without exposing third-party result objects.

This design implements contracts only. It does not calculate descriptive statistics, treatment
effects, uncertainty, diagnostics, eligibility, or business impact.

## Approved Approach

Create a modular family of immutable Pydantic v2 models under
`packages/experiments/analysis/`. Pydantic is preferred over frozen dataclasses because these
contracts need cross-field validation, discriminated unions, JSON schemas, and validated
serialization round trips. A single consolidated request/result model is rejected because it would
conflate incompatible concepts and accumulate unrelated optional fields.

The new subpackage is a public internal ExperimentOS boundary. It does not re-export from
`packages.experiments` in this issue, so the existing top-level package contract remains unchanged.

## Non-Negotiable Boundaries

- Preserve the current `POST /ask` request and response schemas.
- Preserve `AgentState`, the existing Phase 2 agents, persistence models, ingestion, evaluation,
  and observability behavior.
- Do not add estimators, an estimator registry, estimator selection, or statistical calculations.
- Do not add database migrations or public API fields.
- Do not expose NumPy, pandas, SciPy, Statsmodels, scikit-learn, EconML, DoWhy, RAGAS, DeepEval,
  LangGraph, or provider-specific types through the contracts.
- Require explicit units, scales, population, treatment, control, outcome direction, estimand,
  uncertainty, status, and provenance where those concepts apply.
- Keep associative, causal, descriptive, and projected evidence structurally distinguishable.
- Keep numerical values machine-readable and finite; presentation strings are not values.
- Permit invalid study inputs to be represented when the next issue must assess eligibility, but
  reject unambiguous structural contradictions at construction time.

## Package Structure

The package has focused modules with one responsibility each:

- `base.py`: strict frozen base model, shared scalar aliases, and finite-number validation helpers.
- `metrics.py`: metric definitions, structured units, outcome direction, analysis units, and sample
  counts.
- `populations.py`: population, segment, and typed selection-criterion contracts.
- `study_designs.py`: treatment, control, allocation, time periods, clustering, covariates,
  pre-treatment metrics, and discriminated study designs.
- `estimands.py`: the supported estimand vocabulary and CATE conditioning.
- `provenance.py`: provenance, assumptions, diagnostics, warnings, and failures.
- `uncertainty.py`: explicit uncertainty measures and uncertainty bundles.
- `requests.py`: the composed analysis request.
- `estimates.py`: descriptive statistics and the four non-projection effect-estimate families.
- `results.py`: eligibility assessments and discriminated terminal analysis outcomes.
- `business_impact.py`: fully sourced business-impact inputs and projection outputs.
- `serialization.py`: canonical JSON and validated union round trips.
- `__init__.py`: deliberate public internal exports.

All models inherit from a local `ContractModel` configured with `frozen=True` and `extra="forbid"`.
Enums inherit from `StrEnum` and use stable lowercase values. Immutable sequences use tuples.

## Metrics, Units, and Samples

### Metric definitions

`MetricDefinition` contains a stable metric identifier, human-readable label, `MetricType`, and
`MetricUnit`. Supported metric types are:

- `continuous`
- `binary`
- `count`
- `proportion`
- `rate`
- `ratio`

`OutcomeMetric` composes a `MetricDefinition` with an explicit `OutcomeDirection` of `increase`,
`decrease`, or `no_preference`. It does not infer business desirability from the metric name.

### Structured units

`MetricUnit` requires all of the following:

- `dimension`: dimensionless, proportion, count, currency, duration, rate, ratio, or custom;
- `value_scale`: raw, proportion, percent, percentage point, basis point, or custom;
- `symbol`: a non-empty machine-readable symbol;
- `scale_to_base_unit`: a positive finite multiplier;
- `currency_code`: required only for currency dimensions;
- `custom_dimension_name`: required only for custom dimensions.

Currency codes are exactly three uppercase ASCII letters. Percentage-like scales are valid only
for proportion dimensions. Their conversion multipliers are standardized: proportion uses `1.0`,
percent and percentage point use `0.01`, and basis point uses `0.0001`. Raw and custom scales keep
an explicitly supplied positive finite multiplier. Currency metadata is forbidden on non-currency
units. These rules make `0.05`, `5%`, five percentage points, and 500 basis points impossible to
confuse silently. Product-specific units such as `orders/user-day` remain representable through an
explicit dimension, scale, and symbol rather than an ambiguous string.

### Analysis units and sample counts

`AnalysisUnit` is a stable identifier and label. Separate request fields represent the unit of
analysis, randomization unit, and clustering unit; none is inferred from another.

`SampleCounts` requires positive integer treatment and control counts, a positive total, and exact
equality between the total and the two arm counts. Fractional, Boolean, negative, zero-arm, and
inconsistent counts are rejected.

## Populations and Segments

`PopulationDefinition` and `SegmentDefinition` contain stable identifiers, labels, and tuples of
`SelectionCriterion`. A criterion contains an attribute, a typed comparison operator, and a scalar
or tuple of scalar values. Mapping-shaped free-form predicates are not used for core selection
logic.

An empty criterion tuple explicitly means the entire named population or segment. `CATE` requires
a non-empty conditioning segment definition; other estimands forbid one.

## Treatment, Control, and Study Design

`TreatmentDefinition` and `ControlDefinition` are separate models. Each requires a stable
identifier, non-empty label, explicit assignment value, and description. The composed request
rejects equal identifiers, labels, or assignment values.

`TimePeriod` contains timezone-aware start and end timestamps and requires `start < end`.

`ClusteringSpecification` is discriminated as either `NoClustering` or `Clustered`, with the latter
requiring an explicit clustering unit. Absence of clustering is therefore stated rather than
inferred from a missing field.

Study designs form a discriminated union:

### Randomized experiment

`RandomizedExperimentDesign` supports method identifiers for fixed-horizon A/B, CUPED, sequential
A/B, Bayesian A/B, and heterogeneous treatment-effect analysis. It requires:

- an experiment period;
- an explicit randomization unit;
- treatment and control allocation values strictly between zero and one;
- allocations whose sum is one within a small floating-point tolerance.

### Quasi-experimental study

`QuasiExperimentalDesign` initially supports Difference-in-Differences. It requires explicit
pre-treatment and post-treatment periods, with the pre-treatment period ending no later than the
post-treatment period starts.

### Observational study

`ObservationalStudyDesign` supports method identifiers for propensity-score analysis, weighting,
Double Machine Learning, and heterogeneous treatment-effect analysis. It requires an observation
period and does not imply randomized assignment.

Method identifiers communicate intended analysis structure only. They do not register, select, or
configure an estimator.

## Covariates and Pre-Treatment Metrics

`CovariateDefinition` composes a `MetricDefinition` with:

- timing: pre-treatment, at-treatment, post-treatment, time-varying, or unknown;
- role: adjustment, confounder, precision, effect modifier, CUPED, treatment indicator, or
  treatment proxy;
- relationship to treatment: none known, assignment-derived, proxy, or unknown;
- an explicit measurement period.

`PreTreatmentMetric` contains a metric definition and a measurement period that must end no later
than treatment begins for a randomized design when both periods are part of the same request.

Post-treatment covariates, unknown timing, treatment-derived fields, treatment proxies, and CUPED
fields with questionable timing remain representable. Their explicit attributes allow issue #89 to
return typed eligibility failures. This issue does not implement leakage, overlap, power, CUPED,
exchangeability, or method-suitability policy.

## Estimands

`EstimandDefinition` supports exactly:

- difference in means;
- difference in proportions;
- absolute lift;
- relative lift;
- average treatment effect;
- average treatment effect on the treated;
- conditional average treatment effect;
- intention-to-treat effect.

`CATE` requires a conditioning segment. Every other estimand forbids one. Compatibility between a
metric type, study design, and estimand is deferred to eligibility policy unless the combination is
structurally meaningless at the contract layer.

## Analysis Requests

`AnalysisRequest` carries `schema_version="1"` and requires:

- population and an optional target segment;
- treatment and control definitions;
- outcome metric;
- estimand;
- a discriminated study design;
- unit of analysis;
- explicit clustering specification;
- sample counts;
- either a requested confidence level or requested credible level;
- covariates and pre-treatment metrics as tuples that may be empty.

Requested confidence and credible levels are distinct discriminated models and require values
strictly between zero and one. The request does not accept a generic `level` without semantic type.

## Uncertainty

Every effect estimate and business-impact projection requires a non-empty `UncertaintyBundle`.
The bundle contains discriminated measures:

- `StandardError`: a finite value greater than or equal to zero;
- `ConfidenceInterval`: finite ordered bounds and a confidence level strictly between zero and one;
- `CredibleInterval`: finite ordered bounds and a credible level strictly between zero and one;
- `PosteriorProbability`: a probability from zero through one and a required event statement;
- `UncertaintyUnavailable`: a required reason.

`UncertaintyUnavailable` cannot coexist with a numerical uncertainty measure. Interval bounds are
validated for order, but the contract does not impose symmetry or calculate interval coverage.

## Evidence and Epistemic Distinctions

The six required conceptual categories are represented structurally:

1. `DescriptiveStatistic`
2. `AssociationalEstimate`
3. `RandomizedExperimentEstimate`
4. `QuasiExperimentalEstimate`
5. `ObservationalEstimate`
6. `BusinessImpactProjection`

`DescriptiveStatistic` identifies a sample mean, sample proportion, or sample count and never
carries a treatment-effect estimand.

Effect estimates compose an estimand, outcome, finite point value, unit, uncertainty, sample
counts, assumptions, diagnostics, warnings, and non-empty provenance. Every estimate also carries
an explicit analysis status restricted to `completed` or `inconclusive`.

`AssociationalEstimate` fixes its conclusion type to `association`. Randomized, quasi-experimental,
and observational estimates require an explicit conclusion type of `association` or
`causal_effect`; no causal default exists. A caller must therefore make a visible, validated choice
before representing a causal claim.

## Assumptions, Diagnostics, Warnings, Failures, and Provenance

`AssumptionAssessment` contains a stable code, statement, and status of supported, violated,
unassessed, or untestable.

`Diagnostic` contains a stable code, severity, outcome, message, optional typed observed value, and
optional typed threshold. Diagnostic severity and outcome are separate so a failed advisory check
does not silently become fatal.

`AnalysisWarning` contains a stable code, message, and affected scope. `AnalysisFailure` contains a
stable code, stage, message, and retryability.

`ProvenanceRecord` requires a source type and stable source identifier. Version, URI, and
observation timestamp are optional because not every repository source has those attributes.
Every effect estimate, descriptive statistic, and projection requires at least one provenance
record.

## Eligibility and Analysis Outcomes

One stable `AnalysisStatus` enum contains:

- eligible;
- eligible with warnings;
- ineligible;
- needs more data;
- completed;
- inconclusive;
- abstained;
- failed.

Models restrict which values they may contain:

- `EligibilityAssessment` accepts only the four eligibility states and carries diagnostics,
  warnings, and required-data descriptions.
- `CompletedAnalysisResult` accepts only `completed` and requires at least one completed finding.
- `InconclusiveAnalysisResult` accepts only `inconclusive` and requires at least one inconclusive
  numerical finding.
- `AbstainedAnalysisResult` accepts only `abstained`, requires a typed abstention reason and missing
  or invalid information, and has no estimate field.
- `FailedAnalysisResult` accepts only `failed`, requires one or more typed failures, and has no
  estimate field.

These form a discriminated `AnalysisOutcome` union. Result validators require child finding status
to match the parent result. Invalid, insufficient, abstained, and failed outcomes therefore cannot
contain fabricated values.

## Business-Impact Inputs and Projections

Business impact is a projection domain, not a causal-estimate synonym.

`BusinessImpactInputs` requires all of the following sourced values:

- eligible population;
- exposure frequency;
- baseline rate;
- average order value;
- contribution margin;
- rollout proportion;
- analysis horizon;
- currency.

Sourced count, quantity, proportion, money, currency, and time-period models each require a
non-empty provenance tuple. Missing inputs or missing provenance fail construction. A
`SourcedProportion` is canonical normalized data: its value is in `[0, 1]`, its unit dimension and
value scale are both proportion, and its multiplier is `1.0`. General `MetricUnit` and
`MeasuredValue` contracts may still represent percent, percentage-point, and basis-point values.
Safe structural validation enforces positive population, non-negative exposure frequency, finite
quantities, bounded baseline and rollout proportions, valid currency codes, and ordered horizons.
Zero exposure frequency remains representable. Contribution margin preserves its explicit unit
rather than assuming a percentage or currency amount.

`BusinessImpactProjection` carries `schema_version="1"` and requires:

- the complete input set;
- the complete source effect estimate;
- a projected incremental outcome composed from a measured value and its uncertainty bundle;
- a projected financial impact composed from a measured value and its uncertainty bundle, with an
  explicit currency unit;
- assumptions, diagnostics, warnings, provenance, and status.

The reusable `ProjectedValue` contract attaches one non-empty uncertainty bundle to exactly one
measured output. `BusinessImpactProjection` has no shared projection-level `uncertainty` field, so
the uncertainty for one output cannot be mistaken for the other. The projected financial value's
currency must match the sourced currency input. Because the complete source estimate is embedded,
an associative estimate remains visibly associative and cannot be promoted to a causal effect by
the projection wrapper. No projection calculation is implemented.

## Public Contract Documentation

Every public module and every exported enum, model, and runtime type contract in
`packages.experiments.analysis` has a concise useful docstring. Public type aliases are documented
at module level and with nearby explanatory text because aliases cannot reliably carry runtime
docstrings; wrapper classes are not introduced solely for documentation.

## Serialization

Top-level requests, outcomes, and projections use `schema_version="1"`. Public type adapters
validate each discriminated union. `serialization.py` provides canonical JSON using Pydantic
JSON-mode data plus sorted keys and compact separators. Matching decode functions validate JSON
back into the requested ExperimentOS contract type.

Enum values, discriminators, field names, and schema version are tested for stability. Canonical
serialization never uses provider objects or presentation formatting.

## Validation Boundary

The contract layer validates only unambiguous invariants:

- required and non-empty identifiers and labels;
- finite numeric values;
- explicit valid units and scales;
- distinct treatment and control;
- consistent positive sample counts;
- valid allocations and allocation sum;
- ordered time periods;
- valid confidence, credible, and probability levels;
- ordered interval bounds;
- CATE conditioning;
- valid discriminators and status/result combinations;
- non-empty provenance where required;
- complete financial-impact input structure;
- matching projected and input currency.

The layer does not validate statistical power, sample-ratio mismatch, overlap, positivity,
exchangeability, consistency, interference, parallel trends, CUPED correlation, sequential plans,
Bayesian priors, model fit, treatment leakage policy, estimator compatibility, or business
plausibility. Those belong to later Phase 4 issues.

## Compatibility

No existing model is extended. `packages.experiments.__all__`, `AgentState`, `AskRequest`,
`AskResponse`, SQLAlchemy models, migrations, and current agent/evaluation structures remain
unchanged. New consumers import from `packages.experiments.analysis`.

Existing focused API, agent-state, analysis-agent, business-impact-agent, and package-import tests
remain the compatibility authority. The pre-change focused baseline is 48 passing tests.

## Test-Driven Implementation

Production implementation follows strict red-green-refactor cycles. New tests are organized as:

- `tests/test_analysis_requests.py`
- `tests/test_analysis_estimates.py`
- `tests/test_analysis_results.py`
- `tests/test_business_impact_contracts.py`
- `tests/test_analysis_contract_serialization.py`

The tests cover valid randomized and observational requests; invalid treatments, units, interval
bounds, levels, sample counts, allocations, and time periods; post-treatment and unknown-timing
covariates; estimand, estimate, diagnostic, and abstention serialization; business-input provenance;
incomplete financial inputs; canonical and normal round trips; enum stability; immutable models;
and rejection of unknown fields.

Each behavior is first expressed by a test and observed failing for the intended missing behavior
before minimal production code is added.

## Documentation and Verification

Add `docs/phase4/statistical_analysis_contracts.md` with deterministic randomized,
observational, abstention, and business-impact examples. Update `docs/architecture.md` with the new
domain boundary and the explicit absence of estimator, workflow, persistence, and public API
integration.

The repository currently has no static type checker. Add `mypy` to the development dependency group
and configure strict checks for `packages/experiments/analysis`. Update `pyproject.toml` and
`uv.lock` together.

Fresh completion verification runs:

- `uv lock --check`;
- `uv run ruff format --check .`;
- `uv run ruff check .`;
- `uv run mypy packages/experiments/analysis`;
- all focused contract and compatibility tests;
- `uv run pytest`.

No verification step requires a database, Docker, credentials, network, live LLM, judge model,
hosted telemetry, EconML, or DoWhy.

## Deferred Work

The next issue owns dataset eligibility, leakage rejection, metric/design/estimand compatibility,
method preconditions, and typed invalid-input outcomes generated from actual validation. Later
issues own descriptive calculations, randomized inference, CUPED, sequential and Bayesian methods,
Difference-in-Differences, propensity methods, weighting, Double Machine Learning, heterogeneous
effects, third-party adapters, workflow integration, observability events, quality policy,
business-impact calculation, persistence, and public API decisions.

## Known Risks

- The first schema version will become a compatibility surface; tests must pin discriminators and
  enum values deliberately.
- Static typing across Pydantic discriminated unions can expose mypy limitations. The design keeps
  unions explicit and confines any justified typing workaround to the contract package.
- Business formulas may later require additional sourced inputs. New projection types should be
  added compositionally rather than weakening the complete-input requirement of this version.
- Eligibility policy must not be smuggled into constructors during implementation merely to make
  invalid scientific inputs impossible to represent.
