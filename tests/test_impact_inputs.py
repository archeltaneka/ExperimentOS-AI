from importlib import import_module

import pytest
from pydantic import ValidationError


def contracts():
    module = import_module("packages.experiments.analysis.impact.inputs")
    return module


def test_ranges_require_order_and_do_not_invent_a_central_value():
    m = contracts()
    assert m.InputRange(lower=1.0, upper=3.0).central is None
    assert m.InputRange.fixed(2).central == 2
    with pytest.raises(ValidationError):
        m.InputRange(lower=3.0, upper=1.0)
    with pytest.raises(ValidationError):
        m.InputRange(lower=1.0, upper=3.0, central=4.0)


def test_evidence_requires_explicit_repository_field_and_nonempty_provenance():
    m = contracts()
    record = {"source_type": "report", "source_id": "report-1"}
    with pytest.raises(ValidationError):
        m.InputEvidence(origin="repository_evidence", status="measured", provenance=(record,))
    with pytest.raises(ValidationError):
        m.InputEvidence(origin="user_supplied", status="assumed", provenance=())
    evidence = m.InputEvidence(
        origin="repository_evidence",
        status="measured",
        provenance=(record,),
        reference="report-1:eligible_users",
    )
    assert evidence.reference == "report-1:eligible_users"


@pytest.mark.parametrize("lower,upper", [(-0.1, 0.5), (0.5, 1.1)])
def test_exposure_rejects_out_of_range_rates(lower, upper):
    m = contracts()
    with pytest.raises(ValidationError):
        m.ExposureInput(
            value=m.InputRange(lower=lower, upper=upper),
            meaning="rollout",
            evidence={
                "origin": "user_supplied",
                "status": "assumed",
                "provenance": [{"source_type": "user_supplied", "source_id": "u"}],
            },
            horizon={"count": 1, "unit": "months"},
        )


def test_repository_reference_must_identify_a_supplied_record_field():
    m = contracts()
    with pytest.raises(ValidationError):
        m.InputEvidence(
            origin="repository_evidence",
            status="measured",
            provenance=({"source_type": "report", "source_id": "report-1"},),
            reference="a-different-document:population",
        )
