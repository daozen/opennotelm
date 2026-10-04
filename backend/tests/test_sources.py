import time

from epub_factory import make_epub
from fastapi.testclient import TestClient
from opennotelm.main import create_app
from restart_support import restart


def wait_for_job(client, job_id, *, timeout=30):
    # Image encoding/browser export can exceed five seconds on hosted runners.
    # Keep a bounded real-time deadline; callers can still request a short limit.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("completed", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError(f"Job did not finish: {job}")


def import_book(client):
    notebook = client.post("/api/notebooks", json={"title": "Reader"}).json()
    response = client.post(
        f"/api/notebooks/{notebook['id']}/sources/upload",
        files={"file": ("book.epub", make_epub(), "application/epub+zip")},
    )
    assert response.status_code == 202, response.text
    result = response.json()
    assert wait_for_job(client, result["job"]["id"])["status"] == "completed"
    return notebook, result["source"]["id"]


def test_import_reader_selection_duplicate_unlink_and_restart(client, settings, provider):
    notebook, source_id = import_book(client)
    source = client.get(f"/api/sources/{source_id}").json()
    assert source["title"] == "长期思考"
    assert source["status"] == "parsed"
    nodes = client.get(f"/api/sources/{source_id}/nodes").json()
    chapter = next(n for n in nodes if n["type"] == "chapter")
    blocks = client.get(f"/api/sources/{source_id}/blocks?node_id={chapter['id']}").json()
    assert any("耐心意味着" in b["text"] for b in blocks)
    assert not any("长期复利" in b["text"] for b in blocks)
    assert (
        client.patch(
            f"/api/notebooks/{notebook['id']}/sources/{source_id}", json={"enabled": False}
        ).status_code
        == 200
    )
    assert not client.get(f"/api/notebooks/{notebook['id']}/sources").json()[0]["enabled"]
    another = client.post("/api/notebooks", json={"title": "Another notebook"}).json()
    duplicate = client.post(
        f"/api/notebooks/{another['id']}/sources/upload",
        files={"file": ("another.epub", make_epub())},
    ).json()
    assert duplicate["duplicate"]
    assert duplicate["source"]["id"] == source_id
    assert client.get(f"/api/notebooks/{another['id']}/sources").json() == []
    assert client.post(f"/api/notebooks/{another['id']}/sources/{source_id}").status_code == 200
    assert client.delete(f"/api/notebooks/{notebook['id']}/sources/{source_id}").status_code == 204
    assert client.get(f"/api/sources/{source_id}").status_code == 200
    with restart(client, settings, transport=provider[0]) as restarted:
        assert restarted.get(f"/api/sources/{source_id}/nodes").json() == nodes
        assert len(restarted.get(f"/api/notebooks/{another['id']}/sources").json()) == 1
    raw = settings.data_dir / "sources" / source_id / "original.epub"
    assert raw.read_bytes() == make_epub()
    assert client.delete(f"/api/sources/{source_id}").status_code == 204
    assert client.get(f"/api/sources/{source_id}").status_code == 404
    assert not raw.exists()


def test_bad_source_error_retry_and_idempotency(client):
    notebook = client.post("/api/notebooks", json={"title": "Bad"}).json()
    result = client.post(
        f"/api/notebooks/{notebook['id']}/sources/upload",
        files={"file": ("bad.epub", b"not a zip")},
    ).json()
    job = wait_for_job(client, result["job"]["id"])
    assert job["status"] == "failed"
    assert job["error_code"] == "EPUB_PARSE_FAILED"
    retry = client.post(f"/api/jobs/{job['id']}/retry").json()
    assert retry["retry_count"] == 1
    assert wait_for_job(client, retry["id"])["error_code"] == "EPUB_PARSE_FAILED"
    _, source_id = import_book(client)
    original_blocks = client.get(f"/api/sources/{source_id}/blocks").json()
    new_job = client.post(f"/api/sources/{source_id}/retry").json()
    finished = wait_for_job(client, new_job["id"])
    assert finished["result"]["skipped"]
    assert client.get(f"/api/sources/{source_id}/blocks").json() == original_blocks


def test_upload_limits_and_unsupported_type(client):
    notebook = client.post("/api/notebooks", json={"title": "Limits"}).json()
    path = f"/api/notebooks/{notebook['id']}/sources/upload"
    assert (
        client.post(path, files={"file": ("book.epub", b"")}).json()["error"]["code"]
        == "SOURCE_EMPTY"
    )
    assert (
        client.post(path, files={"file": ("book.doc", b"hi")}).json()["error"]["code"]
        == "SOURCE_TYPE_UNSUPPORTED"
    )
    assert (
        client.post(
            "/api/notebooks/missing/sources/upload", files={"file": ("book.epub", b"hi")}
        ).status_code
        == 404
    )
    assert client.get("/api/sources/missing").status_code == 404


def test_scanned_pdf_error_persists_and_retry_is_safe(client):
    from document_factory import make_pdf

    notebook = client.post("/api/notebooks", json={"title": "Scan"}).json()
    result = client.post(
        f"/api/notebooks/{notebook['id']}/sources/upload",
        files={"file": ("scan.pdf", make_pdf(blank=True))},
    ).json()
    job = wait_for_job(client, result["job"]["id"])
    assert job["error_code"] == "PDF_NO_READABLE_CONTENT"
    assert client.get(f"/api/sources/{result['source']['id']}/blocks").json() == []
    client.post(f"/api/jobs/{job['id']}/retry")
    assert wait_for_job(client, job["id"])["error_code"] == "PDF_NO_READABLE_CONTENT"


def test_format_specific_size_limits(settings, provider):
    from dataclasses import replace

    limited = replace(settings, max_text_bytes=4, max_document_bytes=10)
    with TestClient(create_app(limited, transport=provider[0])) as client:
        notebook = client.post("/api/notebooks", json={"title": "Limits"}).json()
        endpoint = f"/api/notebooks/{notebook['id']}/sources/upload"
        for filename, raw in [
            ("large.md", b"12345"),
            ("large.txt", b"12345"),
            ("large.pdf", b"12345678901"),
        ]:
            response = client.post(endpoint, files={"file": (filename, raw)})
            assert response.status_code == 413
            assert response.json()["error"]["code"] == "SOURCE_TOO_LARGE"
        assert client.get(f"/api/notebooks/{notebook['id']}/sources").json() == []
        assert not list((settings.data_dir / "cache").iterdir())


def test_concurrent_attach_and_notebook_delete_has_no_foreign_key_failure(client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    _, source_id = import_book(client)
    for _ in range(5):
        notebook = client.post("/api/notebooks", json={"title": "Concurrent"}).json()["id"]
        barrier = Barrier(2)

        def attach(barrier=barrier, notebook=notebook):
            barrier.wait()
            return client.post(f"/api/notebooks/{notebook}/sources/{source_id}").status_code

        def delete(barrier=barrier, notebook=notebook):
            barrier.wait()
            return client.delete(f"/api/notebooks/{notebook}").status_code

        with ThreadPoolExecutor(max_workers=2) as executor:
            added, removed = executor.submit(attach), executor.submit(delete)
            assert added.result() in (200, 404)
            assert removed.result() == 204
        assert client.post(f"/api/notebooks/{notebook}/sources/{source_id}").status_code == 404
