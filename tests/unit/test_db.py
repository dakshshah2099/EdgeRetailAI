from pathlib import Path

from storage.db import get_connection, init_db


def test_init_db_creates_all_expected_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "test_retail.db"
    init_db(db_path)

    assert db_path.exists()
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    expected_tables = {
        "detection_events",
        "dwell_events",
        "stock_events",
        "queue_events",
        "alerts",
    }
    assert expected_tables.issubset(tables)


def test_init_db_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test_retail.db"
    init_db(db_path)
    # Calling second time on same path should not raise or recreate tables
    init_db(db_path)

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]
    conn.close()

    assert len(tables) == 5


def test_init_db_creates_parent_directories(tmp_path: Path) -> None:
    nested_db_path = tmp_path / "nested" / "deep" / "retail.db"
    assert not nested_db_path.parent.exists()
    init_db(nested_db_path)
    assert nested_db_path.exists()


def test_structural_no_pii_or_raw_imagery_columns(tmp_path: Path) -> None:
    """Structural test: ensures no table schema contains columns for raw images, frames, or PII."""
    forbidden_substrings = {
        "image",
        "frame",
        "face",
        "embedding",
        "raw",
        "pixels",
        "crop",
    }
    db_path = tmp_path / "test_retail.db"
    init_db(db_path)

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]

    assert len(tables) == 5

    for table_name in tables:
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [row[1] for row in cursor.fetchall()]
        for col in columns:
            for forbidden in forbidden_substrings:
                assert forbidden not in col.lower(), (
                    f"Forbidden PII/image column '{col}' found in table '{table_name}'"
                )
    conn.close()
