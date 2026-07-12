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

## Fix pass

### Reviewer findings addressed

- Fixed the Phoenix placeholder provider path so `PhoenixObservabilityProvider(settings=PhoenixSettings(enabled=True, endpoint="http://localhost:6006")).start_root_span("test").finish()` is safely non-crashing in this task.
- Fixed top-level `ObservabilitySettings` compatibility properties so Phoenix-only configurations report truthful provider-agnostic values instead of always proxying LangSmith.
- Re-ran `uv run ruff check .` as required by the review plan and recorded the result here.

### Additional TDD evidence

#### Failing command

`uv run pytest tests\test_observability_config.py -v`

#### Failing output

- `AttributeError: 'PhoenixSettings' object has no attribute 'sampling_rate'`
- `AssertionError: assert None == 'phoenix-key'`
- Summary: `2 failed, 3 passed`

#### Passing commands

- `uv run pytest tests\test_observability_config.py -v`
- `uv run ruff check .`

#### Passing output

- `5 passed in 0.22s`
- `All checks passed!`

### Files changed in fix pass

- `packages/observability/models.py`
- `tests/test_observability_config.py`

### Self-review findings for fix pass

- Shared provider defaults now cover the fields used by `BaseObservabilityProvider`, which keeps the Phoenix placeholder safe without implementing export behavior.
- Compatibility properties now read from the active provider configuration, so Phoenix-only setups no longer misreport endpoint, project, API key, tracing flags, or tags.
- The Phoenix placeholder remains intentionally non-exporting for this task; the fix is scoped to safety and truthfulness of configuration reporting.

## Second fix pass

### Reviewer finding addressed

- Restored legacy top-level `ObservabilitySettings(...)` constructor compatibility for existing LangSmith-style callers while preserving the nested `langsmith` / `phoenix` settings shape introduced in Task 1.

### Additional TDD evidence

#### Failing command

`uv run pytest tests\test_observability_config.py -v`

#### Failing output

- `TypeError: ObservabilitySettings.__init__() got an unexpected keyword argument 'enabled'`
- Summary: `1 failed, 5 passed`

#### Passing commands

- `uv run pytest tests\test_observability_config.py tests\test_observability_langsmith.py tests\test_observability_redaction.py tests\test_observability_integration.py -v`
- `uv run ruff check .`

#### Passing output

- `15 passed in 1.81s`
- `All checks passed!`

### Files changed in second fix pass

- `packages/observability/models.py`
- `tests/test_observability_config.py`

### Self-review findings for second fix pass

- `ObservabilitySettings` now accepts both nested provider instances and legacy top-level LangSmith-compatible keyword arguments.
- Legacy constructor arguments are applied onto the nested `langsmith` settings, which preserves existing LangSmith/redaction/integration call sites without backing out the provider-aware refactor.
- Provider-aware compatibility behavior from the previous fix pass remains intact, and the Phoenix placeholder remains safely non-crashing.
