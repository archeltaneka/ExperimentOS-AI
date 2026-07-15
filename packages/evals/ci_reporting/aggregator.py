from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.evals.ci_reporting.models import (
    CategorySummary,
    CiQualityReport,
    ExecutionDetails,
    MetricDelta,
    ReportFinding,
    ReportMetadata,
    SuiteResult,
)

_SUITE_NAMES = {
    "evaluation.json": "custom RAG",
    "agent_evaluation.json": "agent",
    "agent_e2e_evaluation.json": "end-to-end",
    "phase3/prompt_regression.json": "prompt regression",
    "phase3/factuality_report.json": "factuality",
    "phase3/ragas_report.json": "RAGAS",
    "phase3/deepeval_report.json": "DeepEval",
}


def build_ci_quality_report(
    report_dir: Path,
    *,
    metadata: ReportMetadata,
    strict: bool = False,
    baseline_report: Path | None = None,
) -> CiQualityReport:
    try:
        policy = _read_object(report_dir / "phase3/quality_policy.json", required=True)
        gate = _read_object(report_dir / "phase3/ai_quality_gate.json", required=True)
        manifest = _read_object(report_dir / "phase3/artifact_manifest.json", required=False)
        environment = _read_object(report_dir / "phase3/ci_environment.json", required=False)
    except _ReportReadError as exc:
        return _infrastructure_report(metadata, str(exc), exc.failure_type)

    missing = _missing_required(manifest)
    if missing:
        return _infrastructure_report(
            metadata,
            "Missing required reports: " + ", ".join(missing),
            "missing_required_report",
            policy,
            gate,
            environment,
        )

    execution = _execution(gate, environment, metadata)
    return CiQualityReport(
        overall_status=_status(policy, gate),
        policy_version=_string(policy.get("policy_version")) or None,
        metadata=metadata,
        categories=_categories(policy),
        critical_violations=_findings(policy.get("violations"), critical_only=True),
        warnings=_findings(policy.get("warnings"), critical_only=False),
        skipped_metrics=_findings(policy.get("skipped_metrics"), critical_only=False),
        metric_deltas=_metric_deltas(policy, report_dir, baseline_report),
        suites=_suites(report_dir, manifest, policy),
        execution=execution,
        failure_type=_failure_type(gate),
        artifact_name=execution.artifact_name,
        metadata_extra={"strict": strict},
    )


def _read_object(path: Path, *, required: bool) -> dict[str, Any]:
    if not path.is_file():
        if required:
            raise _ReportReadError("missing_required_report", f"Missing required report: {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _ReportReadError("malformed_report", f"Malformed report: {path}") from exc
    if not isinstance(payload, dict):
        raise _ReportReadError("malformed_report", f"Expected JSON object: {path}")
    return payload


def _missing_required(manifest: dict[str, Any]) -> tuple[str, ...]:
    reports = manifest.get("required_reports", [])
    if not isinstance(reports, list):
        return ()
    return tuple(
        _string(item.get("relative_path"))
        for item in reports
        if isinstance(item, dict)
        and item.get("present") is False
        and _string(item.get("relative_path"))
    )


def _categories(policy: dict[str, Any]) -> tuple[CategorySummary, ...]:
    values = policy.get("category_results", {})
    if not isinstance(values, dict):
        return ()
    return tuple(
        CategorySummary(
            name=_string(value.get("name")) or str(name),
            status=_string(value.get("status")) or "incomplete",
            key_result=_category_result(value),
        )
        for name, value in values.items()
        if isinstance(value, dict)
    )


def _category_result(value: dict[str, Any]) -> str:
    for key in ("failed_count", "warning_count", "skipped_count"):
        count = value.get(key)
        if isinstance(count, int) and count:
            return f"{count} {key.removesuffix('_count').replace('_', ' ')}"
    return ""


def _findings(payload: object, *, critical_only: bool) -> tuple[ReportFinding, ...]:
    if not isinstance(payload, list):
        return ()
    findings = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        severity = _string(item.get("severity"))
        if critical_only and severity != "critical":
            continue
        findings.append(
            ReportFinding(
                metric_id=_string(item.get("metric_id")) or "unknown.metric",
                message=_string(item.get("message")) or "No structured message was supplied.",
                severity=severity,
                category=_string(item.get("category")),
            )
        )
    return tuple(findings)


def _status(policy: dict[str, Any], gate: dict[str, Any]) -> str:
    if _string(gate.get("status")) == "infrastructure_fail":
        return "infrastructure_error"
    value = _string(policy.get("overall_status"))
    if value in {"pass", "warning", "fail"}:
        return value
    if _string(gate.get("status")) == "quality_fail":
        return "fail"
    return "incomplete"


def _failure_type(gate: dict[str, Any]) -> str | None:
    return (
        "quality_gate_infrastructure_error"
        if _string(gate.get("status")) == "infrastructure_fail"
        else None
    )


def _execution(
    gate: dict[str, Any], environment: dict[str, Any], metadata: ReportMetadata
) -> ExecutionDetails:
    fingerprint = gate.get("fingerprint", {})
    if not isinstance(fingerprint, dict):
        fingerprint = {}
    source = environment or fingerprint
    return ExecutionDetails(
        database_backed_path_executed=(
            bool(fingerprint.get("database_url_present"))
            if "database_url_present" in fingerprint
            else None
        ),
        embedding_provider=_string(
            source.get("embedding_provider") or fingerprint.get("embedding_provider")
        ),
        llm_provider=_string(source.get("llm_provider") or fingerprint.get("llm_provider")),
        external_judge_used=bool(
            source.get("external_judges_enabled", fingerprint.get("external_judges_enabled", False))
        ),
        live_provider_used=bool(
            source.get(
                "live_provider_configured", fingerprint.get("live_provider_configured", False)
            )
        ),
        artifact_name=_string(gate.get("artifact_name")) or None,
        workflow_run_id=metadata.workflow_run_id,
    )


def _suites(
    report_dir: Path, manifest: dict[str, Any], policy: dict[str, Any]
) -> tuple[SuiteResult, ...]:
    availability = {
        _string(item.get("relative_path")): bool(item.get("present"))
        for group in ("required_reports", "optional_reports")
        for item in manifest.get(group, [])
        if isinstance(item, dict)
    }
    suites = []
    for path, name in _SUITE_NAMES.items():
        present = availability.get(path, (report_dir / path).is_file())
        suites.append(
            SuiteResult(
                suite_name=name, status=_suite_status(policy, name, present), report_path=path
            )
        )
    for path, present in availability.items():
        if path.startswith("phase3/prompt_experiments/"):
            suites.append(
                SuiteResult(
                    suite_name="prompt experiment validation",
                    status="pass" if present else "skipped",
                    report_path=path,
                )
            )
    return tuple(suites)


def _suite_status(policy: dict[str, Any], name: str, present: bool) -> str:
    if not present:
        return "skipped"
    prefix = {
        "custom RAG": "rag.",
        "agent": "agent.",
        "end-to-end": "agent_e2e.",
        "prompt regression": "prompt_regression.",
        "factuality": "factuality.",
        "RAGAS": "ragas.",
        "DeepEval": "deepeval.",
    }[name]
    statuses = [
        _string(item.get("status"))
        for item in policy.get("metrics_evaluated", [])
        if isinstance(item, dict) and _string(item.get("metric_id")).startswith(prefix)
    ]
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    return "pass" if statuses else "incomplete"


def _metric_deltas(
    policy: dict[str, Any],
    report_dir: Path,
    baseline_report: Path | None,
) -> tuple[MetricDelta, ...]:
    dataset_version = _current_dataset_version(report_dir)
    baseline = _load_baseline(
        baseline_report,
        _string(policy.get("policy_version")),
        dataset_version,
    )
    values = baseline.get("metrics", {}) if baseline else {}
    if not isinstance(values, dict):
        values = {}
    result = []
    for metric in policy.get("metrics_evaluated", []):
        if not isinstance(metric, dict):
            continue
        metric_id = _string(metric.get("metric_id"))
        current = metric.get("observed_value")
        previous = values.get(metric_id)
        if isinstance(current, (int, float)) and isinstance(previous, (int, float)):
            result.append(
                MetricDelta(
                    metric_id=metric_id,
                    current_value=current,
                    baseline_value=previous,
                    absolute_delta=float(current - previous),
                    threshold=metric.get("threshold_value"),
                    status=_string(metric.get("status")) or "unavailable",
                    message="Trusted baseline comparison.",
                )
            )
        else:
            result.append(
                MetricDelta(
                    metric_id=metric_id,
                    current_value=current,
                    threshold=metric.get("threshold_value"),
                )
            )
    return tuple(result)


def _current_dataset_version(report_dir: Path) -> str:
    try:
        payload = _read_object(report_dir / "evaluation.json", required=False)
    except _ReportReadError:
        return ""
    return _string(payload.get("dataset_version"))


def _load_baseline(path: Path | None, version: str, dataset_version: str) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        payload = _read_object(path, required=False)
    except _ReportReadError:
        return {}
    if _string(payload.get("policy_version")) != version:
        return {}
    if not dataset_version or _string(payload.get("dataset_version")) != dataset_version:
        return {}
    return payload


def _infrastructure_report(
    metadata: ReportMetadata,
    message: str,
    failure_type: str,
    policy: dict[str, Any] | None = None,
    gate: dict[str, Any] | None = None,
    environment: dict[str, Any] | None = None,
) -> CiQualityReport:
    policy = policy or {}
    gate = gate or {}
    execution = _execution(gate, environment or {}, metadata)
    return CiQualityReport(
        overall_status="infrastructure_error",
        policy_version=_string(policy.get("policy_version")) or None,
        metadata=metadata,
        categories=_categories(policy),
        warnings=(ReportFinding(metric_id="report.infrastructure", message=message),),
        execution=execution,
        failure_type=failure_type,
        artifact_name=execution.artifact_name,
    )


class _ReportReadError(ValueError):
    def __init__(self, failure_type: str, message: str) -> None:
        super().__init__(message)
        self.failure_type = failure_type


def _string(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""
