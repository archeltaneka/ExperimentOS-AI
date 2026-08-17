"""Deterministic randomized-inference fixtures for the Phase 4 reliability baseline."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict

from packages.evals.analysis_validation_cases import build_validation_golden_cases
from packages.experiments.analysis import (
    AnalysisRequest,
    AnalysisTable,
    CovariateDefinition,
    CovariateRole,
    CovariateTiming,
    MetricType,
    ProvenanceRecord,
    ProvenanceSourceType,
    RandomizedAnalysisMethod,
    RequestedCredibleLevel,
    SampleCounts,
    TimePeriod,
    TreatmentRelationship,
)
from packages.experiments.analysis.randomized.bayesian import (
    BayesianAnalysisExecutionRequest,
    BayesianAnalysisService,
    BernoulliBinomialLikelihood,
    BetaPrior,
    NormalInverseGammaPrior,
    NormalUnknownMeanVarianceLikelihood,
    PracticalEquivalenceRegion,
)
from packages.experiments.analysis.randomized.cuped import (
    CupedAnalysisExecutionRequest,
    CupedAnalysisService,
)
from packages.experiments.analysis.randomized.sequential import (
    SequentialAnalysisPlan,
    SequentialAnalysisService,
    SequentialLookDefinition,
    SequentialLookExecution,
)
from packages.experiments.analysis.validation import (
    AnalysisDataBinding,
    MetricColumnBinding,
    OutcomeDataBinding,
    ValidationPolicy,
)
from packages.observability.base import BaseObservabilityProvider


class SkippedStatisticalFixture(BaseModel):
    """Typed evidence for an optional capability that does not exist in estimator v1."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["skipped"] = "skipped"
    reason: Literal["no_seeded_sampling_path"] = "no_seeded_sampling_path"
    diagnostics: tuple[()] = ()
    warnings: tuple[()] = ()


def run_randomized_inference_fixture(
    fixture_id: str,
    *,
    reverse_rows: bool,
    observability_provider: BaseObservabilityProvider | None,
) -> BaseModel:
    if fixture_id.startswith("cuped_"):
        return _run_cuped(fixture_id, reverse_rows, observability_provider)
    if fixture_id.startswith("sequential_"):
        return _run_sequential(fixture_id, reverse_rows, observability_provider)
    if fixture_id.startswith("bayesian_"):
        return _run_bayesian(fixture_id, reverse_rows, observability_provider)
    raise ValueError(f"unknown randomized-inference fixture_id: {fixture_id}")


def _source(source_id: str) -> tuple[ProvenanceRecord, ...]:
    return (
        ProvenanceRecord(
            source_type=ProvenanceSourceType.EXTERNAL_REFERENCE,
            source_id=source_id,
            source_version="1",
        ),
    )


def _base_request(metric_type: MetricType) -> tuple[AnalysisRequest, AnalysisDataBinding]:
    cases = {case.case_id: case for case in build_validation_golden_cases()}
    case = cases["valid-randomized" if metric_type is MetricType.BINARY else "fully-eligible"]
    if case.request is None:
        raise RuntimeError("reference validation case is missing its request")
    return case.request, case.binding


def _arm_table(
    treatment: Sequence[object],
    control: Sequence[object],
    *,
    covariates: tuple[Sequence[object], Sequence[object]] | None = None,
    reverse_rows: bool = False,
) -> AnalysisTable:
    rows: tuple[tuple[object, ...], ...]
    columns: tuple[str, ...]
    if covariates is None:
        rows = tuple(
            (f"treatment-{index}", "treatment", value) for index, value in enumerate(treatment)
        ) + tuple((f"control-{index}", "control", value) for index, value in enumerate(control))
        columns = ("unit", "arm", "outcome")
    else:
        treatment_covariates, control_covariates = covariates
        rows = tuple(
            (f"treatment-{index}", "treatment", value, treatment_covariates[index])
            for index, value in enumerate(treatment)
        ) + tuple(
            (f"control-{index}", "control", value, control_covariates[index])
            for index, value in enumerate(control)
        )
        columns = ("unit", "arm", "outcome", "prior_covariate")
    return AnalysisTable(columns=columns, rows=tuple(reversed(rows)) if reverse_rows else rows)


def _cuped_request(
    *,
    timing: CovariateTiming = CovariateTiming.PRE_TREATMENT,
    relationship: TreatmentRelationship = TreatmentRelationship.NONE_KNOWN,
    treatment: int = 4,
    control: int = 4,
) -> tuple[AnalysisRequest, AnalysisDataBinding]:
    request, binding = _base_request(MetricType.CONTINUOUS)
    design = request.study_design.model_copy(update={"method": RandomizedAnalysisMethod.CUPED})
    covariate_metric = request.outcome.metric.model_copy(
        update={"metric_id": "prior_covariate", "label": "Prior covariate"}
    )
    covariate = CovariateDefinition(
        metric=covariate_metric,
        timing=timing,
        role=CovariateRole.CUPED,
        treatment_relationship=relationship,
        measurement_period=TimePeriod(
            start=datetime(2026, 5, 1, tzinfo=UTC),
            end=datetime(2026, 6, 1, tzinfo=UTC),
        ),
    )
    request = request.model_copy(
        update={
            "study_design": design,
            "sample_counts": SampleCounts(
                total=treatment + control,
                treatment=treatment,
                control=control,
            ),
            "covariates": (covariate,),
        }
    )
    return request, binding.model_copy(
        update={
            "covariates": (
                MetricColumnBinding(metric_id="prior_covariate", column="prior_covariate"),
            )
        }
    )


def _run_cuped(
    fixture_id: str,
    reverse_rows: bool,
    provider: BaseObservabilityProvider | None,
) -> BaseModel:
    control_outcomes: Sequence[object] = (0.0, 3.0, 3.0, 6.0)
    treatment_outcomes: Sequence[object] = (4.0, 4.0, 7.0, 10.0)
    control_covariates: Sequence[object] = (0.0, 1.0, 2.0, 3.0)
    treatment_covariates: Sequence[object] = (0.0, 1.0, 2.0, 3.0)
    timing = CovariateTiming.PRE_TREATMENT
    relationship = TreatmentRelationship.NONE_KNOWN
    treatment_count = 4
    control_count = 4
    policy_updates: dict[str, object] = {}

    if fixture_id == "cuped_zero_reduction":
        control_outcomes = (0.0, 1.0, 1.0, 0.0)
        treatment_outcomes = (2.0, 3.0, 3.0, 2.0)
    elif fixture_id == "cuped_negative_reduction":
        control_outcomes = (-2.0, -1.0, -3.0, -2.0)
        treatment_outcomes = (6.0, 1.0, 7.0, 2.0)
        control_covariates = (-2.0, 3.0, -1.0, 1.0)
        treatment_covariates = (2.0, 3.0, 0.0, 2.0)
    elif fixture_id == "cuped_constant_covariate":
        control_covariates = treatment_covariates = (2.0, 2.0, 2.0, 2.0)
    elif fixture_id == "cuped_post_treatment":
        timing = CovariateTiming.POST_TREATMENT
        relationship = TreatmentRelationship.ASSIGNMENT_DERIVED
    elif fixture_id == "cuped_missing_covariate":
        control_covariates = (None, 1.0, 2.0, 3.0)
        treatment_covariates = (None, 1.0, 2.0, 3.0)
    elif fixture_id == "cuped_excessive_missingness":
        control_covariates = (None, None, 2.0, 3.0)
        treatment_covariates = (None, 1.0, 2.0, 3.0)
        policy_updates["maximum_covariate_missing_rate"] = 0.25
    elif fixture_id == "cuped_arm_imbalance":
        treatment_outcomes = (4.0, 4.0, 7.0, 10.0, 11.0, 12.0)
        treatment_covariates = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
        treatment_count = 6
    elif fixture_id != "cuped_positive_reduction":
        raise ValueError(f"unknown CUPED fixture_id: {fixture_id}")

    request, binding = _cuped_request(
        timing=timing,
        relationship=relationship,
        treatment=treatment_count,
        control=control_count,
    )
    policy_values: dict[str, object] = {
        "minimum_total": 4,
        "minimum_per_arm": 2,
        "weak_total": 4,
        "weak_per_arm": 2,
    }
    policy_values.update(policy_updates)
    return CupedAnalysisService(
        validation_policy=ValidationPolicy(**policy_values),  # type: ignore[arg-type]
        observability_provider=provider,
    ).analyze(
        CupedAnalysisExecutionRequest(
            request_id=f"phase4-{fixture_id}",
            analysis_request=request,
        ),
        _arm_table(
            treatment_outcomes,
            control_outcomes,
            covariates=(treatment_covariates, control_covariates),
            reverse_rows=reverse_rows,
        ),
        binding,
        provenance=_source("phase4-cuped-reference"),
    )


def _sequential_plan(information_times: tuple[float, ...]) -> SequentialAnalysisPlan:
    request, _ = _base_request(MetricType.CONTINUOUS)
    request = request.model_copy(
        update={
            "study_design": request.study_design.model_copy(
                update={"method": RandomizedAnalysisMethod.SEQUENTIAL_AB}
            ),
            "sample_counts": SampleCounts(total=60, treatment=30, control=30),
        }
    )
    return SequentialAnalysisPlan(
        plan_id="phase4-sequential-reference",
        experiment_id="phase4-reference",
        analysis_request=request,
        total_alpha=0.05,
        planned_looks=tuple(
            SequentialLookDefinition(look_index=index, information_time=time)
            for index, time in enumerate(information_times, start=1)
        ),
        registration_marker="phase4-reference-registration",
        registered_at=datetime(2026, 7, 1, tzinfo=UTC),
        provenance=_source("phase4-sequential-plan"),
    )


def _sequential_binding() -> AnalysisDataBinding:
    return AnalysisDataBinding(
        treatment_column="arm",
        outcome=OutcomeDataBinding(value_column="outcome"),
        observation_unit_column="unit",
        randomization_unit_column="unit",
    )


def _look(
    plan: SequentialAnalysisPlan,
    index: int,
    treatment: Sequence[object],
    control: Sequence[object],
    *,
    reverse_rows: bool,
    request: AnalysisRequest | None = None,
    fingerprint: str | None = None,
) -> SequentialLookExecution:
    return SequentialLookExecution(
        look_index=index,
        information_time=plan.planned_looks[index - 1].information_time,
        plan_fingerprint=fingerprint or plan.plan_fingerprint,  # type: ignore[arg-type]
        analysis_request=request or plan.analysis_request,
        table=_arm_table(treatment, control, reverse_rows=reverse_rows),
        binding=_sequential_binding(),
        executed_at=datetime(2026, 7, 2, tzinfo=UTC) + timedelta(days=index),
    )


def _run_sequential(
    fixture_id: str,
    reverse_rows: bool,
    provider: BaseObservabilityProvider | None,
) -> BaseModel:
    information_times: tuple[float, ...] = (
        (1.0,)
        if fixture_id
        in {
            "sequential_invalid_fingerprint",
            "sequential_insufficient_sample",
        }
        else (0.5, 1.0)
    )
    if fixture_id == "sequential_late_efficacy":
        information_times = (0.25, 0.5, 1.0)
    plan = _sequential_plan(information_times)
    null_15 = tuple(float(value) for value in range(15))
    null_30 = tuple(float(value) for value in range(30))
    looks: tuple[SequentialLookExecution, ...]

    if fixture_id == "sequential_early_efficacy":
        looks = (
            _look(
                plan, 1, tuple(value + 20 for value in null_15), null_15, reverse_rows=reverse_rows
            ),
        )
    elif fixture_id == "sequential_late_efficacy":
        control_2 = tuple(float(value) for value in range(20))
        treatment_2 = null_15 + tuple(float(value + 4) for value in range(15, 20))
        treatment_3 = treatment_2 + tuple(float(value + 21) for value in range(20, 30))
        looks = (
            _look(plan, 1, null_15, null_15, reverse_rows=reverse_rows),
            _look(plan, 2, treatment_2, control_2, reverse_rows=reverse_rows),
            _look(plan, 3, treatment_3, null_30, reverse_rows=reverse_rows),
        )
    elif fixture_id == "sequential_no_stop":
        looks = (
            _look(
                plan,
                1,
                tuple(value + 0.25 for value in null_15),
                null_15,
                reverse_rows=reverse_rows,
            ),
        )
    elif fixture_id == "sequential_null_sequence":
        looks = (
            _look(plan, 1, null_15, null_15, reverse_rows=reverse_rows),
            _look(plan, 2, null_30, null_30, reverse_rows=reverse_rows),
        )
    elif fixture_id == "sequential_skipped_look":
        looks = (_look(plan, 2, null_30, null_30, reverse_rows=reverse_rows),)
    elif fixture_id == "sequential_duplicate_look":
        first = _look(plan, 1, null_15, null_15, reverse_rows=reverse_rows)
        looks = (first, first)
    elif fixture_id == "sequential_decreasing_sample":
        looks = (
            _look(plan, 1, null_30, null_30, reverse_rows=reverse_rows),
            _look(plan, 2, null_15, null_15, reverse_rows=reverse_rows),
        )
    elif fixture_id == "sequential_invalid_fingerprint":
        looks = (
            _look(plan, 1, null_15, null_15, reverse_rows=reverse_rows, fingerprint="invalid"),
        )
    elif fixture_id == "sequential_changed_outcome":
        changed = plan.analysis_request.model_copy(
            update={
                "outcome": plan.analysis_request.outcome.model_copy(
                    update={
                        "metric": plan.analysis_request.outcome.metric.model_copy(
                            update={"metric_id": "changed_outcome"}
                        )
                    }
                )
            }
        )
        looks = (_look(plan, 1, null_15, null_15, reverse_rows=reverse_rows, request=changed),)
    elif fixture_id == "sequential_changed_treatment":
        changed = plan.analysis_request.model_copy(
            update={
                "treatment": plan.analysis_request.treatment.model_copy(
                    update={"treatment_id": "changed_treatment"}
                )
            }
        )
        looks = (_look(plan, 1, null_15, null_15, reverse_rows=reverse_rows, request=changed),)
    elif fixture_id == "sequential_insufficient_sample":
        looks = (_look(plan, 1, (1.0,), (0.0,), reverse_rows=reverse_rows),)
    elif fixture_id == "sequential_plan_mutation":
        object.__setattr__(plan, "total_alpha", 0.04)
        looks = ()
    else:
        raise ValueError(f"unknown sequential fixture_id: {fixture_id}")

    return SequentialAnalysisService(
        validation_policy=ValidationPolicy(
            minimum_total=20,
            minimum_per_arm=10,
            weak_total=100,
            weak_per_arm=30,
        ),
        observability_provider=provider,
    ).analyze(plan, looks, provenance=_source("phase4-sequential-reference"))


def _bayesian_request(metric_type: MetricType, treatment: int, control: int) -> AnalysisRequest:
    request, _ = _base_request(metric_type)
    return request.model_copy(
        update={
            "study_design": request.study_design.model_copy(
                update={"method": RandomizedAnalysisMethod.BAYESIAN_AB}
            ),
            "sample_counts": SampleCounts(
                total=treatment + control,
                treatment=treatment,
                control=control,
            ),
            "uncertainty": RequestedCredibleLevel(level=0.95),
        }
    )


def _run_bayesian(
    fixture_id: str,
    reverse_rows: bool,
    provider: BaseObservabilityProvider | None,
) -> BaseModel:
    if fixture_id == "bayesian_seeded_skipped":
        return SkippedStatisticalFixture()
    if fixture_id in {"bayesian_invalid_prior", "bayesian_unsupported_likelihood"}:
        request = _bayesian_request(MetricType.BINARY, 20, 20)
        prior = BetaPrior(alpha=1.0, beta=1.0, provenance=_source("phase4-beta-prior"))
        payload = BayesianAnalysisExecutionRequest(
            request_id=fixture_id,
            analysis_request=request,
            treatment_prior=prior,
            control_prior=prior,
            likelihood=BernoulliBinomialLikelihood(),
        ).model_dump(mode="python")
        if fixture_id == "bayesian_invalid_prior":
            payload["treatment_prior"]["alpha"] = -1.0
        else:
            payload["likelihood"] = {"likelihood_family": "poisson"}
        return BayesianAnalysisService(observability_provider=provider).analyze_payload(
            payload,
            _arm_table((1,) * 14 + (0,) * 6, (1,) * 8 + (0,) * 12, reverse_rows=reverse_rows),
            _base_request(MetricType.BINARY)[1],
            provenance=_source("phase4-bayesian-invalid-reference"),
        )

    treatment: Sequence[object]
    control: Sequence[object]
    if fixture_id.startswith("bayesian_continuous"):
        treatment = (2.0, 3.0, 4.0)
        control = (1.0, 2.0, 3.0)
        if fixture_id == "bayesian_continuous_inadequate":
            treatment, control = (2.0,), (1.0,)
        request = _bayesian_request(MetricType.CONTINUOUS, len(treatment), len(control))
        control_prior = NormalInverseGammaPrior(
            mu_0=0.0,
            kappa_0=1.0,
            alpha_0=2.0,
            beta_0=2.0,
            provenance=_source("phase4-nig-prior"),
        )
        treatment_prior = control_prior.model_copy(update={"mu_0": 1.0})
        execution = BayesianAnalysisExecutionRequest(
            request_id=fixture_id,
            analysis_request=request,
            treatment_prior=treatment_prior,
            control_prior=control_prior,
            likelihood=NormalUnknownMeanVarianceLikelihood(),
        )
        binding = _base_request(MetricType.CONTINUOUS)[1]
    else:
        treatment = (1, 1)
        control = (1, 0)
        alpha = beta = 1.0
        if fixture_id == "bayesian_binary_null":
            treatment = control = (1,) * 10 + (0,) * 10
        elif fixture_id == "bayesian_binary_negative":
            treatment, control = control, treatment
        elif fixture_id == "bayesian_binary_sparse":
            treatment, control = (1, 0, 0, 0), (0, 0, 0, 0)
        elif fixture_id == "bayesian_binary_zero":
            treatment = control = (0, 0, 0, 0)
        elif fixture_id == "bayesian_binary_informative":
            treatment, control = (1, 0, 1, 0), (1, 0, 1, 0)
            alpha = beta = 50.0
        elif fixture_id not in {"bayesian_binary_base", "bayesian_binary_rope"}:
            raise ValueError(f"unknown Bayesian fixture_id: {fixture_id}")
        request = _bayesian_request(MetricType.BINARY, len(treatment), len(control))
        prior = BetaPrior(
            alpha=alpha,
            beta=beta,
            provenance=_source("phase4-beta-prior"),
        )
        rope = None
        if fixture_id == "bayesian_binary_rope":
            rope = PracticalEquivalenceRegion(
                lower=-0.05,
                upper=0.05,
                unit=request.outcome.metric.unit,
            )
        execution = BayesianAnalysisExecutionRequest(
            request_id=fixture_id,
            analysis_request=request,
            treatment_prior=prior,
            control_prior=prior,
            likelihood=BernoulliBinomialLikelihood(),
            rope=rope,
        )
        binding = _base_request(MetricType.BINARY)[1]
    return BayesianAnalysisService(
        validation_policy=ValidationPolicy(
            minimum_total=2,
            minimum_per_arm=1,
            weak_total=2,
            weak_per_arm=1,
        ),
        observability_provider=provider,
    ).analyze(
        execution,
        _arm_table(treatment, control, reverse_rows=reverse_rows),
        binding,
        provenance=_source("phase4-bayesian-reference"),
    )


__all__ = ["run_randomized_inference_fixture"]
