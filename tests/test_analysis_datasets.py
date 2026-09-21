"""Request-scoped snapshots must never resolve another experiment's data."""

import warnings

import pytest
from pydantic import ValidationError

from packages.experiments.analysis.orchestration.datasets import (
    AnalysisDatasetInput,
    DatasetResolutionFailure,
    RequestDatasetResolver,
    ResolvedAnalysisDataset,
)
from tests.analysis_contract_fixtures import source


def dataset_payload():
    return {
        "reference": "sample",
        "experiment_id": "experiment-a",
        "version": "1",
        "columns": ["unit", "outcome"],
        "rows": [["one", 1.0], ["two", None]],
        "provenance": [source().model_dump(mode="json")],
    }


def test_missing_reference_is_a_typed_refusal():
    result = RequestDatasetResolver(()).resolve("absent", "experiment-a")
    assert isinstance(result, DatasetResolutionFailure)
    assert result.code == "analysis.dataset_missing"


def test_snapshot_does_not_retain_mutable_input_rows():
    payload = dataset_payload()
    dataset = AnalysisDatasetInput.model_validate(payload)
    payload["rows"][0][1] = 999
    resolved = RequestDatasetResolver((dataset,)).resolve("sample", "experiment-a")
    assert isinstance(resolved, ResolvedAnalysisDataset)
    assert resolved.table.rows == (("one", 1.0), ("two", None))
    assert resolved.version == "1"
    assert resolved.provenance == (source(),)


def test_other_experiment_cannot_resolve_dataset():
    dataset = AnalysisDatasetInput.model_validate(dataset_payload())
    result = RequestDatasetResolver((dataset,)).resolve("sample", "experiment-b")
    assert isinstance(result, DatasetResolutionFailure)
    assert result.code == "analysis.dataset_ownership"


def test_duplicate_reference_never_selects_one_version():
    first = AnalysisDatasetInput.model_validate(dataset_payload())
    second = first.model_copy(update={"version": "2"})
    result = RequestDatasetResolver((first, second)).resolve("sample", "experiment-a")
    assert isinstance(result, DatasetResolutionFailure)
    assert result.code == "analysis.dataset_ambiguous"


def test_same_reference_is_independent_between_requests():
    first = AnalysisDatasetInput.model_validate(dataset_payload())
    second = first.model_copy(update={"rows": (("other", 3.0),)})
    a = RequestDatasetResolver((first,)).resolve("sample", "experiment-a")
    b = RequestDatasetResolver((second,)).resolve("sample", "experiment-a")
    assert isinstance(a, ResolvedAnalysisDataset)
    assert isinstance(b, ResolvedAnalysisDataset)
    assert a.table.rows[0][1] == 1.0
    assert b.table.rows[0][1] == 3.0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rows", [["one"]]),
        ("rows", [["one", {"private": "record"}]]),
        ("rows", [["one", [1, 2]]]),
        ("rows", [["one", float("nan")]]),
        ("rows", [["one", float("inf")]]),
        ("columns", ["unit", "unit"]),
        ("columns", []),
        ("provenance", []),
    ],
)
def test_invalid_snapshot_is_rejected(field, value):
    payload = dataset_payload()
    payload[field] = value
    with pytest.raises(ValidationError):
        AnalysisDatasetInput.model_validate(payload)


def test_resolver_revalidates_copied_models():
    dataset = AnalysisDatasetInput.model_validate(dataset_payload())
    forged = dataset.model_copy(update={"rows": (("one", {"private": "raw"}),)})
    with warnings.catch_warnings(record=True) as emitted:
        result = RequestDatasetResolver((forged,)).resolve("sample", "experiment-a")
    assert not emitted, "rejected raw values must not leak through serializer warnings"
    assert isinstance(result, DatasetResolutionFailure)
    assert result.code == "analysis.dataset_invalid"
