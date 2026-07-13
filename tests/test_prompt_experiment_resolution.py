from __future__ import annotations


def test_prompt_resolution_prefers_explicit_then_context_then_active() -> None:
    from packages.evals.prompt_experiments.models import PromptExperimentContext
    from packages.evals.prompt_experiments.resolution import resolve_prompt_version
    from packages.llm.prompt_registry import get_prompt_registry

    registry = get_prompt_registry()
    context = PromptExperimentContext(
        experiment_id="rag-answer-abstention-v1-v2",
        variant="treatment_2",
        prompt_id="rag.answer",
        prompt_version="2",
        assignment_strategy="deterministic_hash",
        assignment_key_hash="hash",
        allocation={"control": 0.5, "treatment_2": 0.5},
    )

    assert resolve_prompt_version("rag.answer", registry=registry) == "1"
    assert (
        resolve_prompt_version(
            "rag.answer",
            registry=registry,
            experiment_context=context,
        )
        == "2"
    )
    assert (
        resolve_prompt_version(
            "rag.answer",
            registry=registry,
            explicit_version="1",
            experiment_context=context,
        )
        == "1"
    )


def test_prompt_resolution_does_not_override_unrelated_prompt_ids() -> None:
    from packages.evals.prompt_experiments.models import PromptExperimentContext
    from packages.evals.prompt_experiments.resolution import resolve_prompt_version
    from packages.llm.prompt_registry import get_prompt_registry

    registry = get_prompt_registry()
    context = PromptExperimentContext(
        experiment_id="rag-answer-abstention-v1-v2",
        variant="treatment_2",
        prompt_id="rag.answer",
        prompt_version="2",
        assignment_strategy="deterministic_hash",
        assignment_key_hash="hash",
        allocation={"control": 0.5, "treatment_2": 0.5},
    )

    assert (
        resolve_prompt_version(
            "rag.summary",
            registry=registry,
            experiment_context=context,
        )
        == "1"
    )


def test_exposure_recorder_deduplicates_same_execution() -> None:
    from packages.evals.prompt_experiments.exposure import PromptExperimentExposureRecorder
    from packages.evals.prompt_experiments.models import PromptExperimentExposure

    recorder = PromptExperimentExposureRecorder()
    exposure = PromptExperimentExposure(
        experiment_id="rag-answer-abstention-v1-v2",
        variant="treatment_2",
        prompt_id="rag.answer",
        prompt_version="2",
        assignment_key_hash="hash",
        trace_id="trace-123",
        timestamp="2026-07-13T00:00:00Z",
        execution_mode="workflow",
    )

    assert recorder.record_once(exposure) is True
    assert recorder.record_once(exposure) is False
    assert recorder.exposures == [exposure]
