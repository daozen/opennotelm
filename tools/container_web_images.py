"""Synthetic web-image acceptance inside the image, always using a fresh /tmp data root.

Feed this file to the acceptance app's Python over stdin. All page/image/model HTTP
uses MockTransport; no live application data, credentials or external network calls.
"""

import hashlib
import json
import tempfile
import time
from io import BytesIO
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from opennotelm.config import Settings
from opennotelm.main import create_app
from opennotelm.web_fetch import WebFetcher
from opennotelm.web_images import decode_web_image
from PIL import Image

output = BytesIO()
Image.new("RGB", (160, 100), "green").save(output, format="PNG")
image_bytes = output.getvalue() + b"SYNTHETIC_ORIGINAL_BYTES"
for format in ("PNG", "JPEG", "WEBP", "GIF", "AVIF"):
    output = BytesIO()
    Image.new("RGB", (80, 80), "green").save(output, format=format)
    assert decode_web_image(output.getvalue())[0].startswith(b"\x89PNG")

html = b"""<html><title>Synthetic article</title><article><h1>Learning diagrams</h1>
<p>Patient learning compounds with daily practice. This synthetic article explains how
careful reading and reflection support a useful daily routine and accumulating experience.</p>
<img src="/chart.png" alt="Synthetic chart"><img src="http://127.0.0.1/private.png">
</article></html>"""
requests = {"article": 0, "image": 0, "recognition": 0}


def provider(request):
    payload = json.loads(request.content)
    if request.url.path.endswith("/embeddings"):
        data = [{"index": i, "embedding": [0.2, 0.8]} for i in range(len(payload["input"]))]
        return httpx.Response(200, json={"data": data})
    text = '{"ok":true}'
    if isinstance(payload["messages"][-1]["content"], list):
        requests["recognition"] += 1
        text = json.dumps(
            {"paragraphs": ["SYNTHETIC CHART 27"], "description": "", "uncertain": False}
        )
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


async def resolve(host, port):
    return "93.184.216.34"


def article(request):
    requests["article"] += 1
    return httpx.Response(200, content=html, headers={"content-type": "text/html"})


def image(request):
    requests["image"] += 1
    return httpx.Response(200, content=image_bytes, headers={"content-type": "image/png"})


def attach_fetchers(client):
    client.app.state.sources.web_fetcher = WebFetcher(
        resolver=resolve, transport=httpx.MockTransport(article)
    )
    client.app.state.sources.web_images.fetcher = WebFetcher(
        image=True, resolver=resolve, transport=httpx.MockTransport(image)
    )


def finish(client, identity):
    for _ in range(200):
        job = client.get("/api/jobs/" + identity).json()
        if job["status"] not in ("queued", "running"):
            assert job["status"] == "completed", job.get("error_code")
            return job
        time.sleep(0.025)
    raise AssertionError("Synthetic image job did not finish")


settings = Settings(
    data_dir=Path(tempfile.mkdtemp(prefix="web-images-acceptance-")) / "data",
    allowed_hosts=("testserver",),
)
transport = httpx.MockTransport(provider)
with TestClient(create_app(settings, transport=transport)) as client:
    attach_fetchers(client)
    for role in ("language", "embedding"):
        response = client.post(
            "/api/settings/models/test",
            json={
                "role": role,
                "base_url": "https://provider.example/v1",
                "model_id": "synthetic-model",
                "api_key": "test-only-key",
                "max_context_tokens": 16000,
            },
        )
        assert response.status_code == 200
    notebook = client.post("/api/notebooks", json={"title": "Synthetic web images"}).json()["id"]
    route = f"/api/notebooks/{notebook}/sources/urls"
    first = client.post(
        route, json={"urls": ["https://example.com/article"], "save_images": False}
    ).json()["results"][0]
    source = first["source"]["id"]
    finish(client, first["job"]["id"])
    assert requests["image"] == requests["recognition"] == 0
    body = client.get(f"/api/sources/{source}/blocks").json()
    assert client.post(
        route, json={"urls": ["https://example.com/article"], "save_images": True}
    ).json()["results"][0]["duplicate"]
    finish(client, client.get(f"/api/sources/{source}").json()["job"]["id"])
    record = client.get(f"/api/sources/{source}").json()
    assert record["status"] == "indexed" and record["metadata"]["image_failures"] == 1
    blocks = client.get(f"/api/sources/{source}/blocks").json()
    assert [
        {k: v for k, v in b.items() if k != "ordinal"} for b in blocks if b["type"] != "image"
    ] == [{k: v for k, v in b.items() if k != "ordinal"} for b in body]
    ready = next(b for b in blocks if b["metadata"].get("recognition_status") == "ready")
    original_url = ready["metadata"]["original_image_url"]
    assert client.get(original_url).content == image_bytes
    assert "SYNTHETIC CHART 27" in ready["text"]

with TestClient(create_app(settings, transport=transport)) as client:
    attach_fetchers(client)
    assert client.get(f"/api/sources/{source}/blocks").json() == blocks
    assert client.get(original_url).content == image_bytes
    retry = client.post(f"/api/sources/{source}/recognize-images").json()
    finish(client, retry["id"])
    assert requests == {"article": 1, "image": 1, "recognition": 1}
    assert client.get(f"/api/sources/{source}/blocks").json() == blocks
    assert client.delete(f"/api/sources/{source}").status_code == 204
    assert client.get(original_url).status_code == 404

print(
    json.dumps(
        {
            "web_image_acceptance": "passed",
            "formats": 5,
            "text_only_no_image_calls": True,
            "body_preserved": True,
            "original_sha256": hashlib.sha256(image_bytes).hexdigest(),
            "restart_retry_reused": True,
            "source_deletion": True,
        }
    )
)
