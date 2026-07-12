## What I implemented

- Refactored observability configuration into nested provider settings:
  - `ProviderSettings`
  - `LangSmithSettings`
  - `PhoenixSettings`
  - `ObservabilitySettings`
- Updated `load_observability_settings()` to load both LangSmith and Phoenix environment variables with the exact defaults required by the brief.
- Refactored `resolve_observability_provider()` to support:
  - no providers enabled -> `NoOpObservabilityProvider`
  - LangSmith enabled -> validated LangSmith provider
  - Phoenix enabled -> validated Phoenix provider dependency gate
  - multiple enabled providers -> `CompositeObservabilityProvider`
- Preserved compatibility for existing LangSmith-oriented consumers by keeping top-level compatibility properties on `ObservabilitySettings`.
- Added minimal placeholder provider classes for Phoenix and composite fan-out without changing the buffered span abstraction or implementing Phoenix export.
- Replaced the old config tests with the required nested settings and Phoenix dependency-resolution tests.

## Tests run and results

- `uv run pytest tests\test_observability_config.py -v`
  - First run: `2 failed, 1 passed`
  - Second run after implementation: `3 passed`
- `uv run ruff check packages\observability\models.py packages\observability\factory.py packages\observability\__init__.py packages\observability\noop.py tests\test_observability_config.py`
  - Result: `All checks passed!`

## TDD evidence

### Failing command

`uv run pytest tests\test_observability_config.py -v`

### Failing output

- `AttributeError: 'ObservabilitySettings' object has no attribute 'langsmith'`
- `Failed: DID NOT RAISE ObservabilityConfigurationError`
- Summary: `2 failed, 1 passed`

### Passing command

`uv run pytest tests\test_observability_config.py -v`

### Passing output

- `3 passed in 0.20s`

## Files changed

- `packages/observability/models.py`
- `packages/observability/factory.py`
- `packages/observability/__init__.py`
- `packages/observability/noop.py`
- `tests/test_observability_config.py`

## Self-review findings

- The nested config shape matches the task brief and the required default values.
- Provider resolution now cleanly separates LangSmith and Phoenix validation/dependency checks.
- I intentionally kept `PhoenixObservabilityProvider` as a no-op placeholder for this task, because the brief explicitly said not to implement Phoenix export yet.
- I added compatibility properties on `ObservabilitySettings` so untouched LangSmith-oriented code paths are less likely to break before later observability tasks land.

## Issues or concerns

- `PhoenixObservabilityProvider` currently resolves successfully only as a placeholder; it does not emit spans yet by design.
- `CompositeObservabilityProvider` is intentionally minimal and exists to stabilize the resolution surface for later fan-out work.
