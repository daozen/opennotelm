import asyncio
import json

import httpx
import pytest
from opennotelm.errors import AppError
from opennotelm.web_fetch import WebFetcher, normalize_web_url, resolve_public
from opennotelm.web_parser import WebParser
from restart_support import restart
from test_sources import wait_for_job

HTML = b"""<html><head><title>Learning source</title></head><body>
<nav>PRIVATE_NAVIGATION_NOISE</nav><article><h1>Learning patiently</h1>
<p>Patient learning compounds over time. This article explains how experience
accumulates with daily practice and careful reflection.</p>
<h2>Daily practice</h2><p>Start with a small daily routine and record what you learned.
This creates a useful basis for the next day.</p>
<ul><li>Review yesterday</li><li>Practice today</li></ul>
<table><tr><td>Frequency</td><td>Daily</td></tr></table>
<blockquote>Small steps accumulate.</blockquote><img src="/image.png" alt="A learning cycle">
</article><script>PRIVATE_SCRIPT_NOISE</script><footer>PRIVATE_FOOTER_NOISE</footer></body></html>"""


async def public_resolver(host, port):
    return "93.184.216.34"


def fetcher(handler, **kwargs):
    return WebFetcher(resolver=public_resolver, transport=httpx.MockTransport(handler), **kwargs)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://user:password@example.com/",
        "http://localhost/",
        "http://host.local/",
        "https://example.com:8317/",
        "https://example.com/\r\nsecret",
        "https://example.com\\@127.0.0.1/",
        "http://127.0.0.1/",
        "http://192.168.2.125/",
        "http://169.254.169.254/",
        "http://[::1]/",
        "http://[::ffff:93.184.216.34]/",
        "http://[2002:7f00:1::]/",
    ],
)
def test_unsafe_url_rejected(url):
    with pytest.raises(AppError) as error:
        normalize_web_url(url)
    assert error.value.code in ("WEB_URL_INVALID", "WEB_URL_BLOCKED")
    assert url not in error.value.message


def test_normalization_and_dns_pinning_with_original_host_and_tls():
    assert (
        normalize_web_url("HTTPS://EXAMPLE.COM:443/article?q=1#section")
        == "https://example.com/article?q=1"
    )
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200, content=HTML, headers={"content-type": "text/html; charset=utf-8"}
        )

    result = asyncio.run(fetcher(handler).fetch("https://example.com/article"))
    assert result.final_url == "https://example.com/article"
    assert result.data == HTML
    assert seen[0].url.host == "93.184.216.34"
    assert seen[0].headers["host"] == "example.com"
    assert seen[0].extensions["sni_hostname"] == "example.com"


def test_redirect_is_revalidated_and_cannot_access_private_network():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(302, headers={"location": "http://127.0.0.1:8317/v1/models"})

    with pytest.raises(AppError) as error:
        asyncio.run(fetcher(handler).fetch("https://example.com/"))
    assert error.value.code in ("WEB_URL_BLOCKED", "WEB_URL_INVALID")
    assert len(seen) == 1


def test_mixed_dns_answers_are_rejected_before_connection(monkeypatch):
    async def getaddrinfo(*args, **kwargs):
        return [(2, 1, 6, "", ("93.184.216.34", 443)), (2, 1, 6, "", ("10.0.0.1", 443))]

    async def run():
        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
        return await resolve_public("example.com", 443)

    with pytest.raises(AppError) as error:
        asyncio.run(run())
    assert error.value.code == "WEB_URL_BLOCKED"


@pytest.mark.parametrize(
    "status,headers,body,limit,code",
    [
        (403, {}, b"PRIVATE_ERROR", 100, "WEB_ACCESS_DENIED"),
        (404, {}, b"PRIVATE_ERROR", 100, "WEB_HTTP_ERROR"),
        (200, {"content-type": "application/pdf"}, b"%PDF", 100, "WEB_TYPE_UNSUPPORTED"),
        (200, {"content-type": "text/html"}, b"x" * 101, 100, "WEB_TOO_LARGE"),
        (302, {"location": "/loop"}, b"", 100, "WEB_REDIRECT_LIMIT"),
    ],
)
def test_download_errors_are_bounded_and_safe(status, headers, body, limit, code):
    with pytest.raises(AppError) as error:
        asyncio.run(
            fetcher(
                lambda r: httpx.Response(status, headers=headers, content=body), max_bytes=limit
            ).fetch("https://example.com/")
        )
    assert error.value.code == code
    assert "PRIVATE_ERROR" not in error.value.message


def test_total_timeout_includes_dns():
    async def slow(host, port):
        await asyncio.sleep(10)

    with pytest.raises(AppError) as error:
        asyncio.run(WebFetcher(timeout=0.01, resolver=slow).fetch("https://example.com/"))
    assert error.value.code == "WEB_FETCH_TIMEOUT"


def test_article_structure_sanitization_and_stable_provenance(tmp_path):
    path = tmp_path / "original.html"
    path.write_bytes(HTML)
    path.with_name("web.json").write_text(
        json.dumps({"url": "https://example.com/", "final_url": "https://example.com/article"})
    )
    document = WebParser().parse(path, "source", "Web")
    assert document == WebParser().parse(path, "source", "Web")
    assert document.title == "Learning patiently"
    assert [n.title for n in document.nodes[1:]] == ["Learning patiently", "Daily practice"]
    kinds = {b.type for b in document.blocks}
    assert {"paragraph", "heading", "list", "quote", "table", "caption"} <= kinds
    assert "Frequency\tDaily" in [b.text for b in document.blocks]
    assert not any("PRIVATE_" in b.text for b in document.blocks)
    assert all(b.location["url"] == "https://example.com/article" for b in document.blocks)


def test_empty_script_only_page_has_actionable_error(tmp_path):
    path = tmp_path / "original.html"
    path.write_text('<html><title>App</title><script>PRIVATE</script><div id="root"></div></html>')
    path.with_name("web.json").write_text(json.dumps({"final_url": "https://example.com/"}))
    with pytest.raises(AppError) as error:
        WebParser().parse(path, "source", "Web")
    assert error.value.code == "WEB_NO_CONTENT"


def test_batch_partial_failure_duplicate_and_snapshot_restart(client, settings, provider):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=HTML, headers={"content-type": "text/html"})

    client.app.state.sources.web_fetcher = fetcher(handler)
    notebook = client.post("/api/notebooks", json={"title": "Web"}).json()["id"]
    path = f"/api/notebooks/{notebook}/sources/urls"
    response = client.post(
        path,
        json={
            "urls": [
                "https://example.com/article",
                "file:///private",
                "https://example.com/article#anchor",
            ]
        },
    )
    assert response.status_code == 202
    results = response.json()["results"]
    first = results[0]
    assert results[1]["error_code"] == "WEB_URL_INVALID"
    assert results[2]["duplicate"]
    assert results[2]["source"]["id"] == first["source"]["id"]
    assert wait_for_job(client, first["job"]["id"])["status"] == "completed"
    source_id = first["source"]["id"]
    source = client.get(f"/api/sources/{source_id}").json()
    assert source["parser_version"] == "web-v1"
    assert source["metadata"]["url"] == "https://example.com/article"
    assert len(calls) == 1
    blocks = client.get(f"/api/sources/{source_id}/blocks").json()
    assert any("Patient learning" in b["text"] for b in blocks)
    # A second notebook must confirm reuse rather than silently attaching duplicates.
    other = client.post("/api/notebooks", json={"title": "Other"}).json()["id"]
    assert client.post(
        f"/api/notebooks/{other}/sources/urls", json={"urls": ["https://example.com/article"]}
    ).json()["results"][0]["duplicate"]
    assert not client.get(f"/api/notebooks/{other}/sources").json()
    assert client.post(f"/api/notebooks/{other}/sources/{source_id}").status_code == 200
    with restart(client, settings, provider[0]) as restarted:
        assert restarted.get(f"/api/sources/{source_id}/blocks").json() == blocks
        retry = restarted.post(f"/api/sources/{source_id}/retry").json()
        assert wait_for_job(restarted, retry["id"])["result"]["skipped"]
        assert restarted.get(f"/api/sources/{source_id}").json()["metadata"] == source["metadata"]
        assert restarted.delete(f"/api/sources/{source_id}").status_code == 204
        assert not (settings.data_dir / "sources" / source_id).exists()


def test_fetch_failure_retry_and_parse_checkpoint(client):
    state = {"fail": True, "calls": 0}

    def handler(request):
        state["calls"] += 1
        return (
            httpx.Response(403)
            if state["fail"]
            else httpx.Response(200, content=HTML, headers={"content-type": "text/html"})
        )

    client.app.state.sources.web_fetcher = fetcher(handler)
    notebook = client.post("/api/notebooks", json={"title": "Retry"}).json()["id"]
    result = client.post(
        f"/api/notebooks/{notebook}/sources/urls", json={"urls": ["https://example.com/"]}
    ).json()["results"][0]
    job = wait_for_job(client, result["job"]["id"])
    assert job["error_code"] == "WEB_ACCESS_DENIED"
    source_id = result["source"]["id"]
    assert client.get(f"/api/sources/{source_id}").json()["error_code"] == "WEB_ACCESS_DENIED"
    state["fail"] = False
    retry = client.post(f"/api/sources/{source_id}/retry").json()
    assert wait_for_job(client, retry["id"])["status"] == "completed"
    assert state["calls"] == 2
    # Reparse an already fetched source, without fetching the current website again.
    with client.app.state.db.connect() as conn:
        conn.execute("UPDATE sources SET parser_version=NULL WHERE id=?", (source_id,))
    retry = client.post(f"/api/sources/{source_id}/retry").json()
    assert wait_for_job(client, retry["id"])["status"] == "completed"
    assert state["calls"] == 2


def test_url_batch_and_source_limits_leave_no_orphans(client, settings):
    notebook = client.post("/api/notebooks", json={"title": "Limits"}).json()["id"]
    path = f"/api/notebooks/{notebook}/sources/urls"
    assert client.post(path, json={"urls": []}).status_code == 422
    assert client.post(path, json={"urls": ["https://example.com/"] * 51}).status_code == 422
    assert client.post(path, json={"urls": [42]}).status_code == 422
    # Stop the worker so only registration semantics are under test.
    client.portal.call(client.app.state.jobs.stop)
    for i in range(settings.max_sources_per_notebook):
        assert (
            not client.post(path, json={"urls": [f"https://example.com/{i}"]})
            .json()["results"][0]
            .get("error_code")
        )
    assert (
        client.post(path, json={"urls": ["https://example.com/overflow"]}).json()["results"][0][
            "error_code"
        ]
        == "SOURCE_LIMIT"
    )
    assert len(list((settings.data_dir / "sources").iterdir())) == settings.max_sources_per_notebook


def test_fake_ip_dns_fallback_uses_real_public_answers_and_can_be_disabled(monkeypatch):
    async def getaddrinfo(*args, **kwargs):
        return [(2, 1, 6, "", ("198.18.1.5", 443))]

    seen = []

    async def doh(host):
        seen.append(host)
        return ["93.184.216.34"]

    async def run(enabled):
        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
        return await resolve_public("example.com", 443, enabled)

    monkeypatch.setattr("opennotelm.web_fetch.resolve_doh", doh)
    assert asyncio.run(run(True)) == "93.184.216.34"
    assert seen == ["example.com"]
    with pytest.raises(AppError) as error:
        asyncio.run(run(False))
    assert error.value.code == "WEB_URL_BLOCKED"
    assert seen == ["example.com"]


def test_fake_ip_fallback_does_not_relax_private_dns_checks(monkeypatch):
    async def getaddrinfo(*args, **kwargs):
        return [(2, 1, 6, "", ("198.18.1.5", 443))]

    async def doh(host):
        return ["10.0.0.1"]

    async def run():
        monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", getaddrinfo)
        return await resolve_public("example.com", 443)

    monkeypatch.setattr("opennotelm.web_fetch.resolve_doh", doh)
    with pytest.raises(AppError) as error:
        asyncio.run(run())
    assert error.value.code == "WEB_URL_BLOCKED"


def test_third_party_extraction_warnings_do_not_log_original_urls(tmp_path, capsys, caplog):
    path = tmp_path / "original.html"
    path.write_text('<html><title>App</title><div id="root"></div></html>')
    path.with_name("web.json").write_text(
        json.dumps({"final_url": "https://example.com/private?secret=PRIVATE_SECRET"})
    )
    with pytest.raises(AppError):
        WebParser().parse(path, "source", "Web")
    captured = capsys.readouterr()
    assert "PRIVATE_SECRET" not in captured.err + captured.out + caplog.text
