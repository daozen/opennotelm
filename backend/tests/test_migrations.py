import sqlite3

import pytest
from opennotelm.db import Database


def test_migrations_repeat_and_foreign_keys(tmp_path):
    db = Database(tmp_path / "app.db")
    db.migrate()
    db.migrate()
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 21
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO notebook_sources VALUES ('missing','missing',0,1,'now')")


def test_podcast_upgrade_keeps_model_secrets_citation_ids_and_exact_offsets(tmp_path):
    from pathlib import Path

    import opennotelm.db

    migrations = Path(opennotelm.db.__file__).parent / "migrations"
    old = tmp_path / "old"
    old.mkdir()
    for file in migrations.glob("*.sql"):
        if file.name < "020":
            (old / file.name).write_bytes(file.read_bytes())
    db = Database(tmp_path / "app.db")
    db.migrate(old)
    with db.connect() as conn:
        conn.execute("INSERT INTO notebooks VALUES ('book','Book','','now','now')")
        conn.execute(
            "INSERT INTO model_configs VALUES ('language','http://local/v1','model','secret-ref',16000,'{}','now')"
        )
        conn.execute("INSERT INTO citations VALUES ('cite','book','slide','slide','E1','now')")
        conn.execute("INSERT INTO citation_spans VALUES ('cite',0,'source','block',12,47)")
    db.migrate()
    with db.connect() as conn:
        assert tuple(conn.execute("SELECT * FROM citation_spans").fetchone()) == (
            "cite",
            0,
            "source",
            "block",
            12,
            47,
        )
        assert (
            conn.execute("SELECT api_key_secret_ref FROM model_configs").fetchone()[0]
            == "secret-ref"
        )
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()


def test_mindmap_upgrade_preserves_podcast_citations_and_deletion_trigger(tmp_path):
    from pathlib import Path

    import opennotelm.db

    migrations = Path(opennotelm.db.__file__).parent / "migrations"
    old = tmp_path / "through-020"
    old.mkdir()
    for file in migrations.glob("*.sql"):
        if file.name < "021":
            (old / file.name).write_bytes(file.read_bytes())
    db = Database(tmp_path / "app.db")
    db.migrate(old)
    with db.connect() as conn:
        conn.execute("INSERT INTO notebooks VALUES ('book','Book','','now','now')")
        conn.execute(
            "INSERT INTO podcasts(id,notebook_id,title,input_json,source_scope_json,"
            "source_manifest_json,settings_json,created_at,updated_at) "
            "VALUES ('episode','book','Episode','{}','{}','{}','{}','now','now')"
        )
        conn.execute(
            "INSERT INTO podcast_segments(id,podcast_id,ordinal,title,plan_json) "
            "VALUES ('segment','episode',0,'Intro','{}')"
        )
        conn.execute(
            "INSERT INTO citations VALUES ('cite','book','podcast_segment','segment','E1','now')"
        )
        conn.execute("INSERT INTO citation_spans VALUES ('cite',0,'source','block',7,31)")
    db.migrate()
    with db.connect() as conn:
        assert tuple(conn.execute("SELECT * FROM citation_spans").fetchone()) == (
            "cite",
            0,
            "source",
            "block",
            7,
            31,
        )
        conn.execute("DELETE FROM podcasts WHERE id='episode'")
        assert conn.execute("SELECT count(*) FROM citations").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM citation_spans").fetchone()[0] == 0
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
