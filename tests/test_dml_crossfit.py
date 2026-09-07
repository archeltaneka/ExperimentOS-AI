"""Direct leakage and prediction-integrity tests for DML cross-fitting."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from packages.experiments.analysis.causal.dml.crossfit import (
    CrossFitError,
    cross_fit_nuisances,
)
from packages.experiments.analysis.causal.dml.folds import FoldObservation, build_fold_plan
from packages.experiments.analysis.causal.dml.models import DMLFoldPlan
from packages.experiments.analysis.causal.dml.protocols import (
    NuisanceAdapterMetadata,
    NuisanceFeatureBatch,
    NuisanceFitReport,
    NuisanceFitStatus,
    NuisanceRole,
)
from packages.experiments.analysis.causal.dml.validation import validate_dml_input
from tests.dml_fixtures import dml_execution, dml_table


@dataclass
class FitPredictionRecord:
    role: NuisanceRole
    seed: int
    training_ids: tuple[object, ...]
    prediction_ids: tuple[object, ...] = ()


@dataclass
class RecordingOutcomeAdapter:
    metadata: NuisanceAdapterMetadata
    records: list[FitPredictionRecord]
    prediction_mode: str = "valid"
    fail_fit: bool = False
    _record: FitPredictionRecord | None = field(default=None, init=False)

    def for_fold(self, seed: int) -> RecordingOutcomeAdapter:
        return RecordingOutcomeAdapter(
            metadata=NuisanceAdapterMetadata.create(
                role=NuisanceRole.OUTCOME,
                adapter_name="recording_outcome",
                adapter_version="1",
                model_family="test_constant",
                hyperparameters={"prediction_mode": self.prediction_mode},
                preprocessing="identity",
                feature_order=("prior_orders",),
                seed=seed,
                minimum_training_rows=2,
                dependency_name="none",
                dependency_version="owned-test-double",
            ),
            records=self.records,
            prediction_mode=self.prediction_mode,
            fail_fit=self.fail_fit,
        )

    def fit(
        self,
        batch: NuisanceFeatureBatch,
        target: tuple[float, ...],
    ) -> NuisanceFitReport:
        del target
        self._record = FitPredictionRecord(
            role=NuisanceRole.OUTCOME,
            seed=self.metadata.seed,
            training_ids=tuple(batch.observation_ids),
        )
        self.records.append(self._record)
        return NuisanceFitReport(
            role=NuisanceRole.OUTCOME,
            status=NuisanceFitStatus.FAILED if self.fail_fit else NuisanceFitStatus.CONVERGED,
            converged=not self.fail_fit,
            training_count=len(batch.rows),
            warning_codes=("intentional.fit_failure",) if self.fail_fit else (),
        )

    def predict(self, batch: NuisanceFeatureBatch) -> tuple[float, ...]:
        assert self._record is not None
        self._record.prediction_ids = tuple(batch.observation_ids)
        if self.prediction_mode == "short":
            return tuple(0.0 for _ in batch.rows[:-1])
        if self.prediction_mode == "nan":
            return (float("nan"), *(0.0 for _ in batch.rows[1:]))
        if self.prediction_mode == "square":
            return tuple(row[0] ** 2 for row in batch.rows)
        return tuple(row[0] for row in batch.rows)


@dataclass
class RecordingTreatmentAdapter:
    metadata: NuisanceAdapterMetadata
    records: list[FitPredictionRecord]
    prediction_mode: str = "valid"
    fail_fit: bool = False
    _record: FitPredictionRecord | None = field(default=None, init=False)

    def for_fold(self, seed: int) -> RecordingTreatmentAdapter:
        return RecordingTreatmentAdapter(
            metadata=NuisanceAdapterMetadata.create(
                role=NuisanceRole.TREATMENT,
                adapter_name="recording_treatment",
                adapter_version="1",
                model_family="test_probability",
                hyperparameters={"prediction_mode": self.prediction_mode},
                preprocessing="identity",
                feature_order=("prior_orders",),
                seed=seed,
                minimum_training_rows=4,
                dependency_name="none",
                dependency_version="owned-test-double",
            ),
            records=self.records,
            prediction_mode=self.prediction_mode,
            fail_fit=self.fail_fit,
        )

    def fit(
        self,
        batch: NuisanceFeatureBatch,
        target: tuple[float, ...],
    ) -> NuisanceFitReport:
        del target
        self._record = FitPredictionRecord(
            role=NuisanceRole.TREATMENT,
            seed=self.metadata.seed,
            training_ids=tuple(batch.observation_ids),
        )
        self.records.append(self._record)
        return NuisanceFitReport(
            role=NuisanceRole.TREATMENT,
            status=NuisanceFitStatus.FAILED if self.fail_fit else NuisanceFitStatus.CONVERGED,
            converged=not self.fail_fit,
            training_count=len(batch.rows),
            classes=(0, 1) if not self.fail_fit else (),
            warning_codes=("intentional.fit_failure",) if self.fail_fit else (),
        )

    def predict_probability(self, batch: NuisanceFeatureBatch) -> tuple[float, ...]:
        assert self._record is not None
        self._record.prediction_ids = tuple(batch.observation_ids)
        if self.prediction_mode == "outside":
            return (1.1, *(0.5 for _ in batch.rows[1:]))
        if self.prediction_mode == "extreme_by_feature":
            return tuple(0.99 if row[0] > 0.0 else 0.01 for row in batch.rows)
        return tuple(0.5 for _ in batch.rows)


class ReusedOutcomeAdapter(RecordingOutcomeAdapter):
    def for_fold(self, seed: int) -> ReusedOutcomeAdapter:
        del seed
        return self


def adapter_metadata(role: NuisanceRole) -> NuisanceAdapterMetadata:
    return NuisanceAdapterMetadata.create(
        role=role,
        adapter_name=f"recording_{role.value}",
        adapter_version="1",
        model_family="test",
        hyperparameters={"prediction_mode": "valid"},
        preprocessing="identity",
        feature_order=("prior_orders",),
        seed=17,
        minimum_training_rows=2 if role is NuisanceRole.OUTCOME else 4,
        dependency_name="none",
        dependency_version="owned-test-double",
    )


def validated_rows_and_plan() -> tuple[object, DMLFoldPlan]:
    execution = dml_execution()
    validated = validate_dml_input(execution, dml_table())
    plan = build_fold_plan(
        tuple(
            FoldObservation(observation_id=row.observation_id, treated=row.treated)
            for row in validated.rows
        ),
        execution.configuration,
    )
    return validated, plan


def test_cross_fitting_never_predicts_a_training_observation_and_scores_once() -> None:
    validated, plan = validated_rows_and_plan()
    outcome_records: list[FitPredictionRecord] = []
    treatment_records: list[FitPredictionRecord] = []
    outcome = RecordingOutcomeAdapter(adapter_metadata(NuisanceRole.OUTCOME), outcome_records)
    treatment = RecordingTreatmentAdapter(
        adapter_metadata(NuisanceRole.TREATMENT), treatment_records
    )

    result = cross_fit_nuisances(
        validated.rows,
        plan,
        feature_names=("prior_orders",),
        outcome_adapter=outcome,
        treatment_adapter=treatment,
    )

    assert len(outcome_records) == plan.fold_count
    assert len(treatment_records) == plan.fold_count
    for record in (*outcome_records, *treatment_records):
        assert set(record.training_ids).isdisjoint(record.prediction_ids)
        assert record.prediction_ids
    expected_ids = tuple(row.observation_id for row in validated.rows)
    assert result.observation_ids == expected_ids
    assert result.outcome_assignment_counts == (1,) * len(expected_ids)
    assert result.treatment_assignment_counts == (1,) * len(expected_ids)
    assert sorted(item for record in outcome_records for item in record.prediction_ids) == sorted(
        expected_ids
    )


def test_cross_fitting_rejects_adapter_instance_reuse_across_folds() -> None:
    validated, plan = validated_rows_and_plan()
    outcome = ReusedOutcomeAdapter(adapter_metadata(NuisanceRole.OUTCOME), [])
    treatment = RecordingTreatmentAdapter(adapter_metadata(NuisanceRole.TREATMENT), [])

    with pytest.raises(CrossFitError, match="fresh") as error:
        cross_fit_nuisances(
            validated.rows,
            plan,
            feature_names=("prior_orders",),
            outcome_adapter=outcome,
            treatment_adapter=treatment,
        )

    assert error.value.code == "dml.nuisance.fresh_instance_required"


def test_cross_fitting_rejects_mutated_fold_plan_with_stale_fingerprint() -> None:
    validated, plan = validated_rows_and_plan()
    first = plan.assignments[0]
    mutated = plan.model_copy(
        update={
            "assignments": (
                first.model_copy(update={"fold_index": (first.fold_index + 1) % plan.fold_count}),
                *plan.assignments[1:],
            )
        }
    )

    with pytest.raises(CrossFitError) as error:
        cross_fit_nuisances(
            validated.rows,
            mutated,
            feature_names=("prior_orders",),
            outcome_adapter=RecordingOutcomeAdapter(adapter_metadata(NuisanceRole.OUTCOME), []),
            treatment_adapter=RecordingTreatmentAdapter(
                adapter_metadata(NuisanceRole.TREATMENT), []
            ),
        )

    assert error.value.code == "dml.fold.integrity_failure"


@pytest.mark.parametrize(
    ("role", "mode", "code"),
    (
        (NuisanceRole.OUTCOME, "short", "dml.nuisance.invalid_prediction_shape"),
        (NuisanceRole.OUTCOME, "nan", "dml.nuisance.nonfinite_prediction"),
        (NuisanceRole.TREATMENT, "outside", "dml.nuisance.invalid_probability"),
    ),
)
def test_cross_fitting_rejects_invalid_predictions(
    role: NuisanceRole,
    mode: str,
    code: str,
) -> None:
    validated, plan = validated_rows_and_plan()
    outcome = RecordingOutcomeAdapter(
        adapter_metadata(NuisanceRole.OUTCOME),
        [],
        prediction_mode=mode if role is NuisanceRole.OUTCOME else "valid",
    )
    treatment = RecordingTreatmentAdapter(
        adapter_metadata(NuisanceRole.TREATMENT),
        [],
        prediction_mode=mode if role is NuisanceRole.TREATMENT else "valid",
    )

    with pytest.raises(CrossFitError) as captured:
        cross_fit_nuisances(
            validated.rows,
            plan,
            feature_names=("prior_orders",),
            outcome_adapter=outcome,
            treatment_adapter=treatment,
        )

    assert captured.value.code == code
    assert captured.value.role is role
    assert captured.value.fold_index == 0


@pytest.mark.parametrize("role", (NuisanceRole.OUTCOME, NuisanceRole.TREATMENT))
def test_cross_fitting_normalizes_failed_fit_with_fold_and_role(role: NuisanceRole) -> None:
    validated, plan = validated_rows_and_plan()
    outcome = RecordingOutcomeAdapter(
        adapter_metadata(NuisanceRole.OUTCOME), [], fail_fit=role is NuisanceRole.OUTCOME
    )
    treatment = RecordingTreatmentAdapter(
        adapter_metadata(NuisanceRole.TREATMENT),
        [],
        fail_fit=role is NuisanceRole.TREATMENT,
    )

    with pytest.raises(CrossFitError) as captured:
        cross_fit_nuisances(
            validated.rows,
            plan,
            feature_names=("prior_orders",),
            outcome_adapter=outcome,
            treatment_adapter=treatment,
        )

    assert captured.value.code == "dml.nuisance.fit_failure"
    assert captured.value.fold_index == 0
    assert captured.value.role is role


def test_cross_fitting_rejects_duplicate_or_missing_fold_assignment() -> None:
    validated, plan = validated_rows_and_plan()
    duplicate = plan.model_copy(update={"assignments": (*plan.assignments, plan.assignments[0])})
    missing = plan.model_copy(update={"assignments": plan.assignments[:-1]})
    outcome = RecordingOutcomeAdapter(adapter_metadata(NuisanceRole.OUTCOME), [])
    treatment = RecordingTreatmentAdapter(adapter_metadata(NuisanceRole.TREATMENT), [])

    with pytest.raises(CrossFitError, match="fingerprint or summaries") as duplicate_error:
        cross_fit_nuisances(
            validated.rows,
            duplicate,
            feature_names=("prior_orders",),
            outcome_adapter=outcome,
            treatment_adapter=treatment,
        )
    with pytest.raises(CrossFitError, match="fingerprint or summaries") as missing_error:
        cross_fit_nuisances(
            validated.rows,
            missing,
            feature_names=("prior_orders",),
            outcome_adapter=outcome,
            treatment_adapter=treatment,
        )
    assert duplicate_error.value.code == "dml.fold.integrity_failure"
    assert missing_error.value.code == "dml.fold.integrity_failure"
