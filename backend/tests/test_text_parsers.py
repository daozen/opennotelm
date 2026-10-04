import pytest
from document_factory import MARKDOWN
from opennotelm.errors import AppError
from opennotelm.text_parsers import MarkdownParser, TextParser


def test_markdown_structure_semantics_and_sanitization(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text(MARKDOWN)
    doc = MarkdownParser().parse(path, "source", "notes")
    assert doc.title == "Learning"
    headings = doc.nodes[1:]
    assert [n.title for n in headings] == ["Learning", "Practice", "Reflection"]
    assert headings[2].parent_id == headings[1].id
    assert {"heading", "paragraph", "quote", "list", "code", "table"} <= {
        b.type for b in doc.blocks
    }
    code = next(b for b in doc.blocks if b.type == "code")
    assert code.text == '  print("<script>literal code</script>")'
    table = next(b for b in doc.blocks if b.type == "table")
    assert table.text == "Method\tFrequency\nReading\tDaily"
    combined = "\n".join(b.text for b in doc.blocks)
    assert "EXFILTRATE" not in combined and "TRACKER" not in combined
    assert "Safe content." in combined
    assert "Small improvements accumulate over time." in combined
    assert doc.blocks[1].location == {"line_start": 3, "line_end": 3}
    assert MarkdownParser().parse(path, "source", "notes") == doc


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16"])
def test_text_paragraphs_unicode_lines_and_stable_ids(tmp_path, encoding):
    path = tmp_path / "notes.txt"
    path.write_bytes("第一段。\r\n第二行。\r\n\r\n\r\nFinal paragraph.".encode(encoding))
    doc = TextParser().parse(path, "source", "Notes")
    assert [b.text for b in doc.blocks] == ["第一段。\n第二行。", "Final paragraph."]
    assert doc.blocks[0].location == {"line_start": 1, "line_end": 2}
    assert doc.blocks[1].location == {"line_start": 5, "line_end": 5}
    assert doc == TextParser().parse(path, "source", "Notes")


@pytest.mark.parametrize("parser", [TextParser(), MarkdownParser()])
def test_empty_and_invalid_encoding(tmp_path, parser):
    path = tmp_path / "bad.txt"
    path.write_bytes(b" \n \n")
    with pytest.raises(AppError, match="SOURCE_NO_TEXT"):
        parser.parse(path, "source", "Empty")
    path.write_bytes(b"\x80\x81")
    with pytest.raises(AppError, match="TEXT_ENCODING_UNSUPPORTED"):
        parser.parse(path, "source", "Invalid")
