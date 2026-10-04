import json

import pytest
from test_decks import create_deck, notebook_with_source
from test_decks import decks as deck_fixture


@pytest.fixture
def decks(settings):
    yield from deck_fixture.__wrapped__(settings)


@pytest.mark.parametrize(
    "defect",
    [
        "repeated_message",
        "missing_storyboard",
        "missing_grammar",
        "missing_budget",
        "missing_image",
        "too_much_copy",
        "fake_relationship_citation",
    ],
)
def test_invalid_editorial_plan_or_missing_planned_image_is_not_published(decks, defect):
    client, state, _ = decks
    notebook, _ = notebook_with_source(client)
    original = client.app.state.models.gateway.text
    plan_calls = []

    async def invalid_text(config, key, messages, **kwargs):
        output = await original(config, key, messages, **kwargs)
        if messages[0]["content"].startswith("Plan the narrative"):
            value = json.loads(output)
            if defect == "repeated_message":
                value["slides"][1]["key_message"] = value["slides"][0]["key_message"]
            elif defect == "missing_storyboard":
                value["slides"][1]["visual_concept"] = ""
            elif defect == "missing_grammar":
                value["slides"][1]["visual_grammar"] = ""
            elif defect == "missing_budget":
                value["slides"][1]["reading_budget"] = 0
            plan_calls.append(messages[0]["content"])
            return json.dumps(value, ensure_ascii=False)
        if defect in ("missing_image", "too_much_copy", "fake_relationship_citation") and messages[
            0
        ]["content"].startswith("Author one SlideSpec"):
            value = json.loads(output)
            if defect == "missing_image":
                value["asset_requests"] = []
            elif defect == "too_much_copy":
                value["content_elements"][1]["text"] = "测试文字" * 200
            else:
                value["visual_relationships"] = [
                    {
                        "id": "invented_evidence",
                        "source_element": "heading",
                        "target_element": "idea",
                        "kind": "association",
                        "explanation": "Test an unsupported edge",
                        "citations": ["FAKE"],
                    }
                ]
            return json.dumps(value, ensure_ascii=False)
        return output

    client.app.state.models.gateway.text = invalid_text
    deck, job = create_deck(client, notebook)
    if defect in ("missing_image", "too_much_copy", "fake_relationship_citation"):
        assert job["status"] == "completed" and deck["status"] == "partial"
        if defect == "missing_image":
            assert deck["slides"][1]["spec"] is None
            assert deck["slides"][1]["status"] == "failed"
            assert all(s["spec"] for i, s in enumerate(deck["slides"]) if i != 1)
        else:
            assert all(s["spec"] is None and s["status"] == "failed" for s in deck["slides"])
    else:
        assert job["status"] == "failed" and deck["status"] == "failed"
        assert deck["plan"] is None and not deck["slides"]
        assert len(plan_calls) == 2
        assert "previous JSON failed" in plan_calls[-1]
