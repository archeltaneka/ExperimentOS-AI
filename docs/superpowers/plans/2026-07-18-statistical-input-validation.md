# Statistical Input Validation and Eligibility Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build deterministic, typed pre-estimator validation that reports structural invalidity,
insufficient information, warnings, method availability, and complete eligibility summaries.

**Architecture:** Add a focused `packages.experiments.analysis.validation` package around the
existing immutable Phase 4 contracts. An immutable table snapshot and explicit column binding feed
fixed-order request, data, and design rule modules; a service aggregates stable diagnostics and
records safe metadata through the existing observability abstraction.

**Tech Stack:** Python 3.12, Pydantic v2, standard-library dataclasses and datetime/math utilities,
pytest, Ruff, mypy, uv, and the existing ExperimentOS observability provider abstraction.

## Global Constraints

- Issue #89 is the source of truth; no estimator or descriptive-result calculation is implemented.
- Preserve all Phase 1-3 behavior and existing Phase 4 request/result serialization.
- Do not change `POST /ask`, LangGraph routing, persistence models, or Alembic migrations.
- Do not add pandas, Polars, NumPy, SciPy, Statsmodels, EconML, DoWhy, or vendor SDK dependencies.
- Never mutate, filter, impute, coerce, winsorize, or relabel caller data.
- Expected invalidity returns structured results; exceptions remain for programmer/internal failures.
- Diagnostic content and ordering must be deterministic and tests must remain entirely offline.
- Operational thresholds are not power guarantees or claims of causal validity.

---

## File Map

- `packages/experiments/analysis/validation/table.py`: immutable table snapshots.
- `packages/experiments/analysis/validation/bindings.py`: analytical-role column bindings.
- `packages/experiments/analysis/validation/policy.py`: validated operational defaults.
- `packages/experiments/analysis/validation/models.py`: diagnostics, summaries, and final result.
- `packages/experiments/analysis/validation/context.py`: internal normalized rule context.
- `packages/experiments/analysis/validation/criteria.py`: shared typed population/segment criteria.
- `packages/experiments/analysis/validation/capabilities.py`: centralized method capability registry.
- `packages/experiments/analysis/validation/request_rules.py`: cross-contract checks.
- `packages/experiments/analysis/validation/data_rules.py`: schema, treatment, outcome, missingness,
  allocation, and sample rules.
- `packages/experiments/analysis/validation/design_rules.py`: units, covariates, time, and segments.
- `packages/experiments/analysis/validation/service.py`: orchestration, aggregation, observability.
- `packages/experiments/analysis/validation/__init__.py`: validation public internal surface.
- `packages/experiments/analysis/__init__.py`: deliberate re-exports only.
- `packages/experiments/analysis/serialization.py`: validation-result decoder and adapter.
- `tests/analysis_validation_fixtures.py`: compact deterministic fixtures.
- `tests/test_analysis_validation_contracts.py`: table, bindings, policy, result, serialization.
- `tests/test_analysis_validation_request_rules.py`: compatibility and capability rules.
- `tests/test_analysis_validation_data_rules.py`: schema, treatment, outcome, missingness, samples.
- `tests/test_analysis_validation_design_rules.py`: units, covariates, time, segments.
- `tests/test_analysis_validation_service.py`: precedence, abstention, ordering, no estimates.
- `tests/test_analysis_validation_observability.py`: safe spans and provider isolation.
- `packages/evals/analysis_validation_cases.py`: deterministic structured golden cases.
- `tests/test_analysis_validation_evaluation.py`: golden case coverage and consumption.
- `docs/phase4/statistical_input_validation.md`: architecture and five result examples.
- `docs/architecture.md`: Phase 4 eligibility boundary.
- `tests/test_analysis_validation_documentation.py`: documentation boundaries and examples.

---

### Task 1: Immutable Table, Bindings, Policy, and Result Contracts

**Files:**
- Create: `packages/experiments/analysis/validation/table.py`
- Create: `packages/experiments/analysis/validation/bindings.py`
- Create: `packages/experiments/analysis/validation/policy.py`
- Create: `packages/experiments/analysis/validation/models.py`
- Create: `packages/experiments/analysis/validation/__init__.py`
- Create: `tests/analysis_validation_fixtures.py`
- Create: `tests/test_analysis_validation_contracts.py`

**Interfaces:**
- Produces: `AnalysisTable`, `AnalysisDataBinding`, `OutcomeDataBinding`,
  `MetricColumnBinding`, `ValidationPolicy`, `EligibilityDiagnostic`, summary contracts,
  `MethodSupportAssessment`, and `EligibilityValidationResult`.
- Consumes: existing `ContractModel`, `AnalysisStatus`, `DiagnosticSeverity`,
  `DiagnosticOutcome`, `AbstentionReason`, `NonEmptyStr`, and Phase 4 scalar aliases.

- [ ] **Step 1: Write failing table and policy tests**

```python
def test_analysis_table_snapshots_records_without_mutating_callers() -> None:
    records = [{"unit": "u1", "arm": "control", "outcome": 0}]
    table = AnalysisTable.from_records(records)
    records[0]["outcome"] = 1
    assert table.columns == ("unit", "arm", "outcome")
    assert table.rows == (("u1", "control", 0),)


def test_validation_policy_defaults_and_invalid_thresholds() -> None:
    policy = ValidationPolicy()
    assert policy.policy_version == "analysis-validation-v1"
    assert (policy.minimum_total, policy.minimum_per_arm) == (30, 10)
    with pytest.raises(ValidationError):
        ValidationPolicy(allocation_warning_deviation=0.3, allocation_blocking_deviation=0.2)
```

- [ ] **Step 2: Run the tests and verify the missing-package failure**

Run: `uv run pytest tests/test_analysis_validation_contracts.py -q`

Expected: collection fails with `ModuleNotFoundError` for
`packages.experiments.analysis.validation`.

- [ ] **Step 3: Implement the immutable table, binding, and policy primitives**

```python
@dataclass(frozen=True)
class AnalysisTable:
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]

    def __post_init__(self) -> None:
        if any(len(row) != len(self.columns) for row in self.rows):
            raise AnalysisTableError("every row must match the declared column count")

    @classmethod
    def from_records(cls, records: Sequence[Mapping[str, object]]) -> AnalysisTable:
        snapshots = tuple(dict(record) for record in records)
        columns = tuple(snapshots[0]) if snapshots else ()
        if any(set(record) != set(columns) for record in snapshots):
            raise AnalysisTableError("every record must contain the same columns")
        return cls(columns=columns, rows=tuple(tuple(record[name] for name in columns) for record in snapshots))


class ValidationPolicy(ContractModel):
    policy_version: NonEmptyStr = "analysis-validation-v1"
    minimum_total: int = Field(default=30, ge=1)
    minimum_per_arm: int = Field(default=10, ge=1)
    weak_total: int = Field(default=100, ge=1)
    weak_per_arm: int = Field(default=30, ge=1)
    minimum_per_segment_arm: int = Field(default=5, ge=1)
    minimum_clusters: int = Field(default=4, ge=2)
    weak_clusters: int = Field(default=20, ge=2)
    allocation_warning_deviation: Probability = 0.10
    allocation_blocking_deviation: Probability = 0.25
    maximum_segment_cardinality: int = Field(default=50, ge=1)
    maximum_outcome_missingness: Probability | None = None
    maximum_differential_missingness: Probability | None = None
```

- [ ] **Step 4: Write failing diagnostic and result-contract tests**

```python
def test_validation_result_has_no_estimate_and_serializes() -> None:
    result = eligible_result_fixture()
    payload = to_canonical_json(result)
    assert '"outcome_type":"eligibility_validation"' in payload
    assert "estimate" not in result.model_dump(mode="json")


def test_diagnostic_context_order_is_canonical() -> None:
    diagnostic = diagnostic_fixture(context={"z": 2, "a": 1})
    assert [entry.key for entry in diagnostic.context] == ["a", "z"]


def test_policy_defaults_ignore_ambient_environment(monkeypatch) -> None:
    monkeypatch.setenv("EXPERIMENTOS_MINIMUM_TOTAL", "999")
    assert ValidationPolicy().minimum_total == 30
```

- [ ] **Step 5: Implement diagnostics, summaries, and result invariants**

Use `StrEnum` values for `ValidationCategory` and `DiagnosticDisposition`. Represent context as
`tuple[DiagnosticContextEntry, ...]`, sorted by key at construction. Add a model validator requiring
blocking/warning collections to be exact deterministic subsets of `diagnostics`, requiring an
abstention reason only for `ineligible` or `needs_more_data`, and forbidding executable method
support when the final status is ineligible.

```python
class EligibilityDiagnostic(ContractModel):
    code: NonEmptyStr
    category: ValidationCategory
    severity: DiagnosticSeverity
    outcome: DiagnosticOutcome
    disposition: DiagnosticDisposition
    message: NonEmptyStr
    context: tuple[DiagnosticContextEntry, ...] = ()
    recommended_action: NonEmptyStr | None = None


class EligibilityValidationResult(ContractModel):
    outcome_type: Literal["eligibility_validation"] = "eligibility_validation"
    validation_version: Literal["1"] = "1"
    status: EligibilityStatus
    requested_method: NonEmptyStr | None
    experiment_design: NonEmptyStr | None
    diagnostics: tuple[EligibilityDiagnostic, ...]
    blocking_diagnostics: tuple[EligibilityDiagnostic, ...]
    warnings: tuple[EligibilityDiagnostic, ...]
    dataset_summary: DatasetSummary
    treatment_summary: TreatmentSummary
    outcome_summary: OutcomeSummary
    missingness_summary: tuple[MissingnessSummary, ...]
    unit_integrity_summary: UnitIntegritySummary
    time_summary: TimeDesignSummary | None
    segment_summary: SegmentEligibilitySummary | None
    method_support: MethodSupportAssessment
    abstention_reason: AbstentionReason | None
    policy_version: NonEmptyStr
    configuration_provenance: NonEmptyStr
```

- [ ] **Step 6: Run focused tests and commit**

Run: `uv run pytest tests/test_analysis_validation_contracts.py -q`

Expected: all tests pass.

Run: `uv run mypy packages/experiments/analysis/validation`

Expected: `Success: no issues found`.

Run: `git add packages/experiments/analysis/validation tests/analysis_validation_fixtures.py tests/test_analysis_validation_contracts.py`

Commit: `git commit -m "[New Feature] Add validation domain contracts"`

---

### Task 2: Capability Registry and Request Consistency Rules

**Files:**
- Create: `packages/experiments/analysis/validation/context.py`
- Create: `packages/experiments/analysis/validation/capabilities.py`
- Create: `packages/experiments/analysis/validation/request_rules.py`
- Create: `tests/test_analysis_validation_request_rules.py`
- Modify: `tests/analysis_validation_fixtures.py`

**Interfaces:**
- Consumes: Task 1 contracts plus `AnalysisRequest` and all Phase 4 method/design enums.
- Produces: `ValidationContext`, `MethodCapabilityRegistry.assess`, and
  `validate_request_consistency(context)`.

- [ ] **Step 1: Write the failing capability inventory tests**

```python
@pytest.mark.parametrize("request_factory", [randomized_request, quasi_experimental_request, observational_request])
def test_every_contract_method_has_central_capability_entry(request_factory) -> None:
    request = request_factory()
    capability = MethodCapabilityRegistry.default().for_request(request)
    assert capability.contract_status is MethodContractStatus.SUPPORTED
    assert capability.implementation_status is MethodImplementationStatus.UNAVAILABLE


def test_registry_can_declare_future_implementation_without_an_estimator() -> None:
    registry = MethodCapabilityRegistry.with_implemented_methods(
        (RandomizedAnalysisMethod.FIXED_HORIZON_AB,)
    )
    assert registry.for_request(randomized_request()).implementation_status.value == "available"
```

- [ ] **Step 2: Run and verify RED**

Run: `uv run pytest tests/test_analysis_validation_request_rules.py -q`

Expected: import failure for `MethodCapabilityRegistry`.

- [ ] **Step 3: Implement the capability registry**

Build the default tuple from every current randomized, quasi-experimental, and observational enum
member. Store design type, method value, contract support, and implementation availability in one
immutable registry. Reject duplicate `(design_type, method)` entries.

- [ ] **Step 4: Write table-driven request-rule tests**

```python
@pytest.mark.parametrize(
    ("mutator", "expected_code"),
    [
        (with_difference_in_proportions_on_continuous_metric, "request.metric_estimand_incompatible"),
        (with_post_treatment_adjustment, "covariate.post_treatment_leakage"),
        (with_unknown_adjustment_timing, "covariate.timing_unknown"),
        (with_pre_treatment_covariate_measured_after_assignment, "covariate.measurement_after_treatment"),
        (with_outcome_reused_as_covariate, "request.covariate_role_conflict"),
        (with_duplicate_covariate, "request.duplicate_covariate"),
        (with_unclustered_order_analysis_for_account_randomization, "unit.cluster_required"),
    ],
)
def test_request_consistency_codes(mutator, expected_code: str) -> None:
    diagnostics = validate_request_consistency(context_for(mutator(randomized_request())))
    assert expected_code in {item.code for item in diagnostics}
```

- [ ] **Step 5: Implement request consistency in fixed rule order**

Rules must cover metric/estimand compatibility, CATE segment consistency, method prerequisites,
duplicate covariates, treatment/outcome/identifier/segment role conflicts, post-treatment leakage,
unknown causal timing, and randomization/observation/clustering compatibility. Reuse constructor
guarantees and do not retest equal arms, invalid periods, or malformed confidence levels.

- [ ] **Step 6: Run tests and commit**

Run: `uv run pytest tests/test_analysis_validation_request_rules.py tests/test_analysis_requests.py -q`

Expected: all tests pass.

Run: `git add packages/experiments/analysis/validation/context.py packages/experiments/analysis/validation/capabilities.py packages/experiments/analysis/validation/request_rules.py tests/analysis_validation_fixtures.py tests/test_analysis_validation_request_rules.py`

Commit: `git commit -m "[New Feature] Add analysis capability and request rules"`

---

### Task 3: Schema, Treatment, Outcome, Missingness, Allocation, and Sample Rules

**Files:**
- Create: `packages/experiments/analysis/validation/criteria.py`
- Create: `packages/experiments/analysis/validation/data_rules.py`
- Create: `tests/test_analysis_validation_data_rules.py`
- Modify: `tests/analysis_validation_fixtures.py`

**Interfaces:**
- Consumes: `ValidationContext`.
- Produces: `evaluate_criteria` plus `DataRuleResult` containing diagnostics,
  dataset/treatment/outcome/missingness summaries, observed allocation, selected population indexes,
  and derived valid-row indexes. It never returns a mutated table.

- [ ] **Step 1: Write failing schema and arm tests**

```python
@pytest.mark.parametrize(
    ("table", "code"),
    [
        (AnalysisTable(columns=("unit", "arm", "arm"), rows=(("u1", "control", "control"),)), "schema.duplicate_column"),
        (AnalysisTable(columns=(), rows=()), "schema.empty_dataset"),
        (table_without("arm"), "schema.required_column_missing"),
        (table_with_arm_values(("control", "variant-b")), "treatment.unexpected_value"),
        (table_with_arm_values((None, "treatment")), "treatment.assignment_missing"),
        (control_only_table(), "treatment.arm_missing"),
    ],
)
def test_schema_and_treatment_diagnostics(table: AnalysisTable, code: str) -> None:
    result = validate_data(context_for_table(table))
    assert code in {item.code for item in result.diagnostics}


def test_population_criteria_preserve_before_and_after_counts() -> None:
    result = validate_data(context_with_country_population(("AU", "NZ", "AU")))
    assert result.dataset_summary.input_row_count == 3
    assert result.dataset_summary.population_row_count == 2
    assert result.population_row_indexes == (0, 2)
```

- [ ] **Step 2: Run and verify RED**

Run: `uv run pytest tests/test_analysis_validation_data_rules.py -k "schema or treatment" -q`

Expected: import failure for `validate_data`.

- [ ] **Step 3: Implement shared criteria, schema, population, and exact typed arm validation**

Validate duplicate names before indexing. Compare treatment values with exact type and equality so
`True`, `1`, and non-empty strings cannot be interpreted through truthiness. Return unknown, missing,
treatment, and control counts in `TreatmentSummary`. Apply current `CriterionOperator` values through
one shared evaluator, preserve input and selected population counts, and emit `population.empty` when
an explicitly selected population has no rows.

- [ ] **Step 4: Write failing outcome matrix tests**

```python
@pytest.mark.parametrize(
    ("metric_type", "values", "code"),
    [
        (MetricType.BINARY, (0, 2, 1), "outcome.invalid_binary"),
        (MetricType.CONTINUOUS, (1.0, float("nan"), 2.0), "outcome.non_finite"),
        (MetricType.CONTINUOUS, (1.0, float("inf"), 2.0), "outcome.non_finite"),
        (MetricType.CONTINUOUS, ("1.0", 2.0, 3.0), "schema.outcome_not_numeric"),
        (MetricType.COUNT, (1, -1, 2), "outcome.negative"),
        (MetricType.CONTINUOUS, (5.0, 5.0, 5.0), "outcome.zero_variance"),
    ],
)
def test_outcome_diagnostics(metric_type, values, code: str) -> None:
    result = validate_data(context_with_outcomes(metric_type, values))
    assert code in {item.code for item in result.diagnostics}


def test_ratio_denominator_reports_zero_and_invalid_sign() -> None:
    result = validate_data(ratio_context(numerators=(1, 2), denominators=(0, -1)))
    assert {item.code for item in result.diagnostics} >= {
        "outcome.denominator_zero",
        "outcome.denominator_invalid_sign",
    }
```

- [ ] **Step 5: Implement outcome and missingness summaries without dropping rows**

Classify missing, invalid-type, non-finite, binary-invalid, negative, bounds-invalid, and ratio-invalid
rows separately. Build derived valid indexes only for summaries. Always emit role-specific missingness
summaries; emit `missingness.differential` only under an explicit configured threshold.

- [ ] **Step 6: Write failing information and allocation tests**

```python
def test_insufficient_samples_are_needs_more_data_diagnostics() -> None:
    diagnostics = validate_data(context_with_arm_sizes(treatment=9, control=10)).diagnostics
    item = next(item for item in diagnostics if item.code == "sample.arm_insufficient")
    assert item.disposition is DiagnosticDisposition.NEEDS_MORE_DATA


def test_declared_allocation_deviation_uses_policy_thresholds() -> None:
    warning = validate_data(context_with_arm_sizes(treatment=35, control=65)).diagnostics
    assert "allocation.deviation_warning" in {item.code for item in warning}
```

- [ ] **Step 7: Implement sample and allocation rules, run, and commit**

Run: `uv run pytest tests/test_analysis_validation_data_rules.py -q`

Expected: all tests pass.

Run: `git add packages/experiments/analysis/validation/criteria.py packages/experiments/analysis/validation/data_rules.py tests/analysis_validation_fixtures.py tests/test_analysis_validation_data_rules.py`

Commit: `git commit -m "[New Feature] Add dataset population and outcome validation"`

---

### Task 4: Unit, Covariate, Time, and Segment Rules

**Files:**
- Create: `packages/experiments/analysis/validation/design_rules.py`
- Create: `tests/test_analysis_validation_design_rules.py`
- Modify: `tests/analysis_validation_fixtures.py`

**Interfaces:**
- Consumes: `ValidationContext` and `DataRuleResult`.
- Produces: `DesignRuleResult` containing diagnostics plus unit, time, and segment summaries.

- [ ] **Step 1: Write failing unit-integrity tests**

```python
@pytest.mark.parametrize(
    ("context_factory", "code"),
    [
        (context_with_missing_unit, "unit.identifier_missing"),
        (context_with_duplicate_single_row_units, "unit.duplicate_observation"),
        (context_with_randomization_unit_in_both_arms, "treatment.unit_multiple_assignments"),
        (context_with_switching_unit, "treatment.switching"),
        (context_with_repeated_rows_without_cluster, "unit.repeated_without_clustering"),
        (context_with_missing_cluster, "unit.cluster_identifier_missing"),
        (context_with_three_clusters, "sample.cluster_insufficient"),
    ],
)
def test_unit_integrity(context_factory, code: str) -> None:
    result = validate_design(context_factory(), valid_data_result())
    assert code in {item.code for item in result.diagnostics}
```

- [ ] **Step 2: Run and verify RED**

Run: `uv run pytest tests/test_analysis_validation_design_rules.py -k unit -q`

Expected: import failure for `validate_design`.

- [ ] **Step 3: Implement unit and cluster checks**

Group by exact non-missing identifiers. Report duplicates, repeated measurements, conflicting arm
assignments, switching, missing clusters, cluster counts, and randomization/observation mismatch.
Do not calculate standard errors.

- [ ] **Step 4: Write failing covariate and time tests**

```python
@pytest.mark.parametrize(
    ("context_factory", "code"),
    [
        (context_with_covariate_missing_in_required_period, "covariate.period_unavailable"),
        (context_with_missing_optional_covariate_values, "covariate.missing"),
    ],
)
def test_covariate_data_availability(context_factory, code: str) -> None:
    diagnostics = validate_design(context_factory(), valid_data_result()).diagnostics
    assert code in {item.code for item in diagnostics}


def test_invalid_and_missing_period_observations_are_structured() -> None:
    result = validate_design(context_with_invalid_period_rows(), valid_data_result())
    assert {item.code for item in result.diagnostics} >= {
        "time.invalid_timestamp",
        "time.period_coverage_missing",
    }
```

- [ ] **Step 5: Implement explicit covariate availability and period coverage**

Parse ISO 8601 or timezone-aware `datetime` values for checking only. Never replace cells. Apply
declared `TimePeriod` bounds, report units missing required pre/post observations, and detect
assignment instability where treatment timing data are supplied. Request-level leakage remains owned
by `request_rules.py`; this module validates only actual data availability. Never infer timing from
names.

- [ ] **Step 6: Write failing segment tests**

```python
@pytest.mark.parametrize(
    ("context_factory", "code"),
    [
        (context_with_missing_segment_column, "segment.column_missing"),
        (context_with_absent_segment_value, "segment.value_absent"),
        (context_with_segment_missing_control, "segment.arm_missing"),
        (context_with_small_segment, "segment.insufficient_sample"),
        (context_with_missing_segment_assignment, "segment.missing_assignment"),
        (context_with_high_cardinality_segment, "segment.high_cardinality"),
    ],
)
def test_segment_diagnostics(context_factory, code: str) -> None:
    diagnostics = validate_design(context_factory(), valid_data_result()).diagnostics
    assert code in {item.code for item in diagnostics}
```

- [ ] **Step 7: Implement segment criteria and commit**

Reuse the shared `evaluate_criteria` helper for every current `CriterionOperator`. Failed comparisons
from incompatible values become structured segment diagnostics, not broad service exceptions.

Run: `uv run pytest tests/test_analysis_validation_design_rules.py -q`

Expected: all tests pass.

Run: `git add packages/experiments/analysis/validation/design_rules.py tests/analysis_validation_fixtures.py tests/test_analysis_validation_design_rules.py`

Commit: `git commit -m "[New Feature] Add unit time and segment eligibility rules"`

---

### Task 5: Orchestration, Status Precedence, Payload Translation, and Serialization

**Files:**
- Create: `packages/experiments/analysis/validation/service.py`
- Create: `tests/test_analysis_validation_service.py`
- Modify: `packages/experiments/analysis/validation/__init__.py`
- Modify: `packages/experiments/analysis/serialization.py`
- Modify: `packages/experiments/analysis/__init__.py`
- Modify: `tests/test_analysis_contract_serialization.py`

**Interfaces:**
- Consumes: all prior rule outputs.
- Produces: `AnalysisEligibilityService.validate`, `validate_payload`,
  `ELIGIBILITY_VALIDATION_RESULT_ADAPTER`, and `eligibility_validation_result_from_json`.

- [ ] **Step 1: Write failing precedence and no-estimate tests**

```python
@pytest.mark.parametrize(
    ("diagnostics", "status"),
    [
        ((blocking_diagnostic(), needs_data_diagnostic(), warning_diagnostic()), AnalysisStatus.INELIGIBLE),
        ((needs_data_diagnostic(), warning_diagnostic()), AnalysisStatus.NEEDS_MORE_DATA),
        ((warning_diagnostic(),), AnalysisStatus.ELIGIBLE_WITH_WARNINGS),
        ((), AnalysisStatus.ELIGIBLE),
    ],
)
def test_status_precedence(diagnostics, status) -> None:
    assert aggregate_status(diagnostics) is status


def test_service_never_returns_an_estimate_field() -> None:
    result = implemented_service().validate(randomized_request(), eligible_table(), binding())
    assert result.status is AnalysisStatus.ELIGIBLE
    assert "estimate" not in result.model_dump(mode="json")


def test_identical_inputs_have_identical_diagnostic_order_and_content() -> None:
    service = implemented_service()
    first = service.validate(randomized_request(), multi_issue_table(), binding())
    second = service.validate(randomized_request(), multi_issue_table(), binding())
    assert first.diagnostics == second.diagnostics
    assert to_canonical_json(first) == to_canonical_json(second)
```

- [ ] **Step 2: Run and verify RED**

Run: `uv run pytest tests/test_analysis_validation_service.py -q`

Expected: import failure for `AnalysisEligibilityService`.

- [ ] **Step 3: Implement fixed orchestration and aggregation**

```python
def aggregate_status(diagnostics: tuple[EligibilityDiagnostic, ...]) -> EligibilityStatus:
    dispositions = {item.disposition for item in diagnostics}
    if DiagnosticDisposition.BLOCKING in dispositions:
        return AnalysisStatus.INELIGIBLE
    if DiagnosticDisposition.NEEDS_MORE_DATA in dispositions:
        return AnalysisStatus.NEEDS_MORE_DATA
    if DiagnosticDisposition.WARNING in dispositions:
        return AnalysisStatus.ELIGIBLE_WITH_WARNINGS
    return AnalysisStatus.ELIGIBLE
```

The service executes request, data, and design rules in that order. Dependent rules emit unavailable
diagnostics after unreadable schema instead of throwing. It creates one abstention reason from the
first highest-precedence diagnostic and includes all blocking or needs-data codes in deterministic
`missing_or_invalid_information` order.

- [ ] **Step 4: Write failing method-unavailable and payload tests**

```python
def test_structurally_valid_unimplemented_method_abstains() -> None:
    result = AnalysisEligibilityService().validate(randomized_request(), eligible_table(), binding())
    assert result.status is AnalysisStatus.INELIGIBLE
    assert result.method_support.implementation_status.value == "unavailable"
    assert result.abstention_reason.code == "method.implementation_unavailable"


def test_invalid_request_payload_becomes_owned_diagnostic() -> None:
    payload = randomized_request().model_dump(mode="json")
    payload["control"]["assignment_value"] = payload["treatment"]["assignment_value"]
    result = AnalysisEligibilityService().validate_payload(payload, eligible_table(), binding())
    assert result.status is AnalysisStatus.INELIGIBLE
    assert result.diagnostics[0].code == "request.contract_invalid"


def test_validation_result_round_trips_through_public_decoder() -> None:
    result = implemented_service().validate(randomized_request(), eligible_table(), binding())
    assert eligibility_validation_result_from_json(to_canonical_json(result)) == result
```

- [ ] **Step 5: Implement exact `ValidationError` translation and public serialization**

Catch only `pydantic.ValidationError` at the payload boundary. Context may contain error locations and
Pydantic error types but must not include the rejected raw value. Add the adapter and decoder without
changing existing `AnalysisOutcome` variants or canonical payloads.

- [ ] **Step 6: Run service, serialization, and compatibility tests; commit**

Run: `uv run pytest tests/test_analysis_validation_service.py tests/test_analysis_contract_serialization.py tests/test_analysis_results.py -q`

Expected: all tests pass.

Run: `git add packages/experiments/analysis/validation/service.py packages/experiments/analysis/validation/__init__.py packages/experiments/analysis/serialization.py packages/experiments/analysis/__init__.py tests/test_analysis_validation_service.py tests/test_analysis_contract_serialization.py`

Commit: `git commit -m "[New Feature] Add analysis eligibility service"`

---

### Task 6: Safe Observability Integration

**Files:**
- Modify: `packages/experiments/analysis/validation/service.py`
- Create: `tests/test_analysis_validation_observability.py`

**Interfaces:**
- Consumes: existing `BaseObservabilityProvider` and `NoOpObservabilityProvider`.
- Produces: root or child span named `analysis_validation` with low-cardinality metadata.

- [ ] **Step 1: Write failing recording-provider tests**

```python
def test_validation_span_contains_logical_metadata_without_rows() -> None:
    provider = RecordingProvider()
    result = implemented_service(provider=provider).validate(
        randomized_request(), eligible_table(), binding()
    )
    record = provider.records[0]
    assert record.name == "analysis_validation"
    assert record.metadata["status"] == result.status.value
    assert record.metadata["method"] == "fixed_horizon_ab"
    assert record.metadata["blocking_diagnostic_count"] == 0
    serialized = repr(record.inputs) + repr(record.metadata) + repr(record.outputs)
    assert "u1" not in serialized
    assert "outcome_values" not in serialized


def test_provider_failure_does_not_change_validation_result() -> None:
    provider = FailingProvider()
    result = implemented_service(provider=provider).validate(
        randomized_request(), eligible_table(), binding()
    )
    assert result.status is AnalysisStatus.ELIGIBLE
    assert provider.failure_count == 1


def test_unexpected_validator_failure_is_recorded_and_reraised(monkeypatch) -> None:
    provider = RecordingProvider()
    monkeypatch.setattr(service_module, "validate_request_consistency", raising_validator)
    service = implemented_service(provider=provider)
    with pytest.raises(RuntimeError, match="validator failed"):
        service.validate(randomized_request(), eligible_table(), binding())
    assert provider.records[0].error["type"] == "RuntimeError"
```

- [ ] **Step 2: Run and verify RED**

Run: `uv run pytest tests/test_analysis_validation_observability.py -q`

Expected: assertions fail because the service emits no validation span.

- [ ] **Step 3: Add span lifecycle and unexpected-failure recording**

Use `perf_counter` for span duration only; duration is not part of the deterministic validation
result. Record row count, column count, method, design, status, diagnostic counts, and boolean
needs-more-data/method-unavailable flags. Never pass the table or row values as span input.

- [ ] **Step 4: Run tests and commit**

Run: `uv run pytest tests/test_analysis_validation_observability.py tests/test_observability_integration.py tests/test_observability_composite.py -q`

Expected: all tests pass.

Run: `git add packages/experiments/analysis/validation/service.py tests/test_analysis_validation_observability.py`

Commit: `git commit -m "[Improvement] Trace analysis eligibility validation"`

---

### Task 7: Deterministic Golden Evaluation Cases

**Files:**
- Create: `packages/evals/analysis_validation_cases.py`
- Create: `tests/test_analysis_validation_evaluation.py`

**Interfaces:**
- Produces: `ValidationGoldenCase`, `build_validation_golden_cases`, and
  `evaluate_validation_golden_cases` using structured statuses and codes.
- Consumes: `AnalysisEligibilityService` with repository-local fixtures only.

- [ ] **Step 1: Write failing inventory and deterministic-output tests**

```python
REQUIRED_CASE_IDS = {
    "valid-randomized",
    "missing-treatment-column",
    "missing-outcome",
    "empty-dataset",
    "empty-treatment-arm",
    "empty-control-arm",
    "unexpected-treatment-arm",
    "invalid-binary-outcome",
    "non-finite-continuous-outcome",
    "duplicate-randomization-unit",
    "unit-multiple-treatments",
    "post-treatment-leakage",
    "insufficient-total",
    "insufficient-arm",
    "outcome-missingness",
    "invalid-pre-post",
    "missing-cluster",
    "invalid-segment",
    "segment-missing-arm",
    "estimator-unavailable",
    "eligible-with-warnings",
    "fully-eligible",
}


def test_golden_inventory_covers_required_validation_cases() -> None:
    cases = build_validation_golden_cases()
    assert REQUIRED_CASE_IDS <= {case.case_id for case in cases}
    assert len({case.case_id for case in cases}) == len(cases)


def test_golden_evaluation_is_deterministic() -> None:
    first = evaluate_validation_golden_cases(build_validation_golden_cases())
    second = evaluate_validation_golden_cases(build_validation_golden_cases())
    assert first == second
    assert all(case.passed for case in first)
```

- [ ] **Step 2: Run and verify RED**

Run: `uv run pytest tests/test_analysis_validation_evaluation.py -q`

Expected: import failure for `analysis_validation_cases`.

- [ ] **Step 3: Implement immutable cases and structured evaluator**

Each case contains request, table, binding, policy, capability registry, expected status, and expected
diagnostic code set. The evaluator compares only typed status and codes; it never parses messages.
Keep tables compact and deterministic.

- [ ] **Step 4: Run tests and commit**

Run: `uv run pytest tests/test_analysis_validation_evaluation.py -q`

Expected: all tests pass.

Run: `git add packages/evals/analysis_validation_cases.py tests/test_analysis_validation_evaluation.py`

Commit: `git commit -m "[Improvement] Add validation golden evaluation cases"`

---

### Task 8: Phase 4 Documentation and Compatibility

**Files:**
- Create: `docs/phase4/statistical_input_validation.md`
- Modify: `docs/architecture.md`
- Create: `tests/test_analysis_validation_documentation.py`
- Modify: `tests/test_package_imports.py` only if the new public internal exports require inventory.

**Interfaces:**
- Documents every stable status and diagnostic boundary without changing runtime APIs.

- [ ] **Step 1: Write failing documentation tests**

```python
def test_validation_documentation_covers_required_semantics_and_examples() -> None:
    text = Path("docs/phase4/statistical_input_validation.md").read_text(encoding="utf-8")
    for phrase in (
        "Structural validation versus dataset eligibility",
        "eligible_with_warnings",
        "needs_more_data",
        "Diagnostic-code stability",
        "Estimator implementation availability",
        "Post-treatment leakage",
        "Operational thresholds are not statistical power",
        "Observability and data safety",
        "Fully eligible randomized analysis",
        "Estimator unavailable",
    ):
        assert phrase in text
```

- [ ] **Step 2: Run and verify RED**

Run: `uv run pytest tests/test_analysis_validation_documentation.py -q`

Expected: `FileNotFoundError` for the new documentation.

- [ ] **Step 3: Write architecture documentation and five canonical examples**

Include eligible, eligible-with-warnings, post-treatment leakage, needs-more-data, and estimator
unavailable results. Name future estimator consumption, clustering checks, method support, diagnostic
ordering, configuration provenance, and raw-data exclusion from observability.

- [ ] **Step 4: Run documentation and compatibility tests; commit**

Run: `uv run pytest tests/test_analysis_validation_documentation.py tests/test_analysis_contract_documentation.py tests/test_package_imports.py tests/test_api_ask.py tests/test_agent_state.py -q`

Expected: all tests pass.

Run: `git add docs/phase4/statistical_input_validation.md docs/architecture.md tests/test_analysis_validation_documentation.py tests/test_package_imports.py`

Commit: `git commit -m "[Improvement] Document analysis validation eligibility"`

---

### Task 9: Full Verification, Scope Audit, Commit/Push Handoff

**Files:**
- Inspect: all changed files.
- Do not create a pull request and do not merge.

**Interfaces:**
- Proves the complete branch satisfies issue #89 and repository compatibility requirements.

- [ ] **Step 1: Run dependency and formatting validation**

Run: `uv lock --check`

Expected: exit 0 with the lockfile unchanged.

Run: `uv run ruff format --check .`

Expected: all files already formatted.

Run: `uv run ruff check .`

Expected: exit 0 with no lint errors.

- [ ] **Step 2: Run strict Phase 4 typing**

Run: `uv run mypy packages/experiments/analysis`

Expected: `Success: no issues found`.

- [ ] **Step 3: Run focused validation and compatibility tests**

Run: `uv run pytest tests/test_analysis_validation_contracts.py tests/test_analysis_validation_request_rules.py tests/test_analysis_validation_data_rules.py tests/test_analysis_validation_design_rules.py tests/test_analysis_validation_service.py tests/test_analysis_validation_observability.py tests/test_analysis_validation_evaluation.py tests/test_analysis_validation_documentation.py tests/test_analysis_requests.py tests/test_analysis_results.py tests/test_analysis_contract_serialization.py tests/test_api_ask.py tests/test_agent_state.py tests/test_package_imports.py -q`

Expected: all tests pass.

- [ ] **Step 4: Run the complete offline suite**

Run with `DATABASE_URL` unset: `uv run pytest -q`

Expected: all non-database tests pass; database-backed tests report skips rather than failures.

- [ ] **Step 5: Run repository configuration and Phase 3 verification**

Run: `docker compose config --quiet`

Expected: exit 0.

Run: `uv run python scripts/validate_ci_environment.py --no-database --output C:\tmp\experimentos-issue-89-ci-environment.json`

Expected: exit 0.

Run: `uv run python scripts/verify_phase3.py --offline-only --artifact-root C:\tmp\experimentos-issue-89-phase3-artifacts --report-root C:\tmp\experimentos-issue-89-phase3-reports`

Expected: the non-closeout diagnostic completes without an external provider or database; record its
exact recommendation and any documented limitations.

- [ ] **Step 6: Audit the diff against prohibited scope**

Run: `git diff --check`

Run: `git diff --stat origin/main...HEAD`

Run: `git diff origin/main...HEAD -- apps/api migrations packages/agents packages/db pyproject.toml uv.lock`

Expected: no API, migration, agent-routing, database, or dependency changes; any intentional
`pyproject.toml` or lockfile change must be absent because no dependency is added.

Search changed production code for estimator terms and inspect every match:

`rg -n "p_value|confidence_interval|effect_estimate|propensity|econml|dowhy|statsmodels|scipy|pandas|polars" packages/experiments/analysis/validation`

Expected: only documentation/capability vocabulary where required, with no estimation calculations
or imports.

- [ ] **Step 7: Record final commit state and push without PR creation**

Run: `git status -sb`

Expected: clean feature branch.

Run: `git log --oneline origin/main..HEAD`

Expected: design, plan, and verified implementation commits only.

Run: `git push origin feature/issue-89-statistical-input-validation`

Expected: remote branch updated. Do not run `gh pr create` and do not merge.

- [ ] **Step 8: Prepare the final report**

Report files changed, architecture, precedence rules, complete diagnostic-code inventory,
configuration values, evaluation case IDs, observability fields, exact command results, compatibility
impact, unresolved statistical limitations, and explicit confirmation that no estimator, public API
change, live provider, external service, migration, or PR was added.
