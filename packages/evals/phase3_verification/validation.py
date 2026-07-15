from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from packages.evals.phase3_verification.models import (
    CommandResult,
    MilestoneRecommendation,
    VerificationMode,
)

_REQUIRED_QUALITY_GATE_REPORT_KEYS = {
    "quality_gate/evaluation.json": ("samples", "summary", "dataset_version"),
    "quality_gate/agent_evaluation.json": ("samples", "summary", "dataset_version"),
    "quality_gate/agent_e2e_evaluation.json": (
        "samples",
        "summary",
        "dataset_id",
        "dataset_version",
    ),
    "quality_gate/phase3/ragas_report.json": ("metric_results", "case_results"),
    "quality_gate/phase3/deepeval_report.json": ("metric_results", "case_results"),
    "quality_gate/phase3/prompt_regression.json": ("summary", "case_results"),
    "quality_gate/phase3/factuality_report.json": (
        "case_results",
        "findings_by_category",
        "findings_detail",
        "policy_result",
    ),
    "quality_gate/phase3/quality_policy.json": ("policy_version", "overall_status"),
    "quality_gate/phase3/prompt_experiments/rag-answer-abstention-v1-v2.json": (
        "experiment_id",
        "dataset_id",
        "recommendation",
        "production_traffic_involved",
    ),
    "quality_gate/phase3/ai_quality_gate.json": ("status", "manifest", "command_results"),
    "ci/pr_quality_report.json": ("overall_status", "suites", "execution"),
}
_REQUIRED_MARKDOWN_REPORTS = (
    "quality_gate/evaluation.md",
    "quality_gate/agent_evaluation.md",
    "quality_gate/agent_e2e_evaluation.md",
    "quality_gate/phase3/ragas_report.md",
    "quality_gate/phase3/deepeval_report.md",
    "quality_gate/phase3/prompt_regression.md",
    "quality_gate/phase3/factuality_report.md",
    "quality_gate/phase3/quality_policy.md",
    "quality_gate/phase3/prompt_experiments/rag-answer-abstention-v1-v2.md",
    "quality_gate/phase3/github_summary.md",
    "ci/pr_quality_report.md",
    "ci/pr_comment.md",
)
_REQUIRED_DETERMINISTIC_CHECKS = {
    "numerical_grounding",
    "financial_guardrails",
    "statistical_validation",
    "abstention_correctness",
    "structured_consistency",
}
_CRITICAL_FACTUALITY_KEYS = (
    "fabricated_revenue_or_roi",
    "fabricated_statistical_significance",
    "fabricated_experiment_result",
    "structured_decision_contradiction",
    "approval_state_contradiction",
)
_FINAL_REVIEW_KEYS = {
    "schema_version",
    "mode",
    "closeout_eligible",
    "recommendation",
    "overall_status",
    "commands",
    "capability_inventory",
    "factuality_invariants",
}
_ABSOLUTE_WINDOWS_PATH = re.compile(r"(?i)\b[a-z]:[\\/]")
_ABSOLUTE_POSIX_PATH = re.compile(r"/(?:home|users|tmp|var|workspace)/", re.IGNORECASE)
_SECRET_TOKEN = re.compile(
    r"(?:\bsk-[A-Za-z0-9_-]{12,}|\bghp_[A-Za-z0-9]{12,}|\bgithub_pat_[A-Za-z0-9_]{12,})"
)


class VerificationError(ValueError):
    pass


def load_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise VerificationError(f"missing required report: {path.as_posix()}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"report is not valid JSON: {path.as_posix()}: {exc}") from exc
    if not isinstance(payload, dict):
        raise VerificationError(f"report must contain a JSON object: {path.as_posix()}")
    return payload


def validate_required_reports(report_root: Path) -> dict[str, dict[str, object]]:
    errors: list[str] = []
    payloads: dict[str, dict[str, object]] = {}
    for relative_path, required_keys in _REQUIRED_QUALITY_GATE_REPORT_KEYS.items():
        path = report_root / relative_path
        if not path.is_file():
            errors.append(f"missing required report: {relative_path}")
            continue
        try:
            payload = load_json_object(path)
        except VerificationError as exc:
            errors.append(str(exc))
            continue
        missing_keys = sorted(set(required_keys) - set(payload))
        if missing_keys:
            errors.append(f"{relative_path} missing keys: {', '.join(missing_keys)}")
        payloads[relative_path] = payload

    for relative_path in _REQUIRED_MARKDOWN_REPORTS:
        path = report_root / relative_path
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            errors.append(f"missing required report: {relative_path}")

    prompt_path = "quality_gate/phase3/prompt_experiments/rag-answer-abstention-v1-v2.json"
    prompt_payload = payloads.get(prompt_path)
    if prompt_payload is not None:
        errors.extend(_validate_prompt_experiment(prompt_path, prompt_payload))

    if errors:
        raise VerificationError("; ".join(errors))
    return payloads


def extract_factuality_invariants(payload: Mapping[str, object]) -> dict[str, int]:
    checks = _string_set(payload.get("checks_executed"), "checks_executed")
    missing_checks = sorted(_REQUIRED_DETERMINISTIC_CHECKS - checks)
    if missing_checks:
        raise VerificationError(
            "factuality report did not execute required checks: " + ", ".join(missing_checks)
        )

    policy_result = _mapping(payload.get("policy_result"), "policy_result")
    if policy_result.get("status") != "pass":
        raise VerificationError("factuality policy_result.status must be pass")
    categories = _mapping(payload.get("findings_by_category"), "findings_by_category")
    invariants = {
        key: _nonnegative_int(categories.get(key, 0), f"findings_by_category.{key}")
        for key in _CRITICAL_FACTUALITY_KEYS[:3]
    }
    invariants["structured_decision_contradiction"] = 0
    invariants["approval_state_contradiction"] = 0

    details = payload.get("findings_detail")
    if not isinstance(details, list):
        raise VerificationError("findings_detail must be a JSON array")
    for index, value in enumerate(details):
        finding = _mapping(value, f"findings_detail[{index}]")
        if finding.get("category") != "contradiction_with_structured_experiment_data":
            continue
        field_ids = _string_set(
            finding.get("structured_field_ids"),
            f"findings_detail[{index}].structured_field_ids",
        )
        if any(field_id.startswith("decision.") for field_id in field_ids):
            invariants["structured_decision_contradiction"] += 1
        if "approval_status" in field_ids:
            invariants["approval_state_contradiction"] += 1
    return invariants


def derive_recommendation(
    *,
    mode: VerificationMode,
    command_results: Sequence[CommandResult],
    policy_payload: Mapping[str, object],
    factuality_invariants: Mapping[str, int],
    unresolved_critical_findings: int,
) -> MilestoneRecommendation:
    commands_failed = any(
        result.status != "pass" or result.exit_code != 0 for result in command_results
    )
    policy_status = policy_payload.get("overall_status")
    required_metric_skipped = any(
        isinstance(metric, Mapping)
        and metric.get("required") is True
        and metric.get("status") == "skipped"
        for metric in _list(policy_payload.get("skipped_metrics", []), "skipped_metrics")
    )
    factuality_failed = any(
        _nonnegative_int(factuality_invariants.get(key, 0), key) > 0
        for key in _CRITICAL_FACTUALITY_KEYS
    )
    if (
        commands_failed
        or policy_status == "fail"
        or policy_status not in {"pass", "warning"}
        or required_metric_skipped
        or factuality_failed
        or unresolved_critical_findings > 0
    ):
        return "not_ready"
    if mode == "offline_only" or policy_status == "warning":
        return "ready_with_documented_limitations"
    return "ready_to_close"


def validate_final_review_files(json_path: Path, markdown_path: Path) -> None:
    payload = load_json_object(json_path)
    missing_keys = sorted(_FINAL_REVIEW_KEYS - set(payload))
    if missing_keys:
        raise VerificationError("final review missing keys: " + ", ".join(missing_keys))
    try:
        markdown = markdown_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise VerificationError(f"missing or unreadable Markdown report: {markdown_path}") from exc
    if not markdown.strip():
        raise VerificationError("final Markdown report is empty")

    recommendation = payload.get("recommendation")
    mode = payload.get("mode")
    closeout_eligible = payload.get("closeout_eligible")
    if recommendation not in {
        "ready_to_close",
        "ready_with_documented_limitations",
        "not_ready",
    }:
        raise VerificationError("final recommendation is invalid")
    if mode == "offline_only" and recommendation == "ready_to_close":
        raise VerificationError("offline-only evidence cannot recommend ready_to_close")
    if closeout_eligible is not (mode == "strict"):
        raise VerificationError("closeout_eligible is inconsistent with verification mode")
    if str(recommendation) not in markdown:
        raise VerificationError("Markdown and JSON recommendations are inconsistent")

    serialized = json.dumps(payload, sort_keys=True) + "\n" + markdown
    if _ABSOLUTE_WINDOWS_PATH.search(serialized) or _ABSOLUTE_POSIX_PATH.search(serialized):
        raise VerificationError("final reports contain an absolute filesystem path")
    if _SECRET_TOKEN.search(serialized):
        raise VerificationError("final reports contain a secret-bearing value")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 3 final reliability reports.")
    parser.add_argument("json_report", type=Path)
    parser.add_argument("markdown_report", type=Path)
    args = parser.parse_args(argv)
    try:
        validate_final_review_files(args.json_report, args.markdown_report)
    except VerificationError as exc:
        print(f"Phase 3 final report validation failed: {exc}")
        return 2
    print("Phase 3 final reports are valid.")
    return 0


def _validate_prompt_experiment(
    relative_path: str,
    payload: Mapping[str, object],
) -> list[str]:
    errors: list[str] = []
    if payload.get("production_traffic_involved") is not False:
        errors.append(f"{relative_path} must set production_traffic_involved to false")
    recommendation = payload.get("recommendation")
    if not isinstance(recommendation, Mapping):
        errors.append(f"{relative_path} recommendation must be an object")
    elif recommendation.get("outcome") in {"promote", "auto_promote", "automatically_promote"}:
        errors.append(f"{relative_path} must not claim automatic prompt promotion")
    limitations = payload.get("limitations")
    if not isinstance(limitations, list) or not any(
        isinstance(value, str) and "not establish production causal impact" in value.lower()
        for value in limitations
    ):
        errors.append(f"{relative_path} must document the offline causal-impact limitation")
    return errors


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise VerificationError(f"{field_name} must be a JSON object")
    return value


def _list(value: object, field_name: str) -> list[object]:
    if not isinstance(value, list):
        raise VerificationError(f"{field_name} must be a JSON array")
    return value


def _string_set(value: object, field_name: str) -> set[str]:
    values = _list(value, field_name)
    if not all(isinstance(item, str) for item in values):
        raise VerificationError(f"{field_name} must contain only strings")
    return set(values)


def _nonnegative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise VerificationError(f"{field_name} must be a non-negative integer")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
