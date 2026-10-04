from io import BytesIO

import pytest
from document_factory import make_pdf
from opennotelm.errors import AppError
from opennotelm.pdf_parser import PdfParser
from pypdf import PdfReader, PdfWriter


def test_pdf_native_outline_text_and_page_locations(tmp_path):
    path = tmp_path / "book.pdf"
    path.write_bytes(make_pdf())
    doc = PdfParser().parse(path, "source", "book")
    assert doc.title == "Patient learning"
    chapters = [n for n in doc.nodes if n.type == "chapter"]
    assert [n.title for n in chapters] == ["1. Time", "2. Practice"]
    assert [(n.start_page, n.end_page) for n in chapters] == [(1, 1), (2, 2)]
    pages = [n for n in doc.nodes if n.type == "page"]
    assert [n.parent_id for n in pages] == [n.id for n in chapters]
    assert {b.page_start for b in doc.blocks} == {1, 2}
    assert all(b.location["page"] == b.page_start == b.page_end for b in doc.blocks)
    assert any("Page 2: Small improvements" in b.text for b in doc.blocks)
    assert doc == PdfParser().parse(path, "source", "book")


def test_pdf_font_heading_fallback_and_partial_blank_warning(tmp_path):
    writer = PdfWriter()
    reader = PdfReader(BytesIO(make_pdf()))
    for page in reader.pages:
        writer.add_page(page)
    writer.add_blank_page(width=612, height=792)
    path = tmp_path / "no-outline.pdf"
    writer.write(path)
    doc = PdfParser().parse(path, "source", "Fallback")
    assert not any(n.type == "chapter" for n in doc.nodes)
    assert [n.title for n in doc.nodes if n.type == "heading"] == ["1. Time", "2. Practice"]
    assert doc.metadata["warnings"] == ["No extractable text on pages: 3. OCR is not supported."]


def test_pdf_scanned_encrypted_corrupt_and_page_limit(tmp_path):
    path = tmp_path / "book.pdf"
    path.write_bytes(make_pdf(blank=True))
    with pytest.raises(AppError) as error:
        PdfParser().parse(path, "source", "Scanned")
    assert error.value.code == "PDF_NO_TEXT_LAYER"
    path.write_bytes(make_pdf())
    with pytest.raises(AppError) as error:
        PdfParser(max_pages=1).parse(path, "source", "Long")
    assert error.value.code == "PDF_PAGE_LIMIT"
    writer = PdfWriter(clone_from=BytesIO(make_pdf()))
    writer.encrypt("secret")
    writer.write(path)
    with pytest.raises(AppError) as error:
        PdfParser().parse(path, "source", "Encrypted")
    assert error.value.code == "PDF_ENCRYPTED"
    path.write_bytes(b"not a PDF: SECRET_CONTENT")
    with pytest.raises(AppError) as error:
        PdfParser().parse(path, "source", "Corrupt")
    assert error.value.code == "PDF_PARSE_FAILED"
    assert "SECRET_CONTENT" not in str(error.value)
