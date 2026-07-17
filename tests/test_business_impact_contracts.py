from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from packages.experiments.analysis import (
    AnalysisStatus,
    AssociationalEstimate,
    BusinessImpactInputs,
    BusinessImpactProjection,
    ConclusionType,
    SourcedCount,
    SourcedCurrency,
    SourcedMoney,
    SourcedProportion,
    SourcedQuantity,
    SourcedTimePeriod,
)
from tests.analysis_contract_fixtures import (
    count_unit,
    currency_unit,
    effect_details,
    proportion_unit,
    randomized_estimate,
    source,
    valid_business_inputs,
    valid_projection,
)

REQUIRED_INPUT_FIELDS = (
    "eligible_population",
    "exposure_frequency",
    "baseline_rate",
    "average_order_value",
    "contribution_margin",
    "rollout_proportion",
    "analysis_horizon",
    "currency",
)


def test_business_impact_inputs_construct_with_complete_sourced_values() -> None:
    inputs = valid_business_inputs()

    assert inputs.eligible_population.value == 100_000
    assert inputs.exposure_frequency.unit.symbol == "exposures/user/month"
    assert inputs.baseline_rate.value == 0.20
    assert inputs.average_order_value.unit.currency_code == "USD"
    assert inputs.contribution_margin.value == 0.30
    assert inputs.rollout_proportion.value == 0.50
    assert inputs.analysis_horizon.value.start.isoformat() == "2026-08-01T00:00:00+00:00"
    assert inputs.currency.value == "USD"


@pytest.mark.parametrize("input_field", REQUIRED_INPUT_FIELDS)
def test_business_impact_inputs_require_provenance_for_every_input(input_field: str) -> None:
    payload = valid_business_inputs().model_dump(mode="json")
    payload[input_field]["provenance"] = []

    with pytest.raises(ValidationError, match="provenance"):
        BusinessImpactInputs.model_validate(payload)


@pytest.mark.parametrize("missing_field", REQUIRED_INPUT_FIELDS)
def test_business_impact_inputs_reject_incomplete_financial_inputs(missing_field: str) -> None:
    payload = valid_business_inputs().model_dump(mode="json")
    del payload[missing_field]

    with pytest.raises(ValidationError):
        BusinessImpactInputs.model_validate(payload)


def test_sourced_numeric_inputs_reject_unambiguous_invalid_values() -> None:
    provenance = (source(),)
    with pytest.raises(ValidationError):
        SourcedCount(value=0, provenance=provenance)
    with pytest.raises(ValidationError):
        SourcedCount(value=True, provenance=provenance)
    with pytest.raises(ValidationError):
        SourcedQuantity(value=float("nan"), unit=count_unit(), provenance=provenance)
    with pytest.raises(ValidationError):
        SourcedProportion(value=-0.01, unit=proportion_unit(), provenance=provenance)
    with pytest.raises(ValidationError):
        SourcedProportion(value=1.01, unit=proportion_unit(), provenance=provenance)
    with pytest.raises(ValidationError):
        SourcedMoney(value=float("inf"), unit=currency_unit(), provenance=provenance)


def test_sourced_values_require_semantically_explicit_units_and_currency() -> None:
    provenance = (source(),)
    with pytest.raises(ValidationError, match="proportion"):
        SourcedProportion(value=0.2, unit=count_unit(), provenance=provenance)
    with pytest.raises(ValidationError, match="currency"):
        SourcedMoney(value=80.0, unit=count_unit(), provenance=provenance)
    with pytest.raises(ValidationError):
        SourcedCurrency(value="usd", provenance=provenance)


@pytest.mark.parametrize("field", ["baseline_rate", "rollout_proportion"])
def test_business_inputs_reject_unsourced_plain_proportions(field: str) -> None:
    payload = valid_business_inputs().model_dump(mode="json")
    payload[field] = 0.5

    with pytest.raises(ValidationError):
        BusinessImpactInputs.model_validate(payload)


def test_business_inputs_reject_plain_money_without_currency_unit() -> None:
    payload = valid_business_inputs().model_dump(mode="json")
    payload["average_order_value"] = {"value": 80.0, "provenance": [source().model_dump()]}

    with pytest.raises(ValidationError):
        BusinessImpactInputs.model_validate(payload)


def test_sourced_time_period_rejects_naive_or_reversed_horizons() -> None:
    provenance = (source(),)
    with pytest.raises(ValidationError, match="timezone-aware"):
        SourcedTimePeriod.model_validate(
            {
                "value": {
                    "start": datetime(2026, 9, 1),
                    "end": datetime(2026, 10, 1),
                },
                "provenance": provenance,
            }
        )
    with pytest.raises(ValidationError, match="before end"):
        payload = valid_business_inputs().analysis_horizon.model_dump(mode="json")
        payload["value"]["start"], payload["value"]["end"] = (
            payload["value"]["end"],
            payload["value"]["start"],
        )
        SourcedTimePeriod.model_validate(payload)


def test_treatment_effect_alone_cannot_construct_business_projection() -> None:
    with pytest.raises(ValidationError):
        BusinessImpactProjection.model_validate(
            {"source_estimate": randomized_estimate().model_dump(mode="json")}
        )


@pytest.mark.parametrize(
    ("projected_currency", "input_currency"),
    [("AUD", "USD"), ("USD", "AUD")],
)
def test_projection_rejects_currency_mismatch(
    projected_currency: str,
    input_currency: str,
) -> None:
    with pytest.raises(ValidationError, match="currency"):
        valid_projection(
            projected_currency=projected_currency,
            input_currency=input_currency,
        )


def test_projection_rejects_average_order_value_currency_mismatch() -> None:
    payload = valid_business_inputs().model_dump(mode="json")
    payload["average_order_value"]["unit"] = currency_unit("AUD").model_dump(mode="json")

    with pytest.raises(ValidationError, match="currency"):
        BusinessImpactInputs.model_validate(payload)


def test_projection_rejects_currency_valued_contribution_margin_mismatch() -> None:
    payload = valid_business_inputs().model_dump(mode="json")
    payload["contribution_margin"] = SourcedMoney(
        value=24.0,
        unit=currency_unit("AUD"),
        provenance=(source(),),
    ).model_dump(mode="json")

    with pytest.raises(ValidationError, match="currency"):
        BusinessImpactInputs.model_validate(payload)


def test_projection_preserves_associational_source_evidence() -> None:
    projection_payload = valid_projection().model_dump(mode="json")
    projection_payload["source_estimate"] = AssociationalEstimate(
        conclusion_type=ConclusionType.ASSOCIATION,
        estimate=effect_details(),
    ).model_dump(mode="json")

    projection = BusinessImpactProjection.model_validate(projection_payload)

    assert projection.conclusion_type is ConclusionType.PROJECTION
    assert projection.source_estimate.conclusion_type is ConclusionType.ASSOCIATION
    assert projection.source_estimate.estimate.provenance == (source(),)


def test_projection_has_stable_business_impact_serialization_shape() -> None:
    payload = valid_projection().model_dump(mode="json")

    assert payload["projection_type"] == "business_impact_projection"
    assert payload["schema_version"] == "1"
    assert payload["status"] == AnalysisStatus.COMPLETED
    assert payload["conclusion_type"] == "projection"
    assert payload["inputs"]["currency"]["value"] == "USD"
    assert payload["source_estimate"]["finding_type"] == "randomized_experiment_estimate"
    assert payload["source_estimate"]["conclusion_type"] == "causal_effect"
    assert payload["projected_incremental_outcome"] == {
        "value": 550.0,
        "unit": count_unit().model_dump(mode="json"),
    }
    assert payload["projected_financial_impact"] == {
        "value": 13_200.0,
        "unit": currency_unit().model_dump(mode="json"),
    }
    assert payload["uncertainty"]["measures"][0]["kind"] == "confidence_interval"
    assert payload["provenance"][0]["source_id"] == "exp-001-payment-recommendation"


def test_projection_is_frozen_and_forbids_unknown_fields() -> None:
    projection = valid_projection()
    with pytest.raises(ValidationError, match="frozen"):
        projection.status = AnalysisStatus.INCONCLUSIVE  # type: ignore[misc]

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BusinessImpactProjection.model_validate(
            {**projection.model_dump(mode="json"), "calculation": "not allowed"}
        )
