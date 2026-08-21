from __future__ import annotations

from packages.experiments.analysis import (
    CAUSAL_IDENTIFICATION_REQUEST_ADAPTER,
    IDENTIFICATION_RESULT_ADAPTER,
    OBSERVATIONAL_ANALYSIS_REQUEST_ADAPTER,
    CausalIdentificationService,
    causal_identification_request_from_json,
    identification_result_from_json,
    observational_analysis_request_from_json,
    to_canonical_json,
)
from tests.causal_identification_fixtures import request


def test_identification_request_and_result_round_trip() -> None:
    envelope = request()
    identification_payload = to_canonical_json(envelope.identification)
    envelope_payload = to_canonical_json(envelope)
    result = CausalIdentificationService().identify(envelope)
    result_payload = to_canonical_json(result)

    assert (
        causal_identification_request_from_json(identification_payload) == envelope.identification
    )
    assert observational_analysis_request_from_json(envelope_payload) == envelope
    assert identification_result_from_json(result_payload) == result
    assert (
        CAUSAL_IDENTIFICATION_REQUEST_ADAPTER.validate_json(identification_payload)
        == envelope.identification
    )
    assert OBSERVATIONAL_ANALYSIS_REQUEST_ADAPTER.validate_json(envelope_payload) == envelope
    assert IDENTIFICATION_RESULT_ADAPTER.validate_json(result_payload) == result


def test_canonical_json_is_stable_for_semantically_unordered_inputs() -> None:
    original = request()
    reversed_identification = original.identification.model_copy(
        update={
            "variables": tuple(reversed(original.identification.variables)),
            "assumptions": tuple(reversed(original.identification.assumptions)),
            "covariates": tuple(reversed(original.identification.covariates)),
        }
    )
    normalized = type(original.identification).model_validate(
        reversed_identification.model_dump(mode="python")
    )
    assert to_canonical_json(original.identification) == to_canonical_json(normalized)
