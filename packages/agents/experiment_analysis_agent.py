from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select

from packages.agents.state import (
    AgentState,
    AgentStateUpdate,
    Citation,
    ExperimentAnalysis,
    ExperimentMetadata,
    ExperimentMetricRecord,
    MetricComparisonRecord,
    MetricVariantRecord,
    create_error_entry,
    create_trace_entry,
)
from packages.db.models import Experiment, ExperimentMetric
from packages.db.session import create_async_session_factory, create_database_engine
from packages.ingestion.load_experiment import run_async

EXPERIMENT_ANALYSIS_NODE = "experiment_analysis"
SIGNIFICANCE_P_VALUE_THRESHOLD = 0.05


@dataclass(frozen=True)
class ExperimentRecord:
    database_id: str
    external_id: str
    name: str
    hypothesis: str
    primary_metric: str
    secondary_metrics: list[str]
    imperfections: list[str]
    metadata: dict[str, object]


@dataclass(frozen=True)
class StoredMetricRecord:
    metric_name: str
    variant: str
    value: float
    metadata: dict[str, object]


class ExperimentAnalysisRepository(Protocol):
    async def get_experiment(self, identifier: str) -> ExperimentRecord | None:
        pass

    async def search_experiments_by_hint(self, hint: str) -> list[ExperimentRecord]:
        pass

    async def get_metrics(self, experiment_database_id: str) -> list[StoredMetricRecord]:
        pass


@dataclass
class RuntimeExperimentAnalysisRepository:
    async def get_experiment(self, identifier: str) -> ExperimentRecord | None:
        engine = create_database_engine()
        session_factory = create_async_session_factory(engine)
        try:
            async with session_factory() as session:
                experiment = await self._find_experiment(session, identifier)
                return _to_experiment_record(experiment) if experiment is not None else None
        finally:
            await engine.dispose()

    async def search_experiments_by_hint(self, hint: str) -> list[ExperimentRecord]:
        normalized_hint = _normalize_text(hint)
        if not normalized_hint:
            return []

        engine = create_database_engine()
        session_factory = create_async_session_factory(engine)
        try:
            async with session_factory() as session:
                experiments = (await session.scalars(select(Experiment))).all()
        finally:
            await engine.dispose()

        matches = [
            _to_experiment_record(experiment)
            for experiment in experiments
            if _experiment_matches_hint(experiment, normalized_hint)
        ]
        return sorted(
            matches,
            key=lambda record: (
                _normalize_text(record.name) != normalized_hint,
                _normalize_text(record.external_id) != normalized_hint,
                record.name,
            ),
        )

    async def get_metrics(self, experiment_database_id: str) -> list[StoredMetricRecord]:
        parsed_id = UUID(str(experiment_database_id))
        engine = create_database_engine()
        session_factory = create_async_session_factory(engine)
        try:
            async with session_factory() as session:
                metrics = (
                    await session.scalars(
                        select(ExperimentMetric).where(ExperimentMetric.experiment_id == parsed_id)
                    )
                ).all()
        finally:
            await engine.dispose()

        return [
            StoredMetricRecord(
                metric_name=_split_metric_storage_name(metric.name)[0],
                variant=_split_metric_storage_name(metric.name)[1],
                value=metric.value,
                metadata=dict(metric.metric_metadata),
            )
            for metric in metrics
        ]

    async def _find_experiment(self, session: Any, identifier: str) -> Experiment | None:
        parsed_uuid = _maybe_uuid(identifier)
        if parsed_uuid is not None:
            experiment = await session.get(Experiment, parsed_uuid)
            if experiment is not None:
                return experiment

        experiments = (await session.scalars(select(Experiment))).all()
        normalized_identifier = _normalize_text(identifier)
        for experiment in experiments:
            config = _experiment_config(experiment)
            candidates = (
                str(experiment.id),
                experiment.name,
                str(config.get("experiment_id", "")),
                str(config.get("area", "")),
            )
            if any(_normalize_text(candidate) == normalized_identifier for candidate in candidates):
                return experiment
        return None


@dataclass
class ExperimentAnalysisAgent:
    repository: ExperimentAnalysisRepository | None = None

    def __post_init__(self) -> None:
        if self.repository is None:
            self.repository = RuntimeExperimentAnalysisRepository()

    def run(self, state: AgentState) -> AgentStateUpdate:
        started_at = perf_counter()
        trace = [create_trace_entry(node=EXPERIMENT_ANALYSIS_NODE, event="started")]
        try:
            analysis, experiment_metadata, experiment_metrics, resolved_count = run_async(
                self._analyze(state)
            )
        except Exception as exc:
            return {
                "errors": [
                    create_error_entry(
                        code="experiment_analysis_failed",
                        message=f"Experiment analysis failed: {exc}",
                        node=EXPERIMENT_ANALYSIS_NODE,
                        details={"error_type": type(exc).__name__},
                    )
                ],
                "trace": [
                    *trace,
                    create_trace_entry(
                        node=EXPERIMENT_ANALYSIS_NODE,
                        event="failed",
                        details={"error_type": type(exc).__name__},
                    ),
                ],
                "metrics": {
                    **state["metrics"],
                    "experiment_analysis": {
                        "status": "failed",
                        "latency_ms": (perf_counter() - started_at) * 1000.0,
                        "resolved_experiment_count": 0,
                        "citation_count": len(state["citations"]),
                        "guardrail_metric_count": 0,
                    },
                },
            }

        return {
            "experiment_analysis": analysis,
            "experiment_metadata": experiment_metadata,
            "experiment_metrics": experiment_metrics,
            "errors": [],
            "trace": [
                *trace,
                create_trace_entry(
                    node=EXPERIMENT_ANALYSIS_NODE,
                    event="completed",
                    details={
                        "status": analysis["status"],
                        "resolved_experiment_count": resolved_count,
                    },
                ),
            ],
            "metrics": {
                **state["metrics"],
                "experiment_analysis": {
                    "status": analysis["status"],
                    "latency_ms": (perf_counter() - started_at) * 1000.0,
                    "resolved_experiment_count": resolved_count,
                    "citation_count": len(analysis["evidence_citations"]),
                    "guardrail_metric_count": len(analysis["guardrail_metrics"]),
                },
            },
        }

    async def _analyze(
        self,
        state: AgentState,
    ) -> tuple[ExperimentAnalysis, ExperimentMetadata, list[ExperimentMetricRecord], int]:
        experiment, resolved_count = await self._resolve_experiment(state)
        if experiment is None:
            analysis = _build_insufficient_data_analysis(
                base=state["experiment_analysis"],
                summary=(
                    "Insufficient data: no experiment could be resolved from "
                    "planner or retrieval context."
                ),
                findings=["No experiment identifier or hint resolved to a stored experiment."],
                limitations=["Experiment resolution failed before metric analysis could begin."],
                evidence_citations=list(state["citations"]),
            )
            return analysis, {}, [], resolved_count

        metrics = await self.repository.get_metrics(experiment.database_id)
        analysis = _build_analysis(
            base=state["experiment_analysis"],
            experiment=experiment,
            metrics=metrics,
            evidence_citations=_matching_citations(state["citations"], experiment),
        )
        return (
            analysis,
            _experiment_state_metadata(experiment),
            [_stored_metric_state_record(metric) for metric in metrics],
            resolved_count,
        )

    async def _resolve_experiment(self, state: AgentState) -> tuple[ExperimentRecord | None, int]:
        identifiers = list(_candidate_identifiers(state))
        seen_database_ids: set[str] = set()

        for identifier in identifiers:
            experiment = await self.repository.get_experiment(identifier)
            if experiment is not None:
                seen_database_ids.add(experiment.database_id)
                return experiment, len(seen_database_ids)

        hint_matches: list[ExperimentRecord] = []
        for hint in _experiment_hints(state):
            for experiment in await self.repository.search_experiments_by_hint(hint):
                if experiment.database_id not in seen_database_ids:
                    hint_matches.append(experiment)
                    seen_database_ids.add(experiment.database_id)

        if hint_matches:
            return hint_matches[0], len(hint_matches)
        return None, 0


def _build_analysis(
    *,
    base: ExperimentAnalysis,
    experiment: ExperimentRecord,
    metrics: list[StoredMetricRecord],
    evidence_citations: list[Citation],
) -> ExperimentAnalysis:
    grouped_metrics = _group_metrics(metrics)
    primary_metric = experiment.primary_metric
    primary_variants = grouped_metrics.get(primary_metric, {})
    control_metric = primary_variants.get("control")
    treatment_metric = primary_variants.get("treatment")
    limitations = list(experiment.imperfections)

    if control_metric is None or treatment_metric is None:
        limitations.append(
            f"Primary metric {primary_metric} is missing control or treatment "
            "data in stored metrics."
        )
        return _build_insufficient_data_analysis(
            base=base,
            summary=(
                f"Insufficient data: primary metric {primary_metric} is missing a stored "
                "control versus treatment comparison."
            ),
            findings=[
                f"Experiment resolved to {experiment.name}, but the primary metric "
                "comparison is incomplete."
            ],
            experiment=experiment,
            limitations=limitations,
            evidence_citations=evidence_citations,
        )

    control_record = _metric_variant_record(control_metric)
    treatment_record = _metric_variant_record(treatment_metric)
    primary_comparison = _metric_comparison_record(
        metric_name=primary_metric,
        control_metric=control_metric,
        treatment_metric=treatment_metric,
    )
    statistical_significance = _statistical_significance(primary_comparison)
    confidence_level = _confidence_level(control_metric, treatment_metric)
    guardrail_metrics = [
        _metric_comparison_record(
            metric_name=metric_name,
            control_metric=variants["control"],
            treatment_metric=variants["treatment"],
        )
        for metric_name, variants in grouped_metrics.items()
        if metric_name != primary_metric
        and "control" in variants
        and "treatment" in variants
    ]
    analysis_confidence = _analysis_confidence(
        statistical_significance=statistical_significance,
        evidence_citations=evidence_citations,
        guardrail_metrics=guardrail_metrics,
    )

    summary = (
        f"{experiment.name} primary metric {primary_metric} moved from "
        f"{control_metric.value:.4f} in control to {treatment_metric.value:.4f} in treatment."
    )
    if "relative_lift" in primary_comparison:
        summary += f" Stored lift vs control was {primary_comparison['relative_lift']:.4f}."
    if "p_value" in statistical_significance:
        summary += f" Stored p-value was {statistical_significance['p_value']:.3f}."

    findings = [
        f"Hypothesis: {experiment.hypothesis}",
        (
            f"Primary metric {primary_metric}: control={control_metric.value:.4f}, "
            f"treatment={treatment_metric.value:.4f}."
        ),
    ]
    if "absolute_delta" in primary_comparison:
        findings.append(
            f"Absolute delta for {primary_metric}: {primary_comparison['absolute_delta']:.4f}."
        )
    if "relative_lift" in primary_comparison:
        findings.append(
            f"Observed lift vs control for {primary_metric}: "
            f"{primary_comparison['relative_lift']:.4f}."
        )
    if "p_value" in statistical_significance:
        findings.append(
            f"Stored p-value for {primary_metric}: {statistical_significance['p_value']:.3f}."
        )
    if not evidence_citations:
        limitations.append("Retrieval did not provide supporting citations for this experiment.")

    return {
        **base,
        "summary": summary,
        "findings": findings,
        "status": "completed",
        "experiment_id": experiment.external_id or experiment.database_id,
        "experiment_name": experiment.name,
        "hypothesis": experiment.hypothesis,
        "primary_metric": primary_metric,
        "control": control_record,
        "treatment": treatment_record,
        "treatment_control_comparison": primary_comparison,
        "observed_lift": {
            key: value
            for key, value in primary_comparison.items()
            if key in {"metric_name", "relative_lift", "unit", "p_value"}
        },
        "statistical_significance": statistical_significance,
        "confidence_level": confidence_level,
        "guardrail_metrics": guardrail_metrics,
        "limitations": limitations,
        "evidence_citations": evidence_citations,
        "analysis_confidence": analysis_confidence,
    }


def _build_insufficient_data_analysis(
    *,
    base: ExperimentAnalysis,
    summary: str,
    findings: list[str],
    limitations: list[str],
    evidence_citations: list[Citation],
    experiment: ExperimentRecord | None = None,
) -> ExperimentAnalysis:
    experiment_id = ""
    experiment_name = ""
    hypothesis = ""
    primary_metric = ""
    if experiment is not None:
        experiment_id = experiment.external_id or experiment.database_id
        experiment_name = experiment.name
        hypothesis = experiment.hypothesis
        primary_metric = experiment.primary_metric

    return {
        **base,
        "summary": summary,
        "findings": findings,
        "status": "insufficient_data",
        "experiment_id": experiment_id,
        "experiment_name": experiment_name,
        "hypothesis": hypothesis,
        "primary_metric": primary_metric,
        "control": {},
        "treatment": {},
        "treatment_control_comparison": {},
        "observed_lift": {},
        "statistical_significance": {},
        "confidence_level": {},
        "guardrail_metrics": [],
        "limitations": limitations,
        "evidence_citations": evidence_citations,
        "analysis_confidence": "low",
    }


def _candidate_identifiers(state: AgentState) -> Iterable[str]:
    seen: set[str] = set()
    for identifier in state["experiment_context"]["experiment_ids"]:
        if identifier and identifier not in seen:
            seen.add(identifier)
            yield identifier
    for citation in state["citations"]:
        identifier = citation.get("experiment_id", "")
        if identifier and identifier not in seen:
            seen.add(identifier)
            yield identifier
    for chunk in state["retrieved_chunks"]:
        identifier = chunk.get("experiment_id", "")
        if identifier and identifier not in seen:
            seen.add(identifier)
            yield identifier


def _experiment_hints(state: AgentState) -> list[str]:
    hints = state["experiment_context"]["filters"].get("experiment_hints", [])
    if isinstance(hints, list):
        return [str(hint) for hint in hints if str(hint).strip()]
    return []


def _group_metrics(
    metrics: list[StoredMetricRecord],
) -> dict[str, dict[str, StoredMetricRecord]]:
    grouped: dict[str, dict[str, StoredMetricRecord]] = defaultdict(dict)
    for metric in metrics:
        grouped[metric.metric_name][metric.variant] = metric
    return grouped


def _metric_variant_record(metric: StoredMetricRecord) -> MetricVariantRecord:
    record: MetricVariantRecord = {
        "metric_name": metric.metric_name,
        "variant": metric.variant,
        "value": metric.value,
    }
    unit = _metadata_str(metric.metadata, "unit")
    if unit:
        record["unit"] = unit
    numerator = _metadata_float(metric.metadata, "numerator")
    if numerator is not None:
        record["numerator"] = numerator
    denominator = _metadata_float(metric.metadata, "denominator")
    if denominator is not None:
        record["denominator"] = denominator
    notes = _metadata_str(metric.metadata, "notes")
    if notes:
        record["notes"] = notes
    return record


def _metric_comparison_record(
    *,
    metric_name: str,
    control_metric: StoredMetricRecord,
    treatment_metric: StoredMetricRecord,
) -> MetricComparisonRecord:
    record: MetricComparisonRecord = {
        "metric_name": metric_name,
        "control_value": control_metric.value,
        "treatment_value": treatment_metric.value,
        "absolute_delta": round(treatment_metric.value - control_metric.value, 6),
    }
    unit = _metadata_str(treatment_metric.metadata, "unit") or _metadata_str(
        control_metric.metadata,
        "unit",
    )
    if unit:
        record["unit"] = unit

    relative_lift = _metadata_float(treatment_metric.metadata, "lift_vs_control")
    if relative_lift is None and control_metric.value != 0:
        relative_lift = round(
            (treatment_metric.value - control_metric.value) / control_metric.value,
            6,
        )
    if relative_lift is not None:
        record["relative_lift"] = relative_lift

    p_value = _metadata_float(treatment_metric.metadata, "p_value")
    if p_value is not None:
        record["p_value"] = p_value
    return record


def _statistical_significance(comparison: MetricComparisonRecord) -> dict[str, object]:
    p_value = comparison.get("p_value")
    if p_value is None:
        return {}
    return {
        "p_value": p_value,
        "is_significant": p_value < SIGNIFICANCE_P_VALUE_THRESHOLD,
    }


def _confidence_level(
    control_metric: StoredMetricRecord,
    treatment_metric: StoredMetricRecord,
) -> dict[str, object]:
    confidence = _metadata_float(treatment_metric.metadata, "confidence_level")
    if confidence is None:
        confidence = _metadata_float(treatment_metric.metadata, "confidence")
    if confidence is None:
        confidence = _metadata_float(control_metric.metadata, "confidence_level")
    if confidence is None:
        return {}
    return {"confidence_level": confidence}


def _analysis_confidence(
    *,
    statistical_significance: dict[str, object],
    evidence_citations: list[Citation],
    guardrail_metrics: list[MetricComparisonRecord],
) -> str:
    if statistical_significance and evidence_citations and guardrail_metrics:
        return "high"
    if statistical_significance or guardrail_metrics:
        return "medium"
    return "low"


def _matching_citations(
    citations: list[Citation],
    experiment: ExperimentRecord,
) -> list[Citation]:
    matches: list[Citation] = []
    valid_ids = {experiment.database_id, experiment.external_id}
    for citation in citations:
        if citation.get("experiment_id") in valid_ids:
            matches.append(citation)
    return matches


def _to_experiment_record(experiment: Experiment) -> ExperimentRecord:
    config = _experiment_config(experiment)
    return ExperimentRecord(
        database_id=str(experiment.id),
        external_id=str(config.get("experiment_id", "")),
        name=experiment.name,
        hypothesis=str(config.get("hypothesis") or experiment.description or ""),
        primary_metric=str(config.get("primary_metric", "")),
        secondary_metrics=[str(value) for value in config.get("secondary_metrics", [])],
        imperfections=[str(value) for value in config.get("imperfections", [])],
        metadata=config,
    )


def _experiment_config(experiment: Experiment) -> dict[str, Any]:
    return dict(experiment.config or {})


def _experiment_matches_hint(experiment: Experiment, normalized_hint: str) -> bool:
    config = _experiment_config(experiment)
    candidates = (
        experiment.name,
        str(config.get("experiment_id", "")),
        str(config.get("area", "")),
    )
    return any(normalized_hint in _normalize_text(candidate) for candidate in candidates)


def _split_metric_storage_name(storage_name: str) -> tuple[str, str]:
    metric_name, _, variant = storage_name.partition(":")
    return metric_name, variant


def _experiment_state_metadata(experiment: ExperimentRecord) -> ExperimentMetadata:
    metadata: ExperimentMetadata = {
        "experiment_id": experiment.external_id or experiment.database_id,
        "name": experiment.name,
        "hypothesis": experiment.hypothesis,
        "primary_metric": experiment.primary_metric,
        "secondary_metrics": list(experiment.secondary_metrics),
        "imperfections": list(experiment.imperfections),
    }
    for key in (
        "area",
        "owner",
        "status",
        "start_date",
        "end_date",
        "business_decision",
    ):
        value = experiment.metadata.get(key)
        if value not in (None, "", []):
            metadata[key] = value
    return metadata


def _stored_metric_state_record(metric: StoredMetricRecord) -> ExperimentMetricRecord:
    record: ExperimentMetricRecord = {
        "metric_name": metric.metric_name,
        "variant": metric.variant,
        "value": metric.value,
    }
    unit = _metadata_str(metric.metadata, "unit")
    if unit:
        record["unit"] = unit
    numerator = _metadata_float(metric.metadata, "numerator")
    if numerator is not None:
        record["numerator"] = numerator
    denominator = _metadata_float(metric.metadata, "denominator")
    if denominator is not None:
        record["denominator"] = denominator
    notes = _metadata_str(metric.metadata, "notes")
    if notes:
        record["notes"] = notes
    lift_vs_control = _metadata_float(metric.metadata, "lift_vs_control")
    if lift_vs_control is not None:
        record["lift_vs_control"] = lift_vs_control
    p_value = _metadata_float(metric.metadata, "p_value")
    if p_value is not None:
        record["p_value"] = p_value
    return record


def _metadata_float(metadata: dict[str, object], key: str) -> float | None:
    value = metadata.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _metadata_str(metadata: dict[str, object], key: str) -> str:
    value = metadata.get(key)
    if value is None:
        return ""
    return str(value)


def _maybe_uuid(value: str) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _normalize_text(value: str) -> str:
    return " ".join(str(value).strip().lower().split())
