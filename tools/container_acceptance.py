"""Verify the isolated Compose stack, including recreation and encrypted secrets.

Run after the browser container suite. Only the private fixture provider is allowed;
this script refuses to configure real models or operate on the user's application.
"""

import argparse
import hashlib
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:4303"
PROVIDER = "http://127.0.0.1:4301/v1"
FIXTURES = Path(__file__).resolve().parents[1] / "frontend/e2e/fixtures"
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
FILE_CHECK = """
import hashlib, json, os, sqlite3
from pathlib import Path
root = Path('/app/data')
with sqlite3.connect(root / 'app.db') as db:
    active = db.execute("SELECT count(*) FROM jobs WHERE status IN ('queued','running')")
    assert active.fetchone()[0] == 0
assert os.getuid() == 10001
files = {}
for folder in ('sources', 'assets', 'renders', 'exports', 'podcasts', 'mindmaps', 'secrets'):
    for path in sorted((root / folder).rglob('*')):
        if path.is_file():
            files[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
print(json.dumps(files, sort_keys=True))
"""


def container_files():
    assert os.getenv("OPENNOTELM_DATA_DIR"), "Set the isolated acceptance data directory"
    command = [
        "docker",
        "compose",
        "-p",
        "opennotelm-acceptance",
        "-f",
        "compose.yaml",
        "-f",
        "compose.acceptance.yaml",
        "exec",
        "-T",
        "app",
        "/app/.venv/bin/python",
        "-c",
        FILE_CHECK,
    ]
    result = subprocess.run(
        command, cwd=FIXTURES.parents[2], capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)


def request(path, data=None, *, body=None, content_type=None, method=None):
    if data is not None:
        body = json.dumps(data).encode()
        content_type = "application/json"
    headers = {"Content-Type": content_type} if content_type else {}
    with OPENER.open(
        urllib.request.Request(BASE + "/api" + path, data=body, headers=headers, method=method),
        timeout=30,
    ) as response:
        payload = response.read()
        return (
            json.loads(payload)
            if response.headers.get_content_type() == "application/json"
            else payload
        )


def wait_job(job):
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        value = request("/jobs/" + job["id"])
        if value["status"] == "completed":
            return value
        if value["status"] in {"failed", "cancelled"}:
            raise AssertionError(f"Job did not complete: {value['error_code']}")
        time.sleep(0.5)
    raise AssertionError("Container job exceeded five minutes")


def upload(notebook_id, filename):
    boundary = "OpenNoteLMContainerAcceptanceBoundary"
    payload = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'
        ).encode()
        + (FIXTURES / filename).read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    result = request(
        f"/notebooks/{notebook_id}/sources/upload",
        body=payload,
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    if result.get("duplicate"):
        source_id = result["source"]["id"]
        request(f"/notebooks/{notebook_id}/sources/{source_id}", {})
    else:
        wait_job(result["job"])
    source_id = result["source"]["id"]
    assert request(f"/sources/{source_id}")["status"] == "indexed"
    assert request(f"/sources/{source_id}/nodes")
    assert request(f"/sources/{source_id}/reading")
    return source_id


def snapshots(
    notebook_id,
    source_ids,
    knowledge_id,
    deck_id,
    batch_deck_ids=(),
    stopped_id=None,
    podcast_id=None,
    mindmap_id=None,
):
    paths = [
        "/settings/models",
        "/settings/models/image-generation",
        "/settings/preferences",
        f"/notebooks/{notebook_id}",
        f"/notebooks/{notebook_id}/sources",
        f"/notebooks/{notebook_id}/chat",
        f"/knowledge/{knowledge_id}",
        f"/decks/{deck_id}",
        f"/notebooks/{notebook_id}/decks",
    ]
    paths.extend(f"/decks/{identity}" for identity in batch_deck_ids)
    if stopped_id:
        paused = request(f"/decks/{stopped_id}")
        assert paused["status"] == "paused" and paused["job"]["status"] == "cancelled"
        paths.extend([f"/decks/{stopped_id}", f"/jobs/{paused['job']['id']}"])
    for source_id in source_ids:
        paths.append(f"/sources/{source_id}")
        paths.extend(f"/sources/{source_id}/{suffix}" for suffix in ("nodes", "blocks", "reading"))
    values = {path: request(path) for path in paths}
    citations = set(values[f"/knowledge/{knowledge_id}"]["citations"].values())
    for message in values[f"/notebooks/{notebook_id}/chat"]["messages"]:
        citations.update(message.get("citations", {}).values())
    decks = [values[f"/decks/{identity}"] for identity in [deck_id, *batch_deck_ids]]
    for deck in decks:
        for slide in deck["slides"]:
            citations.update(slide["citations"].values())
    for citation_id in sorted(citations):
        path = f"/citations/{citation_id}"
        value = request(path)
        assert value["available"]
        values[path] = value
    downloads = {}
    if podcast_id:
        episode = request(f"/podcasts/{podcast_id}")
        assert episode["status"] == "completed" and episode["download_available"]
        values[f"/podcasts/{podcast_id}"] = episode
        downloads["podcast:" + podcast_id] = f"/api/podcasts/{podcast_id}/audio"
        for segment in episode["segments"]:
            for citation_id in segment["citations"].values():
                values[f"/citations/{citation_id}"] = request(f"/citations/{citation_id}")
    if mindmap_id:
        mindmap = request(f"/mindmaps/{mindmap_id}")
        assert mindmap["status"] == "completed" and mindmap["download_available"]
        assert len(mindmap["tree"]["nodes"]) >= 3 and mindmap["citations"]
        values[f"/mindmaps/{mindmap_id}"] = mindmap
        values[f"/mindmaps/{mindmap_id}/sources"] = request(f"/mindmaps/{mindmap_id}/sources")
        for citation_id in mindmap["citations"].values():
            citation = request(f"/citations/{citation_id}")
            assert citation["available"]
            values[f"/citations/{citation_id}"] = citation
        downloads["mindmap-markdown:" + mindmap_id] = f"/api/mindmaps/{mindmap_id}/download"
        downloads["mindmap-json:" + mindmap_id] = f"/api/mindmaps/{mindmap_id}/download?format=json"
    for deck in decks:
        downloads["pdf:" + deck["id"]] = deck["pdf_export"]["download_url"]
        for slide in deck["slides"]:
            downloads[slide["id"]] = slide["render"]["image_url"]
    for source_id in source_ids:
        for image in values[f"/sources/{source_id}"]["metadata"].get("images", []):
            if image.get("image_url"):
                downloads["source-image:" + image["id"]] = image["image_url"]
    hashes = {}
    for key, url in downloads.items():
        payload = request(url.removeprefix("/api"))
        raw = json.dumps(payload, sort_keys=True).encode() if isinstance(payload, dict) else payload
        hashes[key] = hashlib.sha256(raw).hexdigest()
    return values, downloads, hashes


def prepare(state_path):
    data_dir = Path(os.environ["OPENNOTELM_DATA_DIR"]).resolve()
    assert data_dir.name.startswith(".docker-acceptance-data"), "Use isolated test data"
    configs = request("/settings/models")
    assert configs["setup_complete"], "Run the browser container suite first"
    assert all(c["base_url"] == PROVIDER for c in configs["models"].values()), (
        "Refusing an instance configured with real providers"
    )
    assert (
        request("/settings/models/image-generation", {"concurrency": 20}, method="PUT")[
            "concurrency"
        ]
        == 20
    )
    for role in ("language", "embedding", "image"):
        request(
            "/settings/models/test",
            dict(role=role, base_url=PROVIDER, api_key="test-only-key", model_id="test-model"),
        )
    notebook = request("/notebooks", {"title": "容器重建持久化验收"})
    notebook_id = notebook["id"]
    source_ids = [
        upload(notebook_id, filename)
        for filename in (
            "book.epub",
            "text.pdf",
            "glyphs.pdf",
            "notes.md",
            "notes.txt",
            "illustrated.docx",
            "scan-with-toc.pdf",
            "hierarchy.pdf",
        )
    ]
    scope = {"kind": "source", "source_id": source_ids[0]}
    chat = request(
        f"/notebooks/{notebook_id}/chat",
        {"question": "长期复利的优势是什么？", "scope": scope},
    )
    wait_job(chat)
    messages = request(f"/notebooks/{notebook_id}/chat")["messages"]
    assert messages[-1]["citations"]
    assert "长期复利最大的优势来自时间跨度" in messages[-1]["content"]
    knowledge = request(f"/notebooks/{notebook_id}/knowledge", {"scope": scope})
    wait_job(knowledge["job"])
    knowledge_id = knowledge["page"]["id"]
    assert request(f"/knowledge/{knowledge_id}")["citations"]
    deck = request(
        f"/notebooks/{notebook_id}/decks",
        {"slide_count": 15, "scope": {"kind": "source", "source_id": source_ids[3]}},
    )
    wait_job(deck["job"])
    before = request(f"/decks/{deck['id']}")
    assert before["status"] == "ready", [
        (s["ordinal"], s["error_code"]) for s in before["slides"] if s["status"] == "failed"
    ]
    assert len(before["slides"]) == 15
    assert before["pdf_export"]["page_count"] == 15
    slide = before["slides"][1]
    revision = request(
        f"/decks/{deck['id']}/slides/{slide['id']}/revise",
        {"revision": slide["revision"], "action": "visual", "instruction": "增加留白"},
    )
    wait_job(revision)
    after = request(f"/decks/{deck['id']}")
    assert after["status"] == "ready"
    assert after["slides"][1]["spec"] == before["slides"][1]["spec"]
    for index in range(15):
        if index != 1:
            assert after["slides"][index] == before["slides"][index]
    chapters = request(f"/sources/{source_ids[-1]}/nodes")
    selected = [n["id"] for n in chapters if n["title"] in {"Section Alpha", "Section Beta"}]
    assert len(selected) == 2
    batch_request = {
        "request_key": "container-hierarchy-batch",
        "scope": {"kind": "nodes", "source_id": source_ids[-1], "node_ids": selected},
        "slide_count": 10,
    }
    batch = request(f"/notebooks/{notebook_id}/decks/batch", batch_request)
    batch_deck_ids = [d["id"] for d in batch["decks"]]
    assert len(batch_deck_ids) == 2
    for created, node_id in zip(batch["decks"], selected, strict=True):
        wait_job(created["job"])
        saved = request(f"/decks/{created['id']}")
        assert saved["source_scope"]["node_id"] == node_id
        assert saved["generation_metadata"]["batch_id"] == batch["batch_id"]
        assert saved["pdf_export"]["page_count"] == 10
    stopped = request(
        f"/notebooks/{notebook_id}/decks",
        {"slide_count": 10, "scope": {"kind": "source", "source_id": source_ids[3]}},
    )
    paused = request(f"/decks/{stopped['id']}/stop", {})
    assert paused["status"] == "paused" and paused["job"]["status"] == "cancelled"
    podcast = request(
        f"/notebooks/{notebook_id}/podcasts",
        {
            "scope": {"kind": "source", "source_id": source_ids[3]},
            "target_minutes": 5,
            "language": "en",
        },
    )
    wait_job(podcast["job"])
    mindmap = request(
        f"/notebooks/{notebook_id}/mindmaps",
        {"scope": {"kind": "source", "source_id": source_ids[3]}, "language": "en"},
    )
    wait_job(mindmap["job"])
    values, downloads, hashes = snapshots(
        notebook_id,
        source_ids,
        knowledge_id,
        deck["id"],
        batch_deck_ids,
        stopped["id"],
        podcast["id"],
        mindmap["id"],
    )
    pdf = request(after["pdf_export"]["download_url"].removeprefix("/api"))
    assert pdf.startswith(b"%PDF-")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    (state_path.parent / "container-deck.pdf").write_bytes(pdf)
    state_path.write_text(
        json.dumps(
            dict(
                notebook_id=notebook_id,
                source_ids=source_ids,
                knowledge_id=knowledge_id,
                deck_id=deck["id"],
                batch_id=batch["batch_id"],
                batch_request=batch_request,
                batch_deck_ids=batch_deck_ids,
                stopped_deck_id=stopped["id"],
                podcast_id=podcast["id"],
                mindmap_id=mindmap["id"],
                snapshots=values,
                downloads=downloads,
                hashes=hashes,
                files=container_files(),
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "phase": "prepare",
                "sources": len(source_ids),
                "slides": 15,
                "batch_decks": 2,
                "stopped_decks": 1,
                "mindmaps": 1,
                "snapshots": len(values),
            }
        )
    )


def verify(state_path):
    state = json.loads(state_path.read_text())
    repeated = request(f"/notebooks/{state['notebook_id']}/decks/batch", state["batch_request"])
    assert repeated["batch_id"] == state["batch_id"]
    assert [d["id"] for d in repeated["decks"]] == state["batch_deck_ids"]
    values, downloads, hashes = snapshots(
        state["notebook_id"],
        state["source_ids"],
        state["knowledge_id"],
        state["deck_id"],
        state["batch_deck_ids"],
        state.get("stopped_deck_id"),
        state.get("podcast_id"),
        state.get("mindmap_id"),
    )
    assert values == state["snapshots"], "API state changed after recreation"
    assert downloads == state["downloads"]
    assert hashes == state["hashes"], "Persisted asset/PDF bytes changed after recreation"
    files = container_files()
    assert files == state["files"], "Persisted files changed after recreation"
    # All four roles must still decrypt the persisted key and reach the provider.
    for role in ("language", "embedding", "image", "speech"):
        result = request(
            "/settings/models/discover",
            dict(role=role, base_url=PROVIDER, model_id="test-model", use_saved_key=True),
        )
        assert "test-model" in result["models"]
    print(
        json.dumps(
            {
                "phase": "verify",
                "snapshots": len(values),
                "download_hashes": len(hashes),
                "persisted_files": len(files),
                "saved_secrets_decrypted": 4,
                "podcast_audio_preserved": bool(state.get("podcast_id")),
                "mindmap_tree_and_exports_preserved": bool(state.get("mindmap_id")),
                "batch_retry_reused": True,
                "stopped_deck_preserved": bool(state.get("stopped_deck_id")),
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "verify"))
    parser.add_argument(
        "--state", type=Path, default=Path("frontend/test-results/container-state.json")
    )
    args = parser.parse_args()
    if args.phase == "prepare":
        prepare(args.state)
    else:
        verify(args.state)
