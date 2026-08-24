from __future__ import annotations

from collections.abc import Mapping, Sequence

from packages.experiments.analysis import AnalysisTable
from packages.experiments.analysis.causal import (
    AdjustmentSet,
    AdjustmentValidationStatus,
    CausalEstimandKind,
    CausalVariable,
    MeasurementTiming,
    ObservationalAnalysisRequest,
    ObservationalDesignType,
    VariableRole,
)
from packages.experiments.analysis.causal.propensity import (
    PropensityConfig,
    PropensityCovariateBinding,
    PropensityDataBinding,
    PropensityExecutionRequest,
    PropensityFeatureKind,
)
from tests.causal_identification_fixtures import (
    adjustment_set,
    request,
    variable,
)


def propensity_variables(
    *,
    prior_orders_role: VariableRole = VariableRole.ADJUSTMENT,
    prior_orders_timing: MeasurementTiming = MeasurementTiming.PRE_TREATMENT,
) -> tuple[CausalVariable, ...]:
    return (
        variable("account_id", VariableRole.IDENTIFIER, timing=MeasurementTiming.TIME_INVARIANT),
        variable("treated", VariableRole.TREATMENT, timing=MeasurementTiming.AT_TREATMENT),
        variable("conversion", VariableRole.OUTCOME, timing=MeasurementTiming.POST_TREATMENT),
        variable("observed_at", VariableRole.TIME, timing=MeasurementTiming.TIME_INVARIANT),
        variable("prior_orders", prior_orders_role, timing=prior_orders_timing),
        variable("country", VariableRole.ADJUSTMENT, timing=MeasurementTiming.PRE_TREATMENT),
    )


def propensity_request(
    *,
    estimand_kind: CausalEstimandKind = CausalEstimandKind.ATE,
    declared_variables: tuple[CausalVariable, ...] | None = None,
) -> ObservationalAnalysisRequest:
    adjustment = adjustment_set(estimand_kind).model_copy(
        update={
            "variable_ids": ("country", "prior_orders"),
            "validation_status": AdjustmentValidationStatus.UNVALIDATED,
        }
    )
    candidate = request(
        design_type=ObservationalDesignType.PROPENSITY_WEIGHTING,
        estimand_kind=estimand_kind,
        declared_variables=declared_variables or propensity_variables(),
        adjustment=adjustment,
    )
    return candidate.model_copy(
        update={
            "identification": candidate.identification.model_copy(
                update={"covariates": ("country", "prior_orders")}
            )
        }
    )


def propensity_binding() -> PropensityDataBinding:
    return PropensityDataBinding(
        unit_column="account_id",
        treatment_column="treated",
        covariates=(
            PropensityCovariateBinding(
                variable_id="country",
                column="country",
                feature_kind=PropensityFeatureKind.CATEGORICAL,
            ),
            PropensityCovariateBinding(
                variable_id="prior_orders",
                column="prior_orders",
                feature_kind=PropensityFeatureKind.NUMERIC,
            ),
        ),
    )


def propensity_execution(
    *,
    analysis_request: ObservationalAnalysisRequest | None = None,
    binding: PropensityDataBinding | None = None,
    config: PropensityConfig | None = None,
) -> PropensityExecutionRequest:
    return PropensityExecutionRequest(
        analysis_request=analysis_request or propensity_request(),
        binding=binding or propensity_binding(),
        configuration=config or PropensityConfig(),
    )


def propensity_table(records: Sequence[Mapping[str, object]]) -> AnalysisTable:
    return AnalysisTable.from_records(records)


def small_valid_rows() -> tuple[dict[str, object], ...]:
    return (
        {"account_id": "u-3", "treated": 1, "country": "TH", "prior_orders": 4.0},
        {"account_id": "u-1", "treated": 0, "country": "US", "prior_orders": 2.0},
        {"account_id": "u-4", "treated": 1, "country": "US", "prior_orders": 3.0},
        {"account_id": "u-2", "treated": 0, "country": "TH", "prior_orders": 1.0},
    )


def good_overlap_rows() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    countries = ("TH", "US", "SG")
    for index in range(30):
        rows.extend(
            (
                {
                    "account_id": f"c-{index:02d}",
                    "treated": 0,
                    "country": countries[index % 3],
                    "prior_orders": float(index % 10),
                },
                {
                    "account_id": f"t-{index:02d}",
                    "treated": 1,
                    "country": countries[(index + 1) % 3],
                    "prior_orders": float(index % 10) + 1.5,
                },
            )
        )
    return tuple(rows)


def weak_overlap_rows() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for index in range(30):
        rows.extend(
            (
                {
                    "account_id": f"weak-c-{index:02d}",
                    "treated": 0,
                    "country": "TH" if index % 2 else "US",
                    "prior_orders": -4.0 + index * 0.25,
                },
                {
                    "account_id": f"weak-t-{index:02d}",
                    "treated": 1,
                    "country": "TH" if index % 2 else "US",
                    "prior_orders": 1.0 + index * 0.25,
                },
            )
        )
    return tuple(rows)


def separation_rows() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for index in range(25):
        rows.extend(
            (
                {
                    "account_id": f"sep-c-{index:02d}",
                    "treated": 0,
                    "country": "TH" if index % 2 else "US",
                    "prior_orders": -30.0 + index * 0.5,
                },
                {
                    "account_id": f"sep-t-{index:02d}",
                    "treated": 1,
                    "country": "TH" if index % 2 else "US",
                    "prior_orders": 18.0 + index * 0.5,
                },
            )
        )
    return tuple(rows)


def extreme_weight_rows() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for index in range(40):
        rows.extend(
            (
                {
                    "account_id": f"tail-c-{index:02d}",
                    "treated": 0,
                    "country": "TH" if index % 2 else "US",
                    "prior_orders": -3.0 + index * 0.05,
                },
                {
                    "account_id": f"tail-t-{index:02d}",
                    "treated": 1,
                    "country": "TH" if index % 2 else "US",
                    "prior_orders": 1.0 + index * 0.05,
                },
            )
        )
    rows.extend(
        (
            {
                "account_id": "tail-treated-outlier",
                "treated": 1,
                "country": "TH",
                "prior_orders": -3.0,
            },
            {
                "account_id": "tail-control-outlier",
                "treated": 0,
                "country": "US",
                "prior_orders": 2.95,
            },
        )
    )
    return tuple(rows)


def adjustment_with_ids(
    source: AdjustmentSet,
    variable_ids: tuple[str, ...],
) -> AdjustmentSet:
    return source.model_copy(update={"variable_ids": variable_ids})
