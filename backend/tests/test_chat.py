import json
from io import BytesIO
from zipfile import ZipFile

import httpx
import pytest
from epub_factory import make_epub
from fastapi.testclient import TestClient
from grounded_provider import completion, embedding
from opennotelm.citations import INSUFFICIENT
from opennotelm.main import create_app
from restart_support import restart
from test_models import config
from test_sources import import_book, wait_for_job


@pytest.fixture
def grounded(settings):
    state = {"calls": [], "invalid": False, "uncited": False, "fail_embedding": False}

    def handler(request):
        payload = json.loads(request.content)
        state["calls"].append(payload)
        if request.url.path.endswith("embeddings"):
            if state["fail_embedding"]:
                return httpx.Response(503)
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"index": i, "embedding": embedding(text)}
                        for i, text in enumerate(payload["input"])
                    ]
                },
            )
        value = completion(payload)
        if "EVIDENCE_JSON\n" in payload["messages"][-1]["content"]:
            if state["invalid"]:
                value = "Unsupported marker [[E999]]"
            elif state["uncited"]:
                value = "A statement without a marker."
        elif payload["messages"][0]["content"].startswith("Fix citation markers"):
            if state["invalid"]:
                value = "Changed substantive content [[E1]]"
        return httpx.Response(200, json={"choices": [{"message": {"content": value}}]})

    transport = httpx.MockTransport(handler)
    with TestClient(create_app(settings, transport=transport)) as client:
        for role in ("language", "embedding"):
            assert client.post("/api/settings/models/test", json=config(role)).status_code == 200
        yield client, state, transport


def ask(client, notebook_id, question="长期复利的优势是什么？", scope=None):
    response = client.post(
        f"/api/notebooks/{notebook_id}/chat",
        json={"question": question, "scope": scope or {"kind": "selected"}},
    )
    assert response.status_code == 202, response.text
    return wait_for_job(client, response.json()["id"])


def messages(client, notebook_id):
    return client.get(f"/api/notebooks/{notebook_id}/chat").json()["messages"]


def test_grounded_answer_exact_citation_reindex_and_deletion(grounded, settings):
    client, state, transport = grounded
    notebook, source_id = import_book(client)
    assert client.get(f"/api/sources/{source_id}").json()["status"] == "indexed"
    assert ask(client, notebook["id"])["status"] == "completed"
    answer = messages(client, notebook["id"])[-1]
    citation_id = next(iter(answer["citations"].values()))
    citation = client.get(f"/api/citations/{citation_id}").json()
    span = citation["spans"][0]
    assert span["quote"] == "长期复利最大的优势来自时间跨度。"
    assert span["source_title"] == "长期思考"
    block = next(
        b
        for b in client.get(f"/api/sources/{source_id}/blocks").json()
        if b["id"] == span["block_id"]
    )
    assert block["text"][span["start_offset"] : span["end_offset"]] == span["quote"]
    with client.app.state.db.connect() as conn:
        conn.execute("DELETE FROM chunks WHERE source_id=?", (source_id,))
    job = client.post(f"/api/sources/{source_id}/retry").json()
    assert wait_for_job(client, job["id"])["status"] == "completed"
    assert client.get(f"/api/citations/{citation_id}").json() == citation
    with restart(client, settings, transport=transport) as restarted:
        assert messages(restarted, notebook["id"])[-1]["id"] == answer["id"]
        assert restarted.get(f"/api/citations/{citation_id}").json() == citation
    assert client.delete(f"/api/sources/{source_id}").status_code == 204
    assert messages(client, notebook["id"])[-1]["content"] == answer["content"]
    assert (
        client.get(f"/api/citations/{citation_id}").json()["message"]
        == "Original source unavailable"
    )


def test_scope_isolation_followup_and_empty_selection(grounded):
    client, state, _ = grounded
    notebook, source_id = import_book(client)
    nodes = client.get(f"/api/sources/{source_id}/nodes").json()
    chapter = next(n for n in nodes if n["type"] == "chapter")
    scope = {"kind": "node", "source_id": source_id, "node_id": chapter["id"]}
    assert ask(client, notebook["id"], "解释耐心的价值", scope)["status"] == "completed"
    prompt = next(c for c in reversed(state["calls"]) if "messages" in c)["messages"][-1]["content"]
    assert "耐心意味着" in prompt and "长期复利" not in prompt
    assert ask(client, notebook["id"], "怎么实践？", scope)["status"] == "completed"
    trace = messages(client, notebook["id"])[-1]["metadata"]["retrieval"]
    assert trace["query"] == "解释耐心的价值\n怎么实践？"
    client.patch(f"/api/notebooks/{notebook['id']}/sources/{source_id}", json={"enabled": False})
    calls_before = len(state["calls"])
    assert ask(client, notebook["id"])["status"] == "completed"
    assert messages(client, notebook["id"])[-1]["content"] == INSUFFICIENT
    assert (
        messages(client, notebook["id"])[-1]["metadata"]["answer_status"] == "insufficient_evidence"
    )
    assert len(state["calls"]) == calls_before
    response = client.post(
        f"/api/notebooks/{notebook['id']}/chat",
        json={
            "question": "Bypass selection",
            "scope": {"kind": "selected", "source_ids": [source_id]},
        },
    )
    assert response.status_code == 400
    another = client.post("/api/notebooks", json={"title": "Other"}).json()
    response = client.post(
        f"/api/notebooks/{another['id']}/chat", json={"question": "Bypass notebook", "scope": scope}
    )
    assert response.status_code == 400


def test_failed_citation_repair_is_not_displayed_and_retry_works(grounded):
    client, state, _ = grounded
    notebook, _ = import_book(client)
    state["invalid"] = True
    job = ask(client, notebook["id"])
    assert job["error_code"] == "CITATION_VERIFICATION_FAILED"
    assert not any(m["role"] == "assistant" for m in messages(client, notebook["id"]))
    repairs = [
        c
        for c in state["calls"]
        if "messages" in c and c["messages"][0]["content"].startswith("Fix citation markers")
    ]
    assert len(repairs) == 1
    assert json.loads(repairs[0]["messages"][-1]["content"])["evidence"]
    state["invalid"] = False
    retried = client.post(f"/api/jobs/{job['id']}/retry").json()
    assert wait_for_job(client, retried["id"])["status"] == "completed"
    assert messages(client, notebook["id"])[-1]["citations"]


def test_missing_citation_can_be_repaired_without_rewriting(grounded):
    client, state, _ = grounded
    notebook, _ = import_book(client)
    state["uncited"] = True
    assert ask(client, notebook["id"])["status"] == "completed"
    assert messages(client, notebook["id"])[-1]["content"].startswith(
        "A statement without a marker.[["
    )


def test_embedding_failure_retains_blocks_for_retry(grounded):
    client, state, _ = grounded
    notebook, source_id = import_book(client)
    blocks = client.get(f"/api/sources/{source_id}/blocks").json()
    with client.app.state.db.connect() as conn:
        conn.execute("DELETE FROM embeddings")
    state["fail_embedding"] = True
    job = client.post(f"/api/sources/{source_id}/retry").json()
    assert wait_for_job(client, job["id"])["status"] == "failed"
    assert client.get(f"/api/sources/{source_id}/blocks").json() == blocks
    state["fail_embedding"] = False
    job = client.post(f"/api/sources/{source_id}/retry").json()
    assert wait_for_job(client, job["id"])["status"] == "completed"
    assert client.get(f"/api/sources/{source_id}/blocks").json() == blocks


def test_unselected_source_never_enters_model_evidence(grounded):
    client, state, _ = grounded
    notebook, _ = import_book(client)
    stream = BytesIO()
    with ZipFile(BytesIO(make_epub())) as original, ZipFile(stream, "w") as other:
        for entry in original.infolist():
            content = original.read(entry.filename)
            if entry.filename.endswith(".xhtml"):
                content = content.replace(b"</body>", b"<p>UNSELECTED_SENTINEL</p></body>")
            other.writestr(entry, content)
    imported = client.post(
        f"/api/notebooks/{notebook['id']}/sources/upload",
        files={"file": ("other.epub", stream.getvalue())},
    ).json()
    assert wait_for_job(client, imported["job"]["id"])["status"] == "completed"
    client.patch(
        f"/api/notebooks/{notebook['id']}/sources/{imported['source']['id']}",
        json={"enabled": False},
    )
    assert ask(client, notebook["id"])["status"] == "completed"
    prompt = next(c for c in reversed(state["calls"]) if "messages" in c)
    assert "UNSELECTED_SENTINEL" not in json.dumps(prompt)


def test_queued_chat_freezes_scope_and_rejects_concurrent_send(grounded):
    client, _, _ = grounded
    notebook, source_id = import_book(client)
    client.portal.call(client.app.state.jobs.stop)
    endpoint = f"/api/notebooks/{notebook['id']}/chat"
    first = client.post(endpoint, json={"question": "长期复利的优势是什么？"})
    assert first.status_code == 202
    assert client.post(endpoint, json={"question": "Concurrent"}).status_code == 409
    client.patch(f"/api/notebooks/{notebook['id']}/sources/{source_id}", json={"enabled": False})
    assert client.portal.call(client.app.state.jobs.run_one)
    assert client.get(f"/api/jobs/{first.json()['id']}").json()["status"] == "completed"
    assert messages(client, notebook["id"])[-1]["citations"]


@pytest.mark.parametrize("extension", ["md", "txt", "pdf"])
def test_other_formats_share_original_citation_pipeline(grounded, settings, extension):
    from document_factory import MARKDOWN, make_pdf

    client, _, _ = grounded
    notebook = client.post("/api/notebooks", json={"title": extension}).json()
    raw = (
        make_pdf()
        if extension == "pdf"
        else MARKDOWN.encode()
        if extension == "md"
        else (b"Small improvements accumulate over time.\n\nPractice daily.")
    )
    imported = client.post(
        f"/api/notebooks/{notebook['id']}/sources/upload",
        files={"file": (f"notes.{extension}", raw)},
    ).json()
    assert wait_for_job(client, imported["job"]["id"])["status"] == "completed"
    source_id = imported["source"]["id"]
    assert (settings.data_dir / "sources" / source_id / f"original.{extension}").read_bytes() == raw
    assert ask(client, notebook["id"], "How do small improvements help?")["status"] == "completed"
    answer = messages(client, notebook["id"])[-1]
    assert answer["citations"]
    blocks = {b["id"]: b for b in client.get(f"/api/sources/{source_id}/blocks").json()}
    for citation_id in answer["citations"].values():
        citation = client.get(f"/api/citations/{citation_id}").json()
        assert citation["available"]
        for span in citation["spans"]:
            block = blocks[span["block_id"]]
            assert span["quote"] == block["text"][span["start_offset"] : span["end_offset"]]
            assert span["page"] == block["page_start"]


def test_save_answer_as_knowledge_retains_original_provenance(grounded):
    client, _, _ = grounded
    notebook, source_id = import_book(client)
    assert ask(client, notebook["id"])["status"] == "completed"
    answer = messages(client, notebook["id"])[-1]
    response = client.post(
        f"/api/notebooks/{notebook['id']}/knowledge/from-message", json={"message_id": answer["id"]}
    )
    assert response.status_code == 201
    page = response.json()
    assert page["content_markdown"] == answer["content"]
    assert page["citations"].keys() == answer["citations"].keys()
    for marker, ref in page["citations"].items():
        assert ref != answer["citations"][marker]
        assert (
            client.get(f"/api/citations/{ref}").json()["spans"]
            == client.get(f"/api/citations/{answer['citations'][marker]}").json()["spans"]
        )
    other = client.post("/api/notebooks", json={"title": "Other"}).json()
    assert (
        client.post(
            f"/api/notebooks/{other['id']}/knowledge/from-message",
            json={"message_id": answer["id"]},
        ).status_code
        == 404
    )
    client.delete(f"/api/sources/{source_id}")
    assert (
        client.get(f"/api/knowledge/{page['id']}").json()["content_markdown"] == answer["content"]
    )
