"""Adapter telemetry contains only aggregate operational metadata."""

from __future__ import annotations

import pytest

from packages.evals.statistical.telemetry import telemetry_privacy_violations
from tests.causal_identification_fixtures import provenance
from tests.dml_fixtures import dml_execution, dml_table
from tests.econml_fixtures import dr_execution, linear_rows, requires_econml
from tests.hte_fixtures import effect_rows, hte_table
from tests.test_hte_observability import RecordingProvider


@requires_econml
@pytest.mark.parametrize("hte", [False, True])
def test_successful_adapter_telemetry_is_safe(hte):
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter, EconMLHTEAdapter

    provider = RecordingProvider()
    adapter = (
        EconMLHTEAdapter(observability_provider=provider)
        if hte
        else EconMLDMLAdapter(constant_effect_assumption=True, observability_provider=provider)
    )
    result = adapter.analyze(
        dr_execution(fold_count=4) if hte else dml_execution(fold_count=4, seed=812),
        hte_table(effect_rows()) if hte else dml_table(linear_rows()),
        provenance=provenance(),
    )
    assert result.status.value == "completed"
    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.metadata["adapter"] == "econml"
    assert record.metadata["dependency_available"] is True
    assert record.metadata["status"] == "completed"
    assert telemetry_privacy_violations((record,)) == ()
    for forbidden in ("prior_orders", "account_id", "unit-000", "ID-000", "SG-000", "predictions"):
        assert forbidden not in repr(record)


def test_observability_failure_cannot_change_an_abstention():
    from packages.experiments.analysis.causal.econml import EconMLDMLAdapter

    class BrokenProvider(RecordingProvider):
        def start_root_span(self, *args, **kwargs):
            raise RuntimeError("telemetry unavailable")

    result = EconMLDMLAdapter(
        constant_effect_assumption=True, observability_provider=BrokenProvider()
    ).analyze(dml_execution(), dml_table(linear_rows()), provenance=provenance())
    assert result.status.value in ("completed", "abstained")
