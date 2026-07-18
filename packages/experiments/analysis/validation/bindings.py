"""Explicit mappings from analytical roles to immutable table columns."""

from __future__ import annotations

from typing import Self

from pydantic import StrictBool, model_validator

from ..base import ContractModel, FiniteFloat, NonEmptyStr


class MetricColumnBinding(ContractModel):
    """Bind one declared metric identifier to its physical table column."""

    metric_id: NonEmptyStr
    column: NonEmptyStr


class OutcomeDataBinding(ContractModel):
    """Bind an outcome to either one value column or a numerator/denominator pair."""

    value_column: NonEmptyStr | None = None
    numerator_column: NonEmptyStr | None = None
    denominator_column: NonEmptyStr | None = None
    lower_bound: FiniteFloat | None = None
    upper_bound: FiniteFloat | None = None
    allow_negative: StrictBool = True

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        has_value = self.value_column is not None
        has_numerator = self.numerator_column is not None
        has_denominator = self.denominator_column is not None
        has_ratio = has_numerator and has_denominator
        if has_value == has_ratio or has_numerator != has_denominator:
            raise ValueError(
                "outcome binding requires a value column or a numerator/denominator pair"
            )
        if has_ratio and self.numerator_column == self.denominator_column:
            raise ValueError("outcome numerator and denominator columns must differ")
        if (
            self.lower_bound is not None
            and self.upper_bound is not None
            and self.lower_bound > self.upper_bound
        ):
            raise ValueError("outcome lower_bound must not exceed upper_bound")
        return self

    @property
    def columns(self) -> tuple[str, ...]:
        """Return the physical outcome columns in their analytical order."""
        if self.value_column is not None:
            return (self.value_column,)
        if self.numerator_column is None or self.denominator_column is None:
            raise RuntimeError("validated outcome binding is missing ratio columns")
        return (self.numerator_column, self.denominator_column)


class AnalysisDataBinding(ContractModel):
    """Bind request roles to table columns without interpreting or rewriting values."""

    treatment_column: NonEmptyStr
    outcome: OutcomeDataBinding
    observation_unit_column: NonEmptyStr
    randomization_unit_column: NonEmptyStr | None = None
    clustering_unit_column: NonEmptyStr | None = None
    timestamp_column: NonEmptyStr | None = None
    covariates: tuple[MetricColumnBinding, ...] = ()
    treatment_timestamp_column: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_roles(self) -> Self:
        metric_ids = tuple(binding.metric_id for binding in self.covariates)
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("covariate metric identifiers must be unique")

        covariate_columns = tuple(binding.column for binding in self.covariates)
        if len(covariate_columns) != len(set(covariate_columns)):
            raise ValueError("covariate columns must be unique")

        if self.treatment_column in self.outcome.columns:
            raise ValueError("treatment and outcome columns must differ")

        protected_columns = {
            self.treatment_column,
            *self.outcome.columns,
            self.observation_unit_column,
        }
        protected_columns.update(
            column
            for column in (
                self.randomization_unit_column,
                self.clustering_unit_column,
                self.timestamp_column,
                self.treatment_timestamp_column,
            )
            if column is not None
        )
        if any(column in protected_columns for column in covariate_columns):
            raise ValueError("covariate columns must not reuse another analytical role")
        return self
