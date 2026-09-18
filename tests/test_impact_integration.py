"""Public estimator-to-impact paths and scoped subgroup population safety."""

from datetime import UTC, datetime

import pytest

from packages.experiments.analysis.impact import BusinessImpactService
from packages.experiments.analysis.impact.sources import adapt_source
from packages.experiments.analysis.study_designs import TimePeriod
from tests.impact_fixtures import evidence, request_payload
from tests.impact_source_fixtures import (
    bayesian_result,
    cuped_result,
    did_result,
    dml_result,
    hte_result,
    ipw_result,
    randomized_result,
)


def operational_request(source, subgroup_id=None):
    effect = adapt_source(source, subgroup_id)
    assert effect.calculable, effect.blocking_diagnostics
    p = request_payload()
    p.update(output="outcome", conversion=None, costs=None, subgroup_id=subgroup_id)
    p["population"].update(
        definition=effect.population.model_dump(mode="json"),
        target_kind=effect.target_kind,
        subgroup_id=subgroup_id,
        subgroup_rule=effect.subgroup_rule,
    )
    observed = effect.observed_period or TimePeriod(
        start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 8, 1, tzinfo=UTC)
    )
    days = (observed.end - observed.start).days
    basis = {"count": days, "unit": "days"}
    p["horizon"].update(period=observed.model_dump(mode="json"), basis=basis)
    p["population"]["time_basis"] = basis
    p["exposure"]["horizon"] = basis
    p["binding"].update(
        analysis_unit=effect.analysis_unit.model_dump(mode="json"),
        metric_id=effect.metric.metric.metric_id,
        outcome_unit=effect.metric.metric.unit.model_dump(mode="json"),
        event="conversions" if effect.effect_scale == "absolute_binary" else None,
    )
    if effect.observed_period is None:
        p["binding"].update(
            observed_period=observed.model_dump(mode="json"), evidence=evidence("measured")
        )
    return p, effect


@pytest.mark.parametrize(
    "builder",
    [randomized_result, cuped_result, bayesian_result, ipw_result, did_result, dml_result],
)
def test_public_estimator_results_produce_conditional_sourced_scenarios(builder):
    source = builder()
    request, effect = operational_request(source)
    result = BusinessImpactService().analyze(source, request)
    assert result.status.value == "inconclusive", result.diagnostics
    assert result.gross_incremental_outcome.central == pytest.approx(effect.point * 50000)
    assert result.gross_incremental_outcome.statistical.kind == effect.interval.kind
    assert result.source.provenance
    assert result.source.estimator == effect.estimator
    assert result.source.source_assumptions


def test_hte_requires_the_selected_subgroup_population_and_never_aggregates():
    source = hte_result()
    selected = source.subgroup_results[0].subgroup_id
    request, effect = operational_request(source, selected)
    result = BusinessImpactService().analyze(source, request)
    assert result.status.value == "inconclusive", result.diagnostics
    assert result.gross_incremental_outcome.central == pytest.approx(effect.point * 50000)
    assert result.source.subgroup_id == selected
    request["population"]["subgroup_rule"] = "overlapping or different segment"
    assert BusinessImpactService().analyze(source, request).status.value == "abstained"
    request["subgroup_id"] = None
    assert BusinessImpactService().analyze(source, request).status.value == "abstained"


def test_att_cannot_be_applied_to_full_population():
    source = ipw_result(att=True)
    request, _ = operational_request(source)
    assert BusinessImpactService().analyze(source, request).status.value == "inconclusive"
    request["population"]["target_kind"] = "full"
    assert BusinessImpactService().analyze(source, request).status.value == "abstained"
