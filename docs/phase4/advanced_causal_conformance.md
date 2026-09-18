# Advanced causal conformance

Issue #106 extends the existing Phase 4 statistical reliability baseline. It does
not add estimators, estimator selection, workflow integration, or a second policy
engine. Conformance asks whether an implementation satisfies the ExperimentOS
behavioral contract for its capability, not whether every estimator returns the
same number.

## Architecture

The existing reference dataset loads `data/eval/phase4_advanced_conformance.json`
in stable case-ID order. The deterministic registry in
`packages/evals/statistical/advanced/registry.py` routes each case through the
public estimator/adapter, then inspects the original ExperimentOS-owned result
before serialization. Ordinary `StatisticalCheck` and `StatisticalCaseResult`
records feed the existing centralized quality policy and JSON/Markdown renderer.

Three layers remain separate:

1. Common interface checks: recursive ownership, schema, status, diagnostics,
   configuration provenance, seeded replay, normalized failures, and telemetry.
2. Capability-specific checks: applicable statistical evidence and independent
   known-fixture plausibility.
3. Cross-estimator comparisons: advisory comparisons only after explicit causal
   compatibility checks. They do not replace independent reference checks.

## Capability registry and uncertainty

| Capability ID | Existing implementation | Uncertainty |
| --- | --- | --- |
| `repository_dml` | Repository cross-fitted partially linear DML | Required |
| `repository_hte` | Repository pre-specified orthogonal subgroup interactions | Required per completed subgroup |
| `econml_dml` | Existing EconML LinearDML adapter | Required |
| `econml_hte` | Existing EconML linear DR subgroup adapter | Required per completed subgroup |
| `dowhy_identification` | Explicit-graph default backdoor identification | Not applicable |
| `dowhy_estimation` | Existing backdoor linear-regression handoff | Optional; adapter explicitly does not support intervals |
| `dowhy_placebo` | Existing placebo-treatment refuter | Not applicable |
| `dowhy_common_cause` | Existing random-common-cause refuter | Not applicable |
| `dowhy_subset` | Existing data-subset refuter | Not applicable |

Entries record method, adapter/version, implementation identifier, estimand,
supported continuous outcome/binary treatment, dependency, seed support, and
applicable checks. Runtime case details record the configuration fingerprint and
installed dependency version. Identification and refutation are not primary
treatment-effect estimators and are not required to fabricate confidence intervals.

Required uncertainty means finite standard error, ordered finite interval
containing the estimate, confidence level, and inference method. Unsupported
inference must explicitly refuse; silent fallback or successful fabricated
uncertainty blocks the gate.

## Fixtures and method-specific checks

Shared builders under `statistical/advanced/references` are promoted from the
existing DML, HTE, EconML, and DoWhy tests; test imports reuse these builders.
Small deterministic fixtures include known effects, null effects, homogeneous
and heterogeneous pre-specified subgroups, explicit backdoor graphs, and the
three already-supported seeded refuters.

DML checks cross-fitting, fold fingerprint/seed, validated fold assignments and
train/score counts, observed nuisance fit/predict input disjointness, nuisance provenance, residual evidence, overlap, estimate,
uncertainty, and degenerate-residual abstention. HTE checks pre-treatment
modifiers, assignment fingerprint and subgroup counts, subgroup uncertainty,
Holm multiplicity, capability quality, sparse groups, and overlap refusal.
DoWhy checks graph fingerprint, normalized identification, adjustment set,
conditional interpretation, refuter identity/seed, and observed estimate change.

Purpose-built scoped failure doubles exercise nuisance fitting, external fitting,
inference, malformed/nonfinite outputs, graph contradictions, no identification,
estimation handoff, refuters, and absent dependencies. They do not rely on random
optimizer failures. Real success/replay paths run installed supported adapters.

## Comparison and tolerance rules

Before numeric comparison, both sides must supply matching estimand, treatment
contrast, target population, outcome, adjustment covariates, identification
assumptions, fixture/DGP, and subgroup definition where relevant. Missing or
incompatible evidence yields `SKIPPED` with `NOT_APPLICABLE`, not a numerical
failure. Compatible divergence is advisory; each estimator must independently
pass its own fixture's blocking plausibility checks.

Statistical tolerances live with reference metrics in the JSON dataset and carry
an absolute bound, optional relative bound, rationale, and provenance. Replay and
cross-estimator tolerance specifications live centrally in `advanced/checks.py`.
Replay uses exact structure/categories and a documented absolute floating-point
roundoff bound of `1e-10` in the same dependency environment. Statistical bounds
are not defined in CI YAML. Seeds are explicit and recorded; changing a seed
must change configuration provenance, but need not change the estimate.

## Configuration provenance

The shared configuration digest uses canonical sorted compact JSON and SHA-256,
rejecting NaN/infinity. It includes bounded execution configuration, adapter ID
and version, method/estimand, seed/fold count, inference/refuter settings, supplied
nuisance configuration digests, and safe graph/modifier/binding digest references.
Row-level input tables, outcomes, features, predictions, and fitted objects are
not inputs. Public success and refusal results carry the digest. Package versions
are reported separately rather than silently comparing different environments.

## Status and dependency semantics

Native estimator status and reliability verdict are distinct. The advanced
details retain `successful`, `invalid`, `abstained`, `failed`, and `unavailable`
execution semantics; individual checks can be `skipped` or `advisory`. Reports
preserve these dimensions instead of flattening everything into success/failure.
Expected abstention or a correctly normalized injected failure passes conformance.
Incorrect success is blocking.

Missing top-level EconML/DoWhy distributions are unavailable, normally advisory;
repository DML/HTE continue. Installed packages with incompatible runtimes,
transitive/import failures, malformed outputs, object leaks, or contract failures
are not reclassified as absent. Controlled missing-dependency probes are labeled
separately from genuine environment availability.

## Privacy, failure normalization, and policy

Original public results are recursively inspected, including nested containers,
model extras, and private model attributes. Third-party estimators/inference/
DoWhy objects, raw exceptions, cyclic objects, and nonfinite scalars cannot cross
the conformance boundary. Failure artifacts use safe stable diagnostics, never
exception representations or raw model dumps.

Recorded telemetry is inspected recursively in both keys and values, with
per-key types/shapes, closed categories, and a reviewed diagnostic-code inventory.
Unknown diagnostic strings block and are withheld from artifacts. Allowed
metadata includes bounded adapter identity/version, method, digest, dependency
state/version, status, diagnostics, counts, and duration. Raw graph text, domain
node names, unit IDs, row outcomes/treatments/CATE, feature values, coefficients,
propensity/nuisance predictions, residual arrays, membership, and estimator
objects must not be standard telemetry. Graph digests/counts are permitted.

Existing centralized policy dimensions cover uncertainty, determinism, status,
provenance, reference accuracy, and privacy. Added critical dimensions cover
interface leakage, unnormalized exceptions, unsupported inference acceptance,
data leakage, and dependency failures. Blocking findings dominate advisory
findings. Optional absence, limited evidence, and compatible reference divergence
remain advisory when not accompanied by a blocking violation.

## Command, artifacts, and CI

The canonical offline command remains:

```sh
uv run python -m packages.evals.cli statistical-baseline
```

JSON remains authoritative. Existing case records add typed `advanced` details
(suite version, capability, adapter/version, dependency state/version, seed,
fingerprint, native/semantic status, uncertainty support, execution kind), plus
ordinary checks, findings, skipped reasons, and measured duration. The Markdown
`Advanced Causal Conformance` section renders those same structured records and
distinguishes real execution from injected controlled scenarios; it
does not rerun estimators. Artifacts contain safe aggregate reference checks, not
raw fitted models or row-level outputs. Measured duration is not deterministic
and is excluded from repeatability assertions.

The core CI job runs repository and absent-dependency conformance. One additional
Python 3.13 job installs the existing locked `econml` and `dowhy` groups, runs
adapter tests, and uses the same command with:

```sh
uv run --no-sync python -m packages.evals.cli statistical-baseline \
  --require-optional econml --require-optional dowhy
```

Required mode blocks genuine absence in the optional environment. Both CI paths
feed the existing gate; installation occurs during environment setup only.
Conformance execution uses no network, database, live LLM, hosted tracking, or
telemetry exporter.

## Limits

Conformance does not prove an estimator is correct for every dataset.
Cross-library agreement does not prove causal validity. Comparisons are meaningful
only when estimands and assumptions align. Small fixed fixtures are contract
checks, not production-scale benchmarks or universal statistical calibration.
Optional absence is different from installed-but-broken behavior. Third-party
upstream warnings can remain visible without changing these guarantees.
