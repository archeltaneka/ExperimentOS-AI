# Final Phase 4 reliability review

The canonical human audit for issue #110 is
[final_reliability_review.md](../../reports/phase4/final_reliability_review.md).
Its authoritative structured counterpart is
[final_reliability_review.json](../../reports/phase4/final_reliability_review.json).
The [portable evidence snapshot](../../reports/phase4/reliability_evidence.json)
records executed command outcomes, per-module test results/skips, native and workflow
case checks, policy results, environment versions and current-base GitHub CI metadata.

This is a dated audit of a specific base commit and explicitly identified working-tree
changes. It is not a replacement evaluation engine or a continuously updated release
certification. `READY_WITH_ADVISORIES` does not close an issue, prove causal assumptions,
authorize rollout or certify production deployment. Each capability has its own bounded
classification; DiD, IPW and HTE retain advisory inference limitations, while optional
adapters remain optional even when their installed-runtime checks pass.

## Validate and render

Run from the repository root:

```sh
uv run python -m packages.evals.phase4_review --check
```

The validator checks source and portable-evidence SHA-256 digests, exact JSON Pointer
values, evidence references, command claims against execution records, production
readiness dimension references, and readiness consistency. It compares the existing
Markdown with a fresh rendering of the JSON. It does not independently prove a prose
claim or derive statistical correctness from passing tests: those remain the human
review and existing quality policy's responsibilities.

To regenerate Markdown from the reviewed JSON, omit `--check`. JSON object-key order
does not affect rendering. A changed source or evidence file requires reviewing the
claim again; do not merely replace its digest to make validation pass.

The original runtime reports and logs live under `artifacts/issue110/`, which is ignored
by git. On the audit machine, also verify the full canonical runtime report digests:

```sh
uv run python -m packages.evals.phase4_review --check --verify-runtime
```

A fresh checkout has the portable snapshot, not the ignored runtime archive. Default
validation verifies that snapshot and source references; it does not imply the raw
runtime reports were recovered or recomputed. Preserve `artifacts/issue110/` separately
if complete execution logs are needed. The snapshot omits raw observations, outcomes,
propensity/weight arrays, nuisance predictions, posterior samples and database secrets.

## Reproduce the scientific and compatibility evidence

Use the existing commands, not a second measurement framework:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 uv run python -m packages.evals.cli statistical-baseline \
  --json-output artifacts/issue110/core/statistical_baseline.json \
  --output artifacts/issue110/core/statistical_baseline.md

# In the locked Python 3.13 environment with econml and dowhy groups installed:
uv run --no-sync python -m packages.evals.cli statistical-baseline \
  --scope optional-adapters --require-optional econml --require-optional dowhy \
  --json-output artifacts/issue110/optional/statistical_baseline.json \
  --output artifacts/issue110/optional/statistical_baseline.md

# With DATABASE_URL pointing to a disposable local verification database:
uv run python scripts/verify_phase3.py \
  --artifact-root artifacts/issue110/phase3 \
  --report-root artifacts/issue110/phase3-review

uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Use the existing CI fake embeddings/mock LLM settings, disabled judges/exporters and
fixed seeds. Exact executed commands, environment identities and dates are recorded in
the JSON. Temporary optional-environment paths identify this execution machine; substitute
your equivalent frozen environment when reproducing. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`
was used to avoid unrelated installed pytest plugins; the repository's autouse external
network guard remains active.

The audit initially found no process-level DATABASE_URL, then started the existing
isolated verification container and ran strict database verification. The database-free
core test run's skips remain explicit; separate local database and installed-adapter
runs supply that coverage. Interrupted sandbox attempts and a corrected nonexistent
optional-test path remain recorded and are not passes. Historical offline diagnostics
are not used as strict closeout evidence.

Re-execution changes durations, trace identities and artifact hashes. Review new results
and refresh the structured audit deliberately; do not expect a newly generated report
to match the old bytes. Numerical repeatability is checked by the existing native and
workflow replay contracts. The renderer has no estimator execution, network access or
quality-threshold ownership.
