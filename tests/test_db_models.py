from pgvector.sqlalchemy import VECTOR
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint

from packages.db.models import EMBEDDING_DIMENSION, Base, Document, Experiment


def test_model_metadata_includes_core_domain_tables() -> None:
    assert set(Base.metadata.tables) == {
        "documents",
        "document_chunks",
        "experiments",
        "experiment_metrics",
    }


def test_experiment_relationships_include_metrics_and_documents() -> None:
    assert Experiment.metrics.property.mapper.class_.__tablename__ == "experiment_metrics"
    assert Experiment.documents.property.mapper.class_.__tablename__ == "documents"


def test_document_relationships_include_experiment_and_chunks() -> None:
    assert Document.experiment.property.mapper.class_.__tablename__ == "experiments"
    assert Document.chunks.property.mapper.class_.__tablename__ == "document_chunks"


def test_documents_reference_experiments() -> None:
    documents = Base.metadata.tables["documents"]

    foreign_keys = [
        constraint
        for constraint in documents.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert len(foreign_keys) == 1
    assert [element.target_fullname for element in foreign_keys[0].elements] == ["experiments.id"]


def test_document_chunks_reference_documents_and_are_ordered_per_document() -> None:
    chunks = Base.metadata.tables["document_chunks"]

    foreign_keys = [
        constraint
        for constraint in chunks.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert len(foreign_keys) == 1
    assert [element.target_fullname for element in foreign_keys[0].elements] == ["documents.id"]

    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in chunks.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("document_id", "chunk_index") in unique_constraints

    embedding = chunks.c.embedding.type
    assert isinstance(embedding, VECTOR)
    assert embedding.dim == EMBEDDING_DIMENSION == 1536


def test_experiment_metrics_reference_experiments() -> None:
    metrics = Base.metadata.tables["experiment_metrics"]

    foreign_keys = [
        constraint
        for constraint in metrics.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    assert len(foreign_keys) == 1
    assert [element.target_fullname for element in foreign_keys[0].elements] == ["experiments.id"]

    unique_constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in metrics.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("experiment_id", "name") in unique_constraints
