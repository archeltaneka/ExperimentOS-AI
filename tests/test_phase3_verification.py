from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from packages.evals.phase3_verification import validation as phase3_validation
from packages.evals.phase3_verification.inventory import build_capability_inventory
from packages.evals.phase3_verification.models import CommandResult, VerificationCommand
from packages.evals.phase3_verification.network_guard import ensure_network_address_allowed
from packages.evals.phase3_verification.runner import (
    build_verification_commands,
    build_verification_environment,
    discover_synthetic_fixtures,
    run_command,
)
from packages.evals.phase3_verification.validation import (
    VerificationError,
    derive_recommendation,
    extract_factuality_invariants,
    load_json_object,
    validate_required_reports,
)


def _passing_result() -> CommandResult:
    return CommandResult(
        command_id="passing",
        argv=("python", "-V"),
        status="pass",
        exit_code=0,
        duration_seconds=0.1,
        stdout_tail="",
        stderr_tail="",
        report_paths=(),
    )


def _zero_factuality_invariants() -> dict[str, int]:
    return {
        "fabricated_revenue_or_roi": 0,
        "fabricated_statistical_significance": 0,
        "fabricated_experiment_result": 0,
        "structured_decision_contradiction": 0,
        "approval_state_contradiction": 0,
    }


def _passing_factuality_payload() -> dict[str, object]:
    return {
        "checks_executed": [
            "numerical_grounding",
            "financial_guardrails",
            "statistical_validation",
            "abstention_correctness",
            "structured_consistency",
        ],
        "findings_by_category": {},
        "findings_detail": [],
        "policy_result": {"status": "pass"},
    }


def _write_required_report_set(root: Path) -> None:
    for (
        relative_path,
        required_keys,
    ) in phase3_validation._REQUIRED_QUALITY_GATE_REPORT_KEYS.items():
        payload: dict[str, object] = {key: {} for key in required_keys}
        if "prompt_experiments/" in relative_path:
            payload.update(
                {
                    "recommendation": {"outcome": "retain_control"},
                    "production_traffic_involved": False,
                    "limitations": [
                        "Offline evaluation results do not establish production causal impact."
                    ],
                }
            )
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    for relative_path in phase3_validation._REQUIRED_MARKDOWN_REPORTS:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Verified report\n", encoding="utf-8")


def test_capability_inventory_covers_every_phase3_domain() -> None:
    inventory = build_capability_inventory()
    capability_ids = {item.capability_id for item in inventory}

    assert {
        "evaluation.custom_rag",
        "evaluation.custom_agent",
        "evaluation.end_to_end",
        "evaluation.ragas",
        "evaluation.deepeval",
        "evaluation.prompt_regression",
        "evaluation.factuality",
        "evaluation.quality_policy",
        "prompt.registry",
        "prompt.provenance",
        "prompt.experiments",
        "observability.internal",
        "observability.langsmith",
        "observability.phoenix",
        "observability.opentelemetry",
        "observability.composite",
        "ci.baseline",
        "ci.database",
        "ci.quality_gate",
        "ci.pr_reporting",
    } <= capability_ids


def test_inventory_rows_have_all_required_closeout_fields() -> None:
    for item in build_capability_inventory():
        assert item.implementation_locations
        assert item.configuration
        assert item.cli_commands
        assert item.tests
        assert item.generated_reports
        assert item.documentation
        assert item.default_state in {"enabled", "disabled", "conditional"}
        assert item.external_service_requirement in {"none", "optional", "local_postgres"}


def test_inventory_implementation_and_documentation_paths_exist() -> None:
    for item in build_capability_inventory():
        for path in (*item.implementation_locations, *item.documentation):
            assert Path(path).exists(), (item.capability_id, path)


def test_verification_environment_disables_all_external_paths() -> None:
    env = build_verification_environment(
        {
            "PATH": os.environ["PATH"],
            "OPENAI_API_KEY": "secret",
            "GEMINI_API_KEY": "secret",
            "LANGSMITH_API_KEY": "secret",
            "EXPERIMENTOS_PHOENIX_API_KEY": "secret",
            "EXPERIMENTOS_OTEL_EXPORTER_ENDPOINT": "https://collector.example",
        }
    )

    assert env["EMBEDDING_PROVIDER"] == "fake"
    assert env["LLM_PROVIDER"] == "mock"
    assert env["RAGAS_JUDGE_LLM_PROVIDER"] == "none"
    assert env["RAGAS_JUDGE_EMBEDDING_PROVIDER"] == "none"
    assert env["DEEPEVAL_JUDGE_PROVIDER"] == "none"
    assert env["EXPERIMENTOS_LANGSMITH_ENABLED"] == "false"
    assert env["EXPERIMENTOS_PHOENIX_ENABLED"] == "false"
    assert env["EXPERIMENTOS_OTEL_ENABLED"] == "false"
    assert env["PROMPT_EXPERIMENTS_ENABLED"] == "false"
    assert env["PYTHONHASHSEED"] == "0"
    assert env["OPENAI_API_KEY"] == ""
    assert env["EXPERIMENTOS_OTEL_EXPORTER_ENDPOINT"] == ""


@pytest.mark.parametrize(
    "variable,value",
    [
        ("LLM_PROVIDER", "openai"),
        ("EMBEDDING_PROVIDER", "gemini"),
        ("DEEPEVAL_JUDGE_PROVIDER", "openai"),
        ("EXPERIMENTOS_LANGSMITH_ENABLED", "true"),
        ("PROMPT_EXPERIMENTS_ENABLED", "true"),
    ],
)
def test_verification_environment_rejects_conflicting_live_configuration(
    variable: str,
    value: str,
) -> None:
    with pytest.raises(ValueError, match=variable):
        build_verification_environment({variable: value})


def test_run_command_preserves_child_exit_code(tmp_path: Path) -> None:
    command = VerificationCommand(
        command_id="intentional-failure",
        argv=(sys.executable, "-c", "raise SystemExit(7)"),
        required=True,
        timeout_seconds=5,
    )

    result = run_command(command, env=os.environ, cwd=tmp_path)

    assert result.status == "fail"
    assert result.exit_code == 7


def test_run_command_records_timeout(tmp_path: Path) -> None:
    command = VerificationCommand(
        command_id="intentional-timeout",
        argv=(sys.executable, "-c", "import time; time.sleep(2)"),
        required=True,
        timeout_seconds=1,
    )

    result = run_command(command, env=os.environ, cwd=tmp_path)

    assert result.status == "timeout"
    assert result.exit_code is None


def test_offline_only_plan_contains_no_database_or_closeout_gate(tmp_path: Path) -> None:
    commands = build_verification_commands("offline_only", artifact_root=tmp_path)

    assert all(not command.strict_only for command in commands)
    assert all("alembic" not in command.argv for command in commands)
    assert all("run_ai_quality_gate.py" not in command.argv for command in commands)


def test_strict_plan_contains_database_full_quality_and_ci_report_stages(tmp_path: Path) -> None:
    commands = build_verification_commands("strict", artifact_root=tmp_path)
    argv_text = [" ".join(command.argv) for command in commands]

    assert any("alembic upgrade head" in argv for argv in argv_text)
    assert any("run_ai_quality_gate.py" in argv for argv in argv_text)
    assert any("data/eval/qa_dataset.json" in argv for argv in argv_text)
    assert any("packages.evals.run_ci_report build" in argv for argv in argv_text)
    assert any("packages.evals.run_ci_report validate" in argv for argv in argv_text)
    database_commands = [
        command for command in commands if command.command_id.startswith("database.")
    ]
    assert all(command.strict_only for command in database_commands)


def test_fixture_discovery_requires_every_qa_experiment(tmp_path: Path) -> None:
    (tmp_path / "exp-001-payment-recommendation").mkdir()

    with pytest.raises(ValueError, match="exp-002-hotel-image-quality"):
        discover_synthetic_fixtures(
            tmp_path,
            {"exp-001-payment-recommendation", "exp-002-hotel-image-quality"},
        )


def test_fixture_discovery_is_stable(tmp_path: Path) -> None:
    for experiment_id in ("exp-002-hotel-image-quality", "exp-001-payment-recommendation"):
        (tmp_path / experiment_id).mkdir()

    fixtures = discover_synthetic_fixtures(
        tmp_path,
        {"exp-001-payment-recommendation", "exp-002-hotel-image-quality"},
    )

    assert [path.name for path in fixtures] == [
        "exp-001-payment-recommendation",
        "exp-002-hotel-image-quality",
    ]


def test_fixture_discovery_rejects_extra_directories(tmp_path: Path) -> None:
    (tmp_path / "exp-001-payment-recommendation").mkdir()
    (tmp_path / "developer-local-copy").mkdir()

    with pytest.raises(ValueError, match="developer-local-copy"):
        discover_synthetic_fixtures(tmp_path, {"exp-001-payment-recommendation"})


@pytest.mark.parametrize(
    "address",
    [
        ("localhost", 5433),
        ("127.0.0.1", 5433),
        ("::1", 5433),
        "local-unix-socket",
    ],
)
def test_network_guard_allows_only_local_addresses(address: object) -> None:
    ensure_network_address_allowed(address)


def test_network_guard_rejects_external_addresses() -> None:
    with pytest.raises(RuntimeError, match="external network access is disabled"):
        ensure_network_address_allowed(("api.openai.com", 443))


def test_required_report_validation_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(VerificationError, match="missing required report"):
        validate_required_reports(tmp_path)


def test_required_report_validation_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "evaluation.json"
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(VerificationError, match="valid JSON"):
        load_json_object(path)


def test_required_report_validation_accepts_complete_report_set(tmp_path: Path) -> None:
    _write_required_report_set(tmp_path)

    payloads = validate_required_reports(tmp_path)

    assert len(payloads) == len(phase3_validation._REQUIRED_QUALITY_GATE_REPORT_KEYS)


def test_required_report_validation_rejects_production_prompt_claim(tmp_path: Path) -> None:
    _write_required_report_set(tmp_path)
    relative_path = "quality_gate/phase3/prompt_experiments/rag-answer-abstention-v1-v2.json"
    path = tmp_path / relative_path
    payload = load_json_object(path)
    payload["production_traffic_involved"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(VerificationError, match="production_traffic_involved"):
        validate_required_reports(tmp_path)


def test_factuality_extraction_requires_all_deterministic_checks() -> None:
    payload = _passing_factuality_payload()
    payload["checks_executed"] = ["numerical_grounding"]

    with pytest.raises(VerificationError, match="structured_consistency"):
        extract_factuality_invariants(payload)


def test_factuality_extraction_splits_structured_contradictions() -> None:
    payload = _passing_factuality_payload()
    payload["findings_detail"] = [
        {
            "category": "contradiction_with_structured_experiment_data",
            "structured_field_ids": ["decision.recommendation"],
        },
        {
            "category": "contradiction_with_structured_experiment_data",
            "structured_field_ids": ["approval_status"],
        },
    ]

    invariants = extract_factuality_invariants(payload)

    assert invariants["structured_decision_contradiction"] == 1
    assert invariants["approval_state_contradiction"] == 1


def test_policy_failure_forces_not_ready() -> None:
    recommendation = derive_recommendation(
        mode="strict",
        command_results=(_passing_result(),),
        policy_payload={"overall_status": "fail"},
        factuality_invariants=_zero_factuality_invariants(),
        unresolved_critical_findings=0,
    )

    assert recommendation == "not_ready"


@pytest.mark.parametrize("invariant", tuple(_zero_factuality_invariants()))
def test_each_factuality_violation_forces_not_ready(invariant: str) -> None:
    invariants = _zero_factuality_invariants()
    invariants[invariant] = 1

    assert (
        derive_recommendation(
            mode="strict",
            command_results=(_passing_result(),),
            policy_payload={"overall_status": "pass"},
            factuality_invariants=invariants,
            unresolved_critical_findings=0,
        )
        == "not_ready"
    )


def test_failed_required_command_forces_not_ready() -> None:
    failed = CommandResult(
        command_id="failed",
        argv=("python", "-V"),
        status="fail",
        exit_code=9,
        duration_seconds=0.1,
        stdout_tail="",
        stderr_tail="failure",
        report_paths=(),
    )

    assert (
        derive_recommendation(
            mode="strict",
            command_results=(failed,),
            policy_payload={"overall_status": "pass"},
            factuality_invariants=_zero_factuality_invariants(),
            unresolved_critical_findings=0,
        )
        == "not_ready"
    )


def test_optional_metric_skip_does_not_block_strict_closeout() -> None:
    assert (
        derive_recommendation(
            mode="strict",
            command_results=(_passing_result(),),
            policy_payload={
                "overall_status": "pass",
                "skipped_metrics": [{"required": False, "status": "skipped"}],
            },
            factuality_invariants=_zero_factuality_invariants(),
            unresolved_critical_findings=0,
        )
        == "ready_to_close"
    )


def test_offline_only_is_never_ready_to_close() -> None:
    assert (
        derive_recommendation(
            mode="offline_only",
            command_results=(_passing_result(),),
            policy_payload={"overall_status": "pass"},
            factuality_invariants=_zero_factuality_invariants(),
            unresolved_critical_findings=0,
        )
        == "ready_with_documented_limitations"
    )
