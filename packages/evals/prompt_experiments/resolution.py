from __future__ import annotations

from packages.evals.prompt_experiments.models import PromptExperimentContext
from packages.llm.prompt_registry import PromptRegistry


def resolve_prompt_version(
    prompt_id: str,
    *,
    registry: PromptRegistry,
    explicit_version: str | None = None,
    experiment_context: PromptExperimentContext | None = None,
) -> str:
    if explicit_version is not None:
        registry.get(prompt_id, explicit_version)
        return explicit_version
    if experiment_context is not None and experiment_context.prompt_id == prompt_id:
        registry.get(prompt_id, experiment_context.prompt_version)
        return experiment_context.prompt_version
    return registry.get_active(prompt_id).version
