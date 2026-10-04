import asyncio
import json
import threading
from dataclasses import replace
from io import BytesIO

import httpx
import pytest
from opennotelm.documents import Document, DocumentImage, DocumentNode
from opennotelm.errors import AppError
from opennotelm.source_visuals import SourceVisualService
from opennotelm.web_fetch import WebFetcher
from opennotelm.web_images import WebImageService, decode_web_image
from opennotelm.web_parser import WebParser
from PIL import Image
from restart_support import restart
from test_source_vision import vision_client as shared_vision_client
from test_sources import wait_for_job
from test_web_sources import HTML, fetcher, public_resolver
from vision_factory import scan_image

vision_client = shared_vision_client


def test_image_recognition_starts_before_last_web_download_finishes(vision_client):
    client, _, _, _ = vision_client
    recognized = threading.Event()
    original = client.app.state.sources.vision.recognize

    async def recognize(*args):
        value = await original(*args)
        recognized.set()
        return value

    client.app.state.sources.vision.recognize = recognize

    async def download(request):
        if request.url.path.endswith("slow.png"):
            deadline = asyncio.get_running_loop().time() + 2
            while not recognized.is_set() and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.01)
            assert recognized.is_set(), "Recognition must overlap the remaining download"
        return httpx.Response(200, content=scan_image(), headers={"content-type": "image/png"})

    configure_fetchers(client, '<img src="/fast.png"><img src="/slow.png">', download)
    _, source = import_article(client)
    assert finish_images(client, source)["status"] == "completed"
    images = client.get(f"/api/sources/{source}").json()["metadata"]["images"]
    assert len(images) == 2 and all(image["status"] == "ready" for image in images)


def html_with_images(tags):
    return HTML.replace(b'<img src="/image.png" alt="A learning cycle">', tags.encode())


def image_fetcher(handler, **kwargs):
    return WebFetcher(
        image=True, resolver=public_resolver, transport=httpx.MockTransport(handler), **kwargs
    )


def configure_fetchers(client, tags, handler):
    body_calls = []

    def body(request):
        body_calls.append(request)
        return httpx.Response(
            200, content=html_with_images(tags), headers={"content-type": "text/html"}
        )

    client.app.state.sources.web_fetcher = fetcher(body)
    client.app.state.sources.web_images.fetcher = image_fetcher(handler)
    return body_calls


def import_article(client, save=True):
    notebook = client.post("/api/notebooks", json={"title": "Web images"}).json()["id"]
    result = client.post(
        f"/api/notebooks/{notebook}/sources/urls",
        json={"urls": ["https://example.com/article"], "save_images": save},
    ).json()["results"][0]
    assert wait_for_job(client, result["job"]["id"])["status"] == "completed"
    return notebook, result["source"]["id"]


def finish_images(client, source):
    job = client.get(f"/api/sources/{source}").json()["job"]
    assert job["type"] == "source_web_images"
    return wait_for_job(client, job["id"])


def test_image_discovery_retains_article_facts_and_handles_srcset_lazy_cdn(tmp_path):
    path = tmp_path / "original.html"
    path.write_bytes(
        html_with_images(
            '<img src="/small.jpg" srcset="/small.jpg 400w, '
            '//cdn.example.com/full?id=1 1600w" alt="Cycle">'
            '<p><img data-src="lazy.png" alt="Details"></p>'
            '<img src="/tracker.png" width="1" height="1">'
        )
    )
    path.with_name("web.json").write_text(
        json.dumps({"final_url": "https://example.com/book/chapter"})
    )
    plain = WebParser().parse(path, "source", "Article")
    enhanced = WebParser().parse(path, "source", "Article", True)
    assert enhanced.blocks == plain.blocks
    assert enhanced.nodes == plain.nodes
    assert not plain.images
    assert [image.location["source_image_url"] for image in enhanced.images] == [
        "https://cdn.example.com/full?id=1",
        "https://example.com/book/lazy.png",
    ]
    assert all(image.node_id == enhanced.nodes[-1].id for image in enhanced.images)
    assert enhanced == WebParser().parse(path, "source", "Article", True)
    limited = WebParser(1).parse(path, "source", "Article", True)
    assert len(limited.images) == 1 and limited.metadata["web_image_limit_skipped"] == 1


@pytest.mark.parametrize(
    "content_type,data,code",
    [
        ("image/svg+xml", b'<svg onload="alert(1)"/>', "WEB_IMAGE_TYPE_UNSUPPORTED"),
        ("text/html", b"<script>PRIVATE</script>", "WEB_IMAGE_TYPE_UNSUPPORTED"),
        ("image/png", b"x" * 101, "WEB_IMAGE_TOO_LARGE"),
    ],
)
def test_image_http_limits_and_active_content(content_type, data, code):
    with pytest.raises(AppError) as error:
        asyncio.run(
            image_fetcher(
                lambda r: httpx.Response(200, content=data, headers={"content-type": content_type}),
                max_bytes=100,
            ).fetch("https://cdn.example.com/image")
        )
    assert error.value.code == code


def test_image_redirects_and_dns_rebinding_are_rechecked():
    seen = []

    async def resolver(host, port):
        seen.append(host)
        return "93.184.216.34" if host == "example.com" else "10.0.0.1"

    downloader = WebFetcher(
        image=True,
        resolver=resolver,
        transport=httpx.MockTransport(
            lambda r: httpx.Response(302, headers={"location": "https://cdn.example.com/image.png"})
        ),
    )
    with pytest.raises(AppError) as error:
        asyncio.run(downloader.fetch("https://example.com/image.png"))
    assert error.value.code == "WEB_URL_BLOCKED"
    assert seen == ["example.com", "cdn.example.com"]


@pytest.mark.parametrize("format", ["PNG", "JPEG", "WEBP", "GIF", "AVIF"])
def test_supported_raster_formats_have_safe_png_previews(format):
    output = BytesIO()
    Image.new("RGB", (120, 80), "green").save(output, format=format)
    preview, size, suffix = decode_web_image(output.getvalue())
    assert preview.startswith(b"\x89PNG") and size == (120, 80)
    assert suffix in ("png", "jpg", "webp", "gif", "avif")


def test_optional_images_original_bytes_recognition_citations_deck_and_restart(
    vision_client, settings
):
    client, calls, _, transport = vision_client
    original = scan_image() + b"ORIGINAL_TRAILING_BYTES"
    image_calls = []

    def image(request):
        image_calls.append(request)
        return httpx.Response(200, content=original, headers={"content-type": "image/png"})

    body_calls = configure_fetchers(
        client, '<img src="/image.png" alt="Cycle"><img src="/image.png" alt="Repeated">', image
    )
    notebook, source = import_article(client, False)
    before = client.get(f"/api/sources/{source}/blocks").json()
    assert not image_calls
    assert not client.get(f"/api/sources/{source}").json()["metadata"].get("images")
    paragraph = next(block for block in before if block["type"] == "paragraph")
    evidence = [
        {
            "id": "E1",
            "text": paragraph["text"],
            "spans": [
                {
                    "source_id": source,
                    "block_id": paragraph["id"],
                    "start_offset": 0,
                    "end_offset": len(paragraph["text"]),
                }
            ],
        }
    ]
    with client.app.state.db.connect() as conn:
        citations = client.app.state.citations.persist(
            conn, notebook, "message", "test", "[[E1]]", evidence
        )
    # Reimporting with images supplements the immutable snapshot, including old text-only sources.
    duplicate = client.post(
        f"/api/notebooks/{notebook}/sources/urls",
        json={"urls": ["https://example.com/article"], "save_images": True},
    ).json()["results"][0]
    assert duplicate["duplicate"] and duplicate["source"]["id"] == source
    assert finish_images(client, source)["status"] == "completed"
    source_record = client.get(f"/api/sources/{source}").json()
    assert source_record["status"] == "indexed"
    assert source_record["metadata"]["image_failures"] == 0
    blocks = client.get(f"/api/sources/{source}/blocks").json()
    assert [
        {k: v for k, v in b.items() if k != "ordinal"} for b in blocks if b["type"] != "image"
    ] == [{k: v for k, v in b.items() if k != "ordinal"} for b in before]
    images = [b for b in blocks if b["type"] == "image"]
    assert len(images) == 2 and all("SCAN 27" in b["text"] for b in images)
    assert len(image_calls) == 1 and len(body_calls) == 1
    vision_calls = [
        c for c in calls if isinstance(c.get("messages", [{}])[-1].get("content"), list)
    ]
    assert len(vision_calls) == 1
    response = client.get(images[0]["metadata"]["original_image_url"])
    assert response.content == original
    assert response.headers["content-type"] == "application/octet-stream"
    assert "attachment" in response.headers["content-disposition"]
    assert client.get(images[0]["metadata"]["image_url"]).content != original
    visuals = SourceVisualService(client.app.state.sources).collect(images)
    assert len(visuals) == 2 and all(v.path.is_file() for v in visuals.values())
    assert client.get("/api/citations/" + citations["E1"]).json()["available"]
    cached_calls = len(calls)
    retry = client.post(f"/api/sources/{source}/recognize-images").json()
    assert retry["status"] == "completed"  # Already-complete import is idempotent.
    assert len(calls) == cached_calls and len(image_calls) == 1
    with restart(client, settings, transport) as restarted:
        assert restarted.get(images[0]["metadata"]["original_image_url"]).content == original
        assert restarted.get(f"/api/sources/{source}/blocks").json() == blocks
        assert restarted.delete(f"/api/sources/{source}").status_code == 204
        assert restarted.get(images[0]["metadata"]["original_image_url"]).status_code == 404
        with restarted.app.state.db.connect() as conn:
            assert not conn.execute("SELECT 1 FROM jobs WHERE source_id=?", (source,)).fetchone()


def test_partial_download_and_recognition_failure_retry_preserves_successes(vision_client):
    client, calls, state, _ = vision_client
    failures = {"download": True}
    image_calls = []

    def image(request):
        image_calls.append(request.url.path)
        if request.url.path == "/bad.png" and failures["download"]:
            return httpx.Response(403)
        return httpx.Response(200, content=scan_image(), headers={"content-type": "image/png"})

    body_calls = configure_fetchers(
        client,
        '<img src="/good.png"><img src="/bad.png"><img src="http://127.0.0.1/private.png">',
        image,
    )
    state["fail"] = True
    _, source = import_article(client)
    assert finish_images(client, source)["status"] == "completed"
    record = client.get(f"/api/sources/{source}").json()
    assert record["status"] == "indexed" and record["metadata"]["image_failures"] == 3
    image_blocks = [
        b for b in client.get(f"/api/sources/{source}/blocks").json() if b["type"] == "image"
    ]
    assert [b["location"]["image_index"] for b in image_blocks] == sorted(
        b["location"]["image_index"] for b in image_blocks
    )
    good = record["metadata"]["images"][0]
    assert client.get(good["image_url"]).status_code == 200
    assert client.get(good["original_image_url"]).content == scan_image()
    state["fail"] = failures["download"] = False
    job = client.post(f"/api/sources/{source}/recognize-images").json()
    assert wait_for_job(client, job["id"])["status"] == "completed"
    record = client.get(f"/api/sources/{source}").json()
    assert record["metadata"]["image_failures"] == 1
    assert record["metadata"]["web_images_status"] == "partial"
    assert image_calls.count("/good.png") == 1 and image_calls.count("/bad.png") == 2
    assert len(body_calls) == 1
    ready = [
        b
        for b in client.get(f"/api/sources/{source}/blocks").json()
        if b["metadata"].get("recognition_status") == "ready"
    ]
    assert len(ready) == 2
    before_calls = len(calls)
    # Corrupt/missing checkpoints recover published originals without refetching them.
    directory = client.app.state.sources.settings.data_dir / "sources" / source / "media"
    (directory / "web-images.json").write_text("invalid JSON")
    retry = client.post(f"/api/sources/{source}/recognize-images").json()
    assert wait_for_job(client, retry["id"])["status"] == "completed"
    assert len(calls) == before_calls
    assert image_calls.count("/good.png") == 1 and image_calls.count("/bad.png") == 2
    assert [
        b
        for b in client.get(f"/api/sources/{source}/blocks").json()
        if b["metadata"].get("recognition_status") == "ready"
    ] == ready


def test_body_is_readable_and_indexed_while_image_recognition_runs(vision_client, monkeypatch):
    client, _, _, _ = vision_client
    configure_fetchers(
        client,
        '<img src="/image.png">',
        lambda r: httpx.Response(200, content=scan_image(), headers={"content-type": "image/png"}),
    )
    recognition = client.app.state.sources.vision.recognize
    state = {"waiting": True, "started": False}

    async def blocked(*args):
        state["started"] = True
        while state["waiting"]:
            await asyncio.sleep(0.01)
        return await recognition(*args)

    monkeypatch.setattr(client.app.state.sources.vision, "recognize", blocked)
    try:
        _, source = import_article(client)
        import time

        for _ in range(100):
            if state["started"]:
                break
            time.sleep(0.01)
        assert state["started"]
        record = client.get(f"/api/sources/{source}").json()
        assert record["status"] == "indexed" and record["job"]["status"] == "running"
        assert record["job"]["type"] == "source_web_images"
        assert client.delete(f"/api/sources/{source}").json()["error"]["code"] == "SOURCE_BUSY"
        assert any(
            "Patient learning" in str(block)
            for block in client.get(f"/api/sources/{source}/reading").json()
        )
    finally:
        state["waiting"] = False
    assert finish_images(client, source)["status"] == "completed"


def test_download_pool_dedup_budget_and_timeout_are_bounded(settings):
    configured = replace(
        settings,
        web_image_download_concurrency=2,
        max_web_images_bytes=len(scan_image()) + 1,
        web_images_timeout=0.15,
    )
    configured.prepare()
    directory = configured.data_dir / "sources" / "source"
    directory.mkdir()
    images = [
        DocumentImage(
            str(i), "root", i + 0.5, {"source_image_url": f"https://example.com/{i}.png", "alt": ""}
        )
        for i in range(4)
    ]
    document = Document(
        "Web", [DocumentNode("root", None, "document", "Web", 0, 0)], [], images=images
    )
    active = peak = 0

    async def handler(request):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(10 if request.url.path == "/3.png" else 0.01)
            return httpx.Response(200, content=scan_image(), headers={"content-type": "image/png"})
        finally:
            active -= 1

    service = WebImageService(configured)
    service.fetcher = image_fetcher(handler)

    class Context:
        def progress(self, *args):
            pass

    result = asyncio.run(service.download("source", document, Context()))
    assert peak == 2 and active == 0
    assert [i["status"] for i in result] == ["saved", "saved", "saved", "failed"]
    assert result[-1]["error_code"] == "WEB_FETCH_TIMEOUT"
    assert len(list((directory / "media").glob("original-*"))) == 1
    assert document.metadata["web_image_bytes"] == len(scan_image())


def test_unexpected_image_processing_failure_leaves_article_usable(client, monkeypatch):
    configure_fetchers(
        client,
        '<img src="/image.png">',
        lambda r: httpx.Response(200, content=scan_image(), headers={"content-type": "image/png"}),
    )

    async def fail(*args):
        raise RuntimeError("PRIVATE_DETAILS")

    monkeypatch.setattr(client.app.state.sources.web_images, "download", fail)
    _, source = import_article(client)
    job = finish_images(client, source)
    assert job["status"] == "failed" and "PRIVATE_DETAILS" not in job["error_message"]
    record = client.get(f"/api/sources/{source}").json()
    assert record["status"] == "parsed" and record["parser_version"] == "web-v1"
    assert record["metadata"]["web_images_status"] == "failed"
    assert client.get(f"/api/sources/{source}/reading").json()
