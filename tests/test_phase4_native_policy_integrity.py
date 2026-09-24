"""Native evidence cannot disappear behind retained success summaries."""

import json
from copy import deepcopy

import pytest


@pytest.fixture(scope="module")
def native_report():
    from packages.evals.statistical.dataset import (
        DEFAULT_STATISTICAL_DATASET_PATH,
        load_statistical_reference_cases,
    )
    from packages.evals.statistical.evaluator import StatisticalBaselineEvaluator

    return (
        StatisticalBaselineEvaluator()
        .evaluate(load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH))
        .model_dump(mode="json")
    )


@pytest.mark.parametrize(
    "mutation",
    ["empty", "missing", "duplicate", "checks", "skip", "counter", "capability", "required-check"],
)
def test_native_incomplete_evidence_blocks_policy(native_report, tmp_path, mutation):
    from packages.evals.policy.adapters import _load_statistical_baseline_json

    payload = deepcopy(native_report)
    cases = payload["case_results"]
    if mutation == "empty":
        cases.clear()
    elif mutation == "missing":
        cases.pop()
    elif mutation == "duplicate":
        cases[-1] = deepcopy(cases[0])
    elif mutation == "checks":
        for case in cases:
            case["checks"] = []
    elif mutation == "skip":
        cases[0]["checks"][0]["status"] = "skipped"
    elif mutation == "counter":
        payload["cases_passed"] += 1
    elif mutation == "capability":
        cases[0]["capability"] = "randomized_binary"
    else:
        cases[0]["checks"].pop()
    path = tmp_path / "report.json"
    path.write_text(json.dumps(payload))
    metrics = _load_statistical_baseline_json(path)
    assert metrics["statistics.failures.case_inventory"].value > 0


def test_complete_native_inventory_is_valid(native_report, tmp_path):
    from packages.evals.policy.adapters import _load_statistical_baseline_json

    path = tmp_path / "report.json"
    path.write_text(json.dumps(native_report))
    assert _load_statistical_baseline_json(path)["statistics.failures.case_inventory"].value == 0


def test_optional_subinventory_has_scope_specific_comparison_applicability():
    from packages.evals.statistical.advanced.registry import REGISTRY
    from packages.evals.statistical.dataset import (
        DEFAULT_STATISTICAL_DATASET_PATH,
        load_statistical_reference_cases,
    )
    from packages.evals.statistical.evaluator import StatisticalBaselineEvaluator
    from packages.evals.statistical.native_integrity import native_integrity_metrics

    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    dataset = dataset.model_copy(
        update={
            "cases": tuple(
                c
                for c in dataset.cases
                if c.advanced and REGISTRY[c.advanced.capability_id].dependency
            )
        }
    )
    report = (
        StatisticalBaselineEvaluator()
        .evaluate(dataset)
        .model_copy(update={"scope": "optional-adapters"})
    )
    assert native_integrity_metrics(report)["statistics.failures.case_inventory"] == 0
