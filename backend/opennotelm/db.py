import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .errors import AppError


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def migrate(self, migrations_dir: Path | None = None) -> None:
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            applied = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
            files = sorted((migrations_dir or Path(__file__).parent / "migrations").glob("*.sql"))
            if applied - {file.stem for file in files}:
                raise AppError(
                    "DATABASE_NEWER_THAN_APP",
                    "This data directory needs a newer app version. "
                    "Restore the matching version or a backup.",
                )
            for file in files:
                if file.stem not in applied:
                    sql = file.read_text()
                    rebuild = sql.startswith("-- requires-foreign-keys-off")
                    if rebuild:
                        conn.execute("PRAGMA foreign_keys = OFF")
                    try:
                        conn.executescript(
                            "BEGIN IMMEDIATE;\n"
                            + sql
                            + f"\nINSERT INTO schema_migrations(version) VALUES ('{file.stem}');"
                        )
                        if conn.execute("PRAGMA foreign_key_check").fetchone():
                            raise AppError(
                                "DATABASE_MIGRATION_FAILED",
                                "Database migration failed integrity checks.",
                            )
                        conn.commit()
                    except Exception:
                        conn.rollback()
                        raise
                    finally:
                        if rebuild:
                            conn.execute("PRAGMA foreign_keys = ON")
