from __future__ import annotations

import json

from packages.evals.statistical.dataset import (
    DEFAULT_STATISTICAL_DATASET_PATH,
    load_statistical_reference_cases,
)
from packages.evals.statistical.evaluator import StatisticalBaselineEvaluator
from packages.evals.statistical.reporting import (
    render_statistical_baseline_markdown,
    statistical_baseline_to_json,
)


def test_authoritative_json_contains_every_method_and_policy_evidence_fields() -> None:
    report = StatisticalBaselineEvaluator().evaluate(
        load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    )
    payload = json.loads(statistical_baseline_to_json(report))

    capabilities = {item["capability"] for item in payload["capability_results"]}
    assert capabilities >= {
        "randomized_continuous",
        "randomized_binary",
        "cuped",
        "sequential",
        "bayesian_binary",
        "bayesian_continuous",
    }
    assert payload["cases_failed"] == 0
    assert payload["cases_advisory"] >= 1
    assert payload["cases_skipped"] == 1


def test_markdown_has_method_status_and_reliability_sections() -> None:
    report = StatisticalBaselineEvaluator().evaluate(
        load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    )

    markdown = render_statistical_baseline_markdown(report)

    for heading in (
        "## Overall Randomized-Inference Status",
        "## Fixed-Horizon Status",
        "## CUPED Status",
        "## Sequential Status",
        "## Bayesian Status",
        "## Abstention Correctness",
        "## Determinism",
        "## Telemetry Privacy",
        "## Assumption Completeness",
        "## Uncertainty Completeness",
        "## Limitations",
    ):
        assert heading in markdown
