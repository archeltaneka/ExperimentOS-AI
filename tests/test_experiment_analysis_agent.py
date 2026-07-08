from __future__ import annotations

from dataclasses import dataclass

from packages.agents.state import create_initial_state


@dataclass(frozen=True)
class StubExperimentRecord:
    database_id: str
    external_id: str
    name: str
    hypothesis: str
    primary_metric: str
    secondary_metrics: list[str]
    imperfections: list[str]
    metadata: dict[str, object]


@dataclass(frozen=True)
class StubStoredMetricRecord:
    metric_name: str
    variant: str
    value: float
    metadata: dict[str, object]


class StubExperimentAnalysisRepository:
    def __init__(
        self,
        *,
        experiments_by_identifier: dict[str, StubExperimentRecord],
        hint_matches: dict[str, list[StubExperimentRecord]] | None = None,
        metrics_by_experiment_id: dict[str, list[StubStoredMetricRecord]] | None = None,
        failure: Exception | None = None,
    ) -> None:
        self.experiments_by_identifier = experiments_by_identifier
        self.hint_matches = hint_matches or {}
        self.metrics_by_experiment_id = metrics_by_experiment_id or {}
        self.failure = failure

    @classmethod
    def success(cls) -> StubExperimentAnalysisRepository:
        experiment = StubExperimentRecord(
            database_id="db-exp-1",
            external_id="exp-001-payment-recommendation",
            name="Adaptive Payment Method Recommendation",
            hypothesis=(
                "Ranking locally preferred payment methods above generic card options "
                "will reduce checkout hesitation and raise successful payment completion."
            ),
            primary_metric="payment_success_rate",
            secondary_metrics=[
                "checkout_completion_rate",
                "payment_retry_rate",
            ],
            imperfections=[
                "Sample ratio mismatch from late allocation rule change in mobile web.",
                "Japan wallet success events were under-counted for the first 18 hours.",
            ],
            metadata={
                "area": "payment recommendation",
                "business_decision": (
                    "Roll out to AU, SG, and GB; hold JP pending wallet tracking "
                    "fix."
                ),
            },
        )
        metrics = [
            StubStoredMetricRecord(
                metric_name="payment_success_rate",
                variant="control",
                value=0.6760,
                metadata={
                    "unit": "rate",
                    "numerator": "46",
                    "denominator": "68",
                    "lift_vs_control": "0.0000",
                    "notes": "Primary decision metric.",
                },
            ),
            StubStoredMetricRecord(
                metric_name="payment_success_rate",
                variant="treatment",
                value=0.7310,
                metadata={
                    "unit": "rate",
                    "numerator": "57",
                    "denominator": "78",
                    "lift_vs_control": "0.0814",
                    "p_value": "0.041",
                    "notes": "Primary decision metric.",
                },
            ),
            StubStoredMetricRecord(
                metric_name="checkout_completion_rate",
                variant="control",
                value=0.6420,
                metadata={"unit": "rate", "lift_vs_control": "0.0000"},
            ),
            StubStoredMetricRecord(
                metric_name="checkout_completion_rate",
                variant="treatment",
                value=0.7010,
                metadata={
                    "unit": "rate",
                    "lift_vs_control": "0.0919",
                    "p_value": "0.052",
                },
            ),
            StubStoredMetricRecord(
                metric_name="payment_retry_rate",
                variant="control",
                value=0.1180,
                metadata={"unit": "rate", "lift_vs_control": "0.0000"},
            ),
            StubStoredMetricRecord(
                metric_name="payment_retry_rate",
                variant="treatment",
                value=0.0830,
                metadata={
                    "unit": "rate",
                    "lift_vs_control": "-0.2966",
                    "p_value": "0.083",
                },
            ),
        ]
        return cls(
            experiments_by_identifier={
                "db-exp-1": experiment,
                "exp-001-payment-recommendation": experiment,
            },
            hint_matches={"payment recommendation": [experiment]},
            metrics_by_experiment_id={"db-exp-1": metrics},
        )

    @classmethod
    def missing_primary_metric(cls) -> StubExperimentAnalysisRepository:
        repository = cls.success()
        repository.metrics_by_experiment_id["db-exp-1"] = [
            metric
            for metric in repository.metrics_by_experiment_id["db-exp-1"]
            if metric.metric_name != "payment_success_rate"
        ]
        return repository

    async def get_experiment(self, identifier: str) -> StubExperimentRecord | None:
        if self.failure is not None:
            raise self.failure
        return self.experiments_by_identifier.get(identifier)

    async def search_experiments_by_hint(self, hint: str) -> list[StubExperimentRecord]:
        if self.failure is not None:
            raise self.failure
        return list(self.hint_matches.get(hint, []))

    async def get_metrics(self, experiment_database_id: str) -> list[StubStoredMetricRecord]:
        if self.failure is not None:
            raise self.failure
        return list(self.metrics_by_experiment_id.get(experiment_database_id, []))


def test_experiment_analysis_agent_builds_analysis_for_known_experiment() -> None:
    from packages.agents.experiment_analysis_agent import ExperimentAnalysisAgent

    state = create_initial_state("Should we roll out the payment recommendation experiment?")
    state["required_agents"] = ["retrieval", "experiment_analysis"]
    state["experiment_context"] = {
        "experiment_ids": ["db-exp-1"],
        "filters": {"experiment_hints": ["payment recommendation"]},
    }
    state["citations"] = [
        {
            "document_id": "doc-1",
            "experiment_id": "db-exp-1",
            "quote": "Control recorded 0.6760 while treatment recorded 0.7310.",
            "section": "Results",
            "metadata": {"section": "Results"},
        }
    ]

    update = ExperimentAnalysisAgent(repository=StubExperimentAnalysisRepository.success()).run(
        state
    )

    assert update["experiment_analysis"]["status"] == "completed"
    assert (
        update["experiment_analysis"]["experiment_id"] == "exp-001-payment-recommendation"
    )
    assert (
        update["experiment_analysis"]["experiment_name"]
        == "Adaptive Payment Method Recommendation"
    )
    assert update["experiment_analysis"]["primary_metric"] == "payment_success_rate"
    assert update["experiment_analysis"]["control"]["value"] == 0.6760
    assert update["experiment_analysis"]["treatment"]["value"] == 0.7310
    assert update["experiment_analysis"]["treatment_control_comparison"]["absolute_delta"] == 0.055
    assert update["experiment_analysis"]["observed_lift"]["relative_lift"] == 0.0814
    assert update["experiment_analysis"]["statistical_significance"]["p_value"] == 0.041
    assert update["experiment_analysis"]["guardrail_metrics"][0]["metric_name"] == (
        "checkout_completion_rate"
    )
    assert update["experiment_analysis"]["evidence_citations"] == state["citations"]
    assert update["experiment_analysis"]["analysis_confidence"] == "high"
    assert update["experiment_metadata"]["primary_metric"] == "payment_success_rate"
    assert update["experiment_metrics"][0]["metric_name"] == "payment_success_rate"
    assert update["experiment_metrics"][0]["variant"] == "control"
    assert update["metrics"]["experiment_analysis"]["status"] == "completed"
    assert update["metrics"]["experiment_analysis"]["citation_count"] == 1
    assert [entry["event"] for entry in update["trace"]] == ["started", "completed"]


def test_experiment_analysis_agent_handles_missing_retrieval_context() -> None:
    from packages.agents.experiment_analysis_agent import ExperimentAnalysisAgent

    state = create_initial_state("Analyze this experiment.")
    state["required_agents"] = ["experiment_analysis"]
    state["experiment_context"] = {"experiment_ids": ["db-exp-1"], "filters": {}}

    update = ExperimentAnalysisAgent(repository=StubExperimentAnalysisRepository.success()).run(
        state
    )

    assert update["experiment_analysis"]["status"] == "completed"
    assert update["experiment_analysis"]["evidence_citations"] == []
    assert update["metrics"]["experiment_analysis"]["citation_count"] == 0


def test_experiment_analysis_agent_returns_insufficient_data_when_primary_metric_missing() -> None:
    from packages.agents.experiment_analysis_agent import ExperimentAnalysisAgent

    state = create_initial_state("Analyze this experiment.")
    state["required_agents"] = ["experiment_analysis"]
    state["experiment_context"] = {"experiment_ids": ["db-exp-1"], "filters": {}}

    update = ExperimentAnalysisAgent(
        repository=StubExperimentAnalysisRepository.missing_primary_metric()
    ).run(state)

    assert update["experiment_analysis"]["status"] == "insufficient_data"
    assert "primary metric" in update["experiment_analysis"]["summary"].lower()
    assert update["experiment_analysis"]["analysis_confidence"] == "low"
    assert update["metrics"]["experiment_analysis"]["status"] == "insufficient_data"


def test_experiment_analysis_agent_can_resolve_experiment_from_retrieval_evidence() -> None:
    from packages.agents.experiment_analysis_agent import ExperimentAnalysisAgent

    state = create_initial_state("Analyze what happened.")
    state["required_agents"] = ["experiment_analysis"]
    state["retrieved_chunks"] = [
        {
            "document_id": "doc-1",
            "experiment_id": "db-exp-1",
            "content": "Retrieved results chunk.",
            "score": 0.91,
            "metadata": {"section": "Results"},
        }
    ]

    update = ExperimentAnalysisAgent(repository=StubExperimentAnalysisRepository.success()).run(
        state
    )

    assert update["experiment_analysis"]["status"] == "completed"
    assert (
        update["experiment_analysis"]["experiment_id"] == "exp-001-payment-recommendation"
    )
    assert update["metrics"]["experiment_analysis"]["resolved_experiment_count"] == 1


def test_experiment_analysis_agent_captures_structured_errors_without_raising() -> None:
    from packages.agents.experiment_analysis_agent import ExperimentAnalysisAgent

    state = create_initial_state("Analyze what happened.")
    state["required_agents"] = ["experiment_analysis"]
    state["experiment_context"] = {"experiment_ids": ["db-exp-1"], "filters": {}}

    update = ExperimentAnalysisAgent(
        repository=StubExperimentAnalysisRepository(
            experiments_by_identifier={},
            failure=RuntimeError("database unavailable"),
        )
    ).run(state)

    assert update["errors"][0]["code"] == "experiment_analysis_failed"
    assert update["errors"][0]["node"] == "experiment_analysis"
    assert update["metrics"]["experiment_analysis"]["status"] == "failed"
    assert [entry["event"] for entry in update["trace"]] == ["started", "failed"]
