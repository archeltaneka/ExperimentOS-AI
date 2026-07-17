# Statistical and Causal Analysis Contracts

## Scope

Phase 4 introduces immutable, versioned models for expressing statistical and causal analysis
inputs and outputs without performing analysis. The contracts keep descriptive, associational,
randomized, quasi-experimental, observational, and projected evidence structurally distinct.

No estimator is implemented. `POST /ask`, agents, persistence, and workflows are unchanged. This
work adds no calculations, eligibility policy, agent integration, database schema, or public API
fields.

## Package Boundary

The public internal boundary is `packages.experiments.analysis`. Consumers should import its
models and serialization helpers from that package; `packages.experiments` deliberately does not
re-export them. Contract JSON uses `schema_version: "1"`, stable lowercase enum values, explicit
discriminators, finite numeric values, and ISO 8601 timestamps with timezones.

The models describe declared inputs and typed outcomes. Method names such as `fixed_horizon_ab`
and `double_machine_learning` identify intended analysis structure; they do not select, configure,
or run an estimator.

## Randomized Request Example

This valid request keeps the account-level randomization unit separate from the order-level unit
of analysis and states both allocation and requested uncertainty explicitly.

```json
{
  "schema_version": "1",
  "population": {
    "population_id": "checkout_users",
    "label": "Checkout users",
    "criteria": []
  },
  "treatment": {
    "treatment_id": "ranked_payment",
    "label": "Ranked payment",
    "assignment_value": "treatment",
    "description": "Rank payment methods using the recommendation model."
  },
  "control": {
    "control_id": "standard_payment",
    "label": "Standard payment",
    "assignment_value": "control",
    "description": "Use the standard payment-method ordering."
  },
  "outcome": {
    "metric": {
      "metric_id": "payment_success_rate",
      "label": "Payment success rate",
      "metric_type": "proportion",
      "unit": {
        "dimension": "proportion",
        "value_scale": "proportion",
        "symbol": "1",
        "scale_to_base_unit": 1.0
      }
    },
    "direction": "increase"
  },
  "estimand": {
    "kind": "intention_to_treat"
  },
  "study_design": {
    "design_type": "randomized_experiment",
    "method": "fixed_horizon_ab",
    "experiment_period": {
      "start": "2026-07-01T00:00:00Z",
      "end": "2026-07-15T00:00:00Z"
    },
    "randomization_unit": {
      "unit_id": "account",
      "label": "Account"
    },
    "treatment_allocation": 0.5,
    "control_allocation": 0.5
  },
  "unit_of_analysis": {
    "unit_id": "order",
    "label": "Order"
  },
  "clustering": {
    "kind": "none"
  },
  "sample_counts": {
    "total": 200,
    "treatment": 100,
    "control": 100
  },
  "uncertainty": {
    "kind": "confidence",
    "level": 0.95
  },
  "covariates": [],
  "pre_treatment_metrics": []
}
```

## Observational Request Example

This request explicitly declares an observational design, adjustment covariate timing, clustering,
and exposure groups. The method identifier does not establish causal eligibility or justify a
causal conclusion.

```json
{
  "schema_version": "1",
  "population": {
    "population_id": "eligible_customers",
    "label": "Eligible customers",
    "criteria": []
  },
  "treatment": {
    "treatment_id": "offer_exposed",
    "label": "Offer exposed",
    "assignment_value": "exposed",
    "description": "Customers exposed to the offer."
  },
  "control": {
    "control_id": "offer_unexposed",
    "label": "Offer unexposed",
    "assignment_value": "unexposed",
    "description": "Customers not exposed to the offer."
  },
  "outcome": {
    "metric": {
      "metric_id": "conversion_rate",
      "label": "Conversion rate",
      "metric_type": "proportion",
      "unit": {
        "dimension": "proportion",
        "value_scale": "proportion",
        "symbol": "1",
        "scale_to_base_unit": 1.0
      }
    },
    "direction": "increase"
  },
  "estimand": {
    "kind": "average_treatment_effect_on_treated"
  },
  "study_design": {
    "design_type": "observational_study",
    "method": "double_machine_learning",
    "observation_period": {
      "start": "2026-06-01T00:00:00Z",
      "end": "2026-06-30T00:00:00Z"
    }
  },
  "unit_of_analysis": {
    "unit_id": "customer",
    "label": "Customer"
  },
  "clustering": {
    "kind": "clustered",
    "unit": {
      "unit_id": "customer",
      "label": "Customer"
    }
  },
  "sample_counts": {
    "total": 300,
    "treatment": 120,
    "control": 180
  },
  "uncertainty": {
    "kind": "confidence",
    "level": 0.95
  },
  "covariates": [
    {
      "metric": {
        "metric_id": "prior_order_count",
        "label": "Prior order count",
        "metric_type": "count",
        "unit": {
          "dimension": "count",
          "value_scale": "raw",
          "symbol": "count",
          "scale_to_base_unit": 1.0
        }
      },
      "timing": "pre_treatment",
      "role": "adjustment",
      "treatment_relationship": "none_known",
      "measurement_period": {
        "start": "2026-05-01T00:00:00Z",
        "end": "2026-06-01T00:00:00Z"
      }
    }
  ],
  "pre_treatment_metrics": []
}
```

## Estimate and Uncertainty Example

An estimate records its evidence category and conclusion separately. Its value has an explicit
unit, uncertainty is structured rather than presentation text, and provenance is mandatory. This
example is a representation of a supplied result, not output calculated by this package.

```json
{
  "finding_type": "randomized_experiment_estimate",
  "conclusion_type": "causal_effect",
  "estimate": {
    "status": "completed",
    "estimand": {
      "kind": "intention_to_treat"
    },
    "outcome": {
      "metric": {
        "metric_id": "payment_success_rate",
        "label": "Payment success rate",
        "metric_type": "proportion",
        "unit": {
          "dimension": "proportion",
          "value_scale": "proportion",
          "symbol": "1",
          "scale_to_base_unit": 1.0
        }
      },
      "direction": "increase"
    },
    "point_estimate": {
      "value": 0.055,
      "unit": {
        "dimension": "proportion",
        "value_scale": "proportion",
        "symbol": "1",
        "scale_to_base_unit": 1.0
      }
    },
    "uncertainty": {
      "measures": [
        {
          "kind": "confidence_interval",
          "lower": 0.002,
          "upper": 0.108,
          "confidence_level": 0.95
        }
      ]
    },
    "sample_counts": {
      "total": 200,
      "treatment": 100,
      "control": 100
    },
    "assumptions": [],
    "diagnostics": [],
    "warnings": [],
    "provenance": [
      {
        "source_type": "experiment_data",
        "source_id": "exp-001-payment-recommendation"
      }
    ]
  }
}
```

## Abstention Example

Abstention carries a typed reason and the missing or invalid information. It cannot carry an
estimate, preventing an unavailable analysis from being represented with a fabricated value.

```json
{
  "outcome_type": "abstained",
  "schema_version": "1",
  "status": "abstained",
  "reason": {
    "code": "covariate_timing_unknown",
    "message": "Causal adjustment is unsafe.",
    "missing_or_invalid_information": [
      "covariate timing"
    ]
  },
  "diagnostics": [],
  "warnings": [],
  "provenance": [
    {
      "source_type": "experiment_data",
      "source_id": "exp-001-payment-recommendation"
    }
  ]
}
```

## Business-Impact Projection Inputs

`BusinessImpactProjection` is a projection contract, not a causal estimator. It embeds the complete
source estimate, the following complete sourced inputs, projected numeric outputs with units, an
uncertainty bundle, assumptions, diagnostics, warnings, and projection provenance. An
associational source estimate remains associational inside the projection.

```json
{
  "eligible_population": {
    "value": 100000,
    "provenance": [
      {
        "source_type": "experiment_data",
        "source_id": "exp-001-payment-recommendation"
      }
    ]
  },
  "exposure_frequency": {
    "value": 2.0,
    "unit": {
      "dimension": "custom",
      "value_scale": "custom",
      "symbol": "exposures/user/month",
      "scale_to_base_unit": 1.0,
      "custom_dimension_name": "exposures per user per month"
    },
    "provenance": [
      {
        "source_type": "experiment_data",
        "source_id": "exp-001-payment-recommendation"
      }
    ]
  },
  "baseline_rate": {
    "value": 0.2,
    "unit": {
      "dimension": "proportion",
      "value_scale": "proportion",
      "symbol": "1",
      "scale_to_base_unit": 1.0
    },
    "provenance": [
      {
        "source_type": "experiment_data",
        "source_id": "exp-001-payment-recommendation"
      }
    ]
  },
  "average_order_value": {
    "value": 80.0,
    "unit": {
      "dimension": "currency",
      "value_scale": "raw",
      "symbol": "USD",
      "scale_to_base_unit": 1.0,
      "currency_code": "USD"
    },
    "provenance": [
      {
        "source_type": "experiment_data",
        "source_id": "exp-001-payment-recommendation"
      }
    ]
  },
  "contribution_margin": {
    "value": 0.3,
    "unit": {
      "dimension": "proportion",
      "value_scale": "proportion",
      "symbol": "1",
      "scale_to_base_unit": 1.0
    },
    "provenance": [
      {
        "source_type": "experiment_data",
        "source_id": "exp-001-payment-recommendation"
      }
    ]
  },
  "rollout_proportion": {
    "value": 0.5,
    "unit": {
      "dimension": "proportion",
      "value_scale": "proportion",
      "symbol": "1",
      "scale_to_base_unit": 1.0
    },
    "provenance": [
      {
        "source_type": "experiment_data",
        "source_id": "exp-001-payment-recommendation"
      }
    ]
  },
  "analysis_horizon": {
    "value": {
      "start": "2026-08-01T00:00:00Z",
      "end": "2026-09-01T00:00:00Z"
    },
    "provenance": [
      {
        "source_type": "experiment_data",
        "source_id": "exp-001-payment-recommendation"
      }
    ]
  },
  "currency": {
    "value": "USD",
    "provenance": [
      {
        "source_type": "experiment_data",
        "source_id": "exp-001-payment-recommendation"
      }
    ]
  }
}
```

The contracts validate that the projection currency matches these inputs, but do not calculate
incremental outcomes or financial impact.

## Validation Boundary

The contract layer rejects unambiguous structural contradictions: missing or empty identifiers,
non-finite numbers, invalid units or scales, equal treatment and control values, inconsistent
sample totals, invalid allocations, unordered periods or intervals, invalid probability levels,
invalid CATE conditioning, incompatible status/result shapes, missing required provenance,
incomplete business inputs, and mismatched projection currency.

It deliberately does not decide statistical power, sample-ratio mismatch, overlap, positivity,
exchangeability, consistency, interference, parallel trends, CUPED suitability, sequential plans,
Bayesian priors, model fit, treatment leakage, design/metric/estimand compatibility, estimator
eligibility, or business plausibility. Those checks require later policy and analysis layers.

## Deferred Phase 4 Work

Later Phase 4 work owns eligibility assessment from real data, statistical calculations,
randomized and observational estimators, quasi-experimental methods, third-party adapters,
business-impact calculations, agent and workflow integration, persistence, observability events,
evaluation and quality policy, and any separately designed public API expansion.
