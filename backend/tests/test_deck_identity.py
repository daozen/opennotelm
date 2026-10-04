import json
from pathlib import Path
from urllib.parse import unquote

import pytest
from document_factory import make_nested_pdf
from epub_factory import make_anchor_epub
from opennotelm.db import Database
from opennotelm.deck_sources import directory
from opennotelm.pdf_export import download_filename
from PIL import Image
from reportlab.pdfgen.canvas import Canvas
from test_deck_batches import post_batch
from test_decks import create_deck, decks, notebook_with_source  # noqa: F401
from test_knowledge import create_page, import_text
from test_models import config
from test_pdf_export import install_render_outputs
from test_sources import wait_for_job


def post(client, notebook, scope, **extra):
    return client.post(
        f"/api/notebooks/{notebook}/decks",
        json={
            "scope": scope,
            "slide_count": 10,
            "render_mode": "native",
            **extra,
        },
    )


def test_source_and_chapter_names_survive_planning_and_batch_validation(decks):  # noqa: F811
    client, _, _ = decks
    notebook, source = notebook_with_source(client)
    nodes = client.get(f"/api/sources/{source}/nodes").json()
    chapter = next(node for node in nodes if node["title"] == "Practice")
    for scope, title in [
        ({"kind": "selected", "source_ids": [source]}, "Time"),
        ({"kind": "node", "source_id": source, "node_id": chapter["id"]}, "Time-1.1-Practice"),
    ]:
        result = post(client, notebook, scope, title_mode="source")
        assert result.status_code == 202, result.text
        deck = result.json()
        assert deck["title"] == title
        assert wait_for_job(client, deck["job"]["id"])["status"] == "completed"
        saved = client.get(f"/api/decks/{deck['id']}").json()
        assert saved["title"] == title and saved["title_mode"] == "source"
    other = import_text(client, notebook, "# Another\n\nOther text", "another.md")
    assert post(client, notebook, {"kind": "selected"}, title_mode="source").status_code == 400
    assert (
        post(
            client,
            notebook,
            {
                "kind": "nodes",
                "source_id": source,
                "node_ids": [node["id"] for node in nodes if node["type"] == "heading"],
            },
            title_mode="source",
        ).status_code
        == 202
    )  # parent subsumes its child
    batch = post_batch(client, notebook, {"kind": "selected"}, title_mode="source").json()
    assert {deck["title"] for deck in batch["decks"]} == {"Time", "Another"}
    for deck in batch["decks"]:
        assert wait_for_job(client, deck["job"]["id"])["status"] == "completed"
    assert {deck["source_scope"]["source_id"] for deck in batch["decks"]} == {source, other}
    assert post_batch(client, notebook, {"kind": "selected"}, title_mode="auto").status_code == 409


def test_frozen_sources_chapter_paths_and_unlinked_availability(decks):  # noqa: F811
    client, _, _ = decks
    notebook, source = notebook_with_source(client)
    nodes = client.get(f"/api/sources/{source}/nodes").json()
    chapter = next(node for node in nodes if node["title"] == "Practice")
    deck, _ = create_deck(
        client,
        notebook,
        scope={
            "kind": "node",
            "source_id": source,
            "node_id": chapter["id"],
        },
    )
    endpoint = f"/api/decks/{deck['id']}/sources"
    captured = client.get(endpoint).json()
    entry = captured["sources"][0]
    assert not captured["historical"] and entry["title"] == "Time"
    assert entry["selection"] == "chapters"
    assert entry["chapters"][0]["path"] == ["Time", "Practice"]
    assert entry["chapters"][0]["available"] and entry["chapters"][0]["first_block_id"]
    with client.app.state.db.connect() as conn:
        conn.execute("UPDATE sources SET title='Changed' WHERE id=?", (source,))
        conn.execute("UPDATE source_nodes SET title='Changed chapter' WHERE id=?", (chapter["id"],))
    assert client.get(endpoint).json() == captured
    assert client.delete(f"/api/notebooks/{notebook}/sources/{source}").status_code == 204
    unavailable = client.get(endpoint).json()["sources"][0]
    assert unavailable["title"] == "Time" and not unavailable["available"]
    assert unavailable["chapters"][0]["title"] == "Practice"
    assert not unavailable["chapters"][0]["available"]


def test_knowledge_snapshot_provenance_legacy_fallback_and_copy(decks):  # noqa: F811
    client, _, _ = decks
    notebook, source = notebook_with_source(client)
    page, _ = create_page(client, notebook)
    scope = {"kind": "knowledge", "knowledge_page_id": page["id"]}
    assert post(client, notebook, scope, title_mode="source").status_code == 400
    deck, _ = create_deck(client, notebook, scope=scope)
    endpoint = f"/api/decks/{deck['id']}/sources"
    sources = client.get(endpoint).json()
    assert sources["knowledge"][0]["title"] == page["title"]
    assert sources["knowledge"][0]["revision"] == page["revision"]
    assert sources["sources"][0]["id"] == source
    assert sources["sources"][0]["selection"] == "citations"
    assert sources["sources"][0]["chapters"]
    with client.app.state.db.connect() as conn:
        conn.execute(
            "UPDATE knowledge_pages SET title='Later title',revision=revision+1 WHERE id=?",
            (page["id"],),
        )
    assert client.get(endpoint).json() == sources
    assert client.post("/api/settings/models/test", json=config("image")).status_code == 200
    renamed = client.patch(f"/api/decks/{deck['id']}", json={"title": "My name"}).json()
    assert renamed["title_mode"] == "custom"
    copy = client.post(
        f"/api/decks/{deck['id']}/generated-copy", params={"rewrite_content": True}
    ).json()
    assert wait_for_job(client, copy["job"]["id"])["status"] == "completed"
    assert client.get(f"/api/decks/{copy['id']}").json()["title"] == "My name"
    assert client.get(f"/api/decks/{copy['id']}/sources").json() == sources
    with client.app.state.db.connect() as conn:
        conn.execute("UPDATE decks SET source_manifest_json=NULL WHERE id=?", (deck["id"],))
    old = client.get(endpoint).json()
    assert old["historical"] and old["knowledge"][0]["title"] == page["title"]
    with client.app.state.db.connect() as conn:
        assert (
            conn.execute(
                "SELECT source_manifest_json FROM decks WHERE id=?", (deck["id"],)
            ).fetchone()[0]
            is None
        )
    with client.app.state.db.connect() as conn:
        conn.execute("DELETE FROM knowledge_pages WHERE id=?", (page["id"],))
    assert not client.get(endpoint).json()["knowledge"][0]["available"]


def test_rename_queued_stop_resume_and_old_batch_receipts(decks):  # noqa: F811
    client, _, _ = decks
    notebook, _ = notebook_with_source(client)
    client.portal.call(client.app.state.jobs.stop)
    response = post_batch(client, notebook, {"kind": "selected"})
    deck = response.json()["decks"][0]
    assert client.patch(f"/api/decks/{deck['id']}", json={"title": "New"}).status_code == 409
    assert client.post(f"/api/decks/{deck['id']}/stop").status_code == 200
    assert client.patch(f"/api/decks/{deck['id']}", json={"title": "   "}).status_code == 422
    assert (
        client.patch(f"/api/decks/{deck['id']}", json={"title": "  New name  "}).json()["title"]
        == "New name"
    )
    with client.app.state.db.connect() as conn:
        receipt = conn.execute("SELECT request_json FROM deck_batches").fetchone()[0]
        old = json.loads(receipt)
        old.pop("title_mode")
        conn.execute("UPDATE deck_batches SET request_json=?", (json.dumps(old),))
    assert post_batch(client, notebook, {"kind": "selected"}).json()["decks"][0]["id"] == deck["id"]
    resumed = client.post(f"/api/decks/{deck['id']}/resume").json()
    client.portal.call(client.app.state.jobs.start)
    assert wait_for_job(client, resumed["job"]["id"])["status"] == "completed"
    assert client.get(f"/api/decks/{deck['id']}").json()["title"] == "New name"


def test_rename_keeps_pdf_bytes_signature_and_unicode_filename(decks, settings, tmp_path):  # noqa: F811
    client, _, _ = decks
    notebook, _ = notebook_with_source(client)
    deck, _ = create_deck(client, notebook)
    pdf, image = tmp_path / "page.pdf", tmp_path / "page.png"
    canvas = Canvas(str(pdf), pagesize=(1440, 810))
    canvas.showPage()
    canvas.save()
    Image.new("RGB", (1920, 1080), "white").save(image)
    install_render_outputs(client, deck, settings, {"pdf": pdf, "image": image, "text_layer": []})
    client.app.state.decks.exports = client.app.state.pdf_exports
    job = client.post(f"/api/decks/{deck['id']}/export").json()
    assert wait_for_job(client, job["id"])["status"] == "completed"
    ready = client.get(f"/api/decks/{deck['id']}").json()
    original = client.get(ready["pdf_export"]["download_url"])
    renamed = client.patch(
        f"/api/decks/{deck['id']}", json={"title": "蜂蜜供品 / 深读: 核心思想"}
    ).json()
    assert renamed["pdf_export"]["id"] == ready["pdf_export"]["id"]
    assert renamed["revision"] == ready["revision"]
    assert renamed["pdf_export"]["filename"] == "蜂蜜供品 _ 深读_ 核心思想.pdf"
    download = client.get(renamed["pdf_export"]["download_url"])
    preview = client.get(renamed["pdf_export"]["preview_url"])
    assert download.content == preview.content == original.content
    assert unquote(download.headers["content-disposition"]).endswith(
        "蜂蜜供品 _ 深读_ 核心思想.pdf"
    )
    assert preview.headers["content-disposition"].startswith("inline;")
    with client.app.state.db.connect() as conn:
        conn.execute("UPDATE slides SET revision=revision+1 WHERE id=?", (deck["slides"][0]["id"],))
    assert client.get(renamed["pdf_export"]["download_url"]).status_code == 409


@pytest.mark.parametrize(
    "title,expected",
    [
        ("My Deck", "My Deck.pdf"),
        ("蜂蜜供品.pdf", "蜂蜜供品.pdf"),
        ("../CON", "_CON.pdf"),
        ("CON", "_CON.pdf"),
        ('\r\n/\\:*?"<>|', "___________.pdf"),
        (" . ", "Visual Deck.pdf"),
    ],
)
def test_download_filename(title, expected):
    assert download_filename(title) == expected
    assert len(download_filename("深" * 1000).encode()) <= 224


def test_epub_directory_uses_toc_names_and_hierarchy():
    source = {
        "type": "epub",
        "metadata_json": json.dumps(
            {
                "toc": [
                    {"href": "a.xhtml", "title": "目录卷名", "depth": 1},
                    {"href": "a.xhtml", "fragment": "b", "title": "目录章节", "depth": 2},
                ]
            }
        ),
    }
    nodes = [
        {
            "id": "a",
            "type": "chapter",
            "title": "Raw",
            "parent_id": None,
            "depth": 1,
            "metadata": {"href": "a.xhtml"},
        },
        {
            "id": "b",
            "type": "heading",
            "title": "Raw B",
            "parent_id": "a",
            "depth": 2,
            "metadata": {"href": "a.xhtml", "element_id": "b"},
        },
    ]
    outline = directory(source, list(reversed(nodes)))  # TOC order wins over stored/spine order.
    assert outline[1]["path"] == ["目录卷名", "目录章节"]
    assert [node["number"] for node in outline] == ["1", "1.1"]


def test_chapter_numbers_use_full_outline_not_selected_order_or_pdf_pages(decks):  # noqa: F811
    client, state, _ = decks
    notebook = client.post("/api/notebooks", json={"title": "Numbering"}).json()["id"]
    upload = client.post(
        f"/api/notebooks/{notebook}/sources/upload",
        files={"file": ("book.pdf", make_nested_pdf())},
    ).json()
    assert wait_for_job(client, upload["job"]["id"])["status"] == "completed"
    source = upload["source"]["id"]
    nodes = client.get(f"/api/sources/{source}/nodes").json()
    by_title = {node["title"]: node["id"] for node in nodes}
    client.portal.call(client.app.state.jobs.stop)
    before = len(state["calls"])
    response = post_batch(
        client,
        notebook,
        {
            "kind": "nodes",
            "source_id": source,
            "node_ids": [by_title[title] for title in ("Part Two", "Section Beta", "Detail Alpha")],
        },
        title_mode="source",
    )
    assert response.status_code == 202, response.text
    created = response.json()["decks"]
    assert [deck["title"] for deck in created] == [
        "Chapter hierarchy acceptance-1.1.1-Detail Alpha",
        "Chapter hierarchy acceptance-1.2-Section Beta",
        "Chapter hierarchy acceptance-2-Part Two",
    ]
    assert len(state["calls"]) == before  # Naming makes no model request.
    single = post(
        client,
        notebook,
        {"kind": "node", "source_id": source, "node_id": by_title["Section Beta"]},
        title_mode="source",
    ).json()
    assert single["title"] == created[1]["title"]
    manifest = client.get(f"/api/decks/{single['id']}/sources").json()
    assert manifest["sources"][0]["chapters"][0]["number"] == "1.2"
    with client.app.state.db.connect() as conn:
        conn.execute(
            "UPDATE source_nodes SET title='Later name' WHERE id=?", (by_title["Section Beta"],)
        )
    assert client.get(f"/api/decks/{single['id']}/sources").json() == manifest
    assert client.get(f"/api/decks/{single['id']}").json()["title"] == single["title"]


def test_epub_anchor_chapter_source_name_uses_visible_toc_without_changing_facts(decks):  # noqa: F811
    client, _, _ = decks
    notebook = client.post("/api/notebooks", json={"title": "Anchor names"}).json()["id"]
    upload = client.post(
        f"/api/notebooks/{notebook}/sources/upload",
        files={"file": ("book.epub", make_anchor_epub())},
    ).json()
    assert wait_for_job(client, upload["job"]["id"])["status"] == "completed"
    source = upload["source"]["id"]
    with client.app.state.db.connect() as conn:
        before = [
            tuple(row)
            for row in conn.execute("SELECT * FROM content_blocks WHERE source_id=?", (source,))
        ]
    nodes = client.get(f"/api/sources/{source}/nodes").json()
    beta = next(node for node in nodes if node["title"] == "Beta")
    response = post(
        client,
        notebook,
        {"kind": "node", "source_id": source, "node_id": beta["id"]},
        title_mode="source",
    )
    assert response.status_code == 202, response.text
    deck = response.json()
    assert deck["title"] == "长期思考-2-Beta"
    assert wait_for_job(client, deck["job"]["id"])["status"] == "completed"
    assert client.get(f"/api/decks/{deck['id']}").json()["title"] == "长期思考-2-Beta"
    manifest = client.get(f"/api/decks/{deck['id']}/sources").json()
    assert manifest["sources"][0]["chapters"][0]["path"] == ["Beta"]
    with client.app.state.db.connect() as conn:
        assert [
            tuple(row)
            for row in conn.execute("SELECT * FROM content_blocks WHERE source_id=?", (source,))
        ] == before


def test_migration_preserves_existing_deck_title_and_artifact_hashes(tmp_path):
    from opennotelm import db as module

    migrations = Path(module.__file__).parent / "migrations"
    old = tmp_path / "old"
    old.mkdir()
    for file in migrations.glob("*.sql"):
        if file.name < "019":
            (old / file.name).write_bytes(file.read_bytes())
    db = Database(tmp_path / "upgrade.db")
    db.migrate(old)
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO notebooks(id,title,created_at,updated_at) VALUES ('n','N','now','now')"
        )
        conn.execute(
            "INSERT INTO decks(id,notebook_id,title,source_scope_json,target_slide_count,"
            "language,instruction,created_at,updated_at) "
            "VALUES ('d','n','旧名称','{}',10,'zh-CN','','now','now')"
        )
        conn.execute(
            "INSERT INTO pdf_exports(id,deck_id,input_hash,status,file_sha256,"
            "created_at,updated_at) "
            "VALUES ('p','d','old-signature','ready','old-file-hash','now','now')"
        )
    db.migrate()
    with db.connect() as conn:
        deck = conn.execute("SELECT * FROM decks WHERE id='d'").fetchone()
        assert deck["title"] == deck["export_title"] == "旧名称"
        assert deck["title_mode"] == "auto" and deck["source_manifest_json"] is None
        export = conn.execute("SELECT * FROM pdf_exports WHERE id='p'").fetchone()
        assert export["input_hash"] == "old-signature" and export["file_sha256"] == "old-file-hash"
