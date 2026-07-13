from pathlib import Path


def test_docker_compose_defines_pgvector_postgres_service() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "postgres:" in compose
    assert "image: pgvector/pgvector:pg16" in compose
    assert "POSTGRES_DB: experimentos" in compose
    assert "POSTGRES_USER: experimentos" in compose
    assert "POSTGRES_PASSWORD: experimentos" in compose
    assert '"5433:5432"' in compose
    assert "pgdata:/var/lib/postgresql/data" in compose
    assert "pg_isready -U experimentos -d experimentos" in compose
    assert "volumes:" in compose


def test_env_example_database_url_matches_compose_credentials() -> None:
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert (
        "DATABASE_URL=postgresql+psycopg://experimentos:experimentos@localhost:5433/experimentos"
    ) in env_example
