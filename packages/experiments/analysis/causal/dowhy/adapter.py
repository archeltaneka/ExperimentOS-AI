"""Narrow DoWhy identification, estimation, and refutation adapter."""

from __future__ import annotations

import math
import platform
from time import perf_counter
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from packages.observability.base import BaseObservabilityProvider
from packages.observability.noop import NoOpObservabilityProvider

from ...provenance import ProvenanceRecords
from ...validation.table import AnalysisTable
from ..estimands import CausalEstimandKind, EffectScale
from ..models import IdentificationStatus, ObservationalAnalysisRequest
from ..service import CausalIdentificationService
from . import dependency
from .dependency import AdapterError
from .graph import graph_fingerprint, to_networkx
from .models import (
    DoWhyAbstentionReason,
    DoWhyAdapterProvenance,
    DoWhyAnalysisResult,
    DoWhyDiagnostic,
    DoWhyEstimateEvidence,
    DoWhyExecutionRequest,
    DoWhyFailureCode,
    DoWhyIdentificationEvidence,
    DoWhyOperationStatus,
    DoWhyRefutationResult,
    DoWhyRefuterMethod,
    DoWhyRefuterStatus,
)
from .observability import observe_dowhy_result

_CONDITIONAL = (
    "Identification is conditional on the supplied graph and its encoded assumptions; "
    "it does not prove that the graph is true or that unmeasured confounding is absent."
)


class DoWhyAdapter:
    adapter_id = "experimentos_dowhy"

    def __init__(self, *, observability_provider: BaseObservabilityProvider | None = None) -> None:
        self.observability_provider = observability_provider or NoOpObservabilityProvider()

    def analyze(
        self,
        execution: DoWhyExecutionRequest,
        table: AnalysisTable | None = None,
        *,
        provenance: ProvenanceRecords,
    ) -> DoWhyAnalysisResult:
        started = perf_counter()
        result = self._analyze(execution, table, provenance=provenance)
        observe_dowhy_result(
            self.observability_provider, result, (perf_counter() - started) * 1000.0
        )
        return result

    def _analyze(
        self,
        execution: DoWhyExecutionRequest,
        table: AnalysisTable | None = None,
        *,
        provenance: ProvenanceRecords,
    ) -> DoWhyAnalysisResult:
        source = execution.identification_result
        graph = source.causal_graph
        fingerprint = graph_fingerprint(graph) if graph is not None else "0" * 64
        evidence = DoWhyIdentificationEvidence(
            status=DoWhyOperationStatus.ABSTAINED,
            method="default_backdoor",
            adjustment_set=(),
            graph_fingerprint=fingerprint,
            interpretation=_CONDITIONAL,
        )
        failure = self._validate(execution)
        if failure is not None:
            return self._failed(execution, evidence, provenance, *failure)
        assert graph is not None
        assert source.treatment is not None
        assert source.outcome is not None
        try:
            backend = dependency.load_dowhy()
        except AdapterError as error:
            return self._failed(execution, evidence, provenance, error.code, str(error))
        observed = sorted(node.variable_id for node in graph.nodes if node.observed)
        try:
            model = backend.CausalModel(
                data=pd.DataFrame(columns=observed),
                treatment=source.treatment.treatment_variable,
                outcome=source.outcome.variable_id,
                graph=to_networkx(graph),
                estimand_type="nonparametric-ate",
                proceed_when_unidentifiable=False,
                missing_nodes_as_confounders=False,
                identify_vars=False,
            )
        except Exception:
            return self._failed(
                execution,
                evidence,
                provenance,
                DoWhyFailureCode.MODEL_CONSTRUCTION_FAILURE,
                "DoWhy model construction failed.",
                status=DoWhyOperationStatus.ERROR,
            )
        try:
            identified = model.identify_effect(
                method_name="default",
                proceed_when_unidentifiable=False,
                optimize_backdoor=False,
            )
        except Exception:
            return self._failed(
                execution,
                evidence,
                provenance,
                DoWhyFailureCode.IDENTIFICATION_FAILURE,
                "DoWhy identification failed.",
                status=DoWhyOperationStatus.ERROR,
            )
        estimands = getattr(identified, "estimands", None)
        default = getattr(identified, "default_backdoor_id", None)
        if not isinstance(estimands, dict):
            return self._failed(
                execution,
                evidence,
                provenance,
                DoWhyFailureCode.MALFORMED_DOWHY_RESULT,
                "DoWhy returned a malformed identification result.",
                status=DoWhyOperationStatus.ERROR,
            )
        try:
            if estimands.get("backdoor") is None or default is None:
                return self._failed(
                    execution,
                    evidence,
                    provenance,
                    DoWhyFailureCode.IDENTIFICATION_UNAVAILABLE,
                    "No supported backdoor estimand is identifiable under the supplied graph.",
                )
            adjustment = tuple(sorted(identified.get_adjustment_set("backdoor")))
            requested = (
                source.adjustment_set.variable_ids if source.adjustment_set is not None else ()
            )
            if requested and adjustment != requested:
                return self._failed(
                    execution,
                    evidence,
                    provenance,
                    DoWhyFailureCode.INVALID_GRAPH,
                    "The graph-identified adjustment set contradicts the causal contract.",
                    status=DoWhyOperationStatus.INVALID,
                )
            evidence = evidence.model_copy(
                update={"status": DoWhyOperationStatus.COMPLETED, "adjustment_set": adjustment}
            )
            estimate = None
            refutations: tuple[DoWhyRefutationResult, ...] = ()
            estimator_method = None
            if execution.configuration.run_estimation:
                try:
                    estimate, refutations = self._estimate(
                        backend, execution, table, graph, adjustment
                    )
                    estimator_method = "backdoor.linear_regression"
                except AdapterError as error:
                    return self._failed(execution, evidence, provenance, error.code, str(error))
            recorded = DoWhyAdapterProvenance(
                dowhy_version=backend.version,
                python_version=platform.python_version(),
                graph_fingerprint=fingerprint,
                estimator_method=estimator_method,
            )
            return DoWhyAnalysisResult(
                execution_request=execution,
                status=DoWhyOperationStatus.COMPLETED,
                identification=evidence,
                estimate=estimate,
                refutations=refutations,
                adapter_provenance=recorded,
                provenance=provenance,
            )
        except AdapterError as error:
            return self._failed(execution, evidence, provenance, error.code, str(error))
        except Exception:
            return self._failed(
                execution,
                evidence,
                provenance,
                DoWhyFailureCode.IDENTIFICATION_FAILURE,
                "DoWhy identification failed.",
                status=DoWhyOperationStatus.ERROR,
            )

    @staticmethod
    def _validate(execution: DoWhyExecutionRequest) -> tuple[str, str] | None:
        source = execution.identification_result
        checked = CausalIdentificationService().identify(
            ObservationalAnalysisRequest(
                request_id=source.request_id,
                identification=source.identification_request,
            )
        )
        if (
            source.status is not IdentificationStatus.IDENTIFIED
            or checked.status is not IdentificationStatus.IDENTIFIED
        ):
            return (
                DoWhyFailureCode.INVALID_IDENTIFICATION,
                "An identified causal contract is required.",
            )
        if source.causal_graph is None:
            return (DoWhyFailureCode.INVALID_GRAPH, "An explicit causal graph is required.")
        estimand = source.estimand
        if (
            estimand is None
            or estimand.estimand_type is not CausalEstimandKind.ATE
            or estimand.effect_scale is not EffectScale.MEAN_DIFFERENCE
        ):
            return (DoWhyFailureCode.UNSUPPORTED_ESTIMAND, "Only mean-difference ATE is supported.")
        return None

    @staticmethod
    def _scalar(value: object) -> float:
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise AdapterError(
                DoWhyFailureCode.MALFORMED_DOWHY_RESULT,
                "DoWhy returned a malformed scalar result.",
            ) from None
        if not math.isfinite(number):
            raise AdapterError(
                DoWhyFailureCode.NONFINITE_ESTIMATE,
                "DoWhy returned a non-finite estimate.",
            )
        return number

    def _estimate(
        self,
        backend: dependency.DoWhyBackend,
        execution: DoWhyExecutionRequest,
        table: AnalysisTable | None,
        graph: Any,
        adjustment: tuple[str, ...],
    ) -> tuple[DoWhyEstimateEvidence, tuple[DoWhyRefutationResult, ...]]:
        if table is None:
            raise AdapterError(DoWhyFailureCode.INVALID_DATA, "Estimation requires analysis data.")
        binding = execution.binding
        required = (
            binding.treatment_column,
            binding.outcome_column,
            *(item.column for item in binding.covariates),
        )
        if any(column not in table.columns for column in required):
            raise AdapterError(DoWhyFailureCode.INVALID_DATA, "A required data column is missing.")
        frame = pd.DataFrame(table.rows, columns=table.columns)
        try:
            treatment = frame[binding.treatment_column]
            if not set(treatment.unique()).issubset({0, 1}) or len(set(treatment.unique())) != 2:
                raise AdapterError(
                    DoWhyFailureCode.INVALID_DATA,
                    "Treatment must contain binary control and treated arms.",
                )
            numeric = frame[[binding.outcome_column, *(item.column for item in binding.covariates)]]
            if not all(math.isfinite(float(value)) for value in numeric.to_numpy().reshape(-1)):
                raise AdapterError(DoWhyFailureCode.INVALID_DATA, "Analysis values must be finite.")
            source = execution.identification_result
            assert source.treatment is not None
            assert source.outcome is not None
            model = backend.CausalModel(
                data=frame,
                treatment=source.treatment.treatment_variable,
                outcome=source.outcome.variable_id,
                graph=to_networkx(graph),
                estimand_type="nonparametric-ate",
                proceed_when_unidentifiable=False,
                missing_nodes_as_confounders=False,
                identify_vars=False,
            )
            identified = model.identify_effect(
                method_name="default", proceed_when_unidentifiable=False, optimize_backdoor=False
            )
            raw = model.estimate_effect(
                identified,
                method_name="backdoor.linear_regression",
                control_value=0,
                treatment_value=1,
                confidence_intervals=False,
                test_significance=False,
                target_units="ate",
                method_params={"need_conditional_estimates": False},
            )
        except AdapterError:
            raise
        except Exception:
            raise AdapterError(
                DoWhyFailureCode.ESTIMATION_FAILURE, "DoWhy estimation failed."
            ) from None
        point = self._scalar(getattr(raw, "value", None))
        estimate = DoWhyEstimateEvidence(point_estimate=point, adjustment_set=adjustment)
        return estimate, self._refute(model, identified, raw, execution)

    def _refute(
        self, model: Any, identified: Any, estimate: Any, execution: DoWhyExecutionRequest
    ) -> tuple[DoWhyRefutationResult, ...]:
        config = execution.configuration
        results: list[DoWhyRefutationResult] = []
        for method in config.refuters:
            kwargs: dict[str, object] = {
                "random_seed": config.seed,
                "num_simulations": config.num_simulations,
                "n_jobs": 1,
                "show_progress_bar": False,
            }
            if method is DoWhyRefuterMethod.PLACEBO:
                kwargs["placebo_type"] = "permute"
            elif method is DoWhyRefuterMethod.DATA_SUBSET:
                kwargs["subset_fraction"] = config.subset_fraction
            try:
                raw = model.refute_estimate(
                    identified, estimate, method_name=method.value, **kwargs
                )
                original = self._scalar(getattr(raw, "estimated_effect", None))
                new = self._scalar(getattr(raw, "new_effect", None))
                delta = new - original
                details = getattr(raw, "refutation_result", None)
                p_value = None
                if isinstance(details, dict) and details.get("p_value") is not None:
                    p_value = self._scalar(details["p_value"])
                    if not 0 <= p_value <= 1:
                        raise AdapterError(
                            DoWhyFailureCode.MALFORMED_DOWHY_RESULT,
                            "DoWhy returned an invalid refuter p-value.",
                        )
                stable = (
                    abs(new) <= max(0.1, abs(original) * 0.25)
                    if method is DoWhyRefuterMethod.PLACEBO
                    else abs(delta) <= max(0.1, abs(original) * 0.1)
                )
                interpretation = (
                    f"The estimate was {'stable' if stable else 'sensitive'} under the "
                    f"configured {method.value} perturbation; this does not establish "
                    "causal validity."
                )
                results.append(
                    DoWhyRefutationResult(
                        method=method,
                        status=DoWhyRefuterStatus.PASS if stable else DoWhyRefuterStatus.WARNING,
                        seed=config.seed,
                        num_simulations=config.num_simulations,
                        subset_fraction=(
                            config.subset_fraction
                            if method is DoWhyRefuterMethod.DATA_SUBSET
                            else None
                        ),
                        original_estimate=original,
                        new_estimate=new,
                        delta=delta,
                        p_value=p_value,
                        interpretation=interpretation,
                    )
                )
            except AdapterError:
                raise
            except Exception:
                raise AdapterError(
                    DoWhyFailureCode.REFUTER_FAILURE, "DoWhy refutation failed."
                ) from None
        return tuple(results)

    @staticmethod
    def _failed(
        execution: DoWhyExecutionRequest,
        evidence: DoWhyIdentificationEvidence,
        provenance: ProvenanceRecords,
        code: str,
        message: str,
        *,
        status: DoWhyOperationStatus = DoWhyOperationStatus.ABSTAINED,
    ) -> DoWhyAnalysisResult:
        reason = DoWhyAbstentionReason(code=DoWhyFailureCode(code), message=message)
        return DoWhyAnalysisResult(
            execution_request=execution,
            status=status,
            identification=evidence,
            diagnostics=(DoWhyDiagnostic(code=code, message=message),),
            provenance=provenance,
            abstention_reason=reason,
        )
