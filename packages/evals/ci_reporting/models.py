from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class ReportStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    INFRASTRUCTURE_ERROR = "infrastructure_error"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True)
class ReportMetadata:
    workflow_run_id: str | None = None
    repository: str | None = None
    commit_sha: str | None = None
    pull_request_number: int | None = None
    base_ref: str | None = None
    head_ref: str | None = None
    execution_mode: str = "agent_workflow"
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass(frozen=True)
class CategorySummary:
    name: str
    status: str
    key_result: str = ""


@dataclass(frozen=True)
class ReportFinding:
    metric_id: str
    message: str
    severity: str = ""
    category: str = ""


@dataclass(frozen=True)
class MetricDelta:
    metric_id: str
    current_value: float | int | str | bool | None
    baseline_value: float | int | str | bool | None = None
    absolute_delta: float | None = None
    threshold: float | int | str | bool | None = None
    status: str = "unavailable"
    message: str = "Comparison unavailable."


@dataclass(frozen=True)
class SuiteResult:
    suite_name: str
    status: str
    cases_run: int | None = None
    passed: int | None = None
    failed: int | None = None
    skipped: int | None = None
    key_metrics: tuple[tuple[str, str], ...] = ()
    report_path: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class ExecutionDetails:
    database_backed_path_executed: bool | None = None
    embedding_provider: str = ""
    llm_provider: str = ""
    external_judge_used: bool = False
    live_provider_used: bool = False
    artifact_name: str | None = None
    workflow_run_id: str | None = None


@dataclass(frozen=True)
class RenderLimits:
    max_findings: int = 5
    max_warnings: int = 5
    max_suite_failures: int = 5
    max_characters: int = 12000


@dataclass(frozen=True)
class CiQualityReport:
    overall_status: str
    policy_version: str | None
    metadata: ReportMetadata
    categories: tuple[CategorySummary, ...] = ()
    critical_violations: tuple[ReportFinding, ...] = ()
    warnings: tuple[ReportFinding, ...] = ()
    skipped_metrics: tuple[ReportFinding, ...] = ()
    metric_deltas: tuple[MetricDelta, ...] = ()
    suites: tuple[SuiteResult, ...] = ()
    execution: ExecutionDetails = field(default_factory=ExecutionDetails)
    failure_type: str | None = None
    artifact_name: str | None = None
    metadata_extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def minimal(cls, status: ReportStatus, policy_version: str | None) -> CiQualityReport:
        return cls(
            overall_status=status.value,
            policy_version=policy_version,
            metadata=ReportMetadata(),
        )

    def with_warnings(self, warnings: tuple[str, ...]) -> CiQualityReport:
        return replace(
            self,
            warnings=tuple(
                ReportFinding(metric_id="report.warning", message=warning) for warning in warnings
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return _json_safe(asdict(self))


def _json_safe(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value
