from importlib import import_module

import pytest

from tests.impact_fixtures import binary_source, fixed, request_payload


def analyze(payload=None, source=None):
    m = import_module("packages.experiments.analysis.impact.service")
    return m.BusinessImpactService().analyze(
        binary_source() if source is None else source,
        request_payload() if payload is None else payload,
    )


def test_hand_calculated_gross_net_and_auditable_layers():
    result = analyze()
    assert result.status.value == "inconclusive"
    assert result.exposed_population.central == 50000
    assert result.gross_incremental_outcome.central == pytest.approx(1000)
    assert result.gross_incremental_outcome.combined.lower == pytest.approx(500)
    assert result.gross_incremental_outcome.combined.upper == pytest.approx(1500)
    assert result.gross_monetary_impact.central == pytest.approx(10000)
    assert result.net_monetary_impact.combined.lower == pytest.approx(4000)
    assert result.net_monetary_impact.combined.upper == pytest.approx(14000)
    assert result.net_monetary_impact.statistical.kind == "confidence_interval"
    assert result.inputs.population.evidence.status == "assumed"
    assert result.source.native_status == "completed"
    assert result.derivations
    assert result.gross_monetary_impact.category == "derived"
    assert "recommendation" not in result.model_dump()


def test_combined_range_preserves_negative_and_positive_without_midpoints():
    p = request_payload()
    p["output"] = "gross"
    p["costs"] = None
    p["population"]["value"] = {"lower": 90000, "upper": 110000}
    p["exposure"]["value"] = {"lower": 0.4, "upper": 0.6}
    p["conversion"]["value"] = {"lower": 10, "upper": 12}
    src = binary_source().model_dump(mode="json")
    src["test_result"]["confidence_interval"]["lower"] = -0.01
    result = analyze(p, type(binary_source()).model_validate(src))
    assert result.gross_monetary_impact.combined.lower == pytest.approx(-7920)
    assert result.gross_monetary_impact.combined.upper == pytest.approx(23760)
    assert result.gross_monetary_impact.central is None
    assert result.gross_monetary_impact.statistical is None
    assert result.gross_monetary_impact.statistical_unavailable_reason


@pytest.mark.parametrize("field", ["population", "exposure", "horizon", "binding"])
def test_missing_required_input_returns_structured_abstention(field):
    p = request_payload()
    del p[field]
    result = analyze(p)
    assert result.status.value == "abstained"
    assert result.gross_incremental_outcome is None
    assert any(field in d.message for d in result.diagnostics)


def test_missing_costs_do_not_mean_zero():
    p = request_payload()
    p["costs"] = None
    assert analyze(p).status.value == "abstained"
    p["output"] = "gross"
    assert analyze(p).gross_monetary_impact.central == pytest.approx(10000)


def test_outcome_only_does_not_require_monetary_conversion():
    p = request_payload()
    p.update(output="outcome", conversion=None, costs=None)
    assert analyze(p).gross_incremental_outcome.central == pytest.approx(1000)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["costs"]["items"][0].update(currency="AUD"),
        lambda p: p["population"].update(entity="orders"),
        lambda p: p["population"].update(exposure_basis="already_exposed"),
        lambda p: p["population"]["evidence"].update(provenance=[]),
        lambda p: p["population"].update(target_kind="treated"),
        lambda p: p["binding"].update(metric_id="invented"),
        lambda p: p["costs"]["items"][0].update(value=fixed(-1)),
    ],
)
def test_incompatible_inputs_abstain_without_partial_estimates(mutate):
    p = request_payload()
    mutate(p)
    result = analyze(p)
    assert result.status.value == "abstained"
    assert result.gross_monetary_impact is None
    assert result.abstention_reason


def test_failed_source_never_acquires_impact():
    result = analyze(source=0.02)
    assert result.status.value == "abstained"
    assert result.net_monetary_impact is None


def test_extrapolation_requires_persistence_and_explicit_population_repetition():
    from tests.impact_fixtures import evidence

    p = request_payload()
    year = {"count": 12, "unit": "months"}
    p["horizon"]["period"]["end"] = "2027-07-01T00:00:00Z"
    p["horizon"]["basis"] = year
    p["exposure"]["horizon"] = year
    p["conversion"]["horizon"] = year
    p["costs"]["items"][0]["horizon"] = year
    assert analyze(p).status.value == "abstained"
    p["persistence"] = {
        "period": p["horizon"]["period"],
        "statement": "Assume stable effect for one year",
        "evidence": evidence(),
    }
    assert analyze(p).status.value == "abstained"
    p["repetition"] = {
        "source_basis": {"count": 1, "unit": "months"},
        "target_basis": year,
        "repetitions": 12,
        "statement": "Twelve additive monthly opportunities",
        "evidence": evidence(),
    }
    result = analyze(p)
    assert result.horizon_kind == "extrapolated"
    assert result.population_multiplier == 12
    assert result.net_monetary_impact.central == pytest.approx(119000)
    assert result.declared_costs.central == 1000
    # Annual population already contains all opportunities; it must not multiply again.
    p["population"]["time_basis"] = year
    p["population"]["basis"] = "total"
    p["population"]["value"] = fixed(1200000)
    assert analyze(p).status.value == "abstained"
    p["repetition"] = None
    assert analyze(p).net_monetary_impact.central == pytest.approx(119000)


def test_days_are_not_months_and_horizon_values_must_match_actual_dates():
    p = request_payload()
    p["horizon"]["basis"] = {"count": 30, "unit": "days"}
    assert analyze(p).status.value == "abstained"  # July has 31 days.
    p["horizon"]["basis"]["count"] = 31
    assert analyze(p).status.value == "abstained"  # Different operational period basis.


def test_shared_effect_in_gross_and_incremental_cost_does_not_widen_net():
    from tests.impact_fixtures import evidence

    p = request_payload()
    p["costs"]["items"] = [
        {
            "cost_id": "variable",
            "value": fixed(10),
            "currency": "USD",
            "basis": "per_incremental_outcome",
            "horizon": p["horizon"]["basis"],
            "metric_id": p["binding"]["metric_id"],
            "outcome_unit": p["conversion"]["per_unit"],
            "event": "conversions",
            "evidence": evidence(),
        }
    ]
    result = analyze(p)
    assert result.net_monetary_impact.combined.lower == 0
    assert result.net_monetary_impact.combined.upper == 0
    assert result.declared_costs.combined.lower == pytest.approx(5000)
    assert result.declared_costs.combined.upper == pytest.approx(15000)


def test_zero_exposure_explicit_zero_costs_and_serialization():
    p = request_payload()
    p["exposure"]["value"] = fixed(0)
    p["costs"]["items"] = []
    result = analyze(p)
    assert result.net_monetary_impact.combined.lower == 0
    assert result.net_monetary_impact.combined.upper == 0
    assert result == type(result).model_validate_json(result.model_dump_json())
    assert result.model_dump_json() == analyze(p).model_dump_json()


def test_already_exposed_population_requires_explicit_identity_exposure():
    p = request_payload()
    p["population"].update(value=fixed(50000), exposure_basis="already_exposed")
    p["exposure"].update(value=fixed(1), meaning="already_exposed")
    assert analyze(p).gross_incremental_outcome.central == pytest.approx(1000)


def test_user_to_order_conversion_and_per_exposure_cost_have_explicit_units():
    from tests.impact_fixtures import evidence

    p = request_payload()
    p["population"]["entity"] = "sessions"
    p["exposure_conversion"] = {
        "value": fixed(2),
        "from_entity": "sessions",
        "to_entity": "users",
        "horizon": p["horizon"]["basis"],
        "evidence": evidence(),
    }
    p["costs"]["items"] = [
        {
            "cost_id": "exposure",
            "value": fixed(0.1),
            "currency": "USD",
            "basis": "per_exposure",
            "entity": "users",
            "horizon": p["horizon"]["basis"],
            "evidence": evidence(),
        }
    ]
    result = analyze(p)
    assert result.exposed_population.central == 100000
    assert result.gross_incremental_outcome.central == pytest.approx(2000)
    assert result.declared_costs.central == pytest.approx(10000)
    assert result.net_monetary_impact.central == pytest.approx(10000)


def test_negative_effect_and_avoided_event_value_are_not_confused():
    p = request_payload()
    src = binary_source().model_dump(mode="json")
    src["point_effect"]["absolute_effect"]["value"] = -0.02
    src["test_result"]["confidence_interval"].update(lower=-0.03, upper=-0.01)
    p["conversion"]["orientation"] = "avoided"
    result = analyze(p, type(binary_source()).model_validate(src))
    assert result.gross_incremental_outcome.central == pytest.approx(-1000)
    assert result.gross_monetary_impact.central == pytest.approx(10000)
    assert result.net_monetary_impact.combined.lower == pytest.approx(4000)


def test_recurring_fixed_cost_uses_declared_occurrences_and_setup_is_once():
    from tests.impact_fixtures import evidence

    p = request_payload()
    quarter = {"count": 3, "unit": "months"}
    p["horizon"]["period"]["end"] = "2026-10-01T00:00:00Z"
    p["horizon"]["basis"] = quarter
    p["exposure"]["horizon"] = quarter
    p["conversion"]["horizon"] = quarter
    p["costs"]["items"][0]["horizon"] = quarter
    p["costs"]["items"].append(
        {
            "cost_id": "monthly",
            "value": fixed(100),
            "currency": "USD",
            "basis": "recurring",
            "horizon": {"count": 1, "unit": "months"},
            "evidence": evidence(),
        }
    )
    p["persistence"] = {
        "period": p["horizon"]["period"],
        "statement": "Three months stable",
        "evidence": evidence(),
    }
    p["repetition"] = {
        "source_basis": {"count": 1, "unit": "months"},
        "target_basis": quarter,
        "repetitions": 3,
        "statement": "Three additive monthly populations",
        "evidence": evidence(),
    }
    result = analyze(p)
    assert result.declared_costs.central == 1300
    assert result.net_monetary_impact.central == pytest.approx(28700)
    assert [c.amount.central for c in result.cost_breakdown] == [1000, 300]


def test_scaled_probability_points_are_normalized_before_counting_events():
    p = request_payload()
    src = binary_source().model_dump(mode="json")
    unit = {
        "dimension": "proportion",
        "value_scale": "percentage_point",
        "symbol": "pp",
        "scale_to_base_unit": 0.01,
    }
    src["metric"]["unit"] = unit
    src["analysis_request"]["outcome"]["metric"]["unit"] = unit
    src["point_effect"]["absolute_effect"] = {"value": 2.0, "unit": unit}
    src["test_result"]["confidence_interval"].update(lower=1, upper=3)
    p["binding"]["outcome_unit"] = unit
    result = analyze(p, type(binary_source()).model_validate(src))
    assert result.gross_incremental_outcome.combined.lower == pytest.approx(500)
    assert result.gross_incremental_outcome.combined.upper == pytest.approx(1500)


def test_quantities_independent_of_effect_do_not_inherit_a_confidence_level():
    result = analyze()
    assert result.exposed_population.statistical is None
    assert "independent" in result.exposed_population.statistical_unavailable_reason
    assert result.cost_breakdown[0].amount.statistical is None
    assert result.declared_costs.statistical is None
    assert result.net_monetary_impact.statistical is not None


@pytest.mark.parametrize("output", ["outcome", "gross"])
def test_requested_output_scope_is_respected_even_when_extra_inputs_are_supplied(output):
    p = request_payload()
    p["output"] = output
    result = analyze(p)
    assert result.net_monetary_impact is None
    assert result.declared_costs is None
    assert result.cost_breakdown == ()
    if output == "outcome":
        assert result.gross_monetary_impact is None


def test_repository_input_requires_resolved_structured_evidence_not_just_a_pointer():
    p = request_payload()
    p["population"]["evidence"] = {
        "origin": "repository_evidence",
        "status": "measured",
        "reference": "population-report:eligible",
        "provenance": [{"source_type": "report", "source_id": "population-report"}],
    }
    assert analyze(p).status.value == "abstained"


def test_deserialized_result_cannot_omit_required_net_or_claim_confidence_for_missing_band():
    from pydantic import ValidationError

    result = analyze()
    p = result.model_dump(mode="json")
    p["net_monetary_impact"] = None
    with pytest.raises(ValidationError):
        type(result).model_validate(p)
    q = result.gross_incremental_outcome.model_dump(mode="json")
    q["statistical_unavailable_reason"] = "conflicting metadata"
    with pytest.raises(ValidationError):
        type(result.gross_incremental_outcome).model_validate(q)


def test_lower_latency_is_nonmonetary_until_explicit_conversion():
    from tests.impact_fixtures import continuous_source

    src = continuous_source()
    p = request_payload()
    p.update(output="outcome", conversion=None, costs=None)
    p["binding"].update(event=None, outcome_unit=src.metric.unit.model_dump(mode="json"))
    result = analyze(p, src)
    assert result.gross_incremental_outcome.central == -1000000
    assert result.gross_incremental_outcome.unit.symbol == "ms"
    assert result.source.metric.direction.value == "decrease"
    assert result.gross_monetary_impact is None
    p["output"] = "gross"
    assert analyze(p, src).status.value == "abstained"


def test_continuous_currency_effect_has_explicit_source_currency():
    from tests.impact_fixtures import continuous_source

    src = continuous_source(money=True)
    p = request_payload()
    p.update(output="gross", conversion=None, costs=None)
    p["binding"].update(event=None, outcome_unit=src.metric.unit.model_dump(mode="json"))
    result = analyze(p, src)
    assert result.gross_monetary_impact.central == -1000000
    assert result.gross_monetary_impact.unit.currency_code == "USD"
    assert result.gross_monetary_impact.combined.lower == -1500000
    assert result.gross_monetary_impact.combined.upper == -500000


def test_count_outcome_requires_event_semantics():
    from tests.impact_fixtures import continuous_source

    src = continuous_source(count=True)
    p = request_payload()
    p.update(output="outcome", conversion=None, costs=None)
    p["binding"].update(event=None, outcome_unit=src.metric.unit.model_dump(mode="json"))
    assert analyze(p, src).status.value == "abstained"
    p["binding"]["event"] = "orders"
    assert analyze(p, src).gross_incremental_outcome.central == -1000000


def test_resolved_repository_input_matches_value_and_semantics():
    from packages.experiments.analysis.impact.inputs import PopulationInput

    p = request_payload()
    p["population"]["evidence"] = {
        "origin": "repository_evidence",
        "status": "measured",
        "reference": "population-report:eligible",
        "provenance": [{"source_type": "report", "source_id": "population-report"}],
    }
    population = PopulationInput.model_validate(p["population"])
    p["repository_evidence"] = [
        {
            "reference": "population-report:eligible",
            "status": "measured",
            "provenance": population.evidence.model_dump(mode="json")["provenance"],
            "value": population.model_dump(mode="json", exclude={"evidence"}),
        }
    ]
    assert analyze(p).gross_incremental_outcome.central == pytest.approx(1000)
    p["population"]["value"] = fixed(999999999)
    assert analyze(p).status.value == "abstained"


def test_unrepresentable_horizon_returns_refusal_instead_of_raising_overflow():
    p = request_payload()
    p["horizon"]["basis"] = {"count": 10**30, "unit": "days"}
    assert analyze(p).status.value == "abstained"


def test_deserialization_cannot_upgrade_a_conditional_scenario():
    from pydantic import ValidationError

    result = analyze()
    p = result.model_dump(mode="json")
    p["status"] = "completed"
    with pytest.raises(ValidationError):
        type(result).model_validate(p)
