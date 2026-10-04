"""Original pixels, scope boundaries, bounded reading and citation provenance."""

import asyncio
import base64
import copy
import hashlib
import json
from io import BytesIO

import httpx
import pytest
from fastapi.testclient import TestClient
from grounded_provider import completion
from image_factory import image_response
from opennotelm.composition import CompositionService
from opennotelm.errors import AppError
from opennotelm.main import create_app
from opennotelm.retrieval import Scope
from opennotelm.schemas import StrictModel
from opennotelm.source_visuals import (
    IMAGE_TOKENS,
    MAX_IMAGES,
    VISUAL_PLACEHOLDER,
    VISUAL_VERSION,
    bind_visuals,
    content_tokens,
    pack_visual_items,
)
from opennotelm.structured import structured_completion
from PIL import Image, ImageDraw
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from test_decks import create_deck
from test_generated_pages import NoNativeRenderer
from test_models import config
from test_sources import wait_for_job
from vision_factory import vision_completion


def illustrated_pdf(pages=2, color="red"):
    output = BytesIO()
    pdf = Canvas(output, invariant=1)
    for index in range(pages):
        pdf.bookmarkPage(str(index))
        pdf.addOutlineEntry(f"Chapter {index + 1}", str(index))
        image = Image.new("RGB", (600, 400), "white")
        drawing = ImageDraw.Draw(image)
        drawing.rectangle((40 + index * 5, 40, 240, 200), fill=color)
        drawing.ellipse((350, 180, 560, 350), fill="green")
        raw = BytesIO()
        image.save(raw, "PNG")
        # No text: the entire semantic diagram is in original pixels.
        pdf.drawImage(ImageReader(BytesIO(raw.getvalue())), 30, 350, width=520, height=350)
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def text_payload(payload):
    value = copy.deepcopy(payload)
    content = value["messages"][-1]["content"]
    if isinstance(content, list):
        value["messages"][-1]["content"] = content[0]["text"]
    return value


def request_data(payload):
    return json.loads(text_payload(payload)["messages"][-1]["content"])


def original_calls(calls, prefix):
    return [
        call
        for call in calls
        if call.get("messages", [{}])[0].get("content", "").startswith(prefix)
        and isinstance(call["messages"][-1]["content"], list)
    ]


@pytest.fixture
def visual_decks(settings):
    calls, state = [], {"bad_author": False, "fail_visual": False}

    def provider(request):
        payload = json.loads(request.content)
        calls.append(payload)
        if request.url.path.endswith("/images/generations"):
            return httpx.Response(200, json=image_response(payload.get("size")))
        if request.url.path.endswith("/embeddings"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"index": i, "embedding": [0.2, 0.8]} for i in range(len(payload["input"]))
                    ]
                },
            )
        system = payload["messages"][0]["content"]
        if system.startswith("Transcribe one document image"):
            # Deliberately omit the shapes, colors and spatial relationship from the transcript.
            result = json.dumps({"paragraphs": [], "description": "A diagram.", "uncertain": False})
        else:
            visual = isinstance(payload["messages"][-1]["content"], list)
            if visual and state["fail_visual"]:
                return httpx.Response(503)
            result = (
                vision_completion(payload)
                if payload["messages"][0]["role"] == "user" and visual
                else None
            )
            result = result or completion(text_payload(payload))
            if system.startswith("Author one SlideSpec") and VISUAL_PLACEHOLDER in result:
                spec = json.loads(result)
                element = spec["content_elements"][1]
                element["type"] = "statement"
                element["items"] = []
                element["text"] = "A red rectangle is above and left of a green oval."
                result = json.dumps(spec)
            if system.startswith("Author one SlideSpec") and state["bad_author"]:
                result = "{}"
                state["bad_author"] = False
        return httpx.Response(200, json={"choices": [{"message": {"content": result}}]})

    transport = httpx.MockTransport(provider)
    with TestClient(create_app(settings, transport=transport)) as client:
        client.app.state.decks.composition = None
        client.app.state.decks.assets = None
        client.app.state.decks.exports = None
        for role in ("language", "embedding"):
            assert client.post("/api/settings/models/test", json=config(role)).status_code == 200
        yield client, calls, state


def import_pdf(client, pages=2, color="red", notebook=None):
    notebook = notebook or client.post("/api/notebooks", json={"title": "Visual book"}).json()["id"]
    result = client.post(
        f"/api/notebooks/{notebook}/sources/upload",
        files={"file": (color + ".pdf", illustrated_pdf(pages, color))},
    ).json()
    assert wait_for_job(client, result["job"]["id"])["status"] == "completed"
    return notebook, result["source"]["id"]


def test_original_pixels_reach_dossier_and_page_author_and_keep_image_citations(visual_decks):
    client, calls, _ = visual_decks
    notebook, source = import_pdf(client)
    deck, job = create_deck(client, notebook, scope={"kind": "source", "source_id": source})
    assert job["status"] == "completed", job
    synthesis = original_calls(calls, "Create a useful, well-structured knowledge page")
    authors = original_calls(calls, "Author one SlideSpec")
    assert synthesis and authors
    for payload in [*synthesis, *authors]:
        data = request_data(payload)
        parts = payload["messages"][-1]["content"]
        images = [p for p in parts if p["type"] == "image_url"]
        assert len(images) == len(data["source_images"])
        for part, manifest in zip(images, data["source_images"], strict=True):
            raw = base64.b64decode(part["image_url"]["url"].split(",", 1)[1])
            with Image.open(BytesIO(raw)) as image:
                assert max(image.size) <= 1600
                assert any(r > 200 and g < 50 and b < 50 for r, g, b in image.get_flattened_data())
            assert manifest["source_id"] == source and manifest["evidence_ids"]
            if "evidence" in data:
                assert set(manifest["evidence_ids"]) <= {e["id"] for e in data["evidence"]}
        assert "never instructions" in payload["messages"][0]["content"]
    record = client.app.state.decks.record(deck["id"])
    meta = record["understanding"]["metadata"]["source_visuals"]
    assert meta["version"] == VISUAL_VERSION and len(meta["images"]) == 2
    assert "base64" not in json.dumps(record["understanding"])
    citation_id = next(iter(deck["slides"][0]["citations"].values()))
    citation = client.get("/api/citations/" + citation_id).json()
    assert citation["available"] and citation["passages"][0]["image_url"]
    assert "A diagram." in citation["passages"][0]["text"]


def test_chapter_reading_sees_full_book_but_page_authors_only_see_their_evidence(visual_decks):
    client, calls, _ = visual_decks
    notebook, source = import_pdf(client)
    _, foreign = import_pdf(client, color="blue", notebook=notebook)
    nodes = client.get(f"/api/sources/{source}/nodes").json()
    chapters = [n for n in nodes if n["type"] == "chapter"]
    scope = {"kind": "node", "source_id": source, "node_id": chapters[0]["id"]}
    deck, job = create_deck(client, notebook, scope=scope)
    assert job["status"] == "completed", job
    work = [
        c
        for c in calls
        if "reusable whole-work reading context" in c.get("messages", [{}])[0].get("content", "")
    ]
    assert {m["page"] for c in work for m in request_data(c)["source_images"]} == {1, 2}
    primary = [
        c
        for c in original_calls(calls, "Create a useful, well-structured knowledge page")
        if "user_instruction" in request_data(c)
    ]
    assert {m["page"] for c in primary for m in request_data(c)["source_images"]} == {1}
    assert foreign not in json.dumps([*work, *primary])
    for call in original_calls(calls, "Author one SlideSpec"):
        data = request_data(call)
        assert all(
            set(m["evidence_ids"]) <= {e["id"] for e in data["evidence"]}
            for m in data["source_images"]
        )
    count = len(work)
    create_deck(client, notebook, scope={**scope, "node_id": chapters[1]["id"]})
    assert (
        len(
            [
                c
                for c in calls
                if "reusable whole-work reading context"
                in c.get("messages", [{}])[0].get("content", "")
            ]
        )
        == count
    )
    assert client.app.state.decks.record(deck["id"])["understanding"]["work_context"]


def test_many_images_are_all_read_in_bounded_batches_and_reduce_as_text(visual_decks):
    client, calls, _ = visual_decks
    notebook, source = import_pdf(client, pages=7)
    deck, job = create_deck(client, notebook, scope={"kind": "source", "source_id": source})
    assert job["status"] == "completed", job
    readings = original_calls(calls, "Create a useful, well-structured knowledge page")
    assert len(readings) >= 2
    assert {m["page"] for c in readings for m in request_data(c)["source_images"]} == set(
        range(1, 8)
    )
    assert all(len(request_data(c)["source_images"]) <= MAX_IMAGES for c in readings)
    for call in readings:
        assert (
            sum(content_tokens(m["content"]) for m in call["messages"]) + call["max_tokens"] < 16000
        )
    understanding = client.app.state.decks.record(deck["id"])["understanding"]
    assert understanding["metadata"]["reduction_levels"] > 0
    assert len(understanding["metadata"]["source_visuals"]["images"]) == 7


def test_image_changes_invalidate_work_reading_without_changing_transcript(visual_decks):
    client, calls, _ = visual_decks
    notebook, source = import_pdf(client)
    chapter = next(
        n for n in client.get(f"/api/sources/{source}/nodes").json() if n["type"] == "chapter"
    )
    scope = {"kind": "node", "source_id": source, "node_id": chapter["id"]}
    one, job = create_deck(client, notebook, scope=scope)
    assert job["status"] == "completed"
    before = client.app.state.decks.record(one["id"])["understanding"]["metadata"]["work_context"]
    block = next(b for b in client.app.state.sources.blocks(source) if b["type"] == "image")
    path = client.app.state.sources.media_path(source, block["metadata"]["image_id"])
    with Image.open(path) as image:
        image = image.copy()
        ImageDraw.Draw(image).rectangle((50, 50, 200, 200), fill="purple")
        image.save(path, "PNG")
    two, job = create_deck(client, notebook, scope=scope)
    assert job["status"] == "completed"
    after = client.app.state.decks.record(two["id"])["understanding"]["metadata"]["work_context"]
    assert before["readings"][0]["input_hash"] != after["readings"][0]["input_hash"]
    assert not after["readings"][0]["cache_reused"]


def test_multimodal_repair_retains_originals_and_missing_media_fails_explicitly(visual_decks):
    client, calls, state = visual_decks
    notebook, source = import_pdf(client, pages=1)
    state["bad_author"] = True
    deck, job = create_deck(client, notebook, scope={"kind": "source", "source_id": source})
    assert job["status"] == "completed"
    authors = original_calls(calls, "Author one SlideSpec")
    repair = next(c for c in authors if "previous JSON failed" in c["messages"][0]["content"])
    original = next(
        c
        for c in authors
        if request_data(c)["slide_plan"] == request_data(repair)["slide_plan"] and c is not repair
    )
    assert "candidate_data" in request_data(repair)
    assert original["messages"][-1]["content"][1:] == repair["messages"][-1]["content"][1:]
    block = next(b for b in client.app.state.sources.blocks(source) if b["type"] == "image")
    client.app.state.sources.media_path(source, block["metadata"]["image_id"]).unlink()
    failed, job = create_deck(client, notebook, scope={"kind": "source", "source_id": source})
    assert job["status"] == "failed" and job["error_code"] == "SOURCE_MEDIA_NOT_FOUND"
    assert not client.app.state.decks.record(failed["id"])["understanding"]
    assert client.get(f"/api/decks/{deck['id']}").json()["status"] == "draft"


def test_provider_rejecting_images_does_not_silently_generate_from_transcripts(visual_decks):
    client, calls, state = visual_decks
    notebook, source = import_pdf(client, pages=1)
    state["fail_visual"] = True
    deck, job = create_deck(client, notebook, scope={"kind": "source", "source_id": source})
    assert job["status"] == "failed"
    assert not client.app.state.decks.record(deck["id"])["understanding"]
    assert original_calls(calls, "Create a useful, well-structured knowledge page")
    state["fail_visual"] = False
    resumed = client.post(f"/api/decks/{deck['id']}/retry").json()
    assert wait_for_job(client, resumed["id"])["status"] == "completed"


def test_knowledge_contract_stays_text_only(visual_decks):
    client, calls, _ = visual_decks
    notebook, source = import_pdf(client)
    response = client.post(
        f"/api/notebooks/{notebook}/knowledge",
        json={"scope": {"kind": "source", "source_id": source}},
    )
    assert response.status_code == 202, response.text
    assert wait_for_job(client, response.json()["job"]["id"])["status"] == "completed"
    assert not original_calls(calls, "Create a useful, well-structured knowledge page")


def test_image_budget_counts_pixels_without_counting_base64_as_text():
    parts = [
        {"type": "text", "text": "a" * 300},
        {"type": "image_url", "image_url": {"url": "data:" + "a" * 90000}},
    ]
    assert content_tokens(parts) == 100 + IMAGE_TOKENS
    items = [{"id": f"E{i}", "text": "A diagram."} for i in range(7)]
    groups = pack_visual_items(items, IMAGE_TOKENS * 3 + 200, {f"E{i}": [str(i)] for i in range(7)})
    assert [i for group in groups for i in group] == items
    assert all(len(group) <= 3 for group in groups)
    with pytest.raises(AppError, match="CONTEXT_BUDGET_EXCEEDED"):
        pack_visual_items(items, 100, {"E0": ["first"]})


def test_bound_original_changes_are_detected_before_sending(visual_decks):
    client, _, _ = visual_decks
    notebook, source = import_pdf(client, pages=1)
    blocks = client.app.state.retrieval.scope_blocks(
        notebook, Scope(kind="source", source_id=source)
    )
    visual = next(iter(client.app.state.knowledge.synthesis.visuals.collect(blocks).values()))
    assert visual.sha256 == hashlib.sha256(visual.path.read_bytes()).hexdigest()
    visual.path.write_bytes(b"changed")
    with pytest.raises(AppError, match="SOURCE_IMAGE_INVALID"):
        visual.image_part()


def test_observed_visual_guidance_reaches_art_direction_and_final_page_prompt(
    visual_decks, settings
):
    client, calls, _ = visual_decks
    notebook, source = import_pdf(client, pages=1)
    assert client.post("/api/settings/models/test", json=config("image")).status_code == 200
    client.app.state.decks.composition = CompositionService(
        client.app.state.db, client.app.state.models, settings, NoNativeRenderer()
    )
    client.app.state.decks.assets = client.app.state.assets
    client.app.state.decks.exports = client.app.state.pdf_exports
    deck, job = create_deck(
        client,
        notebook,
        scope={"kind": "source", "source_id": source},
        render_mode="generated_page",
    )
    assert job["status"] == "completed", job
    art = next(
        c
        for c in calls
        if c.get("messages", [{}])[0]
        .get("content", "")
        .startswith("Art-direct the complete illustrated deck")
    )
    assert all(p["source_visual_guidance"] for p in request_data(art)["pages"])
    images = [c for c in calls if "PAGE DATA:\n" in c.get("prompt", "")]
    assert len(images) == 10
    assert all(
        json.loads(c["prompt"].split("PAGE DATA:\n")[1])["source_visual_guidance"] for c in images
    )
    assert all("pixel-identical" in c["prompt"] for c in images)
    assert deck["pdf_export"]["status"] == "ready"


def test_captionless_image_can_be_read_and_cited_without_fabricating_text(visual_decks):
    client, calls, _ = visual_decks
    notebook, source = import_pdf(client, pages=2)
    block = next(b for b in client.app.state.sources.blocks(source) if b["type"] == "image")
    with client.app.state.db.connect() as conn:
        conn.execute("UPDATE content_blocks SET text='' WHERE id=?", (block["id"],))
    deck, job = create_deck(client, notebook, scope={"kind": "source", "source_id": source})
    assert job["status"] == "completed", job
    assert original_calls(calls, "Author one SlideSpec")
    citation_id = next(iter(deck["slides"][0]["citations"].values()))
    citation = client.get("/api/citations/" + citation_id).json()
    assert citation["available"]
    assert citation["spans"][0]["start_offset"] == citation["spans"][0]["end_offset"] == 0
    assert citation["spans"][0]["quote"] == ""
    assert citation["passages"][0]["image_url"]
    assert citation["passages"][0]["text"] == ""
    assert client.app.state.sources.blocks(source)[0]["text"] == ""
    understanding = client.app.state.decks.record(deck["id"])["understanding"]
    spans = [span for packet in understanding["evidence"] for span in packet["spans"]]
    with client.app.state.db.connect() as conn:
        ref = client.app.state.citations.persist(
            conn,
            notebook,
            "message",
            "mixed",
            "[[Emixed]]",
            [{"id": "Emixed", "text": "", "spans": spans}],
        )["Emixed"]
    mixed = client.get("/api/citations/" + ref).json()
    assert len(mixed["passages"]) == 2
    assert all(p["image_url"] for p in mixed["passages"])
    assert {p["text"] for p in mixed["passages"]} == {"", "A diagram."}
    client.app.state.sources.media_path(source, block["metadata"]["image_id"]).unlink()
    assert not client.get("/api/citations/" + citation_id).json()["available"]


def test_zero_width_text_span_cannot_impersonate_an_image_citation(visual_decks):
    client, _, _ = visual_decks
    notebook, source = import_pdf(client, pages=1)
    block = client.app.state.sources.blocks(source)[0]
    packet = {
        "id": "Ezero",
        "text": "",
        "spans": [
            {"source_id": source, "block_id": block["id"], "start_offset": 0, "end_offset": 0}
        ],
    }
    with client.app.state.db.connect() as conn:
        with pytest.raises(AppError, match="CITATION_SOURCE_CHANGED"):
            client.app.state.citations.persist(
                conn, notebook, "message", "bad", "[[Ezero]]", [packet]
            )

        conn.rollback()
        conn.execute(
            "UPDATE content_blocks SET text='',type='paragraph' WHERE id=?", (block["id"],)
        )
        with pytest.raises(AppError, match="CITATION_SOURCE_CHANGED"):
            client.app.state.citations.persist(
                conn, notebook, "message", "bad", "[[Ezero]]", [packet]
            )


def test_page_review_attachment_count_adapts_to_remaining_context(visual_decks):
    client, calls, _ = visual_decks
    _, source = import_pdf(client, pages=4)
    synthesis = client.app.state.knowledge.synthesis
    blocks = client.app.state.sources.blocks(source)
    refs = bind_visuals(
        synthesis.evidence(blocks, "budget", 16000), synthesis.visuals.collect(blocks)
    )

    class Probe(StrictModel):
        ok: bool

    output = asyncio.run(
        structured_completion(
            client.app.state.models, "Budget test. Return ok=true.", {}, Probe, source_images=refs
        )
    )
    assert output.ok
    call = calls[-1]
    data = request_data(call)
    assert 0 < len(data["source_images"]) < 4
    assert len(data["source_images"]) + len(data["additional_source_images_not_reattached"]) == 4
    assert sum(content_tokens(m["content"]) for m in call["messages"]) + call["max_tokens"] < 16000


def test_identical_visual_readings_reused_across_jobs_with_current_citation_ids(visual_decks):
    client, calls, _ = visual_decks
    notebook, source = import_pdf(client, pages=5)
    scope = {"kind": "source", "source_id": source}
    first, job = create_deck(client, notebook, scope=scope)
    assert job["status"] == "completed", job
    reductions = [
        c
        for c in calls
        if c.get("messages", [{}])[0]
        .get("content", "")
        .startswith("Create a useful, well-structured knowledge page")
        and request_data(c).get("task", "").startswith("Condense")
    ]
    assert reductions
    before = len(reductions)
    second, job = create_deck(client, notebook, scope=scope)
    assert job["status"] == "completed", job
    reductions = [
        c
        for c in calls
        if c.get("messages", [{}])[0]
        .get("content", "")
        .startswith("Create a useful, well-structured knowledge page")
        and request_data(c).get("task", "").startswith("Condense")
    ]
    assert len(reductions) == before
    one = client.app.state.decks.record(first["id"])["understanding"]
    two = client.app.state.decks.record(second["id"])["understanding"]
    assert one["evidence"][0]["id"] != two["evidence"][0]["id"]
    assert one["evidence"][0]["id"] not in two["content"]
