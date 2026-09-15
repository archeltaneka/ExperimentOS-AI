"""Private deterministic folds, safe inference normalization and reproducibility metadata."""

from __future__ import annotations

import math
import platform
import warnings
from importlib import metadata
from typing import Any

import numpy as np
from sklearn.exceptions import ConvergenceWarning  # type: ignore[import-untyped]

from ...base import ScalarValue
from ...uncertainty import ConfidenceInterval
from ..advanced.models import (
    AdvancedAdapterProvenance,
    AdvancedEstimatorConfig,
    AdvancedFailureCode,
    AdvancedFeatureMetadata,
    AdvancedInference,
    RuntimeDependency,
)
from ..dml.folds import FoldObservation, build_fold_plan, canonical_observation_key
from ..dml.models import DMLConfig, DMLFoldPlan
from ..dml.protocols import NuisanceHyperparameter
from ..models import IdentificationResult, IdentificationStatus, ObservationalAnalysisRequest
from ..service import CausalIdentificationService
from ..variables import VariableRole
from .dependency import AdapterError, EconMLBackend


def validate_identification(identification: IdentificationResult) -> None:
    """Recheck owned causal declarations; never ask EconML to identify a causal effect."""
    if identification.status is not IdentificationStatus.IDENTIFIED:
        raise AdapterError("identification.invalid", "An identified causal contract is required.")
    checked = CausalIdentificationService().identify(
        ObservationalAnalysisRequest(
            request_id=identification.request_id,
            identification=identification.identification_request,
        )
    )
    if (
        checked.status is not IdentificationStatus.IDENTIFIED
        or checked.adjustment_set != identification.adjustment_set
    ):
        raise AdapterError(
            "identification.invalid", "Causal identification declarations failed revalidation."
        )


def make_splits(
    identities: tuple[ScalarValue, ...],
    treated: tuple[bool, ...],
    config: DMLConfig,
) -> tuple[DMLFoldPlan, tuple[tuple[np.ndarray, np.ndarray], ...]]:
    plan = build_fold_plan(
        tuple(
            FoldObservation(observation_id=i, treated=t)
            for i, t in zip(identities, treated, strict=True)
        ),
        config,
    )
    by_key = {canonical_observation_key(a.observation_id): a.fold_index for a in plan.assignments}
    folds = np.asarray([by_key[canonical_observation_key(i)] for i in identities])
    splits = tuple(
        (np.flatnonzero(folds != k), np.flatnonzero(folds == k)) for k in range(config.fold_count)
    )
    return plan, splits


def fit_estimator(
    estimator: Any, outcome: np.ndarray, treatment: np.ndarray, **kwargs: Any
) -> None:
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            estimator.fit(outcome, treatment, **kwargs)
        if any(issubclass(w.category, ConvergenceWarning) for w in captured):
            raise AdapterError(
                AdvancedFailureCode.ESTIMATOR_FIT_FAILURE, "A nuisance fit did not converge."
            )
    except AdapterError:
        raise
    except Exception:
        raise AdapterError(
            AdvancedFailureCode.ESTIMATOR_FIT_FAILURE, "Optional estimator fit failed."
        ) from None


def scalar(value: Any, code: str) -> float:
    try:
        array = np.asarray(value, dtype=float)
        if array.size != 1:
            raise AdapterError(
                AdvancedFailureCode.INVALID_DATA_SHAPE,
                "Inference must return one scalar per requested effect.",
            )
        number = float(array.reshape(-1)[0])
    except AdapterError:
        raise
    except Exception:
        raise AdapterError(
            AdvancedFailureCode.INVALID_DATA_SHAPE, "Inference returned an invalid scalar shape."
        ) from None
    if not math.isfinite(number):
        raise AdapterError(code, "Optional estimator returned a non-finite numerical result.")
    return number


def normalize_inference(
    info: Any, interval: Any, confidence: float
) -> tuple[float, AdvancedInference]:
    point = scalar(info.point_estimate, AdvancedFailureCode.NONFINITE_ESTIMATE)
    error = scalar(info.stderr, AdvancedFailureCode.NONFINITE_UNCERTAINTY)
    if error <= 0:
        raise AdapterError(
            AdvancedFailureCode.NONFINITE_UNCERTAINTY,
            "Inference requires positive finite uncertainty.",
        )
    lower = scalar(interval[0], AdvancedFailureCode.NONFINITE_UNCERTAINTY)
    upper = scalar(interval[1], AdvancedFailureCode.NONFINITE_UNCERTAINTY)
    if not lower <= point <= upper or lower == upper:
        raise AdapterError(
            AdvancedFailureCode.NONFINITE_UNCERTAINTY,
            "Inference interval is invalid or degenerate.",
        )
    inference = AdvancedInference(
        standard_error=error,
        statistic=scalar(info.zstat(value=0), AdvancedFailureCode.NONFINITE_UNCERTAINTY),
        p_value=scalar(info.pvalue(value=0), AdvancedFailureCode.NONFINITE_UNCERTAINTY),
        confidence_interval=ConfidenceInterval(
            lower=lower, upper=upper, confidence_level=confidence
        ),
    )
    return point, inference


def effect_inference(
    estimator: Any, x: np.ndarray | None, confidence: float
) -> tuple[float, AdvancedInference]:
    try:
        info = estimator.effect_inference(x, T0=0, T1=1)
        # Validate before calling interval APIs that may themselves compute invalid uncertainty.
        scalar(info.point_estimate, AdvancedFailureCode.NONFINITE_ESTIMATE)
        error = scalar(info.stderr, AdvancedFailureCode.NONFINITE_UNCERTAINTY)
        if error <= 0:
            raise AdapterError(
                AdvancedFailureCode.NONFINITE_UNCERTAINTY, "Inference uncertainty is degenerate."
            )
        interval = estimator.effect_interval(x, T0=0, T1=1, alpha=1 - confidence)
        point, inference = normalize_inference(info, interval, confidence)
        direct = scalar(estimator.effect(x, T0=0, T1=1), AdvancedFailureCode.NONFINITE_ESTIMATE)
        if not math.isclose(point, direct, rel_tol=1e-10, abs_tol=1e-12):
            raise AdapterError(
                AdvancedFailureCode.INVALID_DATA_SHAPE, "Effect and inference estimates disagree."
            )
        return point, inference
    except AdapterError:
        raise
    except Exception:
        raise AdapterError(
            AdvancedFailureCode.INFERENCE_FAILURE, "Optional estimator inference failed."
        ) from None


def adapter_provenance(
    *,
    backend: EconMLBackend,
    adapter_id: str,
    estimator_class: str,
    identification: IdentificationResult,
    columns: tuple[tuple[str, str, VariableRole], ...],
    config: AdvancedEstimatorConfig,
    plan: DMLFoldPlan,
    dr: bool,
) -> AdvancedAdapterProvenance:
    variables = {v.variable_id: v for v in identification.identification_request.variables}
    values: dict[str, ScalarValue] = {
        "categories": "control=0,treated=1",
        "discrete_outcome": False,
        "fit_cate_intercept": True,
        "mc_iters": "none",
        "allow_missing": False,
        "use_ray": False,
        "cov_type": "HC1",
        "random_state": plan.random_seed,
        "cv": "ExperimentOS explicit stable-ID index splits",
    }
    if dr:
        values.update(
            {
                "min_propensity": 0.0,
                "trimming_threshold": "none",
                "cate_features": "single registered subgroup indicator",
            }
        )
    else:
        values.update({"discrete_treatment": True, "cate_features": "none:constant effect"})
    assert identification.estimand is not None
    return AdvancedAdapterProvenance(
        adapter_id=adapter_id,
        econml_version=backend.version,
        estimator_class=estimator_class,
        estimator_configuration=tuple(
            NuisanceHyperparameter(key=k, value=v) for k, v in sorted(values.items())
        ),
        estimand="cate" if dr else "ate",
        nuisance_configuration=config,
        seed=plan.random_seed,
        random_state=plan.random_seed,
        nuisance_seed=plan.random_seed,
        fold_count=plan.fold_count,
        fold_fingerprint_sha256=plan.fingerprint_sha256,
        features=tuple(
            AdvancedFeatureMetadata(
                variable_id=v, column=c, role=r, timing=variables[v].timing.measurement_timing
            )
            for v, c, r in columns
        ),
        python_version=platform.python_version(),
        platform=f"{platform.system()}-{platform.machine()}",
        dependencies=tuple(
            RuntimeDependency(name=n, version=metadata.version(n))
            for n in (
                "econml",
                "numpy",
                "scipy",
                "scikit-learn",
                "statsmodels",
                "shap",
                "lightgbm",
                "numba",
                "sparse",
                "pandas",
                "llvmlite",
                "joblib",
                "packaging",
            )
        ),
    )
