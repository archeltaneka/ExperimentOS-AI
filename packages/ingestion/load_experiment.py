from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import logging
import selectors
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.config.env import load_environment
from packages.db.models import Document, DocumentChunk, Experiment, ExperimentMetric
from packages.db.session import create_async_session_factory, create_database_engine
from packages.ingestion.chunking import chunk_markdown_report
from packages.ingestion.embeddings import build_embedding_provider

LOGGER = logging.getLogger(__name__)

REQUIRED_METRIC_COLUMNS = {
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
}


class IngestionInputError(ValueError):
    pass


class OwnerMetadata(BaseModel):
    name: str
    team: str


class ExperimentMetadata(BaseModel):
    experiment_id: str
    name: str
    area: str
    hypothesis: str
    owner: OwnerMetadata
    status: str
    start_date: str
    end_date: str
    variants: list[dict[str, Any]]
    primary_metric: str
    secondary_metrics: list[str]
    imperfections: list[str]
    business_decision: str


@dataclass(frozen=True)
class MetricInput:
    metric_name: str
    variant: str
    value: float
    metadata: dict[str, Any]

    @property
    def storage_name(self) -> str:
        return f"{self.metric_name}:{self.variant}"


@dataclass(frozen=True)
class ExperimentInput:
    experiment_dir: Path
    metadata: ExperimentMetadata
    metadata_raw: dict[str, Any]
    metrics: list[MetricInput]
    report_content: str


@dataclass(frozen=True)
class IngestionResult:
    experiment_name: str
    metrics_inserted: int
    document_inserted: bool
    chunks_inserted: int
    replaced_existing: bool


def _read_metadata(path: Path) -> tuple[ExperimentMetadata, dict[str, Any]]:
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise IngestionInputError(f"Unable to read metadata.json: {exc}") from exc

    try:
        metadata = ExperimentMetadata.model_validate_json(raw_text)
    except ValidationError as exc:
        raise IngestionInputError(f"metadata.json validation failed:\n{exc}") from exc

    return metadata, metadata.model_dump(mode="json")


def _read_metrics(path: Path, experiment_id: str) -> list[MetricInput]:
    try:
        with path.open(newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            columns = set(reader.fieldnames or [])
            missing = sorted(REQUIRED_METRIC_COLUMNS - columns)
            if missing:
                raise IngestionInputError(
                    "metrics.csv is missing required columns: " + ", ".join(missing)
                )

            metrics: list[MetricInput] = []
            for line_number, row in enumerate(reader, start=2):
                row_experiment_id = (row.get("experiment_id") or "").strip()
                metric_name = (row.get("metric_name") or "").strip()
                variant = (row.get("variant") or "").strip()
                raw_value = (row.get("value") or "").strip()

                if row_experiment_id != experiment_id:
                    raise IngestionInputError(
                        "metrics.csv line "
                        f"{line_number} has experiment_id {row_experiment_id!r}; "
                        f"expected {experiment_id!r}"
                    )
                if not metric_name:
                    raise IngestionInputError(
                        f"metrics.csv line {line_number} has empty metric_name"
                    )
                if not variant:
                    raise IngestionInputError(f"metrics.csv line {line_number} has empty variant")

                try:
                    value = float(raw_value)
                except ValueError as exc:
                    raise IngestionInputError(
                        f"metrics.csv line {line_number} has non-numeric value {raw_value!r}"
                    ) from exc

                metrics.append(
                    MetricInput(
                        metric_name=metric_name,
                        variant=variant,
                        value=value,
                        metadata={key: value for key, value in row.items() if key is not None},
                    )
                )
    except OSError as exc:
        raise IngestionInputError(f"Unable to read metrics.csv: {exc}") from exc

    if not metrics:
        raise IngestionInputError("metrics.csv must contain at least one metric row")

    metric_names = [metric.storage_name for metric in metrics]
    if len(metric_names) != len(set(metric_names)):
        raise IngestionInputError("metrics.csv contains duplicate metric_name/variant rows")

    return metrics


def _read_report(path: Path) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise IngestionInputError(f"Unable to read report.md: {exc}") from exc

    if not content.strip():
        raise IngestionInputError("report.md must be non-empty")

    return content


def load_experiment_files(experiment_dir: Path) -> ExperimentInput:
    experiment_dir = experiment_dir.resolve()
    if not experiment_dir.is_dir():
        raise IngestionInputError(f"Experiment directory does not exist: {experiment_dir}")

    metadata_path = experiment_dir / "metadata.json"
    metrics_path = experiment_dir / "metrics.csv"
    report_path = experiment_dir / "report.md"

    if not metadata_path.is_file():
        raise IngestionInputError(f"metadata.json is required at {metadata_path}")
    if not metrics_path.is_file():
        raise IngestionInputError(f"metrics.csv is required at {metrics_path}")
    if not report_path.is_file():
        raise IngestionInputError(f"report.md is required at {report_path}")

    metadata, metadata_raw = _read_metadata(metadata_path)
    return ExperimentInput(
        experiment_dir=experiment_dir,
        metadata=metadata,
        metadata_raw=metadata_raw,
        metrics=_read_metrics(metrics_path, metadata.experiment_id),
        report_content=_read_report(report_path),
    )


def _document_title(report_content: str, fallback: str) -> str:
    for line in report_content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped.removeprefix("# ").strip() or fallback
    return fallback


async def ingest_experiment_dir(
    experiment_dir: Path,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    embedding_provider: str = "auto",
    skip_embeddings: bool = False,
) -> IngestionResult:
    experiment_input = load_experiment_files(experiment_dir)
    metadata = experiment_input.metadata
    chunks = chunk_markdown_report(experiment_input.report_content)
    provider = None if skip_embeddings else build_embedding_provider(embedding_provider)
    embeddings = (
        [None] * len(chunks)
        if provider is None
        else provider.embed_texts([chunk.text for chunk in chunks])
    )

    async with session_factory() as session:
        async with session.begin():
            experiment = await session.scalar(
                select(Experiment).where(Experiment.name == metadata.name)
            )
            replaced_existing = experiment is not None

            if experiment is None:
                experiment = Experiment(
                    name=metadata.name,
                    description=metadata.hypothesis,
                    config=experiment_input.metadata_raw,
                    status=metadata.status,
                )
                session.add(experiment)
                await session.flush()
            else:
                experiment.description = metadata.hypothesis
                experiment.config = experiment_input.metadata_raw
                experiment.status = metadata.status
                await session.execute(
                    delete(Document).where(Document.experiment_id == experiment.id)
                )
                await session.execute(
                    delete(ExperimentMetric).where(ExperimentMetric.experiment_id == experiment.id)
                )

            for metric in experiment_input.metrics:
                session.add(
                    ExperimentMetric(
                        experiment_id=experiment.id,
                        name=metric.storage_name,
                        value=metric.value,
                        metric_metadata=metric.metadata,
                    )
                )

            report_path = experiment_input.experiment_dir / "report.md"
            document = Document(
                experiment_id=experiment.id,
                source_uri=str(report_path),
                source_type="markdown",
                title=_document_title(experiment_input.report_content, metadata.name),
                content=experiment_input.report_content,
                content_hash=hashlib.sha256(
                    experiment_input.report_content.encode("utf-8")
                ).hexdigest(),
                document_metadata={
                    "experiment_id": metadata.experiment_id,
                    "filename": "report.md",
                },
            )
            session.add(document)
            await session.flush()
            await session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
            )

            for chunk, embedding in zip(chunks, embeddings, strict=True):
                session.add(
                    DocumentChunk(
                        document_id=document.id,
                        chunk_index=int(chunk.metadata["chunk_index"]),
                        chunk_text=chunk.text,
                        token_count=chunk.token_count,
                        embedding=embedding,
                        chunk_metadata=dict(chunk.metadata),
                    )
                )

    if replaced_existing:
        LOGGER.info("Replaced existing records for experiment: %s", metadata.name)
    LOGGER.info("Experiment loaded: %s", metadata.name)
    LOGGER.info("Metrics rows inserted: %s", len(experiment_input.metrics))
    LOGGER.info("Document inserted: report.md")
    LOGGER.info("Document chunks inserted: %s", len(chunks))

    return IngestionResult(
        experiment_name=metadata.name,
        metrics_inserted=len(experiment_input.metrics),
        document_inserted=True,
        chunks_inserted=len(chunks),
        replaced_existing=replaced_existing,
    )


async def _run_cli(
    experiment_dir: Path,
    *,
    embedding_provider: str,
    skip_embeddings: bool,
) -> IngestionResult:
    engine = create_database_engine()
    session_factory = create_async_session_factory(engine)
    try:
        return await ingest_experiment_dir(
            experiment_dir,
            session_factory,
            embedding_provider=embedding_provider,
            skip_embeddings=skip_embeddings,
        )
    finally:
        await engine.dispose()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load a synthetic experiment into the database.")
    parser.add_argument(
        "--experiment-dir",
        required=True,
        type=Path,
        help=(
            "Path to a synthetic experiment folder containing metadata.json, metrics.csv, "
            "and report.md."
        ),
    )
    parser.add_argument(
        "--embedding-provider",
        choices=("auto", "fake", "openai", "gemini", "huggingface", "ollama"),
        default="auto",
        help=(
            "Embedding provider to use. 'auto' uses Gemini when GEMINI_API_KEY is set, "
            "OpenAI when OPENAI_API_KEY is set, otherwise deterministic fake embeddings. "
            "'gemini' uses gemini-embedding-001 by default. 'huggingface' uses "
            "BAAI/bge-small-en-v1.5. 'ollama' uses nomic-embed-text."
        ),
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Store chunks with NULL embeddings.",
    )
    return parser.parse_args(argv)


def run_async(coro: Any) -> Any:
    if sys.platform == "win32":
        return asyncio.run(
            coro,
            loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
        )
    return asyncio.run(coro)


def main() -> None:
    load_environment()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    try:
        run_async(
            _run_cli(
                args.experiment_dir,
                embedding_provider=args.embedding_provider,
                skip_embeddings=args.skip_embeddings,
            )
        )
    except IngestionInputError as exc:
        raise SystemExit(f"Input error: {exc}") from exc


if __name__ == "__main__":
    main()
