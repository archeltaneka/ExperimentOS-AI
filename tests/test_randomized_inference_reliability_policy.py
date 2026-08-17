from __future__ import annotations

from pathlib import Path

from packages.evals.policy.adapters import load_source
from packages.evals.policy.config import load_quality_policy
from packages.evals.policy.models import PolicySource
from packages.evals.statistical.dataset import (
    DEFAULT_STATISTICAL_DATASET_PATH,
    load_statistical_reference_cases,
)
from packages.evals.statistical.evaluator import StatisticalBaselineEvaluator
from packages.evals.statistical.reporting import statistical_baseline_to_json


def test_policy_adapter_exposes_method_and_reliability_aggregates(tmp_path) -> None:
    report = StatisticalBaselineEvaluator().evaluate(
        load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    )
    path = tmp_path / "phase4" / "statistical_baseline.json"
    path.parent.mkdir(parents=True)
    path.write_text(statistical_baseline_to_json(report), encoding="utf-8")

    source = load_source(
        PolicySource(
            source_id="statistics",
            path=path.relative_to(tmp_path),
            format="statistical_baseline_json",
        ),
        tmp_path,
    )

    assert source is not None
    assert source.metrics["statistics.failures.assumptions"].value == 0
    assert source.metrics["statistics.failures.plan_integrity"].value == 0
    assert source.metrics["statistics.failures.telemetry_privacy"].value == 0
    assert source.metrics["statistics.method.cuped.failed"].value == 0
    assert source.metrics["statistics.method.cuped.advisory"].value >= 1
    assert source.metrics["statistics.method.sequential.invalid"].value >= 1
    assert source.metrics["statistics.method.bayesian.skipped"].value == 1


def test_central_policy_classifies_contract_rules_as_blocking_and_performance_as_advisory() -> None:
    policy = load_quality_policy(Path("config/evaluation/quality_policy.yaml"))
    metrics = {metric.metric_id: metric for metric in policy.metrics}

    for metric_id in (
        "statistics.failures.assumptions",
        "statistics.failures.plan_integrity",
        "statistics.failures.telemetry_privacy",
        "statistics.failures.bayesian_semantics",
    ):
        assert metrics[metric_id].severity in {"fail", "critical"}
        assert metrics[metric_id].value == 0
    assert metrics["statistics.performance.advisory_findings"].severity == "warning"
