import json

import pytest
from opennotelm.errors import AppError
from test_revisions import revisions as revisions


def test_notebook_delete_cleans_jobs_files_and_keeps_shared_sources(revisions):
    client, _, _, deck, source = revisions
    settings = client.app.state.sources.settings
    owned = [
        p for directory in ("assets", "renders") for p in (settings.data_dir / directory).iterdir()
    ]
    assert len(owned) == 11
    raw = settings.data_dir / "sources" / source
    assert raw.is_dir()
    assert client.delete(f"/api/notebooks/{deck['notebook_id']}").status_code == 204
    assert all(not p.exists() for p in owned) and raw.is_dir()
    with client.app.state.db.connect() as conn:
        for table in (
            "decks",
            "slides",
            "assets",
            "slide_renders",
            "citations",
            "synthesis_checkpoints",
            "garbage_files",
        ):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
        assert (
            conn.execute("SELECT count(*) FROM jobs WHERE notebook_id IS NOT NULL").fetchone()[0]
            == 0
        )
    assert client.get(f"/api/sources/{source}").status_code == 200


def test_source_delete_scrubs_fact_caches_but_keeps_derived_artifacts(revisions):
    client, _, _, deck, source = revisions
    with client.app.state.db.connect() as conn:
        before = json.loads(
            conn.execute(
                "SELECT understanding_json FROM decks WHERE id=?", (deck["id"],)
            ).fetchone()[0]
        )
        assert before["evidence"][0]["text"]
    assert client.delete(f"/api/sources/{source}").status_code == 204
    with client.app.state.db.connect() as conn:
        after = json.loads(
            conn.execute(
                "SELECT understanding_json FROM decks WHERE id=?", (deck["id"],)
            ).fetchone()[0]
        )
        assert not any(packet["text"] for packet in after["evidence"])
        assert after["content"] == before["content"]
        for table in ("sources", "content_blocks", "chunks", "embeddings", "synthesis_checkpoints"):
            assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    saved = client.get(f"/api/decks/{deck['id']}").json()
    assert saved["slides"] == deck["slides"]
    identity = next(iter(saved["slides"][0]["citations"].values()))
    assert not client.get(f"/api/citations/{identity}").json()["available"]


def test_busy_deletion_rolls_back_cache_changes_and_preserves_tasks(revisions):
    client, _, _, deck, source = revisions
    client.portal.call(client.app.state.jobs.stop)
    job = client.app.state.jobs.enqueue("deck_export", deck["id"], {"deck_id": deck["id"]})
    with client.app.state.db.connect() as conn:
        cached = conn.execute(
            "SELECT understanding_json FROM decks WHERE id=?", (deck["id"],)
        ).fetchone()[0]
    assert client.delete(f"/api/notebooks/{deck['notebook_id']}").status_code == 409
    assert client.delete(f"/api/sources/{source}").status_code == 409
    with client.app.state.db.connect() as conn:
        assert (
            conn.execute(
                "SELECT understanding_json FROM decks WHERE id=?", (deck["id"],)
            ).fetchone()[0]
            == cached
        )
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "queued"


def test_startup_reclaims_orphan_files_and_retries_committed_deletion(client, settings, tmp_path):
    root = settings.data_dir
    orphan = root / "renders" / ("a" * 32)
    orphan.mkdir()
    (orphan / "page.png").write_bytes(b"orphan")
    pending = root / "assets" / ("b" * 32)
    pending.mkdir()
    outside = tmp_path / "keep"
    outside.mkdir()
    (outside / "important.txt").write_text("keep")
    linked = root / "assets" / ("c" * 32)
    linked.symlink_to(outside, target_is_directory=True)
    upload = root / "cache" / ("upload-" + "d" * 32)
    upload.write_bytes(b"interrupted upload")
    with client.app.state.db.connect() as conn:
        conn.execute("INSERT INTO garbage_files VALUES (?)", ("assets/" + "b" * 32,))
        conn.execute("INSERT INTO garbage_files VALUES ('../keep')")
    client.app.state.files.recover()
    assert (
        not orphan.exists() and not pending.exists() and not linked.exists() and not upload.exists()
    )
    assert (outside / "important.txt").read_text() == "keep"


def test_newer_schema_is_rejected_without_mutation(client):
    db = client.app.state.db
    with db.connect() as conn:
        conn.execute("INSERT INTO schema_migrations(version) VALUES ('999_future')")
    with pytest.raises(AppError, match="DATABASE_NEWER_THAN_APP"):
        db.migrate()


def test_upgrade_from_pdf_milestone_preserves_saved_rows_and_backfills_jobs(settings):
    from pathlib import Path

    import opennotelm.db
    from opennotelm.db import Database

    settings.prepare()
    db = Database(settings.data_dir / "app.db")
    directory = Path(opennotelm.db.__file__).parent / "migrations"
    with db.connect() as conn:
        conn.execute(
            "CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, "
            "applied_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        for file in sorted(directory.glob("*.sql"))[:9]:
            conn.executescript(file.read_text())
            conn.execute("INSERT INTO schema_migrations(version) VALUES (?)", (file.stem,))
            conn.commit()
        conn.execute("INSERT INTO notebooks VALUES ('book','Saved title','','then','then')")
        conn.execute(
            "INSERT INTO decks(id,notebook_id,title,source_scope_json,target_slide_count,"
            "language,instruction,created_at,updated_at) "
            "VALUES ('deck','book','Saved deck','{}',10,'zh','','then','then')"
        )
        conn.execute(
            "INSERT INTO slides(id,deck_id,ordinal,plan_json,spec_json,revision,"
            "current_render_id,created_at,updated_at) "
            "VALUES ('slide','deck',0,'{}','{}',3,'render','then','then')"
        )
        conn.execute(
            "INSERT INTO jobs(id,type,entity_id,status,payload_json,created_at) "
            "VALUES ('job','deck_generate','deck','completed','{\"deck_id\":\"deck\"}','then')"
        )
        conn.execute(
            "INSERT INTO jobs(id,type,entity_id,status,payload_json,created_at) "
            "VALUES ('orphan','deck_generate','deleted','failed',"
            "'{\"deck_id\":\"deleted\"}','then')"
        )
    db.migrate()
    db.migrate()
    with db.connect() as conn:
        assert conn.execute("SELECT title FROM notebooks").fetchone()[0] == "Saved title"
        row = conn.execute("SELECT * FROM slides").fetchone()
        assert row["revision"] == row["current_render_revision"] == 3
        assert row["current_render_id"] == "render"
        assert conn.execute("SELECT notebook_id FROM jobs WHERE id='job'").fetchone()[0] == "book"
        assert conn.execute("SELECT 1 FROM jobs WHERE id='orphan'").fetchone() is None
        conn.execute("DELETE FROM notebooks WHERE id='book'")
        assert conn.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
