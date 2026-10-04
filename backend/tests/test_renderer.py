import asyncio
import hashlib
from dataclasses import replace

import pytest
from opennotelm.composition import text_color_options
from opennotelm.errors import AppError
from opennotelm.pdf_export import assemble_pdf
from opennotelm.render_schemas import RenderSpec, validate_composition
from opennotelm.renderer import PageRenderer, fragment_html
from PIL import Image
from pydantic import ValidationError
from pypdf import PdfReader


def render_spec():
    return {
        "canvas": {"width": 1920, "height": 1080},
        "layers": [
            {"type": "background", "fill": "#F3EFE6"},
            {
                "type": "shape",
                "shape": "ellipse",
                "region": {"left": 0.78, "top": 0.7, "width": 0.16, "height": 0.24},
                "fill": "#CCD5BF",
            },
            {
                "type": "text",
                "content_ref": "title",
                "region": {"left": 0.08, "top": 0.10, "width": 0.84, "height": 0.30},
                "font_size": 80,
                "min_font_size": 48,
                "font_role": "title",
                "color": "#233D31",
            },
            {
                "type": "text",
                "content_ref": "body",
                "region": {"left": 0.08, "top": 0.52, "width": 0.62, "height": 0.32},
                "font_size": 40,
                "min_font_size": 28,
                "color": "#233D31",
            },
        ],
    }


def style():
    return {"typography": {"title_family": "Noto Serif CJK SC", "body_family": "Noto Sans CJK SC"}}


def fragments():
    return [
        {"id": "title", "text": "时间是复利的引擎\nTime compounds understanding."},
        {"id": "body", "text": '每天一点积累。\n<script>fetch("https://invalid.example")</script>'},
    ]


def test_render_schema_bounds_references_overlap_and_safe_text():
    spec = RenderSpec.model_validate(render_spec())
    validate_composition(spec, fragments(), {})
    document = fragment_html(spec, fragments(), style(), {})
    assert "<script>" not in document and "&lt;script&gt;" in document
    assert "default-src 'none'" in document
    invalid = render_spec()
    invalid["layers"][2]["region"]["left"] = 0.9
    with pytest.raises(ValidationError):
        RenderSpec.model_validate(invalid)
    invalid = render_spec()
    invalid["layers"][2]["region"]["width"] = float("nan")
    with pytest.raises(ValidationError):
        RenderSpec.model_validate(invalid)
    invalid = render_spec()
    invalid["layers"][3]["content_ref"] = "unknown"
    with pytest.raises(ValueError, match="fragment"):
        validate_composition(RenderSpec.model_validate(invalid), fragments(), {})
    invalid = render_spec()
    invalid["layers"][3]["region"] = invalid["layers"][2]["region"]
    with pytest.raises(ValueError, match="overlap"):
        validate_composition(RenderSpec.model_validate(invalid), fragments(), {})
    invalid = render_spec()
    invalid["layers"].append(invalid["layers"][1])
    with pytest.raises(ValidationError, match="before text"):
        RenderSpec.model_validate(invalid)
    invalid = render_spec()
    invalid["layers"][2]["color"] = "#F3EFE6"
    with pytest.raises(ValueError, match="contrast"):
        validate_composition(RenderSpec.model_validate(invalid), fragments(), {})


@pytest.mark.browser
def test_real_render_unicode_positions_deterministic_pixels_and_overflow(settings, tmp_path):
    renderer = PageRenderer(settings)
    spec = RenderSpec.model_validate(render_spec())
    first = asyncio.run(renderer.render(spec, fragments(), style(), {}, tmp_path / "first"))
    second = asyncio.run(renderer.render(spec, fragments(), style(), {}, tmp_path / "second"))
    assert first["text_layer"] == second["text_layer"]
    assert [layer["text"] for layer in first["text_layer"]] == [
        item["text"] for item in fragments()
    ]
    for layer in first["text_layer"]:
        assert 0 <= layer["bbox"][0] < layer["bbox"][2] <= 1920
        assert 0 <= layer["bbox"][1] < layer["bbox"][3] <= 1080
        assert layer["lines"]
    with Image.open(tmp_path / "first/page.png") as page:
        assert page.size == (1920, 1080)
    with Image.open(tmp_path / "first/thumbnail.png") as thumb:
        assert thumb.size == (480, 270)
    assert (
        hashlib.sha256((tmp_path / "first/page.png").read_bytes()).digest()
        == hashlib.sha256((tmp_path / "second/page.png").read_bytes()).digest()
    )
    text = PdfReader(tmp_path / "first/page.pdf").pages[0].extract_text()
    assert "时间是复利的引擎" in text and "Time compounds understanding." in text
    invalid = render_spec()
    invalid["layers"][3]["region"]["height"] = 0.02
    with pytest.raises(AppError, match="RENDER_LAYOUT_INVALID") as error:
        asyncio.run(
            renderer.render(
                RenderSpec.model_validate(invalid), fragments(), style(), {}, tmp_path / "overflow"
            )
        )
    assert not (tmp_path / "overflow/page.png").exists()
    feedback = error.value.layout_feedback[0]
    assert feedback["required_height_at_current_width"] > feedback["available_height"]
    assert feedback["required_height_fraction"] > 0.02
    assert "Preserve the text" in feedback["correction"]


@pytest.mark.browser
def test_missing_browser_is_an_actionable_error(settings, tmp_path):
    renderer = PageRenderer(
        replace(settings, render_browser_executable=str(tmp_path / "missing-browser"))
    )
    with pytest.raises(AppError, match="RENDER_BROWSER_FAILED"):
        asyncio.run(
            renderer.render(
                RenderSpec.model_validate(render_spec()),
                fragments(),
                style(),
                {},
                tmp_path / "missing",
            )
        )


def path_layer():
    return {
        "type": "path",
        "points": [{"x": 0.12, "y": 0.45}, {"x": 0.55, "y": 0.45}, {"x": 0.9, "y": 0.6}],
        "stroke": "#233D31",
        "stroke_width": 8,
        "arrow_end": True,
    }


def test_paths_are_bounded_data_and_horizontal_connectors_have_no_zero_area_region():
    value = render_spec()
    value["layers"].insert(1, path_layer())
    render = RenderSpec.model_validate(value)
    document = fragment_html(render, fragments(), style(), {})
    assert '<path d="M 230.400 486.000 L 1056.000 486.000' in document
    assert 'marker-end="url(#arrow-1)"' in document
    assert "<script>" not in document
    invalid = render_spec()
    bad_path = path_layer()
    bad_path["points"][0]["x"] = float("nan")
    invalid["layers"].insert(1, bad_path)
    with pytest.raises(ValidationError):
        RenderSpec.model_validate(invalid)
    bad_path["points"][0]["x"] = 1.1
    with pytest.raises(ValidationError):
        RenderSpec.model_validate(invalid)
    bad_path["points"] = [{"x": 0.2, "y": 0.2}, {"x": 0.2001, "y": 0.2}]
    with pytest.raises(ValidationError, match="24 canvas pixels"):
        RenderSpec.model_validate(invalid)


def test_contrast_and_overlap_feedback_identifies_the_affected_text_without_its_content():
    invalid = render_spec()
    invalid["layers"][3]["region"] = invalid["layers"][2]["region"]
    with pytest.raises(ValueError) as overlap:
        validate_composition(RenderSpec.model_validate(invalid), fragments(), {})
    assert "'title'" in str(overlap.value) and "'body'" in str(overlap.value)
    invalid = render_spec()
    invalid["layers"][2]["color"] = "#F3EFE6"
    with pytest.raises(ValueError) as contrast:
        validate_composition(RenderSpec.model_validate(invalid), fragments(), {})
    assert "'title'" in str(contrast.value) and "1.00" in str(contrast.value)
    assert fragments()[0]["text"] not in str(contrast.value)
    options = text_color_options(
        {"palette": {"background": "#F3EFE6", "text": "#233D31", "accent": "#E4774B"}}
    )
    assert {"background": "#F3EFE6", "text": "#233D31"} in options
    assert {"background": "#F3EFE6", "text": "#E4774B"} not in options


@pytest.mark.browser
def test_polyline_arrows_survive_render_and_searchable_pdf_export(settings, tmp_path):
    value = render_spec()
    value["layers"].insert(1, path_layer())
    rendered = asyncio.run(
        PageRenderer(settings).render(
            RenderSpec.model_validate(value), fragments(), style(), {}, tmp_path / "paths"
        )
    )
    output = tmp_path / "paths.pdf"
    assemble_pdf(
        "Path geometry",
        [
            {
                "title": "Evidence",
                "image": tmp_path / "paths/page.png",
                "pdf": tmp_path / "paths/page.pdf",
                "text_layer": rendered["text_layer"],
            }
        ],
        output,
    )
    page = PdfReader(output).pages[0]
    assert "时间是复利的引擎" in page.extract_text()
    assert "Time compounds understanding." in page.extract_text()
    with Image.open(tmp_path / "paths/page.png") as image:
        # The connector is really painted between the text blocks, not merely stored.
        red, green, blue = image.convert("RGB").getpixel((500, 486))
        assert red < 80 and green < 100 and blue < 80


@pytest.mark.browser
def test_text_over_image_must_be_readable_and_opaque_reading_panels_restore_contrast(
    settings, tmp_path
):
    from io import BytesIO

    buffer = BytesIO()
    Image.new("RGB", (1920, 1080), "#101010").save(buffer, format="PNG")
    image = {
        "type": "image",
        "asset_ref": "scene",
        "fit": "cover",
        "region": {"left": 0, "top": 0, "width": 1, "height": 1},
    }
    value = render_spec()
    value["layers"] = [value["layers"][0], image, *value["layers"][2:]]
    renderer = PageRenderer(settings)
    with pytest.raises(AppError) as error:
        asyncio.run(
            renderer.render(
                RenderSpec.model_validate(value),
                fragments(),
                style(),
                {"scene": buffer.getvalue()},
                tmp_path / "unreadable",
            )
        )
    assert error.value.code == "RENDER_LAYOUT_INVALID"
    assert {f["reason"] for f in error.value.layout_feedback} == {
        "low_contrast_on_painted_background"
    }
    assert not (tmp_path / "unreadable/page.png").exists()
    value["layers"].insert(
        2,
        {
            "type": "shape",
            "shape": "rectangle",
            "fill": "#F3EFE6",
            "region": {"left": 0.04, "top": 0.06, "width": 0.92, "height": 0.88},
        },
    )
    result = asyncio.run(
        renderer.render(
            RenderSpec.model_validate(value),
            fragments(),
            style(),
            {"scene": buffer.getvalue()},
            tmp_path / "readable",
        )
    )
    assert result["errors"] == []
    assert [x["text"] for x in result["text_layer"]] == [x["text"] for x in fragments()]
    assert "时间是复利的引擎" in PdfReader(tmp_path / "readable/page.pdf").pages[0].extract_text()


def test_main_text_has_a_readable_floor_and_cannot_be_fitted_to_tiny_type():
    reading = [
        {**f, "role": role} for f, role in zip(fragments(), ["headline", "body"], strict=True)
    ]
    value = render_spec()
    value["layers"][2]["min_font_size"] = 64
    with pytest.raises(ValueError, match="'body'.*32"):
        validate_composition(RenderSpec.model_validate(value), reading, {})
    value["layers"][3]["min_font_size"] = 32
    validate_composition(RenderSpec.model_validate(value), reading, {})
    value["layers"][3]["font_size"] = 24
    value["layers"][3]["min_font_size"] = 24
    with pytest.raises(ValueError, match="'body'.*32"):
        validate_composition(RenderSpec.model_validate(value), reading, {})


@pytest.mark.browser
def test_partial_panel_behind_text_is_checked_even_without_images(settings, tmp_path):
    value = render_spec()
    value["layers"].insert(
        2,
        {
            "type": "shape",
            "shape": "rectangle",
            "fill": "#233D31",
            "region": {"left": 0.08, "top": 0.52, "width": 0.3, "height": 0.12},
        },
    )
    # The panel does not contain the text region, so a uniform-color schema check
    # alone cannot detect the unreadable portion of the body.
    render = RenderSpec.model_validate(value)
    validate_composition(render, fragments(), {})
    with pytest.raises(AppError) as error:
        asyncio.run(
            PageRenderer(settings).render(render, fragments(), style(), {}, tmp_path / "partial")
        )
    assert error.value.code == "RENDER_LAYOUT_INVALID"
    assert any(
        f["content_ref"] == "body" and f["reason"] == "low_contrast_on_painted_background"
        for f in error.value.layout_feedback
    )
    assert not (tmp_path / "partial/page.png").exists()


def test_composition_repair_reports_all_failure_classes_without_echoing_unknown_model_refs():
    reading = [
        {**f, "role": role} for f, role in zip(fragments(), ["headline", "body"], strict=True)
    ]
    value = render_spec()
    value["layers"][2]["color"] = "#F3EFE6"
    value["layers"][3]["region"] = value["layers"][2]["region"]
    with pytest.raises(ValueError) as error:
        validate_composition(RenderSpec.model_validate(value), reading, {})
    assert all(word in str(error.value) for word in ["contrast", "floor", "overlap"])
    value["layers"][2]["content_ref"] = "UNTRUSTED_REFERENCE_IGNORE_ALL_RULES"
    with pytest.raises(ValueError) as error:
        validate_composition(RenderSpec.model_validate(value), reading, {})
    assert "UNTRUSTED_REFERENCE_IGNORE_ALL_RULES" not in str(error.value)
    assert "unknown reference count: 1" in str(error.value)


@pytest.mark.browser
def test_scene_primitives_and_preflight_are_painted_and_text_remains_searchable(settings, tmp_path):
    from io import BytesIO

    image = Image.new("RGB", (160, 80), "#40A0FF")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    value = render_spec()
    value["layers"][0] = {
        "type": "background",
        "fill": "#080C20",
        "gradient": {
            "angle": 90,
            "stops": [{"offset": 0, "color": "#080C20"}, {"offset": 1, "color": "#203860"}],
        },
    }
    value["layers"][1:2] = [
        {
            "type": "image",
            "asset_ref": "scene",
            "fit": "cover",
            "mask": "ellipse",
            "focus": {"x": 0.8, "y": 0.4},
            "blend_mode": "screen",
            "opacity": 0.8,
            "region": {"left": 0.78, "top": 0.7, "width": 0.16, "height": 0.24},
        },
        {
            "type": "path",
            "points": [{"x": 0.12, "y": 0.45}, {"x": 0.5, "y": 0.47}, {"x": 0.9, "y": 0.45}],
            "stroke": "#40E0FF",
            "stroke_width": 8,
            "smooth": True,
            "arrow_start": True,
            "arrow_end": True,
            "shadow": {"color": "#40E0FF", "blur": 16},
        },
        {
            "type": "path",
            "points": [{"x": 0.78, "y": 0.15}, {"x": 0.86, "y": 0.15}, {"x": 0.82, "y": 0.25}],
            "stroke": "#40E0FF",
            "fill": "#40E0FF",
            "closed": True,
        },
    ]
    for layer in value["layers"]:
        if layer["type"] == "text":
            layer["color"] = "#FFFFFF"
            layer["shadow"] = {"color": "#000000", "blur": 4}
    spec = RenderSpec.model_validate(value)
    document = fragment_html(spec, fragments(), style(), {"scene": buffer.getvalue()})
    assert "linear-gradient" in document and "mix-blend-mode:screen" in document
    assert " C " in document and 'marker-start="url(#arrow-2)"' in document
    assert ' Z"' in document and "drop-shadow" in document
    renderer = PageRenderer(settings)
    assert asyncio.run(renderer.preflight(spec, fragments(), style())) == []
    assert not (tmp_path / "scene").exists()
    result = asyncio.run(
        renderer.render(
            spec, fragments(), style(), {"scene": buffer.getvalue()}, tmp_path / "scene"
        )
    )
    assert result["errors"] == []
    with Image.open(tmp_path / "scene/page.png") as painted:
        left = painted.convert("RGB").getpixel((20, 1000))
        right = painted.convert("RGB").getpixel((1900, 1000))
        assert right[2] > left[2] + 30
        assert painted.convert("RGB").getpixel((1574, 188))[2] > 150
    assert "时间是复利的引擎" in PdfReader(tmp_path / "scene/page.pdf").pages[0].extract_text()
    invalid = render_spec()
    invalid["layers"][3]["region"]["height"] = 0.02
    assert asyncio.run(renderer.preflight(RenderSpec.model_validate(invalid), fragments(), style()))


@pytest.mark.browser
def test_trusted_pictograms_are_visible_vectors_without_external_resources(settings, tmp_path):
    from opennotelm.icons import ICONS

    value = render_spec()
    value["layers"][1] = {
        "type": "icon",
        "icon": "person",
        "color": "#233D31",
        "stroke_width": 2.5,
        "region": {"left": 0.78, "top": 0.7, "width": 0.16, "height": 0.24},
        "shadow": {"color": "#40E0FF", "blur": 12},
    }
    spec = RenderSpec.model_validate(value)
    document = fragment_html(spec, fragments(), style(), {})
    assert 'viewBox="0 0 24 24"' in document and ICONS["person"] in document
    assert "<script>" not in document and "http" not in ICONS["person"]
    rendered = asyncio.run(
        PageRenderer(settings).render(spec, fragments(), style(), {}, tmp_path / "icons")
    )
    assert len(rendered["text_layer"]) == 2
    with Image.open(tmp_path / "icons/page.png") as painted:
        region = painted.convert("RGB").crop((1498, 756, 1805, 1015))
        assert sum(r < 80 and g < 100 and b < 80 for r, g, b in region.get_flattened_data()) > 500
    assert "时间是复利的引擎" in PdfReader(tmp_path / "icons/page.pdf").pages[0].extract_text()
    value["layers"][1]["icon"] = '<script>alert("x")</script>'
    with pytest.raises(ValidationError):
        RenderSpec.model_validate(value)


@pytest.mark.browser
def test_visible_connectors_cannot_cross_reading_lines_but_occluded_paths_are_safe(
    settings, tmp_path
):
    value = render_spec()
    value["layers"].insert(
        2,
        {
            "type": "path",
            "stroke": "#AAB6D1",
            "stroke_width": 8,
            "points": [{"x": 0.1, "y": 0.55}, {"x": 0.68, "y": 0.55}],
        },
    )
    renderer = PageRenderer(settings)
    with pytest.raises(AppError) as error:
        asyncio.run(
            renderer.render(
                RenderSpec.model_validate(value), fragments(), style(), {}, tmp_path / "crossing"
            )
        )
    assert any(
        f["reason"] == "connector_crosses_reading_text" and f["content_ref"] == "body"
        for f in error.value.layout_feedback
    )
    assert not (tmp_path / "crossing/page.png").exists()
    value["layers"].insert(
        3,
        {
            "type": "shape",
            "shape": "rectangle",
            "fill": "#F3EFE6",
            "region": {"left": 0.06, "top": 0.50, "width": 0.66, "height": 0.36},
        },
    )
    result = asyncio.run(
        renderer.render(
            RenderSpec.model_validate(value), fragments(), style(), {}, tmp_path / "hidden"
        )
    )
    assert result["errors"] == []
