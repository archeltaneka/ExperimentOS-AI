"""Native executions independent of workflow routing; not numerical oracles."""

from contextlib import ExitStack
from datetime import datetime
from unittest.mock import patch

from packages.experiments.analysis.causal.dml.models import DMLExecutionRequest
from packages.experiments.analysis.causal.hte.models import HTEExecutionRequest
from packages.experiments.analysis.causal.ipw.models import IPWExecutionRequest
from packages.experiments.analysis.causal.models import IdentificationStatus
from packages.experiments.analysis.causal.propensity.models import PropensityExecutionRequest
from packages.experiments.analysis.causal.service import CausalIdentificationService
from packages.experiments.analysis.orchestration.datasets import (
    AnalysisDatasetInput,
    RequestDatasetResolver,
    resolve_dataset,
)
from packages.experiments.analysis.orchestration.requests import (
    AnalysisRoutingRefusal,
    normalize_analysis_input,
)
from packages.experiments.analysis.validation import AnalysisTable


def run_native_reference(case):
    request = normalize_analysis_input(
        case.ask_payload["analysis"], experiment_id=str(case.ask_payload["experiment_id"])
    )
    if isinstance(request, AnalysisRoutingRefusal):
        return None
    resolver = RequestDatasetResolver(
        tuple(
            AnalysisDatasetInput.model_validate(d)
            for d in case.ask_payload.get("analysis_datasets", [])
        )
    )
    if request.method == "sequential":
        from packages.experiments.analysis.randomized.sequential.service import (
            SequentialAnalysisService,
            SequentialLookExecution,
        )

        looks = []
        provenance = request.plan.provenance
        for look in request.looks:
            dataset = resolve_dataset(resolver, look.dataset, request.experiment_id)
            provenance = (*provenance, *dataset.provenance)
            looks.append(
                SequentialLookExecution(
                    look_index=look.look_index,
                    information_time=look.information_time,
                    plan_fingerprint=look.plan_fingerprint,
                    analysis_request=look.analysis_request,
                    binding=look.binding,
                    executed_at=look.executed_at,
                    table=dataset.table,
                )
            )
        return SequentialAnalysisService().analyze(
            request.plan, tuple(looks), provenance=provenance
        )
    dataset = (
        resolve_dataset(resolver, request.dataset, request.experiment_id)
        if request.dataset
        else None
    )
    table = dataset.table if dataset else None
    provenance = dataset.provenance if dataset else ()
    if request.method in {"randomized_fixed_horizon", "cuped", "bayesian_ab"}:
        from packages.experiments.analysis.randomized.bayesian.service import (
            BayesianAnalysisService,
        )
        from packages.experiments.analysis.randomized.cuped.service import CupedAnalysisService
        from packages.experiments.analysis.randomized.service import RandomizedAnalysisService

        factory = {
            "randomized_fixed_horizon": RandomizedAnalysisService,
            "cuped": CupedAnalysisService,
            "bayesian_ab": BayesianAnalysisService,
        }[request.method]
        return factory().analyze(request.execution, table, request.binding, provenance=provenance)
    if request.method == "did":
        from packages.experiments.analysis.causal.did.service import DifferenceInDifferencesService

        columns = {
            request.execution.binding.time_column,
            request.execution.binding.treatment_start_column,
        }

        def decode(column, value):
            if column in columns and isinstance(value, str):
                try:
                    return datetime.fromisoformat(value)
                except ValueError:
                    pass
            return value

        table = AnalysisTable(
            columns=table.columns,
            rows=tuple(
                tuple(decode(c, v) for c, v in zip(table.columns, row, strict=True))
                for row in table.rows
            ),
        )
        return DifferenceInDifferencesService().analyze(
            request.execution, table, provenance=provenance
        )
    identification = CausalIdentificationService().identify(
        request.execution.analysis_request
        if request.method == "propensity_diagnostics"
        else request.analysis_request
    )
    if identification.status is not IdentificationStatus.IDENTIFIED:
        return identification
    if request.method in {"propensity_diagnostics", "ipw_ate", "ipw_att"}:
        from packages.experiments.analysis.causal.ipw.service import IPWTreatmentEffectEstimator
        from packages.experiments.analysis.causal.propensity.service import (
            DeterministicLogisticPropensityEstimator,
        )

        execution = (
            request.execution
            if request.method == "propensity_diagnostics"
            else PropensityExecutionRequest(
                analysis_request=request.analysis_request,
                binding=request.propensity_binding,
                configuration=request.propensity_configuration,
            )
        )
        propensity = DeterministicLogisticPropensityEstimator().fit_predict(
            execution, table, provenance=provenance
        )
        if request.method == "propensity_diagnostics" or propensity.status != "completed":
            return propensity
        return IPWTreatmentEffectEstimator().analyze(
            IPWExecutionRequest(
                identification_result=identification,
                propensity_result=propensity,
                binding=request.binding,
                configuration=request.configuration,
            ),
            table,
            provenance=provenance,
        )
    with ExitStack() as stack:
        if case.optional_unavailable:
            from packages.experiments.analysis.causal.econml.dependency import AdapterError

            stack.enter_context(
                patch(
                    "packages.experiments.analysis.causal.econml.dependency.load_econml",
                    side_effect=AdapterError(
                        "OPTIONAL_DEPENDENCY_UNAVAILABLE", "Offline unavailable-runtime case"
                    ),
                )
            )
        if request.method in {"dml", "econml_dml"}:
            from packages.experiments.analysis.causal.dml.service import (
                DoubleMachineLearningEstimator,
            )

            if request.method == "econml_dml":
                from packages.experiments.analysis.causal.econml import EconMLDMLAdapter

                estimator = EconMLDMLAdapter(configuration=request.adapter_configuration)
            else:
                estimator = DoubleMachineLearningEstimator()
            return estimator.analyze(
                DMLExecutionRequest(
                    identification_result=identification,
                    binding=request.binding,
                    configuration=request.configuration,
                ),
                table,
                provenance=provenance,
            )
        if request.method in {"hte", "econml_hte"}:
            from packages.experiments.analysis.causal.hte.service import (
                HeterogeneousEffectEstimator,
            )

            if request.method == "econml_hte":
                from packages.experiments.analysis.causal.econml import EconMLHTEAdapter

                estimator = EconMLHTEAdapter(configuration=request.adapter_configuration)
            else:
                estimator = HeterogeneousEffectEstimator()
            return estimator.analyze(
                HTEExecutionRequest(
                    identification_result=identification,
                    binding=request.binding,
                    configuration=request.configuration,
                    modifier=request.modifier,
                ),
                table,
                provenance=provenance,
            )
        if request.method == "dowhy":
            from packages.experiments.analysis.causal.dowhy.adapter import DoWhyAdapter
            from packages.experiments.analysis.causal.dowhy.models import DoWhyExecutionRequest

            return DoWhyAdapter().analyze(
                DoWhyExecutionRequest(
                    identification_result=identification,
                    binding=request.binding,
                    configuration=request.configuration,
                ),
                table,
                provenance=provenance,
            )
    raise ValueError("unsupported reference method")
