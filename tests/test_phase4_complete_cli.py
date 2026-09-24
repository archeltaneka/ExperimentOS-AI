"""Canonical command owns all four safe artifacts and exact failure exits."""

import json

import pytest

from packages.evals.run_statistical_baseline import main


def arguments(root):
    return [
        "--json-output",
        str(root / "statistical_baseline.json"),
        "--output",
        str(root / "statistical_baseline.md"),
    ]


def test_complete_command_writes_all_artifacts(tmp_path):
    assert main(arguments(tmp_path)) == 0
    report = json.loads((tmp_path / "statistical_baseline.json").read_text())
    assert report["scope"] == "complete"
    assert len(report["workflow"]) >= 75
    assert report["workflow_case_count"] == len(report["workflow"])
    assert (tmp_path / "quality_policy.json").is_file()
    assert (tmp_path / "github_summary.md").is_file()


def test_renderer_failure_replaces_stale_success_without_private_error(
    tmp_path, monkeypatch, capsys
):
    from packages.evals import run_statistical_baseline as command

    assert main(arguments(tmp_path)) == 0

    def fail(*args):
        raise RuntimeError("PRIVATE_ROWS_SENTINEL Bearer secret-token")

    monkeypatch.setattr(command, "render_statistical_baseline_markdown", fail)
    assert main(arguments(tmp_path)) == 2
    payload = json.loads((tmp_path / "statistical_baseline.json").read_text())
    assert payload["run_status"] == "infrastructure_fail"
    assert payload["stage"] == "rendering"
    assert payload["evaluation"]["workflow"]
    for path in tmp_path.iterdir():
        assert "PRIVATE_ROWS_SENTINEL" not in path.read_text()
    assert "infrastructure_fail" in (tmp_path / "statistical_baseline.md").read_text()
    assert "PRIVATE_ROWS_SENTINEL" not in str(capsys.readouterr())


def test_escaping_injection_is_quality_failure(tmp_path, monkeypatch):
    from packages.evals.statistical.workflow import injections

    monkeypatch.setattr(injections, "injection_detected", lambda *args: False)
    assert main(arguments(tmp_path)) == 1


@pytest.mark.parametrize("kind", ["dataset", "policy", "workflow-dataset"])
def test_malformed_configuration_is_safe_infrastructure_failure(tmp_path, kind, capsys):
    broken = tmp_path / "input"
    if kind == "workflow-dataset":
        broken.mkdir()
        (broken / "bad.json").write_text('{"secret": "PRIVATE_ROWS_SENTINEL"}')
    else:
        broken.write_text("PRIVATE_ROWS_SENTINEL")
    assert main([*arguments(tmp_path), "--" + kind, str(broken)]) == 2
    assert "PRIVATE_ROWS_SENTINEL" not in str(capsys.readouterr())
    assert (
        json.loads((tmp_path / "statistical_baseline.json").read_text())["run_status"]
        == "infrastructure_fail"
    )


def test_optional_scope_runs_without_core_duplication(tmp_path):
    assert main([*arguments(tmp_path), "--scope", "optional-adapters"]) == 0
    report = json.loads((tmp_path / "statistical_baseline.json").read_text())
    assert report["scope"] == "optional-adapters"
    assert all(c["family"] == "adapter" for c in report["workflow"])
    assert all(c["advanced"] is not None for c in report["case_results"])


def test_harness_exception_collects_other_cases_and_returns_two(tmp_path, monkeypatch):
    from packages.evals.statistical.workflow import suite

    original = suite.evaluate_workflow_case

    def fail_one(case, **kwargs):
        if case.case_id == "dml-success":
            raise RuntimeError("PRIVATE_HARNESS_SENTINEL")
        return original(case, **kwargs)

    monkeypatch.setattr(suite, "evaluate_workflow_case", fail_one)
    assert main(arguments(tmp_path)) == 2
    payload = json.loads((tmp_path / "statistical_baseline.json").read_text())
    assert payload["stage"] == "workflow"
    assert len(payload["evaluation"]["workflow"]) > 50
    assert "PRIVATE_HARNESS_SENTINEL" not in json.dumps(payload)


def test_unwritable_outputs_fail_safely(tmp_path, monkeypatch, capsys):
    from packages.evals import run_statistical_baseline as command

    def fail(*args):
        raise PermissionError("PRIVATE_DESTINATION_SENTINEL")

    monkeypatch.setattr(command, "_write", fail)
    assert main(arguments(tmp_path)) == 2
    assert "PRIVATE_DESTINATION_SENTINEL" not in str(capsys.readouterr())


def test_required_absent_optional_dependency_is_blocking(tmp_path, monkeypatch):
    from packages.evals.statistical.workflow import optional

    monkeypatch.setattr(optional, "dependency_state", lambda _: ("unavailable", None))
    with optional.dependency_override("econml_dml", "absent"):
        assert (
            main(
                [
                    *arguments(tmp_path),
                    "--scope",
                    "optional-adapters",
                    "--require-optional",
                    "econml",
                ]
            )
            == 1
        )
