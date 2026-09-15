"""Two-group doubly robust HTE adapter using existing owned subgroup contracts."""

from __future__ import annotations

from time import perf_counter

import numpy as np
from scipy.stats import chi2  # type: ignore[import-untyped]

from packages.observability.base import BaseObservabilityProvider
from packages.observability.noop import NoOpObservabilityProvider

from ...provenance import DiagnosticSeverity, ProvenanceRecords
from ...validation.table import AnalysisTable
from ..advanced.models import AdvancedEstimatorConfig, AdvancedFailureCode
from ..dml.folds import canonical_observation_key
from ..dml.numerics import assess_dml_overlap, build_nuisance_diagnostics
from ..hte.assignment import subgroup_rule
from ..hte.models import HTEExecutionRequest, HTEModifierType
from ..hte.numerics import holm_adjust
from ..hte.results import (
    GlobalHeterogeneityEvidence,
    HeterogeneousEffectResult,
    HTEDiagnostic,
    HTEDiagnosticStatus,
    HTEEvidenceStatus,
    HTEStatus,
    HTESubgroupStatus,
    InteractionEffectResult,
    MultiplicityContext,
    SubgroupEffectResult,
)
from ..hte.validation import HTEValidationDisposition, validate_hte_input
from ..propensity.models import OverlapStatus
from ..variables import VariableRole
from . import dependency
from .common import (
    adapter_provenance,
    effect_inference,
    fit_estimator,
    make_splits,
    normalize_inference,
    scalar,
    validate_identification,
)
from .dependency import AdapterError
from .nuisance import audit_nuisances, build_nuisances
from .observability import observe_result


class EconMLHTEAdapter:
    adapter_id = "econml_linear_dr_subgroups"
    supported_estimand = "cate"
    treatment_type = "binary"
    outcome_type = "continuous"

    def __init__(
        self,
        *,
        configuration: AdvancedEstimatorConfig | None = None,
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self.configuration = configuration or AdvancedEstimatorConfig()
        self.observability_provider = observability_provider or NoOpObservabilityProvider()

    def analyze(
        self,
        execution: HTEExecutionRequest,
        table: AnalysisTable,
        *,
        provenance: ProvenanceRecords,
    ) -> HeterogeneousEffectResult:
        started = perf_counter()
        result = self._analyze(execution, table, provenance=provenance)
        observe_result(
            self.observability_provider,
            result,
            estimator="LinearDRLearner",
            category="hte",
            inference=self.configuration.inference_mode,
            duration_ms=(perf_counter() - started) * 1000,
        )
        return result

    def _analyze(
        self,
        execution: HTEExecutionRequest,
        table: AnalysisTable,
        *,
        provenance: ProvenanceRecords,
    ) -> HeterogeneousEffectResult:
        base = _initial(execution, table, provenance)
        try:
            execution = HTEExecutionRequest.model_validate(execution.model_dump())
            validated = validate_hte_input(
                execution, table, supported_method="doubly_robust_subgroup_effects"
            )
            groups = tuple(
                SubgroupEffectResult(
                    subgroup_id=definition.subgroup_id,
                    label=definition.label,
                    rule=subgroup_rule(execution, definition),
                    sample_counts=counts.as_public_counts(),
                    status=HTESubgroupStatus.ABSTAINED,
                    abstention_reason="Input validation did not complete.",
                )
                for definition, counts in zip(
                    execution.modifier.subgroups, validated.subgroup_counts, strict=True
                )
            )
            base = base.model_copy(
                update={
                    "subgroup_results": groups,
                    "retained_count": len(validated.rows),
                    "unassigned_count": validated.unassigned_count,
                    "assignment_fingerprint_sha256": validated.assignment_fingerprint_sha256,
                }
            )
            if validated.disposition is not HTEValidationDisposition.VALID:
                primary = validated.diagnostics[0]
                return _failed(
                    base,
                    primary.code,
                    primary.message,
                    HTEStatus(validated.disposition.value),
                    validated.diagnostics,
                )
            validate_identification(execution.identification_result)
            if execution.configuration.analysis_version != "hte-dr-v1":
                return _failed(
                    base,
                    "hte.configuration.version_mismatch",
                    "DR estimation requires explicit hte-dr-v1 configuration.",
                    HTEStatus.UNSUPPORTED,
                )
            if (
                execution.modifier.modifier_type is not HTEModifierType.BINARY_CATEGORICAL
                or len(groups) != 2
            ):
                return _failed(
                    base,
                    AdvancedFailureCode.INVALID_EFFECT_MODIFIER,
                    "This adapter supports two pre-specified binary categorical groups only.",
                    HTEStatus.UNSUPPORTED,
                )
            if self.configuration.inference_mode != "statsmodels_hc1":
                return _failed(
                    base,
                    AdvancedFailureCode.UNSUPPORTED_INFERENCE,
                    "Only explicit statsmodels HC1 inference is supported.",
                    HTEStatus.UNSUPPORTED,
                )
            policy = execution.configuration
            if any(
                g.sample_counts.retained_count < policy.minimum_subgroup_retained
                or g.sample_counts.treated_count < policy.minimum_subgroup_treated
                or g.sample_counts.control_count < policy.minimum_subgroup_control
                for g in groups
            ):
                return _failed(
                    base,
                    "hte.subgroup.insufficient_support",
                    "Both declared groups must satisfy sample support minima.",
                )
            backend = dependency.load_econml()
            rows = tuple(
                sorted(validated.rows, key=lambda r: canonical_observation_key(r.observation_id))
            )
            config = policy.dml
            plan, splits = make_splits(
                tuple(r.observation_id for r in rows), tuple(r.treated for r in rows), config
            )
            y = np.asarray([r.outcome for r in rows], dtype=float)
            t = np.asarray([int(r.treated) for r in rows])
            # validate_hte_input appends exactly one registered non-reference indicator.
            features = np.asarray([r.features for r in rows], dtype=float)
            x = features[:, -1:]
            w = features[:, :-1]
            nuisance_features = np.column_stack((x, w))
            model_y, model_t = build_nuisances(self.configuration, config.random_seed, dr=True)
            estimator = backend.dr.LinearDRLearner(
                model_regression=model_y,
                model_propensity=model_t,
                categories=[0, 1],
                cv=splits,
                random_state=config.random_seed,
                discrete_outcome=False,
                fit_cate_intercept=True,
                min_propensity=0.0,
                trimming_threshold=None,
                mc_iters=None,
                allow_missing=False,
                use_ray=False,
            )
            fit_estimator(
                estimator,
                y,
                t,
                X=x,
                W=w,
                inference=backend.inference.StatsModelsInferenceDiscrete(cov_type="HC1"),
            )
            audit = audit_nuisances(
                estimator,
                features=nuisance_features,
                treatments=t,
                splits=splits,
                plan=plan,
                feature_names=(validated.feature_names[-1], *validated.feature_names[:-1]),
                config=self.configuration,
                dr=True,
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
                estimator_class="econml.dr.LinearDRLearner",
                identification=execution.identification_result,
                columns=(
                    (
                        execution.modifier.variable_id,
                        execution.modifier.column,
                        VariableRole.EFFECT_MODIFIER,
                    ),
                    *(
                        (c.variable_id, c.column, VariableRole.ADJUSTMENT)
                        for c in execution.binding.covariates
                    ),
                ),
                config=self.configuration,
                plan=plan,
                dr=True,
            )
            diagnosed = []
            for group in groups:
                indexes = [i for i, r in enumerate(rows) if r.subgroup_id == group.subgroup_id]
                local = assess_dml_overlap(
                    scores=tuple(audit.treatment_predictions[i] for i in indexes),
                    treated=tuple(rows[i].treated for i in indexes),
                    config=config,
                )
                diagnosed.append(group.model_copy(update={"overlap": local}))
            base = base.model_copy(
                update={
                    "fold_plan": plan,
                    "fold_fits": audit.fold_fits,
                    "global_overlap": overlap,
                    "nuisance_diagnostics": nuisance,
                    "adapter_provenance": recorded,
                    "subgroup_results": tuple(diagnosed),
                }
            )
            if overlap.status is OverlapStatus.SEVERE or any(
                g.overlap is not None and g.overlap.status is OverlapStatus.SEVERE
                for g in diagnosed
            ):
                return _failed(
                    base,
                    "hte.overlap.severe",
                    "Global or subgroup cross-fitted propensities fail overlap policy.",
                )
            results = [
                effect_inference(
                    estimator, np.asarray([[indicator]], dtype=float), config.confidence_level
                )
                for indicator in (0, 1)
            ]
            try:
                info = estimator.coef__inference(T=1)
                scalar(info.point_estimate, AdvancedFailureCode.NONFINITE_ESTIMATE)
                scalar(info.stderr, AdvancedFailureCode.NONFINITE_UNCERTAINTY)
                contrast, contrast_inference = normalize_inference(
                    info, info.conf_int(alpha=1 - config.confidence_level), config.confidence_level
                )
            except AdapterError:
                raise
            except Exception:
                raise AdapterError(
                    AdvancedFailureCode.INFERENCE_FAILURE, "Direct heterogeneity inference failed."
                ) from None
            adjusted = holm_adjust(tuple(inf.p_value for _, inf in results))
            completed = tuple(
                SubgroupEffectResult.model_validate(
                    {
                        **g.model_dump(),
                        "status": HTESubgroupStatus.COMPLETED,
                        "estimate": point,
                        "standard_error": inf.standard_error,
                        "confidence_interval": inf.confidence_interval,
                        "p_value": inf.p_value,
                        "adjusted_p_value": p,
                        "uncertainty_method": "doubly_robust_statsmodels_hc1",
                        "abstention_reason": None,
                    }
                )
                for g, (point, inf), p in zip(diagnosed, results, adjusted, strict=True)
            )
            interaction = InteractionEffectResult(
                reference_subgroup_id=groups[0].subgroup_id,
                comparison_subgroup_id=groups[1].subgroup_id,
                estimate=contrast,
                standard_error=contrast_inference.standard_error,
                confidence_interval=contrast_inference.confidence_interval,
                p_value=contrast_inference.p_value,
                adjusted_p_value=contrast_inference.p_value,
            )
            statistic = scalar(
                contrast_inference.statistic**2, AdvancedFailureCode.NONFINITE_UNCERTAINTY
            )
            p_value = float(chi2.sf(statistic, 1))
            return HeterogeneousEffectResult.model_validate(
                {
                    **base.model_dump(),
                    "status": HTEStatus.COMPLETED,
                    "subgroup_results": completed,
                    "interactions": (interaction,),
                    "abstention_reason": None,
                    "global_heterogeneity": GlobalHeterogeneityEvidence(
                        status=HTEEvidenceStatus.AVAILABLE,
                        method="doubly_robust_interaction_wald_chi_square",
                        statistic=statistic,
                        degrees_of_freedom=1,
                        p_value=p_value,
                        detected=p_value < 1 - config.confidence_level,
                    ),
                    "multiplicity": MultiplicityContext(
                        subgroup_effect_tests=2,
                        interaction_tests=1,
                        global_tests=1,
                        corrected_families=("subgroup_effects", "reference_interactions"),
                    ),
                    "diagnostics": (
                        HTEDiagnostic(
                            code="assumption.unverified",
                            severity=DiagnosticSeverity.WARNING,
                            status=HTEDiagnosticStatus.UNAVAILABLE,
                            message="Causal interpretation is conditional on declared assumptions.",
                        ),
                    ),
                }
            )
        except AdapterError as error:
            return _failed(
                base,
                error.code,
                str(error),
                HTEStatus.INVALID
                if error.code == "identification.invalid"
                else HTEStatus.ABSTAINED,
            )
        except Exception:
            return _failed(
                base,
                AdvancedFailureCode.INVALID_DATA_SHAPE,
                "Adapter input or required diagnostic evidence is invalid.",
                HTEStatus.INVALID,
            )


def _initial(
    execution: HTEExecutionRequest, table: AnalysisTable, provenance: ProvenanceRecords
) -> HeterogeneousEffectResult:
    # Populate subgroup summaries only after declaration revalidation.
    return HeterogeneousEffectResult(
        request_id=execution.request_id,
        execution_request=execution,
        method="doubly_robust_subgroup_effects",
        status=HTEStatus.ABSTAINED,
        analysis_semantics=execution.modifier.pre_specification,
        estimand=execution.identification_result.estimand,
        treatment=execution.identification_result.treatment,
        modifier=execution.modifier,
        subgroup_results=(),
        interactions=(),
        global_heterogeneity=GlobalHeterogeneityEvidence(
            status=HTEEvidenceStatus.UNAVAILABLE,
            method="doubly_robust_interaction_wald_chi_square",
            unavailable_reason="No supported direct inference.",
        ),
        multiplicity=MultiplicityContext(
            subgroup_effect_tests=0, interaction_tests=0, global_tests=0, corrected_families=()
        ),
        global_overlap=None,
        fold_plan=None,
        fold_fits=(),
        nuisance_diagnostics=None,
        assignment_fingerprint_sha256=None,
        raw_count=len(table.rows),
        retained_count=0,
        unassigned_count=len(table.rows),
        assumptions=execution.identification_result.assumptions,
        diagnostics=(),
        provenance=provenance,
        abstention_reason="INVALID_DATA_SHAPE",
    )


def _failed(
    base: HeterogeneousEffectResult,
    code: str,
    message: str,
    status: HTEStatus = HTEStatus.ABSTAINED,
    diagnostics: tuple[HTEDiagnostic, ...] = (),
) -> HeterogeneousEffectResult:
    return base.model_copy(
        update={
            "status": status,
            "abstention_reason": code,
            "diagnostics": diagnostics
            or (
                HTEDiagnostic(
                    code=code,
                    severity=DiagnosticSeverity.FATAL,
                    status=HTEDiagnosticStatus.UNAVAILABLE,
                    message=message,
                ),
            ),
            "subgroup_results": tuple(
                g.model_copy(update={"abstention_reason": code}) for g in base.subgroup_results
            ),
        }
    )
