"""Private scikit-learn adapter for deterministic baseline propensity scores."""

from __future__ import annotations

import warnings

import numpy as np
import sklearn  # type: ignore[import-untyped]
from sklearn.exceptions import ConvergenceWarning  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]

from .encoding import EncodedPropensityData
from .models import PropensityConfig, PropensityFitStatus, PropensityModelFit


class SklearnLogisticPropensityAdapter:
    """Fit scikit-learn logistic regression and return only owned scalar evidence."""

    def fit_predict(
        self,
        encoded: EncodedPropensityData,
        config: PropensityConfig,
    ) -> PropensityModelFit:
        """Return oriented scores or a normalized non-valid fit record."""
        try:
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                estimator = LogisticRegression(
                    C=config.inverse_regularization_strength,
                    l1_ratio=config.l1_ratio,
                    solver=config.solver,
                    tol=config.tolerance,
                    max_iter=config.maximum_iterations,
                    fit_intercept=config.fit_intercept,
                    class_weight=None,
                    random_state=config.random_seed,
                    warm_start=False,
                    n_jobs=1,
                    verbose=0,
                )
                matrix = np.asarray(encoded.model_matrix, dtype=np.float64)
                treatment = np.asarray(encoded.treated, dtype=np.int64)
                estimator.fit(matrix, treatment)
                convergence_warning = any(
                    issubclass(item.category, ConvergenceWarning) for item in captured
                )
            classes = tuple(int(value) for value in estimator.classes_.tolist())
            iteration_count = max(int(value) for value in estimator.n_iter_.tolist())
            non_converged = convergence_warning or iteration_count >= config.maximum_iterations
            if classes != (0, 1):
                return _invalid_fit(
                    config,
                    PropensityFitStatus.FAILED,
                    "model.invalid_class_orientation",
                    classes=classes,
                    iteration_count=iteration_count,
                )
            if non_converged:
                return _invalid_fit(
                    config,
                    PropensityFitStatus.NON_CONVERGED,
                    "model.convergence_failure",
                    classes=classes,
                    iteration_count=iteration_count,
                )

            treated_index = classes.index(1)
            probabilities = estimator.predict_proba(matrix)[:, treated_index]
            scores = tuple(float(value) for value in probabilities.tolist())
            if any(not np.isfinite(value) or value < 0.0 or value > 1.0 for value in scores):
                return _invalid_fit(
                    config,
                    PropensityFitStatus.FAILED,
                    "model.invalid_score",
                    classes=classes,
                    iteration_count=iteration_count,
                )
            predictions = estimator.predict(matrix)
            accuracy = float(np.mean(predictions == treatment))
            maximum_coefficient = float(np.max(np.abs(estimator.coef_)))
            threshold = config.extreme_score_threshold
            extreme_fraction = sum(
                score <= threshold or score >= 1.0 - threshold for score in scores
            ) / len(scores)
            return PropensityModelFit(
                status=PropensityFitStatus.CONVERGED,
                converged=True,
                scores=scores,
                classes=classes,
                iteration_count=iteration_count,
                solver=config.solver,
                warning_codes=(),
                sklearn_version=sklearn.__version__,
                training_accuracy=accuracy,
                maximum_absolute_coefficient=maximum_coefficient,
                extreme_score_fraction=extreme_fraction,
            )
        except Exception:
            return _invalid_fit(
                config,
                PropensityFitStatus.FAILED,
                "model.fit_failure",
            )


def _invalid_fit(
    config: PropensityConfig,
    status: PropensityFitStatus,
    warning_code: str,
    *,
    classes: tuple[int, ...] = (),
    iteration_count: int | None = None,
) -> PropensityModelFit:
    return PropensityModelFit(
        status=status,
        converged=False,
        scores=(),
        classes=classes,
        iteration_count=iteration_count,
        solver=config.solver,
        warning_codes=(warning_code,),
        sklearn_version=sklearn.__version__,
    )


__all__ = ["SklearnLogisticPropensityAdapter"]
