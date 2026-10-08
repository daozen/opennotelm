import asyncio
import json
import threading

import httpx
import pytest
from audio_factory import sample_wav
from fastapi.testclient import TestClient
from grounded_provider import completion
from opennotelm.main import create_app
from opennotelm.podcast_content import speaking_budget, speech_chunks
from test_knowledge import import_text
from test_models import config
from test_sources import wait_for_job


@pytest.fixture
def podcast(settings):
    state = {
        "speech": [],
        "speech_headers": [],
        "scripts": 0,
        "fail_speech": False,
        "block_speech": False,
        "entered": threading.Event(),
        "active": 0,
    }

    async def handler(request):
        body = json.loads(request.content)
        if request.url.path.endswith("/audio/speech"):
            state["speech"].append(body)
            state["speech_headers"].append(dict(request.headers))
            if state["block_speech"]:
                state["active"] += 1
                state["entered"].set()
                try:
                    await asyncio.Event().wait()
                finally:
                    state["active"] -= 1
            if state["fail_speech"] and len(state["speech"]) % 2 == 0:
                return httpx.Response(400, json={"error": "PRIVATE_PROVIDER_BODY"})
            return httpx.Response(200, content=sample_wav(), headers={"Content-Type": "audio/wav"})
        system = body["messages"][0]["content"]
        prompt = body["messages"][-1]["content"]
        data = json.loads(prompt) if prompt.startswith("{") else {}
        if system.startswith("Resolve only the explicit"):
            answer = {"source_only": False, "chapter_only": False}
        elif system.startswith("Create a useful, well-structured reading dossier"):
            answer = "# Reading\n\n" + "\n".join(
                f"{e['text']}[[{e['id']}]]" for e in data["material"]
            )
        elif system.startswith("Plan a coherent podcast"):
            evidence = data["registered_evidence"][0]["id"]
            answer = {
                "title": "Learning together",
                "sections": [
                    {
                        "title": f"Part {i}",
                        "focus": "Explain a mechanism",
                        "evidence_ids": [evidence],
                    }
                    for i in range(data["speaking_budget"]["section_count"])
                ],
            }
        elif system.startswith("Write one complete podcast"):
            state["scripts"] += 1
            evidence = data["original_evidence"][0]["id"]
            answer = {
                "turns": [
                    {
                        "speaker": "A",
                        "text": f"Explanation {data['section_index']}.",
                        "basis": "source",
                        "evidence_ids": [evidence],
                    },
                    {
                        "speaker": "B",
                        "text": "For example, practice strengthens a habit.",
                        "basis": "analogy",
                        "evidence_ids": [],
                    },
                ]
            }
            if data["format"] == "solo":
                answer["turns"] = answer["turns"][:1]
        else:
            answer = completion(body)
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})

    with TestClient(create_app(settings, transport=httpx.MockTransport(handler))) as client:
        assert client.post("/api/settings/models/test", json=config("language")).status_code == 200
        speech = {**config("speech"), "voice_a": "Ryan", "voice_b": "Vivian"}
        assert client.post("/api/settings/models/test", json=speech).status_code == 200
        notebook = client.post("/api/notebooks", json={"title": "Podcast tests"}).json()["id"]
        source = import_text(
            client,
            notebook,
            "Practice supports learning. Reflection makes practice more effective.",
        )
        state["speech"].clear()
        state["speech_headers"].clear()
        yield client, state, notebook, source


def make_episode(podcast, **options):
    client, _, notebook, source = podcast
    result = client.post(
        f"/api/notebooks/{notebook}/podcasts",
        json={"scope": {"kind": "source", "source_id": source}, "target_minutes": 5, **options},
    )
    assert result.status_code == 202, result.text
    episode = result.json()
    job = wait_for_job(client, episode["job"]["id"])
    return client.get(f"/api/podcasts/{episode['id']}").json(), job


def test_audio_citations_range_and_edit_reuses_unchanged_audio(podcast):
    client, state, notebook, source = podcast
    episode, job = make_episode(podcast)
    assert job["status"] == "completed", job
    assert episode["status"] == "completed"
    assert all(
        h["x-opennotelm-speech-policy"] == "podcast-stable-v1"
        and h["x-opennotelm-speech-language"] == episode["input"]["language"]
        for h in state["speech_headers"]
    )
    assert episode["download_available"]
    transcript = client.get(f"/api/podcasts/{episode['id']}/transcript")
    assert transcript.status_code == 200
    assert "Learning%20together.json" in transcript.headers["Content-Disposition"]
    assert len(episode["segments"]) == 3
    assert {r["voice"] for r in state["speech"]} == {"Ryan", "Vivian"}
    audio_url = f"/api/podcasts/{episode['id']}/audio"
    assert client.head(audio_url).status_code == 200
    response = client.get(audio_url, headers={"Range": "bytes=0-99"})
    assert response.status_code == 206 and len(response.content) == 100
    for segment in episode["segments"]:
        for citation in segment["citations"].values():
            span = client.get(f"/api/citations/{citation}").json()["spans"][0]
            assert span["source_id"] == source
            assert span["quote"]
    before = len(state["speech"])
    segment = episode["segments"][0]
    edited = {**segment["script"], "revision": segment["revision"]}
    edited["turns"][0]["text"] = "A revised explanation."
    response = client.patch(f"/api/podcasts/{episode['id']}/segments/{segment['id']}", json=edited)
    assert response.status_code == 200, response.text
    assert not response.json()["download_available"]
    resumed = client.post(f"/api/podcasts/{episode['id']}/resume").json()
    assert wait_for_job(client, resumed["job"]["id"])["status"] == "completed"
    assert len(state["speech"]) == before + 1
    assert state["scripts"] == 3
    report = client.get(f"/api/podcasts/{episode['id']}/diagnostics")
    assert "PRIVATE_PROVIDER_BODY" not in report.text and "Practice supports" not in report.text
    bundle = client.post(
        f"/api/notebooks/{notebook}/artifacts/download",
        json={"items": [{"kind": "podcast", "id": episode["id"]}]},
    )
    assert bundle.status_code == 200, bundle.text
    assert client.get(bundle.json()["download_url"]).status_code == 200


def test_failure_resume_and_delete_preserve_completed_chunks(podcast, settings):
    client, state, notebook, source = podcast
    client.put("/api/settings/models/speech-generation", json={"concurrency": 1})
    state["fail_speech"] = True
    episode, job = make_episode(podcast)
    assert job["status"] == "failed", job
    assert episode["saved_audio_chunks"] == 1
    scripts = state["scripts"]
    state["fail_speech"] = False
    resumed = client.post(f"/api/podcasts/{episode['id']}/resume").json()
    assert wait_for_job(client, resumed["job"]["id"])["status"] == "completed"
    assert state["scripts"] == scripts
    assert len(state["speech"]) == 5  # Repeated unchanged B turns share their checkpoint.
    root = settings.data_dir / "podcasts" / episode["id"]
    assert root.exists()
    assert client.delete(f"/api/podcasts/{episode['id']}").status_code == 204
    assert not root.exists()
    assert client.get(f"/api/sources/{source}").status_code == 200


def test_script_only_and_model_snapshot(podcast):
    client, state, _, _ = podcast
    episode, job = make_episode(podcast, script_only=True, format="solo", target_minutes=30)
    assert job["status"] == "completed", job
    assert episode["status"] == "script_ready" and len(episode["segments"]) == 15
    assert not state["speech"]
    response = client.post(f"/api/podcasts/{episode['id']}/resume")
    assert response.status_code == 202
    assert wait_for_job(client, response.json()["job"]["id"])["status"] == "completed"


def test_time_budgets_and_lossless_unicode_chunking():
    assert speaking_budget(60, "en")["section_count"] == 30
    assert speaking_budget(60, "en")["target_units"] == 8700
    assert speaking_budget(30, "zh-CN")["target_units"] == 7200
    text = ("A sentence.\n" * 400) + ("一段完整的解说。" * 200)
    chunks = speech_chunks(
        [{"id": "x", "script": {"turns": [{"speaker": "A", "text": text}]}}], "openai"
    )
    assert "".join(c["turns"][0]["text"] for c in chunks) == text
    assert all(len(c["turns"][0]["text"]) <= 600 for c in chunks)


def test_stop_joins_inflight_speech_and_resume_keeps_scripts(podcast):
    client, state, _, _ = podcast
    episode, _ = make_episode(podcast, script_only=True)
    state["block_speech"] = True
    response = client.post(f"/api/podcasts/{episode['id']}/resume")
    assert response.status_code == 202
    assert state["entered"].wait(5)
    response = client.post(f"/api/podcasts/{episode['id']}/stop")
    assert response.status_code == 200
    assert state["active"] == 0
    assert response.json()["status"] == "paused"
    assert response.json()["job"]["status"] == "cancelled"
    state["block_speech"] = False
    resumed = client.post(f"/api/podcasts/{episode['id']}/resume").json()
    assert wait_for_job(client, resumed["job"]["id"])["status"] == "completed"
    assert state["scripts"] == 3


def test_queued_batch_stop_survives_worker_restart_and_deleted_batch_is_not_recreated(podcast):
    client, _, notebook, source = podcast
    client.portal.call(client.app.state.jobs.stop)
    payload = {
        "scope": {"kind": "selected", "source_ids": [source]},
        "request_key": "podcast-batch-test",
        "target_minutes": 60,
        "script_only": True,
    }
    url = f"/api/notebooks/{notebook}/podcasts/batch"
    created = client.post(url, json=payload)
    assert created.status_code == 202, created.text
    episodes = created.json()["podcasts"]
    assert client.post(url, json=payload).json()["podcasts"][0]["id"] == episodes[0]["id"]
    episode = episodes[0]
    stopped = client.post(f"/api/podcasts/{episode['id']}/stop").json()
    assert stopped["job"]["status"] == "cancelled"
    client.portal.call(client.app.state.jobs.start)
    assert client.get(f"/api/podcasts/{episode['id']}").json()["job"]["status"] == "cancelled"
    resumed = client.post(f"/api/podcasts/{episode['id']}/resume").json()
    assert wait_for_job(client, resumed["job"]["id"])["status"] == "completed"
    assert len(client.get(f"/api/podcasts/{episode['id']}").json()["segments"]) == 30
    assert client.delete(f"/api/podcasts/{episode['id']}").status_code == 204
    assert client.post(url, json=payload).status_code == 409


def test_legacy_speech_resume_keeps_exact_chunk_signatures_and_no_new_policy(podcast):
    from opennotelm.podcasts import VERSION, digest

    client, state, _, _ = podcast
    episode, _ = make_episode(podcast, script_only=True)
    with client.app.state.db.connect() as conn:
        row = conn.execute(
            "SELECT settings_json FROM podcasts WHERE id=?", (episode["id"],)
        ).fetchone()
        settings = json.loads(row[0])
        settings.pop("speech_policy")
        conn.execute(
            "UPDATE podcasts SET settings_json=? WHERE id=?", (json.dumps(settings), episode["id"])
        )
    resumed = client.post(f"/api/podcasts/{episode['id']}/resume").json()
    assert wait_for_job(client, resumed["job"]["id"])["status"] == "completed"
    assert state["speech_headers"]
    assert all("x-opennotelm-speech-policy" not in h for h in state["speech_headers"])
    with client.app.state.db.connect() as conn:
        row = conn.execute(
            "SELECT settings_json,input_json FROM podcasts WHERE id=?", (episode["id"],)
        ).fetchone()
        settings, inputs = json.loads(row[0]), json.loads(row[1])
        actual = {
            r[0]
            for r in conn.execute(
                "SELECT input_hash FROM podcast_audio_chunks WHERE podcast_id=?", (episode["id"],)
            )
        }
    current = client.get(f"/api/podcasts/{episode['id']}").json()
    expected = {
        digest([VERSION, settings["speech"]["config"], inputs["language"], chunk["turns"]])
        for chunk in speech_chunks(current["segments"], "openai")
    }
    assert actual == expected
    before = len(state["speech"])
    segment = current["segments"][0]
    edited = {**segment["script"], "revision": segment["revision"]}
    edited["turns"][0]["text"] = "A revised explanation for this old episode."
    assert (
        client.patch(
            f"/api/podcasts/{episode['id']}/segments/{segment['id']}", json=edited
        ).status_code
        == 200
    )
    resumed = client.post(f"/api/podcasts/{episode['id']}/resume").json()
    assert wait_for_job(client, resumed["job"]["id"])["status"] == "completed"
    assert len(state["speech"]) == before + 1
    assert "x-opennotelm-speech-policy" not in state["speech_headers"][-1]
