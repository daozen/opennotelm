import asyncio
import hashlib
import json
import threading
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import pytest
from opennotelm import artifact_downloads
from opennotelm.artifact_downloads import ArtifactRef, BundleResponse
from pypdf import PdfWriter


def saved_deck(client, settings, notebook, title="Chapter"):
    identity, slide_id, render_id, export_id = [uuid4().hex for _ in range(4)]
    pdf = PdfWriter()
    pdf.add_blank_page(width=1440, height=810)
    pdf.add_metadata({"/Title": title})
    stream = BytesIO()
    pdf.write(stream)
    content = stream.getvalue()
    directory = settings.data_dir / "exports" / export_id
    directory.mkdir(parents=True)
    path = directory / "deck.pdf"
    path.write_bytes(content)
    with client.app.state.db.connect() as conn:
        conn.execute(
            "INSERT INTO decks(id,notebook_id,title,export_title,source_scope_json,"
            "target_slide_count,"
            "language,instruction,status,plan_json,created_at,updated_at) VALUES (?,?,?,?,?,10,"
            "'zh-CN','','ready','{}','now','now')",
            (identity, notebook, title, title, json.dumps({"kind": "selected"})),
        )
        conn.execute(
            "INSERT INTO slides(id,deck_id,ordinal,plan_json,status,current_render_id,"
            "current_render_revision,created_at,updated_at) "
            "VALUES (?,?,0,?, 'rendered',?,0,'now','now')",
            (slide_id, identity, json.dumps({"title": "Page"}), render_id),
        )
        conn.execute(
            "INSERT INTO slide_renders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                render_id,
                slide_id,
                "hash",
                "{}",
                "renders/page.png",
                "renders/thumb.png",
                "renders/page.pdf",
                1920,
                1080,
                "[]",
                "test",
                "test",
                "now",
            ),
        )
        digest = client.app.state.pdf_exports.snapshot(identity, conn)[2]
        conn.execute(
            "INSERT INTO pdf_exports(id,deck_id,input_hash,status,file_uri,file_sha256,page_count,"
            "file_size,created_at,updated_at) VALUES (?,?,?,'ready',?,?,1,?,'now','now')",
            (
                export_id,
                identity,
                digest,
                str(path.relative_to(settings.data_dir)),
                hashlib.sha256(content).hexdigest(),
                len(content),
            ),
        )
    return identity, path, content


@pytest.fixture
def bundles(client, settings):
    client.portal.call(client.app.state.jobs.stop)
    notebook = client.post("/api/notebooks", json={"title": "书籍 / Chapters"}).json()["id"]
    return client, settings, notebook


def prepare(client, notebook, ids):
    return client.post(
        f"/api/notebooks/{notebook}/artifacts/download",
        json={"items": [{"kind": "deck", "id": identity} for identity in ids]},
    )


def test_bundle_uses_current_names_collision_safe_original_pdf_bytes_and_no_model_calls(
    bundles, provider
):
    client, settings, notebook = bundles
    first = saved_deck(client, settings, notebook, "蜂蜜供品")
    second = saved_deck(client, settings, notebook, "蜂蜜供品")
    third = saved_deck(client, settings, notebook, "../../CON")
    before = len(provider[1])
    result = prepare(client, notebook, [first[0], second[0], third[0]])
    assert result.status_code == 200
    assert result.json()["filename"] == "书籍 _ Chapters.zip"
    response = client.get(result.json()["download_url"])
    assert response.status_code == 200 and response.headers["content-type"] == "application/zip"
    assert response.headers["cache-control"] == "no-store"
    partial = client.get(result.json()["download_url"], headers={"Range": "bytes=0-99"})
    assert partial.status_code == 206 and partial.content == response.content[:100]
    with ZipFile(BytesIO(response.content)) as archive:
        assert archive.namelist() == ["蜂蜜供品.pdf", "蜂蜜供品 (2).pdf", "_.._CON.pdf"]
        assert [archive.read(name) for name in archive.namelist()] == [
            first[2],
            second[2],
            third[2],
        ]
    assert len(provider[1]) == before
    assert [
        entry["download_available"]
        for entry in client.get(f"/api/notebooks/{notebook}/decks").json()
    ] == [True] * 3
    client.patch(f"/api/decks/{first[0]}", json={"title": "改名后的章节"})
    renamed = prepare(client, notebook, [first[0]]).json()
    with ZipFile(BytesIO(client.get(renamed["download_url"]).content)) as archive:
        assert archive.namelist() == ["改名后的章节.pdf"]
        assert archive.read("改名后的章节.pdf") == first[2]
    assert first[1].read_bytes() == first[2]


@pytest.mark.parametrize(
    "items",
    [
        [],
        [{"kind": "knowledge", "id": "a" * 32}],
        [{"kind": "deck", "id": "../bad"}],
        [{"kind": "deck", "id": "a" * 32}] * 2,
        [{"kind": "deck", "id": f"{i:032x}"} for i in range(101)],
    ],
)
def test_invalid_selection_is_rejected_before_packing(bundles, items):
    client, _, notebook = bundles
    assert (
        client.post(
            f"/api/notebooks/{notebook}/artifacts/download", json={"items": items}
        ).status_code
        == 422
    )
    assert not client.app.state.artifact_downloads.entries


@pytest.mark.parametrize(
    "problem", ["foreign", "missing", "stale", "busy", "damage", "removed_file"]
)
def test_batch_fails_atomically_for_unavailable_selection(bundles, problem):
    client, settings, notebook = bundles
    good = saved_deck(client, settings, notebook)
    other_nb = (
        client.post("/api/notebooks", json={"title": "Other"}).json()["id"]
        if problem == "foreign"
        else notebook
    )
    bad = saved_deck(client, settings, other_nb)
    if problem == "missing":
        identity = uuid4().hex
    else:
        identity = bad[0]
    with client.app.state.db.connect() as conn:
        if problem == "stale":
            conn.execute("UPDATE slides SET revision=revision+1 WHERE deck_id=?", (identity,))
        elif problem == "busy":
            client.app.state.jobs.enqueue_in_transaction(
                conn, "deck_export", identity, {"deck_id": identity}
            )
    if problem == "damage":
        bad[1].write_bytes(b"damaged")
    elif problem == "removed_file":
        bad[1].unlink()
    response = prepare(client, notebook, [good[0], identity])
    assert response.status_code in (404, 409)
    service = client.app.state.artifact_downloads
    assert not service.entries and not list(Path(service.directory.name).iterdir())
    assert good[1].read_bytes() == good[2]
    if problem in ("busy", "stale", "removed_file"):
        listing = client.get(f"/api/notebooks/{notebook}/decks").json()
        assert not next(item for item in listing if item["id"] == bad[0])["download_available"]


def test_limits_expiration_deletion_and_shutdown_clean_temp_files(bundles, monkeypatch):
    client, settings, notebook = bundles
    first = saved_deck(client, settings, notebook)
    second = saved_deck(client, settings, notebook, "Other")
    service = client.app.state.artifact_downloads
    monkeypatch.setattr(artifact_downloads, "MAX_BUNDLE_BYTES", 10)
    assert prepare(client, notebook, [first[0]]).status_code == 413
    assert not service.entries
    monkeypatch.setattr(artifact_downloads, "MAX_BUNDLE_BYTES", 512 * 1024 * 1024)
    result = prepare(client, notebook, [first[0]]).json()
    entry = next(iter(service.entries.values()))
    entry["expires"] = 0
    assert client.get(result["download_url"]).status_code == 404

    async def reap():
        service.timer.cancel()
        service.reap()

    client.portal.call(reap)
    assert not entry["path"].exists()
    result = prepare(client, notebook, [first[0], second[0]]).json()
    assert client.delete(f"/api/decks/{first[0]}").status_code == 204
    assert client.get(result["download_url"]).status_code == 404
    assert second[1].read_bytes() == second[2] and not service.entries
    result = prepare(client, notebook, [second[0]]).json()
    assert client.delete(f"/api/notebooks/{notebook}").status_code == 204
    assert client.get(result["download_url"]).status_code == 404
    assert not service.entries


def test_cancelled_packing_joins_thread_before_releasing_entity_lock(bundles, monkeypatch):
    client, settings, notebook = bundles
    saved = saved_deck(client, settings, notebook)
    service = client.app.state.artifact_downloads
    started, release = threading.Event(), threading.Event()
    original = artifact_downloads.write_bundle

    def slow(files, path):
        original(files, path)
        started.set()
        assert release.wait(5)

    monkeypatch.setattr(artifact_downloads, "write_bundle", slow)

    async def check():
        task = asyncio.create_task(
            service.prepare(notebook, [ArtifactRef(kind="deck", id=saved[0])])
        )
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()

        async def deletion():
            async with service.jobs.entity_lock(saved[0]):
                return True

        deleting = asyncio.create_task(deletion())
        try:
            await asyncio.sleep(0.02)
            assert not task.done() and not deleting.done()
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await deleting
        assert not service.entries

    client.portal.call(check)
    assert not list(Path(service.directory.name).iterdir())
    assert saved[1].read_bytes() == saved[2]


def test_download_disconnect_releases_protected_files(bundles):
    client, settings, notebook = bundles
    saved = saved_deck(client, settings, notebook)
    result = prepare(client, notebook, [saved[0]]).json()
    service = client.app.state.artifact_downloads
    token = result["download_url"].split("/")[-2]

    async def check():
        async def send(message):
            if message["type"] == "http.response.body":
                raise RuntimeError("test disconnect")

        async def receive():
            return {"type": "http.disconnect"}

        with pytest.raises(RuntimeError, match="test disconnect"):
            await BundleResponse(service, token)(
                {"type": "http", "method": "GET", "headers": [], "extensions": {}}, receive, send
            )
        assert service.entries[token]["readers"] == 0
        async with service.jobs.entity_lock(saved[0]):
            pass

    client.portal.call(check)
    assert client.get(result["download_url"]).status_code == 200


def test_cache_capacity_and_shutdown_do_not_leak_temporary_files(bundles, monkeypatch):
    client, settings, notebook = bundles
    saved = saved_deck(client, settings, notebook)
    service = client.app.state.artifact_downloads
    monkeypatch.setattr(artifact_downloads, "MAX_CACHE_BYTES", 0)
    assert prepare(client, notebook, [saved[0]]).status_code == 429
    assert not service.entries and not list(Path(service.directory.name).iterdir())
    monkeypatch.setattr(artifact_downloads, "MAX_CACHE_BYTES", 1024 * 1024)
    assert prepare(client, notebook, [saved[0]]).status_code == 200
    directory = Path(service.directory.name)
    client.portal.call(service.close)
    assert not directory.exists() and not service.entries
    assert saved[1].read_bytes() == saved[2]


def test_consecutive_batches_reclaim_old_links_but_preserve_active_downloads(bundles, monkeypatch):
    client, settings, notebook = bundles
    saved = saved_deck(client, settings, notebook)
    service = client.app.state.artifact_downloads
    first = prepare(client, notebook, [saved[0]]).json()
    entry = next(iter(service.entries.values()))
    monkeypatch.setattr(artifact_downloads, "MAX_CACHE_BYTES", entry["size"])
    second = prepare(client, notebook, [saved[0]]).json()
    assert client.get(first["download_url"]).status_code == 404
    assert client.get(second["download_url"]).status_code == 200
    active = next(iter(service.entries.values()))
    active["readers"] = 1
    try:
        assert prepare(client, notebook, [saved[0]]).status_code == 429
        assert active["path"].exists() and len(service.entries) == 1
    finally:
        active["readers"] = 0
    assert client.get(second["download_url"]).status_code == 200
    assert len(list(Path(service.directory.name).iterdir())) == 1
