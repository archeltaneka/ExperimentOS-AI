# Deterministic Descriptive Statistics

## Boundary

`DescriptiveStatisticsService` is the ExperimentOS-owned Phase 4 numerical foundation. It consumes immutable `DescriptiveStatisticsInput` containing validation context and eligibility evidence, requires data eligibility but not estimator availability, reuses eligibility-owned bindings and population selection, does not mutate source rows, and rejects unsafe validated states with `DescriptiveStatisticsInvariantError`.

It returns typed `DescriptiveStatisticsResult`, never a third-party result. Canonical JSON is key-sorted and deterministic. Ordering is fixed or declared: population, treatment, control; requested covariates; selected segment; pre then post periods.

## Metrics and numerical conventions

Continuous and rate metrics use `ContinuousSummary`; binary and proportion metrics use `BinarySummary`; count metrics use `CountSummary`. Ratio metrics remain explicitly unavailable until contracts distinguish ratio of sums from mean of per-unit ratios and state denominator policy. These quantities are not interchangeable, and zero denominators are never divided by.

For finite values \(x_1, \ldots, x_n\), mean is \(\sum_i x_i/n\), sample variance is \(\sum_i (x_i-\bar{x})^2/(n-1)\), and standard error is \(s/\sqrt{n}\). The degrees-of-freedom convention is one. Variance and standard error are unavailable, not zero, below two valid values. Default 0.25, 0.50, and 0.75 quantiles use sorted linear interpolation. One-observation continuous summaries retain location values without variance.

Binary observations accept explicit numeric 0 and 1 only, never Python truthiness. Observed rate is successes divided by valid observations, with binary-observation sample variance and standard error where defined. Count metrics reject negative values. Non-finite input is rejected, and typed output models prevent `NaN` and infinity in canonical JSON. Values are never rounded internally; presentation owns rounding.

## Units, missingness, and raw comparisons

Population, treatment, and control summaries report row counts, unique analysis-unit counts, valid outcomes, and missing outcomes. Declared unit semantics are respected; unresolved repeated rows are rejected rather than collapsed. Clustering metadata is preserved for later estimators and no clustered uncertainty is calculated.

Missing outcomes are counted before valid summaries. No imputation, zero replacement, or silent removal occurs. All-missing populations have unavailable summaries, and complete-valid-observation summaries make no unbiasedness claim.

Comparisons are `raw_unadjusted`: treatment summary minus control summary. Relative difference is `(treatment - control) / control` only for a non-zero baseline. Control `[1, 3]` and treatment `[5, 7]` produce means 2 and 6, absolute raw difference 4, and relative difference 2. Binary control `[0, 1]` and treatment `[1, 1]` produce observed rates 0.5 and 1.0. With zero control and treatment 1.0, absolute difference is 1.0 and relative difference is explicitly unavailable. These values are not causal effects.

## Covariates, segments, periods, diagnostics, and provenance

Only declared pre-treatment numeric covariates are summarized in request order. Categorical output remains unavailable until contracts define category and truncation semantics. Only the validated selected segment is summarized; its small-arm warning is preserved and it is never ranked. Validated quasi-experimental requests produce ordered pre and post summaries without Difference-in-Differences or parallel-trends testing.

Fixed-order diagnostics describe all-missing outcomes, sparse samples, zero variance, and missingness at the existing validation-policy limit. They are not tests. Result identity, direction, configuration, typed subtype, and counts are recorded. Source and eligibility provenance remain the immutable context supplied at the service boundary; raw data are never copied into results or provenance.

## Observability and limitations

The service uses only `BaseObservabilityProvider` and opens one `descriptive_statistics` root span. It records low-cardinality row count, metric type, group/segment counts, status, warning count, unavailable-comparison count, duration, and numeric-safety failure state. It never records rows, units, columns, segment values, or raw payload values. Provider start, lifecycle, and export failures are isolated from the authoritative result.

Golden fixtures cover balanced/unbalanced continuous, binary, count, missing/all-missing, one value, zero variance, zero baseline, non-finite rejection, segment, period, ordering, and canonical serialization. Structured fields use intentional numerical tolerances where harmless floating-point representation differences can occur.

No hypothesis testing, p-values, treatment-effect confidence intervals, significance inference, causal conclusion, rollout decision, business-impact calculation, CUPED, sequential or Bayesian inference, Difference-in-Differences, propensity methods, matching, weighting, adjustment, Double Machine Learning, heterogeneous treatment effects, EconML, DoWhy, LLM interpretation, public API change, LangGraph routing, persistence, charting, automatic segmentation, live LLM call, or external statistical service is implemented.
