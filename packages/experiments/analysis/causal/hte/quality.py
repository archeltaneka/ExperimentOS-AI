"""Policy-compatible safety checks for heterogeneous-effect results."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import Field

from ...base import ContractModel, NonEmptyStr
from ..propensity import OverlapStatus
from ..variables import MeasurementTiming
from .models import HTEPreSpecificationStatus
from .results import (
    HeterogeneousEffectResult,
    HTEEvidenceStatus,
    HTEStatus,
    HTESubgroupStatus,
)


class HTEQualityFindingSeverity(StrEnum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"


class HTEQualityPolicy(ContractModel):
    """Central review thresholds; estimator eligibility thresholds remain in HTEConfig."""

    wide_interval_width: Annotated[float, Field(strict=True, gt=0)] = 10.0
    substantial_attrition_rate: Annotated[float, Field(strict=True, gt=0, lt=1)] = 0.20
    multiplicity_advisory_test_count: Annotated[int, Field(strict=True, gt=0)] = 5


class HTEQualityFinding(ContractModel):
    code: NonEmptyStr
    severity: HTEQualityFindingSeverity
    message: NonEmptyStr
    subgroup_id: NonEmptyStr | None = None


class HTEQualityAssessment(ContractModel):
    blocking_findings: tuple[HTEQualityFinding, ...]
    advisory_findings: tuple[HTEQualityFinding, ...]


def evaluate_hte_quality(
    result: HeterogeneousEffectResult,
    *,
    policy: HTEQualityPolicy | None = None,
) -> HTEQualityAssessment:
    """Evaluate claim-safety invariants without inspecting or emitting row-level data."""
    policy = policy or HTEQualityPolicy()
    blocking: list[HTEQualityFinding] = []
    advisory: list[HTEQualityFinding] = []
    conclusive = result.status is HTEStatus.COMPLETED

    if conclusive and result.modifier.measurement_timing is not MeasurementTiming.PRE_TREATMENT:
        blocking.append(
            _blocking(
                "hte.quality.post_treatment_modifier",
                "Conclusive HTE used a modifier that was not measured pre-treatment.",
            )
        )
    if (
        conclusive
        and result.analysis_semantics is not HTEPreSpecificationStatus.CONFIRMATORY_PRE_SPECIFIED
    ):
        blocking.append(
            _blocking(
                "hte.quality.exploratory_presented_as_confirmatory",
                "Exploratory or data-mined segmentation was presented conclusively.",
            )
        )
    completed = tuple(
        subgroup
        for subgroup in result.subgroup_results
        if subgroup.status is HTESubgroupStatus.COMPLETED
    )
    if (
        conclusive
        and len(completed) >= 2
        and result.global_heterogeneity.status is not HTEEvidenceStatus.AVAILABLE
    ):
        blocking.append(
            _blocking(
                "hte.quality.direct_evidence_missing",
                "Conclusive heterogeneity analysis lacks a direct global comparison.",
            )
        )

    config = result.execution_request.configuration
    for subgroup in completed:
        counts = subgroup.sample_counts
        if (
            counts.retained_count < config.minimum_subgroup_retained
            or counts.treated_count < config.minimum_subgroup_treated
            or counts.control_count < config.minimum_subgroup_control
        ):
            blocking.append(
                _blocking(
                    "hte.quality.sparse_group_conclusive",
                    "A sparse subgroup was presented conclusively.",
                    subgroup.subgroup_id,
                )
            )
        if subgroup.overlap is not None and subgroup.overlap.status is OverlapStatus.SEVERE:
            blocking.append(
                _blocking(
                    "hte.quality.failed_overlap_conclusive",
                    "A subgroup with severe overlap failure was presented conclusively.",
                    subgroup.subgroup_id,
                )
            )
        if any(
            item is None
            for item in (
                subgroup.estimate,
                subgroup.standard_error,
                subgroup.confidence_interval,
                subgroup.uncertainty_method,
            )
        ):
            blocking.append(
                _blocking(
                    "hte.quality.uncertainty_missing",
                    "A conclusive subgroup effect lacks complete uncertainty.",
                    subgroup.subgroup_id,
                )
            )
        if subgroup.overlap is not None and subgroup.overlap.status is OverlapStatus.WEAK:
            advisory.append(
                _advisory(
                    "hte.quality.weak_subgroup_overlap",
                    "Subgroup overlap is weak.",
                    subgroup.subgroup_id,
                )
            )
        if (
            subgroup.confidence_interval is not None
            and subgroup.confidence_interval.upper - subgroup.confidence_interval.lower
            > policy.wide_interval_width
        ):
            advisory.append(
                _advisory(
                    "hte.quality.wide_subgroup_interval",
                    "Subgroup uncertainty exceeds the configured review width.",
                    subgroup.subgroup_id,
                )
            )
        if (
            counts.raw_count
            and counts.dropped_count / counts.raw_count >= policy.substantial_attrition_rate
        ):
            advisory.append(
                _advisory(
                    "hte.quality.substantial_subgroup_attrition",
                    "Subgroup attrition meets the configured review threshold.",
                    subgroup.subgroup_id,
                )
            )

    repeated_tests = (
        result.multiplicity.subgroup_effect_tests
        + result.multiplicity.interaction_tests
        + result.multiplicity.pairwise_tests
    )
    if repeated_tests >= policy.multiplicity_advisory_test_count:
        advisory.append(
            _advisory(
                "hte.quality.multiplicity_burden",
                "The number of repeated tests meets the configured review threshold.",
            )
        )

    def ordering(item: HTEQualityFinding) -> tuple[str, str]:
        return item.code, item.subgroup_id or ""

    return HTEQualityAssessment(
        blocking_findings=tuple(sorted(blocking, key=ordering)),
        advisory_findings=tuple(sorted(advisory, key=ordering)),
    )


def _blocking(code: str, message: str, subgroup_id: str | None = None) -> HTEQualityFinding:
    return HTEQualityFinding(
        code=code,
        severity=HTEQualityFindingSeverity.BLOCKING,
        message=message,
        subgroup_id=subgroup_id,
    )


def _advisory(code: str, message: str, subgroup_id: str | None = None) -> HTEQualityFinding:
    return HTEQualityFinding(
        code=code,
        severity=HTEQualityFindingSeverity.ADVISORY,
        message=message,
        subgroup_id=subgroup_id,
    )


__all__ = [
    "HTEQualityAssessment",
    "HTEQualityFinding",
    "HTEQualityFindingSeverity",
    "HTEQualityPolicy",
    "evaluate_hte_quality",
]
