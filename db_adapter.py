from __future__ import annotations

import os
import sqlite3
from decimal import Decimal
from pathlib import Path

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USING_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))

sqlite3.register_adapter(Decimal, lambda value: str(value))


class HybridRow(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


def hybrid_row(cursor):
    columns = [description.name for description in cursor.description]

    def make_row(values):
        return HybridRow(zip(columns, values))

    return make_row


def _convert_qmark(sql: str) -> str:
    return sql.replace("?", "%s")


class DBConnection:
    def __init__(self, conn, postgres: bool):
        self.conn = conn
        self.postgres = postgres

    def execute(self, sql, params=None):
        if self.postgres:
            sql = _convert_qmark(sql)
        return self.conn.execute(sql) if params is None else self.conn.execute(sql, params)

    def executescript(self, script):
        if self.postgres:
            with self.conn.cursor() as cursor:
                for statement in (part.strip() for part in script.split(";")):
                    if statement:
                        cursor.execute(statement)
            return None
        return self.conn.executescript(script)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        finally:
            self.conn.close()
        return False


def get_connection(instance_dir: Path, db_path: Path):
    if USING_POSTGRES:
        import psycopg

        connection = psycopg.connect(DATABASE_URL, row_factory=hybrid_row)
        return DBConnection(connection, True)

    instance_dir.mkdir(exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return DBConnection(connection, False)
