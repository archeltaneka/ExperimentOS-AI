"""Quality-policy checks for heterogeneous-effect result safety."""

from __future__ import annotations

from packages.experiments.analysis.causal.hte import (
    HTEEvidenceStatus,
    HTEPreSpecificationStatus,
    HTESubgroupStatus,
)
from packages.experiments.analysis.causal.hte.quality import (
    HTEQualityFindingSeverity,
    evaluate_hte_quality,
)
from packages.experiments.analysis.causal.hte.service import HeterogeneousEffectEstimator
from packages.experiments.analysis.causal.propensity import OverlapStatus
from tests.causal_identification_fixtures import provenance
from tests.hte_fixtures import effect_rows, hte_execution, hte_table


def _completed_result():
    return HeterogeneousEffectEstimator().analyze(
        hte_execution(fold_count=4),
        hte_table(effect_rows()),
        provenance=provenance("hte-quality"),
    )


def test_quality_accepts_complete_confirmatory_result() -> None:
    assessment = evaluate_hte_quality(_completed_result())

    assert assessment.blocking_findings == ()


def test_quality_blocks_claim_without_direct_heterogeneity_evidence() -> None:
    result = _completed_result()
    unavailable = result.global_heterogeneity.model_copy(
        update={
            "status": HTEEvidenceStatus.UNAVAILABLE,
            "statistic": None,
            "degrees_of_freedom": None,
            "p_value": None,
            "detected": None,
            "unavailable_reason": "removed by fixture",
        }
    )

    assessment = evaluate_hte_quality(
        result.model_copy(update={"global_heterogeneity": unavailable})
    )

    assert "hte.quality.direct_evidence_missing" in {
        item.code for item in assessment.blocking_findings
    }


def test_quality_blocks_exploratory_result_presented_conclusively() -> None:
    result = _completed_result()

    assessment = evaluate_hte_quality(
        result.model_copy(update={"analysis_semantics": HTEPreSpecificationStatus.EXPLORATORY})
    )

    assert "hte.quality.exploratory_presented_as_confirmatory" in {
        item.code for item in assessment.blocking_findings
    }


def test_quality_blocks_sparse_or_failed_overlap_subgroup_with_estimate() -> None:
    result = _completed_result()
    subgroup = result.subgroup_results[0]
    unsafe = subgroup.model_copy(
        update={
            "status": HTESubgroupStatus.COMPLETED,
            "sample_counts": subgroup.sample_counts.model_copy(
                update={"retained_count": 4, "treated_count": 2, "control_count": 2}
            ),
            "overlap": subgroup.overlap.model_copy(update={"status": OverlapStatus.SEVERE}),
        }
    )

    assessment = evaluate_hte_quality(
        result.model_copy(update={"subgroup_results": (unsafe, *result.subgroup_results[1:])})
    )

    codes = {item.code for item in assessment.blocking_findings}
    assert "hte.quality.sparse_group_conclusive" in codes
    assert "hte.quality.failed_overlap_conclusive" in codes


def test_quality_advisories_are_explicit_and_deterministically_ordered() -> None:
    result = _completed_result()
    first = result.subgroup_results[0]
    wide = first.model_copy(
        update={
            "sample_counts": first.sample_counts.model_copy(
                update={"raw_count": 200, "retained_count": 100, "dropped_count": 100}
            ),
            "confidence_interval": first.confidence_interval.model_copy(
                update={"lower": -20.0, "upper": 20.0}
            ),
            "overlap": first.overlap.model_copy(update={"status": OverlapStatus.WEAK}),
        }
    )
    assessment = evaluate_hte_quality(
        result.model_copy(update={"subgroup_results": (wide, *result.subgroup_results[1:])})
    )

    assert all(
        item.severity is HTEQualityFindingSeverity.ADVISORY for item in assessment.advisory_findings
    )
    assert tuple(item.code for item in assessment.advisory_findings) == tuple(
        sorted(item.code for item in assessment.advisory_findings)
    )
