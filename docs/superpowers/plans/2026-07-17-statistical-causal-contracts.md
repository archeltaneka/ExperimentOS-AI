# Statistical and Causal Analysis Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add immutable, validated, ExperimentOS-owned statistical and causal analysis contracts that preserve epistemic distinctions, uncertainty, provenance, abstention, and complete business-impact inputs without implementing estimators or changing existing APIs.

**Architecture:** Create a focused `packages.experiments.analysis` subpackage of composable Pydantic v2 contracts. Requests, study designs, uncertainty, estimates, terminal outcomes, and projections use explicit discriminators and strict cross-field invariants; canonical JSON helpers validate every boundary round trip. Existing agents, persistence, observability, evaluation models, and `POST /ask` remain unchanged.

**Tech Stack:** Python 3.12, Pydantic v2, mypy, pytest, Ruff, uv.

## Global Constraints

- Follow strict red-green-refactor: no production behavior before its failing test is observed.
- Keep `POST /ask`, `AgentState`, SQLAlchemy models, migrations, agents, and existing package exports unchanged.
- Do not add calculations, estimators, registries, method selection, workflow integration, or public API fields.
- Do not expose third-party statistical, ML, causal, evaluation, workflow, dataframe, or provider result types.
- Use immutable `extra="forbid"` Pydantic models, stable lowercase `StrEnum` values, tuples for immutable collections, and finite machine-readable numbers.
- Add concise module docstrings and model docstrings for every public contract.
- Preserve descriptive, associational, randomized, quasi-experimental, observational, and business-projection distinctions.
- Require explicit uncertainty and provenance for estimates and projections.
- Permit scientifically invalid covariates to be represented explicitly so the next issue can classify eligibility.
- Use Python 3.12, line length 100, deterministic fixtures, and no network or service dependency in tests.
- Update `pyproject.toml` and `uv.lock` together for the mypy development dependency.
- Use bracketed commit subjects only after the task's tests pass.
- Standardize proportion-scale multipliers as `1.0`, `0.01`, `0.01`, and `0.0001` for
  proportion, percent, percentage point, and basis point respectively; keep raw/custom positive
  multipliers explicit.
- Keep `SourcedProportion` canonical: proportion dimension, proportion scale, multiplier `1.0`, and
  value in `[0, 1]`.
- Attach uncertainty independently to each business projection output through `ProjectedValue`;
  do not retain a projection-level shared `uncertainty` field.
- Reject negative exposure frequency while allowing zero.

---

## File Map

### New production files

- `packages/experiments/analysis/base.py`: immutable base model, shared strict scalar aliases, schema version, and analysis status.
- `packages/experiments/analysis/metrics.py`: metric/unit/value/outcome/analysis-unit/sample contracts.
- `packages/experiments/analysis/populations.py`: selection criteria, populations, and segments.
- `packages/experiments/analysis/study_designs.py`: arms, time periods, clustering, design families, covariates, and pre-treatment metrics.
- `packages/experiments/analysis/estimands.py`: supported estimands and CATE conditioning.
- `packages/experiments/analysis/provenance.py`: provenance, assumptions, diagnostics, warnings, and failures.
- `packages/experiments/analysis/uncertainty.py`: requested levels and estimate uncertainty variants.
- `packages/experiments/analysis/requests.py`: composed analysis request and request-level invariants.
- `packages/experiments/analysis/estimates.py`: descriptive and treatment-effect finding families.
- `packages/experiments/analysis/results.py`: eligibility and terminal outcome union.
- `packages/experiments/analysis/business_impact.py`: sourced projection inputs and projection output.
- `packages/experiments/analysis/serialization.py`: canonical JSON and validated union decoding.
- `packages/experiments/analysis/__init__.py`: public internal exports.

### New tests

- `tests/test_analysis_requests.py`
- `tests/test_analysis_estimates.py`
- `tests/test_analysis_results.py`
- `tests/test_business_impact_contracts.py`
- `tests/test_analysis_contract_serialization.py`
- `tests/analysis_contract_fixtures.py`: deterministic construction helpers used only by contract tests.
- `tests/__init__.py`: makes the shared contract-test helper import unambiguous.

### Modified files

- `pyproject.toml`: add mypy and strict package-scoped configuration.
- `uv.lock`: lock the type-checking dependency.
- `docs/architecture.md`: document the Phase 4 contract boundary.
- `docs/phase4/statistical_analysis_contracts.md`: deterministic contract examples and limitations.

---

### Task 1: Establish Contract Primitives, Metrics, Populations, and Estimands

**Files:**
- Create: `packages/experiments/analysis/base.py`
- Create: `packages/experiments/analysis/metrics.py`
- Create: `packages/experiments/analysis/populations.py`
- Create: `packages/experiments/analysis/estimands.py`
- Create: `packages/experiments/analysis/__init__.py`
- Create: `tests/test_analysis_requests.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

**Interfaces:**
- Produces: `ContractModel`, `AnalysisStatus`, strict scalar aliases, `MetricUnit`, `MetricDefinition`, `OutcomeMetric`, `MeasuredValue`, `AnalysisUnit`, `SampleCounts`, `PopulationDefinition`, `SegmentDefinition`, and `EstimandDefinition`.
- Consumes: only Pydantic and Python standard-library types.

- [ ] **Step 1: Write the first failing primitive and unit tests**

Create `tests/test_analysis_requests.py` with imports from the wished-for package and these focused
tests before any production module exists:

```python
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from packages.experiments.analysis import (
    AnalysisUnit,
    EstimandDefinition,
    EstimandKind,
    MetricDefinition,
    MetricType,
    MetricUnit,
    OutcomeDirection,
    OutcomeMetric,
    PopulationDefinition,
    SampleCounts,
    SegmentDefinition,
    UnitDimension,
    ValueScale,
)


def proportion_unit() -> MetricUnit:
    return MetricUnit(
        dimension=UnitDimension.PROPORTION,
        value_scale=ValueScale.PROPORTION,
        symbol="1",
        scale_to_base_unit=1.0,
    )


def test_metric_unit_rejects_ambiguous_or_invalid_units() -> None:
    with pytest.raises(ValidationError):
        MetricUnit.model_validate({"symbol": "%"})
    with pytest.raises(ValidationError, match="proportion dimension"):
        MetricUnit(
            dimension=UnitDimension.COUNT,
            value_scale=ValueScale.PERCENT,
            symbol="%",
            scale_to_base_unit=0.01,
        )
    with pytest.raises(ValidationError, match="currency_code"):
        MetricUnit(
            dimension=UnitDimension.CURRENCY,
            value_scale=ValueScale.RAW,
            symbol="$",
            scale_to_base_unit=1.0,
        )
    with pytest.raises(ValidationError):
        MetricUnit(
            dimension=UnitDimension.COUNT,
            value_scale=ValueScale.RAW,
            symbol="count",
            scale_to_base_unit=float("nan"),
        )


@pytest.mark.parametrize(
    ("total", "treatment", "control"),
    [(0, 0, 0), (10, 0, 10), (10, 5, 4), (-1, 1, 1), (True, 1, 1)],
)
def test_sample_counts_reject_invalid_values(
    total: object,
    treatment: object,
    control: object,
) -> None:
    with pytest.raises(ValidationError):
        SampleCounts(total=total, treatment=treatment, control=control)


def test_cate_requires_a_conditioning_segment_and_other_estimands_forbid_it() -> None:
    segment = SegmentDefinition(segment_id="au", label="Australia", criteria=())
    cate = EstimandDefinition(
        kind=EstimandKind.CONDITIONAL_AVERAGE_TREATMENT_EFFECT,
        conditioning_segment=segment,
    )
    assert cate.conditioning_segment == segment
    with pytest.raises(ValidationError, match="conditioning segment"):
        EstimandDefinition(kind=EstimandKind.CONDITIONAL_AVERAGE_TREATMENT_EFFECT)
    with pytest.raises(ValidationError, match="only valid for CATE"):
        EstimandDefinition(kind=EstimandKind.AVERAGE_TREATMENT_EFFECT, conditioning_segment=segment)


def test_contract_models_are_frozen_and_reject_unknown_fields() -> None:
    unit = proportion_unit()
    with pytest.raises(ValidationError, match="frozen"):
        unit.symbol = "%"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MetricUnit.model_validate({**unit.model_dump(), "presentation": "5%"})
```

- [ ] **Step 2: Run the primitive tests and verify RED**

Run: `uv run pytest tests/test_analysis_requests.py -q`

Expected: collection fails because `packages.experiments.analysis` does not exist. This is the
intended missing-feature failure.

- [ ] **Step 3: Add mypy through uv and configure the new package**

Run: `uv add --dev "mypy>=1.18.2"`

Expected: `pyproject.toml` and `uv.lock` change together.

Add this configuration to `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.12"
strict = true
files = ["packages/experiments/analysis"]
```

- [ ] **Step 4: Implement the immutable base and exact metric interfaces**

Implement `base.py` with these public definitions:

```python
from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StringConstraints,
)

SCHEMA_VERSION: Literal["1"] = "1"
NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, strict=True)]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$", strict=True)]
FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
PositiveFiniteFloat = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
Probability = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
OpenProbability = Annotated[float, Field(strict=True, gt=0, lt=1, allow_inf_nan=False)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
ScalarValue: TypeAlias = StrictBool | StrictInt | StrictFloat | NonEmptyStr


class AnalysisStatus(StrEnum):
    ELIGIBLE = "eligible"
    ELIGIBLE_WITH_WARNINGS = "eligible_with_warnings"
    INELIGIBLE = "ineligible"
    NEEDS_MORE_DATA = "needs_more_data"
    COMPLETED = "completed"
    INCONCLUSIVE = "inconclusive"
    ABSTAINED = "abstained"
    FAILED = "failed"


class ContractModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
```

Create `packages/experiments/analysis/__init__.py` in this task and export the Task 1 public types.
Each later task updates this file in the same RED/GREEN slice so tests always exercise the public
internal boundary.

Implement `metrics.py` with `UnitDimension`, `ValueScale`, `MetricType`, `OutcomeDirection`,
`MetricUnit`, `MetricDefinition`, `OutcomeMetric`, `MeasuredValue`, `AnalysisUnit`, and
`SampleCounts`. `MetricUnit` uses an after-model validator returning `Self` to enforce currency,
custom-dimension, and percentage-scale rules. `SampleCounts` uses strict positive integers and an
after-model validator requiring `total == treatment + control`.

The exact model fields are:

```python
class MetricUnit(ContractModel):
    dimension: UnitDimension
    value_scale: ValueScale
    symbol: NonEmptyStr
    scale_to_base_unit: PositiveFiniteFloat
    currency_code: CurrencyCode | None = None
    custom_dimension_name: NonEmptyStr | None = None


class MetricDefinition(ContractModel):
    metric_id: NonEmptyStr
    label: NonEmptyStr
    metric_type: MetricType
    unit: MetricUnit


class OutcomeMetric(ContractModel):
    metric: MetricDefinition
    direction: OutcomeDirection


class MeasuredValue(ContractModel):
    value: FiniteFloat
    unit: MetricUnit


class AnalysisUnit(ContractModel):
    unit_id: NonEmptyStr
    label: NonEmptyStr


class SampleCounts(ContractModel):
    total: PositiveInt
    treatment: PositiveInt
    control: PositiveInt
```

- [ ] **Step 5: Implement typed populations and the exact estimand set**

Implement `populations.py` with `CriterionOperator`, `SelectionCriterion`,
`PopulationDefinition`, and `SegmentDefinition`. `in` and `not_in` operators require a non-empty
tuple value; scalar operators require one scalar value.

Implement `estimands.py` with exactly these enum values:

```python
class EstimandKind(StrEnum):
    DIFFERENCE_IN_MEANS = "difference_in_means"
    DIFFERENCE_IN_PROPORTIONS = "difference_in_proportions"
    ABSOLUTE_LIFT = "absolute_lift"
    RELATIVE_LIFT = "relative_lift"
    AVERAGE_TREATMENT_EFFECT = "average_treatment_effect"
    AVERAGE_TREATMENT_EFFECT_ON_TREATED = "average_treatment_effect_on_treated"
    CONDITIONAL_AVERAGE_TREATMENT_EFFECT = "conditional_average_treatment_effect"
    INTENTION_TO_TREAT = "intention_to_treat"
```

`EstimandDefinition` has fields `kind` and `conditioning_segment`. Its after-model validator
requires the segment only for CATE and forbids it for every other estimand.

- [ ] **Step 6: Run the primitive suite and type checker; verify GREEN**

Run: `uv run pytest tests/test_analysis_requests.py -q`

Expected: all Task 1 tests pass.

Run: `uv run mypy packages/experiments/analysis`

Expected: success with no issues in the four implemented modules.

- [ ] **Step 7: Commit the passing primitive contract slice**

```powershell
git add pyproject.toml uv.lock packages/experiments/analysis/__init__.py packages/experiments/analysis/base.py packages/experiments/analysis/metrics.py packages/experiments/analysis/populations.py packages/experiments/analysis/estimands.py tests/test_analysis_requests.py
git commit -m "[New Feature] Add statistical contract primitives"
```

---

### Task 2: Add Study Designs, Covariates, and Analysis Requests

**Files:**
- Create: `packages/experiments/analysis/study_designs.py`
- Create: `packages/experiments/analysis/uncertainty.py`
- Create: `packages/experiments/analysis/requests.py`
- Modify: `tests/test_analysis_requests.py`
- Create: `tests/analysis_contract_fixtures.py`
- Create: `tests/__init__.py`
- Modify: `packages/experiments/analysis/__init__.py`

**Interfaces:**
- Consumes: Task 1 metrics, populations, estimands, statuses, and scalar aliases.
- Produces: randomized, quasi-experimental, and observational study-design unions; explicit clustering; covariate timing/role/relationship; requested uncertainty; `AnalysisRequest`.

- [ ] **Step 1: Add valid randomized and observational request tests**

Add deterministic factory helpers and these tests before creating the modules:

```python
def utc(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def test_constructs_valid_randomized_experiment_request() -> None:
    request = randomized_request()
    assert request.study_design.design_type == "randomized_experiment"
    assert request.study_design.randomization_unit.unit_id == "account"
    assert request.unit_of_analysis.unit_id == "order"
    assert request.clustering.kind == "none"
    assert request.estimand.kind is EstimandKind.INTENTION_TO_TREAT


def test_constructs_valid_observational_analysis_request() -> None:
    request = observational_request()
    assert request.study_design.design_type == "observational_study"
    assert request.study_design.method == "double_machine_learning"
    assert request.clustering.unit.unit_id == "customer"
    assert request.estimand.kind is EstimandKind.AVERAGE_TREATMENT_EFFECT_ON_TREATED
```

Create `tests/analysis_contract_fixtures.py` before adding the tests. It defines `utc`,
`proportion_unit`, `count_unit`, `population`, `outcome`, `randomized_design`, `covariate`,
`randomized_request`, and `observational_request`. Use these exact timestamps:

```python
RANDOMIZED_START = datetime(2026, 7, 1, tzinfo=UTC)
RANDOMIZED_END = datetime(2026, 7, 15, tzinfo=UTC)
OBSERVATIONAL_START = datetime(2026, 6, 1, tzinfo=UTC)
OBSERVATIONAL_END = datetime(2026, 6, 30, tzinfo=UTC)
```

The randomized request uses population `checkout_users`; treatment `ranked_payment` with assignment
value `treatment`; control `standard_payment` with assignment value `control`; outcome
`payment_success_rate` as a proportion where increase is preferred; ITT; fixed-horizon A/B;
randomization unit `account`; analysis unit `order`; explicit no clustering; allocation 0.5/0.5;
sample counts 200/100/100; and confidence level 0.95.

The observational request uses population `eligible_customers`; treatment `offer_exposed`; control
`offer_unexposed`; outcome `conversion_rate`; ATT; Double Machine Learning; observation unit
`customer`; clustering by customer; counts 300/120/180; and confidence level 0.95. Its covariate
tuple contains one pre-treatment adjustment covariate whose treatment relationship is none known.

Each factory accepts only the keyword overrides exercised by the tests and constructs a fresh
immutable model; it never mutates an existing model.

Create an empty `tests/__init__.py`, then import the builders explicitly in contract test modules:

```python
from tests.analysis_contract_fixtures import (
    covariate,
    observational_request,
    randomized_design,
    randomized_request,
    utc,
)
```

- [ ] **Step 2: Add failing validation tests for arms, allocation, periods, and covariate representation**

```python
def test_request_rejects_equal_treatment_and_control_definitions() -> None:
    with pytest.raises(ValidationError, match="assignment values must differ"):
        randomized_request(control_assignment_value="treatment")


@pytest.mark.parametrize(
    ("treatment", "control"),
    [(0.0, 1.0), (1.0, 0.0), (0.7, 0.4), (-0.1, 1.1)],
)
def test_randomized_design_rejects_invalid_allocations(treatment: float, control: float) -> None:
    with pytest.raises(ValidationError):
        randomized_design(treatment_allocation=treatment, control_allocation=control)


def test_time_period_rejects_naive_or_reversed_timestamps() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        TimePeriod(start=datetime(2026, 1, 2), end=datetime(2026, 1, 3))
    with pytest.raises(ValidationError, match="before end"):
        TimePeriod(start=utc(2026, 1, 3), end=utc(2026, 1, 2))


def test_post_treatment_and_unknown_covariates_are_explicitly_representable() -> None:
    post = covariate(timing=CovariateTiming.POST_TREATMENT)
    unknown = covariate(
        timing=CovariateTiming.UNKNOWN,
        treatment_relationship=TreatmentRelationship.UNKNOWN,
    )
    assert post.timing is CovariateTiming.POST_TREATMENT
    assert unknown.timing is CovariateTiming.UNKNOWN
    assert unknown.treatment_relationship is TreatmentRelationship.UNKNOWN
```

- [ ] **Step 3: Run request tests and verify RED**

Run: `uv run pytest tests/test_analysis_requests.py -q`

Expected: collection fails on missing study-design, uncertainty, and request symbols.

- [ ] **Step 4: Implement study-design discriminators and validators**

Implement these exact design families in `study_designs.py`:

```python
class RandomizedExperimentDesign(ContractModel):
    design_type: Literal["randomized_experiment"] = "randomized_experiment"
    method: RandomizedAnalysisMethod
    experiment_period: TimePeriod
    randomization_unit: AnalysisUnit
    treatment_allocation: OpenProbability
    control_allocation: OpenProbability


class QuasiExperimentalDesign(ContractModel):
    design_type: Literal["quasi_experimental"] = "quasi_experimental"
    method: QuasiExperimentalMethod
    pre_treatment_period: TimePeriod
    post_treatment_period: TimePeriod


class ObservationalStudyDesign(ContractModel):
    design_type: Literal["observational_study"] = "observational_study"
    method: ObservationalAnalysisMethod
    observation_period: TimePeriod


StudyDesign = Annotated[
    RandomizedExperimentDesign | QuasiExperimentalDesign | ObservationalStudyDesign,
    Field(discriminator="design_type"),
]
```

`RandomizedAnalysisMethod` contains fixed-horizon A/B, CUPED, sequential A/B, Bayesian A/B, and
heterogeneous treatment effect. `QuasiExperimentalMethod` contains only Difference-in-Differences.
`ObservationalAnalysisMethod` contains propensity score, weighting, Double Machine Learning, and
heterogeneous treatment effect.

Implement `TimePeriod`, `TreatmentDefinition`, `ControlDefinition`, `NoClustering`, `Clustered`,
`ClusteringSpecification`, `CovariateDefinition`, and `PreTreatmentMetric`. Allocation validation
uses `math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9)`. Time-period validation requires aware
timestamps and strict ordering. Quasi periods cannot overlap or reverse.

- [ ] **Step 5: Implement requested uncertainty and the composed request**

In `uncertainty.py`, implement `RequestedConfidenceLevel` and `RequestedCredibleLevel`, each with a
`kind` discriminator and an open-probability level. Define `RequestedUncertainty` with
`Field(discriminator="kind")`.

Implement this exact request interface in `requests.py`:

```python
class AnalysisRequest(ContractModel):
    schema_version: Literal["1"] = SCHEMA_VERSION
    population: PopulationDefinition
    segment: SegmentDefinition | None = None
    treatment: TreatmentDefinition
    control: ControlDefinition
    outcome: OutcomeMetric
    estimand: EstimandDefinition
    study_design: StudyDesign
    unit_of_analysis: AnalysisUnit
    clustering: ClusteringSpecification
    sample_counts: SampleCounts
    uncertainty: RequestedUncertainty
    covariates: tuple[CovariateDefinition, ...] = ()
    pre_treatment_metrics: tuple[PreTreatmentMetric, ...] = ()
```

Its after-model validator rejects equal arm identifiers, labels, or assignment values. It validates
pre-treatment metric ordering against randomized treatment start or quasi post-period start, but
does not reject post-treatment covariates, unknown timing, treatment proxies, or CUPED-role fields.

Update `packages/experiments/analysis/__init__.py` to export all Task 2 types before rerunning tests.

- [ ] **Step 6: Run the full request suite and type checker; verify GREEN**

Run: `uv run pytest tests/test_analysis_requests.py -q`

Expected: all randomized, observational, arm, allocation, time, sample, unit, CATE, and covariate
tests pass.

Run: `uv run mypy packages/experiments/analysis`

Expected: success with no issues.

- [ ] **Step 7: Commit the passing request slice**

```powershell
git add packages/experiments/analysis/__init__.py packages/experiments/analysis/study_designs.py packages/experiments/analysis/uncertainty.py packages/experiments/analysis/requests.py tests/__init__.py tests/analysis_contract_fixtures.py tests/test_analysis_requests.py
git commit -m "[New Feature] Add statistical analysis requests"
```

---

### Task 3: Add Provenance and Explicit Uncertainty Measures

**Files:**
- Create: `packages/experiments/analysis/provenance.py`
- Modify: `packages/experiments/analysis/uncertainty.py`
- Create: `tests/test_analysis_estimates.py`
- Modify: `packages/experiments/analysis/__init__.py`

**Interfaces:**
- Consumes: `ContractModel`, metric measured values, probability aliases.
- Produces: assumption/diagnostic/warning/failure/provenance records and a non-empty discriminated uncertainty bundle.

- [ ] **Step 1: Write failing interval and provenance tests**

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.experiments.analysis import (
    ConfidenceInterval,
    CredibleInterval,
    Diagnostic,
    DiagnosticOutcome,
    DiagnosticSeverity,
    PosteriorProbability,
    ProvenanceRecord,
    ProvenanceSourceType,
    StandardError,
    UncertaintyBundle,
    UncertaintyUnavailable,
)


@pytest.mark.parametrize(("lower", "upper"), [(2.0, 1.0), (float("nan"), 1.0)])
def test_interval_rejects_invalid_bounds(lower: float, upper: float) -> None:
    with pytest.raises(ValidationError):
        ConfidenceInterval(lower=lower, upper=upper, confidence_level=0.95)


@pytest.mark.parametrize("level", [0.0, 1.0, -0.1, 1.1])
def test_confidence_and_credible_intervals_reject_invalid_levels(level: float) -> None:
    with pytest.raises(ValidationError):
        ConfidenceInterval(lower=0.0, upper=1.0, confidence_level=level)
    with pytest.raises(ValidationError):
        CredibleInterval(lower=0.0, upper=1.0, credible_level=level)


def test_uncertainty_unavailable_cannot_mix_with_numeric_uncertainty() -> None:
    with pytest.raises(ValidationError, match="cannot coexist"):
        UncertaintyBundle(
            measures=(
                StandardError(value=0.02),
                UncertaintyUnavailable(reason="raw samples unavailable"),
            )
        )


def test_standard_error_and_posterior_probability_reject_invalid_values() -> None:
    with pytest.raises(ValidationError):
        StandardError(value=-0.01)
    with pytest.raises(ValidationError):
        PosteriorProbability(probability=1.01, event="treatment effect is positive")


def test_diagnostic_serializes_with_stable_enum_values() -> None:
    diagnostic = Diagnostic(
        code="overlap.low",
        severity=DiagnosticSeverity.WARNING,
        outcome=DiagnosticOutcome.FAILED,
        message="Observed overlap is below the planned threshold.",
    )
    assert diagnostic.model_dump(mode="json") == {
        "code": "overlap.low",
        "severity": "warning",
        "outcome": "failed",
        "message": "Observed overlap is below the planned threshold.",
        "observed_value": None,
        "threshold": None,
    }
```

- [ ] **Step 2: Run estimate tests and verify RED**

Run: `uv run pytest tests/test_analysis_estimates.py -q`

Expected: collection fails because provenance and estimate-uncertainty symbols do not exist.

- [ ] **Step 3: Implement provenance and evidence records**

Implement these stable enums and fields in `provenance.py`:

```python
class ProvenanceRecord(ContractModel):
    source_type: ProvenanceSourceType
    source_id: NonEmptyStr
    source_version: NonEmptyStr | None = None
    source_uri: NonEmptyStr | None = None
    observed_at: datetime | None = None


class AssumptionAssessment(ContractModel):
    code: NonEmptyStr
    statement: NonEmptyStr
    status: AssumptionStatus


class Diagnostic(ContractModel):
    code: NonEmptyStr
    severity: DiagnosticSeverity
    outcome: DiagnosticOutcome
    message: NonEmptyStr
    observed_value: MeasuredValue | None = None
    threshold: MeasuredValue | None = None


class AnalysisWarning(ContractModel):
    code: NonEmptyStr
    message: NonEmptyStr
    scope: NonEmptyStr


class AnalysisFailure(ContractModel):
    code: NonEmptyStr
    stage: NonEmptyStr
    message: NonEmptyStr
    retryable: bool
```

Define the reusable non-empty provenance alias in the same module:

```python
ProvenanceRecords: TypeAlias = Annotated[
    tuple[ProvenanceRecord, ...],
    Field(min_length=1),
]
```

`ProvenanceRecord` validates timezone awareness when `observed_at` is present. Source types are
experiment data, analysis request, report, configuration, derived, user supplied, and external
reference. Assumption statuses are supported, violated, unassessed, and untestable. Diagnostic
severity is info, warning, error, or fatal; diagnostic outcome is passed, failed, or unavailable.

- [ ] **Step 4: Implement explicit uncertainty variants**

Add `StandardError`, `ConfidenceInterval`, `CredibleInterval`, `PosteriorProbability`, and
`UncertaintyUnavailable` with `kind` literals. Define:

```python
UncertaintyMeasure = Annotated[
    StandardError
    | ConfidenceInterval
    | CredibleInterval
    | PosteriorProbability
    | UncertaintyUnavailable,
    Field(discriminator="kind"),
]


class UncertaintyBundle(ContractModel):
    measures: Annotated[tuple[UncertaintyMeasure, ...], Field(min_length=1)]
```

After-model validation orders interval bounds and forbids unavailable uncertainty alongside any
numeric measure. Posterior probability requires a non-empty event statement.

Update `packages/experiments/analysis/__init__.py` to export all Task 3 types before rerunning tests.

- [ ] **Step 5: Run estimate tests and type checks; verify GREEN**

Run: `uv run pytest tests/test_analysis_estimates.py -q`

Expected: all interval, level, unavailable, provenance, and diagnostic tests pass.

Run: `uv run mypy packages/experiments/analysis`

Expected: success with no issues.

- [ ] **Step 6: Commit the passing evidence slice**

```powershell
git add packages/experiments/analysis/__init__.py packages/experiments/analysis/provenance.py packages/experiments/analysis/uncertainty.py tests/test_analysis_estimates.py
git commit -m "[New Feature] Add analysis evidence contracts"
```

---

### Task 4: Add Typed Estimates, Eligibility, Abstention, and Terminal Results

**Files:**
- Create: `packages/experiments/analysis/estimates.py`
- Create: `packages/experiments/analysis/results.py`
- Modify: `tests/test_analysis_estimates.py`
- Create: `tests/test_analysis_results.py`
- Modify: `tests/analysis_contract_fixtures.py`
- Modify: `packages/experiments/analysis/__init__.py`

**Interfaces:**
- Consumes: metrics, estimands, uncertainty, evidence, samples, and status.
- Produces: descriptive/associational/randomized/quasi/observational finding union and eligibility/completed/inconclusive/abstained/failed outcome union.

- [ ] **Step 1: Add failing estimate distinction and serialization tests**

Import the shared builders explicitly at the top of `tests/test_analysis_estimates.py`:

```python
from tests.analysis_contract_fixtures import effect_details, randomized_estimate
```

```python
def test_associational_estimate_cannot_claim_a_causal_conclusion() -> None:
    with pytest.raises(ValidationError):
        AssociationalEstimate(
            finding_type="associational_estimate",
            conclusion_type=ConclusionType.CAUSAL_EFFECT,
            estimate=effect_details(analysis_status=AnalysisStatus.COMPLETED),
        )


def test_randomized_estimate_requires_an_explicit_conclusion_type() -> None:
    with pytest.raises(ValidationError):
        RandomizedExperimentEstimate.model_validate(
            {
                "finding_type": "randomized_experiment_estimate",
                "estimate": effect_details().model_dump(mode="json"),
            }
        )


def test_estimand_and_estimate_serialize_with_stable_values() -> None:
    estimate = randomized_estimate()
    payload = estimate.model_dump(mode="json")
    assert payload["finding_type"] == "randomized_experiment_estimate"
    assert payload["conclusion_type"] == "causal_effect"
    assert payload["estimate"]["estimand"]["kind"] == "intention_to_treat"
    assert payload["estimate"]["uncertainty"]["measures"][0]["kind"] == "confidence_interval"
```

- [ ] **Step 2: Add failing terminal outcome tests**

Import `abstained_result`, `randomized_estimate`, and `source` from
`tests.analysis_contract_fixtures` at the top of `tests/test_analysis_results.py`.

```python
def test_abstention_result_serializes_without_an_estimate_field() -> None:
    result = AbstainedAnalysisResult(
        outcome_type="abstained",
        status=AnalysisStatus.ABSTAINED,
        reason=AbstentionReason(
            code="covariate_timing_unknown",
            message="Causal adjustment is unsafe.",
            missing_or_invalid_information=("covariate timing",),
        ),
        diagnostics=(),
        warnings=(),
        provenance=(source(),),
    )
    payload = result.model_dump(mode="json")
    assert payload["status"] == "abstained"
    assert "findings" not in payload
    assert payload["reason"]["missing_or_invalid_information"] == ["covariate timing"]


def test_completed_result_rejects_inconclusive_child_status() -> None:
    with pytest.raises(ValidationError, match="finding status"):
        CompletedAnalysisResult(
            outcome_type="completed",
            status=AnalysisStatus.COMPLETED,
            findings=(randomized_estimate(analysis_status=AnalysisStatus.INCONCLUSIVE),),
            diagnostics=(),
            warnings=(),
            provenance=(source(),),
        )


def test_failed_result_requires_typed_failures_and_has_no_findings() -> None:
    with pytest.raises(ValidationError):
        FailedAnalysisResult(
            outcome_type="failed",
            status=AnalysisStatus.FAILED,
            failures=(),
            diagnostics=(),
            provenance=(source(),),
        )


def test_analysis_status_enum_contains_every_required_stable_value() -> None:
    assert [status.value for status in AnalysisStatus] == [
        "eligible",
        "eligible_with_warnings",
        "ineligible",
        "needs_more_data",
        "completed",
        "inconclusive",
        "abstained",
        "failed",
    ]


@pytest.mark.parametrize(
    "status",
    [
        AnalysisStatus.ELIGIBLE,
        AnalysisStatus.ELIGIBLE_WITH_WARNINGS,
        AnalysisStatus.INELIGIBLE,
        AnalysisStatus.NEEDS_MORE_DATA,
    ],
)
def test_eligibility_assessment_accepts_only_eligibility_states(status: AnalysisStatus) -> None:
    assessment = EligibilityAssessment(
        outcome_type="eligibility",
        status=status,
        diagnostics=(),
        warnings=(),
        required_data=(),
        provenance=(source(),),
    )
    assert assessment.status is status
```

- [ ] **Step 3: Run estimate and result tests; verify RED**

Run: `uv run pytest tests/test_analysis_estimates.py tests/test_analysis_results.py -q`

Expected: collection fails on missing estimate and result contracts.

- [ ] **Step 4: Implement composed findings without optional-field inflation**

Implement `EffectEstimateDetails` with required status, estimand, outcome, point estimate,
uncertainty, sample counts, assumptions, diagnostics, warnings, and non-empty provenance.

Define the conclusion vocabulary exactly:

```python
class ConclusionType(StrEnum):
    ASSOCIATION = "association"
    CAUSAL_EFFECT = "causal_effect"
    PROJECTION = "projection"
```

Implement separate wrappers with a `finding_type` discriminator:

```python
class AssociationalEstimate(ContractModel):
    finding_type: Literal["associational_estimate"] = "associational_estimate"
    conclusion_type: Literal[ConclusionType.ASSOCIATION]
    estimate: EffectEstimateDetails


class RandomizedExperimentEstimate(ContractModel):
    finding_type: Literal["randomized_experiment_estimate"] = "randomized_experiment_estimate"
    conclusion_type: ConclusionType
    estimate: EffectEstimateDetails
```

`RandomizedExperimentEstimate`, `QuasiExperimentalEstimate`, and `ObservationalEstimate` validate
that conclusion type is explicitly association or causal effect. None supplies a causal default.
`AssociationalEstimate` accepts association only. `DescriptiveStatistic` has its own statistic type,
status, metric, measured value, uncertainty, sample size, evidence records, and no estimand.

Define `AnalysisFinding` with `Field(discriminator="finding_type")`.

Also define the effect-only union used by business projections:

```python
EffectEstimate = Annotated[
    AssociationalEstimate
    | RandomizedExperimentEstimate
    | QuasiExperimentalEstimate
    | ObservationalEstimate,
    Field(discriminator="finding_type"),
]

AnalysisFinding = Annotated[
    DescriptiveStatistic
    | AssociationalEstimate
    | RandomizedExperimentEstimate
    | QuasiExperimentalEstimate
    | ObservationalEstimate,
    Field(discriminator="finding_type"),
]
```

- [ ] **Step 5: Implement eligibility and discriminated terminal outcomes**

Implement:

```python
EligibilityStatus: TypeAlias = Literal[
    AnalysisStatus.ELIGIBLE,
    AnalysisStatus.ELIGIBLE_WITH_WARNINGS,
    AnalysisStatus.INELIGIBLE,
    AnalysisStatus.NEEDS_MORE_DATA,
]


class EligibilityAssessment(ContractModel):
    outcome_type: Literal["eligibility"] = "eligibility"
    schema_version: Literal["1"] = SCHEMA_VERSION
    status: EligibilityStatus
    diagnostics: tuple[Diagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    required_data: tuple[NonEmptyStr, ...]
    provenance: ProvenanceRecords


class CompletedAnalysisResult(ContractModel):
    outcome_type: Literal["completed"] = "completed"
    schema_version: Literal["1"] = SCHEMA_VERSION
    status: Literal[AnalysisStatus.COMPLETED]
    findings: Annotated[tuple[AnalysisFinding, ...], Field(min_length=1)]
    diagnostics: tuple[Diagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords
```

Add matching inconclusive, abstained, and failed models. `AbstainedAnalysisResult` has a required
`AbstentionReason` and no findings. `FailedAnalysisResult` has a non-empty failures tuple and no
findings. Completed/inconclusive after-model validators require every child finding status to match
the parent.

Define `AnalysisOutcome` with `Field(discriminator="outcome_type")`.

Extend `tests/analysis_contract_fixtures.py` with `source`, `effect_details`,
`randomized_estimate`, and `abstained_result`. `source()` returns experiment-data provenance for
`exp-001-payment-recommendation`; `effect_details()` uses the randomized request's ITT estimand,
outcome, counts, point estimate `0.055` in a proportion unit, a 95% confidence interval from `0.002`
to `0.108`, no assumptions/diagnostics/warnings, and one source record. `randomized_estimate()` uses
an explicit causal-effect conclusion. `abstained_result()` uses the covariate-timing reason shown in
the test.

Update `packages/experiments/analysis/__init__.py` to export all Task 4 types before rerunning tests.

- [ ] **Step 6: Run finding/result tests and type checks; verify GREEN**

Run: `uv run pytest tests/test_analysis_estimates.py tests/test_analysis_results.py -q`

Expected: all epistemic-distinction, serialization, status, abstention, and failure tests pass.

Run: `uv run mypy packages/experiments/analysis`

Expected: success with no issues.

- [ ] **Step 7: Commit the passing result slice**

```powershell
git add packages/experiments/analysis/__init__.py packages/experiments/analysis/estimates.py packages/experiments/analysis/results.py tests/analysis_contract_fixtures.py tests/test_analysis_estimates.py tests/test_analysis_results.py
git commit -m "[New Feature] Add typed analysis outcomes"
```

---

### Task 5: Add Fully Sourced Business-Impact Contracts

**Files:**
- Create: `packages/experiments/analysis/business_impact.py`
- Create: `tests/test_business_impact_contracts.py`
- Modify: `tests/analysis_contract_fixtures.py`
- Modify: `packages/experiments/analysis/__init__.py`

**Interfaces:**
- Consumes: effect estimate union, metric values, time periods, uncertainty, evidence, and status.
- Produces: provenance-bearing input values, complete `BusinessImpactInputs`, and `BusinessImpactProjection`.

- [ ] **Step 1: Write failing complete-input and provenance tests**

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.experiments.analysis import BusinessImpactInputs, BusinessImpactProjection
from tests.analysis_contract_fixtures import (
    randomized_estimate,
    valid_business_inputs,
    valid_projection,
)


def test_business_impact_inputs_require_provenance_for_every_input() -> None:
    payload = valid_business_inputs().model_dump(mode="json")
    payload["baseline_rate"]["provenance"] = []
    with pytest.raises(ValidationError, match="provenance"):
        BusinessImpactInputs.model_validate(payload)


@pytest.mark.parametrize(
    "missing_field",
    [
        "eligible_population",
        "exposure_frequency",
        "baseline_rate",
        "average_order_value",
        "contribution_margin",
        "rollout_proportion",
        "analysis_horizon",
        "currency",
    ],
)
def test_business_impact_inputs_reject_incomplete_financial_inputs(missing_field: str) -> None:
    payload = valid_business_inputs().model_dump(mode="json")
    del payload[missing_field]
    with pytest.raises(ValidationError):
        BusinessImpactInputs.model_validate(payload)


def test_treatment_effect_alone_cannot_construct_business_projection() -> None:
    with pytest.raises(ValidationError):
        BusinessImpactProjection.model_validate(
            {"source_estimate": randomized_estimate().model_dump(mode="json")}
        )


def test_projection_rejects_currency_mismatch() -> None:
    with pytest.raises(ValidationError, match="currency"):
        valid_projection(projected_currency="AUD", input_currency="USD")
```

- [ ] **Step 2: Run business-impact tests and verify RED**

Run: `uv run pytest tests/test_business_impact_contracts.py -q`

Expected: collection fails because the business-impact contracts do not exist.

- [ ] **Step 3: Implement sourced values and complete inputs**

Implement non-empty `ProvenanceRecords` on each sourced model:

```python
class SourcedCount(ContractModel):
    value: PositiveInt
    provenance: ProvenanceRecords


class SourcedQuantity(ContractModel):
    value: FiniteFloat
    unit: MetricUnit
    provenance: ProvenanceRecords


class SourcedProportion(ContractModel):
    value: Probability
    unit: MetricUnit
    provenance: ProvenanceRecords


class SourcedMoney(ContractModel):
    value: FiniteFloat
    unit: MetricUnit
    provenance: ProvenanceRecords


class SourcedCurrency(ContractModel):
    value: CurrencyCode
    provenance: ProvenanceRecords


class SourcedTimePeriod(ContractModel):
    value: TimePeriod
    provenance: ProvenanceRecords
```

`SourcedProportion` requires a proportion unit. `SourcedMoney` requires a currency unit.
`BusinessImpactInputs` requires all eight named input fields with no defaults.

Extend `tests/analysis_contract_fixtures.py` with `currency_unit`, `valid_business_inputs`, and
`valid_projection`. The canonical inputs are population 100,000; exposure frequency 2 per user per
month; baseline rate 0.20; average order value USD 80; contribution margin 0.30 as a proportion;
rollout proportion 0.50; horizon 2026-08-01 through 2026-09-01 UTC; currency USD; and the same
non-empty source provenance on every value. The projection uses the randomized estimate, projected
incremental outcomes 550 in a count unit, projected financial impact USD 13,200, and the same 95%
confidence interval fixture.

- [ ] **Step 4: Implement the projection and currency consistency**

```python
class BusinessImpactProjection(ContractModel):
    projection_type: Literal["business_impact_projection"] = "business_impact_projection"
    schema_version: Literal["1"] = SCHEMA_VERSION
    status: Literal[AnalysisStatus.COMPLETED, AnalysisStatus.INCONCLUSIVE]
    conclusion_type: Literal[ConclusionType.PROJECTION]
    inputs: BusinessImpactInputs
    source_estimate: EffectEstimate
    projected_incremental_outcome: MeasuredValue
    projected_financial_impact: MeasuredValue
    uncertainty: UncertaintyBundle
    assumptions: tuple[AssumptionAssessment, ...]
    diagnostics: tuple[Diagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords
```

After-model validation requires average-order-value and projected-financial units to use the sourced
currency. Currency-valued contribution margin must also match. The source estimate is embedded
without changing its conclusion type.

Update `packages/experiments/analysis/__init__.py` to export all Task 5 types before rerunning tests.

- [ ] **Step 5: Run business-impact tests and type checks; verify GREEN**

Run: `uv run pytest tests/test_business_impact_contracts.py -q`

Expected: all complete-input, provenance, numeric, unit, currency, and no-manufactured-impact tests
pass.

Run: `uv run mypy packages/experiments/analysis`

Expected: success with no issues.

- [ ] **Step 6: Commit the passing business-impact slice**

```powershell
git add packages/experiments/analysis/__init__.py packages/experiments/analysis/business_impact.py tests/analysis_contract_fixtures.py tests/test_business_impact_contracts.py
git commit -m "[New Feature] Add sourced business impact contracts"
```

---

### Task 6: Add Public Internal Exports and Stable Serialization

**Files:**
- Create: `packages/experiments/analysis/serialization.py`
- Modify: `packages/experiments/analysis/__init__.py`
- Create: `tests/test_analysis_contract_serialization.py`

**Interfaces:**
- Consumes: every Task 1-5 model and discriminated union.
- Produces: stable public import surface, canonical JSON, and validated request/finding/outcome/projection decoding.

- [ ] **Step 1: Write failing round-trip and canonical serialization tests**

```python
from __future__ import annotations

import json

from packages.experiments.analysis import (
    AnalysisRequest,
    BusinessImpactProjection,
    analysis_finding_from_json,
    analysis_outcome_from_json,
    analysis_request_from_json,
    business_impact_projection_from_json,
    to_canonical_json,
)
from tests.analysis_contract_fixtures import (
    abstained_result,
    randomized_estimate,
    randomized_request,
    valid_projection,
)


def test_analysis_request_round_trip() -> None:
    original = randomized_request()
    restored = analysis_request_from_json(to_canonical_json(original))
    assert restored == original
    assert isinstance(restored, AnalysisRequest)


def test_estimate_and_abstention_round_trip_through_discriminated_unions() -> None:
    estimate = randomized_estimate()
    result = abstained_result()
    assert analysis_finding_from_json(to_canonical_json(estimate)) == estimate
    assert analysis_outcome_from_json(to_canonical_json(result)) == result


def test_business_projection_round_trip() -> None:
    projection = valid_projection()
    restored = business_impact_projection_from_json(to_canonical_json(projection))
    assert restored == projection
    assert isinstance(restored, BusinessImpactProjection)


def test_canonical_json_has_sorted_keys_and_stable_enum_values() -> None:
    payload = to_canonical_json(randomized_request())
    assert payload == json.dumps(
        json.loads(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    assert '"schema_version":"1"' in payload
    assert '"kind":"intention_to_treat"' in payload
```

- [ ] **Step 2: Run serialization tests and verify RED**

Run: `uv run pytest tests/test_analysis_contract_serialization.py -q`

Expected: collection fails because the package exports and serialization helpers do not exist.

- [ ] **Step 3: Implement canonical JSON and validated decoders**

```python
from __future__ import annotations

import json

from pydantic import TypeAdapter

from packages.experiments.analysis.base import ContractModel
from packages.experiments.analysis.business_impact import BusinessImpactProjection
from packages.experiments.analysis.estimates import AnalysisFinding
from packages.experiments.analysis.requests import AnalysisRequest
from packages.experiments.analysis.results import AnalysisOutcome

ANALYSIS_FINDING_ADAPTER = TypeAdapter(AnalysisFinding)
ANALYSIS_OUTCOME_ADAPTER = TypeAdapter(AnalysisOutcome)


def to_canonical_json(model: ContractModel) -> str:
    return json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def analysis_request_from_json(payload: str | bytes) -> AnalysisRequest:
    return AnalysisRequest.model_validate_json(payload)


def analysis_finding_from_json(payload: str | bytes) -> AnalysisFinding:
    return ANALYSIS_FINDING_ADAPTER.validate_json(payload)


def analysis_outcome_from_json(payload: str | bytes) -> AnalysisOutcome:
    return ANALYSIS_OUTCOME_ADAPTER.validate_json(payload)


def business_impact_projection_from_json(payload: str | bytes) -> BusinessImpactProjection:
    return BusinessImpactProjection.model_validate_json(payload)
```

- [ ] **Step 4: Export the deliberate internal API**

Finalize `packages/experiments/analysis/__init__.py` with explicit imports and `__all__` for every
public enum, model, union adapter, and serialization helper used by the five test modules. Do not
modify `packages/experiments/__init__.py`.

- [ ] **Step 5: Run all contract tests and type checks; verify GREEN**

Run: `uv run pytest tests/test_analysis_requests.py tests/test_analysis_estimates.py tests/test_analysis_results.py tests/test_business_impact_contracts.py tests/test_analysis_contract_serialization.py -q`

Expected: all contract tests pass.

Run: `uv run mypy packages/experiments/analysis`

Expected: success with no issues.

- [ ] **Step 6: Commit the passing serialization slice**

```powershell
git add packages/experiments/analysis/__init__.py packages/experiments/analysis/serialization.py tests/test_analysis_contract_serialization.py
git commit -m "[New Feature] Add analysis contract serialization"
```

---

### Task 7: Document the Contract Boundary and Preserve Compatibility

**Files:**
- Create: `docs/phase4/statistical_analysis_contracts.md`
- Modify: `docs/architecture.md`
- Test: existing compatibility suites plus contract tests.

**Interfaces:**
- Consumes: final public internal exports and deterministic examples.
- Produces: Phase 4 architecture guidance without advertising unimplemented behavior.

- [ ] **Step 1: Write documentation assertions before documentation changes**

Add these assertions to `tests/test_analysis_contract_serialization.py`:

```python
from pathlib import Path


def test_phase4_contract_documentation_records_boundaries_and_examples() -> None:
    documentation = Path("docs/phase4/statistical_analysis_contracts.md").read_text(
        encoding="utf-8"
    )
    assert "## Randomized Request Example" in documentation
    assert "## Observational Request Example" in documentation
    assert "## Abstention Example" in documentation
    assert "## Business-Impact Projection Inputs" in documentation
    assert "No estimator is implemented" in documentation
    assert "POST /ask" in documentation


def test_architecture_names_the_phase4_contract_boundary() -> None:
    architecture = Path("docs/architecture.md").read_text(encoding="utf-8")
    assert "packages.experiments.analysis" in architecture
    assert "not yet integrated" in architecture.lower()
```

- [ ] **Step 2: Run documentation tests and verify RED**

Run: `uv run pytest tests/test_analysis_contract_serialization.py -q`

Expected: failures because the Phase 4 document and architecture section do not exist.

- [ ] **Step 3: Write deterministic examples and explicit limitations**

Create `docs/phase4/statistical_analysis_contracts.md` with these headings:

```markdown
# Statistical and Causal Analysis Contracts
## Scope
## Package Boundary
## Randomized Request Example
## Observational Request Example
## Estimate and Uncertainty Example
## Abstention Example
## Business-Impact Projection Inputs
## Validation Boundary
## Deferred Phase 4 Work
```

Examples must use JSON-compatible enum values, timezone-aware timestamps, explicit units and
scales, separate randomization and analysis units, complete uncertainty, and provenance. State
verbatim that no estimator is implemented and that `POST /ask`, agents, persistence, and workflows
are unchanged.

Update `docs/architecture.md` with a Phase 4 Domain Contracts subsection and one package-overview
row for `packages.experiments.analysis`. State that contracts are not yet integrated with
estimators, agents, persistence, observability emission, evaluation policy, or the public API.

- [ ] **Step 4: Run documentation, package, API, and agent compatibility tests**

Run: `uv run pytest tests/test_analysis_contract_serialization.py tests/test_package_imports.py tests/test_agent_state.py tests/test_api_ask.py tests/test_experiment_analysis_agent.py tests/test_business_impact_agent.py -q`

Expected: all new documentation tests and the pre-change 48 compatibility tests pass.

- [ ] **Step 5: Commit the passing documentation slice**

```powershell
git add docs/phase4/statistical_analysis_contracts.md docs/architecture.md tests/test_analysis_contract_serialization.py
git commit -m "[Improvement] Document Phase 4 analysis contracts"
```

---

### Review-Fix Task: Harden Units, Projections, Frequencies, and Public Documentation

**Files:**
- Modify: `docs/superpowers/specs/2026-07-17-statistical-causal-contracts-design.md`
- Modify: `docs/superpowers/plans/2026-07-17-statistical-causal-contracts.md`
- Modify: `tests/test_analysis_estimates.py`
- Modify: `tests/test_business_impact_contracts.py`
- Modify: `tests/test_analysis_contract_serialization.py`
- Create: `tests/test_analysis_contract_documentation.py`
- Modify: `tests/analysis_contract_fixtures.py`
- Modify: `packages/experiments/analysis/metrics.py`
- Modify: `packages/experiments/analysis/business_impact.py`
- Modify: `packages/experiments/analysis/serialization.py`
- Modify: `packages/experiments/analysis/__init__.py`
- Modify: public modules under `packages/experiments/analysis/` that lack useful documentation
- Modify: `docs/phase4/statistical_analysis_contracts.md`

**Interfaces:**
- Produces: canonical `MetricUnit` multipliers; canonical `SourcedProportion`; non-negative
  `BusinessImpactInputs.exposure_frequency`; public `ProjectedValue(value: MeasuredValue,
  uncertainty: UncertaintyBundle)`; independently uncertain projection outputs; documented public
  contracts; unchanged `schema_version="1"` and `POST /ask`.

- [ ] **Step 1: Add RED tests for standardized multipliers and canonical sourced proportions**

Parameterize all four standardized scales and mismatched multipliers in
`tests/test_analysis_estimates.py`, expecting `MetricUnit` validation to fail. Add
`tests/test_business_impact_contracts.py` cases proving `SourcedProportion` rejects otherwise-valid
percent, percentage-point, and basis-point units while accepting the canonical normalized unit.

- [ ] **Step 2: Add RED tests for exposure frequency and projected output uncertainty**

Assert negative `exposure_frequency.value` is rejected and zero is accepted. Construct
`ProjectedValue` independently for outcome and finance fields, assert canonical serialization and
validated round trip preserve both bundles, and assert projection-level `uncertainty` is absent
from output and rejected as an extra input.

- [ ] **Step 3: Add RED documentation audit**

Add an AST/`inspect` audit over public analysis modules, exported runtime models, and enums. Require
useful docstrings without asserting private implementation symbols; document type aliases through
module docstrings and nearby source comments rather than wrapper classes.

- [ ] **Step 4: Run focused RED and capture expected failures**

Run: `uv run pytest tests/test_analysis_estimates.py tests/test_business_impact_contracts.py tests/test_analysis_contract_serialization.py tests/test_analysis_contract_documentation.py -q`

Expected: failures identify unconstrained standardized multipliers, permissive sourced proportion
units, accepted negative frequency, missing `ProjectedValue`, the old shared uncertainty shape, and
missing public documentation.

- [ ] **Step 5: Implement the minimal GREEN schema changes**

Enforce exact standardized multipliers in `MetricUnit`; keep raw/custom explicit positive values.
Require canonical dimension, scale, and multiplier in `SourcedProportion`. Validate only
`exposure_frequency.value >= 0`. Add and export `ProjectedValue`, change both projection output
fields to that model, remove the shared uncertainty field, and update adapters, fixtures, and
serialization without changing schema version.

- [ ] **Step 6: Complete public documentation and Phase 4 examples**

Add concise useful module and public enum/model/type documentation throughout the analysis package.
Update `docs/phase4/statistical_analysis_contracts.md` to explain canonical sourced proportions and
show each projected output as `{value, uncertainty}`.

- [ ] **Step 7: Run focused GREEN**

Run the Step 4 command again.

Expected: all focused contract tests pass.

- [ ] **Step 8: Run fresh repository verification and commit once**

Run `uv lock --check`, `uv run mypy --strict packages/experiments/analysis`,
`uv run ruff format --check .`, `uv run ruff check .`, `uv run pytest`, documentation example
validation, `git diff --check`, and a final scope/status audit. Only after all are green, commit the
focused hardening as `[Fix] Clarify analysis unit and projection semantics` and write exact evidence
to `.superpowers/sdd/final-review-fixes-report.md`.

---

### Task 8: Perform Fresh Full Verification and Review the Change

**Files:**
- Review: all files from Tasks 1-7.
- Modify only when a verification failure is reproduced by a failing test and fixed through RED/GREEN.

**Interfaces:**
- Consumes: complete contract implementation, tests, documentation, and lockfile.
- Produces: fresh evidence for formatting, linting, type safety, tests, compatibility, and scope.

- [ ] **Step 1: Invoke the verification-before-completion skill**

Use `superpowers:verification-before-completion` before making any completion claim or final commit.

- [ ] **Step 2: Verify dependency consistency and formatting**

Run: `uv lock --check`

Expected: exit 0.

Run: `uv run ruff format --check .`

Expected: exit 0 with no files requiring formatting.

- [ ] **Step 3: Verify lint and static typing**

Run: `uv run ruff check .`

Expected: `All checks passed!`

Run: `uv run mypy packages/experiments/analysis`

Expected: success with no issues found.

- [ ] **Step 4: Run focused contract and compatibility suites**

Run: `uv run pytest tests/test_analysis_requests.py tests/test_analysis_estimates.py tests/test_analysis_results.py tests/test_business_impact_contracts.py tests/test_analysis_contract_serialization.py tests/test_package_imports.py tests/test_agent_state.py tests/test_api_ask.py tests/test_experiment_analysis_agent.py tests/test_business_impact_agent.py -q`

Expected: all contract tests plus the 48-test pre-change compatibility baseline pass without
database, network, LLM, judge, or telemetry requirements.

- [ ] **Step 5: Run the full repository test suite**

Run: `uv run pytest`

Expected: all required tests pass; database-backed tests may report their existing documented skips
when `DATABASE_URL` is unset. No new test may skip.

- [ ] **Step 6: Review scope, whitespace, imports, and forbidden dependencies**

Run: `git diff --check`

Expected: no whitespace errors.

Run: `git diff --stat main...HEAD`

Expected: only analysis contracts, their tests, mypy configuration/lockfile, design/plan artifacts,
and Phase 4 architecture documentation.

Run: `rg -n "numpy|pandas|scipy|statsmodels|sklearn|econml|dowhy|ragas|deepeval|langgraph" packages/experiments/analysis tests/test_analysis_*.py tests/test_business_impact_contracts.py`

Expected: no production imports of forbidden third-party types. Documentation may mention forbidden
libraries only to state that they are not dependencies.

- [ ] **Step 7: Commit any remaining reviewed artifacts after verification**

Force-add the ignored Superpowers files together with no production changes:

```powershell
git add -f docs/superpowers/specs/2026-07-17-statistical-causal-contracts-design.md docs/superpowers/plans/2026-07-17-statistical-causal-contracts.md
git commit -m "[Improvement] Record statistical contract design"
```

Do not push, open a pull request, merge, or close issue #88 unless the user separately requests that
action.

---

## Completion Handoff

The final response must report:

1. files changed;
2. contracts introduced;
3. major design decisions;
4. enforced versus deferred validation;
5. exact verification commands and results;
6. full-test and skip counts;
7. backward-compatibility assessment;
8. deferred work for issue #89 and later Phase 4 issues;
9. unresolved risks;
10. commit and push status.

Every success statement must be based on fresh Task 8 output.
