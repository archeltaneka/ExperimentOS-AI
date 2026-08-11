"""Structured assumptions for single-covariate CUPED adjustment."""

from __future__ import annotations

from ...provenance import AssumptionAssessment, AssumptionStatus
from ..assumptions import randomized_assumptions


def cuped_assumptions(
    *,
    pre_treatment_status: AssumptionStatus = AssumptionStatus.SUPPORTED,
    unaffected_by_treatment_status: AssumptionStatus = AssumptionStatus.UNTESTABLE,
) -> tuple[AssumptionAssessment, ...]:
    """Return stable CUPED assumptions without treating declarations as empirical proof."""
    return randomized_assumptions() + (
        AssumptionAssessment(
            code="covariate_pre_treatment",
            statement="The CUPED covariate is measured before treatment assignment takes effect.",
            status=pre_treatment_status,
        ),
        AssumptionAssessment(
            code="covariate_unaffected_by_treatment",
            statement="Treatment cannot affect the declared CUPED covariate.",
            status=unaffected_by_treatment_status,
        ),
        AssumptionAssessment(
            code="estimand_preserved",
            statement="CUPED estimates the same declared treatment-effect estimand as baseline.",
            status=AssumptionStatus.SUPPORTED,
        ),
        AssumptionAssessment(
            code="complete_case_covariate_policy",
            statement="Rows missing the CUPED covariate are excluded without imputation.",
            status=AssumptionStatus.SUPPORTED,
        ),
        AssumptionAssessment(
            code="no_data_dependent_covariate_selection",
            statement="The CUPED covariate was declared without outcome-dependent selection.",
            status=AssumptionStatus.UNTESTABLE,
        ),
    )


__all__ = ["cuped_assumptions"]
