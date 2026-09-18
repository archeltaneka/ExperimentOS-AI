"""Provenance and privacy of actual public service telemetry."""

import pytest

from packages.evals.statistical.telemetry import _RecordingProvider
from tests.causal_identification_fixtures import provenance
from tests.dml_fixtures import dml_execution, dml_table
from tests.econml_fixtures import linear_rows


def test_repository_service_records_configuration_on_result_and_span():
    from packages.experiments.analysis.causal.dml.service import DoubleMachineLearningEstimator

    provider = _RecordingProvider()
    result = DoubleMachineLearningEstimator(observability_provider=provider).analyze(
        dml_execution(), dml_table(linear_rows()), provenance=provenance()
    )
    assert result.configuration_fingerprint_sha256
    metadata = provider.records[0].metadata
    assert metadata["configuration_fingerprint"] == result.configuration_fingerprint_sha256
    assert metadata["adapter_version"] == "1"
    assert metadata["dependency_state"] == "not_required"


@pytest.mark.parametrize(
    "payload",
    [
        {"innocent": "private-graph-canary"},
        {"innocent": object()},
        {"coefficients": 2.0},
        {"residual_arrays": [1.2, 2.3]},
        {"safe": "unit-secret"},
        {"method": "diagnosis=HIV-positive"},
        {"row_count": {"status": 3.14159}},
        {"diagnostic_codes": ["patient Alice Smith"]},
    ],
)
def test_privacy_checks_values_and_unknown_keys_without_echoing_secrets(payload):
    from packages.evals.statistical.advanced.privacy import privacy_violations

    provider = _RecordingProvider()
    span = provider.start_root_span("test", metadata=payload)
    span.finish()
    violations = privacy_violations(tuple(provider.records))
    assert violations
    assert "private-graph-canary" not in repr(violations)


def test_unsupported_inference_provenance_is_safe():
    from packages.experiments.analysis.causal.advanced.models import AdvancedEstimatorConfig
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter

    provider = _RecordingProvider()
    result = EconMLDMLAdapter(
        configuration=AdvancedEstimatorConfig(inference_mode="private-graph-canary"),
        observability_provider=provider,
    ).analyze(dml_execution(), dml_table(linear_rows()), provenance=provenance())
    assert result.status.value == "unsupported"
    assert result.configuration_fingerprint_sha256
    assert "private-graph-canary" not in repr(provider.records)


def test_second_execution_telemetry_is_also_checked(monkeypatch):
    from packages.evals.statistical.advanced import harness
    from tests.test_advanced_conformance_mutations import case_for

    original = harness.run_case
    count = 0

    def corrupted_repeat(*args):
        nonlocal count
        execution = original(*args)
        count += 1
        if count == 2:
            execution.records[0].metadata["method"] = "private-graph-canary"
        return execution

    monkeypatch.setattr(harness, "run_case", corrupted_repeat)
    result = harness.evaluate_advanced_case(case_for())
    assert not result.passed
    assert any(
        c.dimension == "telemetry_privacy" and c.status.value == "fail" for c in result.checks
    )
