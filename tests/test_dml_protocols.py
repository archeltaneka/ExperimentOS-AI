"""ExperimentOS-owned deterministic nuisance model protocols."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from packages.experiments.analysis.causal.dml.protocols import (
    NuisanceAdapterMetadata,
    NuisanceFeatureBatch,
    NuisanceFitReport,
    NuisanceFitStatus,
    NuisanceRole,
    OutcomeNuisanceModel,
    TreatmentNuisanceModel,
    validate_nuisance_adapter,
)


@dataclass
class DeterministicOutcomeAdapter:
    metadata: NuisanceAdapterMetadata

    def for_fold(self, seed: int) -> DeterministicOutcomeAdapter:
        return DeterministicOutcomeAdapter(
            self.metadata.model_copy(update={"seed": seed})
        )

    def fit(
        self,
        batch: NuisanceFeatureBatch,
        target: tuple[float, ...],
    ) -> NuisanceFitReport:
        return NuisanceFitReport(
            role=NuisanceRole.OUTCOME,
            status=NuisanceFitStatus.CONVERGED,
            converged=True,
            training_count=len(batch.rows),
            iteration_count=1,
        )

    def predict(self, batch: NuisanceFeatureBatch) -> tuple[float, ...]:
        return tuple(row[0] for row in batch.rows)


def metadata(*, role: NuisanceRole = NuisanceRole.OUTCOME) -> NuisanceAdapterMetadata:
    return NuisanceAdapterMetadata.create(
        role=role,
        adapter_name="deterministic_test_adapter",
        adapter_version="1",
        model_family="test_linear",
        hyperparameters={"alpha": 1.0},
        preprocessing="identity",
        feature_order=("x",),
        seed=17,
        minimum_training_rows=2,
        dependency_name="none",
        dependency_version="owned-test-double",
    )


def test_owned_outcome_protocol_accepts_deterministic_adapter() -> None:
    adapter = DeterministicOutcomeAdapter(metadata())

    validated = validate_nuisance_adapter(adapter, role=NuisanceRole.OUTCOME)

    assert isinstance(validated, OutcomeNuisanceModel)
    assert validated.metadata.deterministic is True
    assert len(validated.metadata.configuration_fingerprint_sha256) == 64


def test_owned_protocol_rejects_missing_prediction_capability() -> None:
    class MissingPredict:
        def __init__(self) -> None:
            self.metadata = metadata()

        def for_fold(self, seed: int) -> MissingPredict:
            del seed
            return self

        def fit(
            self,
            batch: NuisanceFeatureBatch,
            target: tuple[float, ...],
        ) -> NuisanceFitReport:
            del batch, target
            raise AssertionError("fit must not run during protocol validation")

    with pytest.raises(TypeError, match="outcome nuisance protocol"):
        validate_nuisance_adapter(MissingPredict(), role=NuisanceRole.OUTCOME)


def test_owned_protocol_rejects_role_mismatch_and_mutated_fingerprint() -> None:
    treatment_metadata = metadata(role=NuisanceRole.TREATMENT)
    adapter = DeterministicOutcomeAdapter(treatment_metadata)

    with pytest.raises(ValueError, match="metadata role"):
        validate_nuisance_adapter(adapter, role=NuisanceRole.OUTCOME)

    mutated = metadata().model_copy(update={"configuration_fingerprint_sha256": "0" * 64})
    with pytest.raises(ValueError, match="configuration fingerprint"):
        validate_nuisance_adapter(
            DeterministicOutcomeAdapter(mutated),
            role=NuisanceRole.OUTCOME,
        )


def test_treatment_protocol_requires_probability_prediction() -> None:
    adapter = DeterministicOutcomeAdapter(metadata(role=NuisanceRole.TREATMENT))

    with pytest.raises(TypeError, match="treatment nuisance protocol"):
        validate_nuisance_adapter(adapter, role=NuisanceRole.TREATMENT)

    assert not isinstance(adapter, TreatmentNuisanceModel)


def test_feature_batch_requires_unique_ids_and_rectangular_finite_rows() -> None:
    with pytest.raises(ValueError, match="observation IDs"):
        NuisanceFeatureBatch(
            observation_ids=("u-1", "u-1"),
            feature_names=("x",),
            rows=((1.0,), (2.0,)),
        )
    with pytest.raises(ValueError, match="feature count"):
        NuisanceFeatureBatch(
            observation_ids=("u-1",),
            feature_names=("x",),
            rows=((1.0, 2.0),),
        )
