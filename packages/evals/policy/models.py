from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

SourceFormat = Literal[
    "rag_markdown",
    "agent_markdown",
    "agent_e2e_markdown",
    "ragas_json",
    "deepeval_json",
    "prompt_regression_json",
    "factuality_json",
]
ComparisonOperator = Literal["gte", "lte", "eq"]
SeverityLevel = Literal["warning", "fail", "critical"]
MetricStatus = Literal["pass", "warning", "fail", "skipped"]


@dataclass(frozen=True)
class PolicySource:
    source_id: str
    path: Path
    format: SourceFormat


@dataclass(frozen=True)
class MetricThreshold:
    metric_id: str
    source: str
    category: str
    operator: ComparisonOperator
    value: float | int | str | bool
    severity: SeverityLevel
    required: bool = True
    weight: float = 1.0
    tolerance: float = 0.0
    description: str = ""


@dataclass(frozen=True)
class QualityPolicy:
    version: str
    sources: dict[str, PolicySource]
    metrics: tuple[MetricThreshold, ...]


@dataclass(frozen=True)
class SourceMetric:
    metric_id: str
    value: float | int | str | bool | None
    status: MetricStatus
    reason: str | None = None


@dataclass(frozen=True)
class LoadedSource:
    source_id: str
    path: Path
    format: SourceFormat
    metrics: dict[str, SourceMetric]


@dataclass(frozen=True)
class EvaluatedMetric:
    metric_id: str
    source: str
    category: str
    source_path: str
    observed_value: float | int | str | bool | None
    operator: ComparisonOperator
    threshold_value: float | int | str | bool
    severity: SeverityLevel
    required: bool
    weight: float
    tolerance: float
    status: MetricStatus
    message: str


@dataclass(frozen=True)
class PolicyViolation:
    metric_id: str
    category: str
    severity: SeverityLevel
    status: MetricStatus
    message: str
    source_path: str
    observed_value: float | int | str | bool | None
    threshold_value: float | int | str | bool


@dataclass(frozen=True)
class CategoryResult:
    name: str
    status: MetricStatus
    metrics: tuple[EvaluatedMetric, ...]
    passed_count: int
    warning_count: int
    failed_count: int
    skipped_count: int


@dataclass(frozen=True)
class PolicyEvaluationResult:
    policy_version: str
    report_dir: str
    overall_status: MetricStatus
    category_results: dict[str, CategoryResult]
    metrics_evaluated: tuple[EvaluatedMetric, ...]
    violations: tuple[PolicyViolation, ...]
    warnings: tuple[PolicyViolation, ...]
    skipped_metrics: tuple[EvaluatedMetric, ...]
    loaded_sources: tuple[str, ...] = field(default_factory=tuple)
    recommendation: str = ""
    rationale: tuple[str, ...] = field(default_factory=tuple)
