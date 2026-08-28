"""Owned inverse-probability-weighting contract behavior."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.experiments.analysis.causal import CausalIdentificationService
from packages.experiments.analysis.causal.ipw import (
    IPWConfig,
    IPWExecutionRequest,
    IPWOutcomeBinding,
    IPWWeightClippingConfig,
)
from packages.experiments.analysis.causal.propensity import (
    DeterministicLogisticPropensityEstimator,
)
from tests.causal_identification_fixtures import provenance
from tests.propensity_fixtures import (
    good_overlap_rows,
    propensity_execution,
    propensity_request,
    propensity_table,
)


def test_config_defaults_require_explicit_stabilization_and_clipping() -> None:
    config = IPWConfig()

    assert config.stabilized is False
    assert config.clipping is None
    assert config.confidence_level == 0.95
    assert config.severe_balance_threshold == 0.25
    assert config.heavy_clipping_fraction == 0.10
    assert config.prevalence_warning_lower == 0.10
    assert config.prevalence_warning_upper == 0.90
    assert config.analysis_version == "ipw-v1"


def test_config_rejects_incoherent_balance_and_prevalence_policy() -> None:
    with pytest.raises(ValidationError, match="severe balance"):
        IPWConfig(severe_balance_threshold=0.05)
    with pytest.raises(ValidationError, match="prevalence"):
        IPWConfig(prevalence_warning_lower=0.90, prevalence_warning_upper=0.10)


def test_clipping_requires_a_positive_finite_maximum() -> None:
    assert IPWWeightClippingConfig(maximum=10.0).maximum == 10.0

    with pytest.raises(ValidationError):
        IPWWeightClippingConfig(maximum=0.0)


def test_execution_request_requires_owned_identification_and_propensity_results() -> None:
    request = propensity_request()
    identification = CausalIdentificationService().identify(request)
    propensity = DeterministicLogisticPropensityEstimator().fit_predict(
        propensity_execution(analysis_request=request),
        propensity_table(good_overlap_rows()),
        provenance=provenance("ipw-contract"),
    )

    execution = IPWExecutionRequest(
        identification_result=identification,
        propensity_result=propensity,
        binding=IPWOutcomeBinding(outcome_column="conversion"),
    )

    assert execution.request_id == request.request_id
    assert execution.binding.outcome_column == "conversion"
    assert execution.configuration == IPWConfig()
