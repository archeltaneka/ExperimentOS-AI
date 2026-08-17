from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.evals.statistical.dataset import (
    DEFAULT_STATISTICAL_DATASET_PATH,
    load_statistical_reference_cases,
)


def _case(case_id: str = "case-a") -> dict[str, object]:
    return {
        "case_id": case_id,
        "capability": "eligibility_validation",
        "category": "successful_inference",
        "analysis_design": "randomized_experiment",
        "metric_type": "continuous",
        "fixture_id": "valid_continuous_validation",
        "expected_status": "eligible",
        "expected_method": "fixed_horizon_ab",
        "expected_diagnostic_codes": [],
        "expected_advisory_codes": [],
        "expected_abstention": False,
        "expected_abstention_reason": None,
        "expected_values": [
            {"path": "dataset_summary.input_row_count", "value": 8},
            {
                "path": "outcome_summary.has_variation",
                "value": True,
            },
        ],
        "notes": "Hand-authored validation reference case.",
        "fixture_provenance": "phase4-statistical-fixtures-v1",
    }


def _payload(*cases: dict[str, object]) -> dict[str, object]:
    return {
        "baseline_id": "phase4-statistical-reliability",
        "version": "1.0.0",
        "fixture_provenance": "phase4-statistical-fixtures-v1",
        "cases": list(cases),
    }


def test_repository_dataset_loads_in_stable_case_id_order() -> None:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)

    case_ids = tuple(case.case_id for case in dataset.cases)

    assert case_ids == tuple(sorted(case_ids))
    assert len(case_ids) == len(set(case_ids))
    assert dataset.baseline_id == "phase4-statistical-reliability"
    assert dataset.version == "2.0.0"


def test_loader_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(_payload(_case(), _case())), encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate statistical case_id: case-a"):
        load_statistical_reference_cases(path)


def test_loader_rejects_malformed_case(tmp_path: Path) -> None:
    malformed = _case()
    malformed.pop("notes")
    path = tmp_path / "malformed.json"
    path.write_text(json.dumps(_payload(malformed)), encoding="utf-8")

    with pytest.raises(ValueError, match="statistical reference dataset is invalid"):
        load_statistical_reference_cases(path)


def test_loader_requires_documented_tolerance_for_floating_expected_values(
    tmp_path: Path,
) -> None:
    missing_tolerance = _case()
    missing_tolerance["expected_values"] = [{"path": "population.summary.mean", "value": 2.5}]
    path = tmp_path / "missing-tolerance.json"
    path.write_text(json.dumps(_payload(missing_tolerance)), encoding="utf-8")

    with pytest.raises(ValueError, match="floating expected values require a tolerance"):
        load_statistical_reference_cases(path)


def test_loader_preserves_tolerance_rationale_and_provenance(tmp_path: Path) -> None:
    documented = _case()
    documented["expected_values"] = [
        {
            "path": "population.summary.mean",
            "value": 2.5,
            "tolerance": {
                "absolute": 1e-12,
                "rationale": "Direct arithmetic summary with small binary-exact inputs.",
                "provenance": "hand-calculated from [1, 2, 3, 4]",
            },
        }
    ]
    path = tmp_path / "documented.json"
    path.write_text(json.dumps(_payload(documented)), encoding="utf-8")

    dataset = load_statistical_reference_cases(path)

    tolerance = dataset.cases[0].expected_values[0].tolerance
    assert tolerance is not None
    assert tolerance.absolute == 1e-12
    assert tolerance.provenance == "hand-calculated from [1, 2, 3, 4]"
