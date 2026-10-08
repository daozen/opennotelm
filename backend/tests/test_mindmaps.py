import asyncio
import json
import threading
from io import BytesIO
from zipfile import ZipFile

import httpx
import pytest
from fastapi.testclient import TestClient
from grounded_provider import completion
from opennotelm.main import create_app
from opennotelm.mindmap_schemas import MindMapTree, validate_tree
from test_knowledge import import_text
from test_models import config
from test_sources import wait_for_job


@pytest.fixture
def mindmap(settings):
    state = {
        "maps": 0,
        "reading": 0,
        "fail": False,
        "block": False,
        "active": 0,
        "entered": threading.Event(),
        "calls": [],
    }

    async def handler(request):
        body = json.loads(request.content)
        system = body["messages"][0]["content"]
        state["calls"].append(body)
        if system.startswith("Create a useful, well-structured reading dossier"):
            state["reading"] += 1
        if system.startswith("Create a concept mind map"):
            state["maps"] += 1
            if state["block"]:
                state["active"] += 1
                state["entered"].set()
                try:
                    await asyncio.Event().wait()
                finally:
                    state["active"] -= 1
            if state["fail"]:
                return httpx.Response(400, json={"error": "PRIVATE_PROVIDER_TEXT"})
        return httpx.Response(200, json={"choices": [{"message": {"content": completion(body)}}]})

    state["transport"] = httpx.MockTransport(handler)
    with TestClient(create_app(settings, transport=state["transport"])) as client:
        assert client.post("/api/settings/models/test", json=config("language")).status_code == 200
        notebook = client.post("/api/notebooks", json={"title": "Mind map test"}).json()["id"]
        source = import_text(
            client, notebook, "Practice strengthens learning. Reflection improves the next attempt."
        )
        yield client, state, notebook, source


def create_map(fixture, **options):
    client, _, notebook, source = fixture
    response = client.post(
        f"/api/notebooks/{notebook}/mindmaps",
        json={
            "scope": {"kind": "source", "source_id": source},
            "instruction": "Explain clearly.\nShow concepts.",
            **options,
        },
    )
    assert response.status_code == 202, response.text
    value = response.json()
    job = wait_for_job(client, value["job"]["id"])
    return client.get(f"/api/mindmaps/{value['id']}").json(), job


def test_tree_exact_citations_download_history_sources_rename_delete(mindmap, settings):
    client, state, notebook, source = mindmap
    value, job = create_map(mindmap, language="ja", title_mode="source")
    assert job["status"] == "completed", job
    assert value["download_available"] and len(value["tree"]["nodes"]) == 5
    assert value["title"] == client.get(f"/api/sources/{source}").json()["title"]
    for citation in value["citations"].values():
        span = client.get(f"/api/citations/{citation}").json()["spans"][0]
        assert span["source_id"] == source
        block = client.get(f"/api/sources/{source}/blocks").json()[0]
        assert span["quote"] == block["text"][span["start_offset"] : span["end_offset"]]
    identity = value["id"]
    url = f"/api/mindmaps/{identity}"
    assert client.get(url + "/sources").json()["sources"][0]["id"] == source
    assert (
        client.get("/api/artifacts/instruction-history?kind=mindmap").json()["items"][0][
            "instruction"
        ]
        == "Explain clearly.\nShow concepts."
    )
    assert client.get("/api/artifacts/instruction-history?kind=deck").json()["items"] == []
    assert all(
        "Japanese" in b["messages"][0]["content"]
        for b in state["calls"]
        if b["messages"][0]["content"].startswith(("Create a concept", "Create a useful"))
    )
    before = client.get(url + "/download").content
    renamed = client.patch(url, json={"title": "My map 测试"})
    assert renamed.status_code == 200
    assert client.get(url + "/download").content == before
    assert "My%20map" in client.get(url + "/download").headers["content-disposition"]
    assert client.get(url + "/download?format=json").json()["tree"] == value["tree"]
    assert client.get(url + "/download?format=bad").status_code == 422
    from restart_support import restart

    calls = len(state["calls"])
    with restart(client, settings, transport=state["transport"]) as restarted:
        restored = restarted.get(url).json()
        assert restored["tree"] == value["tree"]
        assert restored["citations"] == value["citations"]
        assert restarted.get(url + "/download").content == before
    assert len(state["calls"]) == calls
    bundle = client.post(
        f"/api/notebooks/{notebook}/artifacts/download",
        json={"items": [{"kind": "mindmap", "id": identity}]},
    )
    assert bundle.status_code == 200, bundle.text
    with ZipFile(BytesIO(client.get(bundle.json()["download_url"]).content)) as archive:
        assert archive.read(archive.namelist()[0]) == before
    diagnostic = client.get(url + "/diagnostics").text
    assert (
        "PRIVATE_PROVIDER_TEXT" not in diagnostic
        and "Practice strengthens" not in diagnostic
        and "Explain clearly" not in diagnostic
    )
    directory = settings.data_dir / "mindmaps" / identity
    assert directory.is_dir()
    assert client.delete(url).status_code == 204
    assert not directory.exists()
    assert client.get(f"/api/sources/{source}").status_code == 200
    assert client.get("/api/artifacts/instruction-history?kind=mindmap").json()["items"] == []
    assert client.get(bundle.json()["download_url"]).status_code in (404, 410)


def test_failed_tree_resumes_without_reading_again_and_model_change_is_clear(mindmap):
    client, state, _, _ = mindmap
    state["fail"] = True
    value, job = create_map(mindmap)
    assert job["status"] == "failed"
    reading = state["reading"]
    assert reading > 0
    original = config("language")
    changed = {**original, "model_id": "different-model"}
    assert client.post("/api/settings/models/test", json=changed).status_code == 200
    response = client.post(f"/api/mindmaps/{value['id']}/resume")
    assert response.status_code == 202
    job = wait_for_job(client, response.json()["job"]["id"])
    assert job["error_code"] == "MINDMAP_MODEL_CHANGED"
    client.post("/api/settings/models/test", json=original)
    state["fail"] = False
    resumed = client.post(f"/api/mindmaps/{value['id']}/resume").json()
    assert wait_for_job(client, resumed["job"]["id"])["status"] == "completed"
    assert state["reading"] == reading


def test_stop_running_and_queued_batch_survives_restart_and_delete_tombstone(mindmap):
    client, state, notebook, source = mindmap
    state["block"] = True
    response = client.post(
        f"/api/notebooks/{notebook}/mindmaps",
        json={"scope": {"kind": "source", "source_id": source}},
    ).json()
    assert state["entered"].wait(5)
    value = client.post(f"/api/mindmaps/{response['id']}/stop").json()
    assert value["status"] == "paused" and state["active"] == 0
    reading = state["reading"]
    state["block"] = False
    resumed = client.post(f"/api/mindmaps/{value['id']}/resume").json()
    assert wait_for_job(client, resumed["job"]["id"])["status"] == "completed"
    assert state["reading"] == reading
    client.portal.call(client.app.state.jobs.stop)
    payload = {
        "scope": {"kind": "selected", "source_ids": [source]},
        "request_key": "mindmap-batch-test",
        "title_mode": "source",
    }
    url = f"/api/notebooks/{notebook}/mindmaps/batch"
    batch = client.post(url, json=payload)
    assert batch.status_code == 202, batch.text
    saved = batch.json()["mindmaps"][0]
    assert client.post(url, json=payload).json()["mindmaps"][0]["id"] == saved["id"]
    client.post(f"/api/mindmaps/{saved['id']}/stop")
    client.portal.call(client.app.state.jobs.start)
    assert client.get(f"/api/mindmaps/{saved['id']}").json()["job"]["status"] == "cancelled"
    client.delete(f"/api/mindmaps/{saved['id']}")
    assert client.post(url, json=payload).status_code == 409


def test_tree_rejects_cycles_unregistered_evidence_background_citations_and_depth():
    raw = {
        "title": "Map",
        "nodes": [
            {"id": "r", "parent_id": None, "label": "Root", "basis": "structural"},
            {
                "id": "a",
                "parent_id": "r",
                "label": "Fact",
                "basis": "source",
                "evidence_ids": ["E1"],
            },
            {"id": "b", "parent_id": "a", "label": "Example", "basis": "analogy"},
        ],
    }
    validate_tree(MindMapTree(**raw), {"E1"}, primary={"E1"})
    invalid = []
    for node, field, value in [
        (1, "parent_id", "b"),
        (1, "evidence_ids", ["invented"]),
        (2, "evidence_ids", ["E1"]),
        (2, "parent_id", None),
        (1, "id", "r"),
    ]:
        candidate = json.loads(json.dumps(raw))
        candidate["nodes"][node][field] = value
        invalid.append(candidate)
    for candidate in invalid:
        with pytest.raises(ValueError):
            validate_tree(MindMapTree(**candidate), {"E1"})
    with pytest.raises(ValueError):
        validate_tree(MindMapTree(**raw), {"E1"}, source_only=True)
    candidate = json.loads(json.dumps(raw))
    for i in range(6):
        candidate["nodes"].append(
            {
                "id": f"d{i}",
                "parent_id": "b" if i == 0 else f"d{i - 1}",
                "label": "Deep",
                "basis": "source",
                "evidence_ids": ["E1"],
            }
        )
    with pytest.raises(ValueError):
        validate_tree(MindMapTree(**candidate), {"E1"})


def test_chapter_batch_parent_context_knowledge_scope_and_notebook_ownership(mindmap):
    from epub_factory import make_epub

    client, state, notebook, _ = mindmap
    upload = client.post(
        f"/api/notebooks/{notebook}/sources/upload",
        files={"file": ("Learning.epub", make_epub())},
    ).json()
    assert wait_for_job(client, upload["job"]["id"])["status"] == "completed"
    source = upload["source"]["id"]
    chapters = [
        n for n in client.get(f"/api/sources/{source}/nodes").json() if n["type"] == "chapter"
    ]
    response = client.post(
        f"/api/notebooks/{notebook}/mindmaps/batch",
        json={
            "scope": {
                "kind": "nodes",
                "source_id": source,
                "node_ids": [c["id"] for c in reversed(chapters)],
            },
            "request_key": "chapters-context-01",
            "title_mode": "source",
            "language": "en",
        },
    )
    assert response.status_code == 202, response.text
    for created, chapter in zip(response.json()["mindmaps"], chapters, strict=True):
        assert created["source_scope"]["node_id"] == chapter["id"]
        assert wait_for_job(client, created["job"]["id"])["status"] == "completed"
        saved = client.app.state.mindmaps.record(created["id"])
        assert saved["understanding"]["work_context"]["whole_work_readings"]
        manifest = client.get(f"/api/mindmaps/{created['id']}/sources").json()["sources"][0]
        section = manifest["chapters"][0]
        assert saved["title"] == f"{manifest['title']}-{section['number']}-{section['title']}"
    # Empty instructions need no separate intention request.
    assert not any(b["messages"][0]["content"].startswith("Resolve only") for b in state["calls"])
    response = client.post(
        f"/api/notebooks/{notebook}/knowledge",
        json={"scope": {"kind": "source", "source_id": source}},
    )
    assert response.status_code == 202, response.text
    page = response.json()
    completed = wait_for_job(client, page["job"]["id"])
    assert completed["status"] == "completed"
    page = page["page"]
    value, job = create_map(mindmap, scope={"kind": "knowledge", "knowledge_page_id": page["id"]})
    assert job["status"] == "completed", job
    assert value["citations"]
    another = client.post("/api/notebooks", json={"title": "Other notebook"}).json()["id"]
    assert (
        client.post(
            f"/api/notebooks/{another}/mindmaps",
            json={"scope": {"kind": "knowledge", "knowledge_page_id": page["id"]}},
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/api/notebooks/{another}/artifacts/download",
            json={"items": [{"kind": "mindmap", "id": value["id"]}]},
        ).status_code
        == 404
    )
    identity = value["id"]
    assert client.delete(f"/api/notebooks/{notebook}").status_code == 204
    assert client.get(f"/api/mindmaps/{identity}").status_code == 404
