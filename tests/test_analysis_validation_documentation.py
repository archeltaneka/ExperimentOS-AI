from __future__ import annotations

import json
import re
from pathlib import Path

from packages.evals.analysis_validation_cases import build_validation_golden_cases
from packages.experiments.analysis import (
    AnalysisEligibilityService,
    EligibilityValidationResult,
    eligibility_validation_result_from_json,
)

VALIDATION_GUIDE = Path("docs/phase4/statistical_input_validation.md")
ARCHITECTURE = Path("docs/architecture.md")
CANONICAL_EXAMPLES = (
    ("Fully eligible randomized analysis", "fully-eligible"),
    ("Eligible with warnings", "eligible-with-warnings"),
    ("Ineligible post-treatment leakage", "post-treatment-leakage"),
    ("Needs more data", "insufficient-total"),
    ("Estimator unavailable", "estimator-unavailable"),
)


def _example_payload(text: str, heading: str) -> dict[str, object]:
    match = re.search(
        rf"^### {re.escape(heading)}\s+.*?^```json\s+(.*?)^```$",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"missing JSON example under {heading!r}"
    payload = json.loads(match.group(1))
    assert isinstance(payload, dict)
    return payload


def _canonical_examples(text: str) -> dict[str, EligibilityValidationResult]:
    section = text.split("## Canonical structured-result examples", maxsplit=1)[1]
    section = section.split("## Limitations and out of scope", maxsplit=1)[0]
    json_blocks = re.findall(r"^```json\s+(.*?)^```$", section, flags=re.MULTILINE | re.DOTALL)
    assert len(json_blocks) == len(CANONICAL_EXAMPLES)

    return {
        case_id: eligibility_validation_result_from_json(
            json.dumps(_example_payload(section, heading))
        )
        for heading, case_id in CANONICAL_EXAMPLES
    }


def test_validation_documentation_covers_required_semantics() -> None:
    text = VALIDATION_GUIDE.read_text(encoding="utf-8")

    for phrase in (
        "Structural validation versus dataset eligibility",
        "eligible_with_warnings",
        "needs_more_data",
        "Diagnostic-code stability",
        "Estimator implementation availability",
        "Post-treatment leakage",
        "Operational thresholds are not statistical power",
        "Caller-data immutability",
        "Future estimator consumption",
        "Observability and data safety",
        "Payload boundary and exceptions",
        "Contract constructor validation",
        "Service-level cross-object request and capability consistency",
        "Table, data, and design rules determine dataset eligibility",
        "Outcome missingness threshold violations are blocking",
        "Differential missingness threshold violations are warnings",
    ):
        assert phrase in text

    for code_family in (
        "request.*",
        "schema.*",
        "missingness.*",
        "sample.*",
        "unit.*",
        "time.*",
        "segment.*",
        "method.*",
    ):
        assert code_family in text


def test_validation_documentation_has_five_structured_result_examples() -> None:
    text = VALIDATION_GUIDE.read_text(encoding="utf-8")
    documented = _canonical_examples(text)
    golden_cases = {
        case.case_id: case for case in build_validation_golden_cases() if case.case_id in documented
    }

    assert set(documented) == set(golden_cases)
    for case_id, documented_result in documented.items():
        case = golden_cases[case_id]
        service = AnalysisEligibilityService(
            policy=case.policy,
            capability_registry=case.capability_registry,
            configuration_provenance=f"golden-case:{case.case_id}",
        )
        if case.request is not None:
            evaluated_result = service.validate(case.request, case.table, case.binding)
        else:
            assert case.request_payload is not None
            evaluated_result = service.validate_payload(
                case.request_payload,
                case.table,
                case.binding,
            )

        assert documented_result.model_dump(mode="json") == evaluated_result.model_dump(mode="json")


def test_architecture_documents_validation_dependency_direction() -> None:
    text = ARCHITECTURE.read_text(encoding="utf-8")

    assert "docs/phase4/statistical_input_validation.md" in text
    assert "AnalysisEligibilityService" in text
    assert "request rules, data rules, and design rules" in text
    assert "has no FastAPI or vendor SDK dependency" in text
