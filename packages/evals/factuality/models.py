from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Literal

FindingCategory = Literal[
    "unsupported_factual_claim",
    "unsupported_numerical_claim",
    "fabricated_revenue_or_roi",
    "fabricated_statistical_significance",
    "fabricated_experiment_result",
    "citation_missing",
    "citation_does_not_support_claim",
    "contradiction_with_retrieved_context",
    "contradiction_with_structured_experiment_data",
    "overconfident_answer_with_insufficient_evidence",
    "answer_generated_when_abstention_was_expected",
]
Severity = Literal["low", "medium", "high", "critical"]
FindingClassification = Literal[
    "true_positive",
    "false_positive",
    "dataset_mismatch",
    "parser_error",
    "report_error",
    "unresolved",
]
FactualitySurface = Literal["legacy_rag", "agent_workflow"]
PolicyStatus = Literal["pass", "fail", "warning", "skipped"]
FactualityTarget = Literal["legacy_rag", "agent_workflow", "all"]
FactualityMode = Literal["offline", "judge"]


@dataclass(frozen=True)
class EvidenceRecord:
    source_id: str
    source_type: str
    text: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CitationRecord:
    source_id: str
    source_type: str
    text: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FactualityCase:
    case_id: str
    dataset_identifier: str
    question: str
    category: str
    surface: FactualitySurface
    answer: str
    citations: tuple[CitationRecord, ...] = ()
    evidence: tuple[EvidenceRecord, ...] = ()
    experiment_analysis: dict[str, object] = field(default_factory=dict)
    business_impact: dict[str, object] = field(default_factory=dict)
    risk_assessment: dict[str, object] = field(default_factory=dict)
    decision: dict[str, object] = field(default_factory=dict)
    executive_summary: dict[str, object] = field(default_factory=dict)
    approval_status: str | None = None
    expected_min_citations: int = 0
    expected_failure_mode: str | None = None
    expected_decision_status: str | None = None
    expected_recommendation: str | None = None
    expected_summary_status: str | None = None
    expected_approval_status: str | None = None
    prompt_id: str | None = None
    prompt_version: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FactualityFinding:
    category: FindingCategory
    severity: Severity
    claim: str
    evidence: tuple[str, ...]
    source_ids: tuple[str, ...]
    confidence: float
    detector: str
    passed: bool
    explanation: str
    expected_evidence: tuple[str, ...] = ()
    structured_field_ids: tuple[str, ...] = ()
    normalized_claim: str = ""
    classification: FindingClassification = "true_positive"
    remediation_status: str = "action_required"
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FactualityCaseResult:
    case_id: str
    dataset_identifier: str
    category: str
    surface: FactualitySurface
    findings: tuple[FactualityFinding, ...]
    checks_executed: tuple[str, ...]
    skipped_checks: tuple[str, ...]
    citation_coverage: float
    unparsed_claims: bool
    prompt_id: str | None = None
    prompt_version: str | None = None

    @property
    def failed_findings(self) -> tuple[FactualityFinding, ...]:
        return tuple(finding for finding in self.findings if not finding.passed)


@dataclass(frozen=True)
class JudgeMetricResult:
    framework: str
    metric_name: str
    case_id: str
    surface: FactualitySurface
    score: float | None
    threshold: float | None
    passed: bool | None
    skipped: bool
    reason: str | None = None
    provider: str | None = None
    model: str | None = None


@dataclass(frozen=True)
class FactualityPolicy:
    critical_violations_allowed: int = 0
    unsupported_numerical_claims_allowed: int = 0
    fabricated_financial_claims_allowed: int = 0
    fabricated_statistical_claims_allowed: int = 0
    required_citation_coverage_minimum: float = 1.0
    max_unresolved_medium_severity_findings: int = 0
    judge_metric_thresholds: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class FactualityPolicyResult:
    status: PolicyStatus
    reasons: tuple[str, ...]
    finding_counts: dict[str, int]
    severity_counts: dict[str, int]


@dataclass(frozen=True)
class FactualityReport:
    generated_at: str
    target: FactualityTarget
    mode: FactualityMode
    dataset_identifiers: tuple[str, ...]
    case_results: tuple[FactualityCaseResult, ...]
    judge_metrics: tuple[JudgeMetricResult, ...]
    policy_result: FactualityPolicyResult
    judge_provider: str
    judge_model: str | None
    checks_executed: tuple[str, ...]
    checks_skipped: tuple[str, ...]
    findings_by_category: dict[str, int]
    findings_by_severity: dict[str, int]
    case_status_counts: dict[str, int]
    limitations: tuple[str, ...]

    @classmethod
    def build(
        cls,
        *,
        generated_at: str,
        target: FactualityTarget,
        mode: FactualityMode,
        dataset_identifiers: tuple[str, ...],
        case_results: tuple[FactualityCaseResult, ...],
        judge_metrics: tuple[JudgeMetricResult, ...],
        policy_result: FactualityPolicyResult,
        judge_provider: str,
        judge_model: str | None,
        limitations: tuple[str, ...],
    ) -> FactualityReport:
        executed: list[str] = []
        skipped: list[str] = []
        findings_by_category: Counter[str] = Counter()
        findings_by_severity: Counter[str] = Counter()
        case_status_counts: Counter[str] = Counter()

        for case_result in case_results:
            for check in case_result.checks_executed:
                if check not in executed:
                    executed.append(check)
            for check in case_result.skipped_checks:
                if check not in skipped:
                    skipped.append(check)
            for finding in case_result.failed_findings:
                findings_by_category[finding.category] += 1
                findings_by_severity[finding.severity] += 1
            case_status_counts[_case_status(case_result)] += 1

        for metric in judge_metrics:
            name = f"judge:{metric.framework}:{metric.metric_name}"
            if metric.skipped:
                if name not in skipped:
                    skipped.append(name)
            elif name not in executed:
                executed.append(name)

        return cls(
            generated_at=generated_at,
            target=target,
            mode=mode,
            dataset_identifiers=dataset_identifiers,
            case_results=case_results,
            judge_metrics=judge_metrics,
            policy_result=policy_result,
            judge_provider=judge_provider,
            judge_model=judge_model,
            checks_executed=tuple(executed),
            checks_skipped=tuple(skipped),
            findings_by_category=dict(sorted(findings_by_category.items())),
            findings_by_severity=dict(sorted(findings_by_severity.items())),
            case_status_counts=dict(sorted(case_status_counts.items())),
            limitations=limitations,
        )

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["findings_detail"] = [
            _finding_detail(case_result, finding)
            for case_result in self.case_results
            for finding in case_result.failed_findings
        ]
        return payload


def _case_status(case_result: FactualityCaseResult) -> PolicyStatus:
    failed_findings = case_result.failed_findings
    if not failed_findings and not case_result.unparsed_claims:
        return "pass"
    if any(finding.severity in {"high", "critical"} for finding in failed_findings):
        return "fail"
    if failed_findings or case_result.unparsed_claims:
        return "warning"
    return "skipped"


def _finding_detail(
    case_result: FactualityCaseResult,
    finding: FactualityFinding,
) -> dict[str, object]:
    return {
        "case_id": case_result.case_id,
        "surface": case_result.surface,
        "category": finding.category,
        "severity": finding.severity,
        "detector": finding.detector,
        "exact_flagged_claim": finding.claim,
        "normalized_claim": finding.normalized_claim,
        "expected_evidence": list(finding.expected_evidence),
        "available_evidence": list(finding.evidence),
        "source_ids": list(finding.source_ids),
        "structured_field_ids": list(finding.structured_field_ids),
        "explanation": finding.explanation,
        "classification": finding.classification,
        "remediation_status": finding.remediation_status,
    }
