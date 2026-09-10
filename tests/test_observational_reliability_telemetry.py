"""Aggregate causal telemetry and privacy invariants for issue #101."""

from __future__ import annotations

import pytest

from packages.evals.statistical import telemetry as statistical_telemetry
from packages.evals.statistical.dataset import (
    DEFAULT_STATISTICAL_DATASET_PATH,
    load_statistical_reference_cases,
)
from packages.evals.statistical.fixtures import run_statistical_fixture
from packages.evals.statistical.telemetry import (
    _RecordingProvider,
    evaluate_fixture_telemetry_privacy,
)
from packages.observability.base import BufferedSpanRecord


def _case(case_id: str):
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    return next(case for case in dataset.cases if case.case_id == case_id)


@pytest.mark.parametrize(
    "case_id",
    [
        "identification-ate-identified",
        "identification-post-treatment-adjustment",
        "did-known-positive-effect",
        "did-invalid-staggered-adoption",
        "propensity-good-overlap",
        "propensity-convergence-failure",
        "ipw-ate-known-effect",
        "ipw-failed-overlap-abstention",
        "ipw-att-known-effect",
        "ipw-att-failed-overlap-abstention",
    ],
)
def test_observational_success_and_abstention_telemetry_excludes_analysis_records(
    case_id: str,
) -> None:
    passed, violations = evaluate_fixture_telemetry_privacy(_case(case_id))

    assert passed is True
    assert violations == ()


@pytest.mark.parametrize(
    ("case_id", "required_keys"),
    [
        (
            "did-known-positive-effect",
            {"design", "estimand_type", "assumption_codes", "cluster_robust"},
        ),
        (
            "propensity-good-overlap",
            {"design", "model_family", "convergence_status", "overlap_status", "ess_status"},
        ),
        (
            "ipw-att-known-effect",
            {"design", "estimand", "overlap_gate_status", "clipping_enabled"},
        ),
    ],
)
def test_causal_telemetry_contains_required_low_cardinality_dimensions(
    case_id: str,
    required_keys: set[str],
) -> None:
    provider = _RecordingProvider()

    run_statistical_fixture(_case(case_id), observability_provider=provider)

    assert len(provider.records) == 1
    assert required_keys <= set(provider.records[0].metadata)


@pytest.mark.parametrize(
    ("metadata", "expected_violation"),
    [
        ({"payload": [0.1, 0.2, 0.3]}, "forbidden_value:numeric_sequence"),
        ({"candidate": "account-0001"}, "forbidden_value:unit_identifier"),
        ({"candidate": "user_123"}, "forbidden_value:unit_identifier"),
        (
            {"candidate": "550e8400-e29b-41d4-a716-446655440000"},
            "forbidden_value:unit_identifier",
        ),
        ({"candidate": "person@example.com"}, "forbidden_value:unit_identifier"),
        ({"payload": {"treated": 1}}, "forbidden_key:treated"),
        ({"payload": {"outcome": 0.25}}, "forbidden_key:outcome"),
        ({"payload": {"unitId": "opaque"}}, "forbidden_key:unit_id"),
        ({"payload": {"Unit_ID": "opaque"}}, "forbidden_key:unit_id"),
        ({"payload": {"nuisance_predictions": [0.2]}}, "forbidden_key:nuisance_predictions"),
        ({"payload": {"residuals": [0.1]}}, "forbidden_key:residuals"),
        ({"payload": {"influence_values": [0.1]}}, "forbidden_key:influence_values"),
        ({"payload": {"fold_membership": [1]}}, "forbidden_key:fold_membership"),
        ({"payload": {"subgroup_membership": ["a"]}}, "forbidden_key:subgroup_membership"),
        ({"payload": {"raw_subgroup_rows": ["a"]}}, "forbidden_key:raw_subgroup_rows"),
    ],
)
def test_telemetry_privacy_rejects_forbidden_keys_and_value_shapes(
    metadata: dict[str, object],
    expected_violation: str,
) -> None:
    record = BufferedSpanRecord(name="causal_test", run_type="chain", metadata=metadata)

    violations = statistical_telemetry.telemetry_privacy_violations((record,))

    assert expected_violation in violations
