from pathlib import Path

import pytest

from storage.db import get_connection, init_db

pytestmark = pytest.mark.slice_7
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
        "audit_logs",
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

    assert len(tables) == 6


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

    assert len(tables) == 6

    for table_name in tables:
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = [row[1] for row in cursor.fetchall()]
        for col in columns:
            for forbidden in forbidden_substrings:
                assert forbidden not in col.lower(), (
                    f"Forbidden PII/image column '{col}' found in table '{table_name}'"
                )
    conn.close()


def test_throwaway_database_isolation_prevents_production_db_access() -> None:
    """Ensure tests strictly use a throwaway database and never touch backend/retail.db."""
    from api.dependencies import get_db_path
    backend_dir = Path(__file__).resolve().parent.parent.parent
    prod_db = (backend_dir / "retail.db").resolve()

    resolved_db = get_db_path().resolve()
    assert resolved_db != prod_db, "get_db_path() returned production retail.db during testing!"
    assert "pytest" in str(resolved_db) or "tmp" in str(resolved_db)

    # Test connecting via literal 'retail.db' safely redirects to throwaway
    conn = get_connection("retail.db")
    try:
        # Check attached database filename
        cursor = conn.cursor()
        cursor.execute("PRAGMA database_list;")
        row = cursor.fetchone()
        attached_path = Path(row[2]).resolve()
        assert attached_path != prod_db, "get_connection('retail.db') opened production retail.db!"
        assert "pytest" in str(attached_path) or "tmp" in str(attached_path)
    finally:
        conn.close()

