"""Public evidence is typed, private-request-free, and stable through serialization."""

import pytest
from pydantic import ValidationError

from packages.experiments.analysis.orchestration.datasets import RequestDatasetResolver
from packages.experiments.analysis.orchestration.results import AnalysisResultEnvelope
from packages.experiments.analysis.orchestration.service import AnalysisService
from tests.test_analysis_service import fixed_case


def test_envelope_roundtrip_preserves_uncertainty_without_native_request():
    request, dataset = fixed_case()
    result = AnalysisService(resolver=RequestDatasetResolver((dataset,))).analyze(request)
    restored = AnalysisResultEnvelope.model_validate_json(result.model_dump_json())
    assert restored == result
    assert restored.evidence.test_result.confidence_interval.confidence_level == 0.95
    assert "analysis_request" not in restored.evidence.model_dump()
    assert "rows" not in restored.model_dump_json()
    assert "treatment-0" not in restored.model_dump_json()


def test_envelope_rejects_raw_estimator_object():
    request, dataset = fixed_case()
    result = AnalysisService(resolver=RequestDatasetResolver((dataset,))).analyze(request)
    payload = result.model_dump()
    payload["evidence"]["estimator"] = object()
    with pytest.raises(ValidationError):
        AnalysisResultEnvelope.model_validate(payload)


def test_authoritative_result_is_not_replaced_by_caller_mutation():
    request, dataset = fixed_case()
    service = AnalysisService(resolver=RequestDatasetResolver((dataset,)))
    result = service.analyze(request)
    object.__setattr__(result.evidence.point_effect.absolute_effect, "value", 999.0)
    authoritative = service.authoritative_result(result.analysis_id)
    assert authoritative.evidence.point_effect.absolute_effect.value == 10.0


def test_evidence_fingerprint_excludes_runtime_identity():
    request, dataset = fixed_case()
    service = AnalysisService(resolver=RequestDatasetResolver((dataset,)))
    a, b = service.analyze(request), service.analyze(request)
    assert a.analysis_id != b.analysis_id
    assert a.evidence_fingerprint == b.evidence_fingerprint
