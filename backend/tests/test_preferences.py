"""Locale updates must preserve independent privacy preferences and old databases."""

import json

import pytest
from restart_support import restart


def test_language_and_consent_partial_updates_survive_restart(client, settings, provider):
    assert (
        client.put("/api/settings/preferences", json={"telemetry_enabled": True}).status_code == 200
    )
    with client.app.state.db.connect() as conn:
        queue_before = conn.execute("SELECT * FROM telemetry_queue").fetchall()
    preferences = client.put("/api/settings/preferences", json={"ui_language": "en"}).json()
    assert preferences == {"telemetry_enabled": True, "ui_language": "en"}
    with client.app.state.db.connect() as conn:
        assert [tuple(row) for row in conn.execute("SELECT * FROM telemetry_queue")] == [
            tuple(row) for row in queue_before
        ]
    assert client.put("/api/settings/preferences", json={"telemetry_enabled": False}).json() == {
        "telemetry_enabled": False,
        "ui_language": "en",
    }
    with restart(client, settings, transport=provider[0]) as restarted:
        assert restarted.get("/api/settings/preferences").json() == {
            "telemetry_enabled": False,
            "ui_language": "en",
        }
        assert restarted.put("/api/settings/preferences", json={"ui_language": "zh-CN"}).json() == {
            "telemetry_enabled": False,
            "ui_language": "zh-CN",
        }


def test_old_preferences_without_locale_allow_browser_detection_without_changing_consent(client):
    with client.app.state.db.connect() as conn:
        conn.execute(
            "INSERT INTO app_settings VALUES ('preferences',?)",
            (json.dumps({"telemetry_enabled": True}),),
        )
    assert client.get("/api/settings/preferences").json() == {
        "telemetry_enabled": True,
        "ui_language": None,
    }
    assert client.put("/api/settings/preferences", json={"ui_language": "en"}).json() == {
        "telemetry_enabled": True,
        "ui_language": "en",
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"ui_language": "xx"},
        {"ui_language": "EN"},
        {"ui_language": None},
        {"telemetry_enabled": None},
        {"ui_language": "en", "unknown": True},
    ],
)
def test_invalid_preferences_do_not_change_saved_values(client, changes):
    before = client.get("/api/settings/preferences").json()
    assert client.put("/api/settings/preferences", json=changes).status_code == 422
    assert client.get("/api/settings/preferences").json() == before


@pytest.mark.parametrize(
    "language", ["zh-CN", "en", "zh-TW", "ja", "ko", "es", "fr", "de", "pt-BR", "ru", "ar", "hi"]
)
def test_all_supported_locales_persist_without_changing_consent(
    client, settings, provider, language
):
    assert (
        client.put("/api/settings/preferences", json={"telemetry_enabled": True}).status_code == 200
    )
    assert client.put("/api/settings/preferences", json={"ui_language": language}).json() == {
        "ui_language": language,
        "telemetry_enabled": True,
    }
    with restart(client, settings, transport=provider[0]) as restarted:
        assert restarted.get("/api/settings/preferences").json() == {
            "ui_language": language,
            "telemetry_enabled": True,
        }


def test_unset_language_stays_unset_after_privacy_updates_and_restart(client, settings, provider):
    assert client.get("/api/settings/preferences").json() == {
        "telemetry_enabled": False,
        "ui_language": None,
    }
    for enabled in (True, False):
        result = client.put("/api/settings/preferences", json={"telemetry_enabled": enabled}).json()
        assert result == {"telemetry_enabled": enabled, "ui_language": None}
        with client.app.state.db.connect() as conn:
            stored = json.loads(
                conn.execute(
                    "SELECT value_json FROM app_settings WHERE key='preferences'"
                ).fetchone()[0]
            )
        assert "ui_language" not in stored
    with restart(client, settings, transport=provider[0]) as restarted:
        assert restarted.get("/api/settings/preferences").json()["ui_language"] is None
