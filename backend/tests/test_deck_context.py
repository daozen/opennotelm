"""Automatic parent-work reading, explicit scope overrides and exact provenance."""

import asyncio
import json
import threading
import time
from types import SimpleNamespace

from opennotelm.chunking import estimate_tokens
from opennotelm.deck_context import WORK_CONTEXT_VERSION, work_context
from opennotelm.retrieval import Scope
from test_decks import create_deck  # noqa: F401
from test_decks import decks as decks
from test_knowledge import create_page, import_text
from test_models import config
from test_sources import wait_for_job


def chapter_fixture(client):
    notebook = client.post("/api/notebooks", json={"title": "Book context"}).json()["id"]
    source = import_text(
        client,
        notebook,
        "# The journey\n\nThe journey begins with learning to give.\n\n"
        "## Waiting\n\nSELECTED_CHAPTER: waiting is a preparation, not idleness.\n\n"
        "## Returning\n\nOTHER_CHAPTER: returning turns abundance into a gift.",
        name="book.md",
    )
    import_text(client, notebook, "FOREIGN_WORK_MUST_NOT_LEAK", name="different-book.txt")
    nodes = client.get(f"/api/sources/{source}/nodes").json()
    chapters = [n for n in nodes if n["title"] in ("Waiting", "Returning")]
    return notebook, source, chapters


def work_calls(state):
    return [
        c
        for c in state["calls"]
        if "reusable whole-work reading context" in c["messages"][0]["content"]
    ]


def test_parallel_chapter_decks_share_first_whole_book_read_and_keep_provenance(decks):
    client, state, _ = decks
    notebook, source, chapters = chapter_fixture(client)
    original = client.app.state.models.gateway.text
    entered = threading.Event()
    release = asyncio.Event()
    reads = 0

    async def delayed(config, key, messages, **kwargs):
        nonlocal reads
        if "reusable whole-work reading context" in messages[0]["content"]:
            reads += 1
            entered.set()
            await release.wait()
        return await original(config, key, messages, **kwargs)

    client.app.state.models.gateway.text = delayed
    jobs = []
    try:
        for chapter in chapters:
            response = client.post(
                f"/api/notebooks/{notebook}/decks",
                json={
                    "slide_count": 10,
                    "render_mode": "native",
                    "scope": {"kind": "node", "source_id": source, "node_id": chapter["id"]},
                },
            )
            assert response.status_code == 202
            jobs.append(response.json())
        assert entered.wait(2)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if all(
                client.get(f"/api/jobs/{d['job']['id']}").json()["status"] == "running"
                for d in jobs
            ):
                break
            time.sleep(0.01)
        assert all(
            client.get(f"/api/jobs/{d['job']['id']}").json()["status"] == "running" for d in jobs
        )
        assert reads == 1
    finally:
        client.portal.call(release.set)
    for item in jobs:
        assert wait_for_job(client, item["job"]["id"])["status"] == "completed"
        for packet in client.app.state.decks.record(item["id"])["understanding"]["evidence"]:
            assert all(span["source_id"] == source for span in packet["spans"])
    assert reads == 1 and len(work_calls(state)) == 1


def test_chapter_reads_whole_book_once_and_reuses_it_for_sibling_chapters(decks):
    client, state, _ = decks
    notebook, source, chapters = chapter_fixture(client)
    one, job = create_deck(
        client, notebook, scope={"kind": "node", "source_id": source, "node_id": chapters[0]["id"]}
    )
    assert job["status"] == "completed", job
    assert len(work_calls(state)) == 1
    prompts = json.dumps(state["calls"])
    assert "OTHER_CHAPTER" in prompts and "FOREIGN_WORK_MUST_NOT_LEAK" not in prompts
    record = client.app.state.decks.record(one["id"])
    value = record["understanding"]
    work = value["work_context"]
    assert work["sources"][0]["selected_paths"] == [["The journey", "Waiting"]]
    assert [s["title"] for s in work["sources"][0]["work_outline"]] == [
        "The journey",
        "Waiting",
        "Returning",
    ]
    primary = client.app.state.knowledge.retrieval.scope_blocks(
        notebook, Scope.model_validate(record["source_scope"]), frozen=True
    )
    assert value["metadata"]["block_ids"] == [b["id"] for b in primary]
    info = value["metadata"]["work_context"]
    assert info["version"] == WORK_CONTEXT_VERSION and info["mode"] == "whole_work"
    assert info["readings"][0]["block_count"] > len(primary)
    assert not info["readings"][0]["cache_reused"]
    assert value["work_context"]["whole_work_readings"][0]["content"]
    for packet in value["evidence"]:
        for span in packet["spans"]:
            block = next(
                b for b in client.app.state.sources.blocks(source) if b["id"] == span["block_id"]
            )
            assert span["source_id"] == source
            assert block["text"][span["start_offset"] : span["end_offset"]]
    two, job = create_deck(
        client, notebook, scope={"kind": "node", "source_id": source, "node_id": chapters[1]["id"]}
    )
    assert job["status"] == "completed"
    assert len(work_calls(state)) == 1
    info = client.app.state.decks.record(two["id"])["understanding"]["metadata"]["work_context"]
    assert info["readings"][0]["cache_reused"]
    assert client.app.state.decks.record(one["id"])["understanding"] == value


def test_background_chapter_claim_gets_its_own_original_citation(decks):
    client, state, _ = decks
    notebook, source, chapters = chapter_fixture(client)
    original = client.app.state.models.gateway.text

    async def with_connection(model, key, messages, **kwargs):
        output = await original(model, key, messages, **kwargs)
        data = json.loads(messages[-1]["content"])
        work = data.get("work_context") or {}
        if data.get("material") and work.get("evidence_ids"):
            ref = work["evidence_ids"][-1]
            output += f"\n\nThe later chapter explains giving as a response to waiting. [[{ref}]]"
        return output

    client.app.state.models.gateway.text = with_connection
    deck, job = create_deck(
        client, notebook, scope={"kind": "node", "source_id": source, "node_id": chapters[0]["id"]}
    )
    assert job["status"] == "completed", job
    background_citations = [
        ref
        for slide in deck["slides"]
        for marker, ref in slide["citations"].items()
        if marker.startswith("EW")
    ]
    assert background_citations
    for ref in background_citations:
        citation = client.get(f"/api/citations/{ref}").json()
        assert citation["spans"][0]["source_id"] == source
        assert "OTHER_CHAPTER" in " ".join(s["quote"] for s in citation["spans"])
    assert deck["source_scope"]["node_id"] == chapters[0]["id"]


def test_explicit_chapter_only_request_skips_parent_body_reading(decks):
    client, state, _ = decks
    notebook, source, chapters = chapter_fixture(client)
    original = client.app.state.models.gateway.text

    async def override(model, key, messages, **kwargs):
        output = await original(model, key, messages, **kwargs)
        if messages[0]["content"].startswith("Resolve deck content preferences."):
            value = json.loads(output)
            value["chapter_only"] = True
            output = json.dumps(value)
        return output

    client.app.state.models.gateway.text = override
    response = client.post(
        f"/api/notebooks/{notebook}/decks",
        json={
            "scope": {"kind": "node", "source_id": source, "node_id": chapters[0]["id"]},
            "slide_count": 10,
            "instruction": "只分析本章，不联系全书",
            "render_mode": "native",
        },
    )
    assert response.status_code == 202
    assert wait_for_job(client, response.json()["job"]["id"])["status"] == "completed"
    assert not work_calls(state)
    assert "OTHER_CHAPTER" not in json.dumps(state["calls"])
    value = client.app.state.decks.record(response.json()["id"])["understanding"]
    assert value["metadata"]["work_context"]["mode"] == "chapter_only"
    assert value["work_context"] == {}


def test_cache_invalidates_on_actual_source_change_and_model_change(decks):
    client, state, _ = decks
    notebook, source, chapters = chapter_fixture(client)
    scope = {"kind": "node", "source_id": source, "node_id": chapters[0]["id"]}
    create_deck(client, notebook, scope=scope)
    with client.app.state.db.connect() as conn:
        conn.execute(
            "UPDATE content_blocks SET text=text || ' Revised whole-work fact.' "
            "WHERE source_id=? AND node_id=?",
            (source, chapters[1]["id"]),
        )
    create_deck(client, notebook, scope=scope)
    assert len(work_calls(state)) == 2
    assert (
        client.post("/api/settings/models/test", json=config(model_id="new-model")).status_code
        == 200
    )
    create_deck(client, notebook, scope=scope)
    assert len(work_calls(state)) == 3
    with client.app.state.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM work_context_cache").fetchone()[0] == 1


def test_whole_source_and_knowledge_do_not_make_extra_book_calls(decks):
    client, state, _ = decks
    notebook, source, chapters = chapter_fixture(client)
    _, job = create_deck(client, notebook, scope={"kind": "source", "source_id": source})
    assert job["status"] == "completed"
    before = len(state["calls"])
    _, job = create_page(
        client, notebook, scope={"kind": "node", "source_id": source, "node_id": chapters[0]["id"]}
    )
    assert job["status"] == "completed"
    assert not work_calls(state)
    assert "OTHER_CHAPTER" not in json.dumps(state["calls"][before:])
    assert "work_context" not in json.loads(state["calls"][-1]["messages"][-1]["content"])


def test_structure_is_bounded_keeps_ancestors_and_excludes_pdf_pages():
    sources = [{"id": "book", "title": "An unfamiliar work"}]
    nodes = [
        {
            "id": f"n{i}",
            "parent_id": None,
            "title": f"Chapter {i}",
            "type": "chapter",
            "depth": 1,
            "ordinal": i,
        }
        for i in range(1000)
    ]
    nodes.extend(
        [
            {
                "id": "part",
                "parent_id": "n501",
                "title": "A selected subsection",
                "type": "heading",
                "depth": 2,
                "ordinal": 1001,
            },
            {
                "id": "page",
                "parent_id": None,
                "title": "Page 1",
                "type": "page",
                "depth": 1,
                "ordinal": 1002,
            },
        ]
    )
    result = work_context(
        sources,
        {"book": nodes},
        {"kind": "node", "node_id": "part"},
        [{"source_id": "book"}],
        budget=1800,
    )
    assert estimate_tokens(json.dumps(result, ensure_ascii=False)) <= 1800
    entry = result["sources"][0]
    assert entry["selected_paths"] == [["Chapter 501", "A selected subsection"]]
    assert entry["outline_omitted"] > 0
    assert entry["selected_positions"] == [1000]
    assert {"Chapter 501", "A selected subsection"} <= {n["title"] for n in entry["work_outline"]}

    assert all(n["title"] != "Page 1" for n in entry["work_outline"])


def test_long_work_reads_all_blocks_and_checkpoints_resume_without_rereading(decks):
    client, state, _ = decks
    notebook = client.post("/api/notebooks", json={"title": "Long book"}).json()["id"]
    source = import_text(
        client,
        notebook,
        "\n\n".join(f"## Section {i}\n\n" + f"Distinct idea {i}. " * 100 for i in range(20)),
    )
    service = client.app.state.decks.work_context
    with client.app.state.db.connect() as conn:
        conn.execute(
            "INSERT INTO jobs(id,type,entity_id,status,stage,payload_json,created_at) "
            "VALUES ('book-context-test','deck_generate','test','completed','completed',"
            "'{}','2026-01-01')"
        )
    context = SimpleNamespace(job={"id": "book-context-test"}, progress=lambda *args: None)
    one, cached = asyncio.run(
        service.read(
            client.app.state.sources.get(source), client.app.state.sources.nodes(source), context
        )
    )
    assert not cached and one["segment_count"] > 1
    material = [json.loads(c["messages"][-1]["content"])["material"] for c in work_calls(state)]
    supplied = " ".join(item["text"] for group in material for item in group)
    assert all(f"Distinct idea {i}." in supplied for i in range(20))
    before = len(work_calls(state))
    with client.app.state.db.connect() as conn:
        conn.execute("DELETE FROM work_context_cache")
    two, cached = asyncio.run(
        service.read(
            client.app.state.sources.get(source), client.app.state.sources.nodes(source), context
        )
    )
    assert not cached and two == one
    assert len(work_calls(state)) == before  # complete() reuses all durable job checkpoints.


def test_background_only_synthesis_is_repaired_even_after_reduction(decks):
    client, _, _ = decks
    synthesis = client.app.state.knowledge.synthesis
    original = client.app.state.models.gateway.text
    calls = []

    async def background_only(model, key, messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return "# Only book background [[Ework]]"
        return "# Selected chapter and background [[Echapter]] [[Ework]]"

    client.app.state.models.gateway.text = background_only
    with client.app.state.db.connect() as conn:
        conn.execute(
            "INSERT INTO jobs(id,type,entity_id,status,stage,payload_json,created_at) "
            "VALUES ('context-repair','deck_generate','test','completed','completed',"
            "'{}','2026-01-01')"
        )
    model, key = synthesis.models.configured("language")
    output = asyncio.run(
        synthesis.complete(
            [
                {
                    "text": "Previous reduction cites both [[Echapter]] [[Ework]]",
                    "evidence_ids": ["Echapter", "Ework"],
                }
            ],
            model,
            key,
            SimpleNamespace(job={"id": "context-repair"}),
            "final",
            False,
            purpose="deck",
            work_context={"evidence_ids": ["Ework"]},
        )
    )
    assert "Echapter" in output and len(calls) == 2
    assert "keep the selected material central" in calls[1][0]["content"]
    client.app.state.models.gateway.text = original


def test_failed_parent_read_does_not_cache_and_retry_resumes(decks):
    client, state, _ = decks
    notebook, source, chapters = chapter_fixture(client)
    original = client.app.state.models.gateway.text
    invalid = True

    async def unsupported(model, key, messages, **kwargs):
        if invalid and "reusable whole-work reading context" in messages[0]["content"]:
            return "# Fabricated map [[FAKE]]"
        return await original(model, key, messages, **kwargs)

    client.app.state.models.gateway.text = unsupported
    deck, job = create_deck(
        client, notebook, scope={"kind": "node", "source_id": source, "node_id": chapters[0]["id"]}
    )
    assert job["status"] == "failed"
    with client.app.state.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM work_context_cache").fetchone()[0] == 0
    invalid = False
    retry = client.post(f"/api/decks/{deck['id']}/retry").json()
    assert wait_for_job(client, retry["id"])["status"] == "completed"
    record = client.app.state.decks.record(deck["id"])
    assert record["understanding"]["metadata"]["work_context"]["mode"] == "whole_work"
    assert all("FAKE" not in item["text"] for item in record["understanding"]["evidence"])


def test_epub_toc_ancestry_survives_flat_reading_nodes():
    from opennotelm.deck_context import section_paths

    source = {
        "id": "book",
        "title": "A book",
        "metadata": {
            "toc": [
                {"title": "A book", "href": "front.xhtml", "fragment": "", "depth": 1},
                {"title": "Part Two", "href": "part.xhtml", "fragment": "", "depth": 2},
                {"title": "Moral people", "href": "chapter.xhtml", "fragment": "", "depth": 3},
                {
                    "title": "An inner section",
                    "href": "chapter.xhtml",
                    "fragment": "inner",
                    "depth": 4,
                },
            ]
        },
    }
    nodes = [
        {
            "id": "root",
            "parent_id": None,
            "title": "A book",
            "type": "document",
            "depth": 0,
            "ordinal": 0,
            "metadata": {},
        },
        {
            "id": "chapter",
            "parent_id": "root",
            "title": "Moral people",
            "type": "chapter",
            "depth": 1,
            "ordinal": 1,
            "metadata": {"href": "chapter.xhtml"},
        },
        {
            "id": "inner",
            "parent_id": "chapter",
            "title": "An inner section",
            "type": "heading",
            "depth": 2,
            "ordinal": 2,
            "metadata": {"href": "chapter.xhtml", "element_id": "inner"},
        },
    ]
    assert section_paths(source, nodes)["chapter"] == ["A book", "Part Two", "Moral people"]
    result = work_context(
        [source], {"book": nodes}, {"kind": "node", "node_id": "inner"}, [{"source_id": "book"}]
    )
    assert result["sources"][0]["selected_paths"] == [
        ["A book", "Part Two", "Moral people", "An inner section"]
    ]


def test_page_repair_removes_visible_internal_markers_without_losing_citations(decks):
    client, state, _ = decks
    notebook, source, chapters = chapter_fixture(client)
    original = client.app.state.models.gateway.text
    injected = False

    async def visible_marker(model, key, messages, **kwargs):
        nonlocal injected
        output = await original(model, key, messages, **kwargs)
        if messages[0]["content"].startswith("Author one SlideSpec") and not injected:
            value = json.loads(output)
            ref = json.loads(messages[-1]["content"])["evidence"][0]["id"]
            value["content_elements"][0]["text"] += f" [[{ref}]]"
            injected = True
            return json.dumps(value, ensure_ascii=False)
        return output

    client.app.state.models.gateway.text = visible_marker
    deck, job = create_deck(
        client, notebook, scope={"kind": "node", "source_id": source, "node_id": chapters[0]["id"]}
    )
    assert job["status"] == "completed" and deck["status"] == "draft"
    assert all(slide["citations"] for slide in deck["slides"])
    assert all(
        "[[" not in e["text"] for slide in deck["slides"] for e in slide["spec"]["content_elements"]
    )
    authors = [c for c in state["calls"] if c["messages"][0]["content"].startswith("Author one")]
    assert len(authors) == 11  # Only the malformed page was repaired.
    repair = next(c for c in authors if "previous JSON failed" in c["messages"][0]["content"])
    assert (
        "Move evidence markers from visible text"
        in json.loads(repair["messages"][-1]["content"])["validation_feedback"]
    )
    for call in authors:
        data = json.loads(call["messages"][-1]["content"])
        assert set(data["work_context"]["evidence_ids"]) <= {e["id"] for e in data["evidence"]}


def test_planner_can_cite_registered_background_absent_from_selected_dossier(decks):
    client, state, _ = decks
    notebook, source, chapters = chapter_fixture(client)
    original = client.app.state.models.gateway.text
    seen = []

    async def background_plan(model, key, messages, **kwargs):
        output = await original(model, key, messages, **kwargs)
        if messages[0]["content"].startswith("Plan the narrative"):
            data = json.loads(messages[-1]["content"])
            background = [e for e in data["citable_evidence"] if e["role"] == "whole_work"]
            selected = [e for e in background if f"[[{e['id']}]]" not in data["understanding"]]
            assert selected, "Regression must use background not already cited by the dossier"
            value = json.loads(output)
            value["slides"][0]["evidence_ids"].append(selected[-1]["id"])
            seen.append(selected[-1]["id"])
            return json.dumps(value)
        return output

    client.app.state.models.gateway.text = background_plan
    deck, job = create_deck(
        client, notebook, scope={"kind": "node", "source_id": source, "node_id": chapters[0]["id"]}
    )
    assert job["status"] == "completed", job
    assert len(seen) == 1
    assert seen[0] in deck["plan"]["slides"][0]["evidence_ids"]
