# ruff: noqa: F811
# Pytest injects the imported grounded fixture into test parameters.
from copy import deepcopy

import pytest
from document_factory import make_glyph_pdf
from opennotelm.chunking import estimate_tokens
from opennotelm.passages import project_passages
from opennotelm.retrieval import Scope
from restart_support import restart
from test_chat import ask, grounded, messages  # noqa: F401
from test_sources import wait_for_job

PARAGRAPH = (
    "这是按字绘制的中文资料，阅读时应该恢复完整段落。保留原始引用，才能准确返回资料中的位置。"
)


def imported_pdf(client):
    notebook = client.post("/api/notebooks", json={"title": "Paragraph citations"}).json()
    result = client.post(
        f"/api/notebooks/{notebook['id']}/sources/upload",
        files={"file": ("glyphs.pdf", make_glyph_pdf())},
    ).json()
    assert wait_for_job(client, result["job"]["id"])["status"] == "completed"
    source = result["source"]["id"]
    blocks = client.get(f"/api/sources/{source}/blocks").json()
    nodes = client.get(f"/api/sources/{source}/nodes").json()
    page = next(n for n in nodes if n["type"] == "page" and n["start_page"] == 1)
    return notebook["id"], source, blocks, nodes, page


def test_pdf_evidence_is_complete_paragraphs_with_exact_offsets_and_page_scope(grounded):
    client, state, _ = grounded
    notebook, source, blocks, nodes, page = imported_pdf(client)
    scope = Scope(kind="node", source_id=source, node_id=page["id"])
    evidence, trace = client.portal.call(
        client.app.state.retrieval.search, notebook, scope, "完整段落"
    )
    assert trace["evidence_version"] == "paragraph-v1"
    assert PARAGRAPH in [item["text"] for item in evidence]
    assert len(evidence) == 3  # one heading and two actual paragraphs, not glyphs
    facts = {b["id"]: b for b in blocks}
    for packet in evidence:
        assert estimate_tokens(packet["text"]) <= 1000
        for span in packet["spans"]:
            block = facts[span["block_id"]]
            assert block["page_start"] == 1
            assert block["text"][span["start_offset"] : span["end_offset"]]
    assert ask(client, notebook, "请解释完整段落", scope.model_dump())["status"] == "completed"
    answer = messages(client, notebook)[-1]
    assert PARAGRAPH in answer["content"]
    prompt = next(c for c in reversed(state["calls"]) if "messages" in c)["messages"][-1]["content"]
    assert PARAGRAPH in prompt and "第2页" not in prompt
    citation = client.get("/api/citations/" + next(iter(answer["citations"].values()))).json()
    assert len(citation["passages"]) == 1
    assert citation["passages"][0]["text"] == PARAGRAPH
    assert citation["passages"][0]["page"] == 1
    assert len(citation["spans"]) > 20
    assert "".join(span["quote"] for span in citation["spans"]) == PARAGRAPH
    assert client.get(f"/api/sources/{source}/blocks").json() == blocks
    assert client.get(f"/api/sources/{source}/nodes").json() == nodes


def test_historical_one_glyph_citation_gets_context_without_changing_provenance(grounded, settings):
    client, _, transport = grounded
    notebook, source, blocks, _, _ = imported_pdf(client)
    target = next(b for b in blocks if b["page_start"] == 1 and b["text"] == "原")
    original = {"source_id": source, "block_id": target["id"], "start_offset": 0, "end_offset": 1}
    with client.app.state.db.connect() as conn:
        refs = client.app.state.citations.persist(
            conn,
            notebook,
            "message",
            "historical-message",
            "已保存的回答[[Eold]]",
            [{"id": "Eold", "text": "原", "spans": [original]}],
        )
    citation_id = refs["Eold"]
    before = client.get(f"/api/citations/{citation_id}").json()
    assert before["spans"][0]["quote"] == "原"
    assert before["passages"][0]["text"] == PARAGRAPH
    assert before["passages"][0]["anchor_block_id"] == target["id"]
    assert len(before["passages"]) == 1
    with restart(client, settings, transport=transport) as restarted:
        assert restarted.get(f"/api/citations/{citation_id}").json() == before
        assert restarted.get(f"/api/sources/{source}/blocks").json() == blocks
        restarted.delete(f"/api/sources/{source}")
        deleted = restarted.get(f"/api/citations/{citation_id}").json()
        assert not deleted["available"]
        assert not deleted["passages"][0]["available"]
        assert deleted["spans"][0]["block_id"] == target["id"]


def test_duplicate_glyph_hits_group_into_one_paragraph_and_heading_scope_stays_isolated(grounded):
    client, _, _ = grounded
    _, source, blocks, _, _ = imported_pdf(client)
    hits = [
        {"source_id": source, "block_id": b["id"], "start_offset": 0, "end_offset": len(b["text"])}
        for b in blocks
        if b["page_start"] == 1 and b["text"] in {"这", "原", "保"}
    ]
    passages = client.app.state.sources.passages(source, hits * 3)
    assert [p["text"] for p in passages] == [PARAGRAPH]
    allowed = {next(b for b in blocks if b["id"] == hits[0]["block_id"])["node_id"]}
    bounded = client.app.state.sources.passages(source, hits, allowed)
    lookup = {b["id"]: b for b in blocks}
    assert all(lookup[s["block_id"]]["node_id"] in allowed for p in bounded for s in p["spans"])


def test_display_unicode_whitespace_and_long_paragraphs_keep_raw_coordinates():
    text = "The ﬁeld is large. 中文原文不能丢失。\n" * 160
    block = {"id": "raw", "source_id": "source", "text": text}
    projection = [
        {
            "type": "paragraph",
            "page_start": 1,
            "parts": [{"block_id": "raw", "text": text.replace("ﬁ", "fi").replace("\n", " ")}],
        }
    ]
    before = deepcopy(block)
    passages = project_passages(projection, [block], maximum=100)
    assert len(passages) > 10
    covered = set()
    for passage in passages:
        assert estimate_tokens(passage["text"]) <= 100
        for span in passage["spans"]:
            covered.update(range(span["start_offset"], span["end_offset"]))
    assert {i for i, c in enumerate(text) if not c.isspace()} <= covered
    assert block == before
    projection[0]["parts"][0]["text"] = "Invented text"
    with pytest.raises(ValueError):
        project_passages(projection, [block])
