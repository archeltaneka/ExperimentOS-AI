"""Deterministic golden cases for the analysis eligibility boundary."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from packages.experiments.analysis import (
    AnalysisDataBinding,
    AnalysisEligibilityService,
    AnalysisRequest,
    AnalysisStatus,
    AnalysisTable,
    AnalysisUnit,
    Clustered,
    ControlDefinition,
    CovariateDefinition,
    CovariateRole,
    CovariateTiming,
    CriterionOperator,
    EligibilityStatus,
    EstimandDefinition,
    EstimandKind,
    MethodCapabilityRegistry,
    MetricColumnBinding,
    MetricDefinition,
    MetricType,
    MetricUnit,
    NoClustering,
    OutcomeDataBinding,
    OutcomeDirection,
    OutcomeMetric,
    PopulationDefinition,
    QuasiExperimentalDesign,
    QuasiExperimentalMethod,
    RandomizedAnalysisMethod,
    RandomizedExperimentDesign,
    RequestedConfidenceLevel,
    SampleCounts,
    SegmentDefinition,
    SelectionCriterion,
    TimePeriod,
    TreatmentDefinition,
    TreatmentRelationship,
    UnitDimension,
    ValidationPolicy,
    ValueScale,
)

_RANDOMIZED_START = datetime(2026, 7, 1, tzinfo=UTC)
_RANDOMIZED_END = datetime(2026, 7, 15, tzinfo=UTC)
_PRE_START = datetime(2026, 6, 1, tzinfo=UTC)
_POST_START = datetime(2026, 7, 1, tzinfo=UTC)
_POST_END = datetime(2026, 7, 15, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class ValidationGoldenCase:
    """One self-contained immutable validation input and structured expectation."""

    case_id: str
    request: AnalysisRequest
    table: AnalysisTable
    binding: AnalysisDataBinding
    policy: ValidationPolicy
    capability_registry: MethodCapabilityRegistry
    expected_status: EligibilityStatus
    expected_diagnostic_codes: frozenset[str]

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("validation golden case_id must not be blank")
        object.__setattr__(
            self,
            "expected_diagnostic_codes",
            frozenset(self.expected_diagnostic_codes),
        )


@dataclass(frozen=True, slots=True)
class ValidationGoldenCaseResult:
    """Structured status/code comparison for one golden case."""

    case_id: str
    expected_status: EligibilityStatus
    actual_status: EligibilityStatus
    expected_diagnostic_codes: tuple[str, ...]
    actual_diagnostic_codes: tuple[str, ...]
    missing_diagnostic_codes: tuple[str, ...]
    unexpected_diagnostic_codes: tuple[str, ...]
    status_matches: bool
    codes_match: bool
    passed: bool


def build_validation_golden_cases() -> tuple[ValidationGoldenCase, ...]:
    """Build the fixed repository-local validation evaluation inventory."""
    compact = _compact_policy()
    available = _randomized_registry()
    cases = (
        _case(
            "valid-randomized",
            request=_randomized_request(metric_type=MetricType.BINARY),
            table=_balanced_table(6),
            policy=compact,
            registry=available,
            status=AnalysisStatus.ELIGIBLE,
        ),
        _case(
            "missing-treatment-column",
            request=_randomized_request(),
            table=AnalysisTable(
                columns=("unit", "outcome"),
                rows=(("u1", 0.0), ("u2", 1.0)),
            ),
            policy=_compact_policy(),
            registry=_randomized_registry(),
            status=AnalysisStatus.INELIGIBLE,
            codes={"schema.required_column_missing", "schema.dependent_rules_unavailable"},
        ),
        _case(
            "missing-outcome",
            request=_randomized_request(),
            table=AnalysisTable(
                columns=("unit", "arm"),
                rows=(("u1", "control"), ("u2", "treatment")),
            ),
            policy=_compact_policy(),
            registry=_randomized_registry(),
            status=AnalysisStatus.INELIGIBLE,
            codes={"schema.required_column_missing", "schema.dependent_rules_unavailable"},
        ),
        _case(
            "empty-dataset",
            request=_randomized_request(),
            table=AnalysisTable(columns=("unit", "arm", "outcome"), rows=()),
            policy=_compact_policy(),
            registry=_randomized_registry(),
            status=AnalysisStatus.INELIGIBLE,
            codes={"schema.empty_dataset", "schema.dependent_rules_unavailable"},
        ),
        _case(
            "empty-treatment-arm",
            request=_randomized_request(),
            table=_assignment_table(("control",) * 4),
            policy=_compact_policy(),
            registry=_randomized_registry(),
            status=AnalysisStatus.INELIGIBLE,
            codes={"treatment.arm_missing", "sample.arm_insufficient"},
        ),
        _case(
            "empty-control-arm",
            request=_randomized_request(),
            table=_assignment_table(("treatment",) * 4),
            policy=_compact_policy(),
            registry=_randomized_registry(),
            status=AnalysisStatus.INELIGIBLE,
            codes={"treatment.arm_missing", "sample.arm_insufficient"},
        ),
        _case(
            "unexpected-treatment-arm",
            request=_randomized_request(),
            table=_assignment_table(("control", "treatment", "variant-b", "control", "treatment")),
            policy=_compact_policy(),
            registry=_randomized_registry(),
            status=AnalysisStatus.INELIGIBLE,
            codes={"treatment.unexpected_value"},
        ),
        _case(
            "invalid-binary-outcome",
            request=_randomized_request(metric_type=MetricType.BINARY),
            table=_outcome_table((0, 1, 2, 1, 0, 1)),
            policy=_compact_policy(),
            registry=_randomized_registry(),
            status=AnalysisStatus.INELIGIBLE,
            codes={"outcome.invalid_binary"},
        ),
        _case(
            "non-finite-continuous-outcome",
            request=_randomized_request(metric_type=MetricType.CONTINUOUS),
            table=_outcome_table((0.0, 1.0, float("inf"), 1.0, 0.0, 1.0)),
            policy=_compact_policy(),
            registry=_randomized_registry(),
            status=AnalysisStatus.INELIGIBLE,
            codes={"outcome.non_finite"},
        ),
        _case(
            "duplicate-randomization-unit",
            request=_randomized_request(),
            table=AnalysisTable(
                columns=("unit", "arm", "outcome"),
                rows=(
                    ("duplicate", "control", 0.0),
                    ("duplicate", "control", 1.0),
                    ("u2", "control", 0.0),
                    ("u3", "treatment", 1.0),
                    ("u4", "treatment", 0.0),
                    ("u5", "treatment", 1.0),
                ),
            ),
            policy=_compact_policy(),
            registry=_randomized_registry(),
            status=AnalysisStatus.INELIGIBLE,
            codes={"unit.duplicate_observation"},
        ),
        _case(
            "unit-multiple-treatments",
            request=_clustered_randomized_request(),
            table=AnalysisTable(
                columns=("order", "account", "arm", "outcome"),
                rows=(
                    ("o1", "conflict", "control", 0.0),
                    ("o2", "conflict", "treatment", 1.0),
                    ("o3", "a3", "control", 1.0),
                    ("o4", "a4", "treatment", 0.0),
                    ("o5", "a5", "control", 0.0),
                    ("o6", "a6", "treatment", 1.0),
                ),
            ),
            binding=_clustered_binding(),
            policy=_compact_policy(),
            registry=_randomized_registry(),
            status=AnalysisStatus.INELIGIBLE,
            codes={"treatment.unit_multiple_assignments"},
        ),
        _post_treatment_leakage_case(),
        _case(
            "insufficient-total",
            request=_randomized_request(),
            table=_balanced_table(6),
            policy=_compact_policy(minimum_total=10, minimum_per_arm=2),
            registry=_randomized_registry(),
            status=AnalysisStatus.NEEDS_MORE_DATA,
            codes={"sample.total_insufficient"},
        ),
        _case(
            "insufficient-arm",
            request=_randomized_request(),
            table=_assignment_table(("treatment",) * 2 + ("control",) * 8),
            policy=_compact_policy(minimum_total=10, minimum_per_arm=3),
            registry=_randomized_registry(),
            status=AnalysisStatus.NEEDS_MORE_DATA,
            codes={"sample.arm_insufficient"},
        ),
        _case(
            "outcome-missingness",
            request=_randomized_request(),
            table=_outcome_table((None, 1.0, 0.0, 1.0, 0.0, 1.0)),
            policy=_compact_policy(maximum_outcome_missingness=0.10),
            registry=_randomized_registry(),
            status=AnalysisStatus.INELIGIBLE,
            codes={"missingness.outcome_exceeds_threshold"},
        ),
        _invalid_pre_post_case(),
        _missing_cluster_case(),
        _invalid_segment_case(),
        _segment_missing_arm_case(),
        _case(
            "estimator-unavailable",
            request=_randomized_request(),
            table=_balanced_table(100),
            policy=ValidationPolicy(),
            registry=MethodCapabilityRegistry.default(),
            status=AnalysisStatus.INELIGIBLE,
            codes={"method.implementation_unavailable"},
        ),
        _case(
            "eligible-with-warnings",
            request=_randomized_request(),
            table=_balanced_table(40),
            policy=ValidationPolicy(),
            registry=_randomized_registry(),
            status=AnalysisStatus.ELIGIBLE_WITH_WARNINGS,
            codes={"sample.total_weak", "sample.arm_weak"},
        ),
        _case(
            "fully-eligible",
            request=_randomized_request(metric_type=MetricType.CONTINUOUS),
            table=_balanced_table(100),
            policy=ValidationPolicy(),
            registry=_randomized_registry(),
            status=AnalysisStatus.ELIGIBLE,
        ),
    )
    return cases


def evaluate_validation_golden_cases(
    cases: Iterable[ValidationGoldenCase],
) -> tuple[ValidationGoldenCaseResult, ...]:
    """Evaluate cases by typed status and diagnostic codes only."""
    results: list[ValidationGoldenCaseResult] = []
    for case in cases:
        service = AnalysisEligibilityService(
            policy=case.policy,
            capability_registry=case.capability_registry,
            configuration_provenance=f"golden-case:{case.case_id}",
        )
        actual = service.validate(case.request, case.table, case.binding)
        expected_codes = tuple(sorted(case.expected_diagnostic_codes))
        actual_code_set = frozenset(diagnostic.code for diagnostic in actual.diagnostics)
        actual_codes = tuple(sorted(actual_code_set))
        missing_codes = tuple(sorted(case.expected_diagnostic_codes - actual_code_set))
        unexpected_codes = tuple(sorted(actual_code_set - case.expected_diagnostic_codes))
        status_matches = actual.status is case.expected_status
        codes_match = not missing_codes and not unexpected_codes
        results.append(
            ValidationGoldenCaseResult(
                case_id=case.case_id,
                expected_status=case.expected_status,
                actual_status=actual.status,
                expected_diagnostic_codes=expected_codes,
                actual_diagnostic_codes=actual_codes,
                missing_diagnostic_codes=missing_codes,
                unexpected_diagnostic_codes=unexpected_codes,
                status_matches=status_matches,
                codes_match=codes_match,
                passed=status_matches and codes_match,
            )
        )
    return tuple(results)


def _case(
    case_id: str,
    *,
    request: AnalysisRequest,
    table: AnalysisTable,
    policy: ValidationPolicy,
    registry: MethodCapabilityRegistry,
    status: EligibilityStatus,
    codes: set[str] | frozenset[str] = frozenset(),
    binding: AnalysisDataBinding | None = None,
) -> ValidationGoldenCase:
    return ValidationGoldenCase(
        case_id=case_id,
        request=request,
        table=table,
        binding=binding if binding is not None else _binding(),
        policy=policy,
        capability_registry=registry,
        expected_status=status,
        expected_diagnostic_codes=frozenset(codes),
    )


def _compact_policy(
    *,
    minimum_total: int = 2,
    minimum_per_arm: int = 1,
    maximum_outcome_missingness: float | None = None,
) -> ValidationPolicy:
    return ValidationPolicy(
        minimum_total=minimum_total,
        minimum_per_arm=minimum_per_arm,
        weak_total=minimum_total,
        weak_per_arm=minimum_per_arm,
        minimum_per_segment_arm=1,
        minimum_clusters=2,
        weak_clusters=2,
        allocation_warning_deviation=1.0,
        allocation_blocking_deviation=1.0,
        maximum_outcome_missingness=maximum_outcome_missingness,
    )


def _randomized_registry() -> MethodCapabilityRegistry:
    return MethodCapabilityRegistry.with_implemented_methods(
        (RandomizedAnalysisMethod.FIXED_HORIZON_AB,)
    )


def _binding() -> AnalysisDataBinding:
    return AnalysisDataBinding(
        treatment_column="arm",
        outcome=OutcomeDataBinding(value_column="outcome"),
        observation_unit_column="unit",
        randomization_unit_column="unit",
    )


def _clustered_binding() -> AnalysisDataBinding:
    return AnalysisDataBinding(
        treatment_column="arm",
        outcome=OutcomeDataBinding(value_column="outcome"),
        observation_unit_column="order",
        randomization_unit_column="account",
        clustering_unit_column="account",
    )


def _randomized_request(
    *,
    metric_type: MetricType = MetricType.PROPORTION,
    covariates: tuple[CovariateDefinition, ...] = (),
    segment: SegmentDefinition | None = None,
    clustering: Clustered | NoClustering | None = None,
) -> AnalysisRequest:
    unit = AnalysisUnit(unit_id="unit", label="Unit")
    return AnalysisRequest(
        population=PopulationDefinition(
            population_id="all_units",
            label="All units",
            criteria=(),
        ),
        segment=segment,
        treatment=TreatmentDefinition(
            treatment_id="treatment",
            label="Treatment",
            assignment_value="treatment",
            description="Receive the treatment.",
        ),
        control=ControlDefinition(
            control_id="control",
            label="Control",
            assignment_value="control",
            description="Remain in control.",
        ),
        outcome=_outcome(metric_type),
        estimand=EstimandDefinition(kind=EstimandKind.INTENTION_TO_TREAT),
        study_design=RandomizedExperimentDesign(
            method=RandomizedAnalysisMethod.FIXED_HORIZON_AB,
            experiment_period=TimePeriod(start=_RANDOMIZED_START, end=_RANDOMIZED_END),
            randomization_unit=unit,
            treatment_allocation=0.5,
            control_allocation=0.5,
        ),
        unit_of_analysis=unit,
        clustering=clustering if clustering is not None else NoClustering(),
        sample_counts=SampleCounts(total=100, treatment=50, control=50),
        uncertainty=RequestedConfidenceLevel(level=0.95),
        covariates=covariates,
    )


def _clustered_randomized_request() -> AnalysisRequest:
    order = AnalysisUnit(unit_id="order", label="Order")
    account = AnalysisUnit(unit_id="account", label="Account")
    request = _randomized_request()
    design = request.study_design
    if not isinstance(design, RandomizedExperimentDesign):
        raise RuntimeError("randomized golden fixture has the wrong design type")
    return request.model_copy(
        update={
            "study_design": design.model_copy(update={"randomization_unit": account}),
            "unit_of_analysis": order,
            "clustering": Clustered(unit=account),
        }
    )


def _outcome(metric_type: MetricType) -> OutcomeMetric:
    return OutcomeMetric(
        metric=MetricDefinition(
            metric_id="outcome",
            label="Outcome",
            metric_type=metric_type,
            unit=MetricUnit(
                dimension=UnitDimension.PROPORTION,
                value_scale=ValueScale.PROPORTION,
                symbol="1",
                scale_to_base_unit=1.0,
            ),
        ),
        direction=OutcomeDirection.INCREASE,
    )


def _balanced_table(row_count: int) -> AnalysisTable:
    return AnalysisTable(
        columns=("unit", "arm", "outcome"),
        rows=tuple(
            (
                f"u{index}",
                "control" if index % 2 == 0 else "treatment",
                float(index % 2),
            )
            for index in range(row_count)
        ),
    )


def _assignment_table(assignments: tuple[str, ...]) -> AnalysisTable:
    return AnalysisTable(
        columns=("unit", "arm", "outcome"),
        rows=tuple(
            (f"u{index}", assignment, float(index % 2))
            for index, assignment in enumerate(assignments)
        ),
    )


def _outcome_table(outcomes: tuple[object, ...]) -> AnalysisTable:
    return AnalysisTable(
        columns=("unit", "arm", "outcome"),
        rows=tuple(
            (
                f"u{index}",
                "control" if index % 2 == 0 else "treatment",
                value,
            )
            for index, value in enumerate(outcomes)
        ),
    )


def _post_treatment_leakage_case() -> ValidationGoldenCase:
    unit = AnalysisUnit(unit_id="unit", label="Unit")
    covariate = CovariateDefinition(
        metric=MetricDefinition(
            metric_id="prior_count",
            label="Prior count",
            metric_type=MetricType.COUNT,
            unit=MetricUnit(
                dimension=UnitDimension.COUNT,
                value_scale=ValueScale.RAW,
                symbol="count",
                scale_to_base_unit=1.0,
            ),
        ),
        timing=CovariateTiming.POST_TREATMENT,
        role=CovariateRole.ADJUSTMENT,
        treatment_relationship=TreatmentRelationship.NONE_KNOWN,
        measurement_period=TimePeriod(
            start=datetime(2026, 5, 1, tzinfo=UTC),
            end=datetime(2026, 6, 1, tzinfo=UTC),
        ),
    )
    request = _randomized_request(covariates=(covariate,), clustering=Clustered(unit=unit))
    binding = _binding().model_copy(
        update={
            "clustering_unit_column": "unit",
            "timestamp_column": "observed_at",
            "covariates": (MetricColumnBinding(metric_id="prior_count", column="prior_count"),),
        }
    )
    rows: list[tuple[object, ...]] = []
    for index in range(4):
        arm = "control" if index % 2 == 0 else "treatment"
        rows.extend(
            (
                (f"u{index}", arm, float(index % 2), index, "2026-05-15T00:00:00Z"),
                (f"u{index}", arm, float((index + 1) % 2), None, "2026-07-05T00:00:00Z"),
            )
        )
    return _case(
        "post-treatment-leakage",
        request=request,
        table=AnalysisTable(
            columns=("unit", "arm", "outcome", "prior_count", "observed_at"),
            rows=tuple(rows),
        ),
        binding=binding,
        policy=_compact_policy(),
        registry=_randomized_registry(),
        status=AnalysisStatus.INELIGIBLE,
        codes={"covariate.post_treatment_leakage"},
    )


def _invalid_pre_post_case() -> ValidationGoldenCase:
    request = _randomized_request().model_copy(
        update={
            "study_design": QuasiExperimentalDesign(
                method=QuasiExperimentalMethod.DIFFERENCE_IN_DIFFERENCES,
                pre_treatment_period=TimePeriod(start=_PRE_START, end=_POST_START),
                post_treatment_period=TimePeriod(start=_POST_START, end=_POST_END),
            ),
            "estimand": EstimandDefinition(kind=EstimandKind.AVERAGE_TREATMENT_EFFECT),
        }
    )
    binding = _binding().model_copy(update={"timestamp_column": "observed_at"})
    table = AnalysisTable(
        columns=("unit", "arm", "outcome", "observed_at"),
        rows=tuple(
            (
                f"u{index}",
                "control" if index % 2 == 0 else "treatment",
                float(index % 2),
                "2026-07-05T00:00:00Z",
            )
            for index in range(6)
        ),
    )
    return _case(
        "invalid-pre-post",
        request=request,
        table=table,
        binding=binding,
        policy=_compact_policy(),
        registry=MethodCapabilityRegistry.with_implemented_methods(
            (QuasiExperimentalMethod.DIFFERENCE_IN_DIFFERENCES,)
        ),
        status=AnalysisStatus.NEEDS_MORE_DATA,
        codes={"time.period_coverage_missing"},
    )


def _missing_cluster_case() -> ValidationGoldenCase:
    return _case(
        "missing-cluster",
        request=_clustered_randomized_request(),
        table=AnalysisTable(
            columns=("order", "account", "arm", "outcome"),
            rows=(
                ("o1", None, "control", 0.0),
                ("o2", "a2", "treatment", 1.0),
                ("o3", "a3", "control", 1.0),
                ("o4", "a4", "treatment", 0.0),
                ("o5", "a5", "control", 0.0),
                ("o6", "a6", "treatment", 1.0),
            ),
        ),
        binding=_clustered_binding(),
        policy=_compact_policy(),
        registry=_randomized_registry(),
        status=AnalysisStatus.INELIGIBLE,
        codes={"unit.randomization_identifier_missing", "unit.cluster_identifier_missing"},
    )


def _invalid_segment_case() -> ValidationGoldenCase:
    segment = SegmentDefinition(
        segment_id="invalid_segment",
        label="Invalid segment",
        criteria=(
            SelectionCriterion(
                attribute="country",
                operator=CriterionOperator.GREATER_THAN,
                value=5,
            ),
        ),
    )
    return _case(
        "invalid-segment",
        request=_randomized_request(segment=segment),
        table=_segment_table(("AU", "NZ", "AU", "NZ", "AU", "NZ")),
        policy=_compact_policy(),
        registry=_randomized_registry(),
        status=AnalysisStatus.INELIGIBLE,
        codes={"segment.criteria_incompatible"},
    )


def _segment_missing_arm_case() -> ValidationGoldenCase:
    segment = SegmentDefinition(
        segment_id="australian_units",
        label="Australian units",
        criteria=(
            SelectionCriterion(
                attribute="country",
                operator=CriterionOperator.EQUAL,
                value="AU",
            ),
        ),
    )
    table = AnalysisTable(
        columns=("unit", "arm", "outcome", "country"),
        rows=(
            ("u0", "treatment", 0.0, "AU"),
            ("u1", "treatment", 1.0, "AU"),
            ("u2", "treatment", 0.0, "AU"),
            ("u3", "control", 1.0, "NZ"),
            ("u4", "control", 0.0, "NZ"),
            ("u5", "control", 1.0, "NZ"),
        ),
    )
    return _case(
        "segment-missing-arm",
        request=_randomized_request(segment=segment),
        table=table,
        policy=_compact_policy(),
        registry=_randomized_registry(),
        status=AnalysisStatus.NEEDS_MORE_DATA,
        codes={"segment.arm_missing"},
    )


def _segment_table(countries: tuple[str, ...]) -> AnalysisTable:
    return AnalysisTable(
        columns=("unit", "arm", "outcome", "country"),
        rows=tuple(
            (
                f"u{index}",
                "control" if index % 2 == 0 else "treatment",
                float(index % 2),
                country,
            )
            for index, country in enumerate(countries)
        ),
    )
