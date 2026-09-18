from importlib import import_module

import pytest


def test_interval_product_checks_all_endpoints_and_negative_values():
    m = import_module("packages.experiments.analysis.impact.arithmetic")
    assert m.multiply(m.Bounds(-1, 3), m.Bounds(2, 4)) == m.Bounds(-4, 12)
    assert m.multiply(m.Bounds(-3, -1), m.Bounds(-4, -2)) == m.Bounds(2, 12)


def test_subtraction_and_overflow():
    m = import_module("packages.experiments.analysis.impact.arithmetic")
    assert m.subtract(m.Bounds(10, 30), m.Bounds(2, 5)) == m.Bounds(5, 28)
    with pytest.raises(ValueError):
        m.multiply(m.Bounds(1e300, 1e300), m.Bounds(1e300, 1e300))


def test_relative_formula_requires_explicit_baseline_and_preserves_its_range():
    from packages.experiments.analysis.impact.calculation import evaluate
    from packages.experiments.analysis.impact.inputs import BusinessImpactRequest
    from packages.experiments.analysis.impact.source_models import SourceEffect
    from packages.experiments.analysis.impact.sources import adapt_source
    from packages.experiments.analysis.impact.validation import validate
    from tests.impact_fixtures import binary_source, evidence, request_payload

    raw = adapt_source(binary_source()).model_dump(mode="json")
    raw.update(effect_scale="relative_binary", point=0.05)
    raw["interval"].update(lower=0.025, upper=0.075)
    effect = SourceEffect.model_validate(raw)
    p = request_payload()
    request = BusinessImpactRequest.model_validate(p)
    assert any(d.code == "impact.baseline_missing" for d in validate(effect, request).diagnostics)
    p["baseline"] = {
        "value": {"lower": 0.1, "upper": 0.3, "central": 0.2},
        "event": "conversions",
        "per_entity": "users",
        "horizon": p["horizon"]["basis"],
        "evidence": evidence(),
    }
    request = BusinessImpactRequest.model_validate(p)
    alignment = validate(effect, request)
    assert not alignment.diagnostics
    assert evaluate(effect, request, alignment, "central")[
        "gross_incremental_outcome"
    ].lower == pytest.approx(500)
    combined = evaluate(effect, request, alignment, "combined")["gross_incremental_outcome"]
    assert combined.lower == pytest.approx(125)
    assert combined.upper == pytest.approx(1125)


def test_normalized_internal_effect_is_not_a_public_effect_source():
    from packages.experiments.analysis.impact import BusinessImpactService
    from packages.experiments.analysis.impact.sources import adapt_source
    from tests.impact_fixtures import binary_source, request_payload

    result = BusinessImpactService().analyze(adapt_source(binary_source()), request_payload())
    assert result.status.value == "abstained"
