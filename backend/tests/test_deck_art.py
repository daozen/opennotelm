import hashlib
import json

import pytest
from deck_provider import deck_completion
from opennotelm.deck_art import DeckArt, eligible_forms, page_art, validate_art
from opennotelm.deck_schemas import SlideSpec
from opennotelm.errors import AppError
from opennotelm.generated_pages import page_prompt, page_signature
from test_decks import notebook_with_source
from test_generated_pages import new_page_deck
from test_generated_pages import pages as generated_page_fixture
from test_sources import wait_for_job


@pytest.fixture
def pages_fixture(settings):
    yield from generated_page_fixture.__wrapped__(settings)


def semantic(kind="statement"):
    data = deck_completion(
        {
            "messages": [
                {"content": "Author one SlideSpec"},
                {
                    "content": json.dumps(
                        {
                            "slide_plan": {
                                "index": 1,
                                "title": "Meaningful title",
                                "key_message": "Learning",
                            },
                            "evidence": [
                                {"id": "E1", "text": "Small improvements accumulate over time."}
                            ],
                        }
                    )
                },
            ]
        }
    )
    data["content_elements"][1].update(type=kind, items=[])
    return SlideSpec.model_validate(data)


def direction():
    return DeckArt.model_validate(
        deck_completion(
            {
                "messages": [
                    {"content": "Art-direct the complete illustrated deck"},
                    {"content": json.dumps({"pages": [{"index": i} for i in range(1, 11)]})},
                ]
            }
        )
    )


def test_visual_forms_respect_available_evidence_instead_of_manufacturing_variety():
    plain = semantic()
    assert {
        "evidence_quote",
        "numeric_evidence",
        "comparison_stage",
        "sequential_panels",
        "branching_journey",
    }.isdisjoint(eligible_forms(plain))
    assert "evidence_quote" in eligible_forms(semantic("quote"))
    assert "numeric_evidence" in eligible_forms(semantic("number"))
    planned = direction()
    validate_art(planned, [plain] * 10)
    planned.pages[0].form = "numeric_evidence"
    with pytest.raises(ValueError, match="supporting authored content"):
        validate_art(planned, [plain] * 10)


@pytest.mark.parametrize("degeneracy", ["adjacent", "few_forms", "framing", "renamed_layouts"])
def test_whole_deck_repetition_is_rejected(degeneracy):
    art = direction()
    if degeneracy == "adjacent":
        art.pages[1].form = art.pages[0].form
    elif degeneracy == "few_forms":
        for i, page in enumerate(art.pages):
            page.form = ["object_annotation", "immersive_scene"][i % 2]
    elif degeneracy == "framing":
        for page in art.pages:
            page.viewpoint, page.text_placement = "flat", "wide_heading"
    else:
        for i, page in enumerate(art.pages):
            page.layout = f"Page {i + 1}: put text on the left and a glowing scene on the right."
    with pytest.raises(ValueError):
        validate_art(art, [semantic()] * 10)


def test_distinct_non_latin_layouts_are_not_erased_into_one_repeated_layout():
    from opennotelm.deck_art import layout_fingerprint

    layouts = [
        "标题横贯顶端下方以开放空间承载放大的核心意象和短段解释",
        "中央以核心概念为锚周围环绕分布相关解释并留出宽阔边界",
        "通过上下分层展开核心概念内部结构侧面配置简短的完整说明",
        "核心内容按垂直方向渐次展开右侧保留整块空白承载引用说明",
        "用对角线组织多层信息让标题落在左上核心意象落在右下",
        "将主要概念布置成疏密有别的群组短段文字依附相应主体",
        "以大幅原文引句作为中央核心辅助意象在下缘安静展开",
        "以横向的开放长卷组织主题文字分散于独立而相连的空间",
        "用放大的单个物体呈现主题各处特征配置邻近的解释标注",
        "以整体总览图汇集核心思想标题位于顶部概念群组均匀分布",
    ]
    art = direction()
    for page, layout in zip(art.pages, layouts, strict=True):
        page.layout = layout
    validate_art(art, [semantic()] * 10)
    assert len({layout_fingerprint(layout) for layout in layouts}) == 10
    for pair in [
        ("左侧主图右侧正文", "顶部标题下方环形结构"),
        ("слева", "справа"),
        ("يسار", "يمين"),
    ]:
        assert layout_fingerprint(pair[0]) != layout_fingerprint(pair[1])
    assert layout_fingerprint("two columns at 1:2") != layout_fingerprint("two columns at 2:1")


def test_true_multilingual_repetition_localizes_only_excess_layouts_and_safe_counts():
    from opennotelm.deck_art import diagnose_art
    from opennotelm.generation_attempts import safe_validation

    art = direction()
    for index, page in enumerate(art.pages):
        page.layout = f"第{index + 1}页：左侧使用相同大幅主图右侧放置相同结构的正文说明"
    errors = diagnose_art(art.model_dump(), [semantic()] * 10)
    assert len(errors) == 1 and errors[0].reason == "art_layouts"
    assert errors[0].paths == [["pages", i, "layout"] for i in range(4, 10)]
    report = safe_validation(errors)
    assert report["issues"] == [
        {
            "code": "art_layouts",
            "path": ["pages", i, "layout"],
            "max_length": 4,
            "actual_length": 10,
        }
        for i in range(4, 10)
    ]
    assert "左侧" not in json.dumps(report, ensure_ascii=False)


@pytest.mark.parametrize("repair", ["complete", "partial", "stalled"])
def test_layout_patch_preserves_other_art_fields_and_removes_duplicate_feedback(repair):
    import asyncio
    from types import SimpleNamespace

    from opennotelm.deck_art import diagnose_art
    from opennotelm.schemas import ModelInput
    from opennotelm.structured import structured_completion

    original = direction().model_dump()
    candidate = json.loads(json.dumps(original))
    for page in candidate["pages"]:
        page["layout"] = (
            "A single identical image on the left and text on the right with wide margins."
        )
    calls = []

    async def text(config, key, messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return json.dumps(candidate)
        data = json.loads(messages[1]["content"])
        assert data["failed_paths"] == [
            ["pages", i, "layout"] for i in range(6 if len(calls) == 3 else 4, 10)
        ]
        assert "additional_checks" not in data["validation_feedback"]
        paths = data["failed_paths"]
        if repair == "partial" and len(calls) == 2:
            paths = paths[:2]
        if repair == "stalled":
            return json.dumps(
                {"updates": [{"path": paths[0], "value": candidate["pages"][4]["layout"]}]}
            )
        return json.dumps(
            {
                "updates": [
                    {"path": path, "value": original["pages"][path[1]]["layout"]} for path in paths
                ]
            }
        )

    models = SimpleNamespace(
        configured=lambda role: (
            ModelInput(base_url="https://example.com/v1", model_id="test"),
            "",
        ),
        public_configs=lambda: {
            "models": {"language": {"capabilities": {"structured_output": "json_object"}}}
        },
        gateway=SimpleNamespace(text=text),
    )

    async def run():
        return await structured_completion(
            models,
            "Art direct",
            {},
            DeckArt,
            validate=lambda value: validate_art(value, [semantic()] * 10),
            diagnose=lambda value: diagnose_art(value, [semantic()] * 10),
            max_attempts=3,
        )

    if repair == "stalled":
        with pytest.raises(AppError):
            asyncio.run(run())
        assert len(calls) == 2
        return
    result = asyncio.run(run())
    expected = json.loads(json.dumps(candidate))
    for i in range(4, 10):
        expected["pages"][i]["layout"] = original["pages"][i]["layout"]
    assert result.model_dump() == expected and len(calls) == (3 if repair == "partial" else 2)


def test_failed_visual_planning_stops_before_images_then_retry_reuses_authored_copy(pages_fixture):
    client, state, _ = pages_fixture
    notebook, _ = notebook_with_source(client)
    state["bad_art"] = True
    deck, job = new_page_deck(client, notebook)
    assert job["status"] == "failed" and deck["status"] == "failed"
    assert all(s["spec"] and not s["assets"] for s in deck["slides"])
    assert not any(call.get("size") for call in state["calls"])
    old_specs = [s["spec"] for s in deck["slides"]]
    authored = sum(
        c.get("messages", [{}])[0].get("content", "").startswith("Author one SlideSpec")
        for c in state["calls"]
    )
    state["bad_art"] = False
    response = client.post(f"/api/decks/{deck['id']}/retry")
    assert response.status_code == 202
    assert wait_for_job(client, response.json()["id"])["status"] == "completed"
    updated = client.get(f"/api/decks/{deck['id']}").json()
    assert updated["status"] == "ready"
    assert [s["spec"] for s in updated["slides"]] == old_specs
    assert (
        sum(
            c.get("messages", [{}])[0].get("content", "").startswith("Author one SlideSpec")
            for c in state["calls"]
        )
        == authored
    )


def test_incomplete_copy_waits_for_retry_before_any_visual_planning(pages_fixture, monkeypatch):
    client, state, _ = pages_fixture
    notebook, _ = notebook_with_source(client)
    service = client.app.state.decks
    author = service.author
    calls = []

    async def interrupted(*args, **kwargs):
        calls.append(args[2]["id"])
        if len(calls) == 1:
            raise AppError("MODEL_CONNECTION_FAILED", "Temporary authoring failure")
        return await author(*args, **kwargs)

    monkeypatch.setattr(service, "author", interrupted)
    deck, job = new_page_deck(client, notebook)
    assert job["status"] == "completed" and deck["status"] == "partial"
    assert deck["art_direction"] is None
    assert any(s["error_code"] == "MODEL_CONNECTION_FAILED" for s in deck["slides"])
    assert sum(bool(s["spec"]) for s in deck["slides"]) == 9
    assert not any(call.get("size") for call in state["calls"])
    saved = {s["id"]: s["spec"] for s in deck["slides"] if s["spec"]}
    retry = client.post(f"/api/decks/{deck['id']}/retry")
    assert wait_for_job(client, retry.json()["id"])["status"] == "completed"
    restored = client.get(f"/api/decks/{deck['id']}").json()
    assert restored["status"] == "ready" and len(calls) == 11
    assert all(s["spec"] == saved[s["id"]] for s in restored["slides"] if s["id"] in saved)


def test_coordinated_directions_reach_images_after_all_copy_and_do_not_replan_on_retry(
    pages_fixture,
):
    client, state, _ = pages_fixture
    notebook, _ = notebook_with_source(client)
    deck, _ = new_page_deck(client, notebook)
    calls = state["calls"]
    art_calls = [
        i
        for i, c in enumerate(calls)
        if c.get("messages", [{}])[0]
        .get("content", "")
        .startswith("Art-direct the complete illustrated deck")
    ]
    assert len(art_calls) == 1
    assert (
        sum(
            c.get("messages", [{}])[0].get("content", "").startswith("Author one SlideSpec")
            for c in calls[: art_calls[0]]
        )
        == 10
    )
    images = [c for c in calls if "prompt" in c and c.get("size")]
    assert len(images) == 10
    for slide, image in zip(deck["slides"], images, strict=True):
        data = json.loads(image["prompt"].split("PAGE DATA:\n")[1])
        assert data["art_direction"]["page"] == deck["art_direction"]["pages"][slide["id"]]
        # Real-provider review exposed topic scenery overriding late JSON metadata.
        # The selected subject and concrete layout must precede the generic copy contract.
        brief, _data = image["prompt"].split("PAGE DATA:\n", 1)
        assert brief.index(data["art_direction"]["page"]["scene"]) < brief.index(
            "Render every string in exact_visible_copy"
        )
        assert "visual_direction" not in data and "visual_concept" not in data
        assert "composition" not in data["deck_style"]
        assert all(identity not in image["prompt"] for identity in slide["citations"])
        assert slide["spec"]["content_elements"][0]["text"] in image["prompt"]


def test_art_changes_affect_only_the_selected_signature_and_removed_quote_is_not_invented():
    spec = semantic("quote")
    plan = direction().model_dump()
    plan.update(
        version="deck-art-v1", pages={"first": plan["pages"][0], "second": plan["pages"][1]}
    )
    plan["pages"]["first"]["form"] = "evidence_quote"
    deck = {
        "generation_metadata": {"generation_version": "deck-content-v5", "art_direction": plan},
        "style": {"palette": {"background": "#FFFFFF"}},
        "language": "en",
    }
    first = {
        "id": "first",
        "plan_json": json.dumps({"index": 1, "purpose": "Learn"}),
        "visual_revision": 0,
        "image_revision": 0,
        "visual_instruction": "",
        "image_instruction": "",
    }
    second = {**first, "id": "second"}
    before = page_signature(deck, second, spec)
    original = page_signature(deck, first, spec)
    plan["pages"]["first"]["surface"] = "light"
    assert page_signature(deck, first, spec) != original
    assert page_signature(deck, second, spec) == before
    updated = semantic()
    assert page_art(deck, first, updated)["page"]["form"] == "object_annotation"
    data = json.loads(page_prompt(deck, first, updated).split("PAGE DATA:\n")[1])
    assert "removed" in data["art_direction"]["page"]["scene"]
    assert data["exact_visible_copy"][1]["role"] == "statement"


def test_saved_v4_retains_exact_signature_and_prompt_without_new_art_planning():
    spec = semantic()
    slide = {
        "id": "old",
        "plan_json": json.dumps({"index": 1, "purpose": "Learn"}),
        "visual_revision": 0,
        "image_revision": 0,
        "visual_instruction": "",
        "image_instruction": "",
    }
    deck = {
        "generation_metadata": {"generation_version": "deck-content-v4"},
        "style": {"palette": {"background": "#FFFFFF"}},
        "language": "en",
    }
    expected = {
        "spec": spec.model_dump(),
        "style": deck["style"],
        "language": "en",
        "plan": json.loads(slide["plan_json"]),
        "visual_revision": 0,
        "image_revision": 0,
        "visual_instruction": "",
        "image_instruction": "",
        "version": "whole-page-v1",
        "size": "2048x1152",
    }
    assert (
        page_signature(deck, slide, spec)
        == hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()
    )
    assert "art_direction" not in page_prompt(deck, slide, spec)


def test_art_repairs_schema_and_content_eligibility_together_without_rewriting_valid_pages():
    import asyncio
    from types import SimpleNamespace

    from opennotelm.deck_art import diagnose_art
    from opennotelm.schemas import ModelInput
    from opennotelm.structured import structured_completion

    candidate = direction().model_dump()
    original = json.loads(json.dumps(candidate))
    candidate["pages"][0]["viewpoint"] = "low_level"
    candidate["pages"][6]["form"] = "branching_journey"
    specs = [semantic()] * 10
    calls = []

    async def text(config, key, messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return json.dumps(candidate)
        data = json.loads(messages[1]["content"])
        assert "literal_error" in data["validation_feedback"]
        assert "no supporting authored content" in data["validation_feedback"]
        assert ["pages", 0, "viewpoint"] in data["failed_paths"]
        assert ["pages", 6] in data["failed_paths"]
        return json.dumps(
            {
                "updates": [
                    {"path": ["pages", 0, "viewpoint"], "value": original["pages"][0]["viewpoint"]},
                    {"path": ["pages", 6], "value": original["pages"][6]},
                ]
            }
        )

    models = SimpleNamespace(
        configured=lambda role: (
            ModelInput(base_url="https://example.com/v1", model_id="test"),
            "",
        ),
        public_configs=lambda: {
            "models": {"language": {"capabilities": {"structured_output": "json_object"}}}
        },
        gateway=SimpleNamespace(text=text),
    )
    result = asyncio.run(
        structured_completion(
            models,
            "Art direct",
            {},
            DeckArt,
            validate=lambda value: validate_art(value, specs),
            diagnose=lambda value: diagnose_art(value, specs),
            max_attempts=3,
        )
    )
    assert result.model_dump() == original and len(calls) == 2


def test_deck_failure_report_includes_rules_without_cross_deck_data(pages_fixture):
    client, state, _ = pages_fixture
    notebook, _ = notebook_with_source(client)
    state["bad_art"] = True
    deck, job = new_page_deck(client, notebook)
    assert job["error_code"] == "DECK_ART_INVALID"
    response = client.get(f"/api/decks/{deck['id']}/diagnostics?download=true")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert "attachment" in response.headers["content-disposition"]
    report = response.json()
    assert len(report["slides"]) == 10
    assert report["jobs"][0]["stage"] == "art_directing"
    attempts = [a for a in report["attempts"] if a["stage"] == "DeckArt"]
    assert attempts and any(i["code"] == "art_variety" for i in attempts[0]["issues"])
    assert all(a["job_id"] == job["id"] for a in report["attempts"])
    assert all("prompt" not in a and "output" not in a for a in report["attempts"])
    assert client.get("/api/decks/does-not-exist/diagnostics").status_code == 404
    state["bad_art"] = False
    other, _ = new_page_deck(client, notebook)
    other_report = client.get(f"/api/decks/{other['id']}/diagnostics").json()
    assert all(a["job_id"] != job["id"] for a in other_report["attempts"])
