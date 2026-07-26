# Task 2 report: Finite numerical helpers

## Delivered

- Added pure `summarize_continuous`, `summarize_binary`, and `summarize_count` helpers.
- Added `NumericSummaryInvariantError` for invalid or non-finite numerical inputs and
  non-finite derived statistics.
- Empty inputs return `UnavailableSummary(reason="no observations")`.
- Continuous summaries use `math.fsum`, sample standard deviation, and sorted linear
  quartiles. A single observation retains its descriptive values while its deviation is
  unavailable.
- Binary inputs must be exact `0.0` or `1.0`; counts must be finite, non-negative
  integers.

## TDD evidence

### Red

After adding `tests/test_descriptive_statistics_numeric.py`, before production code:

```text
$ uv run pytest tests/test_descriptive_statistics_numeric.py
ModuleNotFoundError: No module named 'packages.experiments.analysis.descriptive.numeric'
```

The test module could not import the intentionally absent feature module.

### Green

After adding `numeric.py`:

```text
$ uv run pytest tests/test_descriptive_statistics_numeric.py
9 passed in 0.25s

$ uv run ruff check .
All checks passed!

$ git diff --check
(no output; passed)
```

## Changed paths

- `packages/experiments/analysis/descriptive/numeric.py`
- `tests/test_descriptive_statistics_numeric.py`
- `.superpowers/sdd/2026-07-26-descriptive-statistics/task-2-report.md`

## Tests covered

- Hand-calculable continuous data `(1, 2, 3, 4)` and linear quartiles.
- A single observation, empty values, zero variance, and extreme finite values.
- Valid all-binary outcomes and invalid binary value `2`.
- Zero counts and negative count rejection.

## Commit

`[New Feature] Add deterministic descriptive numeric summaries`

## Concerns

None.

## Contract follow-up

The Task 1 contracts were subsequently expanded with variance, standard-error, and binary
success/failure/rate fields. Task 2 now returns all of those fields.

### Red

```text
$ uv run pytest tests/test_descriptive_statistics_numeric.py
5 failed, 4 passed
```

The new assertions showed that the helpers had omitted the newly contracted values.

### Green

```text
$ uv run pytest tests/test_descriptive_statistics_numeric.py
11 passed in 0.26s

$ uv run ruff check .
All checks passed!

$ git diff --check
(no output; passed)
```

Continuous and count summaries now emit sample variance and standard error when `n >= 2`;
otherwise both fields are `None`. Binary summaries emit success/failure counts, rate, sample
variance, and observed-rate standard error under the same availability rule.
