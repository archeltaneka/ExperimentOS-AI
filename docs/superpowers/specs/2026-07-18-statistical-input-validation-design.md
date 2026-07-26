# Statistical Input Validation and Eligibility Diagnostics Design

## Purpose

Issue #89 adds an ExperimentOS-owned boundary that validates an analysis request and its supplied
tabular data before any statistical or causal estimator can run. The boundary returns deterministic,
typed eligibility outcomes for invalid structure, insufficient information, advisory weakness, and
eligible inputs. It never calculates a treatment effect or silently cleans caller data.

The GitHub issue is the source of truth. The additional implementation brief supplied for this work
clarifies the required rule families, result summaries, method capability reporting, evaluation
foundation, observability, and documentation. Where that brief makes a feature conditional on the
issue explicitly requiring it, the issue governs: standardized mean differences and Phase 3 quality
policy thresholds are not part of this implementation.

## Approved Approach

Add a focused `packages.experiments.analysis.validation` subpackage. It will compose small,
deterministic validators around the immutable Phase 4 contracts and an ExperimentOS-owned immutable
table snapshot. It will not add pandas, Polars, NumPy, SciPy, Statsmodels, or an estimator library.

The alternative of accepting only `Sequence[Mapping[str, object]]` was rejected because mappings
cannot preserve duplicate column names and leave column ordering implicit. Accepting pandas was
rejected because the repository has no dataframe dependency or dataframe-domain convention and the
validation boundary should not expose a new third-party type.

## Existing Contract Boundary

The service builds on the existing `packages.experiments.analysis` contracts and does not duplicate
constructor guarantees. Existing constructors already reject:

- empty or malformed identifiers;
- equal treatment and control identifiers, labels, or assignment values;
- invalid allocations and inconsistent declared sample totals;
- naive, reversed, or overlapping declared periods;
- invalid confidence and credible levels;
- invalid CATE conditioning;
- pre-treatment metrics measured after declared treatment begins;
- unknown fields and non-finite contract numbers.

The validation service owns cross-object consistency and data-dependent eligibility. An optional
payload entry point may translate a Pydantic request-construction failure into the stable
`request.contract_invalid` diagnostic. It must not reimplement the constructor's scientific or
structural rules.

## Package Structure

The new subpackage has explicit responsibilities:

- `models.py`: validation diagnostics, summaries, method support, and the top-level result.
- `table.py`: immutable columns-and-rows snapshots and safe record conversion.
- `bindings.py`: explicit mappings between Phase 4 roles and dataset columns.
- `policy.py`: typed operational thresholds and configuration provenance.
- `capabilities.py`: centralized contract support and estimator availability.
- `request_rules.py`: cross-object method, design, estimand, and role checks.
- `data_rules.py`: schema, treatment, outcome, missingness, and information checks.
- `design_rules.py`: units, clustering, covariates, time structure, and segments.
- `service.py`: fixed rule composition, result aggregation, and observability.
- `__init__.py`: deliberate public internal exports.

The public internal imports will also be re-exported from `packages.experiments.analysis` where they
are intended for Phase 4 consumers. No export will be added to `packages.experiments` itself.

## Immutable Tabular Input

`AnalysisTable` is a frozen snapshot containing:

- an ordered tuple of column names;
- an ordered tuple of row tuples;
- an invariant that every row has exactly the declared number of cells.

An explicit `from_records` constructor may snapshot mappings in deterministic column order. The
validator reads the snapshot only and never mutates caller objects, drops rows, imputes values,
winsorizes values, coerces treatment labels, or rewrites timestamps.

The explicit column tuple allows duplicate column names to be reported. Validators must not build a
name-to-index mapping until uniqueness has been established. Dataset read failures and malformed row
widths are ExperimentOS-owned boundary failures, not generic ineligibility outcomes.

## Data Bindings

The Phase 4 request identifies analytical concepts but does not identify every physical dataset
column. `AnalysisDataBinding` makes that connection explicit. It contains:

- treatment assignment column;
- outcome value column, or numerator and denominator columns for a declared ratio input;
- observation-unit identifier column;
- randomization-unit identifier column for randomized designs;
- clustering-unit identifier column when clustering is declared;
- timestamp column for designs that require time structure;
- covariate metric-to-column bindings;
- optional treatment-assignment timestamp column;
- optional explicit outcome bounds and negative-value policy.

Population and segment criteria continue to name their attributes directly. The service validates
that those attributes exist before evaluating a criterion. Bindings are strict, immutable, and reject
duplicate role declarations such as using the treatment or outcome column as an ordinary adjustment
covariate.

The current contracts represent one optional segment rather than a collection of mutually exclusive
segments. The service can validate that segment's criteria and arm coverage, but it cannot claim to
validate overlap among an unrepresented segment collection.

## Validation Policy

`ValidationPolicy` centralizes deterministic operational defaults and records a stable policy
version. It includes:

- minimum total valid observations;
- minimum valid observations per arm;
- weak-information warning levels above the hard minimums;
- minimum observations per requested segment arm;
- minimum cluster count;
- allocation-deviation warning and blocking thresholds;
- maximum exploratory segment cardinality where such a request is represented;
- optional missingness thresholds when explicitly configured.

The version-one defaults are: 30 total valid observations, 10 valid observations per arm, a weak
information warning below 100 total or 30 per arm, 5 valid observations per requested segment arm,
4 clusters with a weak-information warning below 20 clusters, allocation-deviation warning at 0.10
and blocking at 0.25 absolute proportion points, and exploratory segment cardinality capped at 50.
Unknown treatment values are blocking. Outcome and differential-missingness thresholds default to
unset, so their rates are reported without inventing a universal scientific cutoff.

The defaults are operational eligibility guardrails. They are not a power calculation, minimum
detectable effect calculation, proof of causal validity, or guarantee of statistical usefulness.
Missingness rates are always reported. A missingness rate becomes blocking only when a policy or
contract-supplied threshold explicitly says so.

Policy objects reject negative minimums, inconsistent warning and blocking thresholds, invalid
probabilities, and blank policy versions. Tests construct policy explicitly and never depend
on ambient environment variables.

## Structured Diagnostics

`EligibilityDiagnostic` is an ExperimentOS-owned immutable contract. Each diagnostic contains:

- stable code;
- category;
- severity using the existing Phase 4 severity vocabulary;
- outcome using the existing Phase 4 diagnostic outcome vocabulary;
- aggregation disposition: blocking, needs-more-data, warning, or informational;
- human-readable message;
- deterministic structured context;
- optional recommended action.

Context values are limited to JSON-safe, low-cardinality summaries such as counts, rates, column
names, metric identifiers, and period labels. Raw row values are excluded. Context mappings are
stored canonically so equal inputs cannot produce order-dependent serialization.

Initial code families include:

- `request.*` for request and cross-object consistency;
- `schema.*` for columns and usable types;
- `treatment.*` for arm presence, unknown values, missing assignment, and switching;
- `outcome.*` for missing, non-finite, invalid binary, negative, bounded, degenerate, and ratio data;
- `unit.*` for identifiers, duplicates, repeated observations, assignment conflicts, and clustering;
- `covariate.*` for leakage, timing, role conflicts, duplicates, and availability;
- `missingness.*` for role-specific and differential missingness;
- `sample.*` for total, arm, cluster, period, and segment information;
- `allocation.*` for declared-versus-observed assignment proportions;
- `time.*` for parseability, period coverage, ordering, and treatment timing;
- `segment.*` for schema, requested values, cardinality, missing values, arm coverage, and sample size;
- `method.*` for contract support and estimator availability.

Rule execution order is fixed. Final diagnostic ordering is deterministic by rule ordinal, code, and
canonical context. Messages are stable presentation text, but evaluation and policy consumers must
assert codes and structured fields rather than parse messages.

## Request and Method Consistency

Cross-object request validation checks combinations that no individual constructor owns:

- metric type against estimand kind;
- design type against declared method family;
- randomized assignment unit against observation and clustering units;
- duplicate metric, covariate, treatment, outcome, identifier, and segment roles;
- CATE segment consistency between the request segment and estimand conditioning segment;
- method prerequisites such as pre-treatment inputs for CUPED or pre/post periods for future DiD;
- unsupported combinations represented by otherwise valid contracts.

No invalid design is silently changed into another method or estimand.

`MethodCapabilityRegistry` is the single source of method capability decisions. For each method it
records whether the Phase 4 contract recognizes it and whether an implementation is available. Data
eligibility is evaluated separately. The result therefore distinguishes contract support, data
eligibility, implementation availability, and executability.

The default registry truthfully marks current estimators unavailable. Tests and future estimator
composition may supply a registry that declares a method implementation available; this does not
implement or invoke an estimator.

## Dataset and Population Rules

Schema validation runs before rules that read values. It checks empty data, duplicate columns,
required role columns, declared covariates and segment attributes, ratio inputs, usable role types,
and timestamp parseability. It does not mutate or filter the table.

Treatment validation uses exact typed equality rather than truthiness. It reports treatment and
control counts, missing assignments, unknown values, empty arms, unexpected arms, unit assignment
conflicts, treatment switching, and period instability where the declared data make those checks
possible. The presence of two arms is never treated as evidence of randomization.

Outcome validation reports missing counts and rates, non-numeric inputs, NaN, infinity, invalid
binary values, prohibited negative values, explicit-bound violations, invalid ratio denominators,
zero variation, empty valid-outcome populations, and valid outcome counts by arm. Invalid rows are
counted but are not silently removed from the caller's data. Counts that require a valid-outcome
subset are reported as derived summaries rather than a mutated dataset.

## Unit, Timing, and Leakage Rules

Unit rules check missing identifiers, duplicate observation units when one row per unit is required,
multiple treatment assignments for one randomization unit, unsupported switching, repeated
measurements without clustering, observation-level analysis that ignores clustered assignment,
randomization-versus-observation mismatch, and cluster counts. They do not calculate clustered
standard errors.

Covariate rules use only explicit Phase 4 timing and role metadata. Post-treatment adjustment,
treatment-derived adjustment, treatment or outcome reuse, and identifier-as-adjustment are blocking.
Unknown timing is blocking when the requested method requires causal timing. Missing optional
covariate data is reported and becomes blocking only under explicit policy. Column names never serve
as evidence of temporal or causal role.

Time rules parse without rewriting values. They validate timezone-aware timestamps according to the
existing contract convention, declared period membership, pre/post coverage, treatment timing, unit
coverage in required periods, and stable treatment assignment across periods. They validate only
structural readiness for Difference-in-Differences and never test parallel trends.

## Segments and Allocation

Segment validation evaluates the current predefined segment criteria deterministically and reports
missing attributes, missing assignments, absent requested values, arm coverage, valid outcome counts,
and operational minimums. Unsupported high-cardinality exploratory use is flagged only where the
input explicitly represents such a request.

Allocation diagnostics report observed arm proportions and deviation from declared randomized
allocation. Warning and blocking decisions come from policy. They do not claim that observed balance
proves randomization. Standardized mean differences and propensity scores are excluded.

## Eligibility Result and Aggregation

`EligibilityValidationResult` is a new top-level validation contract rather than a mutation of the
existing policy-free `EligibilityAssessment`. This preserves existing Phase 4 serialization while
providing the richer issue #89 output. It contains:

- eligibility status using the existing four `AnalysisStatus` eligibility values;
- requested method and experiment design when structurally available;
- complete diagnostics, blocking diagnostics, and warnings;
- dataset, treatment, outcome, missingness, unit, time, and segment summaries;
- method support assessment;
- optional abstention reason using the existing Phase 4 contract;
- validation and policy versions;
- configuration provenance.

The model has no estimate, confidence interval, p-value, or effect field.

Aggregation precedence is explicit:

1. Any blocking diagnostic produces `ineligible`.
2. Otherwise, any needs-more-data diagnostic produces `needs_more_data`.
3. Otherwise, any warning diagnostic produces `eligible_with_warnings`.
4. Otherwise, the result is `eligible`.

Unsupported methods and required-but-unavailable estimators are blocking. Insufficient total, arm,
cluster, period, or segment information produces `needs_more_data` when no structural blocker is
present. Ineligible and needs-more-data results carry a deterministic abstention reason; eligible
results do not.

## Service Flow

`AnalysisEligibilityService.validate` performs the following fixed sequence:

1. Start an internal validation span.
2. Snapshot or accept the immutable table.
3. Run request and capability rules.
4. Run schema rules.
5. If required columns are unreadable, skip dependent rules with explicit unavailable diagnostics.
6. Run treatment, outcome, missingness, unit, covariate, time, segment, allocation, and sample rules.
7. Canonically order diagnostics and build summaries.
8. Aggregate status and abstention.
9. Finish observability with logical summaries.
10. Return the immutable validation result.

Expected invalid or insufficient inputs return results. Exceptions are reserved for malformed
internal tables, violated service invariants, programmer errors, and unexpected infrastructure
failures that cannot safely be represented.

## Observability

The service depends only on the existing ExperimentOS `BaseObservabilityProvider` abstraction and
defaults to `NoOpObservabilityProvider`. It emits a logical validation span with:

- validation started and completed through span lifecycle;
- requested design and method;
- final eligibility status;
- blocking and warning counts;
- needs-more-data and method-unavailable flags;
- validation duration;
- validator failure stage for unexpected failures.

Inputs contain row and column counts only. Raw datasets, raw row values, treatment values, outcome
values, and sensitive identifiers are excluded. Existing provider isolation remains authoritative;
provider export failure cannot change the validation result.

## Evaluation Foundation

Add deterministic repository-local golden cases under `packages.evals` or `data/eval` using compact
synthetic tables. Each case records expected eligibility status and diagnostic codes. Coverage
includes the issue-required valid input and fatal/advisory cases plus the explicitly requested
missing arms, unexpected arm, invalid outcomes, duplicate units, assignment conflicts, leakage,
insufficient samples, period errors, missing cluster, segment failures, estimator unavailable,
warnings, and full eligibility cases.

The evaluator consumes structured status and code fields. It does not call live models, remote
services, hosted observability, or third-party judge frameworks. No quality-policy gate is added in
this issue.

## Testing Strategy

Implementation follows strict red-green-refactor cycles. Tests are split by responsibility:

- validation contracts, bindings, policy, and serialization;
- request and capability rules;
- schema, treatment, outcome, and missingness rules;
- unit, covariate, time, segment, allocation, and sample rules;
- service aggregation and deterministic ordering;
- observability metadata and failure isolation;
- golden evaluation cases and documentation;
- Phase 1-3 and previous Phase 4 compatibility.

Fixtures are compact, deterministic, and explicit about their data-generating intent. No test uses
ambient validation configuration, network access, live LLMs, or nondeterministic providers.

## Documentation

Add Phase 4 documentation describing the validation architecture, structural versus dataset
eligibility, status precedence, diagnostic stability, method availability, operational thresholds,
leakage prevention, unit and clustering checks, future estimator consumption, and safe
observability. Include examples for eligible, eligible-with-warnings, post-treatment ineligibility,
needs-more-data, and estimator-unavailable outcomes. Update `docs/architecture.md` to name the new
boundary without changing the public API flow.

## Compatibility and Scope

The implementation preserves:

- `POST /ask` request and response behavior;
- Phase 1-3 agents, workflows, ingestion, retrieval, evaluation, persistence, and configuration;
- existing Phase 4 request, estimate, result, and canonical serialization behavior;
- all SQLAlchemy models and Alembic history;
- deterministic fake/mock provider behavior.

It adds no estimator, descriptive-statistics result generator, confidence interval, p-value, power
calculation, CUPED calculation, sequential analysis, Bayesian inference, DiD estimate, propensity
score, matching, weighting, regression adjustment, DML, heterogeneous-effect estimate, business
impact calculation, LLM interpretation, API endpoint, workflow route, database table, migration, or
vendor SDK dependency.

## Completion Verification

Fresh verification will run:

- focused validation and Phase 4 contract tests;
- compatibility tests for API, agents, package imports, and Phase 3 architecture;
- `uv lock --check`;
- `uv run ruff format --check .`;
- `uv run ruff check .`;
- `uv run mypy packages/experiments/analysis`;
- `uv run pytest` with database tests skipped when `DATABASE_URL` is unset;
- configuration validation commands already used by the repository;
- the existing Phase 3 offline verification command.

The final diff will be inspected for public API changes, estimator logic, duplicated constructor
validation, dependency expansion, migrations, and generated data.
