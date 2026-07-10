from __future__ import annotations

import pytest


def test_default_prompt_registry_exposes_registered_prompts_and_active_versions() -> None:
    from packages.llm.prompt_registry import get_prompt_registry

    registry = get_prompt_registry()

    prompt_ids = [definition.prompt_id for definition in registry.list_prompts()]

    assert prompt_ids == ["rag.answer", "rag.decision", "rag.summary"]
    assert registry.get_active("rag.answer").version == "1"
    assert registry.get_active("rag.answer").status == "active"
    assert registry.get_active("rag.decision").status == "experimental"
    assert registry.list_versions("rag.answer") == ("1",)


def test_prompt_registry_rejects_duplicate_prompt_registration() -> None:
    from packages.llm.prompt_registry import (
        DuplicatePromptRegistrationError,
        PromptDefinition,
        PromptRegistry,
    )

    registry = PromptRegistry()
    definition = PromptDefinition(
        prompt_id="test.prompt",
        name="Test Prompt",
        version="1",
        description="A test prompt.",
        system_template="System",
        user_template="Question: {question}",
        input_variables=("question",),
        output_contract="plain text",
        tags=("test",),
        status="active",
        created_at="2026-07-10T00:00:00Z",
        metadata={"surface": "unit-test"},
    )

    registry.register(definition, active=True)

    with pytest.raises(DuplicatePromptRegistrationError):
        registry.register(definition, active=True)


def test_prompt_registry_supports_explicit_and_active_lookup() -> None:
    from packages.llm.prompt_registry import PromptDefinition, PromptRegistry

    registry = PromptRegistry()
    v1 = PromptDefinition(
        prompt_id="test.prompt",
        name="Test Prompt",
        version="1",
        description="Initial version.",
        system_template="System {audience}",
        user_template="Question: {question}",
        input_variables=("audience", "question"),
        output_contract="plain text",
        tags=("test",),
        status="deprecated",
        created_at="2026-07-10T00:00:00Z",
        metadata={},
    )
    v2 = PromptDefinition(
        prompt_id="test.prompt",
        name="Test Prompt",
        version="2",
        description="Current version.",
        system_template="System {audience}",
        user_template="Question: {question}",
        input_variables=("audience", "question"),
        output_contract="plain text",
        tags=("test",),
        status="active",
        created_at="2026-07-10T00:00:01Z",
        metadata={},
    )

    registry.register(v1)
    registry.register(v2, active=True)

    assert registry.get("test.prompt", "1").description == "Initial version."
    assert registry.get_active("test.prompt").version == "2"


def test_prompt_registry_rejects_unknown_prompt_and_unknown_version() -> None:
    from packages.llm.prompt_registry import PromptLookupError, get_prompt_registry

    registry = get_prompt_registry()

    with pytest.raises(PromptLookupError, match="unknown prompt"):
        registry.get_active("missing.prompt")

    with pytest.raises(PromptLookupError, match="unknown version"):
        registry.get("rag.answer", "99")


def test_prompt_definition_rejects_malformed_template_variable_contract() -> None:
    from packages.llm.prompt_registry import PromptDefinition, PromptDefinitionError

    with pytest.raises(PromptDefinitionError, match="template variables"):
        PromptDefinition(
            prompt_id="bad.prompt",
            name="Bad Prompt",
            version="1",
            description="Malformed prompt.",
            system_template="System",
            user_template="Question: {question}\nContext: {context}",
            input_variables=("question",),
            output_contract="plain text",
            tags=("test",),
            status="active",
            created_at="2026-07-10T00:00:00Z",
            metadata={},
        )


def test_prompt_registry_render_rejects_missing_and_unexpected_variables() -> None:
    from packages.llm.prompt_registry import PromptRenderError, get_prompt_registry

    registry = get_prompt_registry()

    with pytest.raises(PromptRenderError, match="missing variables"):
        registry.render("rag.answer", {"question": "Why did it ship?"})

    with pytest.raises(PromptRenderError, match="unexpected variables"):
        registry.render(
            "rag.answer",
            {
                "question": "Why did it ship?",
                "context": "Chunk 1",
                "extra": "nope",
            },
        )


def test_prompt_registry_renders_grounded_prompt_with_metadata() -> None:
    from packages.llm.prompt_registry import get_prompt_registry

    registry = get_prompt_registry()

    rendered = registry.render(
        "rag.answer",
        {
            "question": "Why did it ship?",
            "context": "Chunk 1\nText:\nThe rollout passed guardrails.",
        },
    )

    assert rendered.prompt_id == "rag.answer"
    assert rendered.version == "1"
    assert rendered.system_prompt.startswith("Only answer using retrieved context.")
    assert rendered.user_prompt.endswith("cite the supporting documents.")
    assert rendered.variables == {
        "question": "Why did it ship?",
        "context": "Chunk 1\nText:\nThe rollout passed guardrails.",
    }
