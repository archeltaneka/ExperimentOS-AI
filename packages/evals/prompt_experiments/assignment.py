from __future__ import annotations

import hashlib

from packages.evals.prompt_experiments.models import (
    AssignedPromptVariant,
    PromptExperimentDefinition,
)


def assign_prompt_experiment_variant(
    definition: PromptExperimentDefinition,
    randomization_key: str,
) -> AssignedPromptVariant:
    assignment_key_hash = hash_assignment_key(
        definition.experiment_id,
        definition.seed,
        randomization_key,
    )
    variant = _select_variant(definition, assignment_key_hash)
    prompt_version = (
        definition.control_version if variant == "control" else variant.removeprefix("treatment_")
    )
    return AssignedPromptVariant(
        experiment_id=definition.experiment_id,
        variant=variant,
        prompt_id=definition.prompt_id,
        prompt_version=prompt_version,
        assignment_strategy=definition.assignment_strategy,
        assignment_key_hash=assignment_key_hash,
        allocation=dict(definition.allocation),
    )


def hash_assignment_key(experiment_id: str, seed: str, randomization_key: str) -> str:
    payload = ":".join(
        [
            experiment_id.strip(),
            seed.strip(),
            randomization_key.strip(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _select_variant(
    definition: PromptExperimentDefinition,
    assignment_key_hash: str,
) -> str:
    if definition.assignment_strategy == "fixed":
        return max(
            definition.allocation.items(),
            key=lambda item: (item[1], item[0] == "control"),
        )[0]

    bucket_value = int(assignment_key_hash[:8], 16) / 0xFFFFFFFF
    cumulative = 0.0
    for variant, allocation in definition.allocation.items():
        cumulative += allocation
        if bucket_value <= cumulative:
            return variant
    return next(reversed(definition.allocation))
