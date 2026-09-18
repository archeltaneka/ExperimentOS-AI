"""Eligibility and evidence-preservation tests for impact source adapters."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from packages.experiments.analysis.base import AnalysisStatus
from packages.experiments.analysis.causal.diagnostics import CausalDiagnosticCode
from packages.experiments.analysis.causal.estimands import EffectScale
from packages.experiments.analysis.causal.ipw.models import IPWBalanceStatus
from packages.experiments.analysis.causal.models import (
    CausalAbstentionReason,
    IdentificationResult,
    IdentificationStatus,
)
from packages.experiments.analysis.estimands import EstimandDefinition, EstimandKind
from packages.experiments.analysis.impact.source_models import SourceEffect
from packages.experiments.analysis.impact.sources import adapt_source
from packages.experiments.analysis.provenance import AnalysisFailure, AssumptionStatus
from packages.experiments.analysis.randomized import EvidenceCategory
from packages.experiments.analysis.randomized.models import (
    ComputationStatus,
    Conclusion,
    RandomizedAbstentionReason,
)
from packages.experiments.analysis.randomized.sequential import SequentialLookResult
from packages.experiments.analysis.results import FailedAnalysisResult
from packages.experiments.analysis.study_designs import (
    RandomizedAnalysisMethod,
    RandomizedExperimentDesign,
)
from packages.experiments.analysis.uncertainty import ConfidenceInterval
from tests.analysis_contract_fixtures import source as provenance_source
from tests.impact_source_fixtures import (
    advanced_result,
    bayesian_result,
    cuped_result,
    did_result,
    dml_result,
    econml_hte_result,
    hte_result,
    ipw_result,
    randomized_result,
    sequential_result,
)
from tests.ipw_fixtures import ipw_execution


def _blocking_codes(effect: SourceEffect) -> set[str]:
    return {item.code for item in effect.blocking_diagnostics}


def test_randomized_binary_preserves_absolute_effect_and_request_semantics() -> None:
    source = randomized_result(binary=True)
    assert source.analysis_request is not None
    assert isinstance(source.analysis_request.study_design, RandomizedExperimentDesign)
    assert source.test_result is not None

    effect = adapt_source(source)

    assert effect.estimator == "randomized_two_proportion_z"
    assert effect.request_id == source.request_id
    assert effect.native_status == "completed"
    assert effect.metric == source.analysis_request.outcome
    assert effect.population == source.analysis_request.population
    assert effect.analysis_unit == source.analysis_request.unit_of_analysis
    assert effect.observed_period == source.analysis_request.study_design.experiment_period
    assert effect.point == pytest.approx(0.30)
    assert effect.interval == source.test_result.confidence_interval
    assert effect.effect_scale == "absolute_binary"
    assert effect.target_kind == "full"
    assert effect.conditional
    assert not effect.blocking_diagnostics


def test_bayesian_preserves_credible_interval_without_converting_it() -> None:
    source = bayesian_result()
    assert source.effect is not None

    effect = adapt_source(source)

    assert effect.estimator == "bayesian_randomized"
    assert effect.point == source.effect.posterior_mean
    assert effect.interval == source.effect.credible_interval
    assert effect.interval is not None
    assert effect.interval.kind == "credible_interval"
    assert effect.effect_scale == "absolute_binary"


def test_cuped_uses_adjusted_effect_and_keeps_parent_evidence() -> None:
    source = cuped_result()

    effect = adapt_source(source)

    assert source.adjusted_result is not None
    assert source.adjusted_result.point_effect is not None
    assert source.adjusted_result.test_result is not None
    assert effect.estimator == "cuped"
    assert effect.point == source.adjusted_result.point_effect.absolute_effect.value
    assert effect.interval == source.adjusted_result.test_result.confidence_interval
    assert len(effect.source_assumptions) >= len(source.assumptions)
    assert {item.scope for item in effect.source_metadata} >= {"configuration", "cuped"}
    assert effect.calculable


def test_randomized_relative_estimand_is_not_paired_with_absolute_interval() -> None:
    source = randomized_result(binary=True)
    assert source.analysis_request is not None
    estimand = EstimandDefinition(kind=EstimandKind.RELATIVE_LIFT)
    request = source.analysis_request.model_copy(update={"estimand": estimand})
    source = source.model_copy(update={"analysis_request": request, "estimand": estimand})

    effect = adapt_source(source)

    assert effect.point is None
    assert effect.interval is None
    assert "impact.source.relative_uncertainty_missing" in _blocking_codes(effect)


def test_sequential_method_wrapped_as_fixed_horizon_result_is_refused() -> None:
    source = randomized_result()
    assert source.analysis_request is not None
    design = source.analysis_request.study_design.model_copy(
        update={"method": RandomizedAnalysisMethod.SEQUENTIAL_AB}
    )
    request = source.analysis_request.model_copy(update={"study_design": design})
    source = source.model_copy(update={"analysis_request": request})

    effect = adapt_source(source)

    assert effect.point is None
    assert "impact.source.sequential_unsupported" in _blocking_codes(effect)


def test_violated_randomized_evidence_or_assumption_blocks_effect() -> None:
    source = randomized_result()
    violated = source.assumptions[0].model_copy(update={"status": AssumptionStatus.VIOLATED})
    source = source.model_copy(
        update={
            "evidence_category": EvidenceCategory.RANDOMIZED_DESIGN_WITH_VIOLATED_ASSUMPTIONS,
            "assumptions": (violated, *source.assumptions[1:]),
        }
    )

    effect = adapt_source(source)

    assert effect.point is None
    assert "impact.source.assumption_violated" in _blocking_codes(effect)


def test_interval_that_does_not_contain_point_is_refused() -> None:
    source = randomized_result()
    assert source.test_result is not None
    test_result = source.test_result.model_copy(
        update={
            "confidence_interval": ConfidenceInterval(
                lower=0.0,
                upper=1.0,
                confidence_level=source.test_result.confidence_interval.confidence_level,
            )
        }
    )
    source = source.model_copy(update={"test_result": test_result})

    effect = adapt_source(source)

    assert effect.point is None
    assert "impact.source.interval_point_mismatch" in _blocking_codes(effect)


@pytest.mark.parametrize(
    ("factory", "estimator", "target"),
    [
        (lambda: ipw_result(), "ipw", "full"),
        (lambda: ipw_result(att=True), "ipw", "treated"),
        (did_result, "did", "treated"),
        (dml_result, "dml", "full"),
    ],
)
def test_causal_effect_families_preserve_conditional_target_and_uncertainty(
    factory: Callable[[], object], estimator: str, target: str
) -> None:
    source = factory()

    effect = adapt_source(source)

    assert effect.estimator == estimator
    assert effect.native_status == "completed"
    assert effect.point is not None
    assert effect.interval is not None
    assert effect.target_kind == target
    assert effect.conditional
    assert effect.source_assumptions
    assert effect.evidence_limitations
    assert not effect.blocking_diagnostics


def test_hte_requires_one_selected_owned_subgroup_and_preserves_rule() -> None:
    source = hte_result()
    selected = source.subgroup_results[0]

    missing = adapt_source(source)
    effect = adapt_source(source, subgroup_id=selected.subgroup_id)

    assert missing.point is None
    assert "impact.source.subgroup_required" in _blocking_codes(missing)
    assert effect.estimator in {"hte_dml", "hte_doubly_robust", "econml_hte"}
    assert effect.subgroup_id == selected.subgroup_id
    assert effect.subgroup_rule == selected.rule
    assert effect.point == selected.estimate
    assert effect.interval == selected.confidence_interval
    assert effect.target_kind == "conditioned"
    assert not effect.blocking_diagnostics


def test_offline_advanced_dml_and_econml_hte_preserve_adapter_identity() -> None:
    advanced = advanced_result()
    hte = econml_hte_result()
    selected = hte.subgroup_results[0]

    average = adapt_source(advanced)
    subgroup = adapt_source(hte, subgroup_id=selected.subgroup_id)

    assert average.estimator == "econml_LinearDML"
    assert average.calculable
    assert any(item.scope == "advanced" for item in average.source_metadata)
    assert subgroup.estimator == "econml_hte"
    assert subgroup.calculable


def test_advanced_dependency_provenance_mismatch_blocks_claim() -> None:
    source = econml_hte_result()
    assert source.adapter_provenance is not None
    selected = source.subgroup_results[0]
    corrupted = source.model_copy(
        update={
            "adapter_provenance": source.adapter_provenance.model_copy(
                update={"econml_version": "0.16.0"}
            )
        }
    )

    effect = adapt_source(corrupted, subgroup_id=selected.subgroup_id)

    assert effect.point is None
    assert "advanced.quality.dependency_provenance_missing" in _blocking_codes(effect)


def test_risk_ratio_declaration_cannot_relabel_difference_scale_ipw() -> None:
    source = ipw_result(binary=True)
    assert source.estimand is not None
    estimand = source.estimand.model_copy(update={"effect_scale": EffectScale.RISK_RATIO})
    source = source.model_copy(
        update={"estimand": estimand, "effect_scale": EffectScale.RISK_RATIO}
    )

    effect = adapt_source(source)

    assert not effect.calculable
    assert "impact.source.metric_scale_unsupported" in _blocking_codes(effect)


def test_ipw_severe_balance_is_not_calculable() -> None:
    source = ipw_result().model_copy(update={"balance_status": IPWBalanceStatus.SEVERE})

    effect = adapt_source(source)

    assert not effect.calculable
    assert "impact.source.balance_blocking" in _blocking_codes(effect)


def test_ipw_revalidates_identification_declarations_without_refitting() -> None:
    source = ipw_result()
    declaration = source.analysis_request.identification.model_copy(update={"estimand": None})
    request = source.analysis_request.model_copy(update={"identification": declaration})
    source = source.model_copy(update={"analysis_request": request})

    effect = adapt_source(source)

    assert not effect.calculable
    assert "impact.source.identification_invalid" in _blocking_codes(effect)
    assert any(item.scope == "identification" for item in effect.source_diagnostics)


def test_ipw_effect_target_must_match_identified_population() -> None:
    source = ipw_result()
    assert source.target_population is not None
    changed_population = source.target_population.population.model_copy(
        update={"label": "Different population"}
    )
    target = source.target_population.model_copy(update={"population": changed_population})
    source = source.model_copy(update={"target_population": target})

    effect = adapt_source(source)

    assert not effect.calculable
    assert "impact.source.identification_echo_mismatch" in _blocking_codes(effect)


def test_hte_requires_identified_parent() -> None:
    source = hte_result()
    identification = source.execution_request.identification_result.model_copy(
        update={
            "status": IdentificationStatus.INVALID,
            "abstention_reason": CausalAbstentionReason(
                code=CausalDiagnosticCode.INSUFFICIENT_IDENTIFICATION_EVIDENCE,
                message="Parent identification is invalid.",
                missing_or_invalid_information=("identification",),
            ),
        }
    )
    execution = source.execution_request.model_copy(
        update={"identification_result": identification}
    )
    source = source.model_copy(update={"execution_request": execution})

    effect = adapt_source(source, subgroup_id=source.subgroup_results[0].subgroup_id)

    assert not effect.calculable
    assert "impact.source.identification_invalid" in _blocking_codes(effect)


def test_hte_selected_rule_must_match_structured_definition() -> None:
    source = hte_result()
    changed = source.subgroup_results[0].model_copy(
        update={"rule": "everyone, including users outside this subgroup"}
    )
    source = source.model_copy(update={"subgroup_results": (changed, *source.subgroup_results[1:])})

    effect = adapt_source(source, subgroup_id=changed.subgroup_id)

    assert not effect.calculable
    assert "impact.source.subgroup_rule_mismatch" in _blocking_codes(effect)


def test_econml_hte_does_not_flatten_unrelated_subgroup_quality_failure() -> None:
    source = econml_hte_result()
    selected = source.subgroup_results[0]
    unrelated = source.subgroup_results[1]
    sparse_counts = unrelated.sample_counts.model_copy(
        update={
            "raw_count": 2,
            "retained_count": 2,
            "treated_count": 1,
            "control_count": 1,
            "dropped_count": 0,
        }
    )
    unrelated = unrelated.model_copy(update={"sample_counts": sparse_counts})
    source = source.model_copy(
        update={"subgroup_results": (selected, unrelated, *source.subgroup_results[2:])}
    )

    effect = adapt_source(source, subgroup_id=selected.subgroup_id)

    assert effect.calculable
    assert "hte.quality.sparse_group_conclusive" not in _blocking_codes(effect)


def test_non_effect_and_sequential_contracts_refuse_without_raising() -> None:
    execution = ipw_execution()
    identification: IdentificationResult = execution.identification_result

    identified = adapt_source(identification)
    sequential = adapt_source(sequential_result())
    unknown = adapt_source(object())
    propensity = adapt_source(execution.propensity_result)

    assert identified.point is None
    assert "impact.source.non_effect" in _blocking_codes(identified)
    assert sequential.point is None
    assert "impact.source.sequential_unsupported" in _blocking_codes(sequential)
    assert unknown.point is None
    assert "impact.source.unsupported_type" in _blocking_codes(unknown)
    assert propensity.native_status == execution.propensity_result.status.value
    assert "impact.source.non_effect" in _blocking_codes(propensity)


def test_generic_owned_failure_retains_native_failure_audit() -> None:
    source = FailedAnalysisResult(
        status=AnalysisStatus.FAILED,
        failures=(
            AnalysisFailure(
                code="engine.failed",
                stage="estimation",
                message="Owned failure.",
                retryable=False,
            ),
        ),
        diagnostics=(),
        provenance=(provenance_source(),),
    )

    effect = adapt_source(source)

    assert effect.native_status == "failed"
    assert effect.provenance == source.provenance
    assert effect.source_metadata[0].payload["code"] == "engine.failed"
    assert "impact.source.unsupported_owned_result" in _blocking_codes(effect)


def test_malformed_owned_source_refuses_at_revalidation_boundary() -> None:
    effect = adapt_source(SequentialLookResult.model_construct())

    assert effect.point is None
    assert "impact.source.invalid_contract" in _blocking_codes(effect)


def test_exact_type_revalidation_failure_is_auditable_refusal() -> None:
    valid = randomized_result()
    malformed = valid.model_copy(update={"point_effect": None})

    effect = adapt_source(malformed)

    assert effect.request_id == valid.request_id
    assert effect.native_status == "completed"
    assert effect.point is None
    assert effect.interval is None
    assert "impact.source.invalid_contract" in _blocking_codes(effect)


def test_refused_native_result_preserves_original_diagnostics_and_provenance() -> None:
    source = randomized_result()
    refused = source.model_copy(
        update={
            "status": ComputationStatus.INVALID,
            "conclusion": Conclusion.INVALID,
            "treatment_summary": None,
            "control_summary": None,
            "point_effect": None,
            "test_result": None,
            "abstention_reason": RandomizedAbstentionReason(
                code="test.invalid",
                message="Deliberately invalid owned result.",
            ),
        }
    )

    effect = adapt_source(refused)

    assert effect.point is None
    assert effect.interval is None
    assert effect.provenance == source.provenance
    assert effect.source_diagnostics
    assert effect.source_diagnostics[0].payload
    assert "impact.source.native_status" in _blocking_codes(effect)


def test_source_effect_round_trips_deterministically() -> None:
    effect = adapt_source(ipw_result())

    restored = SourceEffect.model_validate_json(effect.model_dump_json())

    assert restored == effect
    assert restored.model_dump_json() == effect.model_dump_json()
