from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from packages.evals.policy.models import (
    ComparisonOperator,
    MetricThreshold,
    PolicySource,
    QualityPolicy,
    SeverityLevel,
    SourceFormat,
)

_ALLOWED_FORMATS = {
    "rag_markdown",
    "agent_markdown",
    "agent_e2e_markdown",
    "ragas_json",
    "deepeval_json",
    "prompt_regression_json",
    "factuality_json",
}
_ALLOWED_OPERATORS = {"gte", "lte", "eq"}
_ALLOWED_SEVERITIES = {"warning", "fail", "critical"}


def load_quality_policy(path: Path) -> QualityPolicy:
    if not path.is_file():
        raise ValueError(f"quality policy file not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("quality policy must be a YAML mapping")

    version = str(payload.get("version", "")).strip()
    if not version:
        raise ValueError("quality policy version is required")

    source_payload = payload.get("sources", {})
    if not isinstance(source_payload, dict) or not source_payload:
        raise ValueError("quality policy sources must be a non-empty mapping")
    sources: dict[str, PolicySource] = {}
    for source_id, raw_source in source_payload.items():
        if not isinstance(raw_source, dict):
            raise ValueError(f"source `{source_id}` must be a mapping")
        raw_path = raw_source.get("path")
        raw_format = raw_source.get("format")
        if not raw_path or not isinstance(raw_path, str):
            raise ValueError(f"source `{source_id}` path must be a non-empty string")
        if raw_format not in _ALLOWED_FORMATS:
            raise ValueError(f"source `{source_id}` format must be one of {_ALLOWED_FORMATS}")
        sources[str(source_id)] = PolicySource(
            source_id=str(source_id),
            path=Path(raw_path),
            format=cast(SourceFormat, raw_format),
        )

    metrics_payload = payload.get("metrics", [])
    if not isinstance(metrics_payload, list) or not metrics_payload:
        raise ValueError("quality policy metrics must be a non-empty list")
    metrics: list[MetricThreshold] = []
    for index, raw_metric in enumerate(metrics_payload, start=1):
        if not isinstance(raw_metric, dict):
            raise ValueError(f"metric #{index} must be a mapping")
        metric_id = str(raw_metric.get("metric_id", "")).strip()
        source = str(raw_metric.get("source", "")).strip()
        category = str(raw_metric.get("category", "")).strip()
        operator = raw_metric.get("operator")
        severity = raw_metric.get("severity")
        if not metric_id:
            raise ValueError(f"metric #{index} is missing metric_id")
        if source not in sources:
            raise ValueError(f"metric `{metric_id}` references unknown source `{source}`")
        if not category:
            raise ValueError(f"metric `{metric_id}` is missing category")
        if operator not in _ALLOWED_OPERATORS:
            raise ValueError(f"metric `{metric_id}` operator must be one of {_ALLOWED_OPERATORS}")
        if severity not in _ALLOWED_SEVERITIES:
            raise ValueError(f"metric `{metric_id}` severity must be one of {_ALLOWED_SEVERITIES}")
        if "value" not in raw_metric:
            raise ValueError(f"metric `{metric_id}` is missing value")
        metrics.append(
            MetricThreshold(
                metric_id=metric_id,
                source=source,
                category=category,
                operator=cast(ComparisonOperator, operator),
                value=_coerce_value(raw_metric["value"]),
                severity=cast(SeverityLevel, severity),
                required=bool(raw_metric.get("required", True)),
                weight=float(raw_metric.get("weight", 1.0) or 1.0),
                tolerance=float(raw_metric.get("tolerance", 0.0) or 0.0),
                description=str(raw_metric.get("description", "")).strip(),
            )
        )

    return QualityPolicy(version=version, sources=sources, metrics=tuple(metrics))


def _coerce_value(value: Any) -> float | int | str | bool:
    if isinstance(value, (float, int, str, bool)):
        return value
    raise ValueError(f"unsupported threshold value type: {type(value).__name__}")
