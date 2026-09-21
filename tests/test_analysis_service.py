"""Orchestration preserves native inference and refuses incomplete datasets."""

from dataclasses import replace

import pytest

from packages.experiments.analysis.metrics import MetricType
from packages.experiments.analysis.orchestration.datasets import (
    AnalysisDatasetInput,
    RequestDatasetResolver,
)
from packages.experiments.analysis.orchestration.registry import (
    AnalysisMethodRegistry,
    default_registry,
)
from packages.experiments.analysis.orchestration.requests import normalize_analysis_input
from packages.experiments.analysis.orchestration.service import AnalysisService
from packages.experiments.analysis.randomized.service import RandomizedAnalysisService
from tests.analysis_contract_fixtures import source
from tests.test_analysis_orchestration_requests import fixed_payload
from tests.test_randomized_service import _binding, _execution_request, _request, _table


def fixed_case():
    execution = _execution_request(_request(MetricType.CONTINUOUS))
    table = _table(tuple(range(11, 31)), tuple(range(1, 21)))
    payload = fixed_payload()
    payload["request_id"] = execution.request_id
    payload["parameters"]["execution"] = execution.model_dump(mode="json")
    payload["parameters"]["binding"] = _binding().model_dump(mode="json")
    request = normalize_analysis_input(payload, experiment_id="experiment-a")
    dataset = AnalysisDatasetInput(
        reference="sample",
        experiment_id="experiment-a",
        version="1",
        columns=table.columns,
        rows=table.rows,
        provenance=(source(),),
    )
    return request, dataset


def test_service_preserves_direct_native_inference_exactly():
    request, dataset = fixed_case()
    service = AnalysisService(resolver=RequestDatasetResolver((dataset,)))
    result = service.analyze(request)
    native = RandomizedAnalysisService().analyze(
        request.execution,
        _table(tuple(range(11, 31)), tuple(range(1, 21))),
        request.binding,
        provenance=(source(),),
    )
    assert result.method == "randomized_fixed_horizon"
    assert result.status == "completed"
    assert result.evidence.point_effect.absolute_effect.value == 10.0
    assert result.evidence.test_result == native.test_result
    assert result.evidence.assumptions == native.assumptions
    assert result.evidence.diagnostics == native.diagnostics
    assert result.evidence.provenance == native.provenance
    assert result.evidence.estimand == native.estimand
    assert result.artifacts


def test_missing_dataset_abstains_before_dispatch():
    request, _ = fixed_case()
    result = AnalysisService(resolver=RequestDatasetResolver(())).analyze(request)
    assert result.status == "abstained"
    assert result.abstention.code == "analysis.dataset_missing"
    assert result.evidence is None


def test_wrong_dataset_version_does_not_analyze_new_data():
    request, dataset = fixed_case()
    dataset = dataset.model_copy(update={"version": "2"})
    result = AnalysisService(resolver=RequestDatasetResolver((dataset,))).analyze(request)
    assert result.status == "abstained"
    assert result.abstention.code == "analysis.dataset_version"


def test_insufficient_sample_retains_native_abstention():
    request, dataset = fixed_case()
    dataset = dataset.model_copy(update={"rows": ()})
    result = AnalysisService(resolver=RequestDatasetResolver((dataset,))).analyze(request)
    assert result.status in {"invalid", "abstained"}
    assert result.evidence.point_effect is None
    assert result.evidence.abstention_reason is not None
    assert result.evidence.diagnostics


def test_unexpected_estimator_exception_is_safe_failed_result():
    def exploding(*args):
        raise RuntimeError("private-row-sentinel")

    request, dataset = fixed_case()
    registration = default_registry().resolve(request.method)
    service = AnalysisService(
        resolver=RequestDatasetResolver((dataset,)),
        registry=AnalysisMethodRegistry((replace(registration, handler=exploding),)),
    )
    result = service.analyze(request)
    assert result.status == "failed"
    assert result.failure.code == "analysis.estimator_failure"
    assert "private-row-sentinel" not in result.model_dump_json()


def test_model_copy_cannot_bypass_method_validation(monkeypatch):
    request, dataset = fixed_case()
    forged = request.model_copy(update={"method": "did"})
    result = AnalysisService(resolver=RequestDatasetResolver((dataset,))).analyze(forged)
    assert result.status == "invalid"
    assert result.evidence is None


def test_invalid_eligibility_does_not_call_numerical_engine(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid input reached numerical calculation")

    monkeypatch.setattr(
        "packages.experiments.analysis.randomized.service.analyze_continuous_welch", forbidden
    )
    request, dataset = fixed_case()
    dataset = dataset.model_copy(update={"columns": ("wrong", "arm", "outcome")})
    result = AnalysisService(resolver=RequestDatasetResolver((dataset,))).analyze(request)
    assert result.status in {"invalid", "abstained"}
    assert result.evidence.point_effect is None


def test_native_abstention_is_exposed_on_envelope():
    request, dataset = fixed_case()
    dataset = dataset.model_copy(update={"rows": ()})
    result = AnalysisService(resolver=RequestDatasetResolver((dataset,))).analyze(request)
    assert result.abstention is not None
    assert result.abstention.code == result.evidence.abstention_reason.code


def test_service_is_available_from_owned_analysis_boundary():
    from packages.experiments.analysis import AnalysisService as PublicService

    request, dataset = fixed_case()
    assert (
        PublicService(resolver=RequestDatasetResolver((dataset,))).analyze(request).status
        == "completed"
    )
