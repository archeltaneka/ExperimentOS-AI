from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from packages.experiments.analysis import (
    AnalysisTable,
    MetricDefinition,
    MetricType,
    MetricUnit,
    OutcomeDirection,
    OutcomeMetric,
    TimePeriod,
    UnitDimension,
    ValueScale,
)
from packages.experiments.analysis.causal import (
    CausalEstimandKind,
    CausalOutcome,
    EffectScale,
    ObservationalAnalysisRequest,
    ObservationalDesignType,
)
from packages.experiments.analysis.causal.did import (
    DifferenceInDifferencesDataBinding,
    DifferenceInDifferencesExecutionRequest,
)
from tests.causal_identification_fixtures import request


def at(day: int) -> datetime:
    return datetime(2026, 7, day, tzinfo=UTC)


def did_request() -> ObservationalAnalysisRequest:
    candidate = request(
        design_type=ObservationalDesignType.DID,
        estimand_kind=CausalEstimandKind.DID_ATT,
    )
    metric = OutcomeMetric(
        metric=MetricDefinition(
            metric_id="conversion",
            label="Revenue per account",
            metric_type=MetricType.CONTINUOUS,
            unit=MetricUnit(
                dimension=UnitDimension.CURRENCY,
                value_scale=ValueScale.RAW,
                symbol="USD",
                scale_to_base_unit=1.0,
                currency_code="USD",
            ),
        ),
        direction=OutcomeDirection.INCREASE,
    )
    identification = candidate.identification
    estimand = identification.estimand
    assert estimand is not None
    return candidate.model_copy(
        update={
            "identification": identification.model_copy(
                update={
                    "outcome": CausalOutcome(variable_id="conversion", metric=metric),
                    "estimand": estimand.model_copy(
                        update={"effect_scale": EffectScale.MEAN_DIFFERENCE}
                    ),
                }
            )
        }
    )


_DEVIATIONS = (-4.5, -3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 4.5)
_POST_DEVIATIONS = (1.5, -2.5, 4.5, -0.5, 2.5, -4.5, 0.5, -3.5, 3.5, -1.5)


def did_rows(*, treated_post_mean: float) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for group, prefix, pre_mean, post_mean in (
        ("treated", "t", 10.0, treated_post_mean),
        ("control", "c", 8.0, 10.0),
    ):
        for index, (pre_deviation, post_deviation) in enumerate(
            zip(_DEVIATIONS, _POST_DEVIATIONS, strict=True),
            start=1,
        ):
            unit_id = f"{prefix}-{index:02d}"
            treatment_start = at(10) if group == "treated" else None
            rows.extend(
                (
                    {
                        "unit_id": unit_id,
                        "observed_at": at(5),
                        "group": group,
                        "exposed": 0,
                        "treatment_start": treatment_start,
                        "outcome": pre_mean + pre_deviation,
                    },
                    {
                        "unit_id": unit_id,
                        "observed_at": at(15),
                        "group": group,
                        "exposed": 1 if group == "treated" else 0,
                        "treatment_start": treatment_start,
                        "outcome": post_mean + post_deviation,
                    },
                )
            )
    return tuple(rows)


def no_effect_rows() -> tuple[dict[str, object], ...]:
    return did_rows(treated_post_mean=12.0)


def positive_effect_rows() -> tuple[dict[str, object], ...]:
    return did_rows(treated_post_mean=15.0)


def did_table(rows: Sequence[dict[str, object]]) -> AnalysisTable:
    return AnalysisTable.from_records(rows)


def did_binding() -> DifferenceInDifferencesDataBinding:
    return DifferenceInDifferencesDataBinding(
        unit_column="unit_id",
        time_column="observed_at",
        group_column="group",
        treatment_column="exposed",
        treatment_start_column="treatment_start",
        outcome_column="outcome",
        treated_group_value="treated",
        control_group_value="control",
    )


def did_execution(
    analysis_request: ObservationalAnalysisRequest | None = None,
    *,
    extra_pre_periods: tuple[TimePeriod, ...] = (),
) -> DifferenceInDifferencesExecutionRequest:
    return DifferenceInDifferencesExecutionRequest(
        analysis_request=analysis_request or did_request(),
        binding=did_binding(),
        extra_pre_periods=extra_pre_periods,
    )


def extra_pre_periods() -> tuple[TimePeriod, TimePeriod]:
    return (
        TimePeriod(
            start=datetime(2026, 6, 1, tzinfo=UTC),
            end=datetime(2026, 6, 2, tzinfo=UTC),
        ),
        TimePeriod(
            start=datetime(2026, 6, 3, tzinfo=UTC),
            end=datetime(2026, 6, 4, tzinfo=UTC),
        ),
    )


def add_extra_pre_rows(
    canonical_rows: tuple[dict[str, object], ...],
    *,
    treated_means: tuple[float, float],
    control_means: tuple[float, float],
) -> tuple[dict[str, object], ...]:
    periods = extra_pre_periods()
    means = {"treated": treated_means, "control": control_means}
    units = tuple(canonical_rows[index] for index in range(0, len(canonical_rows), 2))
    extra: list[dict[str, object]] = []
    for unit_index, unit in enumerate(units):
        group = str(unit["group"])
        for period_index, period in enumerate(periods):
            deviations = _POST_DEVIATIONS if period_index == 0 else _DEVIATIONS
            deviation = deviations[unit_index % 10]
            extra.append(
                {
                    "unit_id": unit["unit_id"],
                    "observed_at": period.start,
                    "group": group,
                    "exposed": 0,
                    "treatment_start": unit["treatment_start"],
                    "outcome": means[group][period_index] + deviation,
                }
            )
    return tuple(extra) + canonical_rows
