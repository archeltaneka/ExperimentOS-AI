"""Real randomized service dispatch, without providers or generated statistics."""

import pytest

from packages.experiments.analysis.orchestration.datasets import (
    AnalysisDatasetInput,
    RequestDatasetResolver,
)
from packages.experiments.analysis.orchestration.requests import normalize_analysis_input
from packages.experiments.analysis.orchestration.service import AnalysisService
from tests.analysis_contract_fixtures import source
from tests.orchestration_fixtures import method_payload
from tests.test_bayesian_service import _binding as bayesian_binding
from tests.test_bayesian_service import _table as bayesian_table
from tests.test_cuped_service import _request as cuped_request
from tests.test_cuped_service import _table as cuped_table


@pytest.mark.parametrize("method", ["cuped", "bayesian_ab"])
def test_real_randomized_dispatch_preserves_native_evidence(method):
    payload = method_payload(method)
    if method == "cuped":
        table = cuped_table(
            control_outcomes=(0.0, 3.0, 3.0, 6.0) * 10,
            treatment_outcomes=(4.0, 4.0, 7.0, 10.0) * 10,
            control_covariates=(0.0, 1.0, 2.0, 3.0) * 10,
            treatment_covariates=(0.0, 1.0, 2.0, 3.0) * 10,
        )
        payload["parameters"]["execution"]["analysis_request"] = cuped_request(
            total=80,
            treatment=40,
            control=40,
        ).model_dump(mode="json")
    else:
        table = bayesian_table((1,) * 14 + (0,) * 6, (1,) * 8 + (0,) * 12)
        payload["parameters"]["binding"] = bayesian_binding().model_dump(mode="json")
    dataset = AnalysisDatasetInput(
        reference="sample",
        experiment_id="experiment-a",
        version="1",
        columns=table.columns,
        rows=table.rows,
        provenance=(source(),),
    )
    request = normalize_analysis_input(payload, experiment_id="experiment-a")
    result = AnalysisService(resolver=RequestDatasetResolver((dataset,))).analyze(request)
    assert result.method == method
    assert result.status == "completed", result
    assert result.evidence.assumptions
    assert result.evidence.provenance
    assert '"analysis_request":' not in result.model_dump_json()
    if method == "cuped":
        assert result.evidence.adjusted_result.test_result.confidence_interval
    else:
        assert result.evidence.effect.credible_interval


def test_sequential_empty_history_is_native_insufficiency_not_method_substitution():
    request = normalize_analysis_input(method_payload("sequential"), experiment_id="experiment-a")
    result = AnalysisService(resolver=RequestDatasetResolver(())).analyze(request)
    assert result.method == "sequential"
    assert result.evidence is not None
    assert result.evidence.evidence_type == "sequential"
    assert result.status == "abstained"
    assert result.abstention is not None


def test_sequential_declared_look_keeps_boundary_and_uncertainty():
    from datetime import UTC, datetime

    from packages.experiments.analysis.randomized.sequential.fingerprint import (
        sequential_plan_fingerprint,
    )
    from tests.sequential_fixtures import sequential_plan

    plan = sequential_plan(information_times=(1.0,))
    plan = plan.model_copy(update={"experiment_id": "experiment-a"})
    plan = plan.model_copy(update={"plan_fingerprint": sequential_plan_fingerprint(plan)})
    table = bayesian_table(tuple(range(20, 40)), tuple(range(20)))
    payload = method_payload("sequential")
    payload["parameters"] = {
        "plan": plan.model_dump(mode="json"),
        "looks": [
            {
                "look_index": 1,
                "information_time": 1.0,
                "plan_fingerprint": plan.plan_fingerprint,
                "analysis_request": plan.analysis_request.model_dump(mode="json"),
                "binding": bayesian_binding().model_dump(mode="json"),
                "dataset": {"reference": "sample", "version": "1"},
                "executed_at": datetime(2026, 7, 2, tzinfo=UTC).isoformat(),
            }
        ],
    }
    dataset = AnalysisDatasetInput(
        reference="sample",
        version="1",
        experiment_id="experiment-a",
        columns=table.columns,
        rows=table.rows,
        provenance=(source(),),
    )
    result = AnalysisService(resolver=RequestDatasetResolver((dataset,))).analyze(
        normalize_analysis_input(payload, experiment_id="experiment-a")
    )
    assert result.status == "completed"
    assert result.evidence.looks[0].look_level_analysis.test_result.confidence_interval
    assert result.evidence.looks[0].boundary_crossed
    assert result.evidence.plan_fingerprint == plan.plan_fingerprint


def test_mutated_sequential_plan_never_runs_fixed_horizon(monkeypatch):
    from packages.experiments.analysis.randomized.service import RandomizedAnalysisService

    monkeypatch.setattr(
        RandomizedAnalysisService,
        "analyze",
        lambda *a, **k: pytest.fail("invalid plan ran estimator"),
    )
    payload = method_payload("sequential")
    payload["parameters"]["plan"]["plan_fingerprint"] = "0" * 64
    result = AnalysisService(resolver=RequestDatasetResolver(())).analyze(
        normalize_analysis_input(payload, experiment_id="experiment-a")
    )
    assert result.status == "invalid"
    assert result.evidence is None
    assert result.diagnostics[0].code == "analysis.request_invalid"
