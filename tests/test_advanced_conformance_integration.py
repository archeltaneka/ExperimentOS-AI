"""Advanced conformance uses the existing command, report and central policy."""

import json

from packages.evals.statistical.dataset import (
    DEFAULT_STATISTICAL_DATASET_PATH,
    load_statistical_reference_cases,
)


def test_default_reference_inventory_contains_all_registered_capabilities():
    from packages.evals.statistical.advanced.registry import REGISTRY

    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    assert set(REGISTRY) <= {c.capability.value for c in dataset.cases}


def test_canonical_cli_renders_advanced_and_blocks_required_absence(tmp_path, monkeypatch):
    from packages.evals.run_statistical_baseline import main
    from packages.evals.statistical.advanced import harness
    from packages.experiments.analysis.causal.econml import dependency

    monkeypatch.setattr(
        harness,
        "dependency_state",
        lambda p: ("unavailable", None) if p else ("not_required", None),
    )
    monkeypatch.setattr(
        dependency,
        "load_econml",
        lambda: (_ for _ in ()).throw(
            dependency.AdapterError("OPTIONAL_DEPENDENCY_UNAVAILABLE", "absent")
        ),
    )
    out = tmp_path / "report.json"
    md = tmp_path / "report.md"
    args = [
        "--dataset",
        "data/eval/phase4_advanced_conformance.json",
        "--json-output",
        str(out),
        "--output",
        str(md),
    ]
    assert main(args) == 0
    payload = json.loads(out.read_text())
    assert payload["case_results"]
    assert "Advanced Causal Conformance" in md.read_text()
    assert "unavailable" in md.read_text()
    assert main([*args, "--require-optional", "econml"]) == 1
    payload = json.loads(out.read_text())
    assert payload["quality_policy"]["blocking_rule_ids"]


def test_malformed_installed_evidence_overrides_advisory(tmp_path):
    from packages.evals.policy.adapters import _load_statistical_baseline_json
    from packages.evals.statistical.advanced.fixtures import reference_cases
    from packages.evals.statistical.evaluator import StatisticalBaselineEvaluator
    from packages.evals.statistical.models import StatisticalReferenceDataset

    cases = reference_cases()
    dataset = StatisticalReferenceDataset(
        baseline_id="test",
        version="1",
        fixture_provenance="phase4-statistical-fixtures-v1",
        cases=cases,
    )
    report = StatisticalBaselineEvaluator().evaluate(dataset)
    data = report.model_dump(mode="json")
    data["case_results"][0]["checks"].append(
        {
            "dimension": "interface_leakage",
            "status": "fail",
            "rule_id": "statistics.advanced.interface",
        }
    )
    path = tmp_path / "report.json"
    path.write_text(json.dumps(data))
    metrics = _load_statistical_baseline_json(path)
    assert metrics["statistics.failures.interface_leakage"].value == 1
