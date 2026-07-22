"""PostgreSQL connection, schema migration, and audit helpers."""

from __future__ import annotations

import json
import atexit
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

import psycopg
from psycopg import sql
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

from config import DATABASE_POOL_SIZE, DATABASE_SCHEMA, DATABASE_URL


PELAKU_COLUMNS = {
    "is_active": "INTEGER NOT NULL DEFAULT 1",
    "deleted_at": "TEXT",
    "deleted_by": "INTEGER",
    "created_at": "TEXT",
    "created_by": "INTEGER",
    "updated_at": "TEXT",
    "updated_by": "INTEGER",
    "import_batch_id": "TEXT",
}

USER_COLUMNS = {
    "updated_at": "TEXT",
    "last_login_at": "TEXT",
    "must_change_password": "INTEGER NOT NULL DEFAULT 0",
}

_pool = ConnectionPool(
    conninfo=DATABASE_URL,
    min_size=0,
    max_size=DATABASE_POOL_SIZE,
    kwargs={
        "row_factory": dict_row,
        "connect_timeout": 15,
        "options": f"-c search_path={DATABASE_SCHEMA}",
    },
    open=False,
)
atexit.register(_pool.close)


def utcnow() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def connect_db(database_url: str | None = None) -> psycopg.Connection:
    """Buka koneksi mandiri; dipertahankan untuk script administrasi dan test."""
    conn = psycopg.connect(
        database_url or DATABASE_URL, row_factory=dict_row, connect_timeout=15
    )
    conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(DATABASE_SCHEMA)))
    return conn


@contextmanager
def connection(database_url: str | None = None) -> Iterator[psycopg.Connection]:
    """Pinjam koneksi aplikasi dari pool, atau koneksi mandiri untuk URL khusus."""
    if database_url and database_url != DATABASE_URL:
        conn = connect_db(database_url)
        try:
            yield conn
        finally:
            conn.close()
        return

    if _pool.closed:
        _pool.open()
    with _pool.connection() as conn:
        yield conn


@contextmanager
def transaction(database_url: str | None = None) -> Iterator[psycopg.Connection]:
    with connection(database_url) as conn:
        with conn.transaction():
            yield conn


def _table_exists(conn: psycopg.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = current_schema() AND table_name = %s", (table,)
    ).fetchone()
    return row is not None


def _column_names(conn: psycopg.Connection, table: str) -> set[str]:
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = %s", (table,)
    ).fetchall()
    return {row["column_name"] for row in rows}


def _ensure_columns(conn: psycopg.Connection, table: str, columns: dict[str, str]) -> None:
    existing = _column_names(conn, table)
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')


def initialize_database(database_url: str | None = None) -> None:
    """Create or upgrade the schema without discarding existing records."""
    with transaction(database_url) as conn:
        if not _table_exists(conn, "pelaku_ekraf"):
            conn.execute(f"""
                CREATE TABLE pelaku_ekraf (
                    id BIGSERIAL PRIMARY KEY,
                    "Nama Narasumber" TEXT,
                    "Nama Usaha" TEXT,
                    "Alamat" TEXT,
                    "Kecamatan" TEXT,
                    "Kelurahan" TEXT,
                    "No Telp" TEXT,
                    "Sub Sektor" TEXT,
                    "Kategori Usaha" TEXT,
                    "Tahun Berdiri" INTEGER,
                    "Email" TEXT,
                    lat REAL,
                    lon REAL,
                    "Sheet" TEXT,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    deleted_at TEXT,
                    deleted_by INTEGER,
                    created_at TEXT,
                    created_by BIGINT,
                    updated_at TEXT,
                    updated_by BIGINT,
                    import_batch_id TEXT
                )
            """)
        else:
            _ensure_columns(conn, "pelaku_ekraf", PELAKU_COLUMNS)

        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                last_login_at TEXT,
                must_change_password INTEGER NOT NULL DEFAULT 0
            )
        """)
        _ensure_columns(conn, "users", USER_COLUMNS)

        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT,
                action TEXT NOT NULL,
                entity TEXT NOT NULL,
                entity_id TEXT,
                old_value TEXT,
                new_value TEXT,
                ip_address TEXT,
                request_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS login_attempts (
                id BIGSERIAL PRIMARY KEY,
                username TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                succeeded INTEGER NOT NULL DEFAULT 0,
                attempted_at TEXT NOT NULL
            )
        """)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS import_batches (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_sha256 TEXT NOT NULL,
                uploaded_by BIGINT NOT NULL,
                status TEXT NOT NULL,
                total_rows INTEGER NOT NULL DEFAULT 0,
                valid_rows INTEGER NOT NULL DEFAULT 0,
                error_rows INTEGER NOT NULL DEFAULT 0,
                duplicate_rows INTEGER NOT NULL DEFAULT 0,
                summary_json TEXT,
                created_at TEXT NOT NULL,
                committed_at TEXT,
                committed_by BIGINT,
                rolled_back_at TEXT,
                rolled_back_by BIGINT,
                FOREIGN KEY (uploaded_by) REFERENCES users(id),
                FOREIGN KEY (committed_by) REFERENCES users(id),
                FOREIGN KEY (rolled_back_by) REFERENCES users(id)
            )
        """)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS import_staging (
                id BIGSERIAL PRIMARY KEY,
                batch_id TEXT NOT NULL,
                row_number INTEGER NOT NULL,
                data_json TEXT NOT NULL,
                validation_status TEXT NOT NULL,
                errors_json TEXT,
                duplicate_of BIGINT,
                committed_record_id BIGINT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (batch_id) REFERENCES import_batches(id) ON DELETE CASCADE
            )
        """)

        now = utcnow()
        conn.execute(
            "UPDATE pelaku_ekraf SET created_at = %s WHERE created_at IS NULL", (now,)
        )
        conn.execute(
            "UPDATE users SET created_at = %s WHERE created_at IS NULL OR created_at = ''", (now,)
        )
        for statement in (
            "CREATE INDEX IF NOT EXISTS idx_pelaku_active ON pelaku_ekraf(is_active)",
            "CREATE INDEX IF NOT EXISTS idx_pelaku_active_id ON pelaku_ekraf(is_active, id)",
            'CREATE INDEX IF NOT EXISTS idx_pelaku_active_kecamatan ON pelaku_ekraf(is_active, "Kecamatan")',
            'CREATE INDEX IF NOT EXISTS idx_pelaku_active_kelurahan ON pelaku_ekraf(is_active, "Kelurahan")',
            'CREATE INDEX IF NOT EXISTS idx_pelaku_active_subsektor ON pelaku_ekraf(is_active, "Sub Sektor")',
            "CREATE INDEX IF NOT EXISTS idx_pelaku_import_batch ON pelaku_ekraf(import_batch_id)",
            "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_login_attempt ON login_attempts(username, ip_address, attempted_at)",
            "CREATE INDEX IF NOT EXISTS idx_staging_batch ON import_staging(batch_id, validation_status)",
        ):
            conn.execute(statement)


def _json_value(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def record_audit(
    conn: psycopg.Connection,
    *,
    action: str,
    entity: str,
    entity_id: str | int | None = None,
    user_id: int | None = None,
    old_value: Any = None,
    new_value: Any = None,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO audit_logs
            (user_id, action, entity, entity_id, old_value, new_value,
             ip_address, request_id, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            user_id,
            action,
            entity,
            str(entity_id) if entity_id is not None else None,
            _json_value(old_value),
            _json_value(new_value),
            ip_address,
            request_id,
            utcnow(),
        ),
    )


def row_as_dict(row) -> dict[str, Any] | None:
    return dict(row) if row is not None else None
