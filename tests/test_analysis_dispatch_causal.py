"""Native causal analyzers behind explicit orchestration."""

from datetime import datetime

import pytest

from packages.experiments.analysis.orchestration.datasets import (
    AnalysisDatasetInput,
    RequestDatasetResolver,
)
from packages.experiments.analysis.orchestration.requests import normalize_analysis_input
from packages.experiments.analysis.orchestration.service import AnalysisService
from tests.analysis_contract_fixtures import source
from tests.did_fixtures import did_table, positive_effect_rows
from tests.dml_fixtures import dml_execution, dml_table
from tests.hte_fixtures import effect_rows, hte_table
from tests.orchestration_fixtures import method_payload
from tests.propensity_fixtures import good_overlap_rows, propensity_table
from tests.test_dml_service import _linear_rows


def causal_case(method):
    payload = method_payload(method)
    if method == "did":
        table = did_table(positive_effect_rows())
    elif method == "dml":
        table = dml_table(_linear_rows())
        payload["parameters"]["configuration"] = dml_execution(
            fold_count=4, seed=812
        ).configuration.model_dump(mode="json")
    elif method == "hte":
        table = hte_table(effect_rows())
        payload["parameters"]["configuration"]["dml"]["fold_count"] = 4
    else:
        records = tuple(
            {**row, "outcome": int(i % 3 == 0)} for i, row in enumerate(good_overlap_rows())
        )
        table = propensity_table(records)
    dataset = AnalysisDatasetInput(
        reference="sample",
        experiment_id="experiment-a",
        version="1",
        columns=table.columns,
        rows=tuple(
            tuple(v.isoformat() if isinstance(v, datetime) else v for v in row)
            for row in table.rows
        ),
        provenance=(source(),),
    )
    return normalize_analysis_input(payload, experiment_id="experiment-a"), dataset


@pytest.mark.parametrize(
    "method", ["did", "propensity_diagnostics", "ipw_ate", "ipw_att", "dml", "hte"]
)
def test_causal_dispatch_preserves_owned_evidence_without_rows(method):
    request, dataset = causal_case(method)
    result = AnalysisService(resolver=RequestDatasetResolver((dataset,))).analyze(request)
    assert result.method == method
    assert result.status == "completed", result
    assert result.evidence.assumptions
    assert result.evidence.provenance
    text = result.model_dump_json()
    assert '"observation_id":' not in text
    assert '"row_index":' not in text
    assert '"observation_key":' not in text
    assert '"unit_id":"c-00"' not in text
    for forbidden in ('"scores":', '"assignments":', '"analysis_request":', '"execution_request":'):
        assert forbidden not in text
    if method == "did":
        assert result.evidence.cell_means.did_estimate == pytest.approx(3)


def test_post_treatment_adjustment_stops_before_dml(monkeypatch):
    from packages.experiments.analysis.causal.dml.service import DoubleMachineLearningEstimator
    from packages.experiments.analysis.causal.variables import MeasurementTiming
    from tests.dml_fixtures import dml_request

    monkeypatch.setattr(
        DoubleMachineLearningEstimator,
        "analyze",
        lambda *a, **k: pytest.fail("invalid identification estimated"),
    )
    payload = method_payload("dml")
    declaration = dml_request(adjustment_timing=MeasurementTiming.POST_TREATMENT)
    payload["parameters"]["analysis_request"] = declaration.model_dump(mode="json")
    result = AnalysisService(resolver=RequestDatasetResolver(())).analyze(
        normalize_analysis_input(payload, experiment_id="experiment-a")
    )
    assert result.status == "invalid"
    assert result.evidence.evidence_type == "identification"
    assert result.abstention is not None


def test_poor_overlap_stops_ipw_before_outcome_estimator(monkeypatch):
    from packages.experiments.analysis.causal.ipw.service import IPWTreatmentEffectEstimator
    from tests.propensity_fixtures import separation_rows

    monkeypatch.setattr(
        IPWTreatmentEffectEstimator,
        "analyze",
        lambda *a, **k: pytest.fail("failed propensity reached IPW"),
    )
    request, dataset = causal_case("ipw_ate")
    table = propensity_table(tuple({**r, "outcome": 0} for r in separation_rows()))
    dataset = dataset.model_copy(update={"columns": table.columns, "rows": table.rows})
    result = AnalysisService(resolver=RequestDatasetResolver((dataset,))).analyze(request)
    assert result.status == "abstained"
    assert result.evidence.evidence_type == "propensity"
    assert result.abstention is not None
