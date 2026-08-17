from __future__ import annotations

from collections.abc import Mapping

import pytest

from packages.evals.statistical.dataset import (
    DEFAULT_STATISTICAL_DATASET_PATH,
    load_statistical_reference_cases,
)
from packages.evals.statistical.fixtures import run_statistical_fixture
from packages.observability.base import BaseObservabilityProvider, BufferedSpanRecord
from packages.observability.models import ProviderSettings


class RecordingProvider(BaseObservabilityProvider):
    def __init__(self) -> None:
        super().__init__(ProviderSettings(enabled=True, sampling_rate=1.0))
        self.records: list[BufferedSpanRecord] = []

    def _emit_root(self, record: BufferedSpanRecord) -> None:
        self.records.append(record)


@pytest.mark.parametrize(
    ("case_id", "family", "method", "abstained"),
    (
        ("cuped-positive-variance-reduction", "frequentist", "cuped", False),
        ("cuped-constant-covariate-abstention", "frequentist", "cuped", True),
        ("sequential-no-stop-sequence", "frequentist", "sequential", False),
        ("sequential-invalid-fingerprint-invalid", "frequentist", "sequential", True),
        ("bayesian-binary-conjugate", "bayesian", "bayesian", False),
        ("bayesian-invalid-prior", "bayesian", "bayesian", True),
    ),
)
def test_randomized_inference_telemetry_has_common_private_schema(
    case_id: str,
    family: str,
    method: str,
    abstained: bool,
) -> None:
    dataset = load_statistical_reference_cases(DEFAULT_STATISTICAL_DATASET_PATH)
    case = next(item for item in dataset.cases if item.case_id == case_id)
    provider = RecordingProvider()

    run_statistical_fixture(case, observability_provider=provider)

    assert len(provider.records) == 1
    record = provider.records[0]
    assert record.metadata["inference_family"] == family
    assert record.metadata["method"] == method
    assert record.metadata["status"]
    assert record.metadata["estimand"] in {
        "intention_to_treat",
        "difference_in_means",
        "difference_in_proportions",
    }
    assert isinstance(record.metadata["diagnostic_codes"], tuple)
    assert isinstance(record.metadata["duration_ms"], float)
    assert record.metadata["abstention_state"] is abstained

    forbidden = {
        "raw_outcomes",
        "raw_covariates",
        "adjusted_outcomes",
        "posterior_draws",
        "sequential_rows",
        "treatment_assignments",
        "credentials",
        "treatment_prior",
        "control_prior",
    }
    assert forbidden.isdisjoint(_nested_keys(_record_payload(record)))


def _record_payload(record: BufferedSpanRecord) -> dict[str, object]:
    return {
        "inputs": record.inputs,
        "metadata": record.metadata,
        "outputs": record.outputs,
        "children": [_record_payload(child) for child in record.children],
    }


def _nested_keys(value: object) -> set[str]:
    if isinstance(value, Mapping):
        return {str(key) for key in value} | set().union(
            *(_nested_keys(item) for item in value.values()),
            set(),
        )
    if isinstance(value, (list, tuple)):
        return set().union(*(_nested_keys(item) for item in value), set())
    return set()
