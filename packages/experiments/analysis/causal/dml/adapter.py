"""Private deterministic scikit-learn nuisance adapters for DML."""

from __future__ import annotations

import warnings

import numpy as np
import sklearn  # type: ignore[import-untyped]
from sklearn.exceptions import ConvergenceWarning  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression, Ridge  # type: ignore[import-untyped]

from .protocols import (
    NuisanceAdapterMetadata,
    NuisanceFeatureBatch,
    NuisanceFitReport,
    NuisanceFitStatus,
    NuisancePreprocessingFeature,
    NuisanceRole,
)


class SklearnRidgeOutcomeAdapter:
    """Deterministic Ridge outcome nuisance with fold-local standardization."""

    def __init__(
        self,
        *,
        feature_order: tuple[str, ...],
        seed: int,
        alpha: float = 1.0,
    ) -> None:
        self._feature_order = feature_order
        self._seed = seed
        self._alpha = alpha
        self._mean: np.ndarray | None = None
        self._scale: np.ndarray | None = None
        self._estimator: Ridge | None = None
        self._metadata = NuisanceAdapterMetadata.create(
            role=NuisanceRole.OUTCOME,
            adapter_name="sklearn_ridge_outcome",
            adapter_version="1",
            model_family="ridge_regression",
            hyperparameters={"alpha": alpha, "fit_intercept": True, "solver": "svd"},
            preprocessing="fold_local_population_standardization",
            feature_order=feature_order,
            seed=seed,
            minimum_training_rows=2,
            dependency_name="scikit-learn",
            dependency_version=sklearn.__version__,
        )

    @property
    def metadata(self) -> NuisanceAdapterMetadata:
        return self._metadata

    def for_fold(self, seed: int) -> SklearnRidgeOutcomeAdapter:
        return SklearnRidgeOutcomeAdapter(
            feature_order=self._feature_order,
            seed=seed,
            alpha=self._alpha,
        )

    def fit(
        self,
        batch: NuisanceFeatureBatch,
        target: tuple[float, ...],
    ) -> NuisanceFitReport:
        try:
            matrix, values = self._training_arrays(batch, target)
            scaled, preprocessing = self._fit_preprocessing(matrix)
            estimator = Ridge(alpha=self._alpha, fit_intercept=True, solver="svd")
            estimator.fit(scaled, values)
            self._estimator = estimator
            return NuisanceFitReport(
                role=NuisanceRole.OUTCOME,
                status=NuisanceFitStatus.CONVERGED,
                converged=True,
                training_count=len(target),
                preprocessing=preprocessing,
            )
        except Exception:
            self._estimator = None
            return _failed_report(NuisanceRole.OUTCOME, len(target), "nuisance.fit_failure")

    def predict(self, batch: NuisanceFeatureBatch) -> tuple[float, ...]:
        if self._estimator is None or self._mean is None or self._scale is None:
            raise RuntimeError("outcome nuisance adapter has no converged fit")
        matrix = self._prediction_matrix(batch)
        predictions = self._estimator.predict((matrix - self._mean) / self._scale)
        return tuple(float(value) for value in predictions.tolist())

    def _training_arrays(
        self,
        batch: NuisanceFeatureBatch,
        target: tuple[float, ...],
    ) -> tuple[np.ndarray, np.ndarray]:
        if batch.feature_names != self._feature_order or len(target) != len(batch.rows):
            raise ValueError("outcome nuisance training data is not aligned")
        matrix = np.asarray(batch.rows, dtype=np.float64)
        values = np.asarray(target, dtype=np.float64)
        if not np.all(np.isfinite(values)):
            raise ValueError("outcome nuisance targets must be finite")
        return matrix, values

    def _prediction_matrix(self, batch: NuisanceFeatureBatch) -> np.ndarray:
        if batch.feature_names != self._feature_order:
            raise ValueError("outcome nuisance feature order changed")
        return np.asarray(batch.rows, dtype=np.float64)

    def _fit_preprocessing(
        self,
        matrix: np.ndarray,
    ) -> tuple[np.ndarray, tuple[NuisancePreprocessingFeature, ...]]:
        mean = np.mean(matrix, axis=0)
        raw_scale = np.std(matrix, axis=0, ddof=0)
        zero_variance = raw_scale == 0.0
        scale = np.where(zero_variance, 1.0, raw_scale)
        self._mean = mean
        self._scale = scale
        provenance = tuple(
            NuisancePreprocessingFeature(
                feature_name=name,
                mean=float(mean[index]),
                scale=float(scale[index]),
                zero_variance=bool(zero_variance[index]),
            )
            for index, name in enumerate(self._feature_order)
        )
        return (matrix - mean) / scale, provenance


class SklearnLogisticTreatmentAdapter:
    """Deterministic logistic treatment nuisance with oriented probabilities."""

    def __init__(
        self,
        *,
        feature_order: tuple[str, ...],
        seed: int,
        inverse_regularization_strength: float = 1.0,
        tolerance: float = 1e-8,
        maximum_iterations: int = 1000,
    ) -> None:
        self._feature_order = feature_order
        self._seed = seed
        self._c = inverse_regularization_strength
        self._tolerance = tolerance
        self._maximum_iterations = maximum_iterations
        self._mean: np.ndarray | None = None
        self._scale: np.ndarray | None = None
        self._estimator: LogisticRegression | None = None
        self._metadata = NuisanceAdapterMetadata.create(
            role=NuisanceRole.TREATMENT,
            adapter_name="sklearn_logistic_treatment",
            adapter_version="1",
            model_family="regularized_logistic_regression",
            hyperparameters={
                "C": inverse_regularization_strength,
                "fit_intercept": True,
                "l1_ratio": 0.0,
                "maximum_iterations": maximum_iterations,
                "solver": "lbfgs",
                "tolerance": tolerance,
            },
            preprocessing="fold_local_population_standardization",
            feature_order=feature_order,
            seed=seed,
            minimum_training_rows=4,
            dependency_name="scikit-learn",
            dependency_version=sklearn.__version__,
        )

    @property
    def metadata(self) -> NuisanceAdapterMetadata:
        return self._metadata

    def for_fold(self, seed: int) -> SklearnLogisticTreatmentAdapter:
        return SklearnLogisticTreatmentAdapter(
            feature_order=self._feature_order,
            seed=seed,
            inverse_regularization_strength=self._c,
            tolerance=self._tolerance,
            maximum_iterations=self._maximum_iterations,
        )

    def fit(
        self,
        batch: NuisanceFeatureBatch,
        target: tuple[float, ...],
    ) -> NuisanceFitReport:
        try:
            if batch.feature_names != self._feature_order or len(target) != len(batch.rows):
                raise ValueError("treatment nuisance training data is not aligned")
            values = np.asarray(target, dtype=np.int64)
            if set(values.tolist()) != {0, 1}:
                raise ValueError("treatment nuisance requires both binary classes")
            matrix = np.asarray(batch.rows, dtype=np.float64)
            mean = np.mean(matrix, axis=0)
            raw_scale = np.std(matrix, axis=0, ddof=0)
            zero_variance = raw_scale == 0.0
            scale = np.where(zero_variance, 1.0, raw_scale)
            preprocessing = tuple(
                NuisancePreprocessingFeature(
                    feature_name=name,
                    mean=float(mean[index]),
                    scale=float(scale[index]),
                    zero_variance=bool(zero_variance[index]),
                )
                for index, name in enumerate(self._feature_order)
            )
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                estimator = LogisticRegression(
                    C=self._c,
                    l1_ratio=0.0,
                    solver="lbfgs",
                    tol=self._tolerance,
                    max_iter=self._maximum_iterations,
                    fit_intercept=True,
                    class_weight=None,
                    random_state=self._seed,
                    warm_start=False,
                    n_jobs=1,
                    verbose=0,
                )
                estimator.fit((matrix - mean) / scale, values)
                convergence_warning = any(
                    issubclass(item.category, ConvergenceWarning) for item in captured
                )
            classes = tuple(int(value) for value in estimator.classes_.tolist())
            iterations = max(int(value) for value in estimator.n_iter_.tolist())
            if convergence_warning or iterations >= self._maximum_iterations:
                self._estimator = None
                return NuisanceFitReport(
                    role=NuisanceRole.TREATMENT,
                    status=NuisanceFitStatus.NON_CONVERGED,
                    converged=False,
                    training_count=len(target),
                    iteration_count=iterations,
                    classes=classes,
                    warning_codes=("nuisance.convergence_failure",),
                    preprocessing=preprocessing,
                )
            if classes != (0, 1):
                raise ValueError("treatment probability orientation is invalid")
            self._mean = mean
            self._scale = scale
            self._estimator = estimator
            return NuisanceFitReport(
                role=NuisanceRole.TREATMENT,
                status=NuisanceFitStatus.CONVERGED,
                converged=True,
                training_count=len(target),
                iteration_count=iterations,
                classes=classes,
                preprocessing=preprocessing,
            )
        except Exception:
            self._estimator = None
            return _failed_report(NuisanceRole.TREATMENT, len(target), "nuisance.fit_failure")

    def predict_probability(self, batch: NuisanceFeatureBatch) -> tuple[float, ...]:
        if self._estimator is None or self._mean is None or self._scale is None:
            raise RuntimeError("treatment nuisance adapter has no converged fit")
        if batch.feature_names != self._feature_order:
            raise ValueError("treatment nuisance feature order changed")
        matrix = np.asarray(batch.rows, dtype=np.float64)
        classes = tuple(int(value) for value in self._estimator.classes_.tolist())
        treated_index = classes.index(1)
        scores = self._estimator.predict_proba((matrix - self._mean) / self._scale)[
            :, treated_index
        ]
        return tuple(float(value) for value in scores.tolist())


def _failed_report(
    role: NuisanceRole,
    training_count: int,
    code: str,
) -> NuisanceFitReport:
    return NuisanceFitReport(
        role=role,
        status=NuisanceFitStatus.FAILED,
        converged=False,
        training_count=max(1, training_count),
        warning_codes=(code,),
    )


__all__ = ["SklearnLogisticTreatmentAdapter", "SklearnRidgeOutcomeAdapter"]
