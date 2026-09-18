"""Behavioral mutations for the shared advanced causal conformance boundary."""

from datetime import datetime

import pytest

from tests.dml_fixtures import dml_execution


def test_configuration_fingerprint_tracks_semantics_not_source_rows():
    from packages.experiments.analysis.causal.advanced.conformance import configuration_fingerprint

    execution = dml_execution(seed=17)
    first = configuration_fingerprint(execution, "repository_dml")
    assert len(first) == 64
    assert first == configuration_fingerprint(execution.model_copy(), "repository_dml")
    assert first != configuration_fingerprint(dml_execution(seed=18), "repository_dml")
    assert first != configuration_fingerprint(execution, "econml_linear_dml")
    assert "prior_orders" not in first


def test_boundary_rejects_hidden_objects_exceptions_and_cycles():
    from packages.evals.statistical.advanced.checks import boundary_violations

    assert boundary_violations({"safe": [1, "ok", datetime(2026, 1, 1)]}) == ()
    for bad in (object(), ValueError("private-array-123")):
        assert boundary_violations({"nested": [bad]})
    cycle = []
    cycle.append(cycle)
    assert boundary_violations(cycle)


@pytest.mark.parametrize(
    "field",
    [
        "estimand",
        "contrast",
        "population",
        "outcome",
        "covariates",
        "assumptions",
        "fixture",
        "subgroups",
    ],
)
def test_incompatible_comparison_is_skipped_before_numbers(field):
    from packages.evals.statistical.advanced.checks import compare_effects

    signature = dict.fromkeys(
        (
            "estimand",
            "contrast",
            "population",
            "outcome",
            "covariates",
            "assumptions",
            "fixture",
            "subgroups",
        ),
        "same",
    )
    changed = {**signature, field: "different"}
    check = compare_effects(signature, changed, 2.0, 9999.0)
    assert check.status.value == "skipped"
    assert field in check.message


def test_comparable_difference_is_advisory_and_never_exact_equality():
    from packages.evals.statistical.advanced.checks import compare_effects

    signature = dict.fromkeys(
        (
            "estimand",
            "contrast",
            "population",
            "outcome",
            "covariates",
            "assumptions",
            "fixture",
            "subgroups",
        ),
        "same",
    )
    assert compare_effects(signature, signature, 2.0, 2.01).status.value == "pass"
    assert compare_effects(signature, signature, 2.0, 20.0).status.value == "advisory"


def test_numerical_replay_does_not_hide_categorical_changes():
    from packages.evals.statistical.advanced.checks import equivalent

    assert equivalent({"estimate": 2.0, "seed": 1}, {"estimate": 2.0 + 1e-12, "seed": 1})
    assert not equivalent({"estimate": 2.0, "seed": 1}, {"estimate": 2.0, "seed": 2})
    assert not equivalent({"estimate": float("nan")}, {"estimate": float("nan")})


def test_missing_comparison_evidence_is_not_compatibility():
    from packages.evals.statistical.advanced.checks import COMPATIBILITY_FIELDS, compare_effects

    signature = dict.fromkeys(COMPATIBILITY_FIELDS, "same")
    signature["assumptions"] = None
    assert compare_effects(signature, signature, 2.0, 2.0).status.value == "skipped"


def test_private_model_attributes_cannot_hide_foreign_objects():
    from packages.evals.statistical.advanced.checks import boundary_violations

    request = dml_execution()
    object.__setattr__(request, "__pydantic_private__", {"backend": object()})
    assert boundary_violations(request) == ("unowned_object",)


def test_relative_tolerance_has_an_explicit_absolute_floor():
    from packages.evals.statistical.models import StatisticalTolerance

    tolerance = StatisticalTolerance(
        absolute=0.01, relative=0.001, rationale="Scale-aware arithmetic", provenance="test"
    )
    assert tolerance.accepts(100.1, 100.0)
    assert not tolerance.accepts(100.2, 100.0)
    assert tolerance.accepts(0.005, 0.0)


def test_inference_and_refuter_settings_change_fingerprints():
    from packages.experiments.analysis.causal.advanced.conformance import configuration_fingerprint
    from packages.experiments.analysis.causal.advanced.models import AdvancedEstimatorConfig
    from tests.dowhy_fixtures import execution

    first = configuration_fingerprint(
        dml_execution(), "econml_linear_dml", AdvancedEstimatorConfig()
    )
    assert first != configuration_fingerprint(
        dml_execution(), "econml_linear_dml", AdvancedEstimatorConfig(inference_mode="bootstrap")
    )
    graph_request = execution()
    changed = graph_request.model_copy(
        update={
            "configuration": graph_request.configuration.model_copy(update={"num_simulations": 21})
        }
    )
    assert configuration_fingerprint(
        graph_request, "experimentos_dowhy"
    ) != configuration_fingerprint(changed, "experimentos_dowhy")
