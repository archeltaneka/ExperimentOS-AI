"""Owned immutable dispatch inventory, not estimator selection."""

from collections.abc import Callable
from dataclasses import dataclass

from packages.observability.base import BaseObservabilityProvider

from .datasets import AnalysisDataResolver
from .dispatch_causal import (
    dispatch_did,
    dispatch_dml,
    dispatch_hte,
    dispatch_ipw,
    dispatch_propensity,
)
from .dispatch_optional import dispatch_dowhy, dispatch_econml_dml, dispatch_econml_hte
from .dispatch_randomized import (
    dispatch_bayesian,
    dispatch_cuped,
    dispatch_fixed_horizon,
    dispatch_sequential,
)
from .requests import WorkflowAnalysisRequest
from .results import OwnedAnalysisResult

type AnalysisHandler = Callable[
    [WorkflowAnalysisRequest, AnalysisDataResolver, BaseObservabilityProvider], OwnedAnalysisResult
]


@dataclass(frozen=True)
class MethodRegistration:
    method_id: str
    capability: str
    design: str
    estimands: tuple[str, ...]
    required_inputs: tuple[str, ...]
    handler: AnalysisHandler
    implementation_version: str = "1"
    optional_dependency: str | None = None
    workflow_eligible: bool = True


@dataclass(frozen=True)
class AnalysisMethodRegistry:
    entries: tuple[MethodRegistration, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(self.entries))
        if len(self.method_ids) != len(set(self.method_ids)):
            raise ValueError("duplicate analysis method registration")

    @property
    def method_ids(self) -> tuple[str, ...]:
        return tuple(entry.method_id for entry in self.entries)

    def resolve(self, method: str) -> MethodRegistration | None:
        return next((entry for entry in self.entries if entry.method_id == method), None)


def default_registry() -> AnalysisMethodRegistry:
    return AnalysisMethodRegistry(
        (
            MethodRegistration(
                "econml_dml",
                "observational",
                "observational",
                ("ate",),
                ("analysis_request", "dataset", "adapter_configuration"),
                dispatch_econml_dml,
                optional_dependency="econml",
            ),
            MethodRegistration(
                "econml_hte",
                "heterogeneity",
                "observational",
                ("cate",),
                ("analysis_request", "dataset", "modifier", "adapter_configuration"),
                dispatch_econml_hte,
                optional_dependency="econml",
            ),
            MethodRegistration(
                "dowhy",
                "causal_evidence",
                "observational",
                ("ate",),
                ("analysis_request", "configuration"),
                dispatch_dowhy,
                optional_dependency="dowhy",
            ),
            MethodRegistration(
                "did",
                "observational",
                "difference_in_differences",
                ("did_att",),
                ("execution", "dataset"),
                dispatch_did,
            ),
            MethodRegistration(
                "propensity_diagnostics",
                "diagnostics",
                "observational",
                ("ate", "att"),
                ("execution", "dataset"),
                dispatch_propensity,
            ),
            MethodRegistration(
                "ipw_ate",
                "observational",
                "observational",
                ("ate",),
                ("analysis_request", "dataset", "propensity_binding"),
                dispatch_ipw,
            ),
            MethodRegistration(
                "ipw_att",
                "observational",
                "observational",
                ("att",),
                ("analysis_request", "dataset", "propensity_binding"),
                dispatch_ipw,
            ),
            MethodRegistration(
                "dml",
                "observational",
                "observational",
                ("ate",),
                ("analysis_request", "dataset"),
                dispatch_dml,
            ),
            MethodRegistration(
                "hte",
                "heterogeneity",
                "observational",
                ("cate",),
                ("analysis_request", "dataset", "modifier"),
                dispatch_hte,
            ),
            MethodRegistration(
                method_id="randomized_fixed_horizon",
                capability="randomized",
                design="randomized_experiment",
                estimands=(
                    "difference_in_means",
                    "difference_in_proportions",
                    "intention_to_treat",
                ),
                required_inputs=("execution", "binding", "dataset"),
                handler=dispatch_fixed_horizon,
            ),
            MethodRegistration(
                "cuped",
                "randomized",
                "randomized_experiment",
                ("difference_in_means",),
                ("execution", "binding", "dataset"),
                dispatch_cuped,
            ),
            MethodRegistration(
                "bayesian_ab",
                "randomized",
                "randomized_experiment",
                ("difference_in_means", "difference_in_proportions"),
                ("execution", "binding", "dataset"),
                dispatch_bayesian,
            ),
            MethodRegistration(
                "sequential",
                "randomized",
                "randomized_experiment",
                ("difference_in_means", "difference_in_proportions"),
                ("plan", "looks"),
                dispatch_sequential,
            ),
        )
    )
