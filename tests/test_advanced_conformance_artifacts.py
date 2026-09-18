"""Structured advanced status/provenance is the only Markdown source."""

import pytest

from packages.evals.statistical.advanced.fixtures import reference_cases
from packages.evals.statistical.evaluator import StatisticalBaselineEvaluator
from packages.evals.statistical.models import StatisticalBaselineReport, StatisticalReferenceDataset
from packages.evals.statistical.reporting import render_statistical_baseline_markdown


@pytest.mark.parametrize(
    "semantic,verdict",
    [
        ("successful", "pass"),
        ("unavailable", "advisory"),
        ("skipped", "skipped"),
        ("failed", "fail"),
        ("invalid", "pass"),
        ("abstained", "pass"),
        ("successful", "advisory"),
    ],
)
def test_all_statuses_and_execution_kind_render_from_json(semantic, verdict):
    case = next(c for c in reference_cases() if c.case_id == "advanced-repository_dml-success")
    report = StatisticalBaselineEvaluator().evaluate(
        StatisticalReferenceDataset(
            baseline_id="artifact-test",
            version="1",
            fixture_provenance="phase4-statistical-fixtures-v1",
            cases=(case,),
        )
    )
    payload = report.model_dump(mode="json")
    item = payload["case_results"][0]
    item["evaluation_status"] = verdict
    item["advanced"]["semantic_status"] = semantic
    item["advanced"]["execution_kind"] = "controlled"
    restored = StatisticalBaselineReport.model_validate(payload)
    markdown = render_statistical_baseline_markdown(restored)
    assert f"/ {semantic} | {verdict}" in markdown
    assert "controlled" in markdown
    assert item["advanced"]["configuration_fingerprint"] in markdown
    assert item["advanced"]["implementation_version"] in markdown
    assert "subgroup_membership" not in restored.model_dump_json()


def test_injected_inference_is_not_labeled_real_execution():
    from packages.evals.statistical.advanced.harness import evaluate_advanced_case

    case = next(
        c for c in reference_cases() if c.case_id == "advanced-econml_dml-inference_failure"
    )
    result = evaluate_advanced_case(case)
    assert result.advanced.execution_kind == "controlled"
