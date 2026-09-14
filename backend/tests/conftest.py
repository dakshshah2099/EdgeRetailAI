from collections.abc import Generator
from pathlib import Path

import pytest

import api.env_manager as em
from storage.db import init_db


@pytest.fixture(autouse=True)
def isolate_test_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[None, None, None]:
    """Ensure all unit and e2e tests write to an isolated temporary database and .env,

    preventing test telemetry, alerts, and reconfigurations from leaking into the workspace.
    """
    test_db = tmp_path / "test_isolated_suite.db"
    init_db(test_db)
    monkeypatch.setenv("DATABASE_PATH", str(test_db))

    test_env = tmp_path / ".env"
    real_env = em.BACKEND_DIR / ".env"
    if real_env.is_file():
        test_env.write_text(real_env.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        test_env.write_text("DEBUG_MODE=false\n", encoding="utf-8")

    monkeypatch.setenv("ENV_PATH", str(test_env))
    monkeypatch.setattr("api.env_manager.ENV_PATH", test_env)
    monkeypatch.setattr("api.env_manager.get_default_env_path", lambda: test_env)

    em._cached_env_mtime = -1.0
    em._cached_env = {}
    em._cached_env_path = None

    yield
