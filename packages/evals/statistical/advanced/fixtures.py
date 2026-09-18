"""Versioned advanced references and public execution fixtures."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel

from packages.experiments.analysis.causal.advanced.models import AdvancedEstimatorConfig
from packages.experiments.analysis.causal.dml.service import DoubleMachineLearningEstimator
from packages.experiments.analysis.causal.hte.service import HeterogeneousEffectEstimator
from packages.observability.base import BaseObservabilityProvider

from ..models import StatisticalReferenceCase
from .audit import record_nuisance_calls
from .references.causal import provenance
from .references.dml import dml_execution, dml_identification, dml_table
from .references.dowhy import execution as dowhy_execution
from .references.dowhy import known_effect_table
from .references.econml import dr_execution, linear_rows
from .references.hte import effect_rows, hte_execution, hte_modifier, hte_table
from .registry import REGISTRY


def reference_cases() -> tuple[StatisticalReferenceCase, ...]:
    """Load the same checked-in companion consumed by the default Phase 4 command."""
    from pathlib import Path

    from ..dataset import load_statistical_reference_cases

    path = Path(__file__).resolve().parents[4] / "data/eval/phase4_advanced_conformance.json"
    return load_statistical_reference_cases(path).cases


@dataclass
class Execution:
    result: BaseModel
    request: BaseModel
    configuration: AdvancedEstimatorConfig | None
    records: tuple
    nuisance_calls: tuple = ()


def prepare_case(case: StatisticalReferenceCase, seed: int | None = None):
    from packages.experiments.analysis.causal.dowhy.models import DoWhyConfig, DoWhyRefuterMethod
    from packages.experiments.analysis.causal.variables import MeasurementTiming

    details = case.advanced
    assert details is not None
    capability = REGISTRY[details.capability_id]
    scenario = details.scenario
    seed = details.seed if seed is None else seed
    config = None
    if capability.capability_id.startswith("dowhy"):
        refuters = (
            (DoWhyRefuterMethod(capability.method),)
            if capability.capability_id in {"dowhy_placebo", "dowhy_common_cause", "dowhy_subset"}
            else ()
        )
        request = dowhy_execution(
            latent=scenario == "unidentified",
            run_estimation=capability.capability_id != "dowhy_identification",
        )
        request = request.model_copy(
            update={
                "configuration": DoWhyConfig(
                    seed=seed,
                    run_estimation=request.configuration.run_estimation,
                    num_simulations=5,
                    refuters=refuters,
                )
            }
        )
        if scenario == "missing_graph":
            request = request.model_copy(
                update={
                    "identification_result": request.identification_result.model_copy(
                        update={"causal_graph": None}
                    )
                }
            )
        table = known_effect_table() if request.configuration.run_estimation else None
    elif "hte" in capability.capability_id:
        factory = dr_execution if capability.dependency else hte_execution
        request = factory(fold_count=4, seed=seed)
        if scenario == "invalid_modifier":
            request = request.model_copy(
                update={"modifier": hte_modifier(timing=MeasurementTiming.POST_TREATMENT)}
            )
        if scenario == "sparse":
            request = request.model_copy(
                update={
                    "configuration": request.configuration.model_copy(
                        update={"minimum_subgroup_retained": 1000}
                    )
                }
            )
        table = hte_table(
            effect_rows(effects=(("ID", 2.0), ("SG", 2.0)))
            if scenario == "homogeneous"
            else effect_rows()
        )
    else:
        request = dml_execution(fold_count=4, seed=seed)
        if scenario == "invalid":
            request = request.model_copy(
                update={
                    "identification_result": dml_identification(
                        adjustment_timing=MeasurementTiming.POST_TREATMENT
                    )
                }
            )
        if scenario == "degenerate":
            request = request.model_copy(
                update={
                    "configuration": request.configuration.model_copy(
                        update={"treatment_residual_tolerance": 1000.0}
                    )
                }
            )
        table = dml_table(linear_rows(0.0 if scenario == "null" else 2.0))
    if capability.dependency == "econml":
        config = AdvancedEstimatorConfig(
            constant_effect_assumption=True,
            inference_mode="bootstrap"
            if scenario == "unsupported_inference"
            else "statsmodels_hc1",
        )
    return request, table, config


class FailingModel:
    """A deterministic third-party fit failure, independent of library availability."""

    def __init__(self, **kwargs):
        pass

    def fit(self, *args, **kwargs):
        raise RuntimeError("private-array-canary [9.87654321] unit-secret")


class DoWhyModel:
    """Controlled DoWhy operation failures; real success uses the actual library."""

    def __init__(self, *, scenario, **kwargs):
        self.scenario = scenario
        if scenario == "runtime_failure":
            raise RuntimeError("private-graph-canary")

    def identify_effect(self, **kwargs):
        if self.scenario == "malformed":
            return SimpleNamespace()
        return SimpleNamespace(
            estimands={"backdoor": None if self.scenario == "unidentified" else {}},
            default_backdoor_id=None if self.scenario == "unidentified" else "backdoor",
            get_adjustment_set=lambda method: (
                ["contradiction"] if self.scenario == "contradictory_graph" else ["prior_orders"]
            ),
        )

    def estimate_effect(self, *args, **kwargs):
        if self.scenario == "estimation_failure":
            raise RuntimeError("private-array-canary")
        return SimpleNamespace(value=float("nan") if self.scenario == "nonfinite" else 2.0)

    def refute_estimate(self, *args, **kwargs):
        raise RuntimeError("private-graph-canary")


def run_case(case: StatisticalReferenceCase, provider: BaseObservabilityProvider) -> Execution:
    """Run the existing public boundary with scoped, explicitly labelled failure doubles."""
    from packages.experiments.analysis.causal.dml import numerics
    from packages.experiments.analysis.causal.dml.adapter import SklearnRidgeOutcomeAdapter
    from packages.experiments.analysis.causal.dowhy import dependency as dd
    from packages.experiments.analysis.causal.dowhy.adapter import DoWhyAdapter
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter, EconMLHTEAdapter
    from packages.experiments.analysis.causal.econml import dependency as ed

    assert case.advanced is not None
    capability = REGISTRY[case.advanced.capability_id]
    scenario = case.advanced.scenario
    request, table, config = prepare_case(case)
    with ExitStack() as stack:
        calls = record_nuisance_calls(stack) if capability.dependency is None else []
        if capability.dependency == "econml" and scenario in {
            "inference_failure",
            "malformed",
            "nonfinite",
        }:
            try:
                real = ed.load_econml()
            except ed.AdapterError:
                real = None  # Public call below must produce the actual dependency refusal.
            if real is not None:
                estimator_type = (
                    real.dr.LinearDRLearner
                    if "hte" in capability.capability_id
                    else real.dml.LinearDML
                )
                if scenario == "inference_failure":
                    stack.enter_context(
                        patch.object(
                            estimator_type,
                            "effect_inference",
                            side_effect=RuntimeError("private-array-canary"),
                        )
                    )
                elif scenario == "malformed":
                    stack.enter_context(
                        patch.object(estimator_type, "effect_inference", return_value=object())
                    )
                else:
                    import numpy as np

                    info = SimpleNamespace(
                        point_estimate=np.asarray([float("nan")]), stderr=np.asarray([0.1])
                    )
                    stack.enter_context(
                        patch.object(estimator_type, "effect_inference", return_value=info)
                    )
        if scenario == "absent":
            dependency = ed if capability.dependency == "econml" else dd
            name = "load_econml" if capability.dependency == "econml" else "load_dowhy"
            stack.enter_context(
                patch.object(
                    dependency,
                    name,
                    side_effect=dependency.AdapterError(
                        "OPTIONAL_DEPENDENCY_UNAVAILABLE", "Optional package is absent."
                    ),
                )
            )
        if capability.dependency == "econml" and scenario == "runtime_failure":
            backend = ed.EconMLBackend(
                dml=SimpleNamespace(LinearDML=FailingModel),
                dr=SimpleNamespace(LinearDRLearner=FailingModel),
                inference=SimpleNamespace(
                    StatsModelsInference=lambda **kwargs: None,
                    StatsModelsInferenceDiscrete=lambda **kwargs: None,
                ),
                version="0.17.0",
            )
            stack.enter_context(patch.object(ed, "load_econml", return_value=backend))
        if capability.dependency == "dowhy" and scenario in {
            "runtime_failure",
            "malformed",
            "unidentified",
            "contradictory_graph",
            "refuter_failure",
            "nonfinite",
            "estimation_failure",
        }:
            backend = dd.DoWhyBackend(
                CausalModel=lambda **kw: DoWhyModel(scenario=scenario, **kw), version="0.14"
            )
            stack.enter_context(patch.object(dd, "load_dowhy", return_value=backend))
        if capability.dependency is None and scenario == "runtime_failure":
            stack.enter_context(
                patch.object(
                    SklearnRidgeOutcomeAdapter,
                    "fit",
                    side_effect=RuntimeError("private-array-canary"),
                )
            )
        if scenario == "overlap":
            original = numerics.assess_dml_overlap

            def severe(**kwargs):
                from packages.experiments.analysis.causal.propensity import OverlapStatus

                return original(**kwargs).model_copy(update={"status": OverlapStatus.SEVERE})

            module = "hte" if "hte" in capability.capability_id else "dml"
            stack.enter_context(
                patch(
                    f"packages.experiments.analysis.causal.{module}.service.assess_dml_overlap",
                    severe,
                )
            )
        adapter = {
            "repository_dml": lambda: DoubleMachineLearningEstimator(
                observability_provider=provider
            ),
            "repository_hte": lambda: HeterogeneousEffectEstimator(observability_provider=provider),
            "econml_dml": lambda: EconMLDMLAdapter(
                configuration=config, observability_provider=provider
            ),
            "econml_hte": lambda: EconMLHTEAdapter(
                configuration=config, observability_provider=provider
            ),
        }.get(capability.capability_id, lambda: DoWhyAdapter(observability_provider=provider))()
        result = adapter.analyze(request, table, provenance=provenance("advanced-conformance-v1"))
    return Execution(result, request, config, tuple(provider.records), tuple(calls))
