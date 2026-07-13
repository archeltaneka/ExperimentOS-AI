from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.evals.prompt_experiments.loader import (
        DEFAULT_PROMPT_EXPERIMENT_CONFIG_DIR,
        load_prompt_experiment_definition,
    )
    from packages.evals.prompt_experiments.models import (
        PromptExperimentDefinition,
        PromptExperimentReport,
    )
    from packages.evals.prompt_experiments.reporting import (
        prompt_experiment_report_to_json,
        render_prompt_experiment_report,
    )
    from packages.evals.prompt_experiments.runner import PromptExperimentRunner
    from packages.evals.prompt_experiments.validation import (
        DEFAULT_DATASET_CATALOG,
        PromptExperimentValidationError,
        get_experimentable_prompt_ids,
        validate_prompt_experiment_definition,
    )

__all__ = [
    "DEFAULT_DATASET_CATALOG",
    "DEFAULT_PROMPT_EXPERIMENT_CONFIG_DIR",
    "PromptExperimentDefinition",
    "PromptExperimentReport",
    "PromptExperimentRunner",
    "PromptExperimentValidationError",
    "get_experimentable_prompt_ids",
    "load_prompt_experiment_definition",
    "prompt_experiment_report_to_json",
    "render_prompt_experiment_report",
    "validate_prompt_experiment_definition",
]

_MODULE_BY_EXPORT = {
    "DEFAULT_DATASET_CATALOG": "packages.evals.prompt_experiments.validation",
    "DEFAULT_PROMPT_EXPERIMENT_CONFIG_DIR": "packages.evals.prompt_experiments.loader",
    "PromptExperimentDefinition": "packages.evals.prompt_experiments.models",
    "PromptExperimentReport": "packages.evals.prompt_experiments.models",
    "PromptExperimentRunner": "packages.evals.prompt_experiments.runner",
    "PromptExperimentValidationError": "packages.evals.prompt_experiments.validation",
    "get_experimentable_prompt_ids": "packages.evals.prompt_experiments.validation",
    "load_prompt_experiment_definition": "packages.evals.prompt_experiments.loader",
    "prompt_experiment_report_to_json": "packages.evals.prompt_experiments.reporting",
    "render_prompt_experiment_report": "packages.evals.prompt_experiments.reporting",
    "validate_prompt_experiment_definition": "packages.evals.prompt_experiments.validation",
}


def __getattr__(name: str):
    try:
        module_name = _MODULE_BY_EXPORT[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = import_module(module_name)
    return getattr(module, name)
