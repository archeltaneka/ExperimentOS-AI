"""Hand-calculable owned evidence and explicit operational declarations."""

from datetime import UTC, datetime

from packages.experiments.analysis.base import ContractModel
from packages.experiments.analysis.randomized.binary import analyze_binary_two_proportion_z
from packages.experiments.analysis.randomized.models import RandomizedAnalysisResult
from tests.analysis_contract_fixtures import randomized_request, source


def evidence(status="assumed"):
    return {
        "origin": "user_supplied",
        "status": status,
        "provenance": [{"source_type": "user_supplied", "source_id": "business-owner-v1"}],
    }


def binary_source():
    request = randomized_request().model_dump(mode="json")
    request["outcome"]["metric"]["metric_type"] = "binary"
    request["estimand"] = {"kind": "difference_in_proportions"}
    request["sample_counts"] = {"total": 2000, "treatment": 1000, "control": 1000}
    request["study_design"]["experiment_period"] = {
        "start": "2026-07-01T00:00:00Z",
        "end": "2026-08-01T00:00:00Z",
    }
    from packages.experiments.analysis.requests import AnalysisRequest

    req = AnalysisRequest.model_validate(request)
    result = analyze_binary_two_proportion_z(
        request_id="hand-fixture",
        metric=req.outcome.metric,
        estimand=req.estimand,
        treatment_arm_id=req.treatment.treatment_id,
        treatment_values=(1,) * 120 + (0,) * 880,
        control_arm_id=req.control.control_id,
        control_values=(1,) * 100 + (0,) * 900,
        provenance=(source(),),
    )
    payload = result.model_dump(mode="json")
    payload["analysis_request"] = request
    payload["point_effect"]["absolute_effect"]["value"] = 0.02
    payload["test_result"]["confidence_interval"]["lower"] = 0.01
    payload["test_result"]["confidence_interval"]["upper"] = 0.03
    return RandomizedAnalysisResult.model_validate(payload)


def fixed(value):
    return {"lower": value, "upper": value, "central": value}


def request_payload():
    source_result = binary_source()
    req = source_result.analysis_request
    assert req is not None
    basis = {"count": 1, "unit": "months"}
    count_unit = {
        "dimension": "count",
        "value_scale": "raw",
        "symbol": "events",
        "scale_to_base_unit": 1.0,
    }
    return {
        "request_id": "scenario-hand",
        "output": "net",
        "population": {
            "value": fixed(100000),
            "entity": "users",
            "definition": req.population.model_dump(mode="json"),
            "target_kind": "full",
            "basis": "per_period",
            "time_basis": basis,
            "exposure_basis": "eligible",
            "evidence": evidence(),
        },
        "exposure": {
            "value": fixed(0.5),
            "meaning": "rollout",
            "horizon": basis,
            "evidence": evidence(),
        },
        "horizon": {
            "period": {
                "start": datetime(2026, 7, 1, tzinfo=UTC),
                "end": datetime(2026, 8, 1, tzinfo=UTC),
            },
            "basis": basis,
            "evidence": evidence(),
        },
        "binding": {
            "analysis_unit": req.unit_of_analysis.model_dump(mode="json"),
            "entity": "users",
            "metric_id": req.outcome.metric.metric_id,
            "outcome_unit": req.outcome.metric.unit.model_dump(mode="json"),
            "event": "conversions",
            "evidence": evidence(),
        },
        "conversion": {
            "value": fixed(10),
            "currency": "USD",
            "metric_id": req.outcome.metric.metric_id,
            "per_unit": count_unit,
            "event": "conversions",
            "orientation": "added",
            "meaning": "contribution",
            "horizon": basis,
            "evidence": evidence(),
        },
        "costs": {
            "complete": True,
            "evidence": evidence(),
            "items": [
                {
                    "cost_id": "setup",
                    "value": fixed(1000),
                    "currency": "USD",
                    "basis": "implementation",
                    "horizon": basis,
                    "evidence": evidence(),
                }
            ],
        },
    }


def changed(model: ContractModel, **changes):
    payload = model.model_dump()
    payload.update(changes)
    return type(model).model_validate(payload)


def continuous_source(*, money=False, count=False):
    from packages.experiments.analysis.randomized.continuous import analyze_continuous_welch
    from packages.experiments.analysis.requests import AnalysisRequest

    request = binary_source().analysis_request.model_dump(mode="json")
    unit = (
        {
            "dimension": "currency",
            "value_scale": "raw",
            "symbol": "USD",
            "scale_to_base_unit": 1.0,
            "currency_code": "USD",
        }
        if money
        else {
            "dimension": "count" if count else "duration",
            "value_scale": "raw",
            "symbol": "events" if count else "ms",
            "scale_to_base_unit": 1.0,
        }
    )
    request["outcome"]["metric"].update(metric_type="continuous", unit=unit)
    request["outcome"]["direction"] = "increase" if money else "decrease"
    request["estimand"] = {"kind": "difference_in_means"}
    request["sample_counts"] = {"total": 40, "treatment": 20, "control": 20}
    req = AnalysisRequest.model_validate(request)
    result = analyze_continuous_welch(
        request_id="continuous-hand",
        metric=req.outcome.metric,
        estimand=req.estimand,
        treatment_arm_id=req.treatment.treatment_id,
        treatment_values=tuple(float(n) for n in range(20)),
        control_arm_id=req.control.control_id,
        control_values=tuple(float(n + 20) for n in range(20)),
        provenance=(source(),),
    )
    payload = result.model_dump(mode="json")
    payload["analysis_request"] = request
    payload["test_result"]["confidence_interval"].update(lower=-30, upper=-10)
    return RandomizedAnalysisResult.model_validate(payload)
