"""Business scenarios require authoritative eligible evidence and explicit inputs."""

import pytest

from packages.experiments.analysis.orchestration.datasets import (
    AnalysisDatasetInput,
    RequestDatasetResolver,
)
from packages.experiments.analysis.orchestration.requests import normalize_analysis_input
from packages.experiments.analysis.orchestration.service import AnalysisService
from tests.analysis_contract_fixtures import source
from tests.impact_fixtures import binary_source, request_payload
from tests.test_randomized_service import _binding, _execution_request, _table


def business_case():
    native_request = binary_source().analysis_request
    native_request = native_request.model_copy(
        update={"unit_of_analysis": native_request.study_design.randomization_unit}
    )
    execution = _execution_request(native_request)
    table = _table((1,) * 120 + (0,) * 880, (1,) * 100 + (0,) * 900)
    payload = {
        "method": "randomized_fixed_horizon",
        "request_id": execution.request_id,
        "parameters": {
            "execution": execution.model_dump(mode="json"),
            "binding": _binding().model_dump(mode="json"),
            "dataset": {"reference": "sample", "version": "1"},
        },
        "business": request_payload(),
    }
    dataset = AnalysisDatasetInput(
        reference="sample",
        version="1",
        experiment_id="experiment-a",
        columns=table.columns,
        rows=table.rows,
        provenance=(source(),),
    )
    payload["business"]["binding"]["analysis_unit"] = native_request.unit_of_analysis.model_dump(
        mode="json"
    )
    return payload, dataset


def test_business_preserves_exact_statistical_evidence_and_operational_inputs():
    payload, dataset = business_case()
    service = AnalysisService(resolver=RequestDatasetResolver((dataset,)))
    result = service.analyze(normalize_analysis_input(payload, experiment_id="experiment-a"))
    updated = service.analyze_business(result.analysis_id)
    assert updated.evidence == result.evidence
    assert updated.evidence_fingerprint == result.evidence_fingerprint
    impact = updated.business_impact
    assert impact.status == "inconclusive"
    assert impact.inputs.population.value.central == 100000
    assert impact.gross_incremental_outcome.central == pytest.approx(1000)
    assert impact.net_monetary_impact.central == pytest.approx(9000)
    assert impact.gross_monetary_impact.statistical is not None
    assert impact.derivations
    assert impact.provenance


@pytest.mark.parametrize("invalid", ["upstream", "missing", "provenance"])
def test_business_prerequisite_failure_never_calls_calculator(monkeypatch, invalid):
    from packages.experiments.analysis.impact.service import BusinessImpactService

    monkeypatch.setattr(
        BusinessImpactService,
        "analyze",
        lambda *a, **k: pytest.fail("blocked business calculation"),
    )
    payload, dataset = business_case()
    if invalid == "missing":
        payload.pop("business")
    elif invalid == "provenance":
        payload["business"]["population"]["evidence"]["provenance"] = []
    service = AnalysisService(
        resolver=RequestDatasetResolver(() if invalid == "upstream" else (dataset,))
    )
    result = service.analyze(normalize_analysis_input(payload, experiment_id="experiment-a"))
    updated = service.analyze_business(result.analysis_id)
    assert updated.business_impact.status == "abstained"
    assert updated.business_impact.abstention is not None
    assert updated.business_impact.net_monetary_impact is None
    assert updated.evidence == result.evidence
