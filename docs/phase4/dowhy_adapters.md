# Optional DoWhy identification and refutation evidence

DoWhy 0.14 is an optional evidence adapter. It does not replace ExperimentOS causal contracts,
baseline estimators, graph validation, assumptions, abstention, policy, or decisions. Causal graphs
are supplied assumptions, not learned truth. Automated causal discovery is not supported.

## Runtime and installation

The verified adapter runtime is Python 3.13 with `uv sync --group dowhy`. Python 3.12 remains a
supported core runtime, but DoWhy 0.14 conflicts with the core SciPy floor there; requests return
`INCOMPATIBLE_DEPENDENCY_RUNTIME`. DoWhy is never imported by baseline causal modules.

## Supported surface

The adapter requires an explicit owned DAG with observed/latent node declarations. It supports
binary 0/1 treatment, continuous outcome, full-population mean-difference ATE, default backdoor
identification, and one `backdoor.linear_regression` handoff. Canonical sorted graph semantics are
hashed with SHA-256; provenance is recorded separately.

Successful identification means that the effect is identifiable conditional on the supplied graph
and its encoded assumptions. It does not establish graph truth, exchangeability, or absence of
unmeasured confounding. A missing backdoor estimand abstains without an adjustment set or estimate.

## Refuters

Supported refuters are permuted placebo treatment, random common cause, and data subset. Every run
records its seed, simulation count, subset fraction where relevant, original/new estimate, delta,
status, graph fingerprint, and runtime provenance. Each refuter tests a specific perturbation.
A stable or passed refuter does not prove causal validity. It provides evidence only about the
configured perturbation.

## Determinism, privacy, and limitations

Stochastic calls receive an explicit seed, fixed simulation count, and `n_jobs=1`. Same-runtime
repeated executions must produce equivalent normalized results. DoWhy/NetworkX objects and raw
exceptions remain private. Telemetry contains statuses, methods, diagnostic codes, graph counts,
and duration—not graph labels/text, rows, treatment/outcome values, covariates, IDs, or samples.

Unsupported estimands, malformed/cyclic graphs, descendant adjustment, absent/incompatible
dependencies, unavailable identification, non-finite estimates, and third-party failures are
distinct owned outcomes. Refuters are diagnostic perturbations, not sensitivity analyses covering
all possible unmeasured confounding.
