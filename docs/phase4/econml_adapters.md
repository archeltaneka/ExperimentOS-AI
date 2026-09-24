# Optional EconML estimator adapters

Issue #104 adds exactly two explicitly selected computation adapters. Repository-owned
DML, HTE, randomized, IPW and DiD estimators remain supported authoritative baselines;
no default dispatch or public HTTP/workflow endpoint changes.

## Ownership and installation

ExperimentOS request → owned causal identification and execution contracts → owned
advanced estimator protocol → optional EconML computation → normalized owned result.
EconML does not replace ExperimentOS causal identification, prove exchangeability,
or solve poor overlap. Advanced estimator complexity is not evidence of causal validity.

EconML is optional because its compiled and explanatory-model dependency closure is
substantial. Following existing dependency-group conventions:

```sh
uv sync --group econml
# Development and full regression tests:
uv sync --group dev --group eval --group observability --group econml
```

The default development group excludes EconML. `uv sync` installs core without it.
Importing either adapter does not import EconML. A valid supported request without the
package produces abstention with `OPTIONAL_DEPENDENCY_UNAVAILABLE`. An installed package
that cannot import is an incompatible runtime, not optional absence; its conformance
failure blocks quality. Exceptions are normalized and cannot expose `ImportError`.
Unsupported declarations are rejected
before loading the optional implementation. Incompatible installed versions/runtime
produce `INCOMPATIBLE_DEPENDENCY_RUNTIME`; no dependency repair or downgrade occurs.

## Compatibility investigation

Context7 resolved `/py-why/econml`. Its documentation/source snippets include older
releases, so APIs and requirements were cross-checked against the versioned
[EconML 0.17.0 release source](https://github.com/py-why/EconML/tree/v0.17.0).
The package declares Python ≥3.9, classifiers through 3.14. ExperimentOS requires
Python ≥3.12. The adapter intentionally verifies Python 3.12–3.14; the optional group
has a Python <3.15 marker, preserving the wider core constraint.

The tested environment is Linux x86_64, Python 3.12.14, NumPy 2.5.0, SciPy 1.18.0,
scikit-learn 1.9.0. EconML 0.17.0 requires NumPy ≥2.0.2, SciPy ≥1.13.1,
scikit-learn ≥1.6,<1.10, statsmodels ≥0.14.4, SHAP ≥0.46, lightgbm ≥4.5,
numba ≥0.60, sparse ≥0.15.4, pandas ≥2.2.3, joblib ≥1.4.2 and packaging ≥24.2.
These constraints are compatible with the repository's current runtime and lock.
Resolution with every existing group retained changed zero existing package versions.
Statsmodels, SHAP and LightGBM are required upstream dependencies even though these
adapters do not call SHAP explanations or LightGBM models. Universal locking retains
platform-specific SHAP versions, including the upstream macOS Intel constraint.
Resolution is not runtime verification of other Python/platform combinations.

## Supported estimators and contracts

| Adapter | Computation | Owned request/result | Supported target |
|---|---|---|---|
| `EconMLDMLAdapter` | `econml.dml.LinearDML` | `DMLExecutionRequest` / `AdvancedCausalResult` | Full-population ATE, mean difference, explicit constant treatment effect |
| `EconMLHTEAdapter` | `econml.dr.LinearDRLearner` | `HTEExecutionRequest` / `HeterogeneousEffectResult` | Prespecified subgroup CATEs and their direct contrast |

Both require binary treatment encoded control=0, treated=1, scalar continuous outcome,
pre-treatment approved adjustment variables, stable observation identities and owned
identification assumptions. Multiple treatments/outcomes, continuous treatment,
ATT/ATC/overlap targets and individualized recommendations are unsupported.

LinearDML fits `Y,T,X=None,W=covariates`: its single effect maps to ATE only under the
explicitly asserted constant-effect partially linear restriction. Without that
restriction, heterogeneous effects and varying propensities can produce a
propensity-variance-weighted effect rather than full-population ATE. Declare it through
owned `AdvancedEstimatorConfig(constant_effect_assumption=True)` or the adapter's
`constant_effect_assumption=True` convenience argument. Default False fails closed.
The declaration is an assumption, not evidence that treatment effects are homogeneous.

LinearDRLearner fits `Y,T,X=registered_group_indicator,W=covariates`. It requires exactly
two exhaustive, prespecified, pre-treatment binary categorical groups, CATE estimand,
explicit identification method `doubly_robust_subgroup_effects`, and HTE analysis version
`hte-dr-v1`. The baseline `partialling_out_dml_subgroup_interactions` method is not
silently interpreted as DR. Both groups must meet existing treated/control sample
minima. Global and within-group overlap are checked on actual held-out predictions;
severe overlap abstains without subgroup effects or conclusive heterogeneity evidence.
This adapter does not expose row CATEs or personalized treatment policies.

## Inference and deterministic computation

Only owned inference mode `statsmodels_hc1` is supported. LinearDML uses explicit
`StatsModelsInference(cov_type="HC1")`; LinearDRLearner uses explicit
`StatsModelsInferenceDiscrete(cov_type="HC1")`. No `auto`, bootstrap, HC0, forest or
silent fallback is accepted. The narrower adapter scope does not wrap every inference
option supported by upstream estimators.

Both verified 0.17.0 estimator APIs accept upstream `auto`, `statsmodels`, `bootstrap`
and disabled inference (`None`); bootstrap requires explicit bootstrap configuration
for reproducibility. Both fit signatures are `fit(Y,T,*,X=None,W=None,...,inference='auto')`
and support random_state. LinearDRLearner requires discrete treatment; LinearDML is
explicitly configured with discrete_treatment=True. Any upstream options for other treatment/outcome shapes or weighting/grouping are
not exposed by these adapters.

Effects and intervals use documented `effect`, `effect_inference`, `effect_interval`
with T0=0,T1=1 and alpha=1-confidence_level. Standard errors, normal z statistics and
p-values come from the library inference object, then immediately become owned scalar
contracts. HTE uses X=[[0]] and [[1]] for group effects and `coef__inference(T=1)` for
the direct difference. Squared contrast z yields the one-degree-of-freedom Wald
chi-square statistic; Holm correction uses separate subgroup and reference-contrast
families. Intervals are marginal, not simultaneous multiplicity-adjusted intervals.
No standard error is reconstructed from interval endpoints or fabricated.

HC1 uses n/(n-final-design-rank) covariance correction and asymptotic normal inference.
It assumes independent observations and appropriate final effect specification;
clustered/panel, survey-weighted, repeated-unit uncertainty is outside this adapter.
DML nuisance consistency/product-rate and DR nuisance/inference regularity assumptions
remain necessary. Double robustness of point estimation does not by itself establish
valid confidence interval coverage. Finite uncertainty does not establish causal validity.

The existing seed controls explicit stable-ID stratified cross-fitting index splits,
EconML random_state and all nuisance-model seeds. Rows are canonically ordered before
fitting. Fixed scaled Ridge (SVD solver) and scaled logistic regression use owned alpha,
C, tolerance and iteration limit; no auto nuisance selection or tuning. The DR outcome
pipeline includes pairwise treatment/feature interactions. One Monte Carlo cross-fit,
no Ray, no missing values, no propensity clipping (`min_propensity=0`) or trimming.
Nonconvergence and numerical failure abstain. Identical supported runs reproduce within
the same runtime, including input-row permutation; cross-platform bitwise determinism
is not promised.

## Normalization, provenance and diagnostics

The advanced protocol exposes capabilities and `analyze(execution, table, provenance)`;
request models own estimand, treatment/outcome, feature/modifier declarations and seed.
Adapter configuration is a bounded owned model, not raw EconML constructor arguments.
HTE reuses existing result, sample, overlap, subgroup, interaction and multiplicity
contracts; there is no EconML-specific public HTE model.

Successful results retain adapter ID/version, EconML version/class, scalar constructor
configuration, inference mode, estimand/treatment/outcome, nuisance configuration,
ExperimentOS/random-state/nuisance seeds, fold fingerprint/count, actual nuisance-fit
reports, feature names/roles/timing, Python/platform and dependency versions. Source
identification/provenance remain available through owned execution/result contracts.
Fitted estimators, inference objects, sklearn models and exceptions are never serialized.

Failures normalize to dependency unavailable/incompatible, unsupported configuration,
invalid timing/modifier/data shape, fit/inference failure, non-finite estimate or
uncertainty, plus existing identification/sample/overlap diagnostic codes. Failed
inference suppresses the point estimate too. Safe messages exclude third-party exception
text and row data. Actual fitted nuisance models are used privately to audit held-out
predictions; proxy refits are not used for diagnostics.

Minimal `evaluate_advanced_quality` checks completed adapter identification, dependency
provenance, supported inference, deterministic seeds, finite required uncertainty and
overlap; HTE delegates existing safety checks too. The separate
[advanced-adapter conformance suite](advanced_causal_conformance.md) now exercises
these adapters through the canonical Phase 4 quality gate. Neither layer selects estimators.

Existing observability providers receive adapter/class/category, estimand, inference
mode, dependency availability where known, status, diagnostic codes and duration only.
Provider failures do not change statistical results. No X/Y/T vectors, CATE arrays,
nuisance predictions, unit IDs, fitted objects or row effects are emitted.

## Baseline comparisons and limitations

Shared independent deterministic fixtures test known ATE=2 and null ATE=0, heterogeneous
subgroups=1/3 and homogeneous subgroups=2/2. The existing baseline known-effect tolerance
of 0.25 is retained; expected direction, estimand compatibility and finite uncertainty
are checked independently, without exact equality between implementations.

EconML estimators may differ numerically from repository baselines because of nuisance
model regularization, feature transformations, seed handling, cross-fitting mechanics,
HC1 design-rank correction and score formulation. In particular DR subgroup estimation
is not the baseline partialling-out interaction estimator. Tests are finite-sample
reference checks, not coverage studies or evidence of exchangeability. Poor overlap,
unmeasured confounding and misspecified effect models remain statistical limitations.
