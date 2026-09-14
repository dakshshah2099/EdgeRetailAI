import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

import api.env_manager as em
from storage.db import init_db


def pytest_configure(config: pytest.Config) -> None:
    """Pre-collection initialization: ensure DATABASE_PATH points to a temporary throwaway DB."""
    session_db = Path(tempfile.gettempdir()) / "retail_pytest_session.db"
    init_db(session_db)
    os.environ["DATABASE_PATH"] = str(session_db)


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
    fixture_video = str(em.BACKEND_DIR / "tests/fixtures/sample_video.mp4")
    monkeypatch.setenv("CAMERA_SOURCE", fixture_video)

    if real_env.is_file():
        env_content = real_env.read_text(encoding="utf-8")
        lines = [
            line
            for line in env_content.splitlines()
            if not line.startswith("DATABASE_PATH=") and not line.startswith("CAMERA_SOURCE=")
        ]
        lines.append(f"DATABASE_PATH={test_db}")
        lines.append(f"CAMERA_SOURCE={fixture_video}")
        test_env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        test_env.write_text(
            f"DEBUG_MODE=false\nDATABASE_PATH={test_db}\nCAMERA_SOURCE={fixture_video}\n",
            encoding="utf-8",
        )

    monkeypatch.setenv("ENV_PATH", str(test_env))
    monkeypatch.setattr("api.env_manager.ENV_PATH", test_env)
    monkeypatch.setattr("api.env_manager.get_default_env_path", lambda: test_env)

    em._cached_env_mtime = -1.0
    em._cached_env = {}
    em._cached_env_path = None

    yield

    from api.stream_manager import stream_manager
    from vision.camera_mesh import camera_mesh

    stream_manager.stop()
    camera_mesh.close()
