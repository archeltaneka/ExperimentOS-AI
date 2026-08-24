"""Deterministic owned feature encoding for propensity-score fitting and balance."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import cast

from ...base import ScalarValue
from .models import (
    CategoricalFeatureEncoding,
    NumericFeatureEncoding,
    PropensityConfig,
    PropensityEncodingMetadata,
    PropensityFeatureKind,
)
from .validation import PropensityValidationDisposition, PropensityValidationResult


class PropensityEncodingError(ValueError):
    """Raised when validated rows cannot be deterministically encoded."""


@dataclass(frozen=True, slots=True)
class EncodedPropensityData:
    """Private tuple-backed matrices aligned with the validated model population."""

    unit_ids: tuple[object, ...]
    treated: tuple[bool, ...]
    model_matrix: tuple[tuple[float, ...], ...]
    balance_matrix: tuple[tuple[float, ...], ...]
    metadata: PropensityEncodingMetadata


def encode_propensity_features(
    validated: PropensityValidationResult,
    config: PropensityConfig,
) -> EncodedPropensityData:
    """Encode validated complete cases without relying on library category ordering."""
    del config
    if validated.disposition is not PropensityValidationDisposition.VALID or not validated.rows:
        raise PropensityEncodingError("only valid non-empty propensity inputs can be encoded")

    model_columns: list[tuple[float, ...]] = []
    balance_columns: list[tuple[float, ...]] = []
    model_names: list[str] = []
    balance_names: list[str] = []
    numeric_metadata: list[NumericFeatureEncoding] = []
    categorical_metadata: list[CategoricalFeatureEncoding] = []

    for index, covariate in enumerate(validated.covariates):
        values = tuple(row.covariate_values[index] for row in validated.rows)
        if covariate.feature_kind is PropensityFeatureKind.NUMERIC:
            numeric = tuple(float(cast(int | float, value)) for value in values)
            mean = math.fsum(numeric) / len(numeric)
            variance = math.fsum((value - mean) ** 2 for value in numeric) / len(numeric)
            raw_scale = math.sqrt(variance)
            zero_variance = raw_scale == 0.0
            scale = 1.0 if zero_variance else raw_scale
            model_columns.append(tuple((value - mean) / scale for value in numeric))
            balance_columns.append(numeric)
            model_names.append(covariate.variable_id)
            balance_names.append(covariate.variable_id)
            numeric_metadata.append(
                NumericFeatureEncoding(
                    variable_id=covariate.variable_id,
                    feature_name=covariate.variable_id,
                    mean=mean,
                    scale=scale,
                    zero_variance=zero_variance,
                )
            )
            continue

        categories = tuple(cast(ScalarValue, value) for value in _ordered_distinct(values))
        reference = categories[0]
        categorical_model_names: list[str] = []
        categorical_balance_names: list[str] = []
        for category_index, category in enumerate(categories):
            feature_name = f"{covariate.variable_id}=={_category_label(category)}"
            indicator = tuple(float(_typed_equal(value, category)) for value in values)
            balance_columns.append(indicator)
            balance_names.append(feature_name)
            categorical_balance_names.append(feature_name)
            if category_index > 0:
                model_columns.append(indicator)
                model_names.append(feature_name)
                categorical_model_names.append(feature_name)
        categorical_metadata.append(
            CategoricalFeatureEncoding(
                variable_id=covariate.variable_id,
                categories=categories,
                reference_category=reference,
                model_feature_names=tuple(categorical_model_names),
                balance_feature_names=tuple(categorical_balance_names),
            )
        )

    return EncodedPropensityData(
        unit_ids=tuple(row.unit_id for row in validated.rows),
        treated=tuple(row.treated for row in validated.rows),
        model_matrix=_transpose(model_columns, len(validated.rows)),
        balance_matrix=_transpose(balance_columns, len(validated.rows)),
        metadata=PropensityEncodingMetadata(
            numeric=tuple(numeric_metadata),
            categorical=tuple(categorical_metadata),
            model_feature_names=tuple(model_names),
            balance_feature_names=tuple(balance_names),
        ),
    )


def _transpose(
    columns: list[tuple[float, ...]],
    row_count: int,
) -> tuple[tuple[float, ...], ...]:
    if not columns:
        raise PropensityEncodingError("at least one encoded feature is required")
    return tuple(tuple(column[row] for column in columns) for row in range(row_count))


def _ordered_distinct(values: tuple[object, ...]) -> tuple[object, ...]:
    by_key = {_category_key(value): value for value in values}
    return tuple(by_key[key] for key in sorted(by_key))


def _category_key(value: object) -> tuple[int, str]:
    ranks = {bool: 0, int: 1, float: 2, str: 3}
    rank = ranks.get(type(value))
    if rank is None:
        raise PropensityEncodingError("unsupported categorical scalar type")
    return rank, json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _category_label(value: object) -> str:
    tags = {bool: "bool", int: "int", float: "float", str: "str"}
    return f"{tags[type(value)]}:{_category_key(value)[1]}"


def _typed_equal(left: object, right: object) -> bool:
    return type(left) is type(right) and left == right


__all__ = ["EncodedPropensityData", "PropensityEncodingError", "encode_propensity_features"]
