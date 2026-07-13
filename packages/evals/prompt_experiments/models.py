from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PromptExperimentStatus = Literal[
    "draft",
    "validated",
    "running",
    "completed",
    "cancelled",
    "archived",
]
AssignmentStrategy = Literal["fixed", "deterministic_hash", "dataset_alternating"]
RandomizationUnit = Literal["dataset_case", "explicit_runtime_key"]
RecommendationOutcome = Literal[
    "recommend_treatment",
    "retain_control",
    "inconclusive",
    "invalid_experiment",
]


@dataclass(frozen=True)
class PromptExperimentDefinition:
    experiment_id: str
    name: str
    description: str
    prompt_id: str
    control_version: str
    treatment_versions: tuple[str, ...]
    hypothesis: str
    primary_metric: str
    secondary_metrics: tuple[str, ...]
    guardrail_metrics: tuple[str, ...]
    dataset_id: str
    assignment_strategy: AssignmentStrategy
    allocation: dict[str, float]
    randomization_unit: RandomizationUnit
    seed: str
    status: PromptExperimentStatus
    allow_deprecated_versions: bool = False
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "treatment_versions", tuple(self.treatment_versions))
        object.__setattr__(self, "secondary_metrics", tuple(self.secondary_metrics))
        object.__setattr__(self, "guardrail_metrics", tuple(self.guardrail_metrics))
        object.__setattr__(self, "allocation", dict(self.allocation))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True)
class AssignedPromptVariant:
    experiment_id: str
    variant: str
    prompt_id: str
    prompt_version: str
    assignment_strategy: AssignmentStrategy
    assignment_key_hash: str
    allocation: dict[str, float]


@dataclass(frozen=True)
class PromptExperimentContext:
    experiment_id: str
    variant: str
    prompt_id: str
    prompt_version: str
    assignment_strategy: AssignmentStrategy
    assignment_key_hash: str
    allocation: dict[str, float]


@dataclass(frozen=True)
class PromptExperimentExposure:
    experiment_id: str
    variant: str
    prompt_id: str
    prompt_version: str
    assignment_key_hash: str
    trace_id: str
    timestamp: str
    execution_mode: str


@dataclass(frozen=True)
class PromptExperimentVariantResult:
    variant: str
    prompt_version: str
    sample_size: int
    metrics: dict[str, float]
    factuality_findings: dict[str, int]
    regression_findings: dict[str, int]
    latency_ms: float
    passed: bool


@dataclass(frozen=True)
class PromptExperimentRecommendation:
    outcome: RecommendationOutcome
    variant: str | None
    reasons: tuple[str, ...]
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class PromptExperimentReport:
    experiment_id: str
    name: str
    description: str
    prompt_id: str
    control_version: str
    treatment_versions: tuple[str, ...]
    dataset_id: str
    hypothesis: str
    primary_metric: str
    secondary_metrics: tuple[str, ...]
    guardrail_metrics: tuple[str, ...]
    assignment_strategy: AssignmentStrategy
    variants: dict[str, PromptExperimentVariantResult]
    metric_deltas: dict[str, dict[str, float]]
    recommendation: PromptExperimentRecommendation
    limitations: tuple[str, ...]
    validity_status: str
    config_fingerprint: dict[str, object]
    production_traffic_involved: bool = False
