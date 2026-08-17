"""Privacy and provider-failure isolation for Bayesian estimator telemetry."""

from __future__ import annotations

from packages.experiments.analysis import MetricType
from packages.experiments.analysis.randomized.bayesian import (
    BayesianAnalysisExecutionRequest,
    BayesianAnalysisService,
    BayesianComputationStatus,
    BernoulliBinomialLikelihood,
    BetaPrior,
)
from packages.experiments.analysis.validation import AnalysisTable
from packages.observability.base import BaseObservabilityProvider, BufferedSpan, BufferedSpanRecord
from packages.observability.models import ProviderSettings
from tests.analysis_contract_fixtures import source
from tests.test_bayesian_service import _binding, _request, _table


class RecordingProvider(BaseObservabilityProvider):
    def __init__(self) -> None:
        super().__init__(ProviderSettings(enabled=True, sampling_rate=1.0))
        self.records: list[BufferedSpanRecord] = []

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        self.records.append(record)


class FailingStartProvider(RecordingProvider):
    def start_root_span(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        run_type: str = "chain",
        inputs: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
        tags: tuple[str, ...] | list[str] = (),
    ) -> BufferedSpan:
        raise RuntimeError("provider unavailable")


def _execution() -> BayesianAnalysisExecutionRequest:
    prior = BetaPrior(
        alpha=123.456,
        beta=78.9,
        provenance=(source(),),
        label="private prior label",
    )
    return BayesianAnalysisExecutionRequest(
        request_id="private-high-cardinality-bayesian-request",
        analysis_request=_request(MetricType.BINARY),
        treatment_prior=prior,
        control_prior=prior,
        likelihood=BernoulliBinomialLikelihood(),
    )


def _private_table() -> AnalysisTable:
    table = _table((1,) * 14 + (0,) * 6, (1,) * 8 + (0,) * 12)
    return AnalysisTable(
        columns=table.columns + ("raw_covariate", "credential"),
        rows=tuple(row + (98765.4321, "sk-private-bayesian") for row in table.rows),
    )


def _render(record: BufferedSpanRecord) -> str:
    return repr(
        {
            "name": record.name,
            "inputs": record.inputs,
            "metadata": record.metadata,
            "outputs": record.outputs,
            "children": [_render(child) for child in record.children],
        }
    )


def test_success_emits_only_low_cardinality_bayesian_metadata() -> None:
    provider = RecordingProvider()
    result = BayesianAnalysisService(observability_provider=provider).analyze(
        _execution(),
        _private_table(),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is BayesianComputationStatus.COMPLETED
    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.name == "bayesian_randomized_analysis"
    assert record.inputs == {"total_row_count": 40}
    assert record.metadata["inference_family"] == "bayesian"
    assert record.metadata["likelihood_family"] == "bernoulli_binomial"
    assert record.metadata["outcome_type"] == "binary"
    assert record.metadata["computation_mode"] == "deterministic_quadrature"
    assert record.metadata["status"] == "completed"
    assert record.metadata["prior_validity"] == "valid"
    assert record.metadata["rope_requested"] is False
    assert record.metadata["probability_of_superiority_available"] is True
    assert isinstance(record.metadata["duration_ms"], float)
    assert record.outputs == {"status": "completed", "analysis_completed": True}

    rendered = _render(record)
    for private in (
        "123.456",
        "78.9",
        "private prior label",
        "98765.4321",
        "sk-private-bayesian",
        "private-high-cardinality-bayesian-request",
        "raw_covariate",
        "credential",
        "rows",
    ):
        assert private not in rendered


def test_observability_start_failure_does_not_change_result() -> None:
    expected = BayesianAnalysisService().analyze(
        _execution(),
        _private_table(),
        _binding(),
        provenance=(source(),),
    )
    provider = FailingStartProvider()
    actual = BayesianAnalysisService(observability_provider=provider).analyze(
        _execution(),
        _private_table(),
        _binding(),
        provenance=(source(),),
    )

    assert actual.model_dump_json() == expected.model_dump_json()
    assert provider.failure_count == 1


def test_invalid_prior_payload_emits_invalid_state_without_prior_values() -> None:
    provider = RecordingProvider()
    payload = _execution().model_dump(mode="python")
    assert isinstance(payload["treatment_prior"], dict)
    payload["treatment_prior"]["alpha"] = -99999.125

    result = BayesianAnalysisService(observability_provider=provider).analyze_payload(
        payload,
        _private_table(),
        _binding(),
        provenance=(source(),),
    )

    assert result.status is BayesianComputationStatus.INVALID
    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.metadata["status"] == "invalid"
    assert record.metadata["prior_validity"] == "invalid"
    assert record.metadata["probability_of_superiority_available"] is False
    assert "-99999.125" not in _render(record)
