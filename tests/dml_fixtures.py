"""Deterministic request and table fixtures for issue #102."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from packages.experiments.analysis import (
    AnalysisTable,
    MetricDefinition,
    MetricType,
    MetricUnit,
    OutcomeDirection,
    OutcomeMetric,
    UnitDimension,
    ValueScale,
)
from packages.experiments.analysis.causal import (
    CausalEstimandKind,
    CausalIdentificationService,
    CausalOutcome,
    EffectScale,
    IdentificationResult,
    MeasurementTiming,
    ObservationalAnalysisRequest,
    ObservationalDesignType,
    VariableRole,
)
from packages.experiments.analysis.causal.dml.models import (
    DMLConfig,
    DMLCovariateBinding,
    DMLDataBinding,
    DMLExecutionRequest,
)
from tests.causal_identification_fixtures import request, variable


def dml_variables(*, adjustment_timing: MeasurementTiming = MeasurementTiming.PRE_TREATMENT):
    return (
        variable("account_id", VariableRole.IDENTIFIER, timing=MeasurementTiming.TIME_INVARIANT),
        variable("treated", VariableRole.TREATMENT, timing=MeasurementTiming.AT_TREATMENT),
        variable("outcome", VariableRole.OUTCOME, timing=MeasurementTiming.POST_TREATMENT),
        variable("prior_orders", VariableRole.ADJUSTMENT, timing=adjustment_timing),
    )


def dml_request(
    *,
    estimand_kind: CausalEstimandKind = CausalEstimandKind.ATE,
    design_type: ObservationalDesignType = ObservationalDesignType.DML,
    outcome_type: MetricType = MetricType.CONTINUOUS,
    adjustment_timing: MeasurementTiming = MeasurementTiming.PRE_TREATMENT,
) -> ObservationalAnalysisRequest:
    source = request(
        design_type=design_type,
        estimand_kind=estimand_kind,
        declared_variables=dml_variables(adjustment_timing=adjustment_timing),
    )
    metric = OutcomeMetric(
        metric=MetricDefinition(
            metric_id="outcome",
            label="Continuous outcome",
            metric_type=outcome_type,
            unit=MetricUnit(
                dimension=UnitDimension.DIMENSIONLESS,
                value_scale=ValueScale.RAW,
                symbol="units",
                scale_to_base_unit=1.0,
            ),
        ),
        direction=OutcomeDirection.INCREASE,
    )
    declared_estimand = source.identification.estimand
    assert declared_estimand is not None
    updated_estimand = declared_estimand.model_copy(
        update={
            "outcome_variable": "outcome",
            "effect_scale": EffectScale.MEAN_DIFFERENCE,
        }
    )
    contrast = source.identification.treatment
    assert contrast is not None
    outcome = CausalOutcome(variable_id="outcome", metric=metric)
    adjustment = source.identification.adjustment_set
    assert adjustment is not None
    return source.model_copy(
        update={
            "identification": source.identification.model_copy(
                update={
                    "design": source.identification.design.model_copy(
                        update={"design_type": design_type, "method": "partialling_out_dml"}
                    ),
                    "estimand": updated_estimand,
                    "treatment": contrast,
                    "outcome": outcome,
                    "time": source.identification.time.model_copy(update={"time_variable": None}),
                    "variables": dml_variables(adjustment_timing=adjustment_timing),
                    "covariates": ("prior_orders",),
                    "adjustment_set": adjustment.model_copy(
                        update={
                            "variable_ids": ("prior_orders",),
                            "estimand_type": estimand_kind,
                        }
                    ),
                }
            )
        }
    )


def dml_identification(**kwargs: object) -> IdentificationResult:
    return CausalIdentificationService().identify(dml_request(**kwargs))


def dml_binding() -> DMLDataBinding:
    return DMLDataBinding(
        observation_id_column="account_id",
        treatment_variable_id="treated",
        treatment_column="treated",
        outcome_variable_id="outcome",
        outcome_column="outcome",
        covariates=(DMLCovariateBinding(variable_id="prior_orders", column="prior_orders"),),
    )


def dml_execution(
    *,
    identification_result: IdentificationResult | None = None,
    binding: DMLDataBinding | None = None,
    fold_count: int = 2,
    seed: int = 17,
) -> DMLExecutionRequest:
    return DMLExecutionRequest(
        identification_result=identification_result or dml_identification(),
        binding=binding or dml_binding(),
        configuration=DMLConfig(fold_count=fold_count, random_seed=seed),
    )


def dml_rows() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "account_id": f"{arm}-{index}",
            "treated": treated,
            "outcome": float(index + 2 * treated),
            "prior_orders": float(index),
        }
        for arm, treated in (("c", 0), ("t", 1))
        for index in range(4)
    )


def dml_table(
    rows: Sequence[Mapping[str, object]] | None = None,
) -> AnalysisTable:
    return AnalysisTable.from_records(tuple(rows or dml_rows()))
