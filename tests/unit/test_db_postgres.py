"""Kiểm thử lớp Database Dual-Engine cho PostgreSQL (không silent fallback, dịch SQL, chuẩn hoá datetime)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pytest

from backend.config import Settings
from backend.database.db import Database


def test_postgres_unreachable_raises_error_without_silent_fallback():
    """Khi cấu hình DB_BACKEND=postgres nhưng PostgreSQL không chạy, phải báo lỗi rõ ràng, KHÔNG âm thầm rơi về SQLite."""
    s = Settings()
    s.db_backend = "postgres"
    s.database_url = "postgresql://postgres:postgres@127.0.0.1:59999/smartcart_nonexistent"
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        Database.from_settings(s)


def test_pg_sql_translation_and_datetime_normalization():
    """Kiểm tra chuyển đổi placeholder '?' -> '%s' và chuẩn hoá TIMESTAMPTZ sang chuỗi ISO UTC."""
    db = Database(":memory:", backend="sqlite")
    try:
        assert db._to_pg_sql("SELECT * FROM products WHERE id=? AND active=?") == "SELECT * FROM products WHERE id=%s AND active=%s"

        tz_plus7 = timezone(timedelta(hours=7))
        dt_local = datetime(2026, 11, 17, 17, 30, 0, tzinfo=tz_plus7)
        dt_naive = datetime(2026, 11, 17, 10, 30, 0)
        norm = db._normalize_row({"id": 1, "created_at": dt_local, "last_seen": dt_naive, "name": "Xe 1"})
        assert norm["created_at"] == "2026-11-17T10:30:00Z"
        assert norm["last_seen"] == "2026-11-17T10:30:00Z"
        assert norm["name"] == "Xe 1"
    finally:
        db.close()
