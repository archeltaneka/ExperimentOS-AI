"""Deterministic identification and data validation for bounded DiD analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from numbers import Real

from ...metrics import MetricType
from ...provenance import DiagnosticSeverity
from ...validation.table import AnalysisTable
from ..diagnostics import CausalDiagnosticCode
from ..estimands import (
    CausalEstimandKind,
    EffectScale,
    TargetPopulationKind,
    TreatmentContrast,
)
from ..models import IdentificationResult, IdentificationStatus
from ..service import CausalIdentificationService
from .models import (
    DidDiagnostic,
    DidDiagnosticCategory,
    DidDiagnosticStatus,
    DidSampleCounts,
    DifferenceInDifferencesExecutionRequest,
)


class DidValidationDisposition(StrEnum):
    """Structural outcome of estimator-specific DiD validation."""

    VALID = "valid"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class DidObservation:
    """One finite canonical observation retained only inside the estimator."""

    unit_id: object
    treated: bool
    post: bool
    outcome: float


@dataclass(frozen=True, slots=True)
class DidPretrendObservation:
    """One diagnostic-period observation kept outside the ATT estimation sample."""

    unit_id: object
    treated: bool | None
    period_index: int
    exposure: object
    treatment_start: object
    outcome: object


@dataclass(frozen=True, slots=True)
class DidValidationResult:
    """Internal validated observations plus safe aggregate validation evidence."""

    disposition: DidValidationDisposition
    identification_result: IdentificationResult
    observations: tuple[DidObservation, ...]
    pretrend_observations: tuple[DidPretrendObservation, ...]
    sample_counts: DidSampleCounts
    diagnostics: tuple[DidDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class _CanonicalRow:
    unit_id: object
    treated_group: bool | None
    post: bool
    exposure: object
    treatment_start: object
    outcome: object


def validate_did_input(
    execution: DifferenceInDifferencesExecutionRequest,
    table: AnalysisTable,
) -> DidValidationResult:
    """Validate identification, timing, adoption, and strict canonical panel structure."""
    identification_result = CausalIdentificationService().identify(execution.analysis_request)
    diagnostics: list[DidDiagnostic] = []
    diagnostics.extend(_declared_design_diagnostics(execution))
    diagnostics.extend(_identification_diagnostics(identification_result))

    early_disposition = _blocking_declaration_disposition(diagnostics)
    if early_disposition is not None:
        return _result(
            early_disposition,
            identification_result,
            DidSampleCounts(),
            diagnostics,
        )

    missing_columns = tuple(
        column for column in _binding_columns(execution) if column not in table.columns
    )
    if missing_columns:
        diagnostics.append(
            _diagnostic(
                "did.missing_column",
                DidDiagnosticCategory.DESIGN,
                "Every declared DiD binding column must exist.",
                severity=DiagnosticSeverity.ERROR,
                context={"missing_column_count": len(missing_columns)},
            )
        )
        return _result(
            DidValidationDisposition.INVALID,
            identification_result,
            DidSampleCounts(rows=len(table.rows)),
            diagnostics,
        )

    canonical_rows, pretrend_rows, row_diagnostics = _canonical_rows(execution, table)
    diagnostics.extend(row_diagnostics)
    sample_counts, observations, panel_diagnostics = _validate_panel(
        execution, canonical_rows, table
    )
    diagnostics.extend(panel_diagnostics)
    diagnostics.extend(
        _diagnostic_window_design_diagnostics(execution, canonical_rows, pretrend_rows)
    )

    disposition = _derive_disposition(diagnostics)
    return _result(
        disposition,
        identification_result,
        sample_counts,
        diagnostics,
        observations=observations if disposition is DidValidationDisposition.VALID else (),
        pretrend_observations=(
            pretrend_rows if disposition is DidValidationDisposition.VALID else ()
        ),
    )


def _declared_design_diagnostics(
    execution: DifferenceInDifferencesExecutionRequest,
) -> tuple[DidDiagnostic, ...]:
    request = execution.analysis_request.identification
    diagnostics: list[DidDiagnostic] = []
    estimand = request.estimand
    outcome = request.outcome
    if estimand is None or estimand.estimand_type is not CausalEstimandKind.DID_ATT:
        diagnostics.append(
            _diagnostic(
                "did.incompatible_estimand",
                DidDiagnosticCategory.IDENTIFICATION,
                "V1 requires the declared DiD ATT estimand.",
                severity=DiagnosticSeverity.ERROR,
                unsupported=True,
            )
        )
    elif (
        estimand.target_population.kind is not TargetPopulationKind.TREATED
        or estimand.effect_scale is not EffectScale.MEAN_DIFFERENCE
    ):
        diagnostics.append(
            _diagnostic(
                "did.incompatible_estimand",
                DidDiagnosticCategory.IDENTIFICATION,
                "V1 requires treated-target mean-difference DiD ATT semantics.",
                severity=DiagnosticSeverity.ERROR,
                unsupported=True,
            )
        )
    if outcome is None or outcome.metric.metric.metric_type is not MetricType.CONTINUOUS:
        diagnostics.append(
            _diagnostic(
                "did.unsupported_metric",
                DidDiagnosticCategory.OUTCOME,
                "V1 supports only a declared continuous outcome.",
                severity=DiagnosticSeverity.ERROR,
                unsupported=True,
            )
        )

    time = request.time
    pre = time.pre_period
    post = time.post_period
    start = time.treatment_start
    if pre is not None and post is not None and pre.end > post.start:
        diagnostics.append(
            _diagnostic(
                "did.reversed_timing",
                DidDiagnosticCategory.TIMING,
                "The canonical pre-period must end no later than the post-period starts.",
                severity=DiagnosticSeverity.ERROR,
            )
        )
    if pre is not None and start is not None and start < pre.end:
        diagnostics.append(
            _diagnostic(
                "did.treatment_too_early",
                DidDiagnosticCategory.TIMING,
                "Treatment must not begin before the canonical pre-period ends.",
                severity=DiagnosticSeverity.ERROR,
            )
        )
    if post is not None and start is not None and start > post.start:
        diagnostics.append(
            _diagnostic(
                "did.treatment_too_late",
                DidDiagnosticCategory.TIMING,
                "Treatment must begin no later than the canonical post-period starts.",
                severity=DiagnosticSeverity.ERROR,
            )
        )
    return tuple(diagnostics)


def _identification_diagnostics(result: IdentificationResult) -> tuple[DidDiagnostic, ...]:
    if result.status is IdentificationStatus.IDENTIFIED:
        return ()
    if any(item.code is CausalDiagnosticCode.REVERSED_TIMING for item in result.diagnostics):
        return ()
    disposition_severity = (
        DiagnosticSeverity.WARNING
        if result.status is IdentificationStatus.PARTIALLY_IDENTIFIED
        else DiagnosticSeverity.ERROR
    )
    return (
        _diagnostic(
            f"did.identification_{result.status.value}",
            DidDiagnosticCategory.IDENTIFICATION,
            "The issue #97 identification status is incompatible with DiD estimation.",
            severity=disposition_severity,
            unavailable=result.status
            in {
                IdentificationStatus.PARTIALLY_IDENTIFIED,
                IdentificationStatus.INSUFFICIENT_EVIDENCE,
            },
            unsupported=result.status is IdentificationStatus.UNSUPPORTED,
        ),
    )


def _binding_columns(execution: DifferenceInDifferencesExecutionRequest) -> tuple[str, ...]:
    binding = execution.binding
    return (
        binding.unit_column,
        binding.time_column,
        binding.group_column,
        binding.treatment_column,
        binding.treatment_start_column,
        binding.outcome_column,
    )


def _canonical_rows(
    execution: DifferenceInDifferencesExecutionRequest,
    table: AnalysisTable,
) -> tuple[
    tuple[_CanonicalRow, ...],
    tuple[DidPretrendObservation, ...],
    tuple[DidDiagnostic, ...],
]:
    binding = execution.binding
    indexes = {column: table.columns.index(column) for column in _binding_columns(execution)}
    time = execution.analysis_request.identification.time
    pre = time.pre_period
    post = time.post_period
    if pre is None or post is None:
        return (), (), ()

    diagnostics: list[DidDiagnostic] = []
    rows: list[_CanonicalRow] = []
    pretrend_rows: list[DidPretrendObservation] = []
    invalid_time_count = 0
    outside_period_count = 0
    invalid_unit_count = 0
    for source_row in table.rows:
        timestamp = source_row[indexes[binding.time_column]]
        if not isinstance(timestamp, datetime) or timestamp.utcoffset() is None:
            invalid_time_count += 1
            continue
        is_pre = pre.start <= timestamp < pre.end
        is_post = post.start <= timestamp < post.end
        extra_period_index = _extra_pre_period_index(timestamp, execution)
        if not is_pre and not is_post:
            if extra_period_index is None:
                outside_period_count += 1
                continue
        unit_id = source_row[indexes[binding.unit_column]]
        try:
            hash(unit_id)
        except TypeError:
            invalid_unit_count += 1
            continue
        if unit_id is None or isinstance(unit_id, bool):
            invalid_unit_count += 1
            continue
        group = source_row[indexes[binding.group_column]]
        treated_group: bool | None
        if _strict_equal(group, binding.treated_group_value):
            treated_group = True
        elif _strict_equal(group, binding.control_group_value):
            treated_group = False
        else:
            treated_group = None
        if extra_period_index is not None and not is_pre and not is_post:
            pretrend_rows.append(
                DidPretrendObservation(
                    unit_id=unit_id,
                    treated=treated_group,
                    period_index=extra_period_index,
                    exposure=source_row[indexes[binding.treatment_column]],
                    treatment_start=source_row[indexes[binding.treatment_start_column]],
                    outcome=source_row[indexes[binding.outcome_column]],
                )
            )
            continue
        rows.append(
            _CanonicalRow(
                unit_id=unit_id,
                treated_group=treated_group,
                post=is_post,
                exposure=source_row[indexes[binding.treatment_column]],
                treatment_start=source_row[indexes[binding.treatment_start_column]],
                outcome=source_row[indexes[binding.outcome_column]],
            )
        )
        if is_pre:
            pretrend_rows.append(
                DidPretrendObservation(
                    unit_id=unit_id,
                    treated=treated_group,
                    period_index=len(execution.extra_pre_periods),
                    exposure=source_row[indexes[binding.treatment_column]],
                    treatment_start=source_row[indexes[binding.treatment_start_column]],
                    outcome=source_row[indexes[binding.outcome_column]],
                )
            )
    if invalid_time_count:
        diagnostics.append(
            _diagnostic(
                "did.invalid_time_value",
                DidDiagnosticCategory.TIMING,
                "Time values must be timezone-aware datetimes.",
                severity=DiagnosticSeverity.ERROR,
                context={"invalid_row_count": invalid_time_count},
            )
        )
    if outside_period_count:
        diagnostics.append(
            _diagnostic(
                "did.unsupported_period",
                DidDiagnosticCategory.TIMING,
                "Rows outside declared canonical or diagnostic periods are unsupported.",
                severity=DiagnosticSeverity.ERROR,
                context={"outside_period_row_count": outside_period_count},
                unsupported=True,
            )
        )
    if invalid_unit_count:
        diagnostics.append(
            _diagnostic(
                "did.invalid_unit",
                DidDiagnosticCategory.PANEL,
                "Analysis-unit values must be non-null hashable identifiers.",
                severity=DiagnosticSeverity.ERROR,
                context={"invalid_row_count": invalid_unit_count},
            )
        )
    return tuple(rows), tuple(pretrend_rows), tuple(diagnostics)


def _extra_pre_period_index(
    timestamp: datetime,
    execution: DifferenceInDifferencesExecutionRequest,
) -> int | None:
    for index, period in enumerate(execution.extra_pre_periods):
        if period.start <= timestamp < period.end:
            return index
    return None


def _validate_panel(
    execution: DifferenceInDifferencesExecutionRequest,
    rows: tuple[_CanonicalRow, ...],
    table: AnalysisTable,
) -> tuple[DidSampleCounts, tuple[DidObservation, ...], tuple[DidDiagnostic, ...]]:
    by_unit: dict[object, list[_CanonicalRow]] = {}
    for row in rows:
        by_unit.setdefault(row.unit_id, []).append(row)

    diagnostics: list[DidDiagnostic] = []
    membership_by_unit = {
        unit: {row.treated_group for row in unit_rows} for unit, unit_rows in by_unit.items()
    }
    unknown_group_units = {
        unit for unit, memberships in membership_by_unit.items() if None in memberships
    }
    switching_units = {
        unit
        for unit, memberships in membership_by_unit.items()
        if True in memberships and False in memberships
    }
    if unknown_group_units:
        diagnostics.append(
            _diagnostic(
                "did.unknown_group",
                DidDiagnosticCategory.GROUP,
                "Every canonical row must belong to the declared treated or control group.",
                severity=DiagnosticSeverity.ERROR,
                context={"affected_unit_count": len(unknown_group_units)},
            )
        )
    if switching_units:
        diagnostics.append(
            _diagnostic(
                "did.group_switching",
                DidDiagnosticCategory.GROUP,
                "Treated/control membership must remain stable across canonical periods.",
                severity=DiagnosticSeverity.ERROR,
                context={"affected_unit_count": len(switching_units)},
            )
        )

    treated_units = {
        unit for unit, memberships in membership_by_unit.items() if memberships == {True}
    }
    control_units = {
        unit for unit, memberships in membership_by_unit.items() if memberships == {False}
    }
    if not treated_units:
        diagnostics.append(
            _diagnostic(
                "did.missing_treated_group",
                DidDiagnosticCategory.GROUP,
                "The canonical panel contains no treated group.",
                severity=DiagnosticSeverity.ERROR,
                unavailable=True,
            )
        )
    if not control_units:
        diagnostics.append(
            _diagnostic(
                "did.missing_control_group",
                DidDiagnosticCategory.GROUP,
                "The canonical panel contains no comparison group.",
                severity=DiagnosticSeverity.ERROR,
                unavailable=True,
            )
        )

    pre_by_unit = {
        unit: [row for row in unit_rows if not row.post] for unit, unit_rows in by_unit.items()
    }
    post_by_unit = {
        unit: [row for row in unit_rows if row.post] for unit, unit_rows in by_unit.items()
    }
    duplicate_units = {
        unit for unit in by_unit if len(pre_by_unit[unit]) > 1 or len(post_by_unit[unit]) > 1
    }
    if duplicate_units:
        diagnostics.append(
            _diagnostic(
                "did.duplicate_unit_period",
                DidDiagnosticCategory.PANEL,
                "V1 requires exactly one row per analysis unit and canonical period.",
                severity=DiagnosticSeverity.ERROR,
                context={"affected_unit_count": len(duplicate_units)},
            )
        )

    missing_pre_units = {unit for unit in by_unit if not pre_by_unit[unit]}
    missing_post_units = {unit for unit in by_unit if not post_by_unit[unit]}
    if missing_pre_units or missing_post_units:
        diagnostics.extend(
            (
                _diagnostic(
                    "did.composition_change",
                    DidDiagnosticCategory.PANEL,
                    "Canonical pre/post unit composition changes under the strict panel policy.",
                    severity=DiagnosticSeverity.ERROR,
                    unavailable=True,
                    context={
                        "units_missing_pre": len(missing_pre_units),
                        "units_missing_post": len(missing_post_units),
                    },
                ),
                _diagnostic(
                    "did.incomplete_unit_coverage",
                    DidDiagnosticCategory.PANEL,
                    "Every analysis unit must have both canonical periods.",
                    severity=DiagnosticSeverity.ERROR,
                    unavailable=True,
                    context={"affected_unit_count": len(missing_pre_units | missing_post_units)},
                ),
            )
        )

    invalid_outcome_rows: set[int] = set()
    missing_outcome_rows: set[int] = set()
    for index, row in enumerate(rows):
        if row.outcome is None:
            missing_outcome_rows.add(index)
        elif not _is_finite_real(row.outcome):
            invalid_outcome_rows.add(index)
    if missing_outcome_rows:
        diagnostics.append(
            _diagnostic(
                "did.missing_outcome",
                DidDiagnosticCategory.OUTCOME,
                "Canonical outcomes are missing; V1 does not impute or filter them.",
                severity=DiagnosticSeverity.ERROR,
                unavailable=True,
                context={"missing_outcome_count": len(missing_outcome_rows)},
            )
        )
    if invalid_outcome_rows:
        diagnostics.append(
            _diagnostic(
                "did.nonfinite_outcome",
                DidDiagnosticCategory.OUTCOME,
                "Canonical outcomes must be finite real numbers.",
                severity=DiagnosticSeverity.ERROR,
                context={"invalid_outcome_count": len(invalid_outcome_rows)},
            )
        )

    diagnostics.extend(_adoption_diagnostics(execution, by_unit, membership_by_unit))
    retained_units = {
        unit
        for unit in by_unit
        if unit not in duplicate_units
        and unit not in missing_pre_units
        and unit not in missing_post_units
        and unit not in unknown_group_units
        and unit not in switching_units
        and all(_is_finite_real(row.outcome) for row in by_unit[unit])
    }
    treated_retained = retained_units & treated_units
    control_retained = retained_units & control_units
    counts = _sample_counts(
        table=table,
        rows=rows,
        by_unit=by_unit,
        treated_units=treated_units,
        control_units=control_units,
        retained_units=retained_units,
        treated_retained=treated_retained,
        control_retained=control_retained,
        missing_pre_units=missing_pre_units,
        missing_post_units=missing_post_units,
    )
    observations = tuple(
        DidObservation(
            unit_id=row.unit_id,
            treated=bool(row.treated_group),
            post=row.post,
            outcome=_validated_outcome(row.outcome),
        )
        for row in rows
        if row.unit_id in retained_units
    )
    return counts, observations, tuple(diagnostics)


def _validated_outcome(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimeError("validated DiD row contains a non-numeric outcome")
    return float(value)


def _diagnostic_window_design_diagnostics(
    execution: DifferenceInDifferencesExecutionRequest,
    canonical_rows: tuple[_CanonicalRow, ...],
    pretrend_rows: tuple[DidPretrendObservation, ...],
) -> tuple[DidDiagnostic, ...]:
    extra_rows = tuple(
        row for row in pretrend_rows if row.period_index < len(execution.extra_pre_periods)
    )
    if not extra_rows:
        return ()
    canonical_membership: dict[object, set[bool | None]] = {}
    for canonical_row in canonical_rows:
        canonical_membership.setdefault(canonical_row.unit_id, set()).add(
            canonical_row.treated_group
        )

    request = execution.analysis_request.identification
    contrast = request.treatment
    declared_start = request.time.treatment_start
    unknown_groups = 0
    switching_units: set[object] = set()
    anticipation_units: set[object] = set()
    staggered_units: set[object] = set()
    control_adoption_units: set[object] = set()
    invalid_exposure_units: set[object] = set()
    for diagnostic_row in extra_rows:
        if diagnostic_row.treated is None:
            unknown_groups += 1
            continue
        if (
            diagnostic_row.unit_id in canonical_membership
            and diagnostic_row.treated not in canonical_membership[diagnostic_row.unit_id]
        ):
            switching_units.add(diagnostic_row.unit_id)
        if contrast is None:
            continue
        if not _known_exposure(diagnostic_row.exposure, contrast):
            invalid_exposure_units.add(diagnostic_row.unit_id)
        if diagnostic_row.treated:
            if _strict_equal(diagnostic_row.exposure, contrast.treated_value):
                anticipation_units.add(diagnostic_row.unit_id)
            if declared_start is not None and diagnostic_row.treatment_start != declared_start:
                staggered_units.add(diagnostic_row.unit_id)
        elif diagnostic_row.treatment_start is not None or _strict_equal(
            diagnostic_row.exposure, contrast.treated_value
        ):
            control_adoption_units.add(diagnostic_row.unit_id)

    findings = (
        (
            unknown_groups,
            "did.unknown_group",
            DidDiagnosticCategory.GROUP,
            "Diagnostic pre-period rows must use a declared group.",
        ),
        (
            len(switching_units),
            "did.group_switching",
            DidDiagnosticCategory.GROUP,
            "Treated/control membership must remain stable in diagnostic pre-periods.",
        ),
        (
            len(anticipation_units),
            "did.anticipatory_exposure",
            DidDiagnosticCategory.TIMING,
            "Treated units must be unexposed throughout all declared pre-periods.",
        ),
        (
            len(staggered_units),
            "did.staggered_adoption",
            DidDiagnosticCategory.TIMING,
            "Treated units must share the declared treatment start in all periods.",
        ),
        (
            len(control_adoption_units),
            "did.control_adoption",
            DidDiagnosticCategory.TIMING,
            "Comparison units must remain untreated in diagnostic pre-periods.",
        ),
        (
            len(invalid_exposure_units),
            "did.invalid_treatment_value",
            DidDiagnosticCategory.TIMING,
            "Diagnostic pre-period exposure values must match the declared contrast.",
        ),
    )
    return tuple(
        _diagnostic(
            code,
            category,
            message,
            severity=DiagnosticSeverity.ERROR,
            context={"affected_unit_count": count},
        )
        for count, code, category, message in findings
        if count
    )


def _adoption_diagnostics(
    execution: DifferenceInDifferencesExecutionRequest,
    by_unit: dict[object, list[_CanonicalRow]],
    membership_by_unit: dict[object, set[bool | None]],
) -> tuple[DidDiagnostic, ...]:
    request = execution.analysis_request.identification
    contrast = request.treatment
    declared_start = request.time.treatment_start
    if contrast is None or declared_start is None:
        return ()
    staggered_units = 0
    early_exposure_units = 0
    reversal_units = 0
    control_adoption_units = 0
    invalid_exposure_units = 0
    for unit, unit_rows in by_unit.items():
        memberships = membership_by_unit[unit]
        if memberships == {True}:
            starts = {row.treatment_start for row in unit_rows}
            if starts != {declared_start}:
                staggered_units += 1
            pre_rows = [row for row in unit_rows if not row.post]
            post_rows = [row for row in unit_rows if row.post]
            if any(_strict_equal(row.exposure, contrast.treated_value) for row in pre_rows):
                early_exposure_units += 1
            if any(not _known_exposure(row.exposure, contrast) for row in unit_rows):
                invalid_exposure_units += 1
            if post_rows and any(
                not _strict_equal(row.exposure, contrast.treated_value) for row in post_rows
            ):
                reversal_units += 1
        elif memberships == {False}:
            if any(row.treatment_start is not None for row in unit_rows) or any(
                _strict_equal(row.exposure, contrast.treated_value) for row in unit_rows
            ):
                control_adoption_units += 1
            if any(not _known_exposure(row.exposure, contrast) for row in unit_rows):
                invalid_exposure_units += 1
    diagnostics: list[DidDiagnostic] = []
    for count, code, message in (
        (
            staggered_units,
            "did.staggered_adoption",
            "All treated units must share the declared treatment start.",
        ),
        (
            early_exposure_units,
            "did.anticipatory_exposure",
            "Treated units must be unexposed during the canonical pre-period.",
        ),
        (
            reversal_units,
            "did.treatment_reversal",
            "Treated units must remain treated in the canonical post-period.",
        ),
        (
            control_adoption_units,
            "did.control_adoption",
            "Comparison units must remain untreated throughout the supported window.",
        ),
        (
            invalid_exposure_units,
            "did.invalid_treatment_value",
            "Exposure values must match the declared treatment contrast.",
        ),
    ):
        if count:
            diagnostics.append(
                _diagnostic(
                    code,
                    DidDiagnosticCategory.TIMING,
                    message,
                    severity=DiagnosticSeverity.ERROR,
                    context={"affected_unit_count": count},
                )
            )
    return tuple(diagnostics)


def _sample_counts(
    *,
    table: AnalysisTable,
    rows: tuple[_CanonicalRow, ...],
    by_unit: dict[object, list[_CanonicalRow]],
    treated_units: set[object],
    control_units: set[object],
    retained_units: set[object],
    treated_retained: set[object],
    control_retained: set[object],
    missing_pre_units: set[object],
    missing_post_units: set[object],
) -> DidSampleCounts:
    total_units = len(by_unit)

    def missing(group: bool, post: bool) -> int:
        return sum(
            row.treated_group is group and row.post is post and not _is_finite_real(row.outcome)
            for row in rows
        )

    def coverage(group: bool, post: bool) -> int:
        return sum(row.treated_group is group and row.post is post for row in rows)

    return DidSampleCounts(
        rows=len(table.rows),
        total_units=total_units,
        treated_units=len(treated_units),
        control_units=len(control_units),
        units_with_both_periods=sum(
            any(not row.post for row in unit_rows) and any(row.post for row in unit_rows)
            for unit_rows in by_unit.values()
        ),
        units_missing_pre=len(missing_pre_units),
        units_missing_post=len(missing_post_units),
        retained_units=len(retained_units),
        incomplete_units=total_units - len(retained_units),
        excluded_units=total_units - len(retained_units),
        treated_retained_units=len(treated_retained),
        control_retained_units=len(control_retained),
        treated_pre_rows=coverage(True, False),
        treated_post_rows=coverage(True, True),
        control_pre_rows=coverage(False, False),
        control_post_rows=coverage(False, True),
        treated_missing_pre_outcomes=missing(True, False),
        treated_missing_post_outcomes=missing(True, True),
        control_missing_pre_outcomes=missing(False, False),
        control_missing_post_outcomes=missing(False, True),
        retention_rate=_rate(len(retained_units), total_units),
        treated_retention_rate=_rate(len(treated_retained), len(treated_units)),
        control_retention_rate=_rate(len(control_retained), len(control_units)),
    )


def _blocking_declaration_disposition(
    diagnostics: list[DidDiagnostic],
) -> DidValidationDisposition | None:
    if any(item.code == "did.reversed_timing" for item in diagnostics):
        return DidValidationDisposition.INVALID
    if any(
        item.code in {"did.treatment_too_early", "did.treatment_too_late"} for item in diagnostics
    ):
        return DidValidationDisposition.INVALID
    if any(item.status is DidDiagnosticStatus.UNAVAILABLE for item in diagnostics):
        return DidValidationDisposition.ABSTAINED
    if any(item.category is DidDiagnosticCategory.IDENTIFICATION for item in diagnostics):
        if any(item.code == "did.identification_unsupported" for item in diagnostics):
            return DidValidationDisposition.UNSUPPORTED
        return DidValidationDisposition.INVALID
    if any(
        item.code in {"did.unsupported_metric", "did.incompatible_estimand"} for item in diagnostics
    ):
        return DidValidationDisposition.UNSUPPORTED
    return None


def _derive_disposition(diagnostics: list[DidDiagnostic]) -> DidValidationDisposition:
    if any(item.status is DidDiagnosticStatus.UNAVAILABLE for item in diagnostics):
        return DidValidationDisposition.ABSTAINED
    if any(
        item.code in {"did.unsupported_metric", "did.unsupported_period"} for item in diagnostics
    ):
        return DidValidationDisposition.UNSUPPORTED
    if diagnostics:
        return DidValidationDisposition.INVALID
    return DidValidationDisposition.VALID


def _result(
    disposition: DidValidationDisposition,
    identification_result: IdentificationResult,
    sample_counts: DidSampleCounts,
    diagnostics: list[DidDiagnostic],
    *,
    observations: tuple[DidObservation, ...] = (),
    pretrend_observations: tuple[DidPretrendObservation, ...] = (),
) -> DidValidationResult:
    return DidValidationResult(
        disposition=disposition,
        identification_result=identification_result,
        observations=observations,
        pretrend_observations=pretrend_observations,
        sample_counts=sample_counts,
        diagnostics=tuple(sorted(diagnostics, key=lambda item: item.code)),
    )


def _diagnostic(
    code: str,
    category: DidDiagnosticCategory,
    message: str,
    *,
    severity: DiagnosticSeverity,
    context: dict[str, object] | None = None,
    unavailable: bool = False,
    unsupported: bool = False,
) -> DidDiagnostic:
    del unsupported
    return DidDiagnostic.model_validate(
        {
            "code": code,
            "category": category,
            "severity": severity,
            "status": (
                DidDiagnosticStatus.UNAVAILABLE if unavailable else DidDiagnosticStatus.FAILED
            ),
            "message": message,
            "context": context or {},
        }
    )


def _strict_equal(value: object, expected: object) -> bool:
    return type(value) is type(expected) and value == expected


def _known_exposure(value: object, contrast: TreatmentContrast) -> bool:
    return _strict_equal(value, contrast.treated_value) or _strict_equal(
        value,
        contrast.control_value,
    )


def _is_finite_real(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, Real) and math.isfinite(float(value))


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


__all__ = [
    "DidObservation",
    "DidPretrendObservation",
    "DidValidationDisposition",
    "DidValidationResult",
    "validate_did_input",
]
