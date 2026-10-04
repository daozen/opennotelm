import json
from io import BytesIO
from zipfile import ZipFile

import httpx
import pytest
from docx_factory import make_docx
from epub_factory import make_anchor_epub, make_epub
from fastapi.testclient import TestClient
from grounded_provider import completion
from opennotelm.main import create_app
from opennotelm.retrieval import Scope
from restart_support import restart
from test_models import config
from test_sources import wait_for_job
from vision_factory import scan_image, scan_pdf, vision_completion


@pytest.fixture
def vision_client(settings):
    calls, state = [], {"fail": False, "wrong": False}

    def provider(request):
        payload = json.loads(request.content)
        calls.append(payload)
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"index": i, "embedding": [0.2, 0.8]} for i in range(len(payload["input"]))
                    ]
                },
            )
        value = vision_completion(payload)
        if value and state["fail"]:
            return httpx.Response(503)
        if value and state["wrong"]:
            value = '{"ok": true}'
        return httpx.Response(
            200, json={"choices": [{"message": {"content": value or completion(payload)}}]}
        )

    transport = httpx.MockTransport(provider)
    with TestClient(create_app(settings, transport=transport)) as client:
        for role in ["language", "embedding"]:
            assert client.post("/api/settings/models/test", json=config(role)).status_code == 200
        yield client, calls, state, transport


def upload(client, name, data):
    notebook = client.post("/api/notebooks", json={"title": "Images"}).json()["id"]
    result = client.post(
        f"/api/notebooks/{notebook}/sources/upload", files={"file": (name, data)}
    ).json()
    job = wait_for_job(client, result["job"]["id"])
    return notebook, result["source"]["id"], job


@pytest.mark.parametrize("format", ["pdf", "docx", "epub"])
def test_recognition_original_image_reading_citation_and_restart(vision_client, settings, format):
    client, calls, _, transport = vision_client
    if format == "pdf":
        data = scan_pdf()
    elif format == "docx":
        data = make_docx(scan_image())
    else:
        original = BytesIO(make_epub())
        output = BytesIO()
        with ZipFile(original) as old, ZipFile(output, "w") as new:
            for item in old.infolist():
                value = old.read(item.filename)
                if item.filename.endswith("one.xhtml"):
                    value = value.replace(b"</body>", b'<p><img src="figure.png"/></p></body>')
                new.writestr(item, value)
            # Infer the fixture's resource directory rather than trusting an external URI.
            chapter = next(n for n in old.namelist() if n.endswith("one.xhtml"))
            new.writestr(chapter.rsplit("/", 1)[0] + "/figure.png", scan_image())
        data = output.getvalue()
    notebook, source, job = upload(client, "images." + format, data)
    assert job["status"] == "completed", job
    record = client.get(f"/api/sources/{source}").json()
    assert record["status"] == "indexed"
    assert record["metadata"]["image_failures"] == 0
    reading = client.get(f"/api/sources/{source}/reading").json()
    images = [b for b in reading if b.get("image")]
    assert images and all("SCAN 27" in str(b["parts"]) for b in images)
    original_image = client.get(images[0]["image"]["image_url"]).content
    assert original_image.startswith(b"\x89PNG")
    blocks = client.get(f"/api/sources/{source}/blocks").json()
    image_block = next(b for b in blocks if b["type"] == "image")
    evidence = [
        {
            "id": "E1",
            "text": image_block["text"],
            "spans": [
                {
                    "source_id": source,
                    "block_id": image_block["id"],
                    "start_offset": 0,
                    "end_offset": len(image_block["text"]),
                }
            ],
        }
    ]
    with client.app.state.db.connect() as conn:
        refs = client.app.state.citations.persist(
            conn, notebook, "message", "test", "[[E1]]", evidence
        )
    citation = client.get("/api/citations/" + refs["E1"]).json()
    assert citation["passages"][0]["extraction"] == "vision"
    assert citation["passages"][0]["image_url"] == images[0]["image"]["image_url"]
    before_calls = len(calls)
    retry = client.post(f"/api/sources/{source}/recognize-images").json()
    assert wait_for_job(client, retry["id"])["status"] == "completed"
    assert len(calls) == before_calls  # Transcripts and unchanged index both reuse checkpoints.
    with restart(client, settings, transport) as restarted:
        assert restarted.get(images[0]["image"]["image_url"]).content == original_image
        assert restarted.get(f"/api/sources/{source}/blocks").json() == blocks
        assert restarted.get("/api/citations/" + refs["E1"]).json()["available"]
    assert client.delete(f"/api/sources/{source}").status_code == 204
    assert client.get(images[0]["image"]["image_url"]).status_code == 404


def test_failed_scan_keeps_original_and_can_retry(vision_client):
    client, _, state, _ = vision_client
    state["fail"] = True
    _, source, job = upload(client, "failed.pdf", scan_pdf())
    assert job["status"] == "failed"
    record = client.get(f"/api/sources/{source}").json()
    assert record["metadata"]["image_failures"] == 2
    assert client.get(record["metadata"]["images"][0]["image_url"]).status_code == 200
    state["fail"] = False
    retry = client.post(f"/api/sources/{source}/retry").json()
    assert wait_for_job(client, retry["id"])["status"] == "completed"
    assert client.get(f"/api/sources/{source}").json()["metadata"]["image_failures"] == 0


def test_image_input_capability_is_tested_not_assumed(vision_client):
    client, _, state, _ = vision_client
    state["fail"] = True
    assert client.post("/api/settings/models/vision-test").status_code == 502
    assert (
        not client.get("/api/settings/models")
        .json()["models"]["language"]["capabilities"]
        .get("vision_input")
    )
    state["fail"] = False
    assert client.post("/api/settings/models/vision-test").status_code == 200
    assert client.get("/api/settings/models").json()["models"]["language"]["capabilities"][
        "vision_input"
    ]


def test_partial_image_retry_rebuilds_index_and_keeps_native_facts(vision_client):
    client, _, state, _ = vision_client
    state["fail"] = True
    notebook, source, job = upload(client, "partial.docx", make_docx(scan_image()))
    assert job["status"] == "completed"
    before = client.get(f"/api/sources/{source}/blocks").json()
    native = {b["id"]: b["text"] for b in before if b["type"] != "image"}
    state["fail"] = False
    retry = client.post(f"/api/sources/{source}/retry").json()
    assert wait_for_job(client, retry["id"])["status"] == "completed"
    after = client.get(f"/api/sources/{source}/blocks").json()
    assert {b["id"]: b["text"] for b in after if b["type"] != "image"} == native
    with client.app.state.db.connect() as conn:
        image = next(b for b in after if b["type"] == "image")
        assert conn.execute(
            "SELECT 1 FROM chunk_blocks WHERE block_id=?", (image["id"],)
        ).fetchone()
        assert not conn.execute(
            "SELECT 1 FROM chunks c LEFT JOIN chunk_blocks b ON b.chunk_id=c.id "
            "WHERE c.source_id=? AND b.chunk_id IS NULL",
            (source,),
        ).fetchone()
    scope = client.app.state.retrieval.scope_blocks(
        notebook, Scope(kind="source", source_id=source)
    )
    assert any("SCAN 27" in b["text"] for b in scope)


def test_wrong_vision_answer_is_rejected_and_corrupt_cache_recovers(vision_client, settings):
    client, calls, state, _ = vision_client
    state["wrong"] = True
    response = client.post("/api/settings/models/vision-test")
    assert response.json()["error"]["code"] == "MODEL_VISION_UNAVAILABLE"
    state["wrong"] = False
    _, source, job = upload(client, "cache.docx", make_docx(scan_image()))
    assert job["status"] == "completed"
    directory = settings.data_dir / "sources" / source / "media"
    for path in directory.glob("*.json"):
        path.write_text("corrupt checkpoint")
    before = len(calls)
    retry = client.post(f"/api/sources/{source}/recognize-images").json()
    assert wait_for_job(client, retry["id"])["status"] == "completed"
    assert len(calls) == before + 1


def test_anchor_scope_chat_never_sends_adjacent_chapter_in_shared_chunk(vision_client):
    client, calls, _, _ = vision_client
    notebook, source, job = upload(client, "anchors.epub", make_anchor_epub())
    assert job["status"] == "completed"
    nodes = client.get(f"/api/sources/{source}/nodes").json()
    alpha = next(n for n in nodes if n["title"] == "Alpha")
    response = client.post(
        f"/api/notebooks/{notebook}/chat",
        json={
            "question": "What does patient learning do?",
            "scope": {"kind": "nodes", "source_id": source, "node_ids": [alpha["id"]]},
        },
    ).json()
    assert wait_for_job(client, response["id"])["status"] == "completed"
    prompts = [
        c["messages"][-1]["content"]
        for c in calls
        if "messages" in c
        and isinstance(c["messages"][-1]["content"], str)
        and "EVIDENCE_JSON" in c["messages"][-1]["content"]
    ]
    assert prompts and all("ALPHA_ONLY" in p and "BETA_EXCLUDED" not in p for p in prompts)
