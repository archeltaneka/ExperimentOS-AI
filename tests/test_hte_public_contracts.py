"""The HTE public surface remains ExperimentOS-owned and serializable."""

from __future__ import annotations

from packages.experiments.analysis import (
    EffectModifierDefinition,
    HeterogeneousEffectEstimator,
    HeterogeneousEffectResult,
    HTEConfig,
    HTEExecutionRequest,
    SubgroupEffectResult,
)


def test_public_hte_surface_contains_no_third_party_result_types() -> None:
    public_types = (
        EffectModifierDefinition,
        HeterogeneousEffectEstimator,
        HeterogeneousEffectResult,
        HTEConfig,
        HTEExecutionRequest,
        SubgroupEffectResult,
    )
    forbidden = ("sklearn", "statsmodels", "econml", "dowhy")

    for public_type in public_types:
        assert not any(name in public_type.__module__.lower() for name in forbidden)

    serialized = str(HeterogeneousEffectResult.model_json_schema()).lower()
    assert not any(name in serialized for name in forbidden)
