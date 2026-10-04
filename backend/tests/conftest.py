import sys

import httpx
import pytest
from fastapi.testclient import TestClient
from image_factory import image_response
from opennotelm.browser_environment import check_local_test_ports
from opennotelm.config import Settings
from opennotelm.main import create_app


def pytest_collection_finish(session):
    if sys.platform != "darwin" or not any(
        item.get_closest_marker("browser") for item in session.items
    ):
        return
    try:
        check_local_test_ports()
    except OSError as exc:
        raise pytest.UsageError(
            "Browser tests require permitted macOS process/local-server access. "
            "Run this command from a terminal or an approved test environment. "
            "No browser was started. Use -m 'not browser' for isolated unit tests."
        ) from exc


@pytest.fixture
def provider():
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "test-model"}]})
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.2, 0.8]}]})
        if request.url.path.endswith("/images/generations"):
            return httpx.Response(200, json=image_response())
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok":true}'}}]})

    return httpx.MockTransport(handler), calls


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "data", frontend_dir=tmp_path / "dist")


@pytest.fixture
def client(settings, provider):
    with TestClient(create_app(settings, transport=provider[0])) as client:
        yield client
