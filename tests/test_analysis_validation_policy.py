from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.experiments.analysis.validation import ValidationPolicy


@pytest.mark.parametrize(
    ("field", "valid_value"),
    [
        ("minimum_total", 2),
        ("minimum_per_arm", 2),
        ("weak_total", 101),
        ("weak_per_arm", 31),
        ("minimum_per_segment_arm", 2),
        ("minimum_clusters", 3),
        ("weak_clusters", 21),
        ("maximum_segment_cardinality", 2),
    ],
)
def test_policy_integer_thresholds_are_strict(field: str, valid_value: int) -> None:
    assert getattr(ValidationPolicy(**{field: valid_value}), field) == valid_value
    for invalid_value in (str(valid_value), float(valid_value), True):
        with pytest.raises(ValidationError):
            ValidationPolicy(**{field: invalid_value})


@pytest.mark.parametrize("invalid_value", (-0.01, 1.01, "0.5"))
def test_covariate_missingness_threshold_is_optional_strict_probability(
    invalid_value: object,
) -> None:
    assert ValidationPolicy().maximum_covariate_missing_rate is None
    assert (
        ValidationPolicy(maximum_covariate_missing_rate=0.5).maximum_covariate_missing_rate == 0.5
    )
    with pytest.raises(ValidationError):
        ValidationPolicy(maximum_covariate_missing_rate=invalid_value)


def test_policy_defaults_ignore_ambient_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXPERIMENTOS_MINIMUM_TOTAL", "999")
    monkeypatch.setenv("EXPERIMENTOS_MAXIMUM_COVARIATE_MISSING_RATE", "0.0")

    policy = ValidationPolicy()

    assert policy.minimum_total == 30
    assert policy.maximum_covariate_missing_rate is None
