import sqlite3

import pytest
from opennotelm.db import Database


def test_migrations_repeat_and_foreign_keys(tmp_path):
    db = Database(tmp_path / "app.db")
    db.migrate()
    db.migrate()
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 19
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO notebook_sources VALUES ('missing','missing',0,1,'now')")
