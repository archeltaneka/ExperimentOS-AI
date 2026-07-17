from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from packages.experiments.analysis import (
    ANALYSIS_FINDING_ADAPTER,
    ANALYSIS_OUTCOME_ADAPTER,
    ANALYSIS_REQUEST_ADAPTER,
    BUSINESS_IMPACT_PROJECTION_ADAPTER,
    EFFECT_ESTIMATE_ADAPTER,
    ESTIMAND_ADAPTER,
    STUDY_DESIGN_ADAPTER,
    AnalysisFailure,
    AnalysisStatus,
    AssociationalEstimate,
    BusinessImpactProjection,
    CompletedAnalysisResult,
    ConclusionType,
    DescriptiveStatistic,
    DescriptiveStatisticType,
    Diagnostic,
    DiagnosticOutcome,
    DiagnosticSeverity,
    EligibilityAssessment,
    FailedAnalysisResult,
    InconclusiveAnalysisResult,
    ObservationalEstimate,
    QuasiExperimentalEstimate,
    analysis_finding_from_json,
    analysis_outcome_from_json,
    analysis_request_from_json,
    business_impact_projection_from_json,
    effect_estimate_from_json,
    estimand_from_json,
    study_design_from_json,
    to_canonical_json,
)
from tests.analysis_contract_fixtures import (
    abstained_result,
    effect_details,
    observational_request,
    outcome,
    randomized_estimate,
    randomized_request,
    source,
    valid_projection,
)


def _finding_variants() -> tuple[object, ...]:
    details = effect_details()
    return (
        DescriptiveStatistic(
            statistic_type=DescriptiveStatisticType.SAMPLE_PROPORTION,
            status=AnalysisStatus.COMPLETED,
            metric=outcome().metric,
            value=details.point_estimate,
            uncertainty=details.uncertainty,
            sample_size=details.sample_counts.total,
            provenance=(source(),),
        ),
        AssociationalEstimate(
            conclusion_type=ConclusionType.ASSOCIATION,
            estimate=details,
        ),
        randomized_estimate(),
        QuasiExperimentalEstimate(
            conclusion_type=ConclusionType.CAUSAL_EFFECT,
            estimate=details,
        ),
        ObservationalEstimate(
            conclusion_type=ConclusionType.ASSOCIATION,
            estimate=details,
        ),
    )


def _outcome_variants() -> tuple[object, ...]:
    return (
        EligibilityAssessment(
            status=AnalysisStatus.ELIGIBLE,
            diagnostics=(),
            warnings=(),
            required_data=(),
            provenance=(source(),),
        ),
        CompletedAnalysisResult(
            status=AnalysisStatus.COMPLETED,
            findings=(randomized_estimate(),),
            diagnostics=(),
            warnings=(),
            provenance=(source(),),
        ),
        InconclusiveAnalysisResult(
            status=AnalysisStatus.INCONCLUSIVE,
            findings=(randomized_estimate(analysis_status=AnalysisStatus.INCONCLUSIVE),),
            diagnostics=(),
            warnings=(),
            provenance=(source(),),
        ),
        abstained_result(),
        FailedAnalysisResult(
            status=AnalysisStatus.FAILED,
            failures=(
                AnalysisFailure(
                    code="analysis.execution",
                    stage="analysis",
                    message="Analysis execution failed.",
                    retryable=True,
                ),
            ),
            diagnostics=(),
            provenance=(source(),),
        ),
    )


@pytest.mark.parametrize("original", [randomized_request(), observational_request()])
def test_analysis_request_round_trips_through_public_boundary(original: object) -> None:
    payload = to_canonical_json(original)

    assert analysis_request_from_json(payload) == original
    assert analysis_request_from_json(payload.encode("utf-8")) == original
    assert ANALYSIS_REQUEST_ADAPTER.validate_json(payload) == original


def test_design_and_estimand_round_trip_through_public_adapters() -> None:
    request = observational_request()
    design_payload = to_canonical_json(request.study_design)
    estimand_payload = to_canonical_json(request.estimand)

    assert study_design_from_json(design_payload) == request.study_design
    assert STUDY_DESIGN_ADAPTER.validate_json(design_payload) == request.study_design
    assert estimand_from_json(estimand_payload) == request.estimand
    assert ESTIMAND_ADAPTER.validate_json(estimand_payload) == request.estimand


@pytest.mark.parametrize("original", _finding_variants())
def test_every_finding_category_round_trips_through_public_union(original: object) -> None:
    payload = to_canonical_json(original)

    assert analysis_finding_from_json(payload) == original
    assert ANALYSIS_FINDING_ADAPTER.validate_json(payload) == original


@pytest.mark.parametrize("original", _finding_variants()[1:])
def test_every_effect_estimate_category_round_trips_through_public_union(
    original: object,
) -> None:
    payload = to_canonical_json(original)

    assert effect_estimate_from_json(payload) == original
    assert EFFECT_ESTIMATE_ADAPTER.validate_json(payload) == original


@pytest.mark.parametrize("original", _outcome_variants())
def test_every_analysis_outcome_round_trips_through_public_union(original: object) -> None:
    payload = to_canonical_json(original)

    assert analysis_outcome_from_json(payload) == original
    assert ANALYSIS_OUTCOME_ADAPTER.validate_json(payload) == original


def test_diagnostic_has_deterministic_canonical_serialization() -> None:
    diagnostic = Diagnostic(
        code="overlap.low",
        severity=DiagnosticSeverity.WARNING,
        outcome=DiagnosticOutcome.FAILED,
        message="Observed overlap is below the planned threshold.",
    )

    assert to_canonical_json(diagnostic) == (
        '{"code":"overlap.low","message":"Observed overlap is below the planned threshold.",'
        '"observed_value":null,"outcome":"failed","severity":"warning","threshold":null}'
    )


def test_business_projection_round_trips_through_public_boundary() -> None:
    projection = valid_projection()
    payload = to_canonical_json(projection)

    restored = business_impact_projection_from_json(payload)
    assert restored == projection
    assert isinstance(restored, BusinessImpactProjection)
    assert BUSINESS_IMPACT_PROJECTION_ADAPTER.validate_json(payload) == projection


def test_canonical_json_is_compact_sorted_unicode_and_repeatable() -> None:
    original = randomized_request()
    first = to_canonical_json(original)
    second = to_canonical_json(original)

    assert first == second
    assert first == json.dumps(
        json.loads(first),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    assert first.encode("utf-8").decode("utf-8") == first
    assert '"schema_version":"1"' in first
    assert '"kind":"intention_to_treat"' in first
    assert '"design_type":"randomized_experiment"' in first


def test_top_level_contracts_keep_canonical_schema_version() -> None:
    payloads = (
        json.loads(to_canonical_json(randomized_request())),
        *(json.loads(to_canonical_json(outcome)) for outcome in _outcome_variants()),
        json.loads(to_canonical_json(valid_projection())),
    )

    assert {payload["schema_version"] for payload in payloads} == {"1"}


@pytest.mark.parametrize(
    ("decoder", "payload", "discriminator"),
    [
        (
            analysis_request_from_json,
            randomized_request().model_dump(mode="json"),
            ("study_design", "design_type"),
        ),
        (
            analysis_finding_from_json,
            randomized_estimate().model_dump(mode="json"),
            ("finding_type",),
        ),
        (
            analysis_outcome_from_json,
            abstained_result().model_dump(mode="json"),
            ("outcome_type",),
        ),
        (
            business_impact_projection_from_json,
            valid_projection().model_dump(mode="json"),
            ("projection_type",),
        ),
    ],
)
def test_public_decoders_reject_unknown_discriminators(
    decoder: object,
    payload: dict[str, object],
    discriminator: tuple[str, ...],
) -> None:
    target: dict[str, object] = payload
    for key in discriminator[:-1]:
        target = target[key]  # type: ignore[assignment]
    target[discriminator[-1]] = "unknown"

    with pytest.raises(ValidationError):
        decoder(json.dumps(payload))  # type: ignore[operator]
