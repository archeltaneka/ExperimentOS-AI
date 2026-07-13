from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from apps.api.main import app, get_observability_provider
from packages.db.models import Experiment
from packages.llm.client import MockLLMClient


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL is required")
def test_ask_endpoint_legacy_rag_uses_real_database_retrieval(tmp_path: Path, monkeypatch) -> None:
    from packages.db.session import create_async_session_factory, create_database_engine
    from packages.ingestion.load_experiment import ingest_experiment_dir, run_async

    experiment_dir = tmp_path / "exp-api-ask"
    experiment_dir.mkdir()
    (experiment_dir / "metadata.json").write_text(
        '{"experiment_id":"exp-api-ask","name":"API Ask Integration","area":"payments",'
        '"hypothesis":"test","owner":{"name":"Test Owner","team":"Platform"},'
        '"status":"completed","start_date":"2026-01-01","end_date":"2026-01-02",'
        '"variants":[{"name":"control","description":"old"},{"name":"treatment",'
        '"description":"new"}],"primary_metric":"conversion_rate",'
        '"secondary_metrics":["sample_size"],"imperfections":["synthetic"],'
        '"business_decision":"Roll out to clean markets."}',
        encoding="utf-8",
    )
    (experiment_dir / "metrics.csv").write_text(
        "experiment_id,metric_name,variant,value,unit,numerator,denominator,lift_vs_control,"
        "p_value,notes\n"
        "exp-api-ask,conversion_rate,treatment,0.73,rate,73,100,0.08,0.02,"
        "Primary metric improved.\n",
        encoding="utf-8",
    )
    (experiment_dir / "report.md").write_text(
        "# API Ask Integration\n\n"
        "## Recommendation\n"
        "Roll out to clean markets while monitoring wallet telemetry.\n",
        encoding="utf-8",
    )

    async def run_test() -> None:
        engine = create_database_engine()
        session_factory = create_async_session_factory(engine)
        try:
            async with session_factory() as session:
                await session.execute(
                    delete(Experiment).where(Experiment.name == "API Ask Integration")
                )
                await session.commit()

            await ingest_experiment_dir(experiment_dir, session_factory, embedding_provider="fake")

            async with session_factory() as session:
                experiment_id = await session.scalar(
                    select(Experiment.id).where(Experiment.name == "API Ask Integration")
                )

            get_observability_provider.cache_clear()
            get_observability_provider()
            monkeypatch.setenv("ASK_MODE", "legacy_rag")
            monkeypatch.setenv("EMBEDDING_PROVIDER", "fake")
            monkeypatch.setenv("LLM_PROVIDER", "mock")
            monkeypatch.setattr(
                "apps.api.main.get_llm_client",
                lambda: MockLLMClient(answer="Roll out to clean markets."),
            )

            client = TestClient(app)
            response = client.post(
                "/ask",
                json={
                    "question": "Why did the experiment ship?",
                    "experiment_id": str(experiment_id),
                    "top_k": 3,
                },
            )

            assert response.status_code == 200
            assert "Roll out" in response.json()["answer"]
            assert response.json()["prompt_metadata"] == {
                "prompt_id": "rag.answer",
                "prompt_version": "1",
            }
            assert response.json()["citations"]
            retrieved_chunks = response.json()["retrieved_chunks"]
            assert retrieved_chunks
            assert any("wallet telemetry" in chunk["chunk_text"] for chunk in retrieved_chunks)
        finally:
            async with session_factory() as session:
                await session.execute(
                    delete(Experiment).where(Experiment.name == "API Ask Integration")
                )
                await session.commit()
            await engine.dispose()

    run_async(run_test())
