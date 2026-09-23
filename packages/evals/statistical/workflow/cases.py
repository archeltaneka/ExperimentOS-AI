"""Strict workflow fixture loading and inventory validation."""

from pathlib import Path

from .models import AnalysisWorkflowCase

REQUIRED_CASE_IDS = frozenset(
    {
        "randomized",
        "did",
        "business",
        "insufficient",
        "optional_unavailable",
        "prose_conflict",
        "unsupported",
        "ambiguous",
        "missing-business-provenance",
        "negative",
        "cuped-success",
        "cuped-post-treatment",
        "bayesian-success",
        "bayesian-invalid-prior",
        "sequential-success",
        "sequential-invalid-plan",
        "did-invalid-timing",
        "propensity-success",
        "propensity-no-overlap",
        "ipw-ate-success",
        "ipw-att-success",
        "ipw-ate-no-overlap",
        "dml-success",
        "dml-post-treatment",
        "dml-degenerate",
        "hte-success",
        "hte-post-treatment",
        "hte-sparse",
        "business-negative",
        "business-cross-zero",
        "econml_dml-real",
        "econml_dml-absent",
        "econml_dml-broken",
        "econml_hte-real",
        "econml_hte-absent",
        "econml_hte-broken",
        "dowhy-real",
        "dowhy-absent",
        "dowhy-broken",
    }
)


def validate_case_inventory(
    cases: tuple[AnalysisWorkflowCase, ...], *, required_ids: frozenset[str] = frozenset()
) -> tuple[AnalysisWorkflowCase, ...]:
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate workflow case_id")
    if required_ids - set(ids):
        raise ValueError("missing required workflow cases")
    if not cases:
        raise ValueError("empty workflow case inventory")
    return tuple(sorted(cases, key=lambda case: case.case_id))


def read_cases(directory: Path) -> tuple[AnalysisWorkflowCase, ...]:
    try:
        cases = tuple(
            AnalysisWorkflowCase.model_validate_json(path.read_text(encoding="utf-8"))
            for path in sorted(directory.glob("*.json"))
        )
    except (ValueError, OSError):
        raise ValueError("invalid workflow case metadata") from None
    return validate_case_inventory(cases)
