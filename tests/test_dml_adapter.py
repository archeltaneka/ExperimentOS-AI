"""Private sklearn nuisance adapters return only owned deterministic evidence."""

from __future__ import annotations

import inspect

from packages.experiments.analysis.causal.dml.adapter import (
    SklearnLogisticTreatmentAdapter,
    SklearnRidgeOutcomeAdapter,
)
from packages.experiments.analysis.causal.dml.protocols import (
    NuisanceFeatureBatch,
    NuisanceFitStatus,
)


def batch(*, offset: float = 0.0) -> NuisanceFeatureBatch:
    return NuisanceFeatureBatch(
        observation_ids=("u-0", "u-1", "u-2", "u-3", "u-4", "u-5"),
        feature_names=("x",),
        rows=tuple((offset + float(index),) for index in range(6)),
    )


def test_ridge_adapter_is_repeatable_and_records_fold_local_preprocessing() -> None:
    target = (1.0, 3.0, 5.0, 7.0, 9.0, 11.0)
    first = SklearnRidgeOutcomeAdapter(feature_order=("x",), seed=17)
    second = SklearnRidgeOutcomeAdapter(feature_order=("x",), seed=17)

    first_fit = first.fit(batch(), target)
    second_fit = second.fit(batch(), target)

    assert first_fit == second_fit
    assert first_fit.status is NuisanceFitStatus.CONVERGED
    assert first.predict(batch()) == second.predict(batch())
    assert len(first.predict(batch())) == 6
    assert first_fit.preprocessing[0].mean == 2.5
    assert first_fit.preprocessing[0].scale > 0.0
    assert first.metadata.configuration_fingerprint_sha256
    assert "Ridge" not in repr(first_fit)

    shifted = SklearnRidgeOutcomeAdapter(feature_order=("x",), seed=17)
    shifted_fit = shifted.fit(batch(offset=100.0), target)
    assert shifted_fit.preprocessing[0].mean == 102.5


def test_logistic_adapter_is_repeatable_orients_treated_probability_and_converges() -> None:
    treatment = (0.0, 0.0, 0.0, 1.0, 1.0, 1.0)
    first = SklearnLogisticTreatmentAdapter(feature_order=("x",), seed=17)
    second = SklearnLogisticTreatmentAdapter(feature_order=("x",), seed=17)

    first_fit = first.fit(batch(), treatment)
    second_fit = second.fit(batch(), treatment)
    first_scores = first.predict_probability(batch())

    assert first_fit == second_fit
    assert first_fit.status is NuisanceFitStatus.CONVERGED
    assert first_fit.classes == (0, 1)
    assert first_scores == second.predict_probability(batch())
    assert all(0.0 <= score <= 1.0 for score in first_scores)
    assert first_scores[0] < first_scores[-1]
    assert "LogisticRegression" not in repr(first_fit)


def test_logistic_adapter_normalizes_convergence_failure() -> None:
    adapter = SklearnLogisticTreatmentAdapter(
        feature_order=("x",),
        seed=17,
        maximum_iterations=1,
        tolerance=1e-15,
    )

    report = adapter.fit(batch(), (0.0, 0.0, 0.0, 1.0, 1.0, 1.0))

    assert report.status is NuisanceFitStatus.NON_CONVERGED
    assert report.converged is False
    assert "nuisance.convergence_failure" in report.warning_codes


def test_public_protocol_module_does_not_import_sklearn() -> None:
    from packages.experiments.analysis.causal.dml import protocols

    source = inspect.getsource(protocols).lower()
    assert "import sklearn" not in source
    assert "from sklearn" not in source
