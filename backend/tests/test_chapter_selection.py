import json

import pytest
from document_factory import make_pdf
from docx_factory import make_docx
from epub_factory import make_anchor_epub, make_epub
from opennotelm.retrieval import Scope
from test_decks import create_deck, decks  # noqa: F401
from test_sources import wait_for_job


@pytest.mark.parametrize("format", ["epub", "pdf", "docx"])
def test_chapter_union_deck_citations_order_overlap_and_isolation(decks, format):  # noqa: F811
    client, state, _ = decks
    notebook = client.post("/api/notebooks", json={"title": "Chapters"}).json()["id"]
    data = {"epub": make_epub, "pdf": make_pdf, "docx": make_docx}[format]()
    result = client.post(
        f"/api/notebooks/{notebook}/sources/upload", files={"file": ("book." + format, data)}
    ).json()
    assert wait_for_job(client, result["job"]["id"])["status"] == "completed"
    source = result["source"]["id"]
    nodes = client.get(f"/api/sources/{source}/nodes").json()
    chapters = [n for n in nodes if n["type"] == ("heading" if format == "docx" else "chapter")]
    first, second = chapters[:2]
    descendants = [n for n in nodes if n["parent_id"] == first["id"]]
    requested = [first["id"], first["id"], *[n["id"] for n in descendants]]
    scope = {"kind": "nodes", "source_id": source, "node_ids": requested}
    expected = client.app.state.retrieval.scope_blocks(notebook, Scope(**scope))
    excluded = client.app.state.retrieval.scope_blocks(
        notebook, Scope(kind="node", source_id=source, node_id=second["id"])
    )
    assert expected and excluded
    deck, job = create_deck(client, notebook, scope=scope)
    assert job["status"] == "completed", job
    assert deck["source_scope"]["node_ids"] == [first["id"]]
    assert deck["generation_metadata"]["block_ids"] == [b["id"] for b in expected]
    actual_ids = set(deck["generation_metadata"]["block_ids"])
    assert not actual_ids.intersection(b["id"] for b in excluded)
    for slide in deck["slides"]:
        for ref in slide["citations"].values():
            citation = client.get("/api/citations/" + ref).json()
            assert all(s["block_id"] in actual_ids for s in citation["spans"])
    union = Scope(kind="nodes", source_id=source, node_ids=[second["id"], first["id"]])
    canonical = client.app.state.knowledge.freeze(notebook, union)
    assert canonical.node_ids == [first["id"], second["id"]]
    all_blocks = client.app.state.retrieval.scope_blocks(notebook, canonical)
    assert len(all_blocks) == len({b["id"] for b in all_blocks})
    assert [b["ordinal"] for b in all_blocks] == sorted(b["ordinal"] for b in all_blocks)
    assert len(all_blocks) == len(client.get(f"/api/sources/{source}/blocks").json())
    other = client.post("/api/notebooks", json={"title": "Foreign"}).json()["id"]
    invalids = [
        (notebook, {**scope, "node_ids": ["foreign"]}),
        (other, scope),
        (notebook, {**scope, "node_ids": []}),
    ]
    before = len(state["calls"])
    for target, invalid in invalids:
        response = client.post(
            f"/api/notebooks/{target}/decks", json={"scope": invalid, "render_mode": "native"}
        )
        assert response.status_code in (400, 422), response.text
    assert len(state["calls"]) == before
    assert "api_key" not in json.dumps(deck["source_scope"])


def test_epub_non_heading_toc_anchors_work_on_legacy_facts_without_rewriting(decks):  # noqa: F811
    client, _, _ = decks
    notebook = client.post("/api/notebooks", json={"title": "Anchors"}).json()["id"]
    result = client.post(
        f"/api/notebooks/{notebook}/sources/upload",
        files={"file": ("anchors.epub", make_anchor_epub())},
    ).json()
    source = result["source"]["id"]
    assert wait_for_job(client, result["job"]["id"])["status"] == "completed"
    with client.app.state.db.connect() as conn:
        metadata = json.loads(
            conn.execute("SELECT metadata_json FROM sources WHERE id=?", (source,)).fetchone()[0]
        )
        metadata.pop("toc_sections")
        conn.execute(
            "UPDATE sources SET metadata_json=? WHERE id=?", (json.dumps(metadata), source)
        )
        before = [
            tuple(r)
            for r in conn.execute(
                "SELECT * FROM content_blocks WHERE source_id=? ORDER BY ordinal", (source,)
            )
        ]
    nodes = client.get(f"/api/sources/{source}/nodes").json()
    alpha = next(n for n in nodes if n["title"] == "Alpha")
    beta = next(n for n in nodes if n["title"] == "Beta")
    first = client.get(f"/api/sources/{source}/blocks?node_id={alpha['id']}").json()
    assert len(first) == 1 and "ALPHA_ONLY" in first[0]["text"]
    assert "BETA_EXCLUDED" not in str(first)
    scope = {"kind": "nodes", "source_id": source, "node_ids": [alpha["id"]]}
    deck, job = create_deck(client, notebook, scope=scope)
    assert job["status"] == "completed", job
    assert deck["generation_metadata"]["block_ids"] == [first[0]["id"]]
    combined = client.app.state.retrieval.scope_blocks(
        notebook, Scope(**{**scope, "node_ids": [beta["id"], alpha["id"]]})
    )
    assert len(combined) == 2
    with client.app.state.db.connect() as conn:
        assert [
            tuple(r)
            for r in conn.execute(
                "SELECT * FROM content_blocks WHERE source_id=? ORDER BY ordinal", (source,)
            )
        ] == before
