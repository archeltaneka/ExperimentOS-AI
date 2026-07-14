# Repository Output Organization Design

## Goal

Define a clear repository policy that separates commit-worthy source, configuration, curated
reference outputs, and evaluation inputs from disposable local and CI-generated artifacts.

## Scope

This design covers repository hygiene only:

- what categories of files belong in git
- what categories of files should be ignored
- how `reports/`, `artifacts/`, and `data/` are intended to be used
- how developer-facing docs should describe baseline refreshes versus routine local runs

This design does not change production logic, evaluation policy thresholds, or GitHub Actions
business logic.

## Current State

The repository currently contains:

- source code, tests, workflows, migrations, and project docs that should remain versioned
- tracked evaluation input datasets under `data/eval/`
- tracked evaluation report outputs under `reports/` and `reports/phase3/`
- generated CI verification output under `artifacts/`
- generated local synthetic data under `data/synthetic/experiments/`
- local planning notes under `docs/superpowers/plans/` and `docs/superpowers/specs/`

The main ambiguity is that `reports/` is used both as a stable reference location and as a
default output path for several commands, while `artifacts/` is an obviously disposable output
location.

## Decision

Use a two-tier output model:

### 1. `reports/` is repository-owned reference output

`reports/` remains versioned and is reserved for curated baseline or reference artifacts that are
intentionally reviewed and committed.

Allowed examples:

- `reports/evaluation.md`
- `reports/agent_evaluation.md`
- `reports/agent_e2e_evaluation.md`
- `reports/phase3/*.md`
- `reports/phase3/*.json`

These files are commit-worthy when they represent accepted baseline or reference behavior and are
updated deliberately.

### 2. `artifacts/` is runtime-generated disposable output

`artifacts/` is ignored and is used for:

- local verification runs
- CI output
- temporary regression checks
- generated summaries, manifests, and diagnostic files

Recommended subdirectories:

- `artifacts/local/...` for developer runs
- `artifacts/ci/...` for CI and CI-equivalent local verification

Anything that can be regenerated on demand and is not part of the repository's reviewed baseline
belongs here.

## Directory Contract

### Commit

- source code under `apps/`, `packages/`, and similar code directories
- tests under `tests/`
- workflows and repository configuration under `.github/`, root config files, and migration files
- product and engineering docs under `docs/`
- tracked evaluation input datasets under `data/eval/`
- curated baseline/reference outputs under `reports/`

### Ignore

- generated CI and local verification output under `artifacts/`
- generated datasets outside the tracked evaluation fixtures, especially
  `data/synthetic/experiments/`
- local machine/runtime state such as virtual environments, caches, and secrets
- local planning scratch under `docs/superpowers/plans/` and `docs/superpowers/specs/`, unless a
  specific document is intentionally promoted into repository history

## Compatibility Constraints

The cleanup should preserve the existing behavior expectations for:

- `agent_workflow` as the default
- `legacy_rag` compatibility
- existing docs and tests that reference curated report paths under `reports/`

For that reason, current command defaults that write to `reports/` should not be broadly migrated
in this cleanup.

## Implementation Approach

Adopt a minimal-change cleanup:

1. Keep existing code defaults unchanged where they already use `reports/`.
2. Ignore obviously disposable outputs so routine runs do not create git noise.
3. Update developer-facing docs so routine verification examples prefer explicit
   `artifacts/local/...` destinations.
4. Keep curated baseline refresh examples that intentionally write to `reports/`.
5. Do not move existing tracked baseline files out of `reports/` in this change.

## Operational Rules

Use this decision rule for future files:

- if a file is needed for deterministic review, policy comparison, or accepted baseline history,
  commit it
- if a file is produced by running commands and can be recreated without losing repository intent,
  ignore it and place it under `artifacts/`

## Follow-Up Documentation

Developer-facing documentation should clearly distinguish:

- curated baseline refreshes that intentionally update files in `reports/`
- routine local verification runs that should target `artifacts/local/...`

This avoids further ambiguity about whether generated output should be staged.
