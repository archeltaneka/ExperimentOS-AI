"""Independent analytical and DGP references for workflow golden cases, version 1."""

from ..reference_values import StatisticalExpectedValue, StatisticalTolerance
from .models import WorkflowExpectations

# Point values are analytical fixture properties, never fitted at runtime.
# DML/HTE use the same finite-sample DGP interpretation as advanced conformance.
REFERENCES = {
    "econml_dml-real": (
        "point_estimate",
        2.0,
        0.15,
        "Known linear effect DGP; native adapter conformance tolerance",
    ),
    "econml_hte-real": (
        "subgroup_results.0.estimate",
        1.0,
        0.4,
        "Known subgroup effect; finite-sample adapter tolerance",
    ),
    "dowhy-real": (
        "estimate.point_estimate",
        2.0,
        0.15,
        "Known confounded linear effect DGP; native DoWhy conformance tolerance",
    ),
    "randomized": (
        "point_effect.absolute_effect.value",
        10.0,
        1e-12,
        "Equal-sized arms offset by 10",
    ),
    "did": ("cell_means.did_estimate", 3.0, 1e-12, "Hand-computed 2x2 cell contrast"),
    "cuped-success": (
        "adjusted_result.point_effect.absolute_effect.value",
        3.25,
        1e-12,
        "Equal covariate means preserve (4+4+7+10-0-3-3-6)/4",
    ),
    "bayesian-success": (
        "effect.posterior_mean",
        6 / 22,
        1e-10,
        "Uniform beta priors: 15/22 - 9/22",
    ),
    "sequential-success": (
        "looks.0.look_level_analysis.point_effect.absolute_effect.value",
        20.0,
        1e-12,
        "Equal-sized arms offset by 20",
    ),
    "propensity-success": (
        "score_diagnostics.overall.mean",
        0.5,
        0.001,
        "Logistic intercept score equation preserves the balanced treatment prevalence",
    ),
    "ipw-ate-success": ("point_estimate", 2.0, 1e-8, "Matched strata with constant effect 2"),
    "ipw-att-success": (
        "point_estimate",
        2.0,
        1e-8,
        "Matched treated strata with constant effect 2",
    ),
    "dml-success": (
        "point_estimate",
        2.0,
        0.15,
        "Known-effect linear DGP; advanced conformance finite-sample tolerance",
    ),
    "hte-success": (
        "subgroup_results.0.estimate",
        1.0,
        0.35,
        "Known subgroup DGP; bounded finite-sample noise and nuisance fitting",
    ),
}


def attach_expectations(case):
    reference = REFERENCES.get(case.case_id)
    if reference is None:
        return case
    path, value, tolerance, rationale = reference
    return case.model_copy(
        update={
            "expectations": WorkflowExpectations(
                numerical=(
                    StatisticalExpectedValue(
                        path=path,
                        value=value,
                        tolerance=StatisticalTolerance(
                            absolute=tolerance,
                            rationale=rationale,
                            provenance="workflow-reference-v1",
                        ),
                    ),
                )
            )
        }
    )
