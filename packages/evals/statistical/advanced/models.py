"""Typed advanced metadata attached to existing statistical reference/results."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Applicability(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    NOT_APPLICABLE = "not_applicable"


class AdvancedCaseDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    capability_id: str
    scenario: str
    seed: int = 812
    uncertainty: Applicability
    dependency_expectation: Literal["optional", "core", "controlled"]
    fingerprint_expectation: Literal["stable", "changed_seed"] = "stable"


class AdvancedResultDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    suite_version: Literal["1"] = "1"
    capability_id: str
    adapter_id: str
    adapter_version: str
    implementation_version: str
    dependency_package: str | None = None
    dependency_version: str | None = None
    dependency_state: Literal["not_required", "installed", "unavailable", "broken", "controlled"]
    configuration_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    seed: int
    native_status: str
    semantic_status: Literal[
        "successful", "invalid", "abstained", "failed", "unavailable", "skipped"
    ]
    uncertainty: Applicability
    uncertainty_support: Literal["supported", "unsupported", "not_applicable"]
    execution_kind: Literal["real", "controlled"]
