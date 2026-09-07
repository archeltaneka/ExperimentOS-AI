"""Leakage-free deterministic cross-fitting for DML nuisance models."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from .folds import FoldObservation, canonical_observation_key, validate_fold_plan_integrity
from .models import DMLFoldPlan
from .protocols import (
    NuisanceAdapterMetadata,
    NuisanceFeatureBatch,
    NuisanceFitReport,
    NuisanceFitStatus,
    NuisanceRole,
    OutcomeNuisanceModel,
    TreatmentNuisanceModel,
    validate_nuisance_adapter,
)
from .validation import ValidatedDMLRow


class CrossFitError(ValueError):
    """Owned normalized cross-fitting failure with fold and role context."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        fold_index: int | None = None,
        role: NuisanceRole | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.fold_index = fold_index
        self.role = role


@dataclass(frozen=True, slots=True)
class CrossFitFoldRecord:
    """Owned aggregate fit evidence for one cross-fitting fold."""

    fold_index: int
    train_count: int
    score_count: int
    outcome_metadata: NuisanceAdapterMetadata
    treatment_metadata: NuisanceAdapterMetadata
    outcome_fit: NuisanceFitReport
    treatment_fit: NuisanceFitReport


@dataclass(frozen=True, slots=True)
class CrossFittedNuisanceResult:
    """Internal canonical out-of-fold predictions and assignment evidence."""

    observation_ids: tuple[object, ...]
    outcome_predictions: tuple[float, ...]
    treatment_predictions: tuple[float, ...]
    outcome_assignment_counts: tuple[int, ...]
    treatment_assignment_counts: tuple[int, ...]
    fold_records: tuple[CrossFitFoldRecord, ...]


def cross_fit_nuisances(
    rows: tuple[ValidatedDMLRow, ...],
    fold_plan: DMLFoldPlan,
    *,
    feature_names: tuple[str, ...],
    outcome_adapter: OutcomeNuisanceModel,
    treatment_adapter: TreatmentNuisanceModel,
) -> CrossFittedNuisanceResult:
    """Fit on each fold complement and predict only its disjoint score fold."""
    validated_outcome = validate_nuisance_adapter(outcome_adapter, role=NuisanceRole.OUTCOME)
    validated_treatment = validate_nuisance_adapter(
        treatment_adapter,
        role=NuisanceRole.TREATMENT,
    )
    try:
        validate_fold_plan_integrity(
            tuple(
                FoldObservation(observation_id=row.observation_id, treated=row.treated)
                for row in rows
            ),
            fold_plan,
        )
    except ValueError as error:
        raise CrossFitError(
            "dml.fold.integrity_failure",
            "The fold plan fingerprint or summaries do not match its assignments.",
        ) from error
    if validated_outcome.metadata.feature_order != feature_names:
        raise CrossFitError(
            "dml.nuisance.feature_order_mismatch",
            "Outcome nuisance feature order does not match the validated adjustment set.",
            role=NuisanceRole.OUTCOME,
        )
    if validated_treatment.metadata.feature_order != feature_names:
        raise CrossFitError(
            "dml.nuisance.feature_order_mismatch",
            "Treatment nuisance feature order does not match the validated adjustment set.",
            role=NuisanceRole.TREATMENT,
        )

    row_keys = tuple(canonical_observation_key(row.observation_id) for row in rows)
    if len(row_keys) != len(set(row_keys)):
        raise CrossFitError(
            "dml.crossfit.duplicate_row",
            "Canonical DML rows must have unique observation IDs.",
        )
    index_by_key = {key: index for index, key in enumerate(row_keys)}
    assignment_counts = [0] * len(rows)
    fold_by_index: list[int | None] = [None] * len(rows)
    for assignment in fold_plan.assignments:
        key = canonical_observation_key(assignment.observation_id)
        index = index_by_key.get(key)
        if index is None or assignment.fold_index >= fold_plan.fold_count:
            raise CrossFitError(
                "dml.crossfit.invalid_fold_assignment",
                "Every fold assignment must reference one retained observation and valid fold.",
            )
        assignment_counts[index] += 1
        fold_by_index[index] = assignment.fold_index
    if any(count != 1 for count in assignment_counts):
        raise CrossFitError(
            "dml.crossfit.assignment_count",
            "Every retained observation requires exactly one score fold.",
        )

    outcome_predictions: list[float | None] = [None] * len(rows)
    treatment_predictions: list[float | None] = [None] * len(rows)
    outcome_counts = [0] * len(rows)
    treatment_counts = [0] * len(rows)
    fold_records: list[CrossFitFoldRecord] = []
    adapter_instances: list[object] = [validated_outcome, validated_treatment]
    for fold_index in range(fold_plan.fold_count):
        score_indexes = tuple(
            index
            for index, assigned_fold in enumerate(fold_by_index)
            if assigned_fold == fold_index
        )
        train_indexes = tuple(index for index in range(len(rows)) if index not in score_indexes)
        train_keys = {row_keys[index] for index in train_indexes}
        score_keys = {row_keys[index] for index in score_indexes}
        if train_keys & score_keys:
            raise CrossFitError(
                "dml.crossfit.leakage_detected",
                "Training and scoring observations must be disjoint.",
                fold_index=fold_index,
            )
        if train_keys | score_keys != set(row_keys):
            raise CrossFitError(
                "dml.crossfit.incomplete_fold",
                "Training and scoring observations must exactly partition retained rows.",
                fold_index=fold_index,
            )
        train_batch = _batch(rows, train_indexes, feature_names)
        score_batch = _batch(rows, score_indexes, feature_names)
        outcome_seed = _fold_seed(
            fold_plan,
            fold_index,
            NuisanceRole.OUTCOME,
            validated_outcome.metadata,
        )
        treatment_seed = _fold_seed(
            fold_plan,
            fold_index,
            NuisanceRole.TREATMENT,
            validated_treatment.metadata,
        )
        outcome_model = _for_fold(
            validated_outcome,
            seed=outcome_seed,
            fold_index=fold_index,
            role=NuisanceRole.OUTCOME,
        )
        treatment_model = _for_fold(
            validated_treatment,
            seed=treatment_seed,
            fold_index=fold_index,
            role=NuisanceRole.TREATMENT,
        )
        outcome_model = validate_nuisance_adapter(outcome_model, role=NuisanceRole.OUTCOME)
        treatment_model = validate_nuisance_adapter(
            treatment_model,
            role=NuisanceRole.TREATMENT,
        )
        _require_fresh_adapter(
            outcome_model,
            seen=adapter_instances,
            seed=outcome_seed,
            feature_names=feature_names,
            fold_index=fold_index,
            role=NuisanceRole.OUTCOME,
        )
        _require_fresh_adapter(
            treatment_model,
            seen=adapter_instances,
            seed=treatment_seed,
            feature_names=feature_names,
            fold_index=fold_index,
            role=NuisanceRole.TREATMENT,
        )
        _require_training_size(outcome_model.metadata, len(train_indexes), fold_index)
        _require_training_size(treatment_model.metadata, len(train_indexes), fold_index)

        outcome_fit = _fit(
            outcome_model,
            train_batch,
            tuple(rows[index].outcome for index in train_indexes),
            fold_index=fold_index,
            role=NuisanceRole.OUTCOME,
        )
        treatment_fit = _fit(
            treatment_model,
            train_batch,
            tuple(float(rows[index].treated) for index in train_indexes),
            fold_index=fold_index,
            role=NuisanceRole.TREATMENT,
        )
        outcome_values = _predict(
            outcome_model,
            score_batch,
            fold_index=fold_index,
            role=NuisanceRole.OUTCOME,
        )
        treatment_values = _predict(
            treatment_model,
            score_batch,
            fold_index=fold_index,
            role=NuisanceRole.TREATMENT,
        )
        _store_predictions(
            outcome_predictions,
            outcome_counts,
            score_indexes,
            outcome_values,
            fold_index=fold_index,
            role=NuisanceRole.OUTCOME,
        )
        _store_predictions(
            treatment_predictions,
            treatment_counts,
            score_indexes,
            treatment_values,
            fold_index=fold_index,
            role=NuisanceRole.TREATMENT,
        )
        fold_records.append(
            CrossFitFoldRecord(
                fold_index=fold_index,
                train_count=len(train_indexes),
                score_count=len(score_indexes),
                outcome_metadata=outcome_model.metadata,
                treatment_metadata=treatment_model.metadata,
                outcome_fit=outcome_fit,
                treatment_fit=treatment_fit,
            )
        )

    if any(count != 1 for count in (*outcome_counts, *treatment_counts)):
        raise CrossFitError(
            "dml.crossfit.prediction_assignment_count",
            "Every retained observation requires exactly one out-of-fold nuisance prediction.",
        )
    checked_outcome = _require_complete_predictions(outcome_predictions)
    checked_treatment = _require_complete_predictions(treatment_predictions)
    return CrossFittedNuisanceResult(
        observation_ids=tuple(row.observation_id for row in rows),
        outcome_predictions=checked_outcome,
        treatment_predictions=checked_treatment,
        outcome_assignment_counts=tuple(outcome_counts),
        treatment_assignment_counts=tuple(treatment_counts),
        fold_records=tuple(fold_records),
    )


def _batch(
    rows: tuple[ValidatedDMLRow, ...],
    indexes: tuple[int, ...],
    feature_names: tuple[str, ...],
) -> NuisanceFeatureBatch:
    return NuisanceFeatureBatch(
        observation_ids=tuple(rows[index].observation_id for index in indexes),
        feature_names=feature_names,
        rows=tuple(rows[index].features for index in indexes),
    )


def _fit(
    adapter: OutcomeNuisanceModel | TreatmentNuisanceModel,
    batch: NuisanceFeatureBatch,
    target: tuple[float, ...],
    *,
    fold_index: int,
    role: NuisanceRole,
) -> NuisanceFitReport:
    try:
        report = adapter.fit(batch, target)
    except Exception as error:
        raise CrossFitError(
            "dml.nuisance.fit_failure",
            "A nuisance adapter raised while fitting.",
            fold_index=fold_index,
            role=role,
        ) from error
    if (
        not isinstance(report, NuisanceFitReport)
        or report.role is not role
        or report.status is not NuisanceFitStatus.CONVERGED
        or not report.converged
        or report.training_count != len(batch.rows)
        or (role is NuisanceRole.TREATMENT and report.classes != (0, 1))
    ):
        raise CrossFitError(
            "dml.nuisance.fit_failure",
            "A nuisance adapter did not return a converged owned fit report.",
            fold_index=fold_index,
            role=role,
        )
    return report


def _for_fold(
    adapter: OutcomeNuisanceModel | TreatmentNuisanceModel,
    *,
    seed: int,
    fold_index: int,
    role: NuisanceRole,
) -> OutcomeNuisanceModel | TreatmentNuisanceModel:
    try:
        return adapter.for_fold(seed)
    except Exception as error:
        raise CrossFitError(
            "dml.nuisance.fold_adapter_failure",
            "A nuisance adapter failed to create its fold-local instance.",
            fold_index=fold_index,
            role=role,
        ) from error


def _require_fresh_adapter(
    adapter: OutcomeNuisanceModel | TreatmentNuisanceModel,
    *,
    seen: list[object],
    seed: int,
    feature_names: tuple[str, ...],
    fold_index: int,
    role: NuisanceRole,
) -> None:
    if any(adapter is item for item in seen):
        raise CrossFitError(
            "dml.nuisance.fresh_instance_required",
            "Every nuisance role and fold requires a fresh adapter instance.",
            fold_index=fold_index,
            role=role,
        )
    seen.append(adapter)
    if adapter.metadata.seed != seed:
        raise CrossFitError(
            "dml.nuisance.fold_seed_mismatch",
            "A fold-local nuisance adapter must record its derived seed.",
            fold_index=fold_index,
            role=role,
        )
    if adapter.metadata.feature_order != feature_names:
        raise CrossFitError(
            "dml.nuisance.feature_order_mismatch",
            "A fold-local nuisance adapter changed the validated feature order.",
            fold_index=fold_index,
            role=role,
        )


def _predict(
    adapter: OutcomeNuisanceModel | TreatmentNuisanceModel,
    batch: NuisanceFeatureBatch,
    *,
    fold_index: int,
    role: NuisanceRole,
) -> tuple[float, ...]:
    try:
        values = (
            adapter.predict(batch)
            if role is NuisanceRole.OUTCOME and isinstance(adapter, OutcomeNuisanceModel)
            else adapter.predict_probability(batch)  # type: ignore[union-attr]
        )
    except Exception as error:
        raise CrossFitError(
            "dml.nuisance.prediction_failure",
            "A nuisance adapter raised while predicting its scoring fold.",
            fold_index=fold_index,
            role=role,
        ) from error
    if len(values) != len(batch.rows):
        raise CrossFitError(
            "dml.nuisance.invalid_prediction_shape",
            "Nuisance prediction length must equal scoring-fold length.",
            fold_index=fold_index,
            role=role,
        )
    if any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
        raise CrossFitError(
            "dml.nuisance.nonfinite_prediction",
            "Nuisance predictions must be finite real values.",
            fold_index=fold_index,
            role=role,
        )
    checked = tuple(float(value) for value in values)
    if role is NuisanceRole.TREATMENT and any(value < 0.0 or value > 1.0 for value in checked):
        raise CrossFitError(
            "dml.nuisance.invalid_probability",
            "Treatment nuisance predictions must be probabilities in [0, 1].",
            fold_index=fold_index,
            role=role,
        )
    return checked


def _store_predictions(
    destination: list[float | None],
    counts: list[int],
    indexes: tuple[int, ...],
    values: tuple[float, ...],
    *,
    fold_index: int,
    role: NuisanceRole,
) -> None:
    for index, value in zip(indexes, values, strict=True):
        if destination[index] is not None:
            raise CrossFitError(
                "dml.crossfit.duplicate_prediction",
                "A nuisance prediction slot cannot be overwritten by another fold.",
                fold_index=fold_index,
                role=role,
            )
        destination[index] = value
        counts[index] += 1


def _require_complete_predictions(values: list[float | None]) -> tuple[float, ...]:
    checked: list[float] = []
    for value in values:
        if value is None:
            raise CrossFitError(
                "dml.crossfit.missing_prediction",
                "Cross-fitting left at least one retained observation without predictions.",
            )
        checked.append(value)
    return tuple(checked)


def _require_training_size(
    metadata: NuisanceAdapterMetadata,
    training_count: int,
    fold_index: int,
) -> None:
    if training_count < metadata.minimum_training_rows:
        raise CrossFitError(
            "dml.fold.adapter_minimum_training_rows",
            "A training fold is smaller than the nuisance adapter minimum.",
            fold_index=fold_index,
            role=metadata.role,
        )


def _fold_seed(
    plan: DMLFoldPlan,
    fold_index: int,
    role: NuisanceRole,
    metadata: NuisanceAdapterMetadata,
) -> int:
    payload = {
        "adapter_fingerprint": metadata.configuration_fingerprint_sha256,
        "fold_index": fold_index,
        "plan_fingerprint": plan.fingerprint_sha256,
        "role": role.value,
        "seed": plan.random_seed,
        "version": "dml-nuisance-fold-seed-v1",
    }
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(serialized.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


__all__ = [
    "CrossFitError",
    "CrossFitFoldRecord",
    "CrossFittedNuisanceResult",
    "cross_fit_nuisances",
]
