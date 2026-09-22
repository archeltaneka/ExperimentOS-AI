"""Native declarations reused to exercise orchestration without any LLM."""

from packages.experiments.analysis.causal.advanced.models import AdvancedEstimatorConfig
from packages.experiments.analysis.causal.estimands import CausalEstimandKind
from packages.experiments.analysis.causal.ipw.models import IPWConfig, IPWOutcomeBinding
from packages.experiments.analysis.causal.models import ObservationalAnalysisRequest
from packages.experiments.analysis.metrics import MetricType
from packages.experiments.analysis.randomized.cuped.models import CupedAnalysisExecutionRequest
from packages.experiments.analysis.randomized.sequential.fingerprint import (
    sequential_plan_fingerprint,
)
from tests.did_fixtures import did_execution
from tests.dml_fixtures import dml_execution
from tests.dowhy_fixtures import execution as dowhy_execution
from tests.hte_fixtures import hte_execution
from tests.propensity_fixtures import propensity_execution, propensity_request
from tests.sequential_fixtures import sequential_plan
from tests.test_analysis_orchestration_requests import fixed_payload
from tests.test_bayesian_service import _beta_execution
from tests.test_bayesian_service import _request as bayesian_request
from tests.test_cuped_service import _binding as cuped_binding
from tests.test_cuped_service import _request as cuped_request

METHODS = (
    "randomized_fixed_horizon",
    "cuped",
    "bayesian_ab",
    "sequential",
    "did",
    "propensity_diagnostics",
    "ipw_ate",
    "ipw_att",
    "dml",
    "hte",
    "econml_dml",
    "econml_hte",
    "dowhy",
)


def method_payload(method):
    payload = fixed_payload()
    payload["method"] = method
    parameters = {"dataset": {"reference": "sample", "version": "1"}}
    if method == "randomized_fixed_horizon":
        return payload
    if method == "cuped":
        native = CupedAnalysisExecutionRequest(request_id="cuped", analysis_request=cuped_request())
        parameters.update(
            execution=native.model_dump(mode="json"),
            binding=cuped_binding().model_dump(mode="json"),
        )
    elif method == "bayesian_ab":
        native = _beta_execution(bayesian_request(MetricType.BINARY))
        parameters.update(
            execution=native.model_dump(mode="json"), binding=payload["parameters"]["binding"]
        )
    elif method == "sequential":
        plan = sequential_plan()
        plan = plan.model_copy(update={"experiment_id": "experiment-a"})
        plan = plan.model_copy(update={"plan_fingerprint": sequential_plan_fingerprint(plan)})
        payload["request_id"] = "sequential"
        payload["parameters"] = {"plan": plan.model_dump(mode="json"), "looks": []}
        return payload
    elif method in ("did", "propensity_diagnostics"):
        native = did_execution() if method == "did" else propensity_execution()
        parameters["execution"] = native.model_dump(mode="json")
    elif method in ("ipw_ate", "ipw_att"):
        kind = CausalEstimandKind.ATE if method == "ipw_ate" else CausalEstimandKind.ATT
        native = propensity_execution(analysis_request=propensity_request(estimand_kind=kind))
        parameters.update(
            analysis_request=native.analysis_request.model_dump(mode="json"),
            propensity_binding=native.binding.model_dump(mode="json"),
            propensity_configuration=native.configuration.model_dump(mode="json"),
            binding=IPWOutcomeBinding(outcome_column="outcome").model_dump(mode="json"),
            configuration=IPWConfig().model_dump(mode="json"),
        )
    else:
        native = (
            dowhy_execution()
            if method == "dowhy"
            else hte_execution()
            if method in ("hte", "econml_hte")
            else dml_execution()
        )
        observational = ObservationalAnalysisRequest(
            request_id=native.identification_result.request_id,
            identification=native.identification_result.identification_request,
        )
        parameters.update(
            analysis_request=observational.model_dump(mode="json"),
            binding=native.binding.model_dump(mode="json"),
            configuration=native.configuration.model_dump(mode="json"),
        )
        if method in ("hte", "econml_hte"):
            parameters["modifier"] = native.modifier.model_dump(mode="json")
        if method.startswith("econml_"):
            parameters["adapter_configuration"] = AdvancedEstimatorConfig(
                constant_effect_assumption=True
            ).model_dump(mode="json")
        payload["request_id"] = observational.request_id
        payload["parameters"] = parameters
        return payload
    payload["request_id"] = native.request_id
    payload["parameters"] = parameters
    return payload
