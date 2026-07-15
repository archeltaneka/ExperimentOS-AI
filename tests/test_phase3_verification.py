from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Literal

import pytest

from packages.evals.phase3_verification import validation as phase3_validation
from packages.evals.phase3_verification.inventory import build_capability_inventory
from packages.evals.phase3_verification.models import (
    CommandResult,
    FinalReliabilityReview,
    MilestoneRecommendation,
    VerificationCommand,
    VerificationMode,
)
from packages.evals.phase3_verification.network_guard import ensure_network_address_allowed
from packages.evals.phase3_verification.reporting import (
    final_review_to_dict,
    render_final_review_markdown,
    write_final_review,
)
from packages.evals.phase3_verification.runner import (
    build_verification_commands,
    build_verification_environment,
    discover_synthetic_fixtures,
    run_command,
    run_phase3_verification,
)
from packages.evals.phase3_verification.validation import (
    VerificationError,
    derive_recommendation,
    extract_factuality_invariants,
    load_json_object,
    validate_final_review_files,
    validate_required_reports,
)
from scripts import verify_phase3


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


def _sample_final_review(
    *,
    mode: VerificationMode = "strict",
    recommendation: MilestoneRecommendation = "ready_to_close",
    overall_status: Literal["pass", "fail"] = "pass",
    commands: tuple[CommandResult, ...] | None = None,
) -> FinalReliabilityReview:
    return FinalReliabilityReview(
        schema_version="phase3-final-review-v1",
        generated_at_utc="2026-07-15T00:00:00Z",
        mode=mode,
        closeout_eligible=mode == "strict",
        recommendation=recommendation,
        overall_status=overall_status,
        commands=commands or (_passing_result(),),
        capability_inventory=build_capability_inventory(),
        findings=(),
        dataset_versions={"qa.golden": "sha256:" + "a" * 64},
        policy_version="phase3-v1",
        provider_configuration={"embedding": "fake", "llm": "mock", "judges": "none"},
        factuality_invariants=_zero_factuality_invariants(),
        compatibility={
            "ask_mode_default": "agent_workflow",
            "legacy_rag": "pass",
            "post_ask_contract": "pass",
            "deterministic_agents": "pass",
        },
        limitations=("External sinks were verified with dry-runs and in-memory exporters.",),
        unresolved_risks=(),
        section_summaries={"architecture": "Ownership boundaries verified."},
    )


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


def test_final_report_generation_writes_markdown_and_json(tmp_path: Path) -> None:
    review = _sample_final_review(mode="strict")
    markdown_path = tmp_path / "final.md"
    json_path = tmp_path / "final.json"

    write_final_review(review, markdown_path=markdown_path, json_path=json_path)

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["recommendation"] == "ready_to_close"
    assert payload["capability_inventory"]
    validate_final_review_files(json_path, markdown_path)
    for heading in (
        "Files Changed",
        "Capability Inventory",
        "Architecture Review",
        "Defects Fixed",
        "Configuration and Security Findings",
        "Commands Run",
        "Test Results",
        "Database Verification",
        "Evaluation Results",
        "Factuality Invariants",
        "Quality Policy",
        "Observability",
        "CI and PR Reporting",
        "API Compatibility",
        "Documentation Changes",
        "Known Limitations",
        "Unresolved Risks",
        "Recommended Phase 4 Direction",
        "Milestone Recommendation",
    ):
        assert f"## {heading}" in markdown
    assert str(tmp_path.resolve()) not in markdown


def test_final_report_generation_is_deterministic(tmp_path: Path) -> None:
    review = _sample_final_review()
    first_markdown = tmp_path / "first.md"
    first_json = tmp_path / "first.json"
    second_markdown = tmp_path / "second.md"
    second_json = tmp_path / "second.json"

    write_final_review(review, markdown_path=first_markdown, json_path=first_json)
    write_final_review(review, markdown_path=second_markdown, json_path=second_json)

    assert first_markdown.read_bytes() == second_markdown.read_bytes()
    assert first_json.read_bytes() == second_json.read_bytes()


def test_final_report_redacts_secrets_prompts_and_retrieved_chunks() -> None:
    sensitive_result = CommandResult(
        command_id="sensitive",
        argv=("python", "-V"),
        status="pass",
        exit_code=0,
        duration_seconds=0.1,
        stdout_tail=(
            "OPENAI_API_KEY=sk-1234567890abcdef Authorization: Bearer token-value "
            '"prompt":"full private prompt" '
            '"retrieved_chunks":["full private chunk"]'
        ),
        stderr_tail="",
        report_paths=(),
    )
    review = _sample_final_review(commands=(sensitive_result,))

    payload_text = json.dumps(final_review_to_dict(review))
    markdown = render_final_review_markdown(review)

    for sensitive in (
        "sk-1234567890abcdef",
        "token-value",
        "full private prompt",
        "full private chunk",
    ):
        assert sensitive not in payload_text
        assert sensitive not in markdown
    assert "[REDACTED]" in payload_text


def test_cli_defaults_to_strict(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run(**kwargs: object) -> FinalReliabilityReview:
        captured.update(kwargs)
        return _sample_final_review(mode="strict")

    monkeypatch.setattr(verify_phase3, "run_phase3_verification", fake_run)

    exit_code = verify_phase3.main(
        ["--artifact-root", str(tmp_path / "artifacts"), "--report-root", str(tmp_path)]
    )

    assert exit_code == 0
    assert captured["mode"] == "strict"


def test_cli_offline_only_prints_non_closeout_label(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        verify_phase3,
        "run_phase3_verification",
        lambda **kwargs: _sample_final_review(
            mode="offline_only",
            recommendation="ready_with_documented_limitations",
        ),
    )

    assert verify_phase3.main(["--offline-only", "--report-root", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert "NON-CLOSEOUT DIAGNOSTIC" in output
    assert "ready_to_close" not in output


def test_cli_returns_nonzero_when_required_stage_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        verify_phase3,
        "run_phase3_verification",
        lambda **kwargs: _sample_final_review(
            recommendation="not_ready",
            overall_status="fail",
        ),
    )

    assert verify_phase3.main(["--report-root", str(tmp_path)]) != 0


def test_strict_verification_without_database_writes_not_ready_reports(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    review = run_phase3_verification(
        mode="strict",
        artifact_root=tmp_path / "artifacts",
        report_root=tmp_path / "reports",
        repository_root=Path.cwd(),
        source_environment={"PATH": os.environ["PATH"]},
    )

    assert review.recommendation == "not_ready"
    assert review.overall_status == "fail"
    assert review.commands[0].command_id == "configuration.database_url"
    assert "docker compose up -d postgres" in review.commands[0].stderr_tail
    assert (tmp_path / "reports/final_reliability_review.json").is_file()
    assert (tmp_path / "reports/final_reliability_review.md").is_file()
