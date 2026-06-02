"""
db.py — thin psycopg2 wrapper that mimics the sqlite3 Connection API.

Allows adaptive_engine.py to call conn.execute(sql, params).fetchall()
the same way it does with sqlite3, while using PostgreSQL under the hood.

Key behaviour:
- ? placeholders are rewritten to %s automatically
- Rows are returned as dict-like objects (RealDictRow) so row["col"] works
- with conn: acts as a transaction context (commit on success, rollback on error)
"""

from __future__ import annotations

import os
import psycopg2
import psycopg2.extras


class _PGCursor:
    """Wraps a psycopg2 cursor to match the sqlite3 cursor interface."""

    def __init__(self, cur: psycopg2.extensions.cursor) -> None:
        self._cur = cur

    def fetchall(self) -> list:
        try:
            return self._cur.fetchall() or []
        except psycopg2.ProgrammingError:
            return []

    def fetchone(self):
        try:
            return self._cur.fetchone()
        except psycopg2.ProgrammingError:
            return None

    # Expose rowcount so callers can check affected rows
    @property
    def rowcount(self) -> int:
        return self._cur.rowcount


class PGConn:
    """
    sqlite3-compatible wrapper around a psycopg2 connection.

    Usage is identical to sqlite3.Connection:
        conn.execute(sql, params).fetchall()
        with conn:
            conn.execute(insert_sql, params)
    """

    def __init__(self, dsn: str) -> None:
        self._conn = psycopg2.connect(
            dsn, cursor_factory=psycopg2.extras.RealDictCursor
        )

    # ── sqlite3-compatible execute ────────────────────────────────────────
    def execute(self, sql: str, params=()) -> _PGCursor:
        # sqlite3 uses ? placeholders; psycopg2 uses %s
        sql = sql.replace("?", "%s")
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return _PGCursor(cur)

    # ── Transaction context manager (same semantics as sqlite3) ──────────
    def __enter__(self) -> "PGConn":
        # psycopg2 is always in a transaction; __enter__ is a no-op here
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        return False  # don't suppress exceptions

    def close(self) -> None:
        self._conn.close()

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()


def get_pg_connection() -> PGConn:
    """Open a PostgreSQL connection from DATABASE_URL env var."""
    dsn = os.environ["DATABASE_URL"]
    return PGConn(dsn)
