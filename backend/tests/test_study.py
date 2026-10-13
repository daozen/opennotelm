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
from opennotelm.study_schemas import FlashcardContent, QuizContent, validate_study
from test_knowledge import import_text
from test_models import config
from test_sources import wait_for_job


@pytest.fixture
def study(settings):
    state = {
        "reading": 0,
        "writing": 0,
        "fail": False,
        "fail_after_first": False,
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
        if system.startswith("Create source-grounded study material"):
            state["writing"] += 1
            if state["block"]:
                state["active"] += 1
                state["entered"].set()
                try:
                    await asyncio.Event().wait()
                finally:
                    state["active"] -= 1
            data = json.loads(body["messages"][-1]["content"])
            if state["fail"] or (state["fail_after_first"] and data.get("already_written_prompts")):
                return httpx.Response(400, json={"error": "PRIVATE_STUDY_PROVIDER_TEXT"})
        return httpx.Response(200, json={"choices": [{"message": {"content": completion(body)}}]})

    state["transport"] = httpx.MockTransport(handler)
    with TestClient(create_app(settings, transport=state["transport"])) as client:
        assert client.post("/api/settings/models/test", json=config("language")).status_code == 200
        notebook = client.post("/api/notebooks", json={"title": "Study test"}).json()["id"]
        source = import_text(
            client, notebook, "Practice strengthens learning. Reflection improves the next attempt."
        )
        yield client, state, notebook, source


def create(study, resource, **extra):
    client, _, notebook, source = study
    response = client.post(
        f"/api/notebooks/{notebook}/{resource}",
        json={
            "scope": {"kind": "source", "source_id": source},
            "count": 5,
            "instruction": "Explain clearly.\nUse original evidence.",
            **extra,
        },
    )
    assert response.status_code == 202, response.text
    value = response.json()
    job = wait_for_job(client, value["job"]["id"])
    return client.get(f"/api/{resource}/{value['id']}").json(), job


@pytest.mark.parametrize("resource,kind", [("quizzes", "quiz"), ("flashcards", "flashcards")])
def test_citations_languages_history_sources_export_rename_delete(study, settings, resource, kind):
    client, state, notebook, source = study
    value, job = create(study, resource, language="ja", title_mode="source")
    assert job["status"] == "completed", job
    assert len(value["content"]["items"]) == 5 and value["download_available"]
    assert value["kind"] == kind
    assert value["title"] == client.get(f"/api/sources/{source}").json()["title"]
    url = f"/api/{resource}/{value['id']}"
    if kind == "quiz":
        assert "correct_option_id" not in json.dumps(value["content"])
        assert "explanation" not in json.dumps(value["content"])
    assert "settings" not in value and "progress_json" not in value
    for citation in value["citations"].values():
        span = client.get(f"/api/citations/{citation}").json()["spans"][0]
        block = client.get(f"/api/sources/{source}/blocks").json()[0]
        assert span["quote"] == block["text"][span["start_offset"] : span["end_offset"]]
    assert client.get(url + "/sources").json()["sources"][0]["id"] == source
    assert (
        client.get(f"/api/artifacts/instruction-history?kind={kind}")
        .json()["items"][0]["instruction"]
        .startswith("Explain clearly")
    )
    assert client.get("/api/artifacts/instruction-history?kind=deck").json()["items"] == []
    generated = [
        body
        for body in state["calls"]
        if body["messages"][0]["content"].startswith(("Create source-grounded", "Create a useful"))
    ]
    assert generated and all("Japanese" in body["messages"][0]["content"] for body in generated)
    before = client.get(url + "/download").content
    exported = client.get(url + "/download?format=json").json()
    assert len(exported["content"]["items"]) == 5
    if kind == "quiz":
        assert exported["content"]["items"][0]["correct_option_id"] == "A"
    assert client.patch(url, json={"title": "Study 测试"}).status_code == 200
    assert client.get(url + "/download").content == before
    assert "Study%20" in client.get(url + "/download").headers["content-disposition"]
    bundle = client.post(
        f"/api/notebooks/{notebook}/artifacts/download",
        json={"items": [{"kind": kind, "id": value["id"]}]},
    )
    assert bundle.status_code == 200, bundle.text
    with ZipFile(BytesIO(client.get(bundle.json()["download_url"]).content)) as archive:
        assert archive.read(archive.namelist()[0]) == before
    diagnostic = client.get(url + "/diagnostics").text
    assert (
        "PRIVATE_STUDY" not in diagnostic
        and "Practice strengthens" not in diagnostic
        and "Explain clearly" not in diagnostic
    )
    directory = settings.data_dir / resource / value["id"]
    assert directory.is_dir()
    assert client.delete(url).status_code == 204
    assert not directory.exists()
    assert client.get(url).status_code == 404
    assert client.get(f"/api/sources/{source}").status_code == 200
    assert client.get(f"/api/artifacts/instruction-history?kind={kind}").json()["items"] == []
    assert client.get(bundle.json()["download_url"]).status_code == 404


@pytest.mark.parametrize("resource,choice", [("quizzes", "B"), ("flashcards", "review")])
def test_progress_is_local_revisioned_restorable_and_explicitly_reset(
    study, settings, resource, choice
):
    from restart_support import restart

    client, state, _, _ = study
    value, job = create(study, resource)
    assert job["status"] == "completed", job
    calls = len(state["calls"])
    url = f"/api/{resource}/{value['id']}"
    item = value["content"]["items"][0]
    payload = {"item_id": item["id"], "choice": choice, "revision": 0}
    answered = client.post(url + "/responses", json=payload)
    assert answered.status_code == 200, answered.text
    progress = answered.json()["progress"]
    assert progress["revision"] == 1 and progress["responses"][item["id"]]["choice"] == choice
    assert client.post(url + "/responses", json=payload).status_code == 409
    if resource == "quizzes":
        assert progress["responses"][item["id"]]["correct"] is False
        assert progress["responses"][item["id"]]["correct_option_id"] == "A"
        assert (
            client.post(
                url + "/responses", json={**payload, "choice": "A", "revision": 1}
            ).status_code
            == 409
        )
    else:
        new = client.post(url + "/responses", json={**payload, "choice": "known", "revision": 1})
        assert new.status_code == 200
        progress = new.json()["progress"]
    assert (
        client.post(
            url + "/responses",
            json={**payload, "item_id": "missing", "revision": progress["revision"]},
        ).status_code
        == 404
    )
    assert (
        client.post(
            url + "/responses",
            json={
                **payload,
                "item_id": value["content"]["items"][1]["id"],
                "choice": "invalid",
                "revision": progress["revision"],
            },
        ).status_code
        == 400
    )
    with restart(client, settings, transport=state["transport"]) as restarted:
        assert restarted.get(url).json()["progress"] == progress
    assert client.post(url + "/reset", json={"revision": 0}).status_code == 409
    reset = client.post(url + "/reset", json={"revision": progress["revision"]})
    assert reset.status_code == 200 and reset.json()["progress"]["responses"] == {}
    assert reset.json()["content"] == value["content"]
    assert len(state["calls"]) == calls


@pytest.mark.parametrize("resource", ["quizzes", "flashcards"])
def test_failed_and_stopped_tasks_resume_checkpoints_and_frozen_models(study, resource):
    client, state, _, source = study
    state["fail"] = True
    value, job = create(study, resource)
    assert job["status"] == "failed" and value["status"] == "failed"
    reading = state["reading"]
    assert reading > 0
    url = f"/api/{resource}/{value['id']}"
    changed = {**config("language"), "model_id": "other-model"}
    client.post("/api/settings/models/test", json=changed)
    retry = client.post(url + "/resume").json()
    assert wait_for_job(client, retry["job"]["id"])["error_code"] == "STUDY_MODEL_CHANGED"
    client.post("/api/settings/models/test", json=config("language"))
    state["fail"] = False
    state["block"] = True
    resumed = client.post(url + "/resume")
    assert resumed.status_code == 202
    assert state["entered"].wait(5)
    paused = client.post(url + "/stop").json()
    assert paused["status"] == "paused" and state["active"] == 0
    assert client.patch(url, json={"title": "Paused"}).status_code == 200
    state["block"] = False
    resumed = client.post(url + "/resume").json()
    assert wait_for_job(client, resumed["job"]["id"])["status"] == "completed"
    assert state["reading"] == reading
    assert client.get(f"/api/sources/{source}").status_code == 200


@pytest.mark.parametrize("resource", ["quizzes", "flashcards"])
def test_batch_scope_idempotency_tombstone_and_ownership(study, settings, resource):
    from epub_factory import make_epub
    from restart_support import restart

    client, state, notebook, source = study
    uploaded = client.post(
        f"/api/notebooks/{notebook}/sources/upload", files={"file": ("Learning.epub", make_epub())}
    ).json()
    assert wait_for_job(client, uploaded["job"]["id"])["status"] == "completed"
    book = uploaded["source"]["id"]
    chapters = [
        n for n in client.get(f"/api/sources/{book}/nodes").json() if n["type"] == "chapter"
    ]
    url = f"/api/notebooks/{notebook}/{resource}/batch"
    payload = {
        "scope": {
            "kind": "nodes",
            "source_id": book,
            "node_ids": [c["id"] for c in reversed(chapters)],
        },
        "title_mode": "source",
        "count": 5,
        "request_key": "study-chapters-test",
    }
    response = client.post(url, json=payload)
    assert response.status_code == 202, response.text
    for created, chapter in zip(response.json()[resource], chapters, strict=True):
        assert created["input"]["scope"]["kind"] == "nodes"
        assert wait_for_job(client, created["job"]["id"])["status"] == "completed"
        owner = getattr(client.app.state, resource)
        record = owner.record(created["id"])
        assert record["source_scope"]["node_id"] == chapter["id"]
        assert record["understanding"]["work_context"]["whole_work_readings"]
        manifest = client.get(f"/api/{resource}/{created['id']}/sources").json()["sources"][0]
        section = manifest["chapters"][0]
        assert record["title"] == f"{manifest['title']}-{section['number']}-{section['title']}"
    assert [i["id"] for i in client.post(url, json=payload).json()[resource]] == [
        i["id"] for i in response.json()[resource]
    ]
    assert client.post(url, json={**payload, "count": 10}).status_code == 409
    first = response.json()[resource][0]
    other = client.post("/api/notebooks", json={"title": "Other"}).json()["id"]
    assert (
        client.post(
            f"/api/notebooks/{other}/{resource}",
            json={"scope": {"kind": "source", "source_id": source}},
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/api/notebooks/{other}/artifacts/download",
            json={"items": [{"kind": first["kind"], "id": first["id"]}]},
        ).status_code
        == 404
    )
    client.portal.call(client.app.state.jobs.stop)
    queued = client.post(
        f"/api/notebooks/{notebook}/{resource}",
        json={"scope": {"kind": "source", "source_id": source}},
    ).json()
    client.post(f"/api/{resource}/{queued['id']}/stop")
    with restart(client, settings, transport=state["transport"]) as restarted:
        assert (
            restarted.get(f"/api/{resource}/{queued['id']}").json()["job"]["status"] == "cancelled"
        )
    assert client.delete(f"/api/{resource}/{first['id']}").status_code == 204
    assert client.post(url, json=payload).status_code == 409
    assert client.delete(f"/api/notebooks/{notebook}").status_code == 204
    assert client.get(f"/api/{resource}/{queued['id']}").status_code == 404


def test_validation_rejects_unregistered_references_duplicate_ids_options_and_count():
    raw = {
        "title": "Quiz",
        "items": [
            {
                "id": "q",
                "question": "What?",
                "options": [{"id": k, "text": k} for k in "ABCD"],
                "correct_option_id": "A",
                "explanation": "Because.",
                "evidence_ids": ["E1"],
            }
        ],
    }
    validate_study(QuizContent(**raw), {"E1"}, {"E1"}, 5)
    for update in (
        {"evidence_ids": ["invented"]},
        {"question": " "},
        {"explanation": " "},
        {"options": [{"id": "A", "text": k} for k in "ABCD"]},
    ):
        candidate = {**raw, "items": [{**raw["items"][0], **update}]}
        with pytest.raises(ValueError):
            validate_study(QuizContent(**candidate), {"E1"}, {"E1"}, 5)
    with pytest.raises(ValueError):
        validate_study(QuizContent(**raw), {"E1"}, {"other"}, 5)
    with pytest.raises(ValueError):
        validate_study(QuizContent(**{**raw, "items": raw["items"] * 2}), {"E1"}, {"E1"}, 5)
    with pytest.raises(ValueError):
        validate_study(QuizContent(**raw), {"E1"}, {"E1"}, 0)
    with pytest.raises(ValueError):
        validate_study(
            FlashcardContent(
                title="Cards",
                items=[{"id": "f", "front": " ", "back": "Answer", "evidence_ids": ["E1"]}],
            ),
            {"E1"},
            {"E1"},
            5,
        )


@pytest.mark.parametrize("resource", ["quizzes", "flashcards"])
def test_large_sets_checkpoint_completed_batches_without_repeating(study, resource):
    client, state, _, _ = study
    state["fail_after_first"] = True
    value, job = create(study, resource, count=40, language="de", difficulty="hard")
    assert job["status"] == "failed"
    service = getattr(client.app.state, resource)
    saved = service.record(value["id"])
    assert len(json.loads(saved["draft_json"])["items"]) == 8
    assert "draft_json" not in value and value["content"] is None
    reads, writes = state["reading"], state["writing"]
    state["fail_after_first"] = False
    url = f"/api/{resource}/{value['id']}"
    job = client.post(url + "/resume").json()["job"]
    assert wait_for_job(client, job["id"])["status"] == "completed"
    value = client.get(url).json()
    assert len(value["content"]["items"]) == 40
    assert len({item["id"] for item in value["content"]["items"]}) == 40
    assert state["reading"] == reads and state["writing"] == writes + 4
    writes = [b for b in state["calls"] if b["messages"][0]["content"].startswith(STUDY_PREFIX)]
    for body in writes:
        data = json.loads(body["messages"][-1]["content"])
        assert data["requested_count"] <= 8 and data["difficulty"] == "hard"
        assert "German" in body["messages"][0]["content"]


STUDY_PREFIX = "Create source-grounded study material"


def test_study_knowledge_snapshot_retains_original_citations_and_ownership(study):
    client, _, notebook, source = study
    page = client.post(
        f"/api/notebooks/{notebook}/knowledge",
        json={"scope": {"kind": "source", "source_id": source}},
    ).json()
    assert wait_for_job(client, page["job"]["id"])["status"] == "completed"
    for resource in ("quizzes", "flashcards"):
        value, job = create(
            study,
            resource,
            scope={"kind": "knowledge", "knowledge_page_id": page["page"]["id"]},
        )
        assert job["status"] == "completed" and value["citations"]
        manifest = client.get(f"/api/{resource}/{value['id']}/sources").json()
        assert manifest["knowledge"][0]["id"] == page["page"]["id"]
        other = client.post("/api/notebooks", json={"title": "Other"}).json()["id"]
        assert (
            client.post(
                f"/api/notebooks/{other}/{resource}",
                json={"scope": {"kind": "knowledge", "knowledge_page_id": page["page"]["id"]}},
            ).status_code
            == 400
        )
