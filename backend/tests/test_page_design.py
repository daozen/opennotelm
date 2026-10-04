import json

import pytest
from opennotelm.deck_schemas import SlideSpec
from opennotelm.errors import AppError
from opennotelm.page_design import asset_frame
from opennotelm.render_schemas import RenderSpec, validate_relationships
from test_decks import create_deck, notebook_with_source
from test_decks import decks as deck_fixture


@pytest.fixture
def decks(settings):
    yield from deck_fixture.__wrapped__(settings)


def test_artwork_reading_zones_use_local_coordinates_without_disclosing_copy():
    design = RenderSpec.model_validate(
        {
            "layers": [
                {"type": "background", "fill": "#FFFFFF"},
                {
                    "type": "image",
                    "asset_ref": "scene",
                    "region": {"left": 0.1, "top": 0.2, "width": 0.7, "height": 0.7},
                },
                {
                    "type": "path",
                    "stroke": "#000000",
                    "arrow_end": True,
                    "points": [{"x": 0.15, "y": 0.7}, {"x": 0.7, "y": 0.7}],
                },
                {
                    "type": "icon",
                    "icon": "phone",
                    "color": "#000000",
                    "region": {"left": 0.6, "top": 0.7, "width": 0.1, "height": 0.1},
                },
                {
                    "type": "text",
                    "content_ref": "body",
                    "region": {"left": 0.2, "top": 0.3, "width": 0.3, "height": 0.1},
                    "font_size": 40,
                    "color": "#000000",
                },
                {
                    "type": "text",
                    "content_ref": "title",
                    "region": {"left": 0.1, "top": 0.02, "width": 0.7, "height": 0.1},
                    "font_size": 80,
                    "color": "#000000",
                },
            ]
        }
    )
    frame = asset_frame(design, "scene")
    assert frame["aspect_ratio"] == 1.7778
    assert frame["quiet_zones"] == [
        {"left": 0.1429, "top": 0.1429, "width": 0.4286, "height": 0.1429, "text_color": "#000000"}
    ]
    assert "body" not in json.dumps(frame) and "title" not in json.dumps(frame)
    assert frame["native_overlays"][0]["points"] == [
        {"x": 0.0714, "y": 0.7143},
        {"x": 0.8571, "y": 0.7143},
    ]
    assert frame["native_overlays"][0]["arrow_end"] is True
    assert frame["native_overlays"][1]["symbol"] == "phone"
    assert frame["native_overlays"][1]["region"]["left"] == 0.7143
    assert asset_frame(design, "missing") is None


class MeasuringRenderer:
    def __init__(self):
        self.invalid = False
        self.preflight_calls = 0

    async def preflight(self, *args):
        self.preflight_calls += 1
        return [{"content_ref": "heading", "reason": "text_overflow"}] if self.invalid else []

    async def render(self, render, fragments, style, assets, directory):
        directory.mkdir(parents=True, exist_ok=True)
        for filename in ("page.png", "thumbnail.png", "page.pdf"):
            (directory / filename).write_bytes(b"test-only")
        return {"text_layer": [], "browser_version": "test-only"}


def test_design_precedes_image_generation_and_survives_cached_retry(decks, settings):
    from opennotelm.composition import CompositionService
    from test_models import config

    client, state, _ = decks
    renderer = MeasuringRenderer()
    service = CompositionService(client.app.state.db, client.app.state.models, settings, renderer)
    client.app.state.decks.composition = service
    client.app.state.assets.designs = service.designs
    client.app.state.decks.assets = client.app.state.assets
    assert client.post("/api/settings/models/test", json=config("image")).status_code == 200
    before = len(state["calls"])
    notebook, _ = notebook_with_source(client)
    deck, job = create_deck(client, notebook)
    assert job["status"] == "completed" and deck["status"] == "draft"
    calls = state["calls"][before:]
    design_index = next(
        i
        for i, c in enumerate(calls)
        if c.get("messages", [{}])[0]
        .get("content", "")
        .startswith("Design an original visual composition")
    )
    prompt_index = next(
        i
        for i, c in enumerate(calls)
        if c.get("messages", [{}])[0]
        .get("content", "")
        .startswith("Write one image-generation prompt")
    )
    image_index = next(i for i, c in enumerate(calls) if "prompt" in c)
    assert design_index < prompt_index < image_index
    data = json.loads(calls[prompt_index]["messages"][-1]["content"])
    assert data["asset_frame"]["aspect_ratio"] > 0
    assert renderer.preflight_calls == 10
    before = len(state["calls"])
    slide = deck["slides"][1]
    record = client.app.state.decks.record(deck["id"])
    with client.app.state.db.connect() as conn:
        row = dict(conn.execute("SELECT * FROM slides WHERE id=?", (slide["id"],)).fetchone())
        assert conn.execute("SELECT count(*) FROM slide_designs").fetchone()[0] == 10
    assert client.portal.call(service.prepare_design, record, row)
    assert len(state["calls"]) == before and renderer.preflight_calls == 10


def test_invalid_text_design_is_repaired_before_any_image_request(decks, settings):
    from opennotelm.composition import CompositionService

    client, state, _ = decks
    notebook, _ = notebook_with_source(client)
    deck, _ = create_deck(client, notebook)
    renderer = MeasuringRenderer()
    renderer.invalid = True
    service = CompositionService(client.app.state.db, client.app.state.models, settings, renderer)
    with client.app.state.db.connect() as conn:
        row = dict(
            conn.execute(
                "SELECT * FROM slides WHERE deck_id=? ORDER BY ordinal LIMIT 1", (deck["id"],)
            ).fetchone()
        )
    record = client.app.state.decks.record(deck["id"])
    before = state.get("image_calls", 0)
    with pytest.raises(AppError, match="RENDER_LAYOUT_INVALID"):
        client.portal.call(service.prepare_design, record, row)
    assert renderer.preflight_calls == 2 and state.get("image_calls", 0) == before
    with client.app.state.db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM slide_designs").fetchone()[0] == 0
    feedback = json.loads(state["calls"][-1]["messages"][-1]["content"])
    assert feedback["layout_feedback"][0]["reason"] == "text_overflow"


def test_relationships_are_grounded_and_cannot_silently_disappear(decks):
    from pydantic import ValidationError

    client, _, _ = decks
    notebook, _ = notebook_with_source(client)
    deck, _ = create_deck(client, notebook)
    value = deck["slides"][0]["spec"]
    value["visual_relationships"] = [
        {
            "id": "contrast",
            "source_element": "heading",
            "target_element": "idea",
            "kind": "contrast",
            "explanation": "A test-only supported distinction",
            "citations": value["content_elements"][1]["citations"],
        }
    ]
    spec = SlideSpec.model_validate(value)
    assert spec.visual_relationships[0].citations[0] in spec.citation_ids()
    render = RenderSpec.model_validate(
        {
            "layers": [
                {"type": "background", "fill": "#FFFFFF"},
                {
                    "type": "path",
                    "relationship_ref": "contrast",
                    "stroke": "#000000",
                    "points": [{"x": 0.1, "y": 0.5}, {"x": 0.9, "y": 0.5}],
                },
                {
                    "type": "text",
                    "content_ref": "heading",
                    "region": {"left": 0.1, "top": 0.1, "width": 0.8, "height": 0.2},
                    "font_size": 72,
                    "color": "#000000",
                },
            ]
        }
    )
    validate_relationships(render, spec.visual_relationships)
    render.layers[1].relationship_ref = None
    with pytest.raises(ValueError, match="relationship"):
        validate_relationships(render, spec.visual_relationships)
    value["visual_relationships"][0]["target_element"] = "invented"
    with pytest.raises(ValidationError, match="saved content"):
        SlideSpec.model_validate(value)
