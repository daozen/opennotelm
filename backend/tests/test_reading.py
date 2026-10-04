from dataclasses import asdict

from document_factory import make_glyph_pdf
from opennotelm.pdf_parser import PdfParser
from opennotelm.reading import characters, join_short_continuations, page_reading, pdf_reading
from pypdf import PdfReader
from test_sources import wait_for_job


def test_multiline_callback_retains_paragraph_boundaries_and_latin_spaces():
    class Page:
        def extract_text(self, visitor_text):
            text = "First line\ncontinues.\n\nSecond paragraph."
            visitor_text(text, [1, 0, 0, 1, 0, 0], [1, 0, 0, 1, 50, 700], None, 12)
            return text

    blocks = [
        {"id": "first", "text": "First line\ncontinues.", "page_start": 1, "type": "paragraph"},
        {"id": "second", "text": "Second paragraph.", "page_start": 1, "type": "paragraph"},
    ]
    output = page_reading(Page(), blocks)
    assert ["".join(p["text"] for p in item["parts"]) for item in output] == [
        "First line continues.",
        "Second paragraph.",
    ]


def test_fragmented_glyphs_reflow_preserves_every_fact_and_page_scope(tmp_path):
    path = tmp_path / "glyphs.pdf"
    path.write_bytes(make_glyph_pdf())
    document = PdfParser().parse(path, "source", "glyphs")
    blocks = [asdict(block) for block in document.blocks]
    before = [dict(block) for block in blocks]
    output = pdf_reading(path, blocks, blocks)
    assert sum(len(b["text"]) == 1 for b in blocks) > 100
    assert len(output) < 12
    text = "".join(p["text"] for item in output for p in item["parts"])
    assert "这是按字绘制的中文资料，阅读时应该恢复完整段落。" in text
    assert "Clear explanations preserve source evidence." in text
    assert characters(text) == "".join(characters(b["text"]) for b in blocks)
    assert blocks == before
    assert {p["block_id"] for item in output for p in item["parts"]} == {b["id"] for b in blocks}
    assert any(item["type"] == "heading" for item in output)
    selected = [b for b in blocks if b["page_start"] == 2]
    page = pdf_reading(path, blocks, selected)
    assert {item["page_start"] for item in page} == {2}
    assert {p["block_id"] for item in page for p in item["parts"]} == {b["id"] for b in selected}
    # A changed extraction cannot fabricate anchor relationships.
    selected[0] = {**selected[0], "text": "Different fact text"}
    result = page_reading(PdfReader(path).pages[1], selected)
    assert result[0]["parts"][0]["text"] == "Different fact text"


def test_reading_api_does_not_reparse_or_change_citation_facts(client):
    notebook = client.post("/api/notebooks", json={"title": "Reading regression"}).json()
    result = client.post(
        f"/api/notebooks/{notebook['id']}/sources/upload",
        files={"file": ("glyphs.pdf", make_glyph_pdf())},
    ).json()
    assert wait_for_job(client, result["job"]["id"])["status"] == "completed"
    source = result["source"]["id"]
    blocks = client.get(f"/api/sources/{source}/blocks").json()
    nodes = client.get(f"/api/sources/{source}/nodes").json()
    target = next(b for b in blocks if b["page_start"] == 2 and b["text"] == "阅")
    spans = [{"block_id": target["id"], "source_id": source, "start_offset": 0, "end_offset": 1}]
    before = client.app.state.citations.preview_spans(spans)
    node = next(n for n in nodes if n["type"] == "page" and n["start_page"] == 2)
    reading = client.get(f"/api/sources/{source}/reading?node_id={node['id']}")
    assert reading.status_code == 200
    assert len(reading.json()) < 6
    assert target["id"] in {p["block_id"] for item in reading.json() for p in item["parts"]}
    assert client.app.state.citations.preview_spans(spans) == before
    assert client.get(f"/api/sources/{source}/blocks").json() == blocks
    assert client.get(f"/api/sources/{source}/nodes").json() == nodes
    assert client.get(f"/api/sources/{source}/reading?node_id=missing").status_code == 404
    assert client.get("/api/sources/missing/reading").status_code == 404


def test_short_wrapped_sentence_tail_stays_with_paragraph_without_crossing_pages_or_list_items():
    def paragraph(text, page=1, kind="paragraph"):
        return {"type": kind, "page_start": page, "parts": [{"block_id": text, "text": text}]}

    original = [
        paragraph("b. 装饰：支持设置下发后的有效"),
        paragraph("期；"),
        paragraph("c. 货币类：钻石/银币；"),
        paragraph("独立完整句。"),
        paragraph("最后一行仍未结束"),
        paragraph("跨页尾句。", page=2),
        paragraph("这是一个未结束的引导"),
        paragraph("2. 新条目。"),
        paragraph("下一章节", kind="heading"),
    ]
    result = join_short_continuations(original)
    assert "".join(p["text"] for p in result[0]["parts"]) == "b. 装饰：支持设置下发后的有效期；"
    assert len(result) == len(original) - 1
    assert original[0]["parts"][0]["text"].endswith("有效")
    assert {p["block_id"] for item in result for p in item["parts"]} == {
        p["block_id"] for item in original for p in item["parts"]
    }
