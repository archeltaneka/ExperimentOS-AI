# Phase 3 Prompt Registry

ExperimentOS AI now keeps prompt management inside the repository instead of scattering raw prompt
strings across services.

## Why prompts are centrally managed

Central prompt registration gives the project one place to:

- assign stable prompt IDs
- track prompt versions explicitly
- validate template variables before runtime
- reuse prompt definitions without copying strings
- attach prompt provenance to QA and evaluation outputs

This foundation is intentionally narrow. It covers the real prompt-backed surfaces that already
exist today and avoids building a prompt platform before the repository needs one.

## Current scope

Registered prompts currently cover:

- `rag.answer`
  - active version: `1`
  - purpose: grounded `legacy_rag` answer generation
- `rag.decision`
  - active version: `1`
  - status: `experimental`
  - purpose: backward-compatible decision helper template from `packages.llm.prompts`
- `rag.summary`
  - active version: `1`
  - status: `experimental`
  - purpose: backward-compatible summary helper template from `packages.llm.prompts`

Only `rag.answer` is active in production behavior today.

## Architecture

The registry is code-backed and lives in:

- `packages/llm/prompt_registry.py`
- `packages/llm/prompt_registry_cli.py`
- `packages/llm/prompts.py`

`packages.llm.prompts` remains the compatibility facade for existing imports. It now resolves its
constants and grounded QA prompt builder through the registry instead of duplicating raw prompt
strings.

## Prompt model

Each prompt definition includes:

- `prompt_id`
- `name`
- `version`
- `description`
- `system_template`
- `user_template`
- `input_variables`
- `output_contract`
- `tags`
- `status`
- `created_at`
- `metadata`

Rendered prompts expose:

- `prompt_id`
- `version`
- `system_prompt`
- `user_prompt`
- `rendered_text`
- `variables`
- `metadata`

## Naming convention

Prompt IDs use dot-separated scope names owned by the repository:

- `rag.answer`
- `rag.decision`
- `rag.summary`

This keeps IDs stable even if implementation details move between modules.

## Versioning convention

Prompt versions are explicit strings. The first registered version is `1`.

Rules:

- `(prompt_id, version)` must be unique
- each prompt ID has an explicit active version
- definitions are immutable once registered in code

## Lifecycle statuses

The registry currently supports:

- `active`
- `deprecated`
- `experimental`

Status is separate from active-version selection. A prompt can have an active default version while
still being marked `experimental` if it is registered for compatibility or future use rather than
current production behavior.

## Validation behavior

Prompt registration and rendering fail clearly when:

- a prompt definition is malformed
- template placeholders do not match declared input variables
- a duplicate prompt version is registered
- a prompt ID is unknown
- a version is unknown
- required variables are missing
- unexpected variables are passed
- values are blank or `None`

This prevents silent prompt drift and missing-variable bugs.

## Prompt provenance

Prompt provenance is recorded only when an LLM prompt is actually rendered.

Current behavior:

- `legacy_rag` QA responses expose `prompt_id` and `prompt_version`
- `POST /ask` exposes `prompt_metadata` for `legacy_rag`
- offline QA evaluation samples and reports carry prompt provenance when available
- deterministic `agent_workflow` responses intentionally leave prompt provenance empty

The repository does not expose full prompt text through API responses.

## Deterministic agents intentionally not registered

These remain deterministic application logic, not prompt-managed LLM agents:

- planner agent
- experiment analysis agent
- business impact agent
- risk assessment agent
- decision agent
- executive summary agent

The current workflow should not receive invented prompt templates just to fit the registry.

## CLI usage

List prompts:

```powershell
uv run python -m packages.llm.prompt_registry_cli list
```

Show prompt metadata:

```powershell
uv run python -m packages.llm.prompt_registry_cli show rag.answer --version 1
```

List versions:

```powershell
uv run python -m packages.llm.prompt_registry_cli versions rag.answer
```

Validate the registry:

```powershell
uv run python -m packages.llm.prompt_registry_cli validate
```

Use `--show-templates` with `show` only for local inspection when full template text is needed.

## How to add a new prompt

1. Add a new `PromptDefinition` in `packages/llm/prompt_registry.py`.
2. Register it with an explicit version.
3. Mark the active version explicitly.
4. Add or update tests for registration, rendering, and integration behavior.
5. Update evaluation or reporting only if the prompt is used by a real runtime path.
6. Update this document if the new prompt changes current registry scope.

## How to deprecate a prompt version

1. Keep the existing version registered.
2. Mark its status as `deprecated`.
3. Register the replacement version.
4. Move the active version pointer to the new version.
5. Add compatibility tests if any legacy import or workflow still depends on the older wording.

## Why external prompt platforms are not used yet

ExperimentOS AI keeps prompt management local for now because:

- the current prompt surface is small
- repository-owned version control is sufficient
- tests and evaluation should stay deterministic
- the project does not need runtime editing or hosted prompt governance yet

This avoids premature coupling to LangSmith or any other external prompt platform.
