from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from string import Formatter
from types import MappingProxyType
from typing import Literal

PromptStatus = Literal["active", "deprecated", "experimental"]


class PromptRegistryError(RuntimeError):
    pass


class PromptDefinitionError(PromptRegistryError, ValueError):
    pass


class DuplicatePromptRegistrationError(PromptRegistryError):
    pass


class PromptLookupError(PromptRegistryError, LookupError):
    pass


class PromptRenderError(PromptRegistryError, ValueError):
    pass


@dataclass(frozen=True)
class PromptDefinition:
    prompt_id: str
    name: str
    version: str
    description: str
    system_template: str
    user_template: str
    input_variables: tuple[str, ...]
    output_contract: str
    tags: tuple[str, ...] = ()
    status: PromptStatus = "active"
    created_at: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "input_variables", tuple(self.input_variables))
        object.__setattr__(self, "tags", tuple(self.tags))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

        _require_non_empty("prompt_id", self.prompt_id)
        _require_non_empty("name", self.name)
        _require_non_empty("version", self.version)
        _require_non_empty("description", self.description)
        _require_non_empty("output_contract", self.output_contract)
        _require_non_empty("created_at", self.created_at)

        if not self.input_variables:
            raise PromptDefinitionError("input_variables must not be empty")
        if len(set(self.input_variables)) != len(self.input_variables):
            raise PromptDefinitionError("input_variables must be unique")
        if any(not value.strip() for value in self.input_variables):
            raise PromptDefinitionError("input_variables must not contain blank values")

        declared_variables = set(self.input_variables)
        template_variables = _extract_template_variables(
            self.system_template
        ) | _extract_template_variables(self.user_template)
        if template_variables != declared_variables:
            raise PromptDefinitionError(
                "template variables must match input_variables exactly: "
                f"declared={sorted(declared_variables)} actual={sorted(template_variables)}"
            )


@dataclass(frozen=True)
class RenderedPrompt:
    prompt_id: str
    version: str
    system_prompt: str
    user_prompt: str
    rendered_text: str
    variables: dict[str, object]
    metadata: dict[str, object]


class PromptRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, dict[str, PromptDefinition]] = {}
        self._active_versions: dict[str, str] = {}

    def register(self, definition: PromptDefinition, *, active: bool = False) -> PromptDefinition:
        versions = self._definitions.setdefault(definition.prompt_id, {})
        if definition.version in versions:
            raise DuplicatePromptRegistrationError(
                f"duplicate prompt registration for {definition.prompt_id}@{definition.version}"
            )
        versions[definition.version] = definition
        if active:
            self._active_versions[definition.prompt_id] = definition.version
        return definition

    def get(self, prompt_id: str, version: str) -> PromptDefinition:
        versions = self._definitions.get(prompt_id)
        if versions is None:
            raise PromptLookupError(f"unknown prompt: {prompt_id}")
        try:
            return versions[version]
        except KeyError as exc:
            raise PromptLookupError(f"unknown version for {prompt_id}: {version}") from exc

    def get_active(self, prompt_id: str) -> PromptDefinition:
        version = self._active_versions.get(prompt_id)
        if version is None:
            raise PromptLookupError(f"unknown prompt: {prompt_id}")
        return self.get(prompt_id, version)

    def list_prompts(self) -> tuple[PromptDefinition, ...]:
        return tuple(self.get_active(prompt_id) for prompt_id in sorted(self._active_versions))

    def list_versions(self, prompt_id: str) -> tuple[str, ...]:
        versions = self._definitions.get(prompt_id)
        if versions is None:
            raise PromptLookupError(f"unknown prompt: {prompt_id}")
        return tuple(sorted(versions))

    def render(
        self,
        prompt_id: str,
        variables: Mapping[str, object],
        *,
        version: str | None = None,
    ) -> RenderedPrompt:
        if version is not None:
            definition = self.get(prompt_id, version)
        else:
            definition = self.get_active(prompt_id)
        normalized_variables = dict(variables)
        expected_variables = set(definition.input_variables)
        actual_variables = set(normalized_variables)

        missing = sorted(expected_variables - actual_variables)
        if missing:
            raise PromptRenderError(f"missing variables for {prompt_id}: {missing}")

        unexpected = sorted(actual_variables - expected_variables)
        if unexpected:
            raise PromptRenderError(f"unexpected variables for {prompt_id}: {unexpected}")

        for key, value in normalized_variables.items():
            if value is None:
                raise PromptRenderError(f"variable {key!r} must not be None")
            if isinstance(value, str) and not value.strip():
                raise PromptRenderError(f"variable {key!r} must not be empty")

        system_prompt = definition.system_template.format(**normalized_variables)
        user_prompt = definition.user_template.format(**normalized_variables)
        metadata = {
            "name": definition.name,
            "description": definition.description,
            "output_contract": definition.output_contract,
            "status": definition.status,
            "tags": list(definition.tags),
            **dict(definition.metadata),
        }
        return RenderedPrompt(
            prompt_id=definition.prompt_id,
            version=definition.version,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            rendered_text="\n\n".join(
                part for part in (system_prompt, user_prompt) if part.strip()
            ),
            variables=normalized_variables,
            metadata=metadata,
        )

    def validate(self) -> None:
        for prompt_id, versions in self._definitions.items():
            if not versions:
                raise PromptRegistryError(f"prompt {prompt_id} has no registered versions")
            if prompt_id not in self._active_versions:
                raise PromptRegistryError(f"prompt {prompt_id} has no active version")
            active_version = self._active_versions[prompt_id]
            if active_version not in versions:
                raise PromptRegistryError(
                    f"prompt {prompt_id} active version {active_version} is not registered"
                )


def get_prompt_registry() -> PromptRegistry:
    return _PROMPT_REGISTRY


def _build_default_prompt_registry() -> PromptRegistry:
    registry = PromptRegistry()
    registry.register(
        PromptDefinition(
            prompt_id="rag.answer",
            name="Grounded RAG Answer",
            version="1",
            description="Grounded answer prompt for legacy_rag experiment QA.",
            system_template=(
                "Only answer using retrieved context.\n"
                "If the answer cannot be supported by retrieved evidence, say that insufficient "
                "evidence exists.\n"
                "Never invent facts."
            ),
            user_template="\n\n".join(
                [
                    "User Question: {question}",
                    "Retrieved Context:",
                    "{context}",
                    "Answer using only the retrieved context and cite the supporting documents.",
                ]
            ),
            input_variables=("question", "context"),
            output_contract="Grounded answer that cites supporting retrieved documents only.",
            tags=("legacy_rag", "qa", "grounded"),
            status="active",
            created_at="2026-07-10T00:00:00Z",
            metadata={"surface": "legacy_rag", "owner": "packages.qa.question_answering_service"},
        ),
        active=True,
    )
    registry.register(
        PromptDefinition(
            prompt_id="rag.answer",
            name="Grounded RAG Answer",
            version="2",
            description=(
                "Experimental grounded answer prompt with stronger abstention wording and "
                "clearer citation requirements."
            ),
            system_template=(
                "Only answer using retrieved context.\n"
                "If the answer cannot be fully supported by retrieved evidence, say that "
                "insufficient evidence exists.\n"
                "Prefer abstaining over guessing.\n"
                "Never invent facts."
            ),
            user_template="\n\n".join(
                [
                    "User Question: {question}",
                    "Retrieved Context:",
                    "{context}",
                    "Answer using only the retrieved context, cite the supporting documents, "
                    "and state clearly when evidence is insufficient.",
                ]
            ),
            input_variables=("question", "context"),
            output_contract="Grounded answer that cites supporting retrieved documents only.",
            tags=("legacy_rag", "qa", "grounded", "experimental"),
            status="experimental",
            created_at="2026-07-12T00:00:00Z",
            metadata={"surface": "legacy_rag", "owner": "packages.qa.question_answering_service"},
        )
    )
    registry.register(
        PromptDefinition(
            prompt_id="rag.decision",
            name="Decision Helper",
            version="1",
            description=(
                "Legacy decision-oriented prompt template kept for backward-compatible imports."
            ),
            system_template="",
            user_template="\n\n".join(
                [
                    "Decision Question: {question}",
                    "Evidence:",
                    "{context}",
                    "Summarize the decision, supporting evidence, and any unresolved uncertainty.",
                ]
            ),
            input_variables=("question", "context"),
            output_contract="Grounded decision summary.",
            tags=("decision", "legacy_helper"),
            status="experimental",
            created_at="2026-07-10T00:00:00Z",
            metadata={"surface": "inactive_helper", "owner": "packages.llm.prompts"},
        ),
        active=True,
    )
    registry.register(
        PromptDefinition(
            prompt_id="rag.summary",
            name="Summary Helper",
            version="1",
            description=(
                "Legacy summary-oriented prompt template kept for backward-compatible imports."
            ),
            system_template="",
            user_template="\n\n".join(
                [
                    "Summary Request: {question}",
                    "Source Context:",
                    "{context}",
                    "Produce a concise summary grounded only in the source context.",
                ]
            ),
            input_variables=("question", "context"),
            output_contract="Grounded concise summary.",
            tags=("summary", "legacy_helper"),
            status="experimental",
            created_at="2026-07-10T00:00:00Z",
            metadata={"surface": "inactive_helper", "owner": "packages.llm.prompts"},
        ),
        active=True,
    )
    registry.validate()
    return registry


def _extract_template_variables(template: str) -> set[str]:
    variables: set[str] = set()
    for _, field_name, _, _ in Formatter().parse(template):
        if field_name:
            variables.add(field_name)
    return variables


def _require_non_empty(field_name: str, value: str) -> None:
    if not value.strip():
        raise PromptDefinitionError(f"{field_name} must not be empty")


_PROMPT_REGISTRY = _build_default_prompt_registry()
