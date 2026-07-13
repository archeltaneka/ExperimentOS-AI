from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.evals.dataset import EvaluationQuestion, load_evaluation_dataset
    from packages.evals.evaluator import EvaluationRun, EvaluationSampleResult, OfflineEvaluator
    from packages.evals.metrics import EvaluationSummary, SampleMetrics, calculate_sample_metrics
    from packages.evals.report import render_evaluation_report

__all__ = [
    "EvaluationQuestion",
    "EvaluationRun",
    "EvaluationSampleResult",
    "EvaluationSummary",
    "OfflineEvaluator",
    "SampleMetrics",
    "calculate_sample_metrics",
    "load_evaluation_dataset",
    "render_evaluation_report",
]

_MODULE_BY_EXPORT = {
    "EvaluationQuestion": "packages.evals.dataset",
    "load_evaluation_dataset": "packages.evals.dataset",
    "EvaluationRun": "packages.evals.evaluator",
    "EvaluationSampleResult": "packages.evals.evaluator",
    "OfflineEvaluator": "packages.evals.evaluator",
    "EvaluationSummary": "packages.evals.metrics",
    "SampleMetrics": "packages.evals.metrics",
    "calculate_sample_metrics": "packages.evals.metrics",
    "render_evaluation_report": "packages.evals.report",
}


def __getattr__(name: str):
    try:
        module_name = _MODULE_BY_EXPORT[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name)
    return getattr(module, name)
