"""Central contract and implementation capability inventory."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from ..requests import AnalysisRequest
from ..study_designs import (
    ObservationalAnalysisMethod,
    QuasiExperimentalMethod,
    RandomizedAnalysisMethod,
)
from .models import (
    MethodContractStatus,
    MethodImplementationStatus,
    MethodSupportAssessment,
)

type DesignType = Literal[
    "randomized_experiment",
    "quasi_experimental",
    "observational_study",
]
type AnalysisMethod = (
    RandomizedAnalysisMethod | QuasiExperimentalMethod | ObservationalAnalysisMethod
)
type CapabilityKey = tuple[str, str]


@dataclass(frozen=True, slots=True)
class MethodCapability:
    """One method's contract recognition and estimator availability."""

    design_type: DesignType
    method: str
    contract_status: MethodContractStatus
    implementation_status: MethodImplementationStatus

    @property
    def key(self) -> CapabilityKey:
        """Return the design-qualified method identity."""
        return (self.design_type, self.method)


@dataclass(frozen=True, slots=True)
class MethodCapabilityRegistry:
    """Immutable design-qualified method capability registry."""

    entries: tuple[MethodCapability, ...]

    def __post_init__(self) -> None:
        normalized_entries = tuple(self.entries)
        object.__setattr__(self, "entries", normalized_entries)
        keys = tuple(entry.key for entry in normalized_entries)
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate method capability entries are not allowed")

    @classmethod
    def default(cls) -> MethodCapabilityRegistry:
        """Build the complete Phase 4 inventory with no estimators available."""
        return cls._build(implemented=frozenset())

    @classmethod
    def with_implemented_methods(
        cls,
        methods: Iterable[AnalysisMethod],
    ) -> MethodCapabilityRegistry:
        """Build the full inventory while declaring selected implementations available."""
        implemented = frozenset(_method_key(method) for method in methods)
        return cls._build(implemented=implemented)

    @classmethod
    def _build(cls, *, implemented: frozenset[CapabilityKey]) -> MethodCapabilityRegistry:
        entries = tuple(
            MethodCapability(
                design_type=design_type,
                method=method.value,
                contract_status=MethodContractStatus.SUPPORTED,
                implementation_status=(
                    MethodImplementationStatus.AVAILABLE
                    if (design_type, method.value) in implemented
                    else MethodImplementationStatus.UNAVAILABLE
                ),
            )
            for design_type, method_type in _METHOD_FAMILIES
            for method in method_type
        )
        return cls(entries=entries)

    def for_request(self, request: AnalysisRequest) -> MethodCapability:
        """Return the design-qualified capability for a validated request contract."""
        key = (request.study_design.design_type, request.study_design.method.value)
        for entry in self.entries:
            if entry.key == key:
                return entry
        raise LookupError(f"method capability registry has no entry for {key!r}")

    def assess(
        self,
        request: AnalysisRequest,
        *,
        data_eligible: bool,
    ) -> MethodSupportAssessment:
        """Combine registry truth with a separately computed data-eligibility decision."""
        capability = self.for_request(request)
        executable = (
            capability.contract_status is MethodContractStatus.SUPPORTED
            and capability.implementation_status is MethodImplementationStatus.AVAILABLE
            and data_eligible
        )
        return MethodSupportAssessment(
            requested_method=capability.method,
            contract_status=capability.contract_status,
            implementation_status=capability.implementation_status,
            data_eligible=data_eligible,
            executable=executable,
        )


_METHOD_FAMILIES: tuple[
    tuple[DesignType, type[RandomizedAnalysisMethod]],
    tuple[DesignType, type[QuasiExperimentalMethod]],
    tuple[DesignType, type[ObservationalAnalysisMethod]],
] = (
    ("randomized_experiment", RandomizedAnalysisMethod),
    ("quasi_experimental", QuasiExperimentalMethod),
    ("observational_study", ObservationalAnalysisMethod),
)


def _method_key(method: AnalysisMethod) -> CapabilityKey:
    method_type = type(method)
    for design_type, candidate_type in _METHOD_FAMILIES:
        if method_type is candidate_type:
            return (design_type, method.value)
    raise TypeError(f"unsupported analysis method enum: {method!r}")
