from packages.db.session import get_database_url


def test_database_url_loads_from_dotenv_and_overrides_shell(monkeypatch, tmp_path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "DATABASE_URL=postgresql+psycopg://from-file:pass@localhost:5433/app\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://from-shell:pass@localhost:5432/app",
    )

    assert get_database_url() == "postgresql+psycopg://from-file:pass@localhost:5433/app"
