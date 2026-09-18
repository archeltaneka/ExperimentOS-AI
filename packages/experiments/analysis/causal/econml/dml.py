"""Optional LinearDML behind owned identification, diagnostics and result contracts."""

from __future__ import annotations

from time import perf_counter

import numpy as np

from packages.observability.base import BaseObservabilityProvider
from packages.observability.noop import NoOpObservabilityProvider

from ...provenance import DiagnosticSeverity, ProvenanceRecords
from ...validation.table import AnalysisTable
from ..advanced.conformance import configuration_fingerprint
from ..advanced.models import AdvancedCausalResult, AdvancedEstimatorConfig, AdvancedFailureCode
from ..diagnostics import EvidenceLimitation, EvidenceLimitationCode
from ..dml.models import (
    DMLDiagnostic,
    DMLDiagnosticCategory,
    DMLDiagnosticStatus,
    DMLExecutionRequest,
    DMLSampleCounts,
)
from ..dml.numerics import assess_dml_overlap, build_nuisance_diagnostics, summarize_residuals
from ..dml.results import DMLAbstentionReason, DMLStatus
from ..dml.validation import DMLValidationDisposition, validate_dml_input
from ..propensity.models import OverlapStatus
from ..variables import VariableRole
from . import dependency
from .common import (
    adapter_provenance,
    effect_inference,
    fit_estimator,
    make_splits,
    validate_identification,
)
from .dependency import AdapterError
from .nuisance import audit_nuisances, build_nuisances
from .observability import observe_result


class EconMLDMLAdapter:
    """Explicit constant-effect ATE adapter; never selected by baseline dispatch."""

    adapter_id = "econml_linear_dml"
    supported_estimand = "ate"
    treatment_type = "binary"
    outcome_type = "continuous"

    def __init__(
        self,
        *,
        configuration: AdvancedEstimatorConfig | None = None,
        constant_effect_assumption: bool | None = None,
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self.configuration = configuration or AdvancedEstimatorConfig()
        if constant_effect_assumption is not None:
            self.configuration = AdvancedEstimatorConfig.model_validate(
                {
                    **self.configuration.model_dump(),
                    "constant_effect_assumption": constant_effect_assumption,
                }
            )
        self.observability_provider = observability_provider or NoOpObservabilityProvider()

    def analyze(
        self,
        execution: DMLExecutionRequest,
        table: AnalysisTable,
        *,
        provenance: ProvenanceRecords,
    ) -> AdvancedCausalResult:
        started = perf_counter()
        result = self._analyze(execution, table, provenance=provenance)
        try:
            result = result.model_copy(
                update={
                    "configuration_fingerprint_sha256": configuration_fingerprint(
                        execution, "econml_linear_dml", self.configuration
                    )
                }
            )
        except (TypeError, ValueError, AttributeError):
            pass  # Malformed input refusals retain the safe diagnostic, not a fabricated digest.
        observe_result(
            self.observability_provider,
            result,
            estimator="LinearDML",
            category="dml",
            inference=self.configuration.inference_mode,
            duration_ms=(perf_counter() - started) * 1000,
        )
        return result

    def _analyze(
        self,
        execution: DMLExecutionRequest,
        table: AnalysisTable,
        *,
        provenance: ProvenanceRecords,
    ) -> AdvancedCausalResult:
        counts = DMLSampleCounts(
            raw_count=len(table.rows),
            retained_count=0,
            treated_count=0,
            control_count=0,
            complete_case_excluded_count=len(table.rows),
        )
        base = AdvancedCausalResult(
            execution_request=execution,
            configuration=self.configuration,
            status=DMLStatus.ABSTAINED,
            sample_counts=counts,
            evidence_limitations=tuple(
                {
                    item.code: item
                    for item in (
                        *execution.identification_result.evidence_limitations,
                        EvidenceLimitation(
                            code=EvidenceLimitationCode.PARTIALLY_LINEAR_MODEL_RESTRICTION,
                            description=(
                                "Full-population ATE requires the declared constant treatment "
                                "effect; heterogeneity can produce a "
                                "propensity-variance-weighted effect."
                            ),
                            provenance=provenance,
                        ),
                        EvidenceLimitation(
                            code=EvidenceLimitationCode.NUISANCE_MODEL_MISSPECIFICATION,
                            description=(
                                "Cross-fitting does not prove nuisance consistency "
                                "or valid asymptotic interval coverage."
                            ),
                            provenance=provenance,
                        ),
                    )
                }.values()
            ),
            provenance=provenance,
            abstention_reason=DMLAbstentionReason(
                code="INVALID_DATA_SHAPE", message="Input validation did not complete."
            ),
        )
        try:
            # Revalidation catches mutated/stale owned declarations before optional fitting.
            execution = DMLExecutionRequest.model_validate(execution.model_dump())
            validated = validate_dml_input(execution, table)
            base = base.model_copy(update={"sample_counts": validated.sample_counts})
            if validated.disposition is not DMLValidationDisposition.VALID:
                primary = validated.diagnostics[0]
                return _failed(
                    base,
                    primary.code,
                    primary.message,
                    DMLStatus(validated.disposition.value),
                    validated.diagnostics,
                )
            validate_identification(execution.identification_result)
            if self.configuration.inference_mode != "statsmodels_hc1":
                return _failed(
                    base,
                    AdvancedFailureCode.UNSUPPORTED_INFERENCE,
                    "Only explicit statsmodels HC1 inference is supported.",
                    DMLStatus.UNSUPPORTED,
                )
            if not self.configuration.constant_effect_assumption:
                return _failed(
                    base,
                    AdvancedFailureCode.UNSUPPORTED_ESTIMAND,
                    "Full-population ATE requires an explicit constant-effect assumption.",
                    DMLStatus.UNSUPPORTED,
                )
            backend = dependency.load_econml()
            config = execution.configuration
            rows = validated.rows
            plan, splits = make_splits(
                tuple(r.observation_id for r in rows), tuple(r.treated for r in rows), config
            )
            outcome = np.asarray([r.outcome for r in rows], dtype=float)
            treatment = np.asarray([int(r.treated) for r in rows])
            features = np.asarray([r.features for r in rows], dtype=float)
            model_y, model_t = build_nuisances(self.configuration, config.random_seed, dr=False)
            estimator = backend.dml.LinearDML(
                model_y=model_y,
                model_t=model_t,
                discrete_treatment=True,
                discrete_outcome=False,
                categories=[0, 1],
                cv=splits,
                random_state=config.random_seed,
                fit_cate_intercept=True,
                mc_iters=None,
                allow_missing=False,
                use_ray=False,
            )
            fit_estimator(
                estimator,
                outcome,
                treatment,
                X=None,
                W=features,
                inference=backend.inference.StatsModelsInference(cov_type="HC1"),
            )
            audit = audit_nuisances(
                estimator,
                features=features,
                treatments=treatment,
                splits=splits,
                plan=plan,
                feature_names=tuple(c.variable_id for c in execution.binding.covariates),
                config=self.configuration,
                dr=False,
            )
            overlap = assess_dml_overlap(
                scores=audit.treatment_predictions,
                treated=tuple(r.treated for r in rows),
                config=config,
            )
            nuisance = build_nuisance_diagnostics(
                outcome=tuple(r.outcome for r in rows),
                outcome_prediction=audit.outcome_predictions,
                treatment=tuple(r.treated for r in rows),
                treatment_prediction=audit.treatment_predictions,
                config=config,
            )
            recorded = adapter_provenance(
                backend=backend,
                adapter_id=self.adapter_id,
                estimator_class="econml.dml.LinearDML",
                identification=execution.identification_result,
                columns=tuple(
                    (c.variable_id, c.column, VariableRole.ADJUSTMENT)
                    for c in execution.binding.covariates
                ),
                config=self.configuration,
                plan=plan,
                dr=False,
            )
            base = base.model_copy(
                update={
                    "fold_plan": plan,
                    "fold_fits": audit.fold_fits,
                    "overlap": overlap,
                    "nuisance_diagnostics": nuisance,
                    "adapter_provenance": recorded,
                }
            )
            if overlap.status is OverlapStatus.SEVERE:
                return _failed(
                    base,
                    "dml.overlap.severe",
                    "Actual cross-fitted propensities fail overlap policy.",
                )
            treatment_norm = sum(
                (float(t) - p) ** 2
                for t, p in zip(treatment, audit.treatment_predictions, strict=True)
            )
            residuals = tuple(
                y - p for y, p in zip(outcome, audit.outcome_predictions, strict=True)
            )
            if treatment_norm <= config.treatment_residual_tolerance:
                return _failed(
                    base,
                    "dml.degenerate_treatment_residual",
                    "Residual treatment variation is insufficient.",
                )
            if (
                summarize_residuals(residuals).variance
                <= config.outcome_residual_variance_tolerance
            ):
                return _failed(
                    base,
                    "dml.degenerate_outcome_residual",
                    "Residual outcome variation is insufficient.",
                )
            point, inference = effect_inference(estimator, None, config.confidence_level)
            return AdvancedCausalResult.model_validate(
                {
                    **base.model_dump(),
                    "status": DMLStatus.COMPLETED,
                    "point_estimate": point,
                    "inference": inference,
                    "abstention_reason": None,
                    "diagnostics": (
                        DMLDiagnostic(
                            code="assumption.unverified",
                            category=DMLDiagnosticCategory.IDENTIFICATION,
                            severity=DiagnosticSeverity.WARNING,
                            status=DMLDiagnosticStatus.UNAVAILABLE,
                            message="Causal interpretation is conditional on declared assumptions.",
                        ),
                    ),
                }
            )
        except AdapterError as error:
            status = (
                DMLStatus.INVALID if error.code == "identification.invalid" else DMLStatus.ABSTAINED
            )
            return _failed(base, error.code, str(error), status)
        except Exception:
            return _failed(
                base,
                AdvancedFailureCode.INVALID_DATA_SHAPE,
                "Adapter input or required diagnostic evidence is invalid.",
                DMLStatus.INVALID,
            )


def _failed(
    base: AdvancedCausalResult,
    code: str,
    message: str,
    status: DMLStatus = DMLStatus.ABSTAINED,
    diagnostics: tuple[DMLDiagnostic, ...] = (),
) -> AdvancedCausalResult:
    # A failed result retains the input echo, including invalid copied declarations.
    # Revalidating that echo here would let its ValidationError escape the boundary.
    return base.model_copy(
        update={
            "status": status,
            "point_estimate": None,
            "inference": None,
            "abstention_reason": DMLAbstentionReason(code=code, message=message),
            "diagnostics": diagnostics
            or (
                DMLDiagnostic(
                    code=code,
                    category=DMLDiagnosticCategory.NUISANCE,
                    severity=DiagnosticSeverity.FATAL,
                    status=DMLDiagnosticStatus.UNAVAILABLE,
                    message=message,
                ),
            ),
        }
    )
