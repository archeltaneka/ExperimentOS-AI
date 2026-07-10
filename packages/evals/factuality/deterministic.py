from __future__ import annotations

import re
from collections.abc import Iterable

from packages.evals.factuality.models import (
    EvidenceRecord,
    FactualityCase,
    FactualityCaseResult,
    FactualityFinding,
)

_ABSTENTION_MARKERS = (
    "insufficient evidence",
    "cannot determine",
    "cannot be determined",
    "cannot estimate",
    "cannot be claimed",
    "cannot be concluded",
    "need more data",
    "needs more data",
    "unsupported",
    "directional",
    "incomplete",
    "cannot conclude",
    "cannot claim",
    "does not support",
    "not support making definitive claims",
    "not appropriate to claim",
    "no grounded",
    "no explicit",
    "not approved",
    "not ready",
    "unavailable",
)
_FINANCIAL_KEYWORDS = ("roi", "revenue", "profit", "annualized", "usd", "$")
_STATISTICAL_KEYWORDS = (
    "statistically significant",
    "p-value",
    "p value",
    "confidence interval",
    "sample size",
    "n=",
)
_ROLLOUT_TERMS = ("roll out", "rollout", "launch", "ship", "approved")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "with",
}
_NUMBER_PATTERN = re.compile(r"(?P<number>[-+]?\d[\d,]*(?:\.\d+)?)")
_CURRENCY_AMOUNT_PATTERN = re.compile(
    r"(?:USD|AUD|GBP|EUR|JPY|SGD)\s*\$?(?P<number>[-+]?\d[\d,]*(?:\.\d+)?)|\$(?P<dollar>[-+]?\d[\d,]*(?:\.\d+)?)",
    re.IGNORECASE,
)
_ANNUALIZED_AMOUNT_PATTERN = re.compile(
    r"annualized[^\d$A-Z]{0,24}(?:impact|revenue|lift|savings)?[^\d$A-Z]{0,24}"
    r"(?:USD|AUD|GBP|EUR|JPY|SGD)?\s*\$?(?P<number>[-+]?\d[\d,]*(?:\.\d+)?)",
    re.IGNORECASE,
)
_ROI_PATTERN = re.compile(
    r"(?P<number>[-+]?\d[\d,]*(?:\.\d+)?)\s*(?:%|percent)\s+roi",
    re.IGNORECASE,
)


def evaluate_case(case: FactualityCase) -> FactualityCaseResult:
    findings: list[FactualityFinding] = []
    checks_executed = [
        "citation_presence",
        "citation_support",
        "numerical_grounding",
        "financial_guardrails",
        "statistical_validation",
        "abstention_correctness",
        "structured_consistency",
        "evidence_coverage",
    ]
    skipped_checks: list[str] = []
    claims = _extract_claims(case)
    unparsed_claims = False
    if (not claims and case.answer.strip()) or _claims_are_non_specific(claims):
        unparsed_claims = True
        skipped_checks.append("claim_extraction")

    findings.extend(_check_citation_presence(case))
    findings.extend(_check_citation_support(case))
    findings.extend(_check_numerical_grounding(case, claims))
    findings.extend(_check_financial_claims(case, claims))
    findings.extend(_check_statistical_claims(case, claims))
    findings.extend(_check_abstention(case, claims))
    findings.extend(_check_structured_consistency(case))
    findings.extend(_check_evidence_coverage(case, claims))
    findings = _deduplicate_findings(findings)

    expected_citations = max(case.expected_min_citations, 0)
    citation_coverage = 1.0
    if expected_citations > 0:
        citation_coverage = min(len(case.citations) / expected_citations, 1.0)

    return FactualityCaseResult(
        case_id=case.case_id,
        dataset_identifier=case.dataset_identifier,
        category=case.category,
        surface=case.surface,
        findings=tuple(findings),
        checks_executed=tuple(checks_executed),
        skipped_checks=tuple(skipped_checks),
        citation_coverage=citation_coverage,
        unparsed_claims=unparsed_claims,
        prompt_id=case.prompt_id,
        prompt_version=case.prompt_version,
    )


def _check_citation_presence(case: FactualityCase) -> list[FactualityFinding]:
    if len(case.citations) >= max(case.expected_min_citations, 0):
        return []
    return [
        _finding(
            category="citation_missing",
            severity="high",
            claim="Required citations were missing from the evaluated output.",
            evidence=(),
            source_ids=(),
            detector="deterministic.citation_presence",
            explanation=(
                f"Expected at least {case.expected_min_citations} citations, found "
                f"{len(case.citations)}."
            ),
            expected_evidence=(f"expected_min_citations={case.expected_min_citations}",),
            remediation_status="add_or_propagate_citations",
        )
    ]


def _check_citation_support(case: FactualityCase) -> list[FactualityFinding]:
    evidence_ids = {record.source_id for record in case.evidence}
    findings: list[FactualityFinding] = []
    for citation in case.citations:
        if citation.source_id not in evidence_ids:
            findings.append(
                _finding(
                    category="citation_does_not_support_claim",
                    severity="high",
                    claim=f"Citation `{citation.source_id}` does not exist in retrieved evidence.",
                    evidence=tuple(record.text for record in case.evidence),
                    source_ids=(citation.source_id,),
                    detector="deterministic.citation_support",
                    explanation="The cited identifier was absent from the retrieved evidence set.",
                    expected_evidence=tuple(record.source_id for record in case.evidence),
                    remediation_status="fix_citation_source_mapping",
                )
            )
    return findings


def _check_numerical_grounding(
    case: FactualityCase,
    claims: list[str],
) -> list[FactualityFinding]:
    findings: list[FactualityFinding] = []
    supported_values = tuple(_numeric_values_from_case(case))
    expected_evidence, structured_field_ids = _structured_expectations(
        case,
        (
            "experiment_analysis.treatment_control_comparison.control_value",
            "experiment_analysis.treatment_control_comparison.treatment_value",
            "experiment_analysis.treatment_control_comparison.absolute_delta",
            "experiment_analysis.treatment_control_comparison.relative_lift",
            "business_impact.baseline_value",
            "business_impact.treatment_value",
            "business_impact.absolute_lift",
            "business_impact.relative_lift",
            "risk_assessment.risk_factors_count",
        ),
    )
    if not supported_values:
        return findings
    for claim in claims:
        if not _contains_digits(claim):
            continue
        if _contains_any(claim, _FINANCIAL_KEYWORDS) or _contains_any(claim, _STATISTICAL_KEYWORDS):
            continue
        values = _extract_numbers(claim)
        if not values:
            continue
        unsupported = [
            value
            for value in values
            if not any(_numbers_match(value, supported) for supported in supported_values)
        ]
        if not unsupported:
            continue
        findings.append(
            _finding(
                category="unsupported_numerical_claim",
                severity="high",
                claim=claim,
                evidence=_evidence_preview(case.evidence),
                source_ids=tuple(record.source_id for record in case.evidence),
                detector="deterministic.numerical_grounding",
                explanation=(
                    "At least one numerical claim was absent from the structured experiment "
                    "data and retrieved evidence."
                ),
                expected_evidence=expected_evidence,
                structured_field_ids=structured_field_ids,
                metadata={"unsupported_values": unsupported},
                remediation_status="fix_output_or_numeric_parsing",
            )
        )
        if _contains_any(
            claim,
            ("control", "treatment", "metric", "improved", "declined", "increased"),
        ):
            findings.append(
                _finding(
                    category="fabricated_experiment_result",
                    severity="high",
                    claim=claim,
                    evidence=_evidence_preview(case.evidence),
                    source_ids=tuple(record.source_id for record in case.evidence),
                    detector="deterministic.numerical_grounding",
                    explanation=(
                        "The answer asserted an experiment result value that was absent from the "
                        "structured experiment evidence."
                    ),
                    expected_evidence=expected_evidence,
                    structured_field_ids=structured_field_ids,
                    metadata={"unsupported_values": unsupported},
                    remediation_status="fix_output_or_numeric_parsing",
                )
            )
    return findings


def _check_financial_claims(case: FactualityCase, claims: list[str]) -> list[FactualityFinding]:
    findings: list[FactualityFinding] = []
    supported_values = _supported_financial_values(case)
    expected_evidence, structured_field_ids = _structured_expectations(
        case,
        (
            "business_impact.estimated_annualized_impact.amount",
            "business_impact.estimated_annualized_impact.currency",
            "business_impact.impact_status",
        ),
    )
    for claim in claims:
        if not _has_explicit_financial_claim(claim):
            continue
        if _is_abstaining_claim(claim):
            continue
        values = _extract_financial_numbers(claim)
        if not supported_values:
            findings.append(
                _finding(
                    category="fabricated_revenue_or_roi",
                    severity="critical",
                    claim=claim,
                    evidence=_evidence_preview(case.evidence),
                    source_ids=tuple(record.source_id for record in case.evidence),
                    detector="deterministic.financial_guardrails",
                    explanation=(
                        "Financial impact was claimed without supported revenue, ROI, or "
                        "annualized impact inputs."
                    ),
                    expected_evidence=expected_evidence,
                    structured_field_ids=structured_field_ids,
                    remediation_status="fix_output_or_financial_grounding",
                )
            )
            continue
        if values and not all(
            any(_numbers_match(value, supported) for supported in supported_values)
            for value in values
        ):
            findings.append(
                _finding(
                    category="fabricated_revenue_or_roi",
                    severity="critical",
                    claim=claim,
                    evidence=_evidence_preview(case.evidence),
                    source_ids=tuple(record.source_id for record in case.evidence),
                    detector="deterministic.financial_guardrails",
                    explanation=(
                        "Financial amounts in the answer did not match the grounded business "
                        "impact inputs."
                    ),
                    expected_evidence=expected_evidence,
                    structured_field_ids=structured_field_ids,
                    remediation_status="fix_output_or_financial_grounding",
                )
            )
    return findings


def _check_statistical_claims(case: FactualityCase, claims: list[str]) -> list[FactualityFinding]:
    findings: list[FactualityFinding] = []
    significance = case.experiment_analysis.get("statistical_significance", {})
    is_significant = (
        bool(significance.get("is_significant"))
        if isinstance(significance, dict)
        else False
    )
    supported_p_value = _first_numeric(
        significance.get("p_value") if isinstance(significance, dict) else None
    )
    expected_evidence, structured_field_ids = _structured_expectations(
        case,
        (
            "experiment_analysis.statistical_significance.is_significant",
            "experiment_analysis.statistical_significance.p_value",
        ),
    )
    for claim in claims:
        normalized = claim.lower()
        if _is_abstaining_claim(claim):
            continue
        has_significance_assertion = "statistically significant" in normalized
        has_p_value_assertion = bool(re.search(r"p[- ]value[^\d]{0,6}[-+]?\d", normalized))
        has_confidence_interval_assertion = (
            bool(re.search(r"confidence interval[^\d]{0,12}[-+]?\d", normalized))
        )
        has_sample_size_assertion = (
            bool(re.search(r"sample size[^\d]{0,12}[-+]?\d", normalized))
            or "n=" in normalized
        )
        if not any(
            (
                has_significance_assertion,
                has_p_value_assertion,
                has_confidence_interval_assertion,
                has_sample_size_assertion,
            )
        ):
            continue
        values = _extract_numbers(claim)
        if has_significance_assertion and not is_significant:
            findings.append(
                _finding(
                    category="fabricated_statistical_significance",
                    severity="critical",
                    claim=claim,
                    evidence=_evidence_preview(case.evidence),
                    source_ids=tuple(record.source_id for record in case.evidence),
                    detector="deterministic.statistical_validation",
                    explanation="The answer claimed significance without grounded support.",
                    expected_evidence=expected_evidence,
                    structured_field_ids=structured_field_ids,
                    remediation_status="fix_output_or_statistical_grounding",
                )
            )
            continue
        if has_p_value_assertion:
            if supported_p_value is None or not values:
                findings.append(
                    _finding(
                        category="fabricated_statistical_significance",
                        severity="critical",
                        claim=claim,
                        evidence=_evidence_preview(case.evidence),
                        source_ids=tuple(record.source_id for record in case.evidence),
                        detector="deterministic.statistical_validation",
                        explanation="A p-value was claimed without grounded statistical evidence.",
                        expected_evidence=expected_evidence,
                        structured_field_ids=structured_field_ids,
                        remediation_status="fix_output_or_statistical_grounding",
                    )
                )
                continue
            if not all(_numbers_match(value, supported_p_value) for value in values):
                findings.append(
                    _finding(
                        category="fabricated_statistical_significance",
                        severity="critical",
                        claim=claim,
                        evidence=_evidence_preview(case.evidence),
                        source_ids=tuple(record.source_id for record in case.evidence),
                        detector="deterministic.statistical_validation",
                        explanation="The claimed p-value did not match the structured evidence.",
                        expected_evidence=expected_evidence,
                        structured_field_ids=structured_field_ids,
                        remediation_status="fix_output_or_statistical_grounding",
                    )
                )
        if has_confidence_interval_assertion or has_sample_size_assertion:
            findings.append(
                _finding(
                    category="fabricated_statistical_significance",
                    severity="critical",
                    claim=claim,
                    evidence=_evidence_preview(case.evidence),
                    source_ids=tuple(record.source_id for record in case.evidence),
                    detector="deterministic.statistical_validation",
                    explanation=(
                        "Confidence intervals and sample sizes are not grounded by the current "
                        "structured evidence surface."
                    ),
                    expected_evidence=expected_evidence,
                    structured_field_ids=structured_field_ids,
                    remediation_status="fix_output_or_statistical_grounding",
                )
            )
    return findings


def _check_abstention(case: FactualityCase, claims: list[str]) -> list[FactualityFinding]:
    needs_abstention = bool(
        case.expected_failure_mode
        or case.expected_decision_status in {"needs_more_data", "insufficient_data"}
        or case.expected_recommendation == "needs_more_data"
        or case.business_impact.get("impact_status") == "insufficient_data"
        or case.decision.get("decision_status") in {"needs_more_data", "insufficient_data"}
    )
    if not needs_abstention:
        return []

    public_output = " ".join(
        part.lower()
        for part in (
            case.answer,
            str(case.executive_summary.get("summary", "")),
            str(case.executive_summary.get("decision_rationale", "")),
        )
        if str(part).strip()
    )
    if _contains_abstention_marker(public_output):
        return []

    findings = [
        _finding(
            category="answer_generated_when_abstention_was_expected",
            severity="high",
            claim=case.answer,
            evidence=_evidence_preview(case.evidence),
            source_ids=tuple(record.source_id for record in case.evidence),
            detector="deterministic.abstention",
            explanation=(
                "This case expected a needs-more-data or insufficient-evidence outcome, but the "
                "answer remained assertive."
            ),
            expected_evidence=_structured_evidence(case),
            remediation_status="strengthen_abstention_behavior",
        )
    ]
    if _looks_confident(public_output):
        findings.append(
            _finding(
                category="overconfident_answer_with_insufficient_evidence",
                severity="high",
                claim=case.answer,
                evidence=_evidence_preview(case.evidence),
                source_ids=tuple(record.source_id for record in case.evidence),
                detector="deterministic.abstention",
                explanation="The answer was overly confident relative to the available evidence.",
                expected_evidence=_structured_evidence(case),
                remediation_status="strengthen_abstention_behavior",
            )
        )
    return findings


def _check_structured_consistency(case: FactualityCase) -> list[FactualityFinding]:
    findings: list[FactualityFinding] = []
    recommendation = str(case.decision.get("recommendation", "")).strip().lower()
    public_answer = " ".join(
        part.lower()
        for part in (
            case.answer,
            str(case.executive_summary.get("summary", "")),
            str(case.executive_summary.get("decision_rationale", "")),
        )
        if str(part).strip()
    )
    if recommendation == "do_not_rollout" and _looks_like_rollout_endorsement(public_answer):
        findings.append(
            _finding(
                category="contradiction_with_structured_experiment_data",
                severity="critical",
                claim=case.answer,
                evidence=_structured_evidence(case),
                source_ids=tuple(record.source_id for record in case.evidence),
                detector="deterministic.structured_consistency",
                explanation=(
                    "The final answer or summary contradicted the structured decision "
                    "recommendation."
                ),
                expected_evidence=_structured_evidence(case),
                structured_field_ids=("decision.recommendation", "decision.rationale"),
                remediation_status="fix_output_consistency",
            )
        )
    approval_status = (case.approval_status or "").strip().lower()
    if approval_status == "rejected" and (
        _contains_positive_approval_language(public_answer)
        or _looks_like_rollout_endorsement(public_answer)
    ):
        findings.append(
            _finding(
                category="contradiction_with_structured_experiment_data",
                severity="critical",
                claim=case.answer,
                evidence=_structured_evidence(case),
                source_ids=tuple(record.source_id for record in case.evidence),
                detector="deterministic.structured_consistency",
                explanation="The output contradicted the recorded human approval state.",
                expected_evidence=_structured_evidence(case),
                structured_field_ids=("approval_status", "executive_summary.summary"),
                remediation_status="fix_output_consistency",
            )
        )
    return findings


def _check_evidence_coverage(case: FactualityCase, claims: list[str]) -> list[FactualityFinding]:
    evidence_text = _support_text(case)
    findings: list[FactualityFinding] = []
    for claim in claims:
        normalized = claim.lower()
        if _contains_digits(normalized) or _contains_any(normalized, _FINANCIAL_KEYWORDS):
            continue
        tokens = [
            token
            for token in re.findall(r"[a-z]{4,}", normalized)
            if token not in _STOPWORDS
        ]
        if len(tokens) < 2:
            continue
        matched = sum(1 for token in tokens if token in evidence_text)
        if matched == 0 and _contains_any(normalized, _ROLLOUT_TERMS):
            findings.append(
                _finding(
                    category="unsupported_factual_claim",
                    severity="medium",
                    claim=claim,
                    evidence=_evidence_preview(case.evidence),
                    source_ids=tuple(record.source_id for record in case.evidence),
                    detector="deterministic.evidence_coverage",
                    explanation=(
                        "The answer made a factual recommendation that did not have token-level "
                        "support in the retrieved evidence."
                    ),
                    expected_evidence=_structured_evidence(case),
                    structured_field_ids=(
                        "decision.recommendation",
                        "decision.rationale",
                        "approval_status",
                        "risk_assessment.overall_risk_level",
                    ),
                    remediation_status="fix_output_or_support_mapping",
                )
            )
    return findings


def _extract_claims(case: FactualityCase) -> list[str]:
    candidates = [
        case.answer,
        str(case.decision.get("rationale", "")),
        str(case.executive_summary.get("summary", "")),
    ]
    claims: list[str] = []
    for candidate in candidates:
        for segment in re.split(r"(?<!\d)[.!?]+(?!\d)|\n+", candidate):
            normalized = segment.strip()
            if len(normalized.split()) < 3:
                continue
            if normalized not in claims:
                claims.append(normalized)
    return claims


def _claims_are_non_specific(claims: list[str]) -> bool:
    if not claims:
        return False
    return all(
        not _contains_digits(claim)
        and not _contains_metric_like_token(claim)
        and not _contains_any(claim, _FINANCIAL_KEYWORDS)
        and not _contains_any(claim, _STATISTICAL_KEYWORDS)
        and not _contains_any(claim, _ROLLOUT_TERMS)
        for claim in claims
    )


def _supported_financial_values(case: FactualityCase) -> tuple[float, ...]:
    values: list[float] = []
    values.extend(
        _extract_numeric_from_object(case.business_impact.get("estimated_annualized_impact"))
    )
    for record in case.evidence:
        values.extend(_extract_numeric_from_object(record.metadata.get("estimated_annualized_impact")))
    return tuple(values)


def _numeric_values_from_case(case: FactualityCase) -> list[float]:
    values: list[float] = []
    for payload in (
        case.experiment_analysis,
        case.business_impact,
        case.risk_assessment,
        case.decision,
        case.executive_summary,
    ):
        values.extend(_extract_numeric_from_object(payload))
    risk_factors = case.risk_assessment.get("risk_factors")
    if isinstance(risk_factors, list):
        values.append(float(len(risk_factors)))
    return values


def _extract_numeric_from_object(value: object) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, dict):
        collected: list[float] = []
        for nested in value.values():
            collected.extend(_extract_numeric_from_object(nested))
        return collected
    if isinstance(value, list):
        collected: list[float] = []
        for nested in value:
            collected.extend(_extract_numeric_from_object(nested))
        return collected
    return []


def _first_numeric(value: object) -> float | None:
    extracted = _extract_numeric_from_object(value)
    return extracted[0] if extracted else None


def _extract_numbers(text: str) -> list[float]:
    numbers: list[float] = []
    for match in _NUMBER_PATTERN.finditer(text):
        try:
            numbers.append(float(match.group("number").replace(",", "")))
        except ValueError:
            continue
    return numbers


def _extract_financial_numbers(text: str) -> list[float]:
    values: list[float] = []
    for pattern in (_CURRENCY_AMOUNT_PATTERN, _ANNUALIZED_AMOUNT_PATTERN, _ROI_PATTERN):
        for match in pattern.finditer(text):
            raw = match.groupdict().get("number") or match.groupdict().get("dollar")
            if not raw:
                continue
            try:
                values.append(float(raw.replace(",", "")))
            except ValueError:
                continue
    return values


def _numbers_match(left: float, right: float, tolerance: float = 0.02) -> bool:
    if left == right:
        return True
    if right != 0 and abs((left - right) / right) <= tolerance:
        return True
    if abs(left) > 1.0 and abs(right) < 1.0 and abs((left / 100.0) - right) <= tolerance:
        return True
    if abs(right) > 1.0 and abs(left) < 1.0 and abs(left - (right / 100.0)) <= tolerance:
        return True
    return abs(left - right) <= tolerance


def _contains_digits(text: str) -> bool:
    return any(character.isdigit() for character in text)


def _contains_any(text: str, fragments: Iterable[str]) -> bool:
    normalized = text.lower()
    return any(fragment in normalized for fragment in fragments)


def _contains_metric_like_token(text: str) -> bool:
    return bool(re.search(r"\b[a-z]+(?:_[a-z]+)+\b", text.lower()))


def _looks_like_rollout_endorsement(text: str) -> bool:
    normalized = text.lower()
    if (
        "do not roll out" in normalized
        or "needs more data" in normalized
        or "not approved" in normalized
    ):
        return False
    return _contains_any(normalized, _ROLLOUT_TERMS)


def _looks_confident(text: str) -> bool:
    normalized = text.lower()
    if _contains_abstention_marker(normalized):
        return False
    return _looks_like_rollout_endorsement(normalized) or _contains_any(
        normalized,
        ("clear", "definitive", "proves", "certain", "significant"),
    )


def _combined_text(case: FactualityCase) -> str:
    return " ".join(
        part.lower()
        for part in (
            case.answer,
            str(case.decision.get("rationale", "")),
            str(case.executive_summary.get("summary", "")),
        )
        if str(part).strip()
    )


def _structured_evidence(case: FactualityCase) -> tuple[str, ...]:
    fragments = [
        str(case.decision.get("rationale", "")).strip(),
        str(case.executive_summary.get("decision_rationale", "")).strip(),
        str(case.executive_summary.get("summary", "")).strip(),
        str(case.business_impact.get("summary", "")).strip(),
        str(case.experiment_analysis.get("summary", "")).strip(),
        str(case.approval_status or "").strip(),
    ]
    return tuple(fragment for fragment in fragments if fragment)


def _support_text(case: FactualityCase) -> str:
    fragments = [record.text.lower() for record in case.evidence]
    fragments.extend(_flatten_strings(case.experiment_analysis))
    fragments.extend(_flatten_strings(case.business_impact))
    fragments.extend(_flatten_strings(case.risk_assessment))
    fragments.extend(_flatten_strings(case.decision))
    fragments.extend(_flatten_strings(case.executive_summary))
    if case.approval_status:
        fragments.append(str(case.approval_status).lower())
    return " ".join(fragment for fragment in fragments if fragment)


def _flatten_strings(value: object) -> list[str]:
    if isinstance(value, str):
        normalized = value.strip().lower()
        return [normalized] if normalized else []
    if isinstance(value, dict):
        flattened: list[str] = []
        for nested in value.values():
            flattened.extend(_flatten_strings(nested))
        return flattened
    if isinstance(value, list):
        flattened: list[str] = []
        for nested in value:
            flattened.extend(_flatten_strings(nested))
        return flattened
    return []


def _contains_abstention_marker(text: str) -> bool:
    normalized = text.lower()
    return any(marker in normalized for marker in _ABSTENTION_MARKERS)


def _is_abstaining_claim(claim: str) -> bool:
    normalized = claim.lower()
    return _contains_abstention_marker(normalized) or (
        "no " in normalized and ("p-value" in normalized or "roi" in normalized)
    ) or (
        "does not provide" in normalized
        and any(
            phrase in normalized
            for phrase in ("roi", "statistical significance", "definitive proof")
        )
    )


def _has_explicit_financial_claim(claim: str) -> bool:
    normalized = claim.lower()
    sanitized = normalized.replace("revenue_per_user", "")
    return bool(
        re.search(r"\broi\b", sanitized)
        or re.search(r"\brevenue\b", sanitized)
        or re.search(r"\bprofit\b", sanitized)
        or "annualized" in sanitized
        or any(currency in claim for currency in ("$", "USD", "AUD", "GBP", "EUR", "JPY", "SGD"))
    )


def _contains_positive_approval_language(text: str) -> bool:
    normalized = text.lower()
    if any(
        phrase in normalized
        for phrase in ("not approved", "awaiting approval", "revision requested")
    ):
        return False
    return "approved" in normalized


def _structured_expectations(
    case: FactualityCase,
    field_paths: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    expected: list[str] = []
    available_paths: list[str] = []
    for field_path in field_paths:
        value = _resolve_field_path(case, field_path)
        if value in (None, "", [], {}):
            continue
        available_paths.append(field_path)
        expected.append(f"{field_path}={value}")
    return tuple(expected), tuple(available_paths)


def _resolve_field_path(case: FactualityCase, field_path: str) -> object:
    parts = field_path.split(".")
    current: object = case
    for index, part in enumerate(parts):
        if index == 0:
            if hasattr(case, part):
                current = getattr(case, part)
                continue
            return None
        if part == "risk_factors_count" and isinstance(current, dict):
            risk_factors = current.get("risk_factors")
            return len(risk_factors) if isinstance(risk_factors, list) else None
        if isinstance(current, dict):
            current = current.get(part)
            continue
        return None
    return current


def _evidence_preview(records: tuple[EvidenceRecord, ...], limit: int = 2) -> tuple[str, ...]:
    return tuple(record.text for record in records[:limit])


def _finding(
    *,
    category,
    severity,
    claim,
    evidence,
    source_ids,
    detector,
    explanation,
    metadata: dict[str, object] | None = None,
    expected_evidence: tuple[str, ...] = (),
    structured_field_ids: tuple[str, ...] = (),
    classification: str = "true_positive",
    remediation_status: str = "action_required",
) -> FactualityFinding:
    return FactualityFinding(
        category=category,
        severity=severity,
        claim=claim,
        evidence=tuple(evidence),
        source_ids=tuple(source_ids),
        confidence=0.95,
        detector=detector,
        passed=False,
        explanation=explanation,
        expected_evidence=tuple(expected_evidence),
        structured_field_ids=tuple(structured_field_ids),
        normalized_claim=_normalize_claim(claim),
        classification=classification,
        remediation_status=remediation_status,
        metadata=metadata or {},
    )


def _deduplicate_findings(findings: list[FactualityFinding]) -> list[FactualityFinding]:
    deduplicated: list[FactualityFinding] = []
    seen: set[tuple[str, str, str]] = set()
    for finding in findings:
        key = (finding.category, finding.claim, finding.detector)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(finding)
    return deduplicated


def _normalize_claim(claim: str) -> str:
    return " ".join(claim.lower().split())
