import json
import stat

import httpx
from fastapi.testclient import TestClient
from opennotelm.main import create_app
from restart_support import restart


def config(role="language", **overrides):
    return {
        "role": role,
        "base_url": "https://models.example/v1",
        "model_id": "test-model",
        "api_key": "secret-never-leak",
        **overrides,
    }


def test_setup_capabilities_secrets_and_restart(client, settings, provider):
    assert not client.get("/api/settings/models").json()["setup_complete"]
    for role in ("language", "embedding", "image"):
        response = client.post("/api/settings/models/test", json=config(role))
        assert response.status_code == 200, response.text
        assert "secret-never-leak" not in response.text
    data = client.get("/api/settings/models").json()
    assert data["setup_complete"]
    assert data["models"]["embedding"]["capabilities"]["dimensions"] == 2
    with restart(client, settings, transport=provider[0]) as restarted:
        assert restarted.get("/api/settings/models").json() == data
        response = restarted.post(
            "/api/settings/models/test", json=config(api_key="", use_saved_key=True)
        )
        assert response.status_code == 200
    for request in provider[1]:
        assert request.headers.get("authorization") == "Bearer secret-never-leak"
    for path in settings.data_dir.rglob("*"):
        if path.is_file():
            assert b"secret-never-leak" not in path.read_bytes()
    master = settings.data_dir / "secrets/master.key"
    assert stat.S_IMODE(master.stat().st_mode) == 0o600


def test_provider_failures_do_not_save_or_leak(settings):
    def failure(request):
        return httpx.Response(401, json={"secret": "secret-never-leak", "text": "private content"})

    with TestClient(create_app(settings, transport=httpx.MockTransport(failure))) as client:
        response = client.post("/api/settings/models/test", json=config())
        assert response.status_code == 502
        assert response.json()["error"]["code"] == "MODEL_CONNECTION_FAILED"
        assert "secret-never-leak" not in response.text
        assert "private content" not in response.text
        assert client.get("/api/settings/models").json()["models"] == {}
        assert list((settings.data_dir / "secrets").iterdir()) == [
            settings.data_dir / "secrets/master.key"
        ]


def test_json_fallback_and_one_repair(settings):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        body = json.loads(request.content)
        if "response_format" in body:
            return httpx.Response(400)
        text = '{"ok":true}' if count == 4 else "not JSON"
        return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})

    with TestClient(create_app(settings, transport=httpx.MockTransport(handler))) as client:
        response = client.post("/api/settings/models/test", json=config())
        assert response.status_code == 200
        assert response.json()["capabilities"]["structured_output"] == "prompt_json"
        assert count == 4


def test_invalid_json_fails_after_one_repair(settings):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": "not JSON"}}]})

    with TestClient(create_app(settings, transport=httpx.MockTransport(handler))) as client:
        response = client.post("/api/settings/models/test", json=config())
        assert response.json()["error"]["code"] == "MODEL_STRUCTURED_OUTPUT_INVALID"
        assert count == 3


def test_invalid_embedding_rejected(settings):
    with TestClient(
        create_app(
            settings,
            transport=httpx.MockTransport(
                lambda r: httpx.Response(200, json={"data": [{"index": 0, "embedding": [0, 0]}]})
            ),
        )
    ) as client:
        response = client.post("/api/settings/models/test", json=config("embedding"))
        assert response.json()["error"]["code"] == "EMBEDDING_OUTPUT_INVALID"


def test_discovery_optional(client, settings):
    response = client.post("/api/settings/models/discover", json=config())
    assert response.json()["models"] == ["test-model"]
    with restart(
        client, settings, transport=httpx.MockTransport(lambda r: httpx.Response(404))
    ) as restarted:
        response = restarted.post("/api/settings/models/discover", json=config())
        assert response.status_code == 200
        assert response.json()["custom_model_allowed"]


def test_validation_never_echoes_secrets(client):
    response = client.post("/api/settings/models/test", json=config(base_url="javascript:bad"))
    assert response.status_code == 422
    assert "secret-never-leak" not in response.text
    response = client.post(
        "/api/settings/models/test", json=config(base_url="https://user:key@x/v1")
    )
    assert response.status_code == 422
    assert "user:key" not in response.text


def test_environment_key_and_same_endpoint(client, provider, monkeypatch):
    monkeypatch.setenv("OPENNOTELM_LANGUAGE_API_KEY", "from-environment")
    assert client.post("/api/settings/models/test", json=config(api_key="")).status_code == 200
    with client.app.state.db.connect() as conn:
        assert (
            conn.execute("SELECT api_key_secret_ref FROM model_configs")
            .fetchone()[0]
            .startswith("env:")
        )
    response = client.post(
        "/api/settings/models/test", json=config("embedding", api_key="", api_key_source="language")
    )
    assert response.status_code == 200
    assert provider[1][-1].headers["authorization"] == "Bearer from-environment"


def test_preferences_default_off_and_persistent(client, settings, provider):
    assert client.get("/api/settings/preferences").json() == {
        "telemetry_enabled": False,
        "ui_language": None,
    }
    assert (
        client.put("/api/settings/preferences", json={"telemetry_enabled": True}).status_code == 200
    )
    with restart(client, settings, transport=provider[0]) as restarted:
        assert restarted.get("/api/settings/preferences").json()["telemetry_enabled"]
