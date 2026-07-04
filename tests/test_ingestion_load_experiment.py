from __future__ import annotations

import csv
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

from packages.db.models import Document, Experiment, ExperimentMetric


def write_sample_experiment(experiment_dir: Path) -> None:
    experiment_dir.mkdir()
    metadata = {
        "experiment_id": "exp-test-ingestion",
        "name": "Ingestion Pipeline Test",
        "area": "test area",
        "hypothesis": "Loading synthetic experiment files stores the expected database rows.",
        "owner": {"name": "Test Owner", "team": "Data Platform"},
        "status": "completed",
        "start_date": "2026-01-01",
        "end_date": "2026-01-07",
        "variants": [
            {"name": "control", "description": "Existing experience."},
            {"name": "treatment", "description": "New experience."},
        ],
        "primary_metric": "conversion_rate",
        "secondary_metrics": ["sample_size"],
        "imperfections": ["Small synthetic sample."],
        "business_decision": "Use for ingestion tests.",
    }
    (experiment_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    with (experiment_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "experiment_id",
                "metric_name",
                "variant",
                "value",
                "unit",
                "numerator",
                "denominator",
                "lift_vs_control",
                "p_value",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "experiment_id": "exp-test-ingestion",
                    "metric_name": "sample_size",
                    "variant": "control",
                    "value": "10",
                    "unit": "users",
                    "numerator": "10",
                    "denominator": "10",
                    "lift_vs_control": "0.0000",
                    "p_value": "",
                    "notes": "Control assignment count.",
                },
                {
                    "experiment_id": "exp-test-ingestion",
                    "metric_name": "conversion_rate",
                    "variant": "treatment",
                    "value": "0.42",
                    "unit": "rate",
                    "numerator": "4",
                    "denominator": "10",
                    "lift_vs_control": "0.1000",
                    "p_value": "0.050",
                    "notes": "Treatment primary metric.",
                },
            ]
        )

    (experiment_dir / "report.md").write_text(
        "# Ingestion Pipeline Test\n\nThis report is intentionally short but non-empty.\n",
        encoding="utf-8",
    )


def test_missing_metadata_fails(tmp_path: Path) -> None:
    from packages.ingestion.load_experiment import IngestionInputError, load_experiment_files

    experiment_dir = tmp_path / "exp-missing-metadata"
    experiment_dir.mkdir()
    (experiment_dir / "metrics.csv").write_text(
        "experiment_id,metric_name,variant,value\nexp-missing-metadata,sample_size,control,10\n",
        encoding="utf-8",
    )
    (experiment_dir / "report.md").write_text("Non-empty report.", encoding="utf-8")

    with pytest.raises(IngestionInputError, match="metadata.json is required"):
        load_experiment_files(experiment_dir)


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL is required")
def test_valid_experiment_folder_ingests_successfully(tmp_path: Path) -> None:
    from packages.db.session import create_async_session_factory, create_database_engine
    from packages.ingestion.load_experiment import ingest_experiment_dir, run_async

    experiment_dir = tmp_path / "exp-test-ingestion"
    write_sample_experiment(experiment_dir)

    async def run_test() -> None:
        engine = create_database_engine()
        session_factory = create_async_session_factory(engine)
        try:
            async with session_factory() as session:
                await session.execute(
                    delete(Experiment).where(Experiment.name == "Ingestion Pipeline Test")
                )
                await session.commit()

            result = await ingest_experiment_dir(experiment_dir, session_factory)

            async with session_factory() as session:
                experiment_id = await session.scalar(
                    select(Experiment.id).where(Experiment.name == "Ingestion Pipeline Test")
                )
                metric_count = await session.scalar(
                    select(func.count())
                    .select_from(ExperimentMetric)
                    .where(ExperimentMetric.experiment_id == experiment_id)
                )
                document_count = await session.scalar(
                    select(func.count())
                    .select_from(Document)
                    .where(Document.experiment_id == experiment_id)
                )
                await session.execute(
                    delete(Experiment).where(Experiment.name == "Ingestion Pipeline Test")
                )
                await session.commit()
        finally:
            await engine.dispose()

        assert result.metrics_inserted == 2
        assert result.document_inserted is True
        assert metric_count == 2
        assert document_count == 1

    run_async(run_test())


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL is required")
def test_repeated_ingestion_does_not_duplicate_rows(tmp_path: Path) -> None:
    from packages.db.session import create_async_session_factory, create_database_engine
    from packages.ingestion.load_experiment import ingest_experiment_dir, run_async

    experiment_dir = tmp_path / "exp-test-ingestion"
    write_sample_experiment(experiment_dir)

    async def run_test() -> None:
        engine = create_database_engine()
        session_factory = create_async_session_factory(engine)
        try:
            async with session_factory() as session:
                await session.execute(
                    delete(Experiment).where(Experiment.name == "Ingestion Pipeline Test")
                )
                await session.commit()

            first = await ingest_experiment_dir(experiment_dir, session_factory)
            second = await ingest_experiment_dir(experiment_dir, session_factory)

            async with session_factory() as session:
                experiment_id = await session.scalar(
                    select(Experiment.id).where(Experiment.name == "Ingestion Pipeline Test")
                )
                experiment_count = await session.scalar(
                    select(func.count())
                    .select_from(Experiment)
                    .where(Experiment.name == "Ingestion Pipeline Test")
                )
                metric_count = await session.scalar(
                    select(func.count())
                    .select_from(ExperimentMetric)
                    .where(ExperimentMetric.experiment_id == experiment_id)
                )
                document_count = await session.scalar(
                    select(func.count())
                    .select_from(Document)
                    .where(Document.experiment_id == experiment_id)
                )
                await session.execute(
                    delete(Experiment).where(Experiment.name == "Ingestion Pipeline Test")
                )
                await session.commit()
        finally:
            await engine.dispose()

        assert first.replaced_existing is False
        assert second.replaced_existing is True
        assert experiment_count == 1
        assert metric_count == 2
        assert document_count == 1

    run_async(run_test())
