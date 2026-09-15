"""Private fixed scikit-learn nuisance models and audits of actual EconML fits."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import PolynomialFeatures, StandardScaler  # type: ignore[import-untyped]

from ..advanced.models import AdvancedEstimatorConfig, AdvancedFailureCode
from ..dml.models import DMLFoldPlan
from ..dml.protocols import (
    NuisanceAdapterMetadata,
    NuisanceFitReport,
    NuisanceFitStatus,
    NuisancePreprocessingFeature,
    NuisanceRole,
)
from ..dml.results import DMLFoldFitProvenance
from .dependency import AdapterError


@dataclass(frozen=True)
class NuisanceAudit:
    outcome_predictions: tuple[float, ...]
    treatment_predictions: tuple[float, ...]
    fold_fits: tuple[DMLFoldFitProvenance, ...]


def build_nuisances(config: AdvancedEstimatorConfig, seed: int, *, dr: bool) -> tuple[Any, Any]:
    outcome_steps: list[tuple[str, Any]] = []
    if dr:
        outcome_steps.append(
            (
                "interactions",
                PolynomialFeatures(
                    degree=2,
                    interaction_only=True,
                    include_bias=False,
                ),
            )
        )
    outcome_steps.extend(
        [
            ("scale", StandardScaler()),
            ("model", Ridge(alpha=config.ridge_alpha, solver="svd", random_state=seed)),
        ]
    )
    treatment = Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    C=config.logistic_c,
                    l1_ratio=0.0,
                    solver="lbfgs",
                    tol=config.logistic_tolerance,
                    max_iter=config.logistic_max_iterations,
                    random_state=seed,
                    n_jobs=1,
                    warm_start=False,
                ),
            ),
        ]
    )
    return Pipeline(outcome_steps), treatment


def audit_nuisances(
    estimator: Any,
    *,
    features: np.ndarray,
    treatments: np.ndarray,
    splits: tuple[tuple[np.ndarray, np.ndarray], ...],
    plan: DMLFoldPlan,
    feature_names: tuple[str, ...],
    config: AdvancedEstimatorConfig,
    dr: bool,
) -> NuisanceAudit:
    """Replay prediction only on each model's held-out fold, never refit nuisances."""
    outcome_models = estimator.models_regression if dr else estimator.models_y
    treatment_models = estimator.models_propensity if dr else estimator.models_t
    if (
        len(outcome_models) != 1
        or len(treatment_models) != 1
        or len(outcome_models[0]) != len(splits)
        or len(treatment_models[0]) != len(splits)
    ):
        raise AdapterError(
            "NUISANCE_DIAGNOSTICS_UNAVAILABLE", "Actual nuisance fold fits are unavailable."
        )
    outcomes = np.full(len(treatments), np.nan)
    probabilities = np.full(len(treatments), np.nan)
    assignments = np.zeros(len(treatments), dtype=int)
    records: list[DMLFoldFitProvenance] = []
    for index, (train, test) in enumerate(splits):
        outcome_model = outcome_models[0][index]
        treatment_model = treatment_models[0][index]
        values = features[test]
        outcome_values = np.column_stack((values, treatments[test])) if dr else values
        outcomes[test] = checked_vector(outcome_model.predict(outcome_values), len(test))
        predicted = np.asarray(treatment_model.predict_proba(values), dtype=float)
        fitted = treatment_model.named_steps["model"]
        if tuple(fitted.classes_.tolist()) != (0, 1) or predicted.shape != (len(test), 2):
            raise AdapterError(
                AdvancedFailureCode.INVALID_DATA_SHAPE, "Binary probability orientation is invalid."
            )
        probabilities[test] = checked_vector(predicted[:, 1], len(test))
        if int(np.max(fitted.n_iter_)) >= config.logistic_max_iterations:
            raise AdapterError(
                AdvancedFailureCode.ESTIMATOR_FIT_FAILURE, "Treatment nuisance did not converge."
            )
        assignments[test] += 1
        outcome_names = (*feature_names, "treatment::outcome_nuisance") if dr else feature_names
        records.append(
            DMLFoldFitProvenance(
                fold_index=index,
                train_count=len(train),
                score_count=len(test),
                outcome_adapter=_model_metadata(
                    outcome_model, outcome_names, NuisanceRole.OUTCOME, config, plan.random_seed, dr
                ),
                treatment_adapter=_model_metadata(
                    treatment_model,
                    feature_names,
                    NuisanceRole.TREATMENT,
                    config,
                    plan.random_seed,
                    dr,
                ),
                outcome_fit=_fit_report(
                    outcome_model, outcome_names, NuisanceRole.OUTCOME, len(train)
                ),
                treatment_fit=_fit_report(
                    treatment_model, feature_names, NuisanceRole.TREATMENT, len(train)
                ),
            )
        )
    if not np.all(assignments == 1) or np.any(probabilities < 0) or np.any(probabilities > 1):
        raise AdapterError(
            AdvancedFailureCode.INVALID_DATA_SHAPE,
            "Out-of-fold predictions are not aligned probabilities.",
        )
    return NuisanceAudit(
        outcome_predictions=tuple(float(x) for x in outcomes),
        treatment_predictions=tuple(float(x) for x in probabilities),
        fold_fits=tuple(records),
    )


def checked_vector(value: Any, length: int) -> np.ndarray:
    values = np.asarray(value, dtype=float)
    if values.shape != (length,) or not np.all(np.isfinite(values)):
        raise AdapterError(
            AdvancedFailureCode.INVALID_DATA_SHAPE,
            "Nuisance predictions must be finite aligned vectors.",
        )
    return values


def _expanded_names(model: Any, names: tuple[str, ...]) -> tuple[str, ...]:
    if "interactions" in model.named_steps:
        return tuple(str(x) for x in model.named_steps["interactions"].get_feature_names_out(names))
    return names


def _model_metadata(
    model: Any,
    names: tuple[str, ...],
    role: NuisanceRole,
    config: AdvancedEstimatorConfig,
    seed: int,
    dr: bool,
) -> NuisanceAdapterMetadata:
    parameters: dict[str, str | float | int | bool] = (
        {
            "alpha": config.ridge_alpha,
            "solver": "svd",
            "fit_intercept": True,
            "random_state": seed,
            "interaction_degree": 2 if dr else 1,
        }
        if role is NuisanceRole.OUTCOME
        else {
            "C": config.logistic_c,
            "solver": "lbfgs",
            "l1_ratio": 0.0,
            "fit_intercept": True,
            "tolerance": config.logistic_tolerance,
            "maximum_iterations": config.logistic_max_iterations,
            "random_state": seed,
            "n_jobs": 1,
        }
    )
    return NuisanceAdapterMetadata.create(
        role=role,
        adapter_name=f"advanced_scaled_{role.value}",
        adapter_version="1",
        model_family="ridge_conditional_outcome"
        if dr and role is NuisanceRole.OUTCOME
        else "ridge_regression"
        if role is NuisanceRole.OUTCOME
        else "regularized_logistic_regression",
        hyperparameters=parameters,
        preprocessing="fold_local_population_standardization",
        feature_order=_expanded_names(model, names),
        seed=seed,
        minimum_training_rows=4,
        dependency_name="scikit-learn",
        dependency_version=metadata.version("scikit-learn"),
    )


def _fit_report(
    model: Any, names: tuple[str, ...], role: NuisanceRole, count: int
) -> NuisanceFitReport:
    scaler = model.named_steps["scale"]
    fitted = model.named_steps["model"]
    return NuisanceFitReport(
        role=role,
        status=NuisanceFitStatus.CONVERGED,
        converged=True,
        training_count=count,
        iteration_count=int(np.max(fitted.n_iter_)) if role is NuisanceRole.TREATMENT else None,
        classes=(0, 1) if role is NuisanceRole.TREATMENT else (),
        preprocessing=tuple(
            NuisancePreprocessingFeature(
                feature_name=name,
                mean=float(mean),
                scale=float(scale),
                zero_variance=bool(variance == 0),
            )
            for name, mean, scale, variance in zip(
                _expanded_names(model, names),
                scaler.mean_,
                scaler.scale_,
                scaler.var_,
                strict=True,
            )
        ),
    )
