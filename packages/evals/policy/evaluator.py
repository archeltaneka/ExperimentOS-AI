from __future__ import annotations

from pathlib import Path

from packages.evals.policy.adapters import load_source
from packages.evals.policy.models import (
    CategoryResult,
    EvaluatedMetric,
    MetricStatus,
    PolicyEvaluationResult,
    PolicyViolation,
    QualityPolicy,
)

_STATUS_ORDER: dict[MetricStatus, int] = {"pass": 0, "skipped": 1, "warning": 2, "fail": 3}


def repository_relative_path(path: Path | str, *, root: Path | None = None) -> str:
    candidate = Path(path)
    base = (root or Path.cwd()).resolve()
    try:
        return candidate.resolve().relative_to(base).as_posix()
    except ValueError:
        return candidate.name


class PolicyEvaluator:
    def __init__(self, *, policy: QualityPolicy, report_dir: Path) -> None:
        self.policy = policy
        self.report_dir = report_dir

    def evaluate(self) -> PolicyEvaluationResult:
        loaded_sources: dict[str, object] = {}
        loaded_source_ids: list[str] = []
        for source_id, source in self.policy.sources.items():
            loaded = load_source(source, self.report_dir)
            if loaded is not None:
                loaded_sources[source_id] = loaded
                loaded_source_ids.append(source_id)

        evaluated_metrics: list[EvaluatedMetric] = []
        violations: list[PolicyViolation] = []
        warnings: list[PolicyViolation] = []

        for metric in self.policy.metrics:
            loaded = loaded_sources.get(metric.source)
            if loaded is None:
                evaluated = self._missing_source_metric(metric)
            else:
                evaluated = self._evaluate_loaded_metric(metric, loaded)
            evaluated_metrics.append(evaluated)
            if evaluated.status == "fail":
                violations.append(self._to_violation(evaluated))
            elif evaluated.status == "warning":
                warnings.append(self._to_violation(evaluated))

        category_results = self._build_category_results(evaluated_metrics)
        overall_status = self._overall_status(category_results.values())
        skipped_metrics = tuple(
            metric for metric in evaluated_metrics if metric.status == "skipped"
        )
        rationale = self._build_rationale(overall_status, violations, warnings, skipped_metrics)

        return PolicyEvaluationResult(
            policy_version=self.policy.version,
            report_dir=repository_relative_path(self.report_dir),
            overall_status=overall_status,
            category_results=category_results,
            metrics_evaluated=tuple(evaluated_metrics),
            violations=tuple(violations),
            warnings=tuple(warnings),
            skipped_metrics=skipped_metrics,
            loaded_sources=tuple(loaded_source_ids),
            recommendation=_recommendation(overall_status),
            rationale=rationale,
        )

    def _evaluate_loaded_metric(self, metric, loaded_source) -> EvaluatedMetric:
        source_metric = loaded_source.metrics.get(metric.metric_id)
        if source_metric is None:
            if metric.required:
                return self._build_metric(
                    metric=metric,
                    source_path=loaded_source.path,
                    observed_value=None,
                    status="fail",
                    message="Required metric was not found in the source report.",
                )
            return self._build_metric(
                metric=metric,
                source_path=loaded_source.path,
                observed_value=None,
                status="skipped",
                message="Optional metric was not found in the source report.",
            )

        if source_metric.status == "skipped":
            if metric.required:
                return self._build_metric(
                    metric=metric,
                    source_path=loaded_source.path,
                    observed_value=None,
                    status="fail",
                    message=source_metric.reason or "Required metric was skipped.",
                )
            return self._build_metric(
                metric=metric,
                source_path=loaded_source.path,
                observed_value=None,
                status="skipped",
                message=source_metric.reason or "Metric was skipped.",
            )

        passed = _compare(
            observed=source_metric.value,
            operator=metric.operator,
            expected=metric.value,
            tolerance=metric.tolerance,
        )
        if passed:
            return self._build_metric(
                metric=metric,
                source_path=loaded_source.path,
                observed_value=source_metric.value,
                status="pass",
                message="Threshold satisfied.",
            )

        status: MetricStatus = "warning" if metric.severity == "warning" else "fail"
        return self._build_metric(
            metric=metric,
            source_path=loaded_source.path,
            observed_value=source_metric.value,
            status=status,
            message=(
                f"Observed value `{source_metric.value}` did not satisfy "
                f"`{metric.operator} {metric.value}`."
            ),
        )

    def _missing_source_metric(self, metric) -> EvaluatedMetric:
        if metric.required:
            status: MetricStatus = "fail"
            message = "Missing source report for a required metric."
        else:
            status = "skipped"
            message = "Optional source report is missing."
        return self._build_metric(
            metric=metric,
            source_path=str(self.report_dir / self.policy.sources[metric.source].path),
            observed_value=None,
            status=status,
            message=message,
        )

    def _build_metric(
        self,
        *,
        metric,
        source_path,
        observed_value,
        status,
        message,
    ) -> EvaluatedMetric:
        return EvaluatedMetric(
            metric_id=metric.metric_id,
            source=metric.source,
            category=metric.category,
            source_path=repository_relative_path(source_path),
            observed_value=observed_value,
            operator=metric.operator,
            threshold_value=metric.value,
            severity=metric.severity,
            required=metric.required,
            weight=metric.weight,
            tolerance=metric.tolerance,
            status=status,
            message=message,
        )

    def _build_category_results(
        self,
        evaluated_metrics: list[EvaluatedMetric],
    ) -> dict[str, CategoryResult]:
        categories: dict[str, list[EvaluatedMetric]] = {}
        for metric in evaluated_metrics:
            categories.setdefault(metric.category, []).append(metric)

        results: dict[str, CategoryResult] = {}
        for category, metrics in categories.items():
            statuses = [metric.status for metric in metrics]
            status = self._overall_status_from_statuses(statuses)
            results[category] = CategoryResult(
                name=category,
                status=status,
                metrics=tuple(metrics),
                passed_count=sum(1 for metric in metrics if metric.status == "pass"),
                warning_count=sum(1 for metric in metrics if metric.status == "warning"),
                failed_count=sum(1 for metric in metrics if metric.status == "fail"),
                skipped_count=sum(1 for metric in metrics if metric.status == "skipped"),
            )
        return results

    def _overall_status(self, categories) -> MetricStatus:
        return self._overall_status_from_statuses([category.status for category in categories])

    def _overall_status_from_statuses(self, statuses: list[MetricStatus]) -> MetricStatus:
        if not statuses:
            return "skipped"
        if any(status == "fail" for status in statuses):
            return "fail"
        if any(status == "warning" for status in statuses):
            return "warning"
        if all(status == "skipped" for status in statuses):
            return "skipped"
        return "pass"

    def _to_violation(self, metric: EvaluatedMetric) -> PolicyViolation:
        return PolicyViolation(
            metric_id=metric.metric_id,
            category=metric.category,
            severity=metric.severity,
            status=metric.status,
            message=metric.message,
            source_path=metric.source_path,
            observed_value=metric.observed_value,
            threshold_value=metric.threshold_value,
        )

    def _build_rationale(
        self,
        overall_status: MetricStatus,
        violations: list[PolicyViolation],
        warnings: list[PolicyViolation],
        skipped_metrics: tuple[EvaluatedMetric, ...],
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if overall_status == "fail":
            reasons.append("Blocking policy violations were detected.")
        elif overall_status == "warning":
            reasons.append("Only warning-level policy deviations were detected.")
        elif overall_status == "skipped":
            reasons.append("No actionable policy metrics were evaluated.")
        else:
            reasons.append("All required quality policy metrics satisfied their thresholds.")
        if violations:
            reasons.append(f"{len(violations)} blocking metrics failed.")
        if warnings:
            reasons.append(f"{len(warnings)} warning metrics were out of threshold.")
        if skipped_metrics:
            reasons.append(f"{len(skipped_metrics)} metrics were skipped or unavailable.")
        return tuple(reasons)


def _compare(
    *,
    observed,
    operator,
    expected,
    tolerance: float,
) -> bool:
    if operator == "eq":
        if isinstance(observed, (int, float)) and isinstance(expected, (int, float)):
            return abs(float(observed) - float(expected)) <= tolerance
        return observed == expected
    if not isinstance(observed, (int, float)) or not isinstance(expected, (int, float)):
        return False
    if operator == "gte":
        return float(observed) >= float(expected) - tolerance
    if operator == "lte":
        return float(observed) <= float(expected) + tolerance
    raise ValueError(f"unsupported operator: {operator}")


def _recommendation(status: MetricStatus) -> str:
    if status == "fail":
        return "Resolve blocking threshold violations before enabling CI quality gates."
    if status == "warning":
        return "Warnings are present; review advisory metrics before tightening enforcement."
    if status == "skipped":
        return "Collect the required report artifacts before relying on this policy result."
    return "Quality policy thresholds are satisfied for the available offline artifacts."
