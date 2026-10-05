import json

import pytest
from opennotelm.deck_language import deck_language_instruction
from opennotelm.deck_schemas import DeckInput
from opennotelm.languages import LANGUAGE_NAMES
from pydantic import ValidationError
from test_decks import decks as decks  # noqa: F401
from test_decks import notebook_with_source
from test_sources import wait_for_job


@pytest.mark.parametrize("language", LANGUAGE_NAMES)
def test_explicit_language_preserves_quotes_and_requested_bilingual_copy(language):
    prompt = deck_language_instruction(language)
    assert LANGUAGE_NAMES[language] in prompt
    assert f"output language code: {language}" in prompt
    assert "bilingual or multilingual" in prompt
    assert "exact original quotations" in prompt
    assert "planned wording" in prompt
    assert "not visible copy" in prompt
    assert DeckInput(language=language).language == language


def test_unsupported_output_language_is_rejected_before_queueing():
    with pytest.raises(ValidationError):
        DeckInput(language="arbitrary instruction")


def test_english_language_reaches_all_stages_and_structural_repairs(decks):
    client, state, _ = decks
    notebook, source = notebook_with_source(client)
    gateway = client.app.state.models.gateway.text
    injected = set()

    async def mixed_output(config, key, messages, **kwargs):
        output = await gateway(config, key, messages, **kwargs)
        system = messages[0]["content"]
        data = json.loads(messages[-1]["content"])
        stage = next(
            (
                s
                for s in ("Create a DeckBrief.", "Plan the narrative", "Author one SlideSpec")
                if system.startswith(s)
            ),
            None,
        )
        subject = (stage, data.get("slide_plan", {}).get("index"))
        if stage and subject not in injected:
            injected.add(subject)
            value = json.loads(output)
            if stage == "Create a DeckBrief.":
                value["language"] = "zh-CN"
            elif stage == "Plan the narrative":
                value["slides"] = value["slides"][:-1]
            else:
                value["content_elements"][1]["citations"] = ["UNREGISTERED"]
            return json.dumps(value, ensure_ascii=False)
        return output

    client.app.state.models.gateway.text = mixed_output
    response = client.post(
        f"/api/notebooks/{notebook}/decks",
        json={
            "slide_count": 10,
            "language": "en",
            "render_mode": "native",
            "instruction": "请用浅显易懂的方式详尽解读",
            "title_mode": "source",
        },
    )
    assert response.status_code == 202
    value = response.json()
    job = wait_for_job(client, value["job"]["id"])
    assert job["status"] == "completed"
    deck = client.get(f"/api/decks/{value['id']}").json()
    assert all(s["status"] == "authored" for s in deck["slides"])
    assert deck["brief"]["goal"] == "Understand cumulative learning"
    assert deck["plan"]["slides"][0]["title"].startswith("Step 1")
    assert all(s["spec"]["content_elements"][0]["text"].startswith("Step ") for s in deck["slides"])
    calls = [c for c in state["calls"] if "messages" in c]
    for call in calls:
        system = call["messages"][0]["content"]
        if system.startswith(("Create a DeckBrief.", "Plan the narrative", "Author one SlideSpec")):
            assert "English" in system and "output language code: en" in system
            assert json.loads(call["messages"][-1]["content"])["output_language"] == "en"
    reading = next(c for c in calls if c["messages"][0]["content"].startswith("Create a useful"))
    assert "output language code: en" in reading["messages"][0]["content"]
    for slide in deck["slides"]:
        for citation in slide["citations"].values():
            spans = client.get(f"/api/citations/{citation}").json()["spans"]
            assert spans[0]["source_id"] == source and spans[0]["quote"]
