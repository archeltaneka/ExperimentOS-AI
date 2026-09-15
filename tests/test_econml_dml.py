"""Real LinearDML estimates, inference, repeatability and safe failures."""

from __future__ import annotations

import math

import pytest

from tests.causal_identification_fixtures import provenance
from tests.dml_fixtures import dml_execution, dml_identification, dml_table
from tests.econml_fixtures import assert_owned_graph, linear_rows, requires_econml


@requires_econml
@pytest.mark.parametrize("effect", [2.0, 0.0])
def test_known_and_null_dml_effects_have_finite_documented_inference(effect: float) -> None:
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter

    result = EconMLDMLAdapter(
        constant_effect_assumption=True,
    ).analyze(
        dml_execution(fold_count=4, seed=812),
        dml_table(linear_rows(effect)),
        provenance=provenance(),
    )
    assert result.status.value == "completed", result.model_dump_json()
    assert result.point_estimate == pytest.approx(effect, abs=0.25)
    inference = result.inference
    assert inference.standard_error > 0
    assert math.isfinite(inference.statistic)
    assert inference.confidence_interval.lower < result.point_estimate
    assert inference.confidence_interval.upper > result.point_estimate
    assert inference.confidence_interval.confidence_level == 0.95
    assert inference.method == "statsmodels_hc1"
    if effect == 0:
        assert inference.p_value > 0.05
    metadata = result.adapter_provenance
    assert metadata.econml_version == "0.17.0"
    assert metadata.estimator_class == "econml.dml.LinearDML"
    assert metadata.seed == metadata.random_state == 812
    assert metadata.treatment_type == "binary"
    assert metadata.outcome_type == "continuous"
    assert metadata.estimand == "ate"
    assert len(result.fold_fits) == 4
    assert result.nuisance_diagnostics is not None
    assert_owned_graph(result)


@requires_econml
def test_identical_and_reordered_runs_reproduce_equivalent_dml_results() -> None:
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter

    adapter = EconMLDMLAdapter(
        constant_effect_assumption=True,
    )
    execution = dml_execution(fold_count=4, seed=812)
    rows = linear_rows()
    first = adapter.analyze(execution, dml_table(rows), provenance=provenance())
    assert first.status.value == "completed"
    for selected in (rows, tuple(reversed(rows))):
        repeated = adapter.analyze(execution, dml_table(selected), provenance=provenance())
        assert repeated.model_dump() == first.model_dump()


def test_invalid_identification_abstains_before_optional_dependency_is_loaded(monkeypatch) -> None:
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter, dependency
    from packages.experiments.analysis.causal.variables import MeasurementTiming

    def forbidden():
        pytest.fail("invalid identification reached optional estimator loading")

    monkeypatch.setattr(dependency, "load_econml", forbidden)
    result = EconMLDMLAdapter(
        constant_effect_assumption=True,
    ).analyze(
        dml_execution(
            identification_result=dml_identification(
                adjustment_timing=MeasurementTiming.POST_TREATMENT
            )
        ),
        dml_table(linear_rows()),
        provenance=provenance(),
    )
    assert result.status.value == "invalid"
    assert result.point_estimate is None


@requires_econml
@pytest.mark.parametrize(
    ("operation", "code"),
    [("fit", "ESTIMATOR_FIT_FAILURE"), ("effect_inference", "INFERENCE_FAILURE")],
)
def test_third_party_operation_failure_is_normalized(
    monkeypatch, operation: str, code: str
) -> None:
    from econml.dml import LinearDML

    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter

    def fail(*args, **kwargs):
        raise ValueError("row secret: account-123")

    monkeypatch.setattr(LinearDML, operation, fail)
    result = EconMLDMLAdapter(
        constant_effect_assumption=True,
    ).analyze(
        dml_execution(fold_count=4, seed=812), dml_table(linear_rows()), provenance=provenance()
    )
    assert result.status.value == "abstained"
    assert result.abstention_reason.code == code
    assert "account-123" not in result.model_dump_json()
    assert_owned_graph(result)


@requires_econml
@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("pred", float("nan"), "NONFINITE_ESTIMATE"),
        ("pred_stderr", float("inf"), "NONFINITE_UNCERTAINTY"),
        ("pred_stderr", 0.0, "NONFINITE_UNCERTAINTY"),
    ],
)
def test_invalid_inference_values_suppress_the_entire_estimate(
    monkeypatch, field: str, value: float, code: str
) -> None:
    import numpy as np
    from econml.dml import LinearDML

    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter

    original = LinearDML.effect_inference

    def invalid(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        setattr(result, field, np.array([value]))
        return result

    monkeypatch.setattr(LinearDML, "effect_inference", invalid)
    result = EconMLDMLAdapter(
        constant_effect_assumption=True,
    ).analyze(
        dml_execution(fold_count=4, seed=812), dml_table(linear_rows()), provenance=provenance()
    )
    assert result.abstention_reason.code == code
    assert result.point_estimate is result.inference is None
