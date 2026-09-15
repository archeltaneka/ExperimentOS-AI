"""Unsupported shapes, overlap, timing and inference fail closed for both adapters."""

from __future__ import annotations

import pytest

from packages.experiments.analysis.causal.hte.models import CategoricalSubgroup, HTEModifierType
from tests.causal_identification_fixtures import provenance
from tests.dml_fixtures import dml_execution, dml_table
from tests.econml_fixtures import assert_owned_graph, dr_execution, linear_rows, requires_econml
from tests.hte_fixtures import effect_rows, hte_table


def test_multi_group_modifier_is_explicitly_unsupported_before_dependency_loading(monkeypatch):
    from packages.experiments.analysis.causal.econml import EconMLHTEAdapter, dependency

    execution = dr_execution()
    modifier = execution.modifier.model_copy(
        update={
            "modifier_type": HTEModifierType.FINITE_CATEGORICAL,
            "subgroups": (
                *execution.modifier.subgroups,
                CategoricalSubgroup(subgroup_id="my", label="Malaysia", value="MY"),
            ),
        }
    )
    monkeypatch.setattr(dependency, "load_econml", lambda: pytest.fail("modifier gate bypassed"))
    result = EconMLHTEAdapter().analyze(
        execution.model_copy(update={"modifier": modifier}),
        hte_table(effect_rows()),
        provenance=provenance(),
    )
    assert result.status.value == "unsupported"
    assert result.abstention_reason == "INVALID_EFFECT_MODIFIER"


@pytest.mark.parametrize("hte", [False, True])
def test_continuous_treatment_vector_cannot_be_interpreted_as_binary(monkeypatch, hte):
    from packages.experiments.analysis.causal.econml import (
        EconMLDMLAdapter,
        EconMLHTEAdapter,
        dependency,
    )

    monkeypatch.setattr(dependency, "load_econml", lambda: pytest.fail("treatment gate bypassed"))
    rows = effect_rows() if hte else linear_rows()
    invalid = tuple({**row, "treated": 0.25} for row in rows)
    adapter = (
        EconMLHTEAdapter()
        if hte
        else EconMLDMLAdapter(
            constant_effect_assumption=True,
        )
    )
    result = adapter.analyze(
        dr_execution() if hte else dml_execution(),
        hte_table(invalid) if hte else dml_table(invalid),
        provenance=provenance(),
    )
    assert result.status.value == "invalid"
    assert_owned_graph(result)


@requires_econml
@pytest.mark.parametrize("hte", [False, True])
@pytest.mark.parametrize("field", ["pred", "pred_stderr"])
def test_nonfinite_hte_or_dml_output_is_never_public(monkeypatch, hte, field):
    import numpy as np
    from econml.dml import LinearDML
    from econml.dr import LinearDRLearner

    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter, EconMLHTEAdapter

    cls = LinearDRLearner if hte else LinearDML
    original = cls.effect_inference

    def invalid(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        setattr(result, field, np.array([float("nan")]))
        return result

    monkeypatch.setattr(cls, "effect_inference", invalid)
    result = (
        EconMLHTEAdapter()
        if hte
        else EconMLDMLAdapter(
            constant_effect_assumption=True,
        )
    ).analyze(
        dr_execution(fold_count=4) if hte else dml_execution(fold_count=4, seed=812),
        hte_table(effect_rows()) if hte else dml_table(linear_rows()),
        provenance=provenance(),
    )
    assert result.status.value == "abstained"
    assert any(
        d.code == ("NONFINITE_ESTIMATE" if field == "pred" else "NONFINITE_UNCERTAINTY")
        for d in result.diagnostics
    )
    assert_owned_graph(result)


@requires_econml
def test_invalid_inference_shape_is_normalized(monkeypatch):
    import numpy as np
    from econml.dml import LinearDML

    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter

    original = LinearDML.effect_inference

    def invalid(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        result.pred = np.array([1.0, 2.0])
        return result

    monkeypatch.setattr(LinearDML, "effect_inference", invalid)
    result = EconMLDMLAdapter(
        constant_effect_assumption=True,
    ).analyze(
        dml_execution(fold_count=4, seed=812), dml_table(linear_rows()), provenance=provenance()
    )
    assert result.abstention_reason.code == "INVALID_DATA_SHAPE"
    assert result.point_estimate is None


@requires_econml
@pytest.mark.parametrize("hte", [False, True])
def test_nonconverged_nuisance_fit_abstains(monkeypatch, hte):
    from packages.experiments.analysis.causal.advanced.models import AdvancedEstimatorConfig
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter, EconMLHTEAdapter

    config = AdvancedEstimatorConfig(logistic_max_iterations=1)
    result = (
        EconMLHTEAdapter(configuration=config)
        if hte
        else EconMLDMLAdapter(constant_effect_assumption=True, configuration=config)
    ).analyze(
        dr_execution(fold_count=4) if hte else dml_execution(fold_count=4, seed=812),
        hte_table(effect_rows()) if hte else dml_table(linear_rows()),
        provenance=provenance(),
    )
    assert result.status.value == "abstained"
    assert any(d.code == "ESTIMATOR_FIT_FAILURE" for d in result.diagnostics)


@requires_econml
def test_actual_poor_overlap_prevents_dml_inference():
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter

    rows = tuple(
        {
            "account_id": f"poor-{i}",
            "treated": int(i >= 40),
            "prior_orders": float(i - 39.5),
            "outcome": float(i >= 40) + 0.2 * (i - 39.5) + (i % 3) * 0.1,
        }
        for i in range(80)
    )
    result = EconMLDMLAdapter(
        constant_effect_assumption=True,
    ).analyze(dml_execution(fold_count=4), dml_table(rows), provenance=provenance())
    assert result.status.value == "abstained"
    assert result.abstention_reason.code == "dml.overlap.severe"
    assert result.overlap.status.value == "severe"
    assert result.point_estimate is result.inference is None


def test_forged_identification_with_post_treatment_covariate_is_revalidated(monkeypatch):
    from packages.experiments.analysis.causal.econml import EconMLHTEAdapter, dependency
    from packages.experiments.analysis.causal.models import IdentificationStatus
    from packages.experiments.analysis.causal.variables import MeasurementTiming

    execution = dr_execution()
    identified = execution.identification_result
    source = identified.identification_request
    variables = tuple(
        v.model_copy(
            update={
                "timing": v.timing.model_copy(
                    update={
                        "measurement_timing": MeasurementTiming.POST_TREATMENT,
                        "reference_period": None,
                    }
                )
            }
        )
        if v.variable_id == "prior_orders"
        else v
        for v in source.variables
    )
    forged = identified.model_copy(
        update={
            "identification_request": source.model_copy(update={"variables": variables}),
            "status": IdentificationStatus.IDENTIFIED,
        }
    )
    monkeypatch.setattr(
        dependency, "load_econml", lambda: pytest.fail("identification gate bypassed")
    )
    result = EconMLHTEAdapter().analyze(
        execution.model_copy(update={"identification_result": forged}),
        hte_table(effect_rows()),
        provenance=provenance(),
    )
    assert result.status.value == "invalid"
    assert all(g.estimate is None for g in result.subgroup_results)


def test_resolved_adjustment_set_must_match_reidentified_contract():
    from packages.experiments.analysis.causal.econml.common import validate_identification
    from packages.experiments.analysis.causal.econml.dependency import AdapterError

    identified = dml_execution().identification_result
    forged = identified.model_copy(
        update={
            "adjustment_set": identified.adjustment_set.model_copy(
                update={"variable_ids": ("unrelated",)}
            )
        }
    )
    with pytest.raises(AdapterError, match="revalidation"):
        validate_identification(forged)


def test_malformed_modifier_label_returns_owned_failure(monkeypatch):
    from packages.experiments.analysis.causal.econml import EconMLHTEAdapter, dependency

    execution = dr_execution()
    modifier = execution.modifier.model_copy(
        update={
            "subgroups": (
                execution.modifier.subgroups[0].model_copy(update={"label": ""}),
                execution.modifier.subgroups[1],
            )
        }
    )
    monkeypatch.setattr(dependency, "load_econml", lambda: pytest.fail("invalid gate bypassed"))
    result = EconMLHTEAdapter().analyze(
        execution.model_copy(update={"modifier": modifier}),
        hte_table(effect_rows()),
        provenance=provenance(),
    )
    assert result.status.value == "invalid"
    assert result.abstention_reason == "INVALID_DATA_SHAPE"
    assert_owned_graph(result)


def test_malformed_dml_binding_returns_owned_failure():
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter

    execution = dml_execution()
    invalid = execution.model_copy(
        update={"binding": execution.binding.model_copy(update={"outcome_column": ""})}
    )
    result = EconMLDMLAdapter(constant_effect_assumption=True).analyze(
        invalid, dml_table(linear_rows()), provenance=provenance()
    )
    assert result.status.value == "invalid"
    assert result.abstention_reason.code == "INVALID_DATA_SHAPE"
    assert result.point_estimate is result.inference is None
    assert_owned_graph(result)
