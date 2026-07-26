"""Focused contract tests for descriptive diagnostics and scoped group summaries."""

from __future__ import annotations

from packages.experiments.analysis.descriptive import (
    CountSummary,
    DescriptiveStatisticsInput,
    DescriptiveStatisticsService,
)
from packages.experiments.analysis.metrics import AnalysisUnit, MetricType
from packages.experiments.analysis.populations import (
    CriterionOperator,
    SegmentDefinition,
    SelectionCriterion,
)
from packages.experiments.analysis.study_designs import (
    Clustered,
    NoClustering,
    RandomizedExperimentDesign,
)
from packages.experiments.analysis.validation import (
    AnalysisEligibilityService,
    AnalysisTable,
    MetricColumnBinding,
    ValidationPolicy,
)
from tests.analysis_contract_fixtures import covariate, quasi_experimental_request
from tests.analysis_validation_fixtures import context_for


def _input_for(
    table: AnalysisTable,
    *,
    request_update: dict[str, object] | None = None,
    binding_update: dict[str, object] | None = None,
    policy: ValidationPolicy | None = None,
    allow_data_ineligible: bool = False,
) -> DescriptiveStatisticsInput:
    base = context_for(table=table)
    unit = AnalysisUnit(unit_id="order_id", label="Order")
    metric = base.request.outcome.metric.model_copy(update={"metric_type": MetricType.CONTINUOUS})
    outcome = base.request.outcome.model_copy(update={"metric": metric})
    design = base.request.study_design
    if isinstance(design, RandomizedExperimentDesign):
        design = design.model_copy(update={"randomization_unit": unit})
    request = base.request.model_copy(
        update={
            "outcome": outcome,
            "unit_of_analysis": unit,
            "clustering": NoClustering(),
            "study_design": design,
            **(request_update or {}),
        }
    )
    binding = base.binding.model_copy(
        update={"randomization_unit_column": "order_id", **(binding_update or {})}
    )
    selected_policy = policy or ValidationPolicy(
        minimum_total=1,
        minimum_per_arm=1,
        weak_total=1,
        weak_per_arm=2,
        minimum_per_segment_arm=1,
    )
    context = context_for(request, table=table, binding=binding, policy=selected_policy)
    eligibility = AnalysisEligibilityService(policy=selected_policy).validate(
        context.request, context.table, context.binding
    )
    if not allow_data_ineligible:
        assert eligibility.method_support.data_eligible
    return DescriptiveStatisticsInput(context=context, eligibility=eligibility)


def test_service_returns_fixed_order_distribution_diagnostics() -> None:
    """Catches diagnostics that omit a constant outcome or vary their output ordering."""
    analysis_input = _input_for(
        AnalysisTable(
            columns=("order_id", "account_id", "arm", "outcome"),
            rows=(
                ("o1", "a1", "control", 2.0),
                ("o2", "a2", "treatment", 2.0),
            ),
        ),
        allow_data_ineligible=True,
    )
    # The validated eligibility evidence is intentionally re-used; this test only
    # exercises descriptive reporting of an already-known numerical limitation.
    analysis_input = DescriptiveStatisticsInput(
        context=analysis_input.context,
        eligibility=analysis_input.eligibility.model_copy(
            update={
                "method_support": analysis_input.eligibility.method_support.model_copy(
                    update={"data_eligible": True}
                )
            }
        ),
    )

    result = DescriptiveStatisticsService().summarize(analysis_input)

    assert tuple(item.code for item in result.diagnostics) == ("outcome.zero_variance",)


def test_service_reports_all_missing_and_sparse_outcomes_without_fabricated_values() -> None:
    """Catches unavailable populations being represented as a zero-valued numerical summary."""
    analysis_input = _input_for(
        AnalysisTable(
            columns=("order_id", "account_id", "arm", "outcome"),
            rows=(
                ("o1", "a1", "control", None),
                ("o2", "a2", "treatment", None),
            ),
        ),
        allow_data_ineligible=True,
    )
    analysis_input = DescriptiveStatisticsInput(
        context=analysis_input.context,
        eligibility=analysis_input.eligibility.model_copy(
            update={
                "method_support": analysis_input.eligibility.method_support.model_copy(
                    update={"data_eligible": True}
                )
            }
        ),
    )

    result = DescriptiveStatisticsService().summarize(analysis_input)

    assert result.population.summary.summary_type == "unavailable"
    assert tuple(item.code for item in result.diagnostics) == ("outcome.all_missing",)


def test_service_reports_a_single_valid_outcome_as_sparse() -> None:
    """Catches one-observation samples being presented as if variance were available."""
    analysis_input = _input_for(
        AnalysisTable(
            columns=("order_id", "account_id", "arm", "outcome"),
            rows=(
                ("o1", "a1", "control", None),
                ("o2", "a2", "treatment", 2.0),
            ),
        ),
        allow_data_ineligible=True,
    )
    analysis_input = DescriptiveStatisticsInput(
        context=analysis_input.context,
        eligibility=analysis_input.eligibility.model_copy(
            update={
                "method_support": analysis_input.eligibility.method_support.model_copy(
                    update={"data_eligible": True}
                )
            }
        ),
    )

    result = DescriptiveStatisticsService().summarize(analysis_input)

    assert tuple(item.code for item in result.diagnostics) == ("outcome.sparse_valid_sample",)


def test_service_uses_only_the_existing_missingness_policy_limit_for_extreme_missingness() -> None:
    """Catches an invented missingness threshold or an omitted configured-limit diagnostic."""
    analysis_input = _input_for(
        AnalysisTable(
            columns=("order_id", "account_id", "arm", "outcome"),
            rows=(
                ("o1", "a1", "control", None),
                ("o2", "a2", "control", 1.0),
                ("o3", "a3", "treatment", 2.0),
                ("o4", "a4", "treatment", 3.0),
            ),
        ),
        policy=ValidationPolicy(
            minimum_total=1,
            minimum_per_arm=1,
            weak_total=1,
            weak_per_arm=1,
            minimum_per_segment_arm=1,
            maximum_outcome_missingness=0.25,
        ),
    )

    result = DescriptiveStatisticsService().summarize(analysis_input)

    assert tuple(item.code for item in result.diagnostics) == (
        "outcome.missingness_at_configured_limit",
    )


def test_service_summarizes_declared_numeric_covariates_by_population_and_arm() -> None:
    """Catches covariates being omitted, reordered, or summarized as categorical values."""
    table = AnalysisTable(
        columns=("order_id", "account_id", "arm", "outcome", "prior_orders"),
        rows=(
            ("o1", "a1", "control", 1.0, 2),
            ("o2", "a2", "control", 3.0, 4),
            ("o3", "a3", "treatment", 5.0, 8),
            ("o4", "a4", "treatment", 7.0, None),
        ),
    )
    analysis_input = _input_for(
        table,
        request_update={"covariates": (covariate(),)},
        binding_update={
            "covariates": (
                MetricColumnBinding(metric_id="prior_order_count", column="prior_orders"),
            )
        },
    )

    result = DescriptiveStatisticsService().summarize(analysis_input)

    assert tuple(item.covariate_id for item in result.covariates) == ("prior_order_count",)
    covariate_summary = result.covariates[0]
    assert covariate_summary.population.missing_outcome_count == 1
    assert isinstance(covariate_summary.population.summary, CountSummary)
    assert covariate_summary.control.summary.mean == 3.0
    assert covariate_summary.treatment.summary.mean == 8.0


def test_service_returns_selected_segment_with_existing_small_arm_warning() -> None:
    """Catches automatic segmentation or loss of the selected segment's small-arm evidence."""
    segment = SegmentDefinition(
        segment_id="australian_users",
        label="Australian users",
        criteria=(
            SelectionCriterion(attribute="country", operator=CriterionOperator.EQUAL, value="AU"),
        ),
    )
    analysis_input = _input_for(
        AnalysisTable(
            columns=("order_id", "account_id", "arm", "outcome", "country"),
            rows=(
                ("o1", "a1", "control", 1.0, "AU"),
                ("o2", "a2", "treatment", 3.0, "AU"),
                ("o3", "a3", "control", 8.0, "NZ"),
                ("o4", "a4", "treatment", 10.0, "NZ"),
            ),
        ),
        request_update={"segment": segment},
    )

    result = DescriptiveStatisticsService().summarize(analysis_input)

    assert tuple(item.segment_id for item in result.segments) == ("australian_users",)
    selected = result.segments[0]
    assert selected.population.row_count == 2
    assert selected.raw_comparison is not None
    assert selected.raw_comparison.absolute_difference == 2.0
    assert tuple(item.code for item in selected.warnings) == ("segment.small_arm",)


def test_service_summarizes_explicit_quasi_pre_and_post_periods_without_did() -> None:
    """Catches quasi period summaries being omitted or replaced by a DiD estimate."""
    table = AnalysisTable(
        columns=("order_id", "account_id", "arm", "outcome", "observed_at"),
        rows=(
            ("o1", "a1", "control", 0.0, "2026-06-15T00:00:00Z"),
            ("o1", "a1", "control", 1.0, "2026-07-05T00:00:00Z"),
            ("o2", "a2", "treatment", 0.0, "2026-06-15T00:00:00Z"),
            ("o2", "a2", "treatment", 1.0, "2026-07-05T00:00:00Z"),
        ),
    )
    request = quasi_experimental_request().model_copy(
        update={"clustering": Clustered(unit=AnalysisUnit(unit_id="account", label="Account"))}
    )
    analysis_input = _input_for(
        table,
        request_update={
            "study_design": request.study_design,
            "clustering": request.clustering,
            "outcome": request.outcome,
            "estimand": request.estimand,
        },
        binding_update={"timestamp_column": "observed_at", "clustering_unit_column": "account_id"},
        policy=ValidationPolicy(
            minimum_total=1,
            minimum_per_arm=1,
            weak_total=1,
            weak_per_arm=1,
            minimum_per_segment_arm=1,
            minimum_clusters=2,
            weak_clusters=2,
        ),
    )

    result = DescriptiveStatisticsService().summarize(analysis_input)

    assert tuple(item.period_id for item in result.periods) == ("pre", "post")
    assert result.periods[0].control.summary.rate == 0.0
    assert result.periods[1].treatment.summary.rate == 1.0
