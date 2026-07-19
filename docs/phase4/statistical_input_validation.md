# Statistical Input Validation and Eligibility

## Scope

Phase 4 provides deterministic pre-estimator validation through
`packages.experiments.analysis.validation`. It accepts an immutable `AnalysisRequest`, an
`AnalysisTable` snapshot, an `AnalysisDataBinding`, an explicit `ValidationPolicy`, and a
`MethodCapabilityRegistry`. It returns an immutable `EligibilityValidationResult`; it does not
calculate an estimate, alter data, select a model, or run an estimator.

`AnalysisEligibilityService` is the orchestration boundary. Focused validators own request
consistency, dataset eligibility, and design integrity. Their dependency direction is domain
contracts and immutable validation inputs -> focused rules -> service aggregation -> a typed
result. The package has no FastAPI or vendor SDK dependency and is not integrated into `POST /ask`,
agents, workflows, persistence, or migrations.

## Structural validation versus dataset eligibility

These are deliberately separate decisions:

- Structural request validation is performed by the existing strict Pydantic `AnalysisRequest`
  contract. `validate_payload()` converts only a Pydantic `ValidationError` into the blocking
  `request.contract_invalid` diagnostic. Rejected values are not copied into diagnostic context.
- Dataset eligibility evaluates a structurally valid request against the immutable table and its
  analytical-role binding. Expected problems become deterministic diagnostics and summaries.
- Method support is independent again: a method can be contract-supported and the data can be
  eligible while its implementation remains unavailable.

Unreadable schema errors (`schema.duplicate_column`, `schema.empty_dataset`, or
`schema.required_column_missing`) prevent data-dependent design checks. The result then includes
the informational `schema.dependent_rules_unavailable` diagnostic instead of guessing at unit,
time, or segment integrity.

## Result schema and status precedence

Every result has `outcome_type: "eligibility_validation"` and `validation_version: "1"`, plus the
requested method/design, ordered diagnostics, exact blocking and warning subsets, dataset and
design summaries, method support, policy provenance, and an optional abstention reason. It never
has an `estimate` field.

Status aggregation uses this exact precedence:

1. Any `blocking` disposition -> `ineligible`.
2. Otherwise, any `needs_more_data` disposition -> `needs_more_data`.
3. Otherwise, any `warning` disposition -> `eligible_with_warnings`.
4. Otherwise -> `eligible`.

`blocking_diagnostics` is exactly the ordered subset with disposition `blocking`; `warnings` is
exactly the ordered subset with disposition `warning`. A diagnostic with severity `warning` and
disposition `needs_more_data` is therefore not copied into `warnings`. Only `ineligible` and
`needs_more_data` carry an `abstention_reason`; its primary code is the first diagnostic at the
winning disposition and its `missing_or_invalid_information` lists all blocking/needs-data codes in
first-seen order.

Diagnostics are emitted in fixed request/capability, data, dependency, then design-rule order.
Context entries are sorted by normalized key, so identical inputs produce identical result JSON.

## Estimator implementation availability

`method_support` records four different facts:

- `contract_status`: `supported` or `unsupported` describes recognition by the Phase 4 contracts.
- `implementation_status`: `available` or `unavailable` describes the injected capability
  registry, not discovery of a callable estimator.
- `data_eligible` is false for non-capability blocking or needs-data diagnostics; capability-only
  codes do not make the dataset itself ineligible.
- `executable` is the conjunction of contract-supported, implementation-available, and
  data-eligible. It is a gate value only; validation still does not invoke or prove an estimator.

The default registry inventories every current randomized, quasi-experimental, and observational
contract method as `supported` and `unavailable`. Consequently, a structurally valid, otherwise
eligible request passed to the default service is `ineligible` with
`method.implementation_unavailable`, while `method_support.data_eligible` remains `true`. The first
four examples below deliberately inject the golden-case registry declaration `available` to isolate
data-eligibility behavior. This repository still supplies no estimator implementation, and none of
the examples claims that an estimator was run.

## Validation coverage

Focused request rules check metric/estimand and CATE/segment compatibility, method prerequisites,
duplicate declarations, analytical-role conflicts, covariate timing and treatment relationships,
and unit, randomization, clustering, and physical-binding consistency.

Data rules check duplicate/empty/missing schema, explicit population selection, exact typed
treatment/control values, missing or unexpected assignments, absent arms, numeric and finite
outcomes, binary/count/bounds/ratio constraints, zero variation, configured missingness limits,
usable total and per-arm counts, and declared allocation deviation. Missingness summaries are
reported for each bound analytical role; outcome and differential missingness become blocking only
when their corresponding optional policy thresholds are configured.

Design rules check observation, randomization, and clustering identifiers; duplicate or repeated
units; treatment switching and conflicting assignments; required cluster counts; timestamp parsing,
declared period coverage, per-unit treatment timing, covariate data/period availability, and segment
column/type/cardinality/arm/sample eligibility. Repeated observations require compatible clustering.

### Post-treatment leakage

`covariate.post_treatment_leakage` is always blocking for a causal-adjustment covariate declared
`post_treatment`. The validator also blocks unknown timing, a declared pre-treatment measurement
period extending after treatment starts, treatment-derived/proxy relationships, and unknown
treatment relationships. These checks prevent unsafe adjustment; they do not establish causal
identification when they pass.

### Caller-data immutability

`AnalysisTable.from_records()` snapshots caller-owned mappings into frozen ordered columns and
rows. Validators derive row-index sets and summaries without filtering, imputing, coercing,
winsorizing, relabeling, or otherwise mutating the table, request, binding, or original records.
Invalid or missing rows remain represented by counts and diagnostics.

## Operational thresholds are not statistical power

`ValidationPolicy()` uses explicit deterministic operational defaults:

| Field | Default |
| --- | ---: |
| `policy_version` | `analysis-validation-v1` |
| `minimum_total` | `30` |
| `minimum_per_arm` | `10` |
| `weak_total` | `100` |
| `weak_per_arm` | `30` |
| `minimum_per_segment_arm` | `5` |
| `minimum_clusters` | `4` |
| `weak_clusters` | `20` |
| `allocation_warning_deviation` | `0.10` |
| `allocation_blocking_deviation` | `0.25` |
| `maximum_segment_cardinality` | `50` |
| `maximum_outcome_missingness` | `null` (disabled) |
| `maximum_differential_missingness` | `null` (disabled) |

These defaults are guardrails, not minimum-detectable-effect calculations, power guarantees,
causal-validity claims, or substitutes for study-specific planning. Callers may inject a validated
policy and should supply a meaningful `configuration_provenance`. The service default is the
literal `"explicit defaults"`; policy defaults do not read ambient environment variables. Each
result repeats `policy_version` and `configuration_provenance` so downstream decisions retain their
operational provenance.

## Diagnostic-code stability

Consumers should branch on typed status, disposition, category, and machine-readable code, not on
human `message` text. Codes are stable identifiers within validation version `1`; messages may be
clarified without changing semantics. Current stable code families are:

- `request.*`: invalid payloads and request-level compatibility/role conflicts.
- `schema.*`: table readability, required columns, numeric types, and unavailable dependent rules.
- `population.*` and `treatment.*`: population selection and assignment/arm/timing integrity.
- `outcome.*` and `missingness.*`: outcome domain/variation and configured missingness limits.
- `sample.*` and `allocation.*`: operational minimum/advisory counts and allocation deviation.
- `unit.*`, `covariate.*`, `time.*`, and `segment.*`: design-integrity evidence.
- `method.*`: method prerequisites, contract support, and implementation availability.

Categories are `request`, `schema`, `population`, `treatment`, `outcome`, `unit`, `covariate`,
`missingness`, `sample`, `allocation`, `time`, `segment`, and `method`. Dispositions are `blocking`,
`needs_more_data`, `warning`, and `informational`; outcomes are `passed`, `failed`, and
`unavailable`; severities are `info`, `warning`, `error`, and `fatal`.

## Observability and data safety

Validation emits one logical `analysis_validation` root span, or a child span only when a parent
owned by the same provider is active. The default provider is `NoOpObservabilityProvider`.
Observability start/completion/export failures are isolated from the authoritative result.

Inputs contain only `row_count` and `column_count`. Safe metadata contains method, design, status,
blocking/warning counts, duration, needs-data and method-unavailable flags, validation lifecycle
flags, and sanitized failure stage/type. Outputs contain only status and completion. Raw rows,
column names, bindings, identifiers, treatment/control values, outcomes, covariates, segments, and
exception messages are excluded. Unexpected validator failures are recorded generically and then
re-raised unchanged.

## Payload boundary and exceptions

Use `validate(request, table, binding)` when the caller already has a valid `AnalysisRequest`. Use
`validate_payload(payload, table, binding)` at an untrusted request boundary. Only request-model
`ValidationError` becomes `request.contract_invalid`; malformed `AnalysisTable` and binding/policy
construction still raise their owned `AnalysisTableError`/Pydantic validation exceptions.
Capability-registry omissions raise `LookupError`, invalid registry declarations raise
`ValueError`/`TypeError`, and unexpected validator/programmer failures are re-raised. Expected data
ineligibility is returned as a structured result rather than an exception.

## Future estimator consumption

Future estimators must consume caller data only after validation and only through an explicitly
designed integration that checks the complete `EligibilityValidationResult`. A consumer must not
equate `data_eligible: true` with overall eligibility, ignore blocking diagnostics, infer power from
thresholds, or treat `executable` as evidence that an estimate exists. This task adds no estimator
wiring.

## Canonical structured-result examples

These are pretty-printed outputs from the repository's deterministic golden cases. They use real
schema fields, enum values, diagnostic codes, messages, and configured provenance. Human messages
are illustrative; consumers should use codes. There are no estimate fields.

### Fully eligible randomized analysis

The default policy is cleared by 100 balanced valid rows. The golden-case capability registry is
configured `available` only to demonstrate the data-eligibility outcome.

```json
{
  "outcome_type": "eligibility_validation",
  "validation_version": "1",
  "status": "eligible",
  "requested_method": "fixed_horizon_ab",
  "experiment_design": "randomized_experiment",
  "diagnostics": [],
  "blocking_diagnostics": [],
  "warnings": [],
  "dataset_summary": {"input_row_count": 100, "population_row_count": 100, "column_count": 3},
  "treatment_summary": {"treatment_count": 50, "control_count": 50, "missing_count": 0, "unknown_count": 0},
  "outcome_summary": {"valid_count": 100, "missing_count": 0, "invalid_type_count": 0, "non_finite_count": 0, "invalid_value_count": 0, "treatment_valid_count": 50, "control_valid_count": 50, "has_variation": true},
  "missingness_summary": [
    {"role": "treatment", "column": "arm", "total_count": 100, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "outcome", "column": "outcome", "total_count": 100, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "observation_unit", "column": "unit", "total_count": 100, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "randomization_unit", "column": "unit", "total_count": 100, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0}
  ],
  "unit_integrity_summary": {"observation_unit_count": 100, "missing_identifier_count": 0, "duplicate_identifier_count": 0, "repeated_observation_count": 0, "assignment_conflict_count": 0, "cluster_count": null},
  "time_summary": null,
  "segment_summary": null,
  "method_support": {"requested_method": "fixed_horizon_ab", "contract_status": "supported", "implementation_status": "available", "data_eligible": true, "executable": true},
  "abstention_reason": null,
  "policy_version": "analysis-validation-v1",
  "configuration_provenance": "golden-case:fully-eligible"
}
```

### Eligible with warnings

Forty balanced valid rows clear the blocking minimums but not the default advisory thresholds.

```json
{
  "outcome_type": "eligibility_validation",
  "validation_version": "1",
  "status": "eligible_with_warnings",
  "requested_method": "fixed_horizon_ab",
  "experiment_design": "randomized_experiment",
  "diagnostics": [
    {"code": "sample.total_weak", "category": "sample", "severity": "warning", "outcome": "failed", "disposition": "warning", "message": "The usable sample is below the configured advisory total.", "context": [{"key": "observed", "value": 40}, {"key": "threshold", "value": 100}], "recommended_action": null},
    {"code": "sample.arm_weak", "category": "sample", "severity": "warning", "outcome": "failed", "disposition": "warning", "message": "At least one arm is below the configured advisory sample threshold.", "context": [{"key": "control_count", "value": 20}, {"key": "threshold", "value": 30}, {"key": "treatment_count", "value": 20}], "recommended_action": null}
  ],
  "blocking_diagnostics": [],
  "warnings": [
    {"code": "sample.total_weak", "category": "sample", "severity": "warning", "outcome": "failed", "disposition": "warning", "message": "The usable sample is below the configured advisory total.", "context": [{"key": "observed", "value": 40}, {"key": "threshold", "value": 100}], "recommended_action": null},
    {"code": "sample.arm_weak", "category": "sample", "severity": "warning", "outcome": "failed", "disposition": "warning", "message": "At least one arm is below the configured advisory sample threshold.", "context": [{"key": "control_count", "value": 20}, {"key": "threshold", "value": 30}, {"key": "treatment_count", "value": 20}], "recommended_action": null}
  ],
  "dataset_summary": {"input_row_count": 40, "population_row_count": 40, "column_count": 3},
  "treatment_summary": {"treatment_count": 20, "control_count": 20, "missing_count": 0, "unknown_count": 0},
  "outcome_summary": {"valid_count": 40, "missing_count": 0, "invalid_type_count": 0, "non_finite_count": 0, "invalid_value_count": 0, "treatment_valid_count": 20, "control_valid_count": 20, "has_variation": true},
  "missingness_summary": [
    {"role": "treatment", "column": "arm", "total_count": 40, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "outcome", "column": "outcome", "total_count": 40, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "observation_unit", "column": "unit", "total_count": 40, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "randomization_unit", "column": "unit", "total_count": 40, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0}
  ],
  "unit_integrity_summary": {"observation_unit_count": 40, "missing_identifier_count": 0, "duplicate_identifier_count": 0, "repeated_observation_count": 0, "assignment_conflict_count": 0, "cluster_count": null},
  "time_summary": null,
  "segment_summary": null,
  "method_support": {"requested_method": "fixed_horizon_ab", "contract_status": "supported", "implementation_status": "available", "data_eligible": true, "executable": true},
  "abstention_reason": null,
  "policy_version": "analysis-validation-v1",
  "configuration_provenance": "golden-case:eligible-with-warnings"
}
```

### Ineligible post-treatment leakage

The dataset is otherwise usable, but post-treatment adjustment is a blocking causal-design error.

```json
{
  "outcome_type": "eligibility_validation",
  "validation_version": "1",
  "status": "ineligible",
  "requested_method": "fixed_horizon_ab",
  "experiment_design": "randomized_experiment",
  "diagnostics": [
    {"code": "covariate.post_treatment_leakage", "category": "covariate", "severity": "error", "outcome": "failed", "disposition": "blocking", "message": "Post-treatment covariates cannot be used for causal adjustment.", "context": [{"key": "metric_id", "value": "prior_count"}], "recommended_action": null}
  ],
  "blocking_diagnostics": [
    {"code": "covariate.post_treatment_leakage", "category": "covariate", "severity": "error", "outcome": "failed", "disposition": "blocking", "message": "Post-treatment covariates cannot be used for causal adjustment.", "context": [{"key": "metric_id", "value": "prior_count"}], "recommended_action": null}
  ],
  "warnings": [],
  "dataset_summary": {"input_row_count": 4, "population_row_count": 4, "column_count": 5},
  "treatment_summary": {"treatment_count": 2, "control_count": 2, "missing_count": 0, "unknown_count": 0},
  "outcome_summary": {"valid_count": 4, "missing_count": 0, "invalid_type_count": 0, "non_finite_count": 0, "invalid_value_count": 0, "treatment_valid_count": 2, "control_valid_count": 2, "has_variation": true},
  "missingness_summary": [
    {"role": "treatment", "column": "arm", "total_count": 4, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "outcome", "column": "outcome", "total_count": 4, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "observation_unit", "column": "unit", "total_count": 4, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "randomization_unit", "column": "unit", "total_count": 4, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "timestamp", "column": "observed_at", "total_count": 4, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "covariate:prior_count", "column": "prior_count", "total_count": 4, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0}
  ],
  "unit_integrity_summary": {"observation_unit_count": 4, "missing_identifier_count": 0, "duplicate_identifier_count": 0, "repeated_observation_count": 0, "assignment_conflict_count": 0, "cluster_count": null},
  "time_summary": {"total_count": 4, "valid_count": 4, "missing_count": 0, "invalid_count": 0, "pre_period_count": 0, "post_period_count": 4},
  "segment_summary": null,
  "method_support": {"requested_method": "fixed_horizon_ab", "contract_status": "supported", "implementation_status": "available", "data_eligible": false, "executable": false},
  "abstention_reason": {"code": "covariate.post_treatment_leakage", "message": "Post-treatment covariates cannot be used for causal adjustment.", "missing_or_invalid_information": ["covariate.post_treatment_leakage"]},
  "policy_version": "analysis-validation-v1",
  "configuration_provenance": "golden-case:post-treatment-leakage"
}
```

### Needs more data

This case uses an explicit compact policy (`minimum_total: 10`, `minimum_per_arm: 2`) and has six
otherwise valid rows, so it demonstrates needs-data precedence without unrelated diagnostics.

```json
{
  "outcome_type": "eligibility_validation",
  "validation_version": "1",
  "status": "needs_more_data",
  "requested_method": "fixed_horizon_ab",
  "experiment_design": "randomized_experiment",
  "diagnostics": [
    {"code": "sample.total_insufficient", "category": "sample", "severity": "warning", "outcome": "unavailable", "disposition": "needs_more_data", "message": "The usable sample is below the configured minimum total.", "context": [{"key": "observed", "value": 6}, {"key": "threshold", "value": 10}], "recommended_action": null}
  ],
  "blocking_diagnostics": [],
  "warnings": [],
  "dataset_summary": {"input_row_count": 6, "population_row_count": 6, "column_count": 3},
  "treatment_summary": {"treatment_count": 3, "control_count": 3, "missing_count": 0, "unknown_count": 0},
  "outcome_summary": {"valid_count": 6, "missing_count": 0, "invalid_type_count": 0, "non_finite_count": 0, "invalid_value_count": 0, "treatment_valid_count": 3, "control_valid_count": 3, "has_variation": true},
  "missingness_summary": [
    {"role": "treatment", "column": "arm", "total_count": 6, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "outcome", "column": "outcome", "total_count": 6, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "observation_unit", "column": "unit", "total_count": 6, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "randomization_unit", "column": "unit", "total_count": 6, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0}
  ],
  "unit_integrity_summary": {"observation_unit_count": 6, "missing_identifier_count": 0, "duplicate_identifier_count": 0, "repeated_observation_count": 0, "assignment_conflict_count": 0, "cluster_count": null},
  "time_summary": null,
  "segment_summary": null,
  "method_support": {"requested_method": "fixed_horizon_ab", "contract_status": "supported", "implementation_status": "available", "data_eligible": false, "executable": false},
  "abstention_reason": {"code": "sample.total_insufficient", "message": "The usable sample is below the configured minimum total.", "missing_or_invalid_information": ["sample.total_insufficient"]},
  "policy_version": "analysis-validation-v1",
  "configuration_provenance": "golden-case:insufficient-total"
}
```

### Estimator unavailable

This is the default-registry boundary: the request and 100 rows are eligible, but no estimator is
registered. The overall result abstains while preserving `data_eligible: true`.

```json
{
  "outcome_type": "eligibility_validation",
  "validation_version": "1",
  "status": "ineligible",
  "requested_method": "fixed_horizon_ab",
  "experiment_design": "randomized_experiment",
  "diagnostics": [
    {"code": "method.implementation_unavailable", "category": "method", "severity": "error", "outcome": "unavailable", "disposition": "blocking", "message": "No estimator implementation is available for the requested method.", "context": [{"key": "method", "value": "fixed_horizon_ab"}], "recommended_action": null}
  ],
  "blocking_diagnostics": [
    {"code": "method.implementation_unavailable", "category": "method", "severity": "error", "outcome": "unavailable", "disposition": "blocking", "message": "No estimator implementation is available for the requested method.", "context": [{"key": "method", "value": "fixed_horizon_ab"}], "recommended_action": null}
  ],
  "warnings": [],
  "dataset_summary": {"input_row_count": 100, "population_row_count": 100, "column_count": 3},
  "treatment_summary": {"treatment_count": 50, "control_count": 50, "missing_count": 0, "unknown_count": 0},
  "outcome_summary": {"valid_count": 100, "missing_count": 0, "invalid_type_count": 0, "non_finite_count": 0, "invalid_value_count": 0, "treatment_valid_count": 50, "control_valid_count": 50, "has_variation": true},
  "missingness_summary": [
    {"role": "treatment", "column": "arm", "total_count": 100, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "outcome", "column": "outcome", "total_count": 100, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "observation_unit", "column": "unit", "total_count": 100, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0},
    {"role": "randomization_unit", "column": "unit", "total_count": 100, "missing_count": 0, "missing_rate": 0.0, "treatment_missing_rate": 0.0, "control_missing_rate": 0.0, "differential_missingness": 0.0}
  ],
  "unit_integrity_summary": {"observation_unit_count": 100, "missing_identifier_count": 0, "duplicate_identifier_count": 0, "repeated_observation_count": 0, "assignment_conflict_count": 0, "cluster_count": null},
  "time_summary": null,
  "segment_summary": null,
  "method_support": {"requested_method": "fixed_horizon_ab", "contract_status": "supported", "implementation_status": "unavailable", "data_eligible": true, "executable": false},
  "abstention_reason": {"code": "method.implementation_unavailable", "message": "No estimator implementation is available for the requested method.", "missing_or_invalid_information": ["method.implementation_unavailable"]},
  "policy_version": "analysis-validation-v1",
  "configuration_provenance": "golden-case:estimator-unavailable"
}
```

## Limitations and out of scope

Passing validation is not evidence of statistical power, causal identification, model fit,
exchangeability, positivity, consistency, no interference, parallel trends, correct priors, or
business plausibility. The service does not compute descriptive statistics, effects, uncertainty,
power, or projections. It does not choose methods, repair data, call estimator/vendor libraries,
or expose a public HTTP endpoint. Estimator execution, agent/workflow consumption, persistence,
public API design, statistical diagnostics that require fitted models, and business-impact
calculation require separately designed future work.
