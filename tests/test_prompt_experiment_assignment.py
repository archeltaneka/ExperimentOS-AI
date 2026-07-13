from __future__ import annotations

from collections import Counter


def _definition(*, seed: str = "seed-a"):
    from packages.evals.prompt_experiments.models import PromptExperimentDefinition

    return PromptExperimentDefinition(
        experiment_id="rag-answer-abstention-v1-v2",
        name="RAG answer abstention wording",
        description="Stable assignment test.",
        prompt_id="rag.answer",
        control_version="1",
        treatment_versions=("2",),
        hypothesis="Stronger abstention wording improves factuality.",
        primary_metric="factuality_pass_rate",
        secondary_metrics=(),
        guardrail_metrics=("critical_factuality_violations",),
        dataset_id="qa_dataset",
        assignment_strategy="deterministic_hash",
        allocation={"control": 0.5, "treatment_2": 0.5},
        randomization_unit="explicit_runtime_key",
        seed=seed,
        status="validated",
        metadata={},
    )


def test_assignment_is_stable_and_changes_with_seed() -> None:
    from packages.evals.prompt_experiments.assignment import assign_prompt_experiment_variant

    first = assign_prompt_experiment_variant(_definition(seed="seed-a"), "customer-42")
    second = assign_prompt_experiment_variant(_definition(seed="seed-a"), "customer-42")
    third = assign_prompt_experiment_variant(_definition(seed="seed-b"), "customer-42")

    assert first.variant == second.variant
    assert first.assignment_key_hash == second.assignment_key_hash
    assert third.variant != first.variant or third.assignment_key_hash != first.assignment_key_hash


def test_assignment_respects_approximate_allocation_distribution() -> None:
    from packages.evals.prompt_experiments.assignment import assign_prompt_experiment_variant

    counts = Counter(
        assign_prompt_experiment_variant(_definition(), f"customer-{index}").variant
        for index in range(500)
    )

    ratio = counts["control"] / 500
    assert 0.4 <= ratio <= 0.6


def test_assignment_hash_is_stable_and_does_not_expose_raw_key() -> None:
    from packages.evals.prompt_experiments.assignment import hash_assignment_key

    digest = hash_assignment_key(
        "rag-answer-abstention-v1-v2",
        "seed-a",
        "customer-42",
    )

    assert digest == "46e5b19984e0b9d620c913edea3245e9"
    assert "customer-42" not in digest
