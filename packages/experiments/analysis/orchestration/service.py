"""Request-scoped orchestration of explicitly selected validated analysis."""

from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from packages.observability.base import BaseObservabilityProvider
from packages.observability.noop import NoOpObservabilityProvider

from ..randomized.sequential.models import SequentialAnalysisHistory
from ..results import AbstentionReason
from .business import analyze_business
from .datasets import AnalysisDataResolver, DatasetResolutionError
from .observability import analysis_metadata, safe_analysis_provider
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
    AnalysisIntegrityFinding,
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
        self.provider = safe_analysis_provider(
            observability_provider or NoOpObservabilityProvider()
        )
        self._results: dict[str, AnalysisResultEnvelope] = {}
        self._native: dict[str, OwnedAnalysisResult] = {}
        self._requests: dict[str, WorkflowAnalysisRequest] = {}

    def analyze(self, request: AnalysisInput) -> AnalysisResultEnvelope:
        started = perf_counter()
        span = self.provider.start_span("analysis")
        with span.activate():
            result = self._analyze(request)
            span.add_metadata(analysis_metadata(result))
            span.finish(
                outputs={"status": result.status, "duration_ms": (perf_counter() - started) * 1000}
            )
            return result

    def _analyze(self, request: AnalysisInput) -> AnalysisResultEnvelope:
        analysis_id = str(uuid4())
        validation = self.provider.start_span("validation")
        with validation.activate():
            request = self._revalidate(request)
            validation.finish(
                outputs={
                    "status": "invalid"
                    if isinstance(request, AnalysisRoutingRefusal)
                    else "validated"
                }
            )
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
            estimator = self.provider.start_span(
                "estimator", metadata={"method": registration.method_id}
            )
            with estimator.activate():
                native = registration.handler(request, self.resolver, self.provider)
                estimator.finish(outputs={"status": native_status(native)})
            evidence = project_evidence(native)
            status = native_status(native)
        except DatasetResolutionError as exc:
            estimator.finish(outputs={"status": "abstained"})
            return self._refuse(envelope, exc.code)
        except Exception as exc:
            estimator.finish(outputs={"status": "failed", "error_type": type(exc).__name__})
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

    def record_integrity(self, analysis_id: str, *, node: str, code: str) -> AnalysisResultEnvelope:
        result = self.authoritative_result(analysis_id)
        finding = AnalysisIntegrityFinding(code=code, node=node)
        findings = result.integrity_findings
        if finding not in findings:
            findings = (*findings, finding)
        return self._save(result.model_copy(update={"integrity_findings": findings}))

    def analyze_business(self, analysis_id: str) -> AnalysisResultEnvelope:
        span = self.provider.start_span("analysis.business_impact")
        with span.activate():
            result = self._analyze_business(analysis_id)
            span.add_metadata(analysis_metadata(result))
            span.finish(
                outputs={
                    "status": result.business_impact.status if result.business_impact else "skipped"
                }
            )
            return result

    def _analyze_business(self, analysis_id: str) -> AnalysisResultEnvelope:
        envelope = self.authoritative_result(analysis_id)
        request = self._requests.get(analysis_id)
        impact = analyze_business(
            self._native.get(analysis_id), request.business if request else None, envelope.status
        )
        artifact = AnalysisArtifactReference(
            artifact_id=analysis_id + ":business",
            kind="business_impact",
            version="1",
            provenance=impact.provenance,
            evidence_fingerprint=envelope.evidence_fingerprint,
        )
        return self._save(
            envelope.model_copy(
                update={
                    "business_impact": impact,
                    "artifacts": tuple(a for a in envelope.artifacts if a.kind != "business_impact")
                    + (artifact,),
                }
            )
        )

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
