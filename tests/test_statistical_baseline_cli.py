from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from packages.evals.cli import main as evaluation_cli_main
from packages.evals.run_statistical_baseline import (
    STATISTICAL_INFRASTRUCTURE_EXIT_CODE,
    STATISTICAL_QUALITY_FAILURE_EXIT_CODE,
    main,
)


def test_cli_success_writes_json_and_markdown_artifacts(tmp_path: Path) -> None:
    json_output = tmp_path / "phase4" / "statistical_baseline.json"
    markdown_output = tmp_path / "phase4" / "statistical_baseline.md"

    exit_code = main(
        [
            "--json-output",
            str(json_output),
            "--output",
            str(markdown_output),
        ]
    )

    assert exit_code == 0
    assert json_output.is_file()
    assert markdown_output.is_file()
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "pass"
    assert payload["quality_policy"]["overall_status"] == "pass"
    assert payload["quality_policy"]["rules"]
    assert payload["dataset_size"] == 13
    assert "# Phase 4 Statistical Reliability Baseline" in markdown_output.read_text(
        encoding="utf-8"
    )


def test_cli_returns_quality_failure_for_reference_regression(tmp_path: Path) -> None:
    source = json.loads(
        Path("data/eval/phase4_statistical_baseline.json").read_text(encoding="utf-8")
    )
    case = next(
        item for item in source["cases"] if item["case_id"] == "randomized-continuous-reference"
    )
    expected = next(
        item
        for item in case["expected_values"]
        if item["path"] == "point_effect.absolute_effect.value"
    )
    expected["value"] = 999.0
    dataset = tmp_path / "regression.json"
    dataset.write_text(json.dumps(source), encoding="utf-8")
    json_output = tmp_path / "phase4" / "statistical_baseline.json"

    exit_code = main(
        [
            "--dataset",
            str(dataset),
            "--json-output",
            str(json_output),
            "--output",
            str(tmp_path / "phase4" / "statistical_baseline.md"),
        ]
    )

    assert exit_code == STATISTICAL_QUALITY_FAILURE_EXIT_CODE
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert payload["overall_status"] == "fail"
    assert payload["quality_policy"]["overall_status"] == "fail"
    assert any(
        rule["rule_id"] == "statistics.failures.reference_accuracy" and rule["status"] == "fail"
        for rule in payload["quality_policy"]["rules"]
    )


def test_cli_returns_infrastructure_error_for_malformed_dataset(tmp_path: Path) -> None:
    dataset = tmp_path / "malformed.json"
    dataset.write_text("{not-json", encoding="utf-8")

    exit_code = main(
        [
            "--dataset",
            str(dataset),
            "--json-output",
            str(tmp_path / "phase4" / "statistical_baseline.json"),
            "--output",
            str(tmp_path / "phase4" / "statistical_baseline.md"),
        ]
    )

    assert exit_code == STATISTICAL_INFRASTRUCTURE_EXIT_CODE


def test_cli_artifacts_are_byte_stable_across_repeated_runs(tmp_path: Path) -> None:
    outputs = []
    for run in ("first", "second"):
        root = tmp_path / run / "phase4"
        assert (
            main(
                [
                    "--json-output",
                    str(root / "statistical_baseline.json"),
                    "--output",
                    str(root / "statistical_baseline.md"),
                ]
            )
            == 0
        )
        outputs.append(
            (
                (root / "statistical_baseline.json").read_bytes(),
                (root / "statistical_baseline.md").read_bytes(),
            )
        )

    assert outputs[0] == outputs[1]


def test_existing_evaluation_cli_dispatches_statistical_baseline(tmp_path: Path) -> None:
    root = tmp_path / "phase4"

    exit_code = evaluation_cli_main(
        [
            "statistical-baseline",
            "--json-output",
            str(root / "statistical_baseline.json"),
            "--output",
            str(root / "statistical_baseline.md"),
        ]
    )

    assert exit_code == 0
    assert (root / "statistical_baseline.json").is_file()


def test_evaluation_cli_module_accepts_statistical_baseline_options(tmp_path: Path) -> None:
    root = tmp_path / "phase4"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "packages.evals.cli",
            "statistical-baseline",
            "--json-output",
            str(root / "statistical_baseline.json"),
            "--output",
            str(root / "statistical_baseline.md"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert (root / "statistical_baseline.json").is_file()
