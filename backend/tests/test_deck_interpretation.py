"""Interpretation, preference precedence and original-source provenance contracts."""

import json

import pytest
from opennotelm.citations import CITATION_PATTERN
from opennotelm.deck_schemas import SlideContentElement
from opennotelm.generated_pages import visible_element
from test_decks import decks as decks  # noqa: F401
from test_decks import notebook_with_source
from test_revisions import submit, unchanged_siblings
from test_sources import wait_for_job


def generate(client, notebook, instruction):
    response = client.post(
        f"/api/notebooks/{notebook}/decks",
        json={"slide_count": 10, "instruction": instruction, "render_mode": "native"},
    )
    assert response.status_code == 202, response.text
    value = response.json()
    job = wait_for_job(client, value["job"]["id"])
    return client.get(f"/api/decks/{value['id']}").json(), job


@pytest.mark.parametrize("source_only", [False, True])
def test_model_readings_and_examples_are_saved_unless_user_requests_source_only(decks, source_only):
    client, state, _ = decks
    notebook, _ = notebook_with_source(client)
    original = client.app.state.models.gateway.text

    async def elaboration(config, key, messages, **kwargs):
        output = await original(config, key, messages, **kwargs)
        system = messages[0]["content"]
        if system.startswith("Resolve deck content preferences."):
            value = json.loads(output)
            value["source_only"] = source_only
            return json.dumps(value)
        if system.startswith("Author one SlideSpec"):
            value = json.loads(output)
            ref = json.loads(messages[-1]["content"])["evidence"][0]["id"]
            value["content_elements"].extend(
                [
                    {
                        "id": "reading",
                        "type": "statement",
                        "text": "坚持的意义在于让每次反思影响下一次实践。",
                        "basis": "interpretation",
                        "citations": [ref],
                    },
                    {
                        "id": "example",
                        "type": "statement",
                        "text": "比如设想每天练习一个词，再用它写一句话。",
                        "basis": "analogy",
                        "citations": [],
                    },
                ]
            )
            return json.dumps(value, ensure_ascii=False)
        return output

    client.app.state.models.gateway.text = elaboration
    instruction = "仅使用原文，不添加引申" if source_only else "请结合模型知识引申解读，并举例"
    deck, job = generate(client, notebook, instruction)
    assert job["status"] == "completed"
    assert deck["generation_metadata"]["content_preferences"]["source_only"] == source_only
    if source_only:
        assert deck["status"] == "partial"
        assert all(s["spec"] is None for s in deck["slides"])
    else:
        assert all(s["status"] == "authored" for s in deck["slides"])
        for slide in deck["slides"]:
            reading, example = slide["spec"]["content_elements"][-2:]
            assert reading["basis"] == "interpretation" and reading["citations"]
            assert example["basis"] == "analogy" and not example["citations"]
            assert set(slide["citations"]) == set(reading["citations"])
    # Preferences are resolved once and frozen for all pages, not reclassified per page.
    assert (
        sum(
            c.get("messages", [{}])[0]
            .get("content", "")
            .startswith("Resolve deck content preferences.")
            for c in state["calls"]
        )
        == 1
    )


def test_instructions_apply_to_first_reading_and_whole_dossier_reaches_each_author(decks):
    client, state, _ = decks
    notebook, _ = notebook_with_source(client)
    instruction = "先整体解读，再逐段引用关键原文并解释为什么，请尽可能详尽"
    deck, job = generate(client, notebook, instruction)
    assert job["status"] == "completed"
    calls = [c for c in state["calls"] if "messages" in c]
    synthesis = next(c for c in calls if c["messages"][0]["content"].startswith("Create a useful"))
    research_input = json.loads(synthesis["messages"][-1]["content"])
    assert research_input["user_instruction"] == instruction
    assert research_input["source_context"][0]["title"]
    with client.app.state.db.connect() as conn:
        dossier = json.loads(
            conn.execute(
                "SELECT understanding_json FROM decks WHERE id=?", (deck["id"],)
            ).fetchone()[0]
        )["content"]
    assert "\n" in dossier
    authors = [c for c in calls if c["messages"][0]["content"].startswith("Author one SlideSpec")]
    assert len(authors) == 10
    for call in authors:
        data = json.loads(call["messages"][-1]["content"])
        assert data["user_instruction"] == instruction
        assert CITATION_PATTERN.sub("", data["source_context"]) == CITATION_PATTERN.sub("", dossier)
        assert set(CITATION_PATTERN.findall(data["source_context"])) <= {
            e["id"] for e in data["evidence"]
        }


@pytest.mark.parametrize("explicit_notes", [False, True])
def test_user_requested_editorial_labels_override_default_but_negation_does_not(
    decks, explicit_notes
):
    client, state, _ = decks
    notebook, _ = notebook_with_source(client)
    original = client.app.state.models.gateway.text

    async def preferences(config, key, messages, **kwargs):
        output = await original(config, key, messages, **kwargs)
        if messages[0]["content"].startswith("Resolve deck content preferences."):
            value = json.loads(output)
            value["include_editorial_notes"] = explicit_notes
            return json.dumps(value)
        return output

    client.app.state.models.gateway.text = preferences
    state["added_editorial_note"] = True
    instruction = "请添加解读边界说明" if explicit_notes else "请深入解读，不要添加解读边界"
    deck, job = generate(client, notebook, instruction)
    assert job["status"] == "completed"
    assert any("解读边界" in str(slide["spec"]) for slide in deck["slides"]) is explicit_notes


@pytest.mark.parametrize("dense_text", [False, True])
def test_explicit_dense_page_request_can_exceed_normal_budget(decks, dense_text):
    client, _, _ = decks
    notebook, _ = notebook_with_source(client)
    original = client.app.state.models.gateway.text

    async def dense(config, key, messages, **kwargs):
        output = await original(config, key, messages, **kwargs)
        system = messages[0]["content"]
        if system.startswith("Resolve deck content preferences."):
            value = json.loads(output)
            value["dense_text"] = dense_text
        elif system.startswith("Plan the narrative"):
            value = json.loads(output)
            for slide in value["slides"]:
                slide["reading_budget"] = 650
        else:
            return output
        return json.dumps(value)

    client.app.state.models.gateway.text = dense
    instruction = "请增加每页的可见文字" if dense_text else "请尽可能深入解读"
    deck, job = generate(client, notebook, instruction)
    if dense_text:
        assert job["status"] == "completed" and deck["status"] == "draft"
    else:
        assert job["status"] == "failed" and deck["plan"] is None


def test_internal_provenance_never_becomes_visible_image_text():
    element = SlideContentElement(
        id="example", type="statement", text="比如设想这样一个场景", basis="analogy"
    )
    assert visible_element(element) == {"role": "statement", "text": "比如设想这样一个场景"}


def test_specific_page_request_overrides_deck_default_without_changing_other_pages(decks):
    client, _, _ = decks
    notebook, _ = notebook_with_source(client)
    original = client.app.state.models.gateway.text

    async def specific(config, key, messages, **kwargs):
        output = await original(config, key, messages, **kwargs)
        data = json.loads(messages[-1]["content"])
        system = messages[0]["content"]
        if system.startswith("Resolve deck content preferences."):
            value = json.loads(output)
            value["source_only"] = not bool(data["revision_instruction"])
            return json.dumps(value)
        if system.startswith("Author one SlideSpec") and data["revision_instruction"]:
            value = json.loads(output)
            value["content_elements"].append(
                {
                    "id": "extra_context",
                    "type": "statement",
                    "text": "间隔练习是一种常见的学习方法。",
                    "basis": "background",
                    "citations": [],
                }
            )
            return json.dumps(value, ensure_ascii=False)
        return output

    client.app.state.models.gateway.text = specific
    deck, _ = generate(client, notebook, "仅使用原文")
    assert deck["generation_metadata"]["content_preferences"]["source_only"]
    updated, job = submit(client, deck, deck["slides"][0], "content", "本页请补充相关模型知识")
    assert job["status"] == "completed"
    assert updated["slides"][0]["spec"]["content_elements"][-1]["basis"] == "background"
    assert updated["generation_metadata"]["content_preferences"]["source_only"]
    unchanged_siblings(deck, updated, deck["slides"][0]["id"])
