from __future__ import annotations

from pathlib import Path

import pytest

from packages.llm.prompt_registry import PromptDefinition, PromptRegistry


def _write_definition(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_prompt_experiment_definition_loads_and_validates_fixture(tmp_path: Path) -> None:
    from packages.evals.prompt_experiments.loader import load_prompt_experiment_definition
    from packages.evals.prompt_experiments.validation import (
        DEFAULT_DATASET_CATALOG,
        validate_prompt_experiment_definition,
    )

    config_dir = tmp_path / "prompt_experiments"
    config_dir.mkdir()
    _write_definition(
        config_dir / "rag_answer.yaml",
        """
        {
          "experiment_id": "rag-answer-abstention-v1-v2",
          "name": "RAG answer abstention wording",
          "description": "Compare current control and stronger abstention wording.",
          "prompt_id": "rag.answer",
          "control_version": "1",
          "treatment_versions": ["2"],
          "hypothesis": "Stronger abstention wording reduces unsupported claims.",
          "primary_metric": "factuality_pass_rate",
          "secondary_metrics": ["citation_coverage"],
          "guardrail_metrics": ["critical_factuality_violations"],
          "dataset_id": "qa_dataset",
          "assignment_strategy": "fixed",
          "allocation": {"control": 0.5, "treatment_2": 0.5},
          "randomization_unit": "dataset_case",
          "seed": "prompt-exp-seed",
          "status": "validated",
          "allow_deprecated_versions": false,
          "metadata": {"owner": "phase3"}
        }
        """.strip(),
    )

    definition = load_prompt_experiment_definition(
        "rag-answer-abstention-v1-v2",
        config_dir=config_dir,
    )
    validate_prompt_experiment_definition(
        definition,
        dataset_catalog=DEFAULT_DATASET_CATALOG,
    )

    assert definition.prompt_id == "rag.answer"
    assert definition.control_version == "1"
    assert definition.treatment_versions == ("2",)


def test_prompt_experiment_validation_rejects_non_experimentable_prompt_id() -> None:
    from packages.evals.prompt_experiments.models import PromptExperimentDefinition
    from packages.evals.prompt_experiments.validation import (
        PromptExperimentValidationError,
        validate_prompt_experiment_definition,
    )

    definition = PromptExperimentDefinition(
        experiment_id="decision-helper-test",
        name="Decision helper",
        description="Should fail because deterministic surfaces stay out of scope.",
        prompt_id="rag.decision",
        control_version="1",
        treatment_versions=("2",),
        hypothesis="No-op",
        primary_metric="citation_coverage",
        secondary_metrics=(),
        guardrail_metrics=("critical_factuality_violations",),
        dataset_id="qa_dataset",
        assignment_strategy="fixed",
        allocation={"control": 0.5, "treatment_2": 0.5},
        randomization_unit="dataset_case",
        seed="seed",
        status="draft",
        allow_deprecated_versions=False,
        metadata={},
    )

    with pytest.raises(PromptExperimentValidationError, match="experimentable"):
        validate_prompt_experiment_definition(definition)


def test_prompt_experiment_validation_rejects_unknown_version() -> None:
    from packages.evals.prompt_experiments.models import PromptExperimentDefinition
    from packages.evals.prompt_experiments.validation import (
        PromptExperimentValidationError,
        validate_prompt_experiment_definition,
    )

    definition = PromptExperimentDefinition(
        experiment_id="rag-answer-unknown-version",
        name="Unknown version",
        description="Should reject unknown prompt versions.",
        prompt_id="rag.answer",
        control_version="1",
        treatment_versions=("99",),
        hypothesis="No-op",
        primary_metric="citation_coverage",
        secondary_metrics=(),
        guardrail_metrics=("critical_factuality_violations",),
        dataset_id="qa_dataset",
        assignment_strategy="fixed",
        allocation={"control": 0.5, "treatment_99": 0.5},
        randomization_unit="dataset_case",
        seed="seed",
        status="draft",
        allow_deprecated_versions=False,
        metadata={},
    )

    with pytest.raises(PromptExperimentValidationError, match="unknown version"):
        validate_prompt_experiment_definition(definition)


def test_prompt_experiment_validation_rejects_same_control_and_treatment_version() -> None:
    from packages.evals.prompt_experiments.models import PromptExperimentDefinition
    from packages.evals.prompt_experiments.validation import (
        PromptExperimentValidationError,
        validate_prompt_experiment_definition,
    )

    definition = PromptExperimentDefinition(
        experiment_id="rag-answer-duplicate-version",
        name="Duplicate version",
        description="Should reject identical control and treatment versions.",
        prompt_id="rag.answer",
        control_version="1",
        treatment_versions=("1",),
        hypothesis="No-op",
        primary_metric="citation_coverage",
        secondary_metrics=(),
        guardrail_metrics=("critical_factuality_violations",),
        dataset_id="qa_dataset",
        assignment_strategy="fixed",
        allocation={"control": 0.5, "treatment_1": 0.5},
        randomization_unit="dataset_case",
        seed="seed",
        status="draft",
        allow_deprecated_versions=False,
        metadata={},
    )

    with pytest.raises(PromptExperimentValidationError, match="distinct"):
        validate_prompt_experiment_definition(definition)


def test_prompt_experiment_validation_rejects_invalid_allocation_sum() -> None:
    from packages.evals.prompt_experiments.models import PromptExperimentDefinition
    from packages.evals.prompt_experiments.validation import (
        PromptExperimentValidationError,
        validate_prompt_experiment_definition,
    )

    definition = PromptExperimentDefinition(
        experiment_id="rag-answer-invalid-allocation",
        name="Invalid allocation",
        description="Should reject allocations that do not sum to one.",
        prompt_id="rag.answer",
        control_version="1",
        treatment_versions=("2",),
        hypothesis="No-op",
        primary_metric="citation_coverage",
        secondary_metrics=(),
        guardrail_metrics=("critical_factuality_violations",),
        dataset_id="qa_dataset",
        assignment_strategy="fixed",
        allocation={"control": 0.7, "treatment_2": 0.4},
        randomization_unit="dataset_case",
        seed="seed",
        status="draft",
        allow_deprecated_versions=False,
        metadata={},
    )

    with pytest.raises(PromptExperimentValidationError, match="sum"):
        validate_prompt_experiment_definition(definition)


def test_prompt_experiment_validation_rejects_unsupported_primary_metric() -> None:
    from packages.evals.prompt_experiments.models import PromptExperimentDefinition
    from packages.evals.prompt_experiments.validation import (
        PromptExperimentValidationError,
        validate_prompt_experiment_definition,
    )

    definition = PromptExperimentDefinition(
        experiment_id="rag-answer-unsupported-metric",
        name="Unsupported metric",
        description="Should reject unsupported metrics.",
        prompt_id="rag.answer",
        control_version="1",
        treatment_versions=("2",),
        hypothesis="No-op",
        primary_metric="imaginary_metric",
        secondary_metrics=(),
        guardrail_metrics=("critical_factuality_violations",),
        dataset_id="qa_dataset",
        assignment_strategy="fixed",
        allocation={"control": 0.5, "treatment_2": 0.5},
        randomization_unit="dataset_case",
        seed="seed",
        status="draft",
        allow_deprecated_versions=False,
        metadata={},
    )

    with pytest.raises(PromptExperimentValidationError, match="primary metric"):
        validate_prompt_experiment_definition(definition)


def test_prompt_experiment_validation_rejects_deprecated_prompts_without_explicit_opt_in() -> None:
    from packages.evals.prompt_experiments.models import PromptExperimentDefinition
    from packages.evals.prompt_experiments.validation import (
        PromptExperimentValidationError,
        validate_prompt_experiment_definition,
    )

    registry = PromptRegistry()
    registry.register(
        PromptDefinition(
            prompt_id="rag.answer",
            name="Grounded RAG Answer",
            version="1",
            description="Deprecated prompt.",
            system_template="System {question}",
            user_template="Context {context}",
            input_variables=("question", "context"),
            output_contract="Grounded answer.",
            status="deprecated",
            created_at="2026-07-10T00:00:00Z",
        ),
        active=True,
    )
    registry.register(
        PromptDefinition(
            prompt_id="rag.answer",
            name="Grounded RAG Answer",
            version="2",
            description="Experimental prompt.",
            system_template="System {question}",
            user_template="Context {context}",
            input_variables=("question", "context"),
            output_contract="Grounded answer.",
            status="experimental",
            created_at="2026-07-10T00:00:01Z",
        )
    )

    definition = PromptExperimentDefinition(
        experiment_id="rag-answer-deprecated-control",
        name="Deprecated control",
        description="Should reject deprecated control versions by default.",
        prompt_id="rag.answer",
        control_version="1",
        treatment_versions=("2",),
        hypothesis="No-op",
        primary_metric="citation_coverage",
        secondary_metrics=(),
        guardrail_metrics=("critical_factuality_violations",),
        dataset_id="qa_dataset",
        assignment_strategy="fixed",
        allocation={"control": 0.5, "treatment_2": 0.5},
        randomization_unit="dataset_case",
        seed="seed",
        status="draft",
        allow_deprecated_versions=False,
        metadata={},
    )

    with pytest.raises(PromptExperimentValidationError, match="deprecated"):
        validate_prompt_experiment_definition(definition, registry=registry)
