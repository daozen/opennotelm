from dataclasses import replace

import pytest
from restart_support import restart
from test_models import config

ENDPOINT = "/api/settings/models/image-generation"


def test_default_and_environment_fallback_do_not_write_settings(client, settings, provider):
    assert client.get(ENDPOINT).json() == {
        "concurrency": 2,
        "min_concurrency": 1,
        "max_concurrency": 20,
    }
    with restart(client, replace(settings, image_generation_concurrency=7), provider[0]) as app:
        assert app.get(ENDPOINT).json()["concurrency"] == 7
        with app.app.state.db.connect() as conn:
            assert not conn.execute(
                "SELECT * FROM app_settings WHERE key='image_generation'"
            ).fetchall()
    assert not provider[1]


def test_save_without_provider_calls_preserves_models_preferences_and_secrets(
    client, settings, provider
):
    for role in ("language", "embedding", "image"):
        assert client.post("/api/settings/models/test", json=config(role)).status_code == 200
    client.put("/api/settings/preferences", json={"ui_language": "en", "telemetry_enabled": True})
    models = client.get("/api/settings/models").json()
    preferences = client.get("/api/settings/preferences").json()
    secrets = {p.name: p.read_bytes() for p in (settings.data_dir / "secrets").iterdir()}
    calls = len(provider[1])
    result = client.put(ENDPOINT, json={"concurrency": 20})
    assert result.status_code == 200
    assert result.json()["concurrency"] == 20
    # Persisted UI values take precedence over the environment, even after restart.
    with restart(client, replace(settings, image_generation_concurrency=1), provider[0]) as app:
        assert app.get(ENDPOINT).json() == result.json()
        assert app.get("/api/settings/models").json() == models
        assert app.get("/api/settings/preferences").json() == preferences
        assert app.put(ENDPOINT, json={"concurrency": 1}).json()["concurrency"] == 1
    assert len(provider[1]) == calls
    assert {p.name: p.read_bytes() for p in (settings.data_dir / "secrets").iterdir()} == secrets


@pytest.mark.parametrize(
    "data",
    [{"concurrency": value} for value in (0, -1, 21, 1.5, True, None, "20")]
    + [{}, {"concurrency": 20, "unknown": True}],
)
def test_invalid_value_leaves_saved_limit_unchanged(client, provider, data):
    saved = client.put(ENDPOINT, json={"concurrency": 3}).json()
    assert client.put(ENDPOINT, json=data).status_code == 422
    assert client.get(ENDPOINT).json() == saved
    assert not provider[1]
