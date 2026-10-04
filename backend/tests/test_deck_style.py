import json
from types import SimpleNamespace

import pytest
from deck_provider import deck_completion
from opennotelm.deck_art import validate_art
from opennotelm.deck_style import STYLE_VERSION, AdaptiveDeckStyle, validate_style
from opennotelm.generated_pages import page_prompt, page_signature, prompt_version
from test_deck_art import direction, semantic
from test_decks import notebook_with_source
from test_generated_pages import new_page_deck
from test_generated_pages import pages as generated_page_fixture
from test_sources import wait_for_job


@pytest.fixture
def pages(settings):
    yield from generated_page_fixture.__wrapped__(settings)


def test_style_receives_actual_request_and_content_then_keeps_the_selected_medium(pages):
    client, state, _ = pages
    notebook, _ = notebook_with_source(client)
    instruction = "用冷色平面矢量表达，不要复古纸张；文字尽量易懂。"
    response = client.post(
        f"/api/notebooks/{notebook}/decks", json={"slide_count": 10, "instruction": instruction}
    ).json()
    assert wait_for_job(client, response["job"]["id"])["status"] == "completed"
    deck = client.get(f"/api/decks/{response['id']}").json()
    record = client.app.state.decks.record(deck["id"])
    call = next(
        c
        for c in state["calls"]
        if c.get("messages", [{}])[0].get("content", "").startswith("Define a unique")
    )
    data = json.loads(call["messages"][-1]["content"])
    assert data["user_instruction"] == instruction
    assert data["content_context"] == record["understanding"]["content"]
    assert data["pages"][0]["key_message"] == deck["plan"]["slides"][0]["key_message"]
    assert "visual_concept" not in data["pages"][0]  # old scenery cannot choose the medium
    assert deck["generation_metadata"]["visual_style_version"] == STYLE_VERSION
    assert len(deck["generation_metadata"]["visual_strategy"]["candidates"]) == 3
    art_call = next(
        c
        for c in state["calls"]
        if c.get("messages", [{}])[0].get("content", "").startswith("Art-direct")
    )
    art_data = json.loads(art_call["messages"][-1]["content"])
    assert art_data["style"] == deck["style"]
    assert art_data["selected_direction"]["primary_medium"] == "Layered drawing"
    assert deck["art_direction"]["version"] == "deck-art-v2"
    image = next(c for c in state["calls"] if c.get("size"))
    prefix, data = image["prompt"].split("PAGE DATA:\n")
    image_data = json.loads(data)
    assert image_data["user_instruction"] == instruction
    assert image_data["deck_style"]["image_style"] == deck["style"]["image_style"]
    assert prefix.index(deck["style"]["image_style"]) < prefix.index("Render every string")
    # Internal rationale must not be added to the visible copy.
    assert "strategy" not in image_data
    with client.app.state.db.connect() as conn:
        saved = conn.execute(
            "SELECT generation_metadata_json FROM assets WHERE slide_id=? AND request_id=?",
            (deck["slides"][0]["id"], "full_page"),
        ).fetchone()
    assert json.loads(saved[0])["prompt_version"] == "whole-page-v6"
    before = len(state["calls"])
    client.portal.call(
        client.app.state.decks.style,
        record,
        SimpleNamespace(progress=lambda *args: None),
    )
    assert len(state["calls"]) == before  # retries never silently choose a new style
    with client.app.state.db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM slides WHERE deck_id=? ORDER BY ordinal", (deck["id"],)
        ).fetchone()
    before_signature = page_signature(record, row, semantic())
    record["instruction"] += "改用黑白。"
    assert page_signature(record, row, semantic()) != before_signature


def test_flat_visual_identity_can_vary_structure_without_forced_perspective():
    art = direction()
    for page in art.pages:
        page.viewpoint = "flat"
    with pytest.raises(ValueError, match="viewpoints"):
        validate_art(art, [semantic()] * 10)
    validate_art(art, [semantic()] * 10, flat=True)
    for page in art.pages:
        page.text_placement = "wide_heading"
    with pytest.raises(ValueError, match="text placements"):
        validate_art(art, [semantic()] * 10, flat=True)


def test_duplicate_visual_candidates_are_repaired_instead_of_presented_as_alternatives():
    style = AdaptiveDeckStyle.model_validate(
        deck_completion(
            {
                "messages": [
                    {"content": "Define a unique DeckStyleManifest."},
                    {"content": '{"content_context":"Content"}'},
                ]
            }
        )
    )
    validate_style(style)
    style.strategy.candidates[1].primary_medium = " layered DRAWING "
    with pytest.raises(ValueError, match="materially different"):
        validate_style(style)


def test_restyle_copy_replans_identity_without_rewriting_content_or_changing_original(pages):
    client, state, _ = pages
    notebook, _ = notebook_with_source(client)
    original, _ = new_page_deck(client, notebook)
    # Also cover upgrading an old Deck with no content-adaptive planning metadata.
    metadata = original["generation_metadata"]
    metadata.pop("visual_style_version")
    metadata.pop("visual_strategy")
    with client.app.state.db.connect() as conn:
        conn.execute(
            "UPDATE decks SET generation_metadata_json=? WHERE id=?",
            (json.dumps(metadata), original["id"]),
        )
    original = client.get(f"/api/decks/{original['id']}").json()
    before = len(state["calls"])
    created = client.post(f"/api/decks/{original['id']}/generated-copy?restyle=true").json()
    assert wait_for_job(client, created["job"]["id"])["status"] == "completed"
    copy = client.get(f"/api/decks/{created['id']}").json()
    assert copy["status"] == "ready"
    assert copy["generation_metadata"]["restyled"]
    assert copy["generation_metadata"]["visual_style_version"] == STYLE_VERSION
    assert [s["spec"] for s in copy["slides"]] == [s["spec"] for s in original["slides"]]
    assert copy["source_scope"] == original["source_scope"]
    assert client.get(f"/api/decks/{original['id']}").json() == original
    calls = state["calls"][before:]
    assert len(calls) == 12  # one style comparison, one art plan, ten images
    assert not any(
        c.get("messages", [{}])[0].get("content", "").startswith("Author one SlideSpec")
        for c in calls
    )
    assert copy["generation_metadata"]["visual_strategy"]
    for slide in copy["slides"]:
        assert slide["citations"]


@pytest.mark.parametrize(
    ("option", "restyled"), [("", True), ("&restyle=true", True), ("&restyle=false", False)]
)
def test_legacy_content_rewrite_reassesses_style_unless_explicitly_preserved(
    pages, option, restyled
):
    client, state, _ = pages
    notebook, _ = notebook_with_source(client)
    source, _ = new_page_deck(client, notebook)
    metadata = source["generation_metadata"]
    metadata.pop("visual_style_version")
    metadata.pop("visual_strategy")
    with client.app.state.db.connect() as conn:
        conn.execute(
            "UPDATE decks SET generation_metadata_json=? WHERE id=?",
            (json.dumps(metadata), source["id"]),
        )
    source = client.get(f"/api/decks/{source['id']}").json()
    # A visibly different provider result makes accidental style reuse observable.
    state["style_palette_override"] = {
        "background": "#EEF4FA",
        "text": "#17213E",
        "accent": "#405DC4",
        "secondary": "#765CAD",
        "muted": "#73809B",
    }
    before = len(state["calls"])
    created = client.post(
        f"/api/decks/{source['id']}/generated-copy?rewrite_content=true{option}"
    ).json()
    assert wait_for_job(client, created["job"]["id"])["status"] == "completed"
    copy = client.get(f"/api/decks/{created['id']}").json()
    assert copy["status"] == "ready"
    assert copy["generation_metadata"]["restyled"] == restyled
    assert copy["generation_metadata"]["rewritten_content"]
    calls = state["calls"][before:]
    styling = [
        c
        for c in calls
        if c.get("messages", [{}])[0].get("content", "").startswith("Define a unique")
    ]
    assert len(styling) == int(restyled)
    if restyled:
        assert copy["style"]["palette"] == state["style_palette_override"]
        assert copy["style"] != source["style"]
        assert copy["generation_metadata"]["visual_style_version"] == STYLE_VERSION
        assert copy["art_direction"]["version"] == "deck-art-v2"
        record = client.app.state.decks.record(copy["id"])
        data = json.loads(styling[0]["messages"][-1]["content"])
        assert data["content_context"] == record["understanding"]["content"]
    else:
        assert copy["style"] == source["style"]
        assert not copy["generation_metadata"].get("visual_style_version")
    assert copy["source_scope"] == source["source_scope"]
    assert all(s["spec"] and s["citations"] for s in copy["slides"])
    assert client.get(f"/api/decks/{source['id']}").json() == source


def test_legacy_prompt_stays_frozen_when_adaptive_styles_are_introduced():
    deck = {
        "language": "en",
        "style": {"palette": {"background": "#FFFFFF"}},
        "generation_metadata": {"generation_version": "deck-content-v4"},
    }
    slide = {
        "id": "old",
        "plan_json": '{"index":1,"purpose":"Read"}',
        "visual_instruction": "",
        "image_instruction": "",
    }
    assert prompt_version(deck) == "whole-page-v1"
    prompt = page_prompt(deck, slide, semantic())
    assert "PRIMARY VISUAL MEDIUM" not in prompt and "user_instruction" not in prompt
    assert "coherent illustrated explanation" in prompt
