# Causal Identification Contracts

## Purpose

ExperimentOS requires observational analyses to declare a supported causal-identification path
before a future estimator can run. The contracts are immutable, versioned, deterministic, and
owned by `packages.experiments.analysis.causal`.

## Identification vs estimation

Identification asks whether the declared design, variables, timing, adjustment information, and
assumptions provide a coherent path to a future causal estimator. Estimation would calculate a
numerical effect after identification and data eligibility checks. This issue implements only the
first step.

Identified does not mean causality proven. It means the declared design and assumptions provide a
supported identification path for a future estimator. An asserted assumption remains an assertion,
not empirical proof.

## Observational request boundary

`ObservationalAnalysisRequest` contains a request identity and a mandatory
`CausalIdentificationRequest`. This new boundary coexists with the legacy general
`AnalysisRequest`, preserving every randomized, CUPED, sequential, and Bayesian payload. Future
observational execution contracts must consume this identification envelope rather than bypass it.

## Estimands

Every request declares exactly what a future effect would mean:

- **ATE** targets the average treatment effect in the full declared population.
- **ATT** targets the average treatment effect for the treated population and is never mapped to
  ATE.
- **Difference-in-Differences ATT** targets the treated group under explicit pre/post and comparison
  semantics.
- **CATE** targets a conditional average treatment effect under explicit effect modifiers and a
  conditioning definition.

Each estimand contains a treatment/control contrast, target population, outcome variable, effect
scale, and provenance.

## Variable roles

Variables use typed roles: treatment, outcome, adjustment, effect modifier, identifier, time,
clustering, segmentation, post-treatment, or unknown. Treatment, outcome, identifier, and
post-treatment roles cannot be used for adjustment. Adjustment plus effect modifier is the only
explicitly supported dual causal role, and both meanings remain visible.

## Measurement timing

Every variable records pre-treatment, at-treatment, post-treatment, time-invariant, or unknown
timing, along with a reference period or timestamp, relationship to treatment start, and evidence
provenance. ExperimentOS does not infer timing from column names, correlations, or values.

## Adjustment sets

An adjustment set is supplied explicitly with selected variable IDs, purpose, estimand, source,
validation status, diagnostics, and provenance. ExperimentOS checks membership, roles, timing,
duplicates, and leakage. It performs no automatic confounder discovery or adjustment-set selection.

## Causal graph

The owned causal graph consists of variable-backed nodes and directed cause-to-effect edges. It
rejects unknown nodes and variables, duplicate edges, self-loops, and cycles when DAG semantics are
declared. It does not expose NetworkX or DoWhy objects and does not perform graph discovery, DAG
completion, or adjustment sufficiency proofs.

## Assumptions

Typed assumptions cover consistency, interference limitation, exchangeability, positivity,
temporal ordering, parallel trends, no anticipation, stable treatment definition, and stable
unit/population definition. Statuses distinguish asserted, supported by diagnostics, violated,
unverified, and not applicable. Exchangeability is not fully testable from observed data. Balance
diagnostics cannot prove no unmeasured confounding, and the presence of both treatment groups does
not establish positivity.

## Identification statuses

- `identified`: supported design and estimand with coherent roles, timing, identification input, and
  all required assumptions declared.
- `partially_identified`: meaningful structure exists, but required declared assumptions remain
  unresolved.
- `invalid`: contradictions, leakage, impossible timing, violated assumptions, or malformed graph
  structure make the request unsafe.
- `insufficient_evidence`: coherent input is missing an estimand, adjustment information, required
  assumptions, or another required declaration.
- `unsupported`: the declared design or estimand is outside the current contract scope.

Every non-identified result carries a typed abstention reason. None carries an estimate.

## Evidence limitations

Limitations are structured records rather than report-only prose. Results retain that
exchangeability is asserted rather than proven, unmeasured confounding remains possible, overlap is
not evaluated, parallel trends are unverified, no sensitivity analysis was run, an adjustment set
was not graph-validated, or a graph was user supplied.

## Post-treatment leakage

Post-treatment adjustment is blocking. Treatment and outcome leakage, identifier misuse,
post-treatment roles, explicitly post-treatment derived variables, and unknown timing are also
blocking. The validator uses declarations only and does not guess leakage from names.

## Difference-in-Differences

The structural DiD foundation declares treated and comparison groups, treatment time, pre-period,
post-period, analysis and observation units, DiD ATT, parallel trends, no anticipation, and stable
treatment adoption. It does not calculate DiD or test parallel trends.

## Heterogeneous effects

The HTE foundation requires a CATE estimand, target population, conditioning definition, explicit
pre-treatment effect modifiers, adjustment information, assumptions, and timing. It does not
discover subgroups, calculate heterogeneous effects, or make individualized treatment decisions.

## Serialization and observability

Semantically unordered fields are canonicalized before sorted-key JSON serialization. Dedicated
request and result adapters provide round trips. Optional telemetry contains only controlled design,
estimand, status, aggregate counts, assumption codes, diagnostic codes, abstention state, and
duration. It excludes raw values and full graph contents.

## Third-party independence

Public contracts contain only Python, Pydantic, and ExperimentOS-owned types. No DoWhy or EconML
dependency is introduced. No NetworkX graph, statsmodels result, scikit-learn estimator, or
third-party exception crosses the domain boundary.

## Limitations

No causal effects are computed. No propensity scores are fit. No graph discovery is performed.
No DoWhy or EconML dependency is introduced. There is no matching, weighting calculation, DiD
calculation, DML, HTE estimation, causal forest, sensitivity analysis, business-impact calculation,
workflow integration, database access, network service, or live LLM functionality.
