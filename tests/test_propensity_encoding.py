"""Deterministic owned propensity feature encoding."""

from __future__ import annotations

import math

import pytest

from packages.experiments.analysis.causal.propensity import validate_propensity_input
from packages.experiments.analysis.causal.propensity.encoding import encode_propensity_features
from tests.propensity_fixtures import (
    propensity_execution,
    propensity_table,
    small_valid_rows,
)


def validated_input():
    return validate_propensity_input(
        propensity_execution(),
        propensity_table(small_valid_rows()),
    )


def test_encoding_uses_population_scaling_and_explicit_category_reference() -> None:
    encoded = encode_propensity_features(validated_input(), propensity_execution().configuration)

    numeric = encoded.metadata.numeric[0]
    categorical = encoded.metadata.categorical[0]
    assert numeric.variable_id == "prior_orders"
    assert numeric.mean == pytest.approx(2.5)
    assert numeric.scale == pytest.approx(math.sqrt(1.25))
    assert numeric.zero_variance is False
    assert categorical.variable_id == "country"
    assert categorical.categories == ("TH", "US")
    assert categorical.reference_category == "TH"
    assert categorical.unseen_category_policy == "error"
    assert encoded.metadata.model_feature_names == ('country==str:"US"', "prior_orders")
    assert encoded.metadata.balance_feature_names == (
        'country==str:"TH"',
        'country==str:"US"',
        "prior_orders",
    )


def test_encoding_preserves_source_alignment_and_separates_model_from_balance_values() -> None:
    encoded = encode_propensity_features(validated_input(), propensity_execution().configuration)

    assert encoded.unit_ids == ("u-3", "u-1", "u-4", "u-2")
    assert encoded.treated == (True, False, True, False)
    assert encoded.model_matrix[0] == pytest.approx(
        (0.0, (4.0 - 2.5) / math.sqrt(1.25))
    )
    assert encoded.balance_matrix[0] == (1.0, 0.0, 4.0)
    assert encoded.model_matrix[1][0] == 1.0
    assert encoded.balance_matrix[1] == (0.0, 1.0, 2.0)


def test_encoding_is_byte_for_byte_deterministic() -> None:
    first = encode_propensity_features(validated_input(), propensity_execution().configuration)
    second = encode_propensity_features(validated_input(), propensity_execution().configuration)

    assert first == second
    assert first.metadata.model_dump_json() == second.metadata.model_dump_json()


def test_zero_variance_numeric_feature_encodes_as_zero_and_is_recorded() -> None:
    rows = tuple({**row, "prior_orders": 2.0} for row in small_valid_rows())
    validated = validate_propensity_input(propensity_execution(), propensity_table(rows))

    encoded = encode_propensity_features(validated, propensity_execution().configuration)

    assert encoded.metadata.numeric[0].zero_variance is True
    assert encoded.metadata.numeric[0].scale == 1.0
    assert all(row[-1] == 0.0 for row in encoded.model_matrix)


def test_typed_category_order_does_not_equate_boolean_and_integer_values() -> None:
    rows = list(small_valid_rows())
    rows[0] = {**rows[0], "country": True}
    rows[1] = {**rows[1], "country": 1}
    validated = validate_propensity_input(propensity_execution(), propensity_table(rows))

    encoded = encode_propensity_features(validated, propensity_execution().configuration)

    categories = encoded.metadata.categorical[0].categories
    assert categories == (True, 1, "TH", "US")
    assert encoded.metadata.categorical[0].reference_category is True
