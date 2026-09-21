"""Owned immutable dispatch inventory, not estimator selection."""

from collections.abc import Callable
from dataclasses import dataclass

from packages.observability.base import BaseObservabilityProvider

from .datasets import AnalysisDataResolver
from .dispatch_randomized import dispatch_fixed_horizon
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
        )
    )
