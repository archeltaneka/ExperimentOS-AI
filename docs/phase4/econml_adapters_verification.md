# Issue #104 implementation and verification

Branch: `feature/issue-104-econml-adapters`, linked to GitHub issue #104 with
`gh issue develop`. Issue/dependency implementations and repository contracts were
reviewed before implementation. The Superpowers architectural brainstorming design
was approved by the user. Adapter contract tests were written and observed failing
before production code. Dependencies were investigated before packaging changes.
No commit, push, PR, merge or branch-protection change was made.

## Documentation and compatibility evidence

Context7 resolved `/py-why/econml` and was consulted for package compatibility,
LinearDML, LinearDRLearner and inference/effect APIs. Mixed-version snippets were
cross-checked against EconML 0.17.0 versioned source and the installed API signatures.
Both estimators support upstream auto/statsmodels/bootstrap inference and disabled
inference; the adapters deliberately accept only explicit statsmodels HC1.

EconML 0.17.0 is compatible with this Linux x86_64 Python 3.12.14 environment:
NumPy 2.5.0, SciPy 1.18.0 and scikit-learn 1.9.0 satisfy upstream constraints.
Statsmodels 0.15.0, SHAP 0.52.0, LightGBM 4.7.0, numba 0.67.0 and sparse 0.19.2
install together. Python 3.12–3.14 is the adapter's verified declaration range;
other interpreter/platform combinations were not runtime-tested. The Python <3.15
optional-group marker does not narrow the project's Python ≥3.12 core constraint.

Wheel-only constrained resolution probes for core plus EconML (127 packages) and
all existing groups plus EconML (195 packages) succeeded before installation.
Final universal `uv.lock` resolves 200 packages. Comparing every pre-existing locked
package's version set against HEAD shows **zero existing version changes**.

Only the optional `econml` dependency group was added to pyproject.toml. The lock adds
cloudpickle 3.1.2, EconML 0.17.0, formulaic 1.2.2, interface-meta 2.0.1, LightGBM 4.7.0,
llvmlite 0.49.0, numba 0.67.0, patsy 1.0.3, SHAP 0.49.1/0.52.0 universal forks,
slicer 0.0.8, sparse 0.19.2 and statsmodels 0.15.0. No core package downgrade.

## Architecture and files

- `causal/advanced/{models,protocols,quality}.py`: owned bounded configuration,
  capability/execution protocol, normalized ATE uncertainty/result, scalar runtime
  provenance and minimal completed-result safety checks.
- `causal/econml/{dependency,common,nuisance,dml,hte,observability}.py`: lazy verified
  dependency boundary, canonical explicit folds, actual fitted-nuisance auditing,
  exactly two computation adapters, failure/uncertainty normalization and safe providers.
- Existing `causal/hte/{models,results,validation}.py`: minimal explicit DR method/version,
  inference labels and optional owned adapter provenance; baseline defaults preserved.
  Public HTE model docstrings added for the existing documentation check.
- `tests/econml_fixtures.py` and eight `test_econml_*.py` modules: dependency boundaries,
  unsupported inputs, deterministic fixtures, uncertainty/provenance, failure injection,
  owned public graphs, overlap/timing, policy/provider checks and baseline comparisons.
- `tests/test_hte_public_contracts.py`: recursively asserts owned public objects;
  scalar library names in required provenance are permitted.
- `docs/phase4/econml_adapters.md`: installation, supported semantics, uncertainty,
  dependency findings and statistical limitations. This file records verification.

LinearDML maps to constant-effect ATE only with an explicit owned constant-effect
assertion. LinearDRLearner maps two prespecified binary subgroup CATEs and direct
heterogeneity evidence to existing HTE contracts. No estimator selection or baseline
replacement. Identification is rechecked with ExperimentOS, including the resolved
adjustment set; EconML never identifies the causal effect.

Missing/import-failed dependencies abstain explicitly. Incompatible runtime,
unsupported inference/configuration, invalid treatment/outcome/estimand/modifier/shape,
fit/inference failure and non-finite output suppress estimates with safe owned codes.
No third-party exceptions, fitted objects, inference objects or sklearn models escape.
Malformed copied request declarations are also normalized without revalidating the
invalid input echo in failure construction.

Successful provenance records class/version, bounded constructor/nuisance settings,
feature timing/roles, all seeds, actual fit reports, fold fingerprint and runtime versions.
Stable-ID folds, fixed nuisances and explicit library seeds reproduce same-runtime runs
and row permutations. No cross-platform bitwise guarantee.

Quality checks reject completed invalid identification, unavailable dependency,
unsupported inference/estimand, seed inconsistency, missing/non-finite uncertainty and
severe overlap. HTE reuses baseline quality checks. Observability emits only safe scalar
metadata/status/codes/duration; no rows, CATEs, nuisance predictions or fitted objects.

## Final verification commands and exact results

All commands below exited 0. Tests use single-thread BLAS/OpenMP where shown to avoid
contention, without changing estimator selection, seeds, fixtures or tolerances.

| Command | Result |
|---|---|
| `uv sync --group dev --group eval --group observability --frozen --cache-dir /tmp/issue-104-compatibility/cache` | Existing groups installed; core contains 184 compatible packages, EconML absent |
| `UV_PROJECT_ENVIRONMENT=/tmp/issue-104-econml-clean uv sync --group dev --group eval --group observability --group econml --frozen --cache-dir /tmp/issue-104-compatibility/cache` | Clean isolated installation; 196 packages installed |
| `uv lock --check` | Resolved 200 packages; synchronized lock |
| `uv pip check` | Checked 184 packages; all compatible |
| `uv pip check --python /tmp/issue-104-econml-clean/bin/python` | Checked 196 packages; all compatible |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 454 files already formatted |
| `uv run mypy` | Success: no issues found in 116 source files |
| `git diff --check` | No whitespace errors |
| `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q --tb=short` | 1705 passed, 35 skipped, 2 warnings in 74.29s; skips require real EconML |
| `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/issue-104-econml-clean/bin/python -m pytest -q tests/test_econml*.py --tb=short` | 74 passed in 6.67s; no skips |
| `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /tmp/issue-104-econml-clean/bin/python -m pytest -q --tb=short` | 1740 passed, 2 warnings in 72.62s; no skips |
| `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_dml*.py tests/test_hte*.py tests/test_observational_reliability*.py tests/test_ipw*.py tests/test_propensity*.py tests/test_did*.py tests/test_randomized*.py tests/test_statistical_baseline*.py tests/test_phase3*.py --tb=short` | 575 passed, 1 warning in 40.16s |
| `uv run python -m packages.evals.cli statistical-baseline --json-output /tmp/issue-104-statistical-baseline.json --output /tmp/issue-104-statistical-baseline.md` | Both artifacts written; overall pass, observational advisory with 0 blocking failures and 13 existing advisories; exit 0 |
| `.venv/bin/python -c 'import importlib.util; assert importlib.util.find_spec("econml") is None; print("core environment: EconML absent")'` | Core environment: EconML absent |
| Dependency-disabled subprocess contract test | Core API/IPW/DiD/propensity/randomized imports and owned DML/HTE computations succeed with EconML imports blocked |

The full core suite includes Phase 3 API/workflow/evaluation/quality/observability and
real database regressions, with the configured external-network guard active.
`docker compose up -d postgres` started the existing local service;
`uv run alembic upgrade head` completed existing migrations. No live LLM functionality
was implemented or invoked intentionally. Existing warnings concern FastAPI TestClient
and sunset langchain-community, not adapter failure.

Initial verification failures were resolved: absent existing observability group;
sandbox-blocked pytest local socket; missing PostgreSQL service; missing HTE public
contract docstrings; a schema substring assertion conflicting with required scalar
library provenance. A preliminary shared-site-packages optional environment ran real
fixtures but failed `uv pip check` because uv does not count its shared `.pth` closure;
it was replaced with the fully isolated frozen installation above. Review regressions
for substituted adjustment sets, malformed HTE labels/DML bindings and missing
constant-effect declaration were observed failing before their fixes. No tolerance
was loosened to pass a test. Superpowers reviewer reports no remaining important issues.

## Reference comparisons

Independent fixture recovery tolerance remains 0.25; exact equality is not required.
Aggregates were recomputed in the clean optional installation:

| Fixture | Repository baseline | EconML adapter |
|---|---|---|
| Known ATE=2 | 2.041721 (SE 0.073282) | 2.041721 (SE 0.073282) |
| Null ATE=0 | 0.039938 (SE 0.073257) | 0.039938 (SE 0.073257) |
| Subgroups=1/3 | 0.821555 / 2.828993 | 0.823412 / 2.826243 |
| Heterogeneous direct contrast=2 | 2.007437 | 2.002830 |
| Homogeneous subgroups=2/2 | 1.823707 / 1.826034 | 1.824145 / 1.825520 |
| Homogeneous direct contrast=0 | 0.002327 | 0.001374 |

DML nearly coincides here because fixed nuisance/fold configurations align with the
baseline. This is not a universal equality guarantee. DR subgroup and baseline DML
interaction score formulations differ, as do nuisance transformations and potential
regularization/inference behavior. Known direction, null/homogeneous behavior, finite
uncertainty and shared estimand semantics are tested independently.

Remaining limitations: constant-effect ATE restriction; two registered binary HTE
groups only; i.i.d. HC1 asymptotic uncertainty; no bootstrap/cluster/survey/panel inference;
finite-sample nuisance/model misspecification; no exchangeability proof, overlap repair
or causal-validity guarantee; no personalized recommendations; other runtime/platforms
not exercised. The existing offline statistical baseline excludes advanced adapters,
which instead have their dedicated contract/reference suite. Full advanced-adapter
conformance hardening remains out of scope.
