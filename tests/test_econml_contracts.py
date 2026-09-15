"""Unsupported public configurations fail closed before optional imports."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal.designs import ObservationalDesignType
from packages.experiments.analysis.causal.estimands import CausalEstimandKind
from packages.experiments.analysis.metrics import MetricType
from tests.causal_identification_fixtures import provenance
from tests.dml_fixtures import dml_execution, dml_identification, dml_table
from tests.econml_fixtures import dr_execution, linear_rows
from tests.hte_fixtures import effect_rows, hte_table


@pytest.mark.parametrize("hte", [False, True])
@pytest.mark.parametrize("inference", ["bootstrap", "auto", "hc0", "none"])
def test_unsupported_inference_does_not_load_or_fit_optional_estimator(monkeypatch, hte, inference):
    from packages.experiments.analysis.causal.advanced.models import AdvancedEstimatorConfig
    from packages.experiments.analysis.causal.econml import (
        EconMLDMLAdapter,
        EconMLHTEAdapter,
        dependency,
    )

    monkeypatch.setattr(dependency, "load_econml", lambda: pytest.fail("inference gate bypassed"))
    config = AdvancedEstimatorConfig(inference_mode=inference)
    adapter = (
        EconMLHTEAdapter(configuration=config)
        if hte
        else EconMLDMLAdapter(constant_effect_assumption=True, configuration=config)
    )
    result = adapter.analyze(
        dr_execution() if hte else dml_execution(),
        hte_table(effect_rows()) if hte else dml_table(linear_rows()),
        provenance=provenance(),
    )
    assert result.status.value == "unsupported"
    assert any(item.code == "UNSUPPORTED_INFERENCE" for item in result.diagnostics)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"estimand_kind": CausalEstimandKind.ATT},
        {"outcome_type": MetricType.BINARY},
        {"design_type": ObservationalDesignType.DID},
    ],
)
def test_unsupported_dml_contracts_cannot_reach_optional_fit(monkeypatch, kwargs):
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter, dependency

    monkeypatch.setattr(dependency, "load_econml", lambda: pytest.fail("input gate bypassed"))
    result = EconMLDMLAdapter(
        constant_effect_assumption=True,
    ).analyze(
        dml_execution(identification_result=dml_identification(**kwargs)),
        dml_table(linear_rows()),
        provenance=provenance(),
    )
    assert result.status.value in ("unsupported", "invalid")
    assert result.point_estimate is None


def test_unrecognized_treatment_values_and_missing_columns_are_invalid():
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter

    for rows in (
        ({**linear_rows()[0], "treated": 2}, *linear_rows()[1:]),
        tuple(
            {key: value for key, value in row.items() if key != "outcome"} for row in linear_rows()
        ),
    ):
        result = EconMLDMLAdapter(
            constant_effect_assumption=True,
        ).analyze(dml_execution(), dml_table(rows), provenance=provenance())
        assert result.status.value == "invalid"
        assert result.point_estimate is None


def test_adapters_satisfy_owned_estimator_protocol():
    from packages.experiments.analysis.causal.advanced.protocols import AdvancedCausalEstimator
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter, EconMLHTEAdapter

    assert isinstance(
        EconMLDMLAdapter(
            constant_effect_assumption=True,
        ),
        AdvancedCausalEstimator,
    )
    assert isinstance(EconMLHTEAdapter(), AdvancedCausalEstimator)


def test_constant_effect_ate_requires_explicit_assumption(monkeypatch):
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter, dependency

    monkeypatch.setattr(dependency, "load_econml", lambda: pytest.fail("assumption gate bypassed"))
    result = EconMLDMLAdapter().analyze(
        dml_execution(), dml_table(linear_rows()), provenance=provenance()
    )
    assert result.status.value == "unsupported"
    assert any(d.code == "UNSUPPORTED_ESTIMAND" for d in result.diagnostics)


@pytest.mark.parametrize("unsupported", ["outcome", "estimand"])
def test_unsupported_hte_outcome_and_estimand_fail_closed(monkeypatch, unsupported):
    from packages.experiments.analysis.causal import (
        CausalIdentificationService,
        ObservationalAnalysisRequest,
    )
    from packages.experiments.analysis.causal.econml import EconMLHTEAdapter, dependency

    execution = dr_execution()
    source = execution.identification_result.identification_request
    other = dml_identification(
        **(
            {"outcome_type": MetricType.BINARY}
            if unsupported == "outcome"
            else {"estimand_kind": CausalEstimandKind.ATE}
        )
    ).identification_request
    changed = source.model_copy(update={unsupported: getattr(other, unsupported)})
    identified = CausalIdentificationService().identify(
        ObservationalAnalysisRequest(request_id=execution.request_id, identification=changed)
    )
    monkeypatch.setattr(dependency, "load_econml", lambda: pytest.fail("unsupported gate bypassed"))
    result = EconMLHTEAdapter().analyze(
        execution.model_copy(update={"identification_result": identified}),
        hte_table(effect_rows()),
        provenance=provenance(),
    )
    assert result.status.value in ("unsupported", "invalid")
    assert all(g.estimate is None for g in result.subgroup_results)
