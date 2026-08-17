"""Frozen contracts for Bayesian randomized A/B analysis."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from ...base import (
    ContractModel,
    FiniteFloat,
    NonEmptyStr,
    PositiveFiniteFloat,
    PositiveInt,
    Probability,
    ScalarValue,
)
from ...estimands import EstimandDefinition
from ...metrics import MetricDefinition, MetricUnit, OutcomeDirection
from ...provenance import (
    AnalysisWarning,
    AssumptionAssessment,
    DiagnosticSeverity,
    ProvenanceRecord,
    ProvenanceRecords,
    ProvenanceSourceType,
)
from ...requests import AnalysisRequest
from ...study_designs import RandomizedAnalysisMethod
from ...uncertainty import CredibleInterval, PosteriorProbability, RequestedCredibleLevel

type NonNegativeFiniteFloat = Annotated[FiniteFloat, Field(ge=0)]
type NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]


class BetaPrior(ContractModel):
    """Proper Beta prior for one binary-outcome arm."""

    prior_family: Literal["beta"] = "beta"
    prior_family_version: Literal["1"] = "1"
    alpha: PositiveFiniteFloat
    beta: PositiveFiniteFloat
    provenance: ProvenanceRecords
    label: NonEmptyStr | None = None
    effective_sample_size: PositiveFiniteFloat | None = None

    @model_validator(mode="after")
    def populate_effective_sample_size(self) -> Self:
        expected = self.alpha + self.beta
        if self.effective_sample_size is None:
            object.__setattr__(self, "effective_sample_size", expected)
        elif self.effective_sample_size != expected:
            raise ValueError("effective_sample_size must equal alpha plus beta")
        return self


class NormalInverseGammaPrior(ContractModel):
    """Normal–Inverse-Gamma prior using an inverse-gamma shape/scale convention."""

    prior_family: Literal["normal_inverse_gamma"] = "normal_inverse_gamma"
    prior_family_version: Literal["1"] = "1"
    parameterization: Literal["inverse_gamma_shape_scale"] = "inverse_gamma_shape_scale"
    mu_0: FiniteFloat
    kappa_0: PositiveFiniteFloat
    alpha_0: PositiveFiniteFloat
    beta_0: PositiveFiniteFloat
    provenance: ProvenanceRecords
    label: NonEmptyStr | None = None


type BayesianPrior = Annotated[
    BetaPrior | NormalInverseGammaPrior,
    Field(discriminator="prior_family"),
]


class BernoulliBinomialLikelihood(ContractModel):
    """Bernoulli observations summarized by Binomial arm counts."""

    likelihood_family: Literal["bernoulli_binomial"] = "bernoulli_binomial"
    likelihood_family_version: Literal["1"] = "1"
    success_value: Literal[1] = 1


class NormalUnknownMeanVarianceLikelihood(ContractModel):
    """Normal likelihood with an unknown arm-specific mean and variance."""

    likelihood_family: Literal["normal_unknown_mean_variance"] = (
        "normal_unknown_mean_variance"
    )
    likelihood_family_version: Literal["1"] = "1"
    variance_convention: Literal["arm_specific_unknown_variance"] = (
        "arm_specific_unknown_variance"
    )


type BayesianLikelihood = Annotated[
    BernoulliBinomialLikelihood | NormalUnknownMeanVarianceLikelihood,
    Field(discriminator="likelihood_family"),
]


class PracticalEquivalenceRegion(ContractModel):
    """Explicit raw-effect region of practical equivalence."""

    lower: FiniteFloat
    upper: FiniteFloat
    unit: MetricUnit
    effect_scale: Literal["raw_treatment_minus_control"] = "raw_treatment_minus_control"

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if self.lower >= self.upper:
            raise ValueError("ROPE lower bound must be strictly less than upper bound")
        return self


class BayesianAnalysisExecutionRequest(ContractModel):
    """Explicit priors, likelihood, and analysis request for Bayesian A/B inference."""

    request_id: NonEmptyStr
    analysis_request: AnalysisRequest
    treatment_prior: BayesianPrior
    control_prior: BayesianPrior
    likelihood: BayesianLikelihood
    rope: PracticalEquivalenceRegion | None = None

    @model_validator(mode="after")
    def validate_bayesian_declarations(self) -> Self:
        design = self.analysis_request.study_design
        if (
            design.design_type != "randomized_experiment"
            or design.method is not RandomizedAnalysisMethod.BAYESIAN_AB
        ):
            raise ValueError("Bayesian execution requires RandomizedAnalysisMethod.BAYESIAN_AB")
        if not isinstance(self.analysis_request.uncertainty, RequestedCredibleLevel):
            raise ValueError("Bayesian execution requires an explicit credible level")

        if isinstance(self.likelihood, BernoulliBinomialLikelihood):
            if not isinstance(self.treatment_prior, BetaPrior) or not isinstance(
                self.control_prior, BetaPrior
            ):
                raise ValueError("Bernoulli/Binomial likelihood requires Beta priors for both arms")
        elif not isinstance(self.treatment_prior, NormalInverseGammaPrior) or not isinstance(
            self.control_prior, NormalInverseGammaPrior
        ):
            raise ValueError(
                "Normal unknown-variance likelihood requires Normal-Inverse-Gamma priors "
                "for both arms"
            )

        if self.rope is not None and self.rope.unit != self.analysis_request.outcome.metric.unit:
            raise ValueError("ROPE unit must match the outcome metric unit")
        return self


class BayesianComputationStatus(StrEnum):
    """Terminal state of one Bayesian computation."""

    COMPLETED = "completed"
    ABSTAINED = "abstained"
    UNSUPPORTED = "unsupported"
    INVALID = "invalid"


class BayesianDiagnosticCategory(StrEnum):
    """Stable Bayesian diagnostic families."""

    DECLARATION = "declaration"
    INPUT = "input"
    SAMPLE = "sample"
    ASSUMPTION = "assumption"
    COMPUTATION = "computation"
    RESULT = "result"


class BayesianDiagnosticStatus(StrEnum):
    """Observed state of a Bayesian diagnostic."""

    PASSED = "passed"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class BayesianDiagnosticContext(ContractModel):
    """One canonical JSON-safe diagnostic context value."""

    key: NonEmptyStr
    value: ScalarValue

    @field_validator("value")
    @classmethod
    def reject_nonfinite_floats(cls, value: ScalarValue) -> ScalarValue:
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("diagnostic context floats must be finite")
        return value


class BayesianDiagnostic(ContractModel):
    """Structured Bayesian diagnostic with canonical context ordering."""

    code: NonEmptyStr
    category: BayesianDiagnosticCategory
    severity: DiagnosticSeverity = DiagnosticSeverity.INFO
    status: BayesianDiagnosticStatus
    message: NonEmptyStr
    context: tuple[BayesianDiagnosticContext, ...] = ()
    recommended_action: NonEmptyStr | None = None

    @field_validator("context", mode="before")
    @classmethod
    def expand_context_mapping(cls, value: object) -> object:
        if isinstance(value, Mapping):
            if any(not isinstance(key, str) for key in value):
                raise ValueError("diagnostic context keys must be strings")
            return tuple({"key": key, "value": item} for key, item in value.items())
        return value

    @field_validator("context")
    @classmethod
    def canonicalize_context(
        cls,
        value: tuple[BayesianDiagnosticContext, ...],
    ) -> tuple[BayesianDiagnosticContext, ...]:
        canonical = tuple(sorted(value, key=lambda entry: entry.key))
        keys = tuple(entry.key for entry in canonical)
        if len(keys) != len(set(keys)):
            raise ValueError("diagnostic context keys must be unique")
        return canonical


class BayesianAbstentionReason(ContractModel):
    """Typed explanation for a non-numerical Bayesian result."""

    code: NonEmptyStr
    message: NonEmptyStr
    missing_or_invalid_information: tuple[NonEmptyStr, ...] = ()


class BayesianComputationConfig(ContractModel):
    """Versioned deterministic numerical configuration."""

    configuration_version: Literal["1"] = "1"
    interval_method: Literal["equal_tailed"] = "equal_tailed"
    effect_method: Literal["deterministic_quadrature"] = "deterministic_quadrature"
    quadrature_absolute_tolerance: PositiveFiniteFloat = 1e-10
    quadrature_relative_tolerance: PositiveFiniteFloat = 1e-10
    root_absolute_tolerance: PositiveFiniteFloat = 1e-10
    integration_subdivision_limit: PositiveInt = 250
    configuration_id: NonEmptyStr = "bayesian_ab_analysis"

    def configuration_provenance(self) -> ProvenanceRecord:
        """Return stable provenance for the embedded numerical choices."""
        return ProvenanceRecord(
            source_type=ProvenanceSourceType.CONFIGURATION,
            source_id=self.configuration_id,
            source_version=self.configuration_version,
        )


class BetaPosteriorSummary(ContractModel):
    """Exact Beta posterior and observed counts for one binary arm."""

    posterior_family: Literal["beta"] = "beta"
    posterior_family_version: Literal["1"] = "1"
    arm_id: NonEmptyStr
    n: PositiveInt
    successes: NonNegativeInt
    failures: NonNegativeInt
    prior: BetaPrior
    posterior_alpha: PositiveFiniteFloat
    posterior_beta: PositiveFiniteFloat
    posterior_mean: Probability
    posterior_variance: NonNegativeFiniteFloat
    credible_interval: CredibleInterval

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.successes + self.failures != self.n:
            raise ValueError("successes plus failures must equal n")
        return self


class NormalInverseGammaPosteriorSummary(ContractModel):
    """Exact NIG posterior and marginal Student-t mean summary for one arm."""

    posterior_family: Literal["normal_inverse_gamma"] = "normal_inverse_gamma"
    posterior_family_version: Literal["1"] = "1"
    parameterization: Literal["inverse_gamma_shape_scale"] = "inverse_gamma_shape_scale"
    arm_id: NonEmptyStr
    n: PositiveInt
    sample_mean: FiniteFloat
    centered_sum_of_squares: NonNegativeFiniteFloat
    prior: NormalInverseGammaPrior
    posterior_mu: FiniteFloat
    posterior_kappa: PositiveFiniteFloat
    posterior_alpha: PositiveFiniteFloat
    posterior_beta: PositiveFiniteFloat
    marginal_degrees_of_freedom: PositiveFiniteFloat
    marginal_location: FiniteFloat
    marginal_scale: PositiveFiniteFloat
    marginal_mean_variance: NonNegativeFiniteFloat
    credible_interval: CredibleInterval


type BayesianArmPosterior = Annotated[
    BetaPosteriorSummary | NormalInverseGammaPosteriorSummary,
    Field(discriminator="posterior_family"),
]


class QuadratureDiagnostics(ContractModel):
    """Deterministic numerical-integration accuracy metadata."""

    method: Literal["adaptive_quadrature"] = "adaptive_quadrature"
    maximum_absolute_error: NonNegativeFiniteFloat
    absolute_tolerance: PositiveFiniteFloat
    relative_tolerance: PositiveFiniteFloat
    reproducible: Literal[True] = True


class RopeProbabilitySummary(ContractModel):
    """Posterior probability partition around an explicit ROPE."""

    rope: PracticalEquivalenceRegion
    probability_below: Probability
    probability_inside: Probability
    probability_above: Probability
    method: Literal["deterministic_quadrature"] = "deterministic_quadrature"

    @model_validator(mode="after")
    def validate_partition(self) -> Self:
        total = self.probability_below + self.probability_inside + self.probability_above
        if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("ROPE probabilities must sum to one")
        return self


class PosteriorEffectSummary(ContractModel):
    """Posterior treatment-minus-control effect quantities."""

    estimand: Literal["treatment_minus_control"] = "treatment_minus_control"
    effect_scale: Literal["raw_treatment_minus_control"] = "raw_treatment_minus_control"
    posterior_mean: FiniteFloat
    posterior_median: FiniteFloat
    posterior_standard_deviation: NonNegativeFiniteFloat
    credible_interval: CredibleInterval
    interval_method: Literal["equal_tailed"] = "equal_tailed"
    probability_of_superiority: PosteriorProbability
    probability_treatment_is_better: PosteriorProbability | None = None
    metric_direction: OutcomeDirection
    rope_probability: RopeProbabilitySummary | None = None
    computation_method: Literal["deterministic_quadrature"] = "deterministic_quadrature"
    quadrature: QuadratureDiagnostics


class BayesianAnalysisResult(ContractModel):
    """Complete Bayesian result, kept separate from frequentist result contracts."""

    outcome_type: Literal["bayesian_randomized_analysis"] = "bayesian_randomized_analysis"
    schema_version: Literal["1"] = "1"
    request_id: NonEmptyStr
    analysis_request: AnalysisRequest | None = None
    metric: MetricDefinition | None = None
    estimand: EstimandDefinition | None = None
    treatment_arm_id: NonEmptyStr | None = None
    control_arm_id: NonEmptyStr | None = None
    status: BayesianComputationStatus
    likelihood: BayesianLikelihood | None = None
    treatment_prior: BayesianPrior | None = None
    control_prior: BayesianPrior | None = None
    treatment_posterior: BayesianArmPosterior | None = None
    control_posterior: BayesianArmPosterior | None = None
    effect: PosteriorEffectSummary | None = None
    assumptions: tuple[AssumptionAssessment, ...]
    diagnostics: tuple[BayesianDiagnostic, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: ProvenanceRecords
    configuration: BayesianComputationConfig
    configuration_provenance: ProvenanceRecord | None = None
    abstention_reason: BayesianAbstentionReason | None = None

    @field_validator("diagnostics")
    @classmethod
    def canonicalize_diagnostics(
        cls,
        value: tuple[BayesianDiagnostic, ...],
    ) -> tuple[BayesianDiagnostic, ...]:
        return tuple(
            sorted(
                value,
                key=lambda diagnostic: json.dumps(
                    diagnostic.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            )
        )

    @model_validator(mode="after")
    def validate_result_shape(self) -> Self:
        expected_configuration = self.configuration.configuration_provenance()
        if self.configuration_provenance is None:
            object.__setattr__(self, "configuration_provenance", expected_configuration)
        elif self.configuration_provenance != expected_configuration:
            raise ValueError("configuration_provenance must match configuration")

        if self.status is BayesianComputationStatus.COMPLETED:
            required = (
                self.analysis_request,
                self.metric,
                self.estimand,
                self.treatment_arm_id,
                self.control_arm_id,
                self.likelihood,
                self.treatment_prior,
                self.control_prior,
                self.treatment_posterior,
                self.control_posterior,
                self.effect,
            )
            if any(item is None for item in required):
                raise ValueError("numerical Bayesian results require declarations and posteriors")
            if self.abstention_reason is not None:
                raise ValueError("numerical Bayesian results must not include an abstention reason")
            assert self.analysis_request is not None
            assert self.metric is not None
            assert self.estimand is not None
            assert self.treatment_posterior is not None
            assert self.control_posterior is not None
            assert self.effect is not None
            if self.metric != self.analysis_request.outcome.metric:
                raise ValueError("metric must match analysis_request outcome metric")
            if self.estimand != self.analysis_request.estimand:
                raise ValueError("estimand must match analysis_request estimand")
            credible_level = self.analysis_request.uncertainty
            assert isinstance(credible_level, RequestedCredibleLevel)
            intervals = (
                self.treatment_posterior.credible_interval,
                self.control_posterior.credible_interval,
                self.effect.credible_interval,
            )
            if any(
                interval.credible_level != credible_level.level for interval in intervals
            ):
                raise ValueError("all credible intervals must match the requested credible level")
        else:
            if any(
                item is not None
                for item in (self.treatment_posterior, self.control_posterior, self.effect)
            ):
                raise ValueError("non-numerical Bayesian results must not include posteriors")
            if self.abstention_reason is None:
                raise ValueError("non-numerical Bayesian results require an abstention reason")
        return self


__all__ = [
    "BayesianAbstentionReason",
    "BayesianAnalysisResult",
    "BayesianAnalysisExecutionRequest",
    "BayesianArmPosterior",
    "BayesianComputationConfig",
    "BayesianComputationStatus",
    "BayesianDiagnostic",
    "BayesianDiagnosticCategory",
    "BayesianDiagnosticContext",
    "BayesianDiagnosticStatus",
    "BayesianLikelihood",
    "BayesianPrior",
    "BernoulliBinomialLikelihood",
    "BetaPosteriorSummary",
    "BetaPrior",
    "NormalInverseGammaPosteriorSummary",
    "NormalInverseGammaPrior",
    "NormalUnknownMeanVarianceLikelihood",
    "PosteriorEffectSummary",
    "PracticalEquivalenceRegion",
    "QuadratureDiagnostics",
    "RopeProbabilitySummary",
]
