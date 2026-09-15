"""Minimal adapter policy guards reject conclusive invalid or incomplete results."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal.dml.results import DMLStatus
from tests.causal_identification_fixtures import provenance
from tests.dml_fixtures import dml_execution, dml_table
from tests.econml_fixtures import linear_rows, requires_econml


def test_missing_dependency_cannot_be_promoted_to_success(monkeypatch):
    from packages.experiments.analysis.causal.advanced.quality import evaluate_advanced_quality
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter, dependency

    def absent():
        raise dependency.AdapterError("OPTIONAL_DEPENDENCY_UNAVAILABLE", "Dependency absent.")

    monkeypatch.setattr(dependency, "load_econml", absent)

    result = EconMLDMLAdapter(
        constant_effect_assumption=True,
    ).analyze(dml_execution(), dml_table(linear_rows()), provenance=provenance())
    corrupted = result.model_copy(update={"status": DMLStatus.COMPLETED})
    assert evaluate_advanced_quality(corrupted).blocking_findings


@requires_econml
@pytest.mark.parametrize(
    "corruption", ["uncertainty", "estimate", "seed", "inference", "constant_effect"]
)
def test_policy_blocks_missing_uncertainty_nonfinite_values_and_unsupported_configuration(
    corruption,
):
    from packages.experiments.analysis.causal.advanced.quality import evaluate_advanced_quality
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter

    result = EconMLDMLAdapter(
        constant_effect_assumption=True,
    ).analyze(
        dml_execution(fold_count=4, seed=812), dml_table(linear_rows()), provenance=provenance()
    )
    assert result.status is DMLStatus.COMPLETED
    assert evaluate_advanced_quality(result).blocking_findings == ()
    changes = {
        "uncertainty": {"inference": None},
        "estimate": {"point_estimate": float("inf")},
        "seed": {
            "adapter_provenance": result.adapter_provenance.model_copy(update={"random_state": 0})
        },
        "inference": {
            "configuration": result.configuration.model_copy(update={"inference_mode": "bootstrap"})
        },
        "constant_effect": {
            "configuration": result.configuration.model_copy(
                update={"constant_effect_assumption": False}
            )
        },
    }
    assert evaluate_advanced_quality(
        result.model_copy(update=changes[corruption])
    ).blocking_findings
