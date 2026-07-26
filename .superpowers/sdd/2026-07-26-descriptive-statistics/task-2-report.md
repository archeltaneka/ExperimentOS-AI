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

The Task 1 public summary contracts do not expose variance or standard-error fields.
The helpers calculate the required finite standard-error intermediates as invariants, but
return only fields available in those committed contracts.
