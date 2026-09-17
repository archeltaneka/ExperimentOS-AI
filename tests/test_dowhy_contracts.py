from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.experiments.analysis.causal.dowhy.models import (
    DoWhyConfig,
    DoWhyOperationStatus,
    DoWhyRefuterMethod,
)


def test_refuter_configuration_is_bounded() -> None:
    with pytest.raises(ValidationError):
        DoWhyConfig(seed=-1)
    with pytest.raises(ValidationError):
        DoWhyConfig(num_simulations=0)
    with pytest.raises(ValidationError):
        DoWhyConfig(subset_fraction=1.0)


def test_configuration_canonicalizes_refuters() -> None:
    config = DoWhyConfig(refuters=(DoWhyRefuterMethod.DATA_SUBSET, DoWhyRefuterMethod.PLACEBO))
    assert config.refuters == (
        DoWhyRefuterMethod.PLACEBO,
        DoWhyRefuterMethod.DATA_SUBSET,
    )


def test_status_vocabulary_is_explicit() -> None:
    assert {status.value for status in DoWhyOperationStatus} == {
        "completed",
        "abstained",
        "invalid",
        "unsupported",
        "error",
    }


def test_execution_fixture_constructs_owned_request() -> None:
    from tests.dowhy_fixtures import execution

    assert execution().identification_result.request_id == "causal-request-001"
