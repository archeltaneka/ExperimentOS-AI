# Pre-registered sequential testing

ExperimentOS supports deterministic offline monitoring of eligible two-arm randomized experiments
at discrete, pre-registered analysis looks. Sequential monitoring prevents the common error of
repeatedly applying a fixed-horizon `p < 0.05` rule: every extra uncorrected opportunity to reject
increases the experiment-wide false-positive probability.

V1 is intentionally narrow. It supports one primary continuous or binary outcome, fixed treatment
and control definitions, cumulative eligible data, two-sided efficacy testing, and one boundary
method. It does not implement futility, adaptive allocation, sample-size re-estimation, continuous
monitoring, always-valid inference, Bayesian monitoring, observational analysis, sequential CUPED,
automatic experiment stopping, rollout decisions, business-impact logic, persistence, LangGraph,
or live services.

## Registered plan

`SequentialAnalysisPlan` is a frozen ExperimentOS contract. It records:

- a plan and optional experiment identity;
- the complete randomized analysis request, including the primary outcome, estimand,
  treatment/control definitions, analysis unit, and randomization unit;
- total experiment alpha and two-sided testing;
- the boundary method and method version;
- consecutive planned look indexes and strictly increasing information times;
- optional cumulative planned sample counts at every look;
- a logical registration marker, optional timezone-aware registration time, and provenance; and
- a deterministic SHA-256 fingerprint.

Information time is the pre-declared fraction of final statistical information, not an arbitrary
wall-clock percentage. Each value must lie in `(0, 1]`; the final value must equal `1` within an
absolute tolerance of `1e-12`. V1 does not estimate information time from observed effects or add
looks dynamically.

The plan must exist before the first look. ExperimentOS records registration evidence explicitly;
it does not infer honest preregistration from data. If a supplied execution time precedes the plan's
registration time, the history is invalid.

## Fingerprint

The fingerprint is lowercase SHA-256 over compact, key-sorted canonical JSON. It includes the
complete statistical request, total alpha, sidedness, method/version, ordered look indexes and
information times, optional planned cumulative counts, and analysis/randomization-unit semantics.
Plan IDs, registration markers/timestamps, and provenance presentation order are excluded because
they do not alter the statistical design.

The service recomputes the fingerprint before boundary generation. This catches even an in-memory
plan copy that bypassed normal contract revalidation. A changed outcome, treatment, control,
estimand, unit, method, alpha, or schedule cannot inherit the old plan's conclusive result.

## Boundary method and alpha spending

V1 uses an **O'Brien-Fleming-shaped weighted Bonferroni alpha-spending method**. It is conservative
and is not the exact canonical joint-normal O'Brien-Fleming design.

For total two-sided alpha `alpha`, information time `t`, standard-normal CDF `Phi`, and
`c = Phi^-1(1 - alpha/2)`, planned cumulative spending is:

```text
A(t) = 2 * [1 - Phi(c / sqrt(t))]
```

At look `i`:

```text
nominal_alpha_i = A(t_i) - A(t_(i-1)), with A(0) = 0
boundary_i      = Phi^-1(1 - nominal_alpha_i / 2)
```

The final cumulative spending is deterministically clamped to total alpha to remove floating-point
tail drift. Incremental budgets therefore sum to total alpha. Rejecting at look `i` has null
probability at most `nominal_alpha_i`; the union bound controls the probability of one or more false
efficacy declarations by the sum of those budgets, total `alpha`, regardless of correlation among
looks. This is why the procedure is valid but more conservative than exact correlated
group-sequential calibration.

SciPy 1.16+ supplies standard-normal survival and inverse-survival functions. No statsmodels or new
sequential-analysis dependency is used. If an extremely early tail underflows to zero, ExperimentOS
reports zero representable spending and the finite O'Brien-Fleming-shaped boundary `c/sqrt(t)`;
that zero-budget look is explicitly ineligible to cross, preserving the alpha-accounting proof;
NaN and infinity are never serialized.

## Cumulative execution

`SequentialAnalysisService.analyze()` accepts the complete ordered execution history. Every
`SequentialLookExecution` contains one immutable cumulative `AnalysisTable`, its role binding,
declared look index/information time, plan fingerprint, analysis request, and optional execution
time. It does not accept incremental-only rows.

For every valid later look:

- total, treatment, and control eligible counts cannot decrease;
- all previously observed unit identifiers must remain present;
- treatment assignments cannot switch;
- previously observed outcomes cannot change;
- physical analysis-role bindings cannot change; and
- execution times, when supplied, remain chronological.

Unit identifiers, outcomes, tables, and row-level assignments are inspected transiently and are not
stored in the history result.

Each valid look delegates effect estimation to the existing `RandomizedAnalysisService`. Continuous
outcomes retain Welch estimates and binary outcomes retain the two-proportion z estimator. The
ordinary effect, standard error, confidence interval, statistic, and p-value remain available inside
`look_level_analysis` as context.

The ordinary p-value is not the sequential stopping rule. ExperimentOS converts its calibrated
two-sided p-value to a signed normal-equivalent monitoring score:

```text
Z_i = sign(effect_i) * Phi^-1(1 - p_i/2)
```

Efficacy is crossed only when `nominal_alpha_i > 0` and `abs(Z_i) >= boundary_i`. This retains the existing Welch t-tail
calibration for continuous outcomes and the existing normal calibration for binary outcomes while
applying the pre-registered sequential alpha budget.

## Status and deviations

Statuses are:

- `efficacy`: the registered statistical boundary permits rejection of the null;
- `continue`: no registered efficacy boundary has been crossed, including final no-rejection;
- `abstain`: the underlying randomized estimator could not produce valid evidence; and
- `invalid`: plan integrity failed and no conclusive sequential decision is allowed.

`efficacy` means statistically eligible to stop for efficacy. It never means ship, launch, profit,
or automatically stop an experiment. `continue` at the final look means no rejection, not no effect.
Futility is unsupported in v1.

Stable deviation codes include unplanned, duplicate, skipped, information-time mismatch,
fingerprint mutation, changed outcome/metric/treatment/control/estimand/unit/configuration/binding,
non-monotonic counts, missing cumulative units, changed assignments/outcomes, contradictory
chronology, and evaluation after efficacy. A skipped planned look is not silently removed. A
duplicate look is not added twice and does not spend alpha twice.

## Worked four-look example

For total two-sided alpha `0.05` and registered information times 25%, 50%, 75%, and 100%, the
method produces:

| Look | Information time | Cumulative alpha | Incremental alpha | Boundary | Example score | Status |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 0.25 | 0.0000885754 | 0.0000885754 | 3.919928 | 0.40 | continue |
| 2 | 0.50 | 0.0055745967 | 0.0054860212 | 2.777018 | 1.20 | continue |
| 3 | 0.75 | 0.0236251213 | 0.0180505246 | 2.364580 | 2.00 | continue |
| 4 | 1.00 | 0.0500000000 | 0.0263748787 | 2.220647 | 2.30 | efficacy |

The example scores are illustrative sequential monitoring scores. Applying `p < 0.05` independently
at each row would not be a valid replacement.

## Audit and observability

`SequentialAnalysisHistory` retains frozen plan audit metadata, the complete planned boundary
schedule, ordered duplicate-free valid look results, current status, plan integrity, alpha summary,
deviations, first/latest look metadata, assumptions, warnings, and provenance. Canonical
serialization is deterministic and rejects non-finite numbers. Invalid supplied plan state is kept
as an audit snapshot without being relabeled as a validated plan.

Minimal observability uses the existing provider abstraction and records only method, boundary
family, look index, an interim/final information-time bucket, status, boundary crossing, integrity,
diagnostic codes/count, and duration. It excludes plan IDs, raw outcomes, rows, identifiers,
covariates, and credentials. Provider failures do not alter analysis results.
