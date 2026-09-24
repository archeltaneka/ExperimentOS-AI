"""Validate native report completeness without executing estimators at ingestion."""

import hashlib
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

from .advanced.registry import REGISTRY
from .dataset import DEFAULT_STATISTICAL_DATASET_PATH, load_statistical_reference_cases


@lru_cache(maxsize=1)
def _inventory():
    root = Path(__file__).resolve().parents[3]
    cases = load_statistical_reference_cases(root / DEFAULT_STATISTICAL_DATASET_PATH).cases
    contracts = json.loads(Path(__file__).with_name("native_check_inventory.json").read_text())
    if contracts["schema_version"] != 1 or set(contracts["cases"]) != {c.case_id for c in cases}:
        raise ValueError("invalid native check inventory")
    return {c.case_id: c for c in cases}, contracts["cases"]


def native_integrity_metrics(report):
    """Recompute counters and bind required cases/checks to versioned fixtures."""
    cases, contracts = _inventory()
    required = {
        identity
        for identity, case in cases.items()
        if report.scope == "complete"
        or (case.advanced and REGISTRY[case.advanced.capability_id].dependency)
    }
    seen = Counter(r.case_id for r in report.case_results)
    failures = len(required - seen.keys()) + len(seen.keys() - required)
    failures += sum(count - 1 for count in seen.values())
    statuses = Counter()
    capabilities = {}
    for result in report.case_results:
        checks = result.checks
        status = (
            "fail"
            if any(c.status == "fail" for c in checks)
            else "skipped"
            if result.category == "skipped"
            else "advisory"
            if any(c.status == "advisory" for c in checks)
            else "skipped"
            if checks and all(c.status == "skipped" for c in checks)
            else "pass"
        )
        statuses[status] += 1
        counts = capabilities.setdefault(result.capability, Counter())
        counts[status] += 1
        counts["cases"] += 1
        failures += result.evaluation_status != status
        failures += result.passed != (status in {"pass", "advisory"})
        case = cases.get(result.case_id)
        if case is None:
            continue
        failures += (
            result.capability,
            result.category,
            result.design,
            result.estimand,
            result.method,
            result.target_population,
            result.expected_status,
        ) != (
            case.capability,
            case.category,
            case.analysis_design,
            case.estimand,
            case.method,
            case.target_population,
            case.expected_status,
        )
        failures += (result.advanced is None) != (case.advanced is None)
        variant = "available"
        if case.advanced and result.advanced:
            cap = REGISTRY[case.advanced.capability_id]
            controlled = case.advanced.dependency_expectation == "controlled"
            state = result.advanced.dependency_state
            allowed = (
                {"controlled"}
                if controlled
                else {"installed", "unavailable", "broken"}
                if cap.dependency
                else {"not_required"}
            )
            failures += state not in allowed
            failures += result.advanced.capability_id != case.advanced.capability_id
            failures += result.advanced.dependency_package != cap.dependency
            if state == "unavailable" and cap.dependency and not controlled:
                variant = "unavailable"
                failures += result.advanced.dependency_version is not None
            if state == "broken":
                failures += 1
        # This contract pins identities/applicability only, never statistical values.
        signature = sorted(
            (c.check_id, c.dimension, c.rule_id, c.status == "skipped") for c in checks
        )
        digest = hashlib.sha256(
            json.dumps(signature, separators=(",", ":"), sort_keys=True).encode()
        ).hexdigest()
        contract = contracts[result.case_id]
        expected_digest = contract.get(f"{report.scope}:{variant}", contract.get(variant))
        failures += digest != expected_digest
    values = {
        "dataset_size": len(report.case_results),
        "cases_passed": statuses["pass"],
        "cases_failed": statuses["fail"],
        "cases_advisory": statuses["advisory"],
        "cases_skipped": statuses["skipped"],
        "cases_invalid": sum(r.category == "invalid_input" for r in report.case_results),
        "cases_abstained": sum(r.actual_status == "abstained" for r in report.case_results),
    }
    failures += sum(getattr(report, key) != value for key, value in values.items())
    summaries = {c.capability: c for c in report.capability_results}
    failures += len(summaries) != len(report.capability_results)
    failures += summaries.keys() != capabilities.keys()
    for capability, counts in capabilities.items():
        summary = summaries.get(capability)
        if summary is not None:
            failures += (summary.cases, summary.passed, summary.failed, summary.advisory) != (
                counts["cases"],
                counts["pass"],
                counts["fail"],
                counts["advisory"],
            )
    return {
        **{"statistics." + key: value for key, value in values.items()},
        "statistics.failures.case_inventory": failures,
    }
