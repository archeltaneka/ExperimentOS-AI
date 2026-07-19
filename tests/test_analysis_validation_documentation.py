from __future__ import annotations

import json
import re
from pathlib import Path

VALIDATION_GUIDE = Path("docs/phase4/statistical_input_validation.md")
ARCHITECTURE = Path("docs/architecture.md")


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
    expected = {
        "Fully eligible randomized analysis": ("eligible", (), "available", True),
        "Eligible with warnings": (
            "eligible_with_warnings",
            ("sample.total_weak", "sample.arm_weak"),
            "available",
            True,
        ),
        "Ineligible post-treatment leakage": (
            "ineligible",
            ("covariate.post_treatment_leakage",),
            "available",
            False,
        ),
        "Needs more data": (
            "needs_more_data",
            ("sample.total_insufficient",),
            "available",
            False,
        ),
        "Estimator unavailable": (
            "ineligible",
            ("method.implementation_unavailable",),
            "unavailable",
            True,
        ),
    }

    for heading, (status, codes, implementation_status, data_eligible) in expected.items():
        payload = _example_payload(text, heading)
        diagnostics = payload["diagnostics"]
        method_support = payload["method_support"]
        assert isinstance(diagnostics, list)
        assert isinstance(method_support, dict)
        assert payload["outcome_type"] == "eligibility_validation"
        assert payload["validation_version"] == "1"
        assert payload["status"] == status
        assert tuple(item["code"] for item in diagnostics) == codes
        assert method_support["contract_status"] == "supported"
        assert method_support["implementation_status"] == implementation_status
        assert method_support["data_eligible"] is data_eligible
        assert "estimate" not in payload


def test_architecture_documents_validation_dependency_direction() -> None:
    text = ARCHITECTURE.read_text(encoding="utf-8")

    assert "docs/phase4/statistical_input_validation.md" in text
    assert "AnalysisEligibilityService" in text
    assert "request rules, data rules, and design rules" in text
    assert "has no FastAPI or vendor SDK dependency" in text
