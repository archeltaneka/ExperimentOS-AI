import importlib.util
from pathlib import Path

from packages.db.models import Base


def test_alembic_env_uses_model_metadata_for_autogenerate() -> None:
    env_path = Path("migrations/env.py")
    spec = importlib.util.spec_from_file_location("alembic_env", env_path)
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.target_metadata is Base.metadata


def test_alembic_uses_migrations_script_location() -> None:
    config = Path("alembic.ini").read_text()

    assert "script_location = migrations" in config
