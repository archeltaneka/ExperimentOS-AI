"""Private scikit-learn adapter behavior and owned fit boundary."""

from __future__ import annotations

import numpy as np

from packages.experiments.analysis.causal.propensity import (
    PropensityConfig,
    PropensityFitStatus,
    validate_propensity_input,
)
from packages.experiments.analysis.causal.propensity.adapter import (
    SklearnLogisticPropensityAdapter,
)
from packages.experiments.analysis.causal.propensity.encoding import encode_propensity_features
from tests.propensity_fixtures import propensity_execution, propensity_table, small_valid_rows


def encoded_input():
    execution = propensity_execution()
    validated = validate_propensity_input(execution, propensity_table(small_valid_rows()))
    return encode_propensity_features(validated, execution.configuration)


def test_adapter_returns_aligned_finite_owned_scores_deterministically() -> None:
    encoded = encoded_input()
    adapter = SklearnLogisticPropensityAdapter()

    first = adapter.fit_predict(encoded, PropensityConfig())
    second = adapter.fit_predict(encoded, PropensityConfig())

    assert first == second
    assert first.status is PropensityFitStatus.CONVERGED
    assert first.converged is True
    assert first.classes == (0, 1)
    assert first.iteration_count is not None
    assert 0 < first.iteration_count <= 1000
    assert len(first.scores) == len(encoded.unit_ids)
    assert all(0.0 <= score <= 1.0 for score in first.scores)
    assert first.sklearn_version
    assert first.solver == "lbfgs"
    assert not isinstance(first.scores, np.ndarray)
    assert "LogisticRegression" not in repr(first)


def test_adapter_normalizes_deterministic_convergence_failure() -> None:
    encoded = encoded_input()
    config = PropensityConfig(maximum_iterations=1, tolerance=1e-15)

    result = SklearnLogisticPropensityAdapter().fit_predict(encoded, config)

    assert result.status is PropensityFitStatus.NON_CONVERGED
    assert result.converged is False
    assert result.scores == ()
    assert "model.convergence_failure" in result.warning_codes
