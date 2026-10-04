import json

import httpx
import pytest
from fastapi.testclient import TestClient
from grounded_provider import completion
from opennotelm.citations import CITATION_PATTERN
from opennotelm.main import create_app
from restart_support import restart
from test_models import config
from test_sources import wait_for_job


@pytest.fixture
def knowledge(settings):
    state = {"calls": [], "invalid": False, "update_response": None, "fail_at": None}

    def handler(request):
        payload = json.loads(request.content)
        state["calls"].append(payload)
        system = payload["messages"][0]["content"]
        if system.startswith("Create a useful"):
            if state["fail_at"] == len(state["calls"]):
                return httpx.Response(503)
            if state["invalid"]:
                return httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": "Uncited fabrication [[FAKE]]"}}]},
                )
        if system.startswith("Update the existing") and state["update_response"]:
            value = state["update_response"](json.loads(payload["messages"][-1]["content"]))
        else:
            value = completion(payload)
        return httpx.Response(200, json={"choices": [{"message": {"content": value}}]})

    transport = httpx.MockTransport(handler)
    with TestClient(create_app(settings, transport=transport)) as client:
        assert client.post("/api/settings/models/test", json=config("language")).status_code == 200
        yield client, state, transport


def import_text(client, notebook_id, text, name="notes.md"):
    result = client.post(
        f"/api/notebooks/{notebook_id}/sources/upload", files={"file": (name, text.encode())}
    ).json()
    assert wait_for_job(client, result["job"]["id"])["status"] == "completed"
    return result["source"]["id"]


def create_page(client, notebook_id, scope=None):
    response = client.post(
        f"/api/notebooks/{notebook_id}/knowledge", json={"scope": scope or {"kind": "selected"}}
    )
    assert response.status_code == 202, response.text
    job = wait_for_job(client, response.json()["job"]["id"])
    return client.get(f"/api/knowledge/{response.json()['page']['id']}").json(), job


def test_full_scope_no_embedding_and_exact_provenance(knowledge, settings):
    client, state, transport = knowledge
    notebook = client.post("/api/notebooks", json={"title": "Knowledge"}).json()["id"]
    first = import_text(
        client,
        notebook,
        "# Chapter One\n\nThe first concept.\n\n## Chapter Two\n\nThe final concept.",
    )
    second = import_text(client, notebook, "UNSELECTED_SENTINEL")
    client.patch(f"/api/notebooks/{notebook}/sources/{second}", json={"enabled": False})
    page, job = create_page(client, notebook)
    assert job["status"] == "completed", job
    blocks = client.get(f"/api/sources/{first}/blocks").json()
    assert page["generation_metadata"]["block_ids"] == [b["id"] for b in blocks]
    synth = [c for c in state["calls"] if c["messages"][0]["content"].startswith("Create a useful")]
    assert len(synth) == 1
    prompt = synth[0]["messages"][-1]["content"]
    assert "The first concept" in prompt and "The final concept" in prompt
    assert "UNSELECTED_SENTINEL" not in prompt
    assert page["citations"]
    for ref in page["citations"].values():
        span = client.get(f"/api/citations/{ref}").json()["spans"][0]
        block = next(b for b in blocks if b["id"] == span["block_id"])
        assert span["quote"] == block["text"][span["start_offset"] : span["end_offset"]]
    assert client.get("/api/notebooks").json()[0]["knowledge_count"] == 1
    with restart(client, settings, transport=transport) as restarted:
        assert (
            restarted.get(f"/api/knowledge/{page['id']}").json()["content_markdown"]
            == page["content_markdown"]
        )


def test_hierarchical_all_blocks_and_retry_checkpoint_reuse(knowledge):
    client, state, _ = knowledge
    settings = config("language")
    settings["max_context_tokens"] = 4096
    assert client.post("/api/settings/models/test", json=settings).status_code == 200
    notebook = client.post("/api/notebooks", json={"title": "Long"}).json()["id"]
    text = "\n\n".join(f"Paragraph {i}: " + "Learning takes practice. " * 60 for i in range(20))
    source = import_text(client, notebook, text, "long.txt")
    state["fail_at"] = len(state["calls"]) + 3
    page, job = create_page(client, notebook)
    assert job["status"] == "failed"
    before = len(state["calls"])
    state["fail_at"] = None
    client.post(f"/api/jobs/{job['id']}/retry")
    assert wait_for_job(client, job["id"])["status"] == "completed"
    page = client.get(f"/api/knowledge/{page['id']}").json()
    assert page["generation_metadata"]["segment_count"] > 1
    assert page["generation_metadata"]["reduction_levels"] > 0
    assert len(page["generation_metadata"]["block_ids"]) == 20
    resumed = state["calls"][before]["messages"][-1]["content"]
    # The failed segment is retried; successful segments are not sent again.
    assert resumed == state["calls"][before - 1]["messages"][-1]["content"]
    raw_inputs = {}
    for call in state["calls"]:
        if call["messages"][0]["content"].startswith("Create a useful"):
            raw_inputs.update(
                (item["id"], item["text"])
                for item in json.loads(call["messages"][-1]["content"])["material"]
                if "id" in item
            )
    for i in range(20):
        assert any(f"Paragraph {i}:" in item for item in raw_inputs.values())
    blocks = client.get(f"/api/sources/{source}/blocks").json()
    assert "".join(raw_inputs.values()) == "".join(block["text"] for block in blocks)
    assert client.get(f"/api/sources/{source}").json()["status"] == "parsed"


def test_invalid_citation_never_publishes_and_retry_recovers(knowledge):
    client, state, _ = knowledge
    notebook = client.post("/api/notebooks", json={"title": "Invalid"}).json()["id"]
    import_text(client, notebook, "A source-supported insight.")
    state["invalid"] = True
    page, job = create_page(client, notebook)
    assert job["error_code"] == "KNOWLEDGE_OUTPUT_INVALID"
    assert page["content_markdown"] == "" and not page["citations"]
    assert (
        len(
            [c for c in state["calls"] if c["messages"][0]["content"].startswith("Create a useful")]
        )
        == 2
    )
    state["invalid"] = False
    client.post(f"/api/jobs/{job['id']}/retry")
    assert wait_for_job(client, job["id"])["status"] == "completed"


def test_edit_update_preserves_old_information_and_unavailable_citations(knowledge):
    client, state, _ = knowledge
    notebook = client.post("/api/notebooks", json={"title": "Update"}).json()["id"]
    first = import_text(client, notebook, "Older knowledge remains useful.")
    page, _ = create_page(client, notebook)
    content = page["content_markdown"] + "\n\nMy personal note must survive."
    edit = {"title": "My knowledge", "content_markdown": content, "revision": page["revision"]}
    response = client.patch(f"/api/knowledge/{page['id']}", json=edit)
    assert response.status_code == 200
    assert client.patch(f"/api/knowledge/{page['id']}", json=edit).status_code == 409
    old_refs = page["citations"]
    client.delete(f"/api/sources/{first}")
    import_text(client, notebook, "A newly discovered insight adds context.")
    response = client.post(
        f"/api/knowledge/{page['id']}/update", json={"scope": {"kind": "selected"}}
    )
    assert wait_for_job(client, response.json()["id"])["status"] == "completed"
    updated = client.get(f"/api/knowledge/{page['id']}").json()
    assert updated["content_markdown"].startswith(content)
    assert updated["title"] == "My knowledge"
    assert "newly discovered insight" in updated["content_markdown"]
    assert all(updated["citations"][marker] == ref for marker, ref in old_refs.items())
    assert not client.get(f"/api/citations/{next(iter(old_refs.values()))}").json()["available"]
    assert len(updated["citations"]) > len(old_refs)


def test_update_conflicts_validate_evidence_and_preserve_edits(knowledge):
    client, state, _ = knowledge
    notebook = client.post("/api/notebooks", json={"title": "Conflict"}).json()["id"]
    import_text(client, notebook, "The older value was 10.")
    page, _ = create_page(client, notebook)
    import_text(client, notebook, "A correction explicitly replaces 10 with 12.")

    def replacement(data):
        marker = CITATION_PATTERN.findall(data["new_source_synthesis"])[-1]
        return json.dumps(
            {
                "additions_markdown": "",
                "replacements": [
                    {
                        "old_text": page["content_markdown"].split("\n\n")[-1],
                        "new_text": f"Corrected value is 12.[[{marker}]]",
                        "conflict_reason": "New source explicitly corrects the old numeric value.",
                        "conflict_evidence_ids": [marker],
                    }
                ],
            }
        )

    state["update_response"] = replacement
    job = client.post(f"/api/knowledge/{page['id']}/update", json={}).json()
    assert wait_for_job(client, job["id"])["status"] == "completed"
    updated = client.get(f"/api/knowledge/{page['id']}").json()
    assert "Corrected value is 12." in updated["content_markdown"]
    client.portal.call(client.app.state.jobs.stop)
    job = client.post(f"/api/knowledge/{page['id']}/update", json={}).json()
    assert client.post(f"/api/knowledge/{page['id']}/update", json={}).status_code == 409
    edited = client.patch(
        f"/api/knowledge/{page['id']}",
        json={
            "title": "New edit",
            "content_markdown": "Do not overwrite this edit.",
            "revision": updated["revision"],
        },
    )
    assert edited.status_code == 200
    client.portal.call(client.app.state.jobs.run_one)
    assert client.get(f"/api/jobs/{job['id']}").json()["error_code"] == "KNOWLEDGE_CHANGED"
    assert (
        client.get(f"/api/knowledge/{page['id']}").json()["content_markdown"]
        == "Do not overwrite this edit."
    )


def test_unknown_update_citations_are_atomic_and_chapter_scope_is_frozen(knowledge):
    client, state, _ = knowledge
    notebook = client.post("/api/notebooks", json={"title": "Scope"}).json()["id"]
    source = import_text(
        client, notebook, "# First\n\nFirst chapter fact.\n\n# Second\n\nSECOND_SENTINEL"
    )
    nodes = client.get(f"/api/sources/{source}/nodes").json()
    scope = {"kind": "node", "source_id": source, "node_id": nodes[1]["id"]}
    page, job = create_page(client, notebook, scope)
    assert job["status"] == "completed"
    assert "SECOND_SENTINEL" not in page["content_markdown"]
    prompt = state["calls"][-1]["messages"][-1]["content"]
    assert "First chapter fact" in prompt and "SECOND_SENTINEL" not in prompt
    state["update_response"] = lambda data: json.dumps(
        {"additions_markdown": "Fabricated [[NOT_REAL]]", "replacements": []}
    )
    job = client.post(f"/api/knowledge/{page['id']}/update", json={}).json()
    assert wait_for_job(client, job["id"])["error_code"] == "KNOWLEDGE_UPDATE_INVALID"
    assert (
        client.get(f"/api/knowledge/{page['id']}").json()["content_markdown"]
        == page["content_markdown"]
    )
    invalid_edit = client.patch(
        f"/api/knowledge/{page['id']}",
        json={"title": "Invalid", "content_markdown": "[[NOT_REAL]]", "revision": page["revision"]},
    )
    assert invalid_edit.status_code == 400
    client.portal.call(client.app.state.jobs.stop)
    response = client.post(f"/api/notebooks/{notebook}/knowledge", json={}).json()
    client.patch(f"/api/notebooks/{notebook}/sources/{source}", json={"enabled": False})
    client.portal.call(client.app.state.jobs.run_one)
    assert client.get(f"/api/jobs/{response['job']['id']}").json()["status"] == "completed"
    assert (
        client.post(f"/api/notebooks/{notebook}/knowledge", json={}).json()["error"]["code"]
        == "SCOPE_EMPTY"
    )


@pytest.mark.parametrize("kind", ["summary", "outline"])
def test_temporary_transformation_citations_explicit_save_and_discard(knowledge, kind):
    client, state, _ = knowledge
    notebook = client.post("/api/notebooks", json={"title": "Temporary"}).json()["id"]
    source = import_text(client, notebook, "# Learning\n\nPractise every day.")
    result = client.post(f"/api/notebooks/{notebook}/transformations", json={"kind": kind}).json()
    assert wait_for_job(client, result["job"]["id"])["status"] == "completed"
    value = client.get(f"/api/transformations/{result['id']}").json()
    assert client.get(f"/api/notebooks/{notebook}/knowledge").json() == []
    prompt = json.loads(state["calls"][-1]["messages"][-1]["content"])
    assert (
        "hierarchical outline" if kind == "outline" else "concise source-grounded summary"
    ) in prompt["task"]
    ref = next(iter(value["citations"].values()))
    preview = client.get(f"/api/citations/{ref}").json()
    assert preview["available"]
    assert preview["spans"][0]["source_id"] == source
    saved = client.post(f"/api/transformations/{result['id']}/save").json()
    assert client.post(f"/api/transformations/{result['id']}/save").json()["id"] == saved["id"]
    assert len(client.get(f"/api/notebooks/{notebook}/knowledge").json()) == 1
    assert saved["content_markdown"] == value["content_markdown"]
    assert client.delete(f"/api/transformations/{result['id']}").status_code == 204
    assert client.get(f"/api/transformations/{result['id']}").status_code == 404
    assert client.get(f"/api/citations/{ref}").status_code == 404
    actual_ref = next(iter(saved["citations"].values()))
    assert client.get(f"/api/citations/{actual_ref}").json()["spans"] == preview["spans"]
    with client.app.state.db.connect() as conn:
        assert not conn.execute(
            "SELECT 1 FROM synthesis_checkpoints WHERE job_id=?", (result["job"]["id"],)
        ).fetchone()


def test_discarded_and_expired_transforms_never_create_knowledge(knowledge):
    client, state, _ = knowledge
    notebook = client.post("/api/notebooks", json={"title": "Discard"}).json()["id"]
    import_text(client, notebook, "A source to summarize.")
    client.portal.call(client.app.state.jobs.stop)
    result = client.post(
        f"/api/notebooks/{notebook}/transformations", json={"kind": "summary"}
    ).json()
    before = len(state["calls"])
    client.delete(f"/api/transformations/{result['id']}")
    client.portal.call(client.app.state.jobs.run_one)
    assert len(state["calls"]) == before
    assert client.get(f"/api/notebooks/{notebook}/knowledge").json() == []
    result = client.post(
        f"/api/notebooks/{notebook}/transformations", json={"kind": "outline"}
    ).json()
    client.portal.call(client.app.state.jobs.run_one)
    with client.app.state.db.connect() as conn:
        conn.execute("UPDATE transformations SET expires_at=0 WHERE id=?", (result["id"],))
    assert client.get(f"/api/transformations/{result['id']}").status_code == 404
    assert client.post(f"/api/transformations/{result['id']}/save").status_code == 404
    assert client.get(f"/api/notebooks/{notebook}/knowledge").json() == []
