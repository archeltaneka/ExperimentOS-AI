"""Normalize untrusted routing once into explicit owned statistical requests."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, ValidationError

from ..base import ContractModel, NonEmptyStr, PositiveInt, Probability
from ..causal.advanced.models import AdvancedEstimatorConfig
from ..causal.did.models import DifferenceInDifferencesExecutionRequest
from ..causal.dml.models import DMLConfig, DMLDataBinding
from ..causal.dowhy.models import DoWhyConfig, DoWhyDataBinding
from ..causal.hte.models import EffectModifierDefinition, HTEConfig, HTEDataBinding
from ..causal.ipw.models import IPWConfig, IPWOutcomeBinding
from ..causal.models import ObservationalAnalysisRequest
from ..causal.propensity.models import (
    PropensityConfig,
    PropensityDataBinding,
    PropensityExecutionRequest,
)
from ..impact.inputs import BusinessImpactRequest
from ..provenance import Diagnostic, DiagnosticOutcome, DiagnosticSeverity
from ..randomized.bayesian.models import BayesianAnalysisExecutionRequest
from ..randomized.cuped.models import CupedAnalysisExecutionRequest
from ..randomized.sequential.models import SequentialAnalysisPlan
from ..randomized.service import RandomizedAnalysisExecutionRequest
from ..requests import AnalysisRequest
from ..results import AbstentionReason
from ..study_designs import RandomizedExperimentDesign
from ..validation.bindings import AnalysisDataBinding
from .datasets import DatasetReference


def refusal_diagnostic(code: str) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        outcome=DiagnosticOutcome.FAILED,
        message="Explicit supported inputs and provenance are required; no values were inferred.",
    )


def refusal_reason(code: str) -> AbstentionReason:
    return AbstentionReason(
        code=code,
        message="Analysis withheld because required declarations are missing or invalid.",
        missing_or_invalid_information=(code,),
    )


class BusinessInputRefusal(ContractModel):
    diagnostics: tuple[Diagnostic, ...]
    abstention: AbstentionReason


class AnalysisRoutingRefusal(ContractModel):
    method: str | None = None
    request_id: str | None = None
    experiment_id: str
    status: Literal["invalid", "abstained"]
    diagnostics: tuple[Diagnostic, ...]
    abstention: AbstentionReason


class _Common(ContractModel):
    schema_version: Literal["1"] = "1"
    request_id: NonEmptyStr
    experiment_id: NonEmptyStr
    business: BusinessImpactRequest | BusinessInputRefusal | None = None


class FixedHorizonWorkflowRequest(_Common):
    method: Literal["randomized_fixed_horizon"]
    execution: RandomizedAnalysisExecutionRequest
    binding: AnalysisDataBinding
    dataset: DatasetReference


class CupedWorkflowRequest(_Common):
    method: Literal["cuped"]
    execution: CupedAnalysisExecutionRequest
    binding: AnalysisDataBinding
    dataset: DatasetReference


class BayesianWorkflowRequest(_Common):
    method: Literal["bayesian_ab"]
    execution: BayesianAnalysisExecutionRequest
    binding: AnalysisDataBinding
    dataset: DatasetReference


class SequentialLookInput(ContractModel):
    look_index: PositiveInt
    information_time: Probability
    plan_fingerprint: NonEmptyStr
    analysis_request: AnalysisRequest
    binding: AnalysisDataBinding
    dataset: DatasetReference
    executed_at: datetime | None = None


class SequentialWorkflowRequest(_Common):
    method: Literal["sequential"]
    plan: SequentialAnalysisPlan
    looks: tuple[SequentialLookInput, ...]


class DidWorkflowRequest(_Common):
    method: Literal["did"]
    execution: DifferenceInDifferencesExecutionRequest
    dataset: DatasetReference


class PropensityWorkflowRequest(_Common):
    method: Literal["propensity_diagnostics"]
    execution: PropensityExecutionRequest
    dataset: DatasetReference


class IPWWorkflowRequest(_Common):
    method: Literal["ipw_ate", "ipw_att"]
    analysis_request: ObservationalAnalysisRequest
    propensity_binding: PropensityDataBinding
    propensity_configuration: PropensityConfig
    binding: IPWOutcomeBinding
    configuration: IPWConfig
    dataset: DatasetReference


class _DMLFields(_Common):
    analysis_request: ObservationalAnalysisRequest
    binding: DMLDataBinding
    configuration: DMLConfig
    dataset: DatasetReference


class DMLWorkflowRequest(_DMLFields):
    method: Literal["dml"]


class EconMLDMLWorkflowRequest(_DMLFields):
    method: Literal["econml_dml"]
    adapter_configuration: AdvancedEstimatorConfig


class _HTEFields(_Common):
    analysis_request: ObservationalAnalysisRequest
    binding: HTEDataBinding
    configuration: HTEConfig
    modifier: EffectModifierDefinition
    dataset: DatasetReference


class HTEWorkflowRequest(_HTEFields):
    method: Literal["hte"]


class EconMLHTEWorkflowRequest(_HTEFields):
    method: Literal["econml_hte"]
    adapter_configuration: AdvancedEstimatorConfig


class DoWhyWorkflowRequest(_Common):
    method: Literal["dowhy"]
    analysis_request: ObservationalAnalysisRequest
    binding: DoWhyDataBinding
    configuration: DoWhyConfig
    dataset: DatasetReference | None = None


type WorkflowAnalysisRequest = Annotated[
    FixedHorizonWorkflowRequest
    | CupedWorkflowRequest
    | BayesianWorkflowRequest
    | SequentialWorkflowRequest
    | DidWorkflowRequest
    | PropensityWorkflowRequest
    | IPWWorkflowRequest
    | DMLWorkflowRequest
    | HTEWorkflowRequest
    | EconMLDMLWorkflowRequest
    | EconMLHTEWorkflowRequest
    | DoWhyWorkflowRequest,
    Field(discriminator="method"),
]
type AnalysisInput = WorkflowAnalysisRequest | AnalysisRoutingRefusal

WORKFLOW_REQUEST_ADAPTER: TypeAdapter[WorkflowAnalysisRequest] = TypeAdapter(
    WorkflowAnalysisRequest
)
SUPPORTED_METHODS = frozenset(
    {
        "randomized_fixed_horizon",
        "cuped",
        "bayesian_ab",
        "sequential",
        "did",
        "propensity_diagnostics",
        "ipw_ate",
        "ipw_att",
        "dml",
        "hte",
        "econml_dml",
        "econml_hte",
        "dowhy",
    }
)


def routing_refusal(
    code: str,
    *,
    experiment_id: str,
    method: str | None = None,
    request_id: str | None = None,
    status: Literal["invalid", "abstained"] = "invalid",
) -> AnalysisRoutingRefusal:
    return AnalysisRoutingRefusal(
        method=method,
        request_id=request_id,
        experiment_id=experiment_id,
        status=status,
        diagnostics=(refusal_diagnostic(code),),
        abstention=refusal_reason(code),
    )


def normalize_analysis_input(payload: object, *, experiment_id: str) -> AnalysisInput:
    """Only the boundary accepts JSON; malformed values are never retained in refusals."""
    if not isinstance(payload, dict):
        return routing_refusal(
            "analysis.method_ambiguous", experiment_id=experiment_id, status="abstained"
        )
    method = payload.get("method")
    if not isinstance(method, str) or not method.strip():
        return routing_refusal(
            "analysis.method_ambiguous", experiment_id=experiment_id, status="abstained"
        )
    if method not in SUPPORTED_METHODS:
        return routing_refusal(
            "analysis.method_unsupported",
            experiment_id=experiment_id,
            method=method,
            status="abstained",
        )
    request_id = payload.get("request_id")
    request_id = request_id if isinstance(request_id, str) else None
    try:
        if set(payload) - {"schema_version", "request_id", "method", "parameters", "business"}:
            raise ValueError("unknown fields")
        parameters = payload.get("parameters")
        if not isinstance(parameters, dict):
            raise ValueError("parameters required")
        if set(parameters) & {
            "schema_version",
            "request_id",
            "experiment_id",
            "method",
            "business",
        }:
            raise ValueError("reserved fields")
        business: BusinessImpactRequest | BusinessInputRefusal | None = None
        if payload.get("business") is not None:
            try:
                business = BusinessImpactRequest.model_validate(payload["business"])
            except (ValueError, TypeError):
                business = BusinessInputRefusal(
                    diagnostics=(refusal_diagnostic("analysis.business_input_invalid"),),
                    abstention=refusal_reason("analysis.business_input_invalid"),
                )
        request = WORKFLOW_REQUEST_ADAPTER.validate_python(
            {
                **parameters,
                "schema_version": payload.get("schema_version", "1"),
                "request_id": request_id,
                "method": method,
                "experiment_id": experiment_id,
                "business": business,
            }
        )
        validate_selection(request)
        return request
    except (ValidationError, ValueError, TypeError):
        return routing_refusal(
            "analysis.request_invalid",
            experiment_id=experiment_id,
            method=method,
            request_id=request_id,
        )


def validate_selection(request: WorkflowAnalysisRequest) -> None:
    """Identity/design agreement only; statistical eligibility belongs to analyzers."""
    if isinstance(
        request, (FixedHorizonWorkflowRequest, CupedWorkflowRequest, BayesianWorkflowRequest)
    ):
        expected = {
            "randomized_fixed_horizon": "fixed_horizon_ab",
            "cuped": "cuped",
            "bayesian_ab": "bayesian_ab",
        }[request.method]
        design = request.execution.analysis_request.study_design
        if not isinstance(design, RandomizedExperimentDesign) or design.method.value != expected:
            raise ValueError("method/design conflict")
        if request.execution.request_id != request.request_id:
            raise ValueError("request identity conflict")
    elif isinstance(request, SequentialWorkflowRequest):
        if request.plan.experiment_id not in (None, request.experiment_id):
            raise ValueError("sequential experiment conflict")
    else:
        observational = (
            request.execution.analysis_request
            if isinstance(request, (DidWorkflowRequest, PropensityWorkflowRequest))
            else request.analysis_request
        )
        if observational.request_id != request.request_id:
            raise ValueError("request identity conflict")
        if isinstance(request, IPWWorkflowRequest):
            estimand = observational.identification.estimand
            if estimand is None or request.method != "ipw_" + estimand.estimand_type.value:
                raise ValueError("IPW estimand conflict")
