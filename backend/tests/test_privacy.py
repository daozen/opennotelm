import asyncio
import json
from dataclasses import replace
from uuid import UUID, uuid4

import httpx
import pytest
from opennotelm.db import Database
from opennotelm.telemetry import EventProperties, TelemetryService
from pydantic import ValidationError
from test_models import config
from test_sources import wait_for_job


def service(settings, handler):
    settings.prepare()
    db = Database(settings.data_dir / "app.db")
    db.migrate()
    return TelemetryService(
        db,
        replace(
            settings,
            telemetry_host="https://statistics.invalid",
            telemetry_project_token="public-project-token",
        ),
        httpx.MockTransport(handler),
    )


def test_off_is_silent_allowlist_rejects_content_and_sender_uses_anonymous_identity(settings):
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200)

    telemetry = service(settings, handler)
    telemetry.capture("app_started")
    assert telemetry.status()["queued_events"] == 0
    assert asyncio.run(telemetry.send_once()) and not sent
    asyncio.run(telemetry.set_enabled(True))
    with pytest.raises(TypeError):
        telemetry.capture("app_started", {"prompt": "PRIVATE"})
    with pytest.raises(ValidationError):
        EventProperties(source_type="private filename")
    with pytest.raises(ValidationError):
        EventProperties.model_validate({"api_key": "PRIVATE"})
    with pytest.raises(ValidationError):
        telemetry.capture("$identify")
    telemetry.capture(
        "source_import_completed",
        EventProperties(
            source_type="epub",
            size_bucket="1_to_10mb",
            duration_ms=2345,
            error_code="PRIVATE_SECRET",
        ),
    )
    assert asyncio.run(telemetry.send_once())
    body = json.loads(sent[0].content)
    event = body["batch"][0]
    assert UUID(event["distinct_id"]) and UUID(event["uuid"])
    assert event["distinct_id"] == telemetry.install_id
    assert set(event["properties"]) == {
        "source_type",
        "size_bucket",
        "duration_ms",
        "error_code",
        "app_version",
        "os",
        "$process_person_profile",
        "$geoip_disable",
    }
    assert event["properties"]["duration_ms"] == 10000
    assert event["properties"]["error_code"] == "UNKNOWN_ERROR"
    assert event["properties"]["$process_person_profile"] is False
    assert event["properties"]["$geoip_disable"] is True
    assert "authorization" not in sent[0].headers and "cookie" not in sent[0].headers
    assert "PRIVATE" not in sent[0].content.decode()
    assert telemetry.status()["queued_events"] == 0
    restarted = service(settings, handler)
    assert restarted.install_id == telemetry.install_id and restarted.enabled()


def test_sender_retries_without_duplicate_identity_and_disable_clears_queue(settings):
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(503 if len(sent) == 1 else 200)

    telemetry = service(settings, handler)
    asyncio.run(telemetry.set_enabled(True))
    telemetry.capture("app_started")
    assert not asyncio.run(telemetry.send_once())
    assert telemetry.status()["queued_events"] == 1
    assert asyncio.run(telemetry.send_once())
    assert sent[0] == sent[1]
    telemetry.capture("app_started")
    asyncio.run(telemetry.set_enabled(False))
    telemetry.capture("app_started")
    assert telemetry.status()["queued_events"] == 0
    assert asyncio.run(telemetry.send_once()) and len(sent) == 2


def test_unconfigured_receiver_preserves_choice_without_sending(settings):
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200)

    telemetry = service(settings, handler)
    telemetry.settings = replace(telemetry.settings, telemetry_project_token="")
    preferences = asyncio.run(telemetry.set_enabled(True))
    assert preferences["telemetry_enabled"] is True
    telemetry.capture("app_started")
    assert telemetry.status() == {"enabled": True, "configured": False, "queued_events": 1}
    assert asyncio.run(telemetry.send_once()) and not sent
    assert telemetry.status()["queued_events"] == 1
    asyncio.run(telemetry.set_enabled(False))
    assert telemetry.status() == {"enabled": False, "configured": False, "queued_events": 0}


def test_sender_drops_tampered_properties_and_does_not_follow_redirects(settings):
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(302, headers={"Location": "https://another.invalid/collect"})

    telemetry = service(settings, handler)
    asyncio.run(telemetry.set_enabled(True))
    telemetry.capture("app_started")
    with telemetry.db.connect() as conn:
        conn.execute(
            "UPDATE telemetry_queue SET properties_json=?",
            (json.dumps({"source_content": "PRIVATE"}),),
        )
    assert asyncio.run(telemetry.send_once()) and not sent
    telemetry.capture("app_started")
    assert not asyncio.run(telemetry.send_once())
    assert len(sent) == 1 and sent[0].url.host == "statistics.invalid"


def test_queue_has_age_and_size_limits(settings):
    telemetry = service(settings, lambda r: httpx.Response(200))
    asyncio.run(telemetry.set_enabled(True))
    with telemetry.db.connect() as conn:
        import time

        conn.executemany(
            "INSERT INTO telemetry_queue VALUES (?,'app_started','{}','now',?)",
            [(str(uuid4()), int(time.time())) for _ in range(1010)],
        )
        conn.execute(
            "INSERT INTO telemetry_queue VALUES (?,'app_started','{}','now',0)", (str(uuid4()),)
        )
    telemetry.capture("app_started")
    assert telemetry.status()["queued_events"] == 1000
    with telemetry.db.connect() as conn:
        assert (
            conn.execute("SELECT count(*) FROM telemetry_queue WHERE queued_at=0").fetchone()[0]
            == 0
        )


def test_diagnostics_and_job_events_never_export_content_or_provider_secrets(client):
    client.put("/api/settings/preferences", json={"telemetry_enabled": True})
    client.post("/api/settings/models/test", json=config("language"))
    notebook = client.post("/api/notebooks", json={"title": "PRIVATE_NOTEBOOK"}).json()["id"]
    uploaded = client.post(
        f"/api/notebooks/{notebook}/sources/upload",
        files={"file": ("PRIVATE_FILENAME.txt", b"PRIVATE_SOURCE_BODY")},
    ).json()
    assert wait_for_job(client, uploaded["job"]["id"])["status"] == "completed"
    report = client.get("/api/diagnostics")
    assert report.status_code == 200 and "attachment" in report.headers["content-disposition"]
    assert report.json()["models"] == [{"role": "language", "model_id": "test-model"}]
    assert report.json()["source_counts"] == {"text": 1}
    assert report.json()["jobs"] and report.json()["job_traces"]
    forbidden = [
        "PRIVATE_NOTEBOOK",
        "PRIVATE_FILENAME",
        "PRIVATE_SOURCE_BODY",
        "secret-never-leak",
        "https://provider.test",
        "api_key_secret_ref",
        "payload_json",
    ]
    with client.app.state.db.connect() as conn:
        events = [dict(row) for row in conn.execute("SELECT * FROM telemetry_queue")]
    for value in forbidden:
        assert value not in report.text and value not in json.dumps(events)
    names = {row["event"] for row in events}
    assert {"model_connection_tested", "source_import_started", "source_import_completed"} <= names
    # Native framework telemetry must never activate from OTEL environment settings.
    assert not client.app._native_telemetry.enabled()
    assert client.app._telemetry["auto_configure"] is False


def test_optional_telemetry_failure_cannot_fail_a_job(client, monkeypatch):
    queue = client.app.state.jobs
    client.portal.call(queue.stop)

    def broken(*args, **kwargs):
        raise RuntimeError("PRIVATE_PROVIDER_ERROR")

    async def handler(payload, context):
        return {"ok": True}

    monkeypatch.setattr(client.app.state.telemetry, "capture", broken)
    queue.handlers["knowledge_generate"] = handler
    job = queue.enqueue("knowledge_generate", "test", {})
    client.portal.call(queue.run_one)
    assert queue.get(job["id"])["status"] == "completed"


def test_disabling_waits_for_prior_send_and_prevents_any_following_send(settings):
    sent = []

    async def scenario():
        started, finish = asyncio.Event(), asyncio.Event()

        async def handler(request):
            sent.append(request)
            started.set()
            await finish.wait()
            return httpx.Response(200)

        telemetry = service(settings, handler)
        await telemetry.set_enabled(True)
        telemetry.capture("app_started")
        sending = asyncio.create_task(telemetry.send_once())
        await started.wait()
        disable = asyncio.create_task(telemetry.set_enabled(False))
        await asyncio.sleep(0)
        assert not disable.done()
        telemetry.capture("app_started")
        finish.set()
        await sending
        await disable
        assert telemetry.status()["queued_events"] == 0
        telemetry.capture("app_started")
        await telemetry.send_once()
        assert len(sent) == 1

    asyncio.run(scenario())


def test_log_allowlist_excludes_job_payload_exception_text_and_unsafe_identity(client):
    import io
    import logging

    from opennotelm.errors import AppError
    from opennotelm.job_events import logger, record_job

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)
    try:
        record_job(
            client.app.state.jobs,
            {
                "type": "PRIVATE_TYPE",
                "entity_id": "PRIVATE_ID",
                "id": "PRIVATE_JOB",
                "payload": {"prompt": "PRIVATE_PROMPT"},
            },
            "failed",
            1234,
            AppError("PRIVATE_CODE", "PRIVATE_MESSAGE"),
        )
    finally:
        logger.removeHandler(handler)
    output = stream.getvalue()
    assert "PRIVATE" not in output
    assert json.loads(output)["error_code"] == "UNKNOWN_ERROR"
