from importlib import import_module

from tests.test_impact_service import analyze


def test_report_keeps_evidence_inputs_and_uncertainty_separate():
    report = import_module("packages.experiments.analysis.impact.reporting").render_scenario(
        analyze()
    )
    assert "Statistical uncertainty" in report
    assert "Business-input band" in report
    assert "Combined scenario band" in report
    assert "user_supplied" in report and "assumed" in report
    assert "5000" in report and "15000" in report
    assert "USD" in report
    assert "net_monetary_impact" in report
    assert "SHIP" not in report


def test_refusal_report_never_presents_numeric_impact():
    report = import_module("packages.experiments.analysis.impact.reporting").render_scenario(
        analyze(source=0.02)
    )
    assert "abstained" in report
    assert "Combined scenario band" not in report


def test_public_scenario_round_trip_preserves_every_layer():
    public = import_module("packages.experiments.analysis")
    result = analyze()
    restored = public.business_impact_result_from_json(public.to_canonical_json(result))
    assert restored == result
    assert (
        public.BusinessImpactService
        is import_module("packages.experiments.analysis.impact").BusinessImpactService
    )


def test_report_includes_source_provenance_and_interval_level():
    result = analyze()
    report = import_module("packages.experiments.analysis.impact.reporting").render_scenario(result)
    assert result.source.provenance[0].source_id in report
    assert "0.95" in report
