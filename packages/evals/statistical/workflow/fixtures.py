"""Versioned small requests built from repository-owned reference inputs, not outputs."""

from copy import deepcopy
from datetime import UTC, datetime

from packages.experiments.analysis.causal.estimands import CausalEstimandKind
from packages.experiments.analysis.causal.ipw.models import IPWConfig, IPWOutcomeBinding
from packages.experiments.analysis.causal.models import ObservationalAnalysisRequest
from packages.experiments.analysis.causal.propensity.models import (
    PropensityConfig,
    PropensityExecutionRequest,
)
from packages.experiments.analysis.metrics import MetricType
from packages.experiments.analysis.orchestration.datasets import AnalysisDatasetInput
from packages.experiments.analysis.randomized.bayesian.models import (
    BayesianAnalysisExecutionRequest,
    BernoulliBinomialLikelihood,
    BetaPrior,
)
from packages.experiments.analysis.randomized.cuped.models import CupedAnalysisExecutionRequest
from packages.experiments.analysis.validation import AnalysisTable

from ..advanced.references.dml import dml_execution, dml_table
from ..advanced.references.econml import linear_rows
from ..advanced.references.hte import effect_rows, hte_execution, hte_table
from ..observational_fixtures import (
    _good_overlap_rows,
    _ipw_request,
    _propensity_binding,
    _separation_rows,
)
from ..randomized_fixtures import (
    _arm_table,
    _base_request,
    _bayesian_request,
    _cuped_request,
    _sequential_binding,
    _sequential_plan,
    _source,
)
from .models import AnalysisWorkflowCase


def _case(case_id, method, parameters, table, *, experiment="experiment-a", status="completed"):
    dataset = AnalysisDatasetInput(
        reference="sample",
        experiment_id=experiment,
        version="1",
        columns=table.columns,
        rows=table.rows,
        provenance=_source("workflow-reference-v1"),
    )
    request_id = parameters.get("execution", {}).get("request_id", "workflow-reference")
    if "analysis_request" in parameters.get("execution", {}):
        request_id = parameters["execution"].get(
            "request_id", parameters["execution"]["analysis_request"].get("request_id", request_id)
        )
    if "analysis_request" in parameters:
        request_id = parameters["analysis_request"]["request_id"]
    return AnalysisWorkflowCase(
        case_id=case_id,
        family="randomized"
        if method in {"cuped", "bayesian_ab", "sequential"}
        else "observational",
        design="randomized_experiment"
        if method in {"cuped", "bayesian_ab", "sequential"}
        else "observational",
        estimand="att" if method == "ipw_att" else "ate",
        fixture_id=case_id,
        expected_method=method,
        expected_status=status,
        ask_payload={
            "question": "Analyze",
            "experiment_id": experiment,
            "analysis": {"method": method, "request_id": request_id, "parameters": parameters},
            "analysis_datasets": [dataset.model_dump(mode="json")],
        },
    )


def _variant(case, case_id, status, mutate):
    payload = deepcopy(case.ask_payload)
    mutate(payload)
    return case.model_copy(
        update={
            "case_id": case_id,
            "fixture_id": case_id,
            "expected_status": status,
            "ask_payload": payload,
        }
    )


def build_core_cases() -> tuple[AnalysisWorkflowCase, ...]:
    ref = {"reference": "sample", "version": "1"}
    cases = []
    request, binding = _cuped_request(treatment=20, control=20)
    execution = CupedAnalysisExecutionRequest(
        request_id="cuped-reference", analysis_request=request
    )
    cuped = _case(
        "cuped-success",
        "cuped",
        {
            "execution": execution.model_dump(mode="json"),
            "binding": binding.model_dump(mode="json"),
            "dataset": ref,
        },
        _arm_table(
            (4.0, 4.0, 7.0, 10.0) * 5,
            (0.0, 3.0, 3.0, 6.0) * 5,
            covariates=((0.0, 1.0, 2.0, 3.0) * 5, (0.0, 1.0, 2.0, 3.0) * 5),
        ),
    )
    cases.append(cuped)

    def post_cuped(p):
        p["analysis"]["parameters"]["execution"]["analysis_request"]["covariates"][0]["timing"] = (
            "post_treatment"
        )

    cases.append(_variant(cuped, "cuped-post-treatment", "abstained", post_cuped))
    prior = BetaPrior(alpha=1.0, beta=1.0, provenance=_source("uniform-beta-prior-v1"))
    execution = BayesianAnalysisExecutionRequest(
        request_id="bayesian-reference",
        analysis_request=_bayesian_request(MetricType.BINARY, 20, 20),
        treatment_prior=prior,
        control_prior=prior,
        likelihood=BernoulliBinomialLikelihood(),
    )
    bayesian = _case(
        "bayesian-success",
        "bayesian_ab",
        {
            "execution": execution.model_dump(mode="json"),
            "binding": _base_request(MetricType.BINARY)[1].model_dump(mode="json"),
            "dataset": ref,
        },
        _arm_table((1,) * 14 + (0,) * 6, (1,) * 8 + (0,) * 12),
    )
    cases.append(bayesian)

    def invalid_prior(p):
        p["analysis"]["parameters"]["execution"]["treatment_prior"]["alpha"] = -1.0

    cases.append(_variant(bayesian, "bayesian-invalid-prior", "invalid", invalid_prior))
    plan = _sequential_plan((1.0,))
    sequential = _case(
        "sequential-success",
        "sequential",
        {
            "plan": plan.model_dump(mode="json"),
            "looks": [
                {
                    "look_index": 1,
                    "information_time": 1.0,
                    "plan_fingerprint": plan.plan_fingerprint,
                    "analysis_request": plan.analysis_request.model_dump(mode="json"),
                    "binding": _sequential_binding().model_dump(mode="json"),
                    "dataset": ref,
                    "executed_at": datetime(2026, 7, 3, tzinfo=UTC).isoformat(),
                }
            ],
        },
        _arm_table(tuple(float(i + 20) for i in range(30)), tuple(float(i) for i in range(30))),
        experiment=plan.experiment_id,
    )
    cases.append(sequential)

    def invalid_plan(p):
        p["analysis"]["parameters"]["looks"][0]["plan_fingerprint"] = "0" * 64

    cases.append(_variant(sequential, "sequential-invalid-plan", "invalid", invalid_plan))
    # Paired +/- noise at each covariate value gives both weighted effects exactly 2.
    rows = tuple(
        {
            **row,
            "account_id": f"{row['account_id']}-{noise}",
            "conversion": float(2 * row["treated"] + noise),
        }
        for row in _good_overlap_rows()
        for noise in (-1, 1)
    )
    for method in ("propensity_diagnostics", "ipw_ate", "ipw_att"):
        kind = CausalEstimandKind.ATT if method == "ipw_att" else CausalEstimandKind.ATE
        declaration = _ipw_request(estimand=kind, binary=False)
        ps = PropensityExecutionRequest(
            analysis_request=declaration,
            binding=_propensity_binding(),
            configuration=PropensityConfig(),
        )
        params = {"dataset": ref}
        if method == "propensity_diagnostics":
            params["execution"] = ps.model_dump(mode="json")
        else:
            params.update(
                analysis_request=declaration.model_dump(mode="json"),
                propensity_binding=ps.binding.model_dump(mode="json"),
                propensity_configuration=ps.configuration.model_dump(mode="json"),
                binding=IPWOutcomeBinding(outcome_column="conversion").model_dump(mode="json"),
                configuration=IPWConfig().model_dump(mode="json"),
            )
        name = "propensity" if method == "propensity_diagnostics" else method.replace("_", "-")
        case = _case(name + "-success", method, params, AnalysisTable.from_records(rows))
        cases.append(case)
        if method != "ipw_att":
            separated = AnalysisTable.from_records(
                tuple({**r, "conversion": float(i % 5)} for i, r in enumerate(_separation_rows()))
            )
            negative = case.model_copy(deep=True)
            negative.ask_payload["analysis_datasets"][0].update(
                columns=list(separated.columns), rows=[list(r) for r in separated.rows]
            )
            cases.append(
                negative.model_copy(
                    update={"case_id": name + "-no-overlap", "expected_status": "abstained"}
                )
            )
    for method in ("dml", "hte"):
        native = (
            dml_execution(fold_count=4, seed=812)
            if method == "dml"
            else hte_execution(fold_count=4)
        )
        declaration = ObservationalAnalysisRequest(
            request_id=native.identification_result.request_id,
            identification=native.identification_result.identification_request,
        )
        params = {
            "dataset": ref,
            "analysis_request": declaration.model_dump(mode="json"),
            "binding": native.binding.model_dump(mode="json"),
            "configuration": native.configuration.model_dump(mode="json"),
        }
        if method == "hte":
            params["modifier"] = native.modifier.model_dump(mode="json")
        case = _case(
            method + "-success",
            method,
            params,
            dml_table(linear_rows()) if method == "dml" else hte_table(effect_rows()),
        )
        cases.append(case)

        def post_adjustment(p, method=method):
            variables = p["analysis"]["parameters"]["analysis_request"]["identification"][
                "variables"
            ]
            for variable in variables:
                if variable["variable_id"] == ("prior_orders" if method == "dml" else "country"):
                    variable["timing"]["measurement_timing"] = "post_treatment"

        cases.append(_variant(case, method + "-post-treatment", "invalid", post_adjustment))
        if method == "hte":
            cases.append(
                _variant(
                    case,
                    "hte-sparse",
                    "abstained",
                    lambda p: p["analysis"]["parameters"]["configuration"].update(
                        minimum_subgroup_retained=100
                    ),
                )
            )
        else:
            cases.append(
                _variant(
                    case,
                    "dml-degenerate",
                    "abstained",
                    lambda p: p["analysis"]["parameters"]["configuration"].update(
                        treatment_residual_tolerance=1000.0
                    ),
                )
            )
    return tuple(cases)


def build_boundary_variants(by_id):
    """Version 1 business and timing variants with explicit inputs only."""
    business = by_id["business"]

    def negative_cost(p):
        p["analysis"]["business"]["costs"]["items"][0]["value"] = {
            "lower": 20000,
            "central": 20000,
            "upper": 20000,
        }

    def zero_effect(p):
        rows = p["analysis_datasets"][0]["rows"]
        control = [r[2] for r in rows if r[1] == "control"]
        treated = [r for r in rows if r[1] == "treatment"]
        for row, value in zip(treated, control, strict=True):
            row[2] = value

    def invalid_timing(p):
        p["analysis_datasets"][0]["rows"][0][1] = "not-a-timestamp"

    return (
        _variant(business, "business-negative", "completed", negative_cost),
        _variant(business, "business-cross-zero", "completed", zero_effect),
        _variant(by_id["did"], "did-invalid-timing", "abstained", invalid_timing),
    )
