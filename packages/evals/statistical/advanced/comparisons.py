"""Reference comparisons gated on explicit matching causal semantics."""

from __future__ import annotations

from packages.experiments.analysis.causal.advanced.conformance import canonical_digest

from ..models import CheckStatus
from .checks import check, compare_effects
from .fixtures import prepare_case


def signature(case):
    request, _, _ = prepare_case(case)
    source = request.identification_result

    def digest(model):
        return (
            canonical_digest(model.model_dump(mode="json", exclude={"provenance", "evidence"}))
            if model
            else None
        )

    return {
        "estimand": source.estimand.estimand_type.value if source.estimand else None,
        "contrast": digest(source.treatment),
        "population": digest(source.estimand.target_population) if source.estimand else None,
        "outcome": digest(source.outcome),
        "covariates": tuple(source.identification_request.covariates),
        "assumptions": tuple(
            (a.code.value, a.status.value, a.applicability.value) for a in source.assumptions
        ),
        "fixture": (
            "subgroup-v1" if "hte" in case.advanced.capability_id else "constant-effect-linear-v1",
            case.advanced.scenario,
        ),
        "subgroups": digest(getattr(request, "modifier", None)) or "not_applicable",
    }


def attach_comparisons(cases, results):
    by_id = {c.case_id: c for c in cases}
    by_result = {r.case_id: r for r in results}
    updated = []
    for result in results:
        if result.case_id not in {"advanced-econml_dml-success", "advanced-econml_hte-success"}:
            updated.append(result)
            continue
        baseline_id = result.case_id.replace("econml_", "repository_")
        baseline = by_result.get(baseline_id)
        comparisons = []
        if (
            baseline is None
            or result.actual_status != "completed"
            or baseline.actual_status != "completed"
        ):
            comparisons.append(
                check(
                    "comparison",
                    "comparison",
                    True,
                    status=CheckStatus.SKIPPED,
                    message="NOT_APPLICABLE: both compatible estimators "
                    "must have successful evidence.",
                )
            )
        else:
            paths = [e.path for e in by_id[result.case_id].expected_values]
            for path in paths:
                left = next((c.actual for c in baseline.checks if c.check_id == path), None)
                right = next((c.actual for c in result.checks if c.check_id == path), None)
                if left is None or right is None:
                    comparisons.append(
                        check(
                            "comparison",
                            "comparison",
                            True,
                            status=CheckStatus.SKIPPED,
                            message="NOT_APPLICABLE: missing aggregate comparison evidence.",
                        )
                    )
                else:
                    comparisons.append(
                        compare_effects(
                            signature(by_id[baseline_id]),
                            signature(by_id[result.case_id]),
                            left,
                            right,
                        )
                    )
        advisories = tuple(c.rule_id for c in comparisons if c.status is CheckStatus.ADVISORY)
        skipped = tuple(c for c in comparisons if c.status is CheckStatus.SKIPPED)
        updated.append(
            result.model_copy(
                update={
                    "checks": (*result.checks, *comparisons),
                    "advisory_findings": (*result.advisory_findings, *advisories),
                    "skipped_checks": (*result.skipped_checks, *(c.check_id for c in skipped)),
                    "skip_reasons": (*result.skip_reasons, *(c.message for c in skipped)),
                    "evaluation_status": CheckStatus.ADVISORY
                    if advisories and result.evaluation_status is CheckStatus.PASS
                    else result.evaluation_status,
                }
            )
        )
    return tuple(updated)
