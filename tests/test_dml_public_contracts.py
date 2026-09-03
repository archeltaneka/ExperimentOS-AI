"""Public DML contracts remain owned and library-independent."""

from __future__ import annotations

from packages.experiments.analysis import (
    DMLConfig,
    DMLCovariateBinding,
    DMLDataBinding,
    DMLExecutionRequest,
    DMLResult,
    DMLStatus,
    DoubleMachineLearningEstimator,
)
from packages.experiments.analysis.causal.dml import (
    NuisanceAdapterMetadata,
    OutcomeNuisanceModel,
    TreatmentNuisanceModel,
)


def test_public_dml_surface_contains_only_experimentos_owned_types() -> None:
    public_types = (
        DMLConfig,
        DMLCovariateBinding,
        DMLDataBinding,
        DMLExecutionRequest,
        DMLResult,
        DMLStatus,
        DoubleMachineLearningEstimator,
        NuisanceAdapterMetadata,
        OutcomeNuisanceModel,
        TreatmentNuisanceModel,
    )
    forbidden = ("sklearn", "statsmodels", "econml", "dowhy")

    for public_type in public_types:
        assert not any(name in public_type.__module__.lower() for name in forbidden)

    schema = DMLResult.model_json_schema()
    serialized = str(schema).lower()
    assert not any(name in serialized for name in forbidden)
