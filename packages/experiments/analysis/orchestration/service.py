"""Request-scoped orchestration of explicitly selected validated analysis."""

from datetime import UTC, datetime
from uuid import uuid4

from packages.observability.base import BaseObservabilityProvider
from packages.observability.noop import NoOpObservabilityProvider

from ..randomized.sequential.models import SequentialAnalysisHistory
from ..results import AbstentionReason
from .datasets import AnalysisDataResolver, DatasetResolutionError
from .registry import AnalysisMethodRegistry, default_registry
from .requests import (
    WORKFLOW_REQUEST_ADAPTER,
    AnalysisInput,
    AnalysisRoutingRefusal,
    WorkflowAnalysisRequest,
    refusal_diagnostic,
    refusal_reason,
    routing_refusal,
    validate_selection,
)
from .results import (
    AnalysisArtifactReference,
    AnalysisFailure,
    AnalysisResultEnvelope,
    OwnedAnalysisResult,
    native_status,
    project_evidence,
)


class AnalysisService:
    def __init__(
        self,
        *,
        resolver: AnalysisDataResolver,
        registry: AnalysisMethodRegistry | None = None,
        observability_provider: BaseObservabilityProvider | None = None,
    ) -> None:
        self.resolver = resolver
        self.registry = registry if registry is not None else default_registry()
        self.provider = observability_provider or NoOpObservabilityProvider()
        self._results: dict[str, AnalysisResultEnvelope] = {}
        self._native: dict[str, OwnedAnalysisResult] = {}
        self._requests: dict[str, WorkflowAnalysisRequest] = {}

    def analyze(self, request: AnalysisInput) -> AnalysisResultEnvelope:
        analysis_id = str(uuid4())
        request = self._revalidate(request)
        envelope = AnalysisResultEnvelope(
            analysis_id=analysis_id,
            request_id=request.request_id,
            method=request.method,
            capability="unknown",
            status="abstained",
            created_at=datetime.now(UTC),
            artifacts=(
                AnalysisArtifactReference(
                    artifact_id=analysis_id + ":request",
                    kind="request",
                    version="1",
                ),
            ),
        )
        if isinstance(request, AnalysisRoutingRefusal):
            return self._save(
                envelope.model_copy(
                    update={
                        "status": request.status,
                        "diagnostics": request.diagnostics,
                        "abstention": request.abstention,
                    }
                )
            )
        registration = self.registry.resolve(request.method)
        if registration is None or not registration.workflow_eligible:
            return self._refuse(envelope, "analysis.method_unsupported")
        envelope = envelope.model_copy(update={"capability": registration.capability})
        try:
            native = registration.handler(request, self.resolver, self.provider)
            evidence = project_evidence(native)
            status = native_status(native)
        except DatasetResolutionError as exc:
            return self._refuse(envelope, exc.code)
        except Exception as exc:
            return self._save(
                envelope.model_copy(
                    update={
                        "status": "failed",
                        "failure": AnalysisFailure(
                            code="analysis.estimator_failure", error_type=type(exc).__name__
                        ),
                    }
                )
            )
        self._native[analysis_id] = native.model_copy(deep=True)
        self._requests[analysis_id] = request.model_copy(deep=True)
        reason = None if isinstance(native, SequentialAnalysisHistory) else native.abstention_reason
        abstention = (
            refusal_reason(reason)
            if isinstance(reason, str)
            else AbstentionReason(
                code=reason.code,
                message=reason.message,
                missing_or_invalid_information=getattr(reason, "missing_or_invalid_information", ())
                or (reason.code,),
            )
            if reason is not None
            else None
        )
        if abstention is None and status in {"abstained", "invalid", "unavailable"}:
            abstention = refusal_reason("analysis." + status)
        updated = AnalysisResultEnvelope.model_validate(
            {
                **envelope.model_dump(),
                "evidence": evidence,
                "evidence_fingerprint": "",
                "status": status,
                "abstention": abstention,
            }
        )
        artifact = AnalysisArtifactReference(
            artifact_id=analysis_id,
            kind="analysis",
            version=registration.implementation_version,
            provenance=evidence.provenance,
            evidence_fingerprint=updated.evidence_fingerprint,
        )
        return self._save(updated.model_copy(update={"artifacts": (*updated.artifacts, artifact)}))

    def authoritative_result(self, analysis_id: str) -> AnalysisResultEnvelope:
        return self._results[analysis_id].model_copy(deep=True)

    def _save(self, result: AnalysisResultEnvelope) -> AnalysisResultEnvelope:
        validated = AnalysisResultEnvelope.model_validate(result.model_dump(warnings=False))
        self._results[result.analysis_id] = validated.model_copy(deep=True)
        return validated.model_copy(deep=True)

    def _refuse(self, result: AnalysisResultEnvelope, code: str) -> AnalysisResultEnvelope:
        return self._save(
            result.model_copy(
                update={
                    "status": "abstained",
                    "diagnostics": (refusal_diagnostic(code),),
                    "abstention": refusal_reason(code),
                }
            )
        )

    @staticmethod
    def _revalidate(request: AnalysisInput) -> AnalysisInput:
        if isinstance(request, AnalysisRoutingRefusal):
            return AnalysisRoutingRefusal.model_validate(request.model_dump(warnings=False))
        try:
            validated = WORKFLOW_REQUEST_ADAPTER.validate_python(request.model_dump(warnings=False))
            validate_selection(validated)
            if type(validated) is not type(request):
                raise ValueError("request type/method conflict")
            return validated
        except (ValueError, TypeError):
            return routing_refusal(
                "analysis.request_invalid",
                method=request.method,
                experiment_id=request.experiment_id,
                request_id=request.request_id,
            )
