from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import Path

from packages.evals.dataset import DEFAULT_DATASET_PATH
from packages.evals.prompt_experiments.models import PromptExperimentDefinition
from packages.llm.prompt_registry import PromptLookupError, PromptRegistry, get_prompt_registry

SUPPORTED_PRIMARY_METRICS = frozenset(
    {
        "answer_completeness",
        "citation_coverage",
        "deterministic_expected_answer_checks",
        "factuality_pass_rate",
        "latency_ms",
        "prompt_rendering_success",
        "regression_pass_rate",
        "required_output_validity",
        "response_availability",
        "unsupported_claim_rate",
    }
)
SUPPORTED_GUARDRAIL_METRICS = frozenset(
    {
        "citation_coverage_non_regression",
        "critical_factuality_violations",
        "fabricated_revenue_or_roi",
        "fabricated_significance",
        "failure_rate_tolerance",
        "latency_tolerance",
        "structured_output_validity_non_regression",
    }
)
SUPPORTED_RANDOMIZATION_UNITS = frozenset({"dataset_case", "explicit_runtime_key"})
MAX_TREATMENT_COUNT = 3
DEFAULT_DATASET_CATALOG = {
    "qa_dataset": DEFAULT_DATASET_PATH,
    "agent_dataset": Path("data/eval/agent_dataset.json"),
}
_EXPERIMENTABLE_PROMPT_IDS = frozenset({"rag.answer"})


class PromptExperimentValidationError(ValueError):
    pass


def get_experimentable_prompt_ids() -> frozenset[str]:
    return _EXPERIMENTABLE_PROMPT_IDS


def validate_prompt_experiment_definition(
    definition: PromptExperimentDefinition,
    *,
    registry: PromptRegistry | None = None,
    dataset_catalog: Mapping[str, Path] | None = None,
) -> None:
    prompt_registry = registry or get_prompt_registry()
    known_datasets = dict(dataset_catalog or DEFAULT_DATASET_CATALOG)

    if definition.prompt_id not in get_experimentable_prompt_ids():
        raise PromptExperimentValidationError(
            f"prompt_id {definition.prompt_id!r} is not experimentable"
        )
    if definition.primary_metric not in SUPPORTED_PRIMARY_METRICS:
        raise PromptExperimentValidationError(
            f"unsupported primary metric: {definition.primary_metric}"
        )
    if definition.dataset_id not in known_datasets:
        raise PromptExperimentValidationError(f"unknown dataset: {definition.dataset_id}")
    if definition.randomization_unit not in SUPPORTED_RANDOMIZATION_UNITS:
        raise PromptExperimentValidationError(
            f"unsupported randomization unit: {definition.randomization_unit}"
        )
    if not definition.seed.strip():
        raise PromptExperimentValidationError("seed must not be empty")
    if not definition.treatment_versions:
        raise PromptExperimentValidationError("at least one treatment version is required")
    if len(definition.treatment_versions) > MAX_TREATMENT_COUNT:
        raise PromptExperimentValidationError("treatment count exceeds supported limit")
    if len(set(definition.treatment_versions)) != len(definition.treatment_versions):
        raise PromptExperimentValidationError("treatment versions must be unique")
    if definition.control_version in definition.treatment_versions:
        raise PromptExperimentValidationError("control and treatment versions must be distinct")
    if not definition.allocation:
        raise PromptExperimentValidationError("allocation must not be empty")

    expected_variants = {
        "control",
        *[f"treatment_{version}" for version in definition.treatment_versions],
    }
    if set(definition.allocation) != expected_variants:
        raise PromptExperimentValidationError(
            "allocation keys must include control and one entry per treatment version"
        )
    if any(value <= 0.0 for value in definition.allocation.values()):
        raise PromptExperimentValidationError("allocation values must be greater than zero")
    if not math.isclose(sum(definition.allocation.values()), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise PromptExperimentValidationError("allocation values must sum to 1.0")

    invalid_guardrails = [
        metric
        for metric in definition.guardrail_metrics
        if metric not in SUPPORTED_GUARDRAIL_METRICS
    ]
    if invalid_guardrails:
        raise PromptExperimentValidationError(
            f"unsupported guardrail metrics: {', '.join(sorted(invalid_guardrails))}"
        )

    try:
        control = prompt_registry.get(definition.prompt_id, definition.control_version)
    except PromptLookupError as exc:
        raise PromptExperimentValidationError(str(exc)) from exc
    _validate_prompt_status(
        control.status,
        allow_deprecated_versions=definition.allow_deprecated_versions,
    )

    for version in definition.treatment_versions:
        try:
            candidate = prompt_registry.get(definition.prompt_id, version)
        except PromptLookupError as exc:
            raise PromptExperimentValidationError(str(exc)) from exc
        _validate_prompt_status(
            candidate.status,
            allow_deprecated_versions=definition.allow_deprecated_versions,
        )


def _validate_prompt_status(
    status: str,
    *,
    allow_deprecated_versions: bool,
) -> None:
    if status == "deprecated" and not allow_deprecated_versions:
        raise PromptExperimentValidationError(
            "deprecated prompt versions require explicit opt-in"
        )
