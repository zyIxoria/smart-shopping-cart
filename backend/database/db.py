"""Lớp truy cập cơ sở dữ liệu hỗ trợ cả PostgreSQL 16 và SQLite.

- PostgreSQL 16 (khuyến nghị cho Production/Docker): kết nối qua psycopg 3 (dict_row).
- SQLite (mặc định cho DEV cục bộ / unit tests): 1 connection dùng chung + RLock.

Đảm bảo an toàn giao dịch (ACID), re-entrant tx(), idempotency và kiểm soát lỗi rõ ràng.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("db")

SCHEMA_SQLITE = Path(__file__).with_name("schema.sql")
SCHEMA_POSTGRES = Path(__file__).with_name("schema_postgres.sql")


class Database:
    def __init__(
        self,
        path: str = ":memory:",
        backend: str = "sqlite",
        dsn: str | None = None,
    ):
        self.backend = backend.lower()
        self.lock = threading.RLock()
        self.is_postgres = self.backend == "postgres"

        if self.is_postgres:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as e:
                raise RuntimeError(
                    "Đã cấu hình DB_BACKEND=postgres nhưng thiếu thư viện 'psycopg'. "
                    "Hãy cài đặt: pip install 'psycopg[binary]'"
                ) from e

            self.dsn = dsn or "postgresql://postgres:postgres@localhost:5432/smartcart"
            try:
                self._conn = psycopg.connect(self.dsn, autocommit=True, row_factory=dict_row)
                log.info("Kết nối thành công PostgreSQL 16: %s", self.dsn.split("@")[-1])
            except Exception as e:
                raise RuntimeError(
                    f"Không thể kết nối tới cơ sở dữ liệu PostgreSQL ({self.dsn}). "
                    "Vui lòng kiểm tra dịch vụ PostgreSQL đang chạy: " + str(e)
                ) from e
        else:
            self.path = path
            if path != ":memory:":
                Path(path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            if path != ":memory:":
                self._conn.execute("PRAGMA journal_mode = WAL")

    @classmethod
    def from_settings(cls, settings) -> "Database":
        """Khởi tạo từ đối tượng cấu hình Settings."""
        db_backend = getattr(settings, "db_backend", "sqlite").lower()
        db_url = getattr(settings, "database_url", "")
        explicit_sqlite = os.getenv("DB_BACKEND", "").lower() == "sqlite" or db_backend == "sqlite" and not db_url
        if db_backend == "postgres" or (db_url and not explicit_sqlite):
            dsn = db_url or (
                f"postgresql://{settings.postgres_user}:{settings.postgres_password}@"
                f"{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
            )
            return cls(backend="postgres", dsn=dsn)
        return cls(path=settings.db_path, backend="sqlite")

    def _to_pg_sql(self, sql: str) -> str:
        """Chuyển đổi placeholder '?' của SQLite sang '%s' của PostgreSQL."""
        return sql.replace("?", "%s")

    @staticmethod
    def _normalize_row(row: Any) -> dict:
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, datetime):
                dt = v if v.tzinfo else v.replace(tzinfo=timezone.utc)
                d[k] = dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return d

    def init_schema(self) -> None:
        """Khởi tạo bảng, ràng buộc và chỉ mục."""
        with self.lock:
            if self.is_postgres:
                schema_text = SCHEMA_POSTGRES.read_text(encoding="utf-8")
                # psycopg tách script hoặc thực thi khối lệnh
                with self._conn.cursor() as cur:
                    cur.execute(schema_text)
                log.info("Khởi tạo schema PostgreSQL 16 thành công.")
            else:
                schema_text = SCHEMA_SQLITE.read_text(encoding="utf-8")
                self._conn.executescript(schema_text)

    @contextmanager
    def tx(self):
        """Giao dịch: commit nếu thành công, rollback nếu có exception. Re-entrant."""
        with self.lock:
            if self.is_postgres:
                with self._conn.transaction():
                    yield self
            else:
                nested = self._conn.in_transaction
                if not nested:
                    self._conn.execute("BEGIN IMMEDIATE")
                try:
                    yield self
                except BaseException:
                    if not nested:
                        self._conn.execute("ROLLBACK")
                    raise
                else:
                    if not nested:
                        self._conn.execute("COMMIT")

    def execute(self, sql: str, params: tuple = ()) -> Any:
        with self.lock:
            if self.is_postgres:
                return self._conn.execute(self._to_pg_sql(sql), params)
            return self._conn.execute(sql, params)

    def one(self, sql: str, params: tuple = ()) -> dict | None:
        with self.lock:
            if self.is_postgres:
                cur = self._conn.execute(self._to_pg_sql(sql), params)
                r = cur.fetchone()
                return self._normalize_row(r) if r else None
            r = self._conn.execute(sql, params).fetchone()
            return dict(r) if r else None

    def all(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.lock:
            if self.is_postgres:
                cur = self._conn.execute(self._to_pg_sql(sql), params)
                return [self._normalize_row(r) for r in cur.fetchall()]
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def insert(self, sql: str, params: tuple = ()) -> int:
        with self.lock:
            if self.is_postgres:
                pg_sql = self._to_pg_sql(sql)
                if "RETURNING" not in pg_sql.upper():
                    if "smart_carts" in pg_sql.lower():
                        self._conn.execute(pg_sql, params)
                        return 0
                    pg_sql += " RETURNING id"
                cur = self._conn.execute(pg_sql, params)
                row = cur.fetchone()
                return row["id"] if row and "id" in row else 0
            return self._conn.execute(sql, params).lastrowid

    def close(self) -> None:
        with self.lock:
            self._conn.close()
