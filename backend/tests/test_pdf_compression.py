import hashlib
import json
import random
import shutil
import subprocess
from io import BytesIO
from zipfile import ZipFile

import pytest
from opennotelm.generated_pages import write_page
from opennotelm.jobs import JobContext
from opennotelm.pdf_export import assemble_pdf
from opennotelm.pdf_images import ENCODING_VERSION, raster_pdf
from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from test_artifact_downloads import saved_deck
from test_sources import wait_for_job


def old_pdf(raw):
    output = BytesIO()
    canvas = Canvas(output, pagesize=(1440, 810), pageCompression=1, invariant=1)
    canvas.drawImage(ImageReader(BytesIO(raw)), 0, 0, width=1440, height=810)
    canvas.showPage()
    canvas.save()
    return output.getvalue()


def samples(page):
    return [
        (obj.get("/Width"), obj.get("/Height"), obj.get("/ColorSpace"), obj.get_data())
        for ref in page["/Resources"]["/XObject"].values()
        if (obj := ref.get_object()).get("/Subtype") == "/Image"
    ]


def image_bytes(mode="RGB", noise=False):
    size = (1280, 720)
    if noise:
        image = Image.frombytes(mode, size, random.Random(42).randbytes(size[0] * size[1] * 3))
    else:
        gradient = Image.frombytes(
            "L", size, bytes((x * 7 + y * 11) % 256 for y in range(size[1]) for x in range(size[0]))
        )
        image = gradient.convert(mode)
        draw = ImageDraw.Draw(image)
        for i in range(60):
            draw.rectangle((i * 19, i * 7, i * 19 + 70, i * 7 + 70), fill=i * 3)
        draw.text((100, 150), "Pixel-exact text 0123456789", fill=0)
    output = BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


@pytest.mark.parametrize(
    "mode,noise", [("RGB", False), ("L", False), ("RGBA", False), ("RGB", True)]
)
def test_lossless_pdf_preserves_every_sample_and_never_expands_image_stream(mode, noise):
    raw = image_bytes(mode, noise)
    original = PdfReader(BytesIO(old_pdf(raw))).pages[0]
    optimized = raster_pdf(BytesIO(raw)).pages[0]
    assert samples(optimized) == samples(original)
    before = next(iter(original["/Resources"]["/XObject"].values())).get_object()
    after = next(iter(optimized["/Resources"]["/XObject"].values())).get_object()
    assert len(after._data) < len(before._data)
    assert after["/Filter"] == "/FlateDecode"
    if noise:
        assert "/DecodeParms" not in after
    elif mode != "L":
        assert after["/DecodeParms"]["/Predictor"] == 15


def test_generated_page_and_final_pdf_preserve_pixels_dimensions_outlines_and_metadata(
    tmp_path, monkeypatch
):
    raw = image_bytes()
    directory = tmp_path / "render"
    assert write_page(raw, directory) == (1280, 720)
    assert (directory / "page.png").read_bytes() == raw
    assert Image.open(directory / "thumbnail.png").size == (384, 216)
    page_pdf = PdfReader(directory / "page.pdf")
    assert list(page_pdf.pages[0].mediabox) == [0, 0, 1440, 810]

    def redundant_encoding(*args):
        raise AssertionError("A saved compressed page must not be encoded again")

    monkeypatch.setattr("opennotelm.pdf_export.raster_pdf", redundant_encoding)
    output = tmp_path / "deck.pdf"
    assemble_pdf(
        "书籍 — 无损",
        [
            {
                "image": directory / "page.png",
                "pdf": directory / "page.pdf",
                "title": "章节一",
                "text_layer": [],
            }
        ],
        output,
    )
    reader = PdfReader(output)
    assert reader.metadata.title == "书籍 — 无损"
    assert reader.metadata.producer == ENCODING_VERSION
    assert reader.outline[0].title == "章节一"
    assert samples(reader.pages[0]) == samples(PdfReader(BytesIO(old_pdf(raw))).pages[0])
    assert output.stat().st_size < len(old_pdf(raw))


@pytest.mark.skipif(
    not shutil.which("pdftoppm"), reason="Poppler is required for pixel verification"
)
def test_independent_pdf_renderer_matches_old_pdf_exactly(tmp_path):
    raw = image_bytes()
    old = tmp_path / "old.pdf"
    old.write_bytes(old_pdf(raw))
    write_page(raw, tmp_path / "render")
    for name, pdf in [("before", old), ("after", tmp_path / "render/page.pdf")]:
        subprocess.run(
            ["pdftoppm", "-r", "96", "-singlefile", "-png", str(pdf), str(tmp_path / name)],
            check=True,
            capture_output=True,
        )
    with Image.open(tmp_path / "before.png") as before, Image.open(tmp_path / "after.png") as after:
        assert before.size == after.size
        assert before.tobytes() == after.tobytes()


def setup_legacy(client, settings):
    client.portal.call(client.app.state.jobs.stop)
    notebook = client.post("/api/notebooks", json={"title": "Compatibility"}).json()["id"]
    identity, path, _ = saved_deck(client, settings, notebook)
    directory = settings.data_dir / "renders"
    directory.mkdir(exist_ok=True)
    raw = image_bytes()
    (directory / "page.png").write_bytes(raw)
    (directory / "page.pdf").write_bytes(old_pdf(raw))
    original = old_pdf(raw)
    path.write_bytes(original)
    with client.app.state.db.connect() as conn:
        conn.execute(
            "UPDATE slides SET spec_json=? WHERE deck_id=?",
            (json.dumps({"content_elements": [{"type": "headline", "text": "Chapter"}]}), identity),
        )
        conn.execute(
            "UPDATE pdf_exports SET file_sha256=?,file_size=? WHERE deck_id=?",
            (hashlib.sha256(original).hexdigest(), len(original), identity),
        )
    return notebook, identity, path, original


def test_legacy_pdf_frozen_until_explicit_reexport_new_and_old_files_stay_valid(
    client, settings, provider
):
    notebook, identity, path, original = setup_legacy(client, settings)
    service = client.app.state.pdf_exports
    before = service.current(identity)
    signature = service.snapshot(identity)[2]
    calls = len(provider[1])
    context = JobContext(client.app.state.jobs, {"id": "unused"})

    async def cached():
        return await service.build(identity, context)

    assert client.portal.call(cached) == before
    assert path.read_bytes() == original
    job = client.post(f"/api/decks/{identity}/export").json()
    client.portal.call(client.app.state.jobs.start)
    assert wait_for_job(client, job["id"])["status"] == "completed"
    after = service.current(identity)
    assert after["id"] != before["id"] and after["file_size"] < before["file_size"]
    assert service.snapshot(identity)[2] == signature
    assert path.read_bytes() == original
    assert client.get(before["download_url"]).content == original
    optimized = client.get(after["download_url"]).content
    assert samples(PdfReader(BytesIO(optimized)).pages[0]) == samples(
        PdfReader(BytesIO(original)).pages[0]
    )
    assert len(provider[1]) == calls
    assert client.get(f"/api/notebooks/{notebook}/decks").json()[0]["download_available"]
    bundle = client.post(
        f"/api/notebooks/{notebook}/artifacts/download",
        json={"items": [{"kind": "deck", "id": identity}]},
    ).json()
    with ZipFile(BytesIO(client.get(bundle["download_url"]).content)) as archive:
        assert archive.read(archive.namelist()[0]) == optimized
    again = client.post(f"/api/decks/{identity}/export").json()
    assert wait_for_job(client, again["id"])["status"] == "completed"
    assert service.current(identity) == after
    with client.app.state.db.connect() as conn:
        conn.execute("UPDATE slides SET revision=revision+1 WHERE deck_id=?", (identity,))
    assert service.current(identity) is None
    assert client.get(before["download_url"]).status_code == 409
    assert client.get(after["download_url"]).status_code == 409


def test_failed_reexport_preserves_previous_download_and_cleans_only_new_file(
    client, settings, monkeypatch
):
    _, identity, path, original = setup_legacy(client, settings)
    service = client.app.state.pdf_exports
    before = service.current(identity)

    def fail(*args):
        raise RuntimeError("Synthetic compressor failure")

    monkeypatch.setattr("opennotelm.pdf_export.assemble_pdf", fail)
    job = client.post(f"/api/decks/{identity}/export").json()
    client.portal.call(client.app.state.jobs.start)
    assert wait_for_job(client, job["id"])["status"] == "failed"
    assert path.read_bytes() == original
    assert service.current(identity) == before
    assert client.get(before["download_url"]).content == original
    # A later normal pipeline recovery must reuse the failed optimized row, not its legacy ID.
    monkeypatch.undo()
    path.write_bytes(b"damaged legacy")
    context = JobContext(client.app.state.jobs, {"id": "unused"})

    async def recovered():
        return await service.build(identity, context)

    after = client.portal.call(recovered)
    assert after["status"] == "ready" and after["id"] != before["id"]
    assert client.get(after["download_url"]).status_code == 200
