from __future__ import annotations

from pathlib import Path


def test_prompt_experiment_cli_validate_and_assign_work_offline(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import packages.evals.run_prompt_experiment as module
    from packages.evals.prompt_experiments.models import (
        AssignedPromptVariant,
        PromptExperimentDefinition,
    )

    definition = PromptExperimentDefinition(
        experiment_id="rag-answer-abstention-v1-v2",
        name="RAG answer abstention wording",
        description="Offline CLI test.",
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
        seed="seed-a",
        status="validated",
        metadata={},
    )

    monkeypatch.setattr(
        module,
        "load_prompt_experiment_definition",
        lambda experiment_id, config_dir=None: definition,
    )
    monkeypatch.setattr(
        module,
        "validate_prompt_experiment_definition",
        lambda loaded_definition, **_: None,
    )
    monkeypatch.setattr(
        module,
        "assign_prompt_experiment_variant",
        lambda loaded_definition, randomization_key: AssignedPromptVariant(
            experiment_id=loaded_definition.experiment_id,
            variant="treatment_2",
            prompt_id=loaded_definition.prompt_id,
            prompt_version="2",
            assignment_strategy=loaded_definition.assignment_strategy,
            assignment_key_hash="hashed-key",
            allocation=dict(loaded_definition.allocation),
        ),
    )

    assert module.main(["validate", "--experiment", "rag-answer-abstention-v1-v2"]) == 0
    assert (
        module.main(
            [
                "assign",
                "--experiment",
                "rag-answer-abstention-v1-v2",
                "--key",
                "safe-test-key",
            ]
        )
        == 0
    )
