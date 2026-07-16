from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

VerificationMode = Literal["strict", "offline_only"]
CommandStatus = Literal["pass", "fail", "skipped", "timeout"]
MilestoneRecommendation = Literal[
    "ready_to_close",
    "ready_with_documented_limitations",
    "not_ready",
]


@dataclass(frozen=True)
class VerificationCommand:
    command_id: str
    argv: tuple[str, ...]
    required: bool
    timeout_seconds: int
    report_paths: tuple[str, ...] = ()
    strict_only: bool = False


@dataclass(frozen=True)
class CommandResult:
    command_id: str
    argv: tuple[str, ...]
    status: CommandStatus
    exit_code: int | None
    duration_seconds: float
    stdout_tail: str
    stderr_tail: str
    report_paths: tuple[str, ...]


@dataclass(frozen=True)
class CapabilityInventoryItem:
    capability_id: str
    name: str
    implementation_locations: tuple[str, ...]
    configuration: tuple[str, ...]
    cli_commands: tuple[str, ...]
    tests: tuple[str, ...]
    generated_reports: tuple[str, ...]
    documentation: tuple[str, ...]
    optional_dependencies: tuple[str, ...]
    default_state: Literal["enabled", "disabled", "conditional"]
    external_service_requirement: Literal["none", "optional", "local_postgres"]
    known_limitations: tuple[str, ...]


@dataclass(frozen=True)
class ReviewFinding:
    finding_id: str
    area: str
    severity: Literal["info", "warning", "critical"]
    status: Literal["fixed", "open", "accepted"]
    summary: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class FinalReliabilityReview:
    schema_version: str
    generated_at_utc: str
    mode: VerificationMode
    closeout_eligible: bool
    recommendation: MilestoneRecommendation
    overall_status: Literal["pass", "fail"]
    commands: tuple[CommandResult, ...]
    capability_inventory: tuple[CapabilityInventoryItem, ...]
    findings: tuple[ReviewFinding, ...]
    dataset_versions: dict[str, str]
    policy_version: str
    provider_configuration: dict[str, str]
    factuality_invariants: dict[str, int]
    compatibility: dict[str, str]
    limitations: tuple[str, ...]
    unresolved_risks: tuple[str, ...]
    section_summaries: dict[str, str] = field(default_factory=dict)
