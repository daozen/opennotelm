import asyncio
import hashlib
import json
import shutil
import subprocess
from io import BytesIO
from pathlib import Path

import pytest
from opennotelm.errors import AppError
from opennotelm.pdf_export import assemble_pdf, compact
from opennotelm.pdf_text import no_space
from opennotelm.render_schemas import RenderSpec
from opennotelm.renderer import PageRenderer
from PIL import Image, ImageChops, ImageStat
from pypdf import PdfReader
from restart_support import restart
from test_decks import create_deck, notebook_with_source
from test_decks import decks as deck_fixture
from test_renderer import fragments, render_spec, style
from test_sources import wait_for_job


@pytest.fixture
def decks(settings):
    yield from deck_fixture.__wrapped__(settings)


@pytest.fixture
def render_output(settings, tmp_path):
    directory = tmp_path / "render"
    measurement = asyncio.run(
        PageRenderer(settings).render(
            RenderSpec.model_validate(render_spec()), fragments(), style(), {}, directory
        )
    )
    return {
        "image": directory / "page.png",
        "pdf": directory / "page.pdf",
        "title": "时间与学习 · Time",
        "text_layer": measurement["text_layer"],
    }


@pytest.mark.browser
@pytest.mark.parametrize("count", [10, 15, 20])
def test_pdf_has_exact_pages_original_unicode_invisible_text_and_full_page_images(
    render_output, tmp_path, count
):
    output = tmp_path / "deck.pdf"
    assemble_pdf("时间与学习", [render_output] * count, output)
    reader = PdfReader(output)
    assert len(reader.pages) == count and len(reader.outline) == count
    assert reader.metadata.title == "时间与学习"
    expected_text = no_space("".join(item["text"] for item in render_output["text_layer"]))

    def positions(page):
        values = []

        def visit(text, matrix, text_matrix, font, size):
            if text.strip():
                values.append((compact(text), matrix, text_matrix, size))

        page.extract_text(visitor_text=visit)
        return values

    original_positions = positions(PdfReader(render_output["pdf"]).pages[0])
    for page in reader.pages:
        assert no_space(page.extract_text()) == expected_text
        assert positions(page) == original_positions
        assert "时间是复利的引擎" in page.extract_text()
        assert "Time compounds understanding." in page.extract_text()
        assert list(page.mediabox) == [0, 0, 1440, 810]
        images = [img for img in page.images if img.image.size == (1920, 1080)]
        assert len(images) == 1
        operators = page.get_contents().operations
        assert all(operands == [3] for operands, op in operators if op == b"Tr")
        assert any(op == b"Tr" for _, op in operators)


@pytest.mark.browser
def test_pdf_rejects_missing_text_instead_of_publishing_broken_search(render_output, tmp_path):
    render_output["text_layer"].append({"text": "Missing content sentinel"})
    with pytest.raises(AppError, match="PDF_TEXT_INCOMPLETE"):
        assemble_pdf("Invalid", [render_output], tmp_path / "invalid.pdf")


def install_render_outputs(client, deck, settings, render_output):
    directory = settings.data_dir / "renders" / "export-fixture"
    directory.mkdir()
    for name, key in [("page.png", "image"), ("page.pdf", "pdf")]:
        (directory / name).write_bytes(Path(render_output[key]).read_bytes())
    with client.app.state.db.connect() as conn:
        for slide in deck["slides"]:
            render_id = "render-" + slide["id"]
            conn.execute(
                "INSERT INTO slide_renders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    render_id,
                    slide["id"],
                    "hash-" + slide["id"],
                    "{}",
                    "renders/export-fixture/page.png",
                    "renders/export-fixture/page.png",
                    "renders/export-fixture/page.pdf",
                    1920,
                    1080,
                    json.dumps(render_output["text_layer"]),
                    "test",
                    "test",
                    "now",
                ),
            )
            conn.execute(
                "UPDATE slides SET status='rendered',current_render_id=?,"
                "current_render_revision=revision WHERE id=?",
                (render_id, slide["id"]),
            )


@pytest.mark.browser
def test_export_persistence_cache_damage_retry_and_stale_invalidation(
    decks, settings, render_output
):
    client, state, _ = decks
    notebook, _ = notebook_with_source(client)
    deck, _ = create_deck(client, notebook)
    assert client.post(f"/api/decks/{deck['id']}/export").status_code == 409
    install_render_outputs(client, deck, settings, render_output)
    client.app.state.decks.exports = client.app.state.pdf_exports
    before = len(state["calls"])
    job = client.post(f"/api/decks/{deck['id']}/export").json()
    assert wait_for_job(client, job["id"])["status"] == "completed"
    result = client.get(f"/api/decks/{deck['id']}").json()
    assert result["status"] == "ready" and result["pdf_export"]["page_count"] == 10
    downloaded = client.get(result["pdf_export"]["download_url"])
    assert downloaded.headers["content-type"] == "application/pdf"
    assert len(PdfReader(BytesIO(downloaded.content)).pages) == 10

    with restart(client, settings, transport=decks[2]) as restarted:
        restored = restarted.get(f"/api/decks/{deck['id']}").json()
        assert restored["pdf_export"] == result["pdf_export"]
        assert restarted.get(restored["pdf_export"]["download_url"]).content == downloaded.content
    path = client.app.state.pdf_exports.file(result["pdf_export"]["id"])
    original_time = path.stat().st_mtime_ns
    again = client.post(f"/api/decks/{deck['id']}/export").json()
    assert wait_for_job(client, again["id"])["status"] == "completed"
    assert path.stat().st_mtime_ns == original_time
    assert len(state["calls"]) == before
    path.write_bytes(b"corrupt export")
    assert client.get(result["pdf_export"]["download_url"]).status_code == 409
    retry = client.post(f"/api/decks/{deck['id']}/export").json()
    assert wait_for_job(client, retry["id"])["status"] == "completed"
    with client.app.state.db.connect() as conn:
        row = conn.execute(
            "SELECT file_sha256 FROM pdf_exports WHERE id=?", (result["pdf_export"]["id"],)
        ).fetchone()
        assert row[0] == hashlib.sha256(path.read_bytes()).hexdigest()
        conn.execute("UPDATE slides SET revision=revision+1 WHERE id=?", (deck["slides"][0]["id"],))
    assert client.get(f"/api/decks/{deck['id']}").json()["pdf_export"] is None
    assert client.get(result["pdf_export"]["download_url"]).status_code == 409


@pytest.mark.browser
def test_text_inside_encoded_form_remains_searchable_and_invisible(render_output, tmp_path):
    from reportlab.pdfgen.canvas import Canvas

    native = tmp_path / "form.pdf"
    canvas = Canvas(str(native), pagesize=(1440, 810), pageCompression=1)
    canvas.beginForm("text-form")
    canvas.setFont("Helvetica", 32)
    canvas.drawString(100, 600, "Text inside an encoded form")
    canvas.endForm()
    canvas.doForm("text-form")
    canvas.showPage()
    canvas.save()
    fixture = {
        **render_output,
        "pdf": native,
        "text_layer": [{"text": "Text inside an encoded form"}],
    }
    final = tmp_path / "form-final.pdf"
    assemble_pdf("Form", [fixture], final)
    page = PdfReader(final).pages[0]
    assert "Text inside an encoded form" in page.extract_text()
    form = next(
        value.get_object()
        for value in page["/Resources"]["/XObject"].values()
        if value.get_object()["/Subtype"] == "/Form"
    )
    assert b"3 Tr" in form.get_data()


@pytest.mark.browser
@pytest.mark.skipif(
    not shutil.which("pdftoppm"), reason="Poppler is required for pixel verification"
)
def test_pdf_raster_matches_the_original_page_preview(render_output, tmp_path):
    output = tmp_path / "visual-check.pdf"
    assemble_pdf("Visual check", [render_output], output)
    subprocess.run(
        ["pdftoppm", "-r", "96", "-singlefile", "-png", str(output), str(tmp_path / "check")],
        check=True,
        capture_output=True,
    )
    with (
        Image.open(tmp_path / "check.png") as actual,
        Image.open(render_output["image"]) as expected,
    ):
        assert actual.size == expected.size == (1920, 1080)
        difference = ImageChops.difference(actual.convert("RGB"), expected.convert("RGB"))
        assert sum(ImageStat.Stat(difference).mean) / 3 < 1


@pytest.mark.browser
@pytest.mark.parametrize("glyph,source", [("⻚", "页⻚"), ("ﬁ", "fiﬁ"), ("ﬃ", "ffiffi")])
def test_shared_font_glyph_keeps_exact_source_unicode(render_output, tmp_path, glyph, source):
    from opennotelm.pdf_text import encoded_mapping
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    native = PdfWriter()
    page = native.add_blank_page(1440, 810)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/ToUnicode"): native._add_object(encoded_mapping({b"A": glyph}, 1)),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): native._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 40 Tf 100 600 Td (AA) Tj ET")
    page.replace_contents(stream)
    original = tmp_path / "shared-glyph.pdf"
    native.write(original)
    assert PdfReader(original).pages[0].extract_text() == glyph * 2
    output = tmp_path / "shared-glyph-fixed.pdf"
    assemble_pdf(
        "Unicode", [{**render_output, "pdf": original, "text_layer": [{"text": source}]}], output
    )
    fixed = PdfReader(output).pages[0]
    assert fixed.extract_text() == source
    maps = [
        value.get_object()["/ToUnicode"].get_data()
        for value in fixed["/Resources"]["/Font"].values()
        if "/ToUnicode" in value.get_object()
    ]
    assert any(glyph.encode("utf-16-be").hex().encode() in value for value in maps)
    assert len(maps) > 1
