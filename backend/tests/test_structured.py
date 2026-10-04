import asyncio
import json
from types import SimpleNamespace

import pytest
from opennotelm.deck_schemas import DeckBrief
from opennotelm.errors import AppError
from opennotelm.schemas import ModelInput
from opennotelm.structured import structured_completion


def test_repair_explains_schema_and_semantic_errors_without_repeating_source():
    calls = []
    brief = {
        "topic": "Document knowledge",
        "goal": "Explain source-grounded learning",
        "audience": "Readers",
        "language": "zh-CN",
        "slide_count": 15,
        "content_principles": ["Use original citations"],
    }

    async def text(config, key, messages, **kwargs):
        calls.append([dict(message) for message in messages])
        return json.dumps({**brief, "language": "简体中文（zh-CN）"} if len(calls) == 1 else brief)

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

    def validate(value):
        if value.language != "zh-CN":
            raise ValueError("language must equal the exact code 'zh-CN'")

    result = asyncio.run(
        structured_completion(
            models,
            "Create a DeckBrief.",
            {"source": "private source"},
            DeckBrief,
            validate=validate,
        )
    )
    assert result.language == "zh-CN"
    assert len(calls) == 2
    assert "exact code 'zh-CN'" in json.loads(calls[1][1]["content"])["validation_feedback"]
    assert json.loads(calls[1][1]["content"])["source"] == "private source"
    assert json.loads(calls[1][1]["content"])["candidate_data"]["language"] == "简体中文（zh-CN）"
    assert "private source" not in calls[1][0]["content"]


def test_repair_remains_bounded_and_does_not_echo_invalid_input():
    calls = []

    async def text(config, key, messages, **kwargs):
        calls.append([dict(message) for message in messages])
        return json.dumps({"topic": "untrusted-output-sentinel" * 30})

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
    with pytest.raises(AppError) as error:
        asyncio.run(structured_completion(models, "Create a DeckBrief.", {}, DeckBrief))
    assert error.value.code == "MODEL_STRUCTURED_OUTPUT_INVALID"
    assert len(calls) == 2
    assert "string_too_long" in json.loads(calls[1][1]["content"])["validation_feedback"]
    assert "untrusted-output-sentinel" not in calls[1][0]["content"]


def test_repair_patch_changes_only_diagnosed_field():
    from opennotelm.output_repair import EvidenceValidationError

    calls = []
    brief = {
        "topic": "Keep this topic",
        "goal": "Keep this goal",
        "audience": "Readers",
        "language": "wrong",
        "slide_count": 15,
        "content_principles": ["Keep exact original citations"],
    }

    async def text(config, key, messages, **kwargs):
        calls.append(messages)
        return json.dumps(
            brief if len(calls) == 1 else {"updates": [{"path": ["language"], "value": "zh-CN"}]}
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

    def validate(value):
        if value.language != "zh-CN":
            raise EvidenceValidationError([["language"]], {"wrong"}, {"zh-CN"})

    result = asyncio.run(
        structured_completion(models, "Create a DeckBrief.", {}, DeckBrief, validate=validate)
    )
    assert (
        result.language == "zh-CN"
        and result.topic == brief["topic"]
        and result.goal == brief["goal"]
    )
    assert len(calls) == 2


def test_extra_page_repair_requires_validation_progress():
    from opennotelm.output_repair import FieldValidationError

    async def scenario(improve):
        calls = []
        brief = {
            "topic": "Keep topic",
            "goal": "Keep goal",
            "audience": "Readers",
            "language": "zh-CN",
            "slide_count": 15,
            "content_principles": ["Keep citations"],
        }

        async def text(config, key, messages, **kwargs):
            calls.append(messages)
            if len(calls) == 1:
                return json.dumps(brief)
            return json.dumps(
                {
                    "updates": [
                        {"path": ["topic"], "value": "Short title" if len(calls) == 2 else "Short"}
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

        def validate(value):
            if value.topic != "Short":
                progress = 5 if improve and value.topic == "Short title" else 20
                raise FieldValidationError("Shorten title", [["topic"]], progress=progress)

        if improve:
            result = await structured_completion(
                models, "Create brief", {}, DeckBrief, validate=validate, max_attempts=3
            )
            assert result.topic == "Short" and result.goal == "Keep goal" and len(calls) == 3
        else:
            with pytest.raises(AppError):
                await structured_completion(
                    models, "Create brief", {}, DeckBrief, validate=validate, max_attempts=3
                )
            assert len(calls) == 2

    asyncio.run(scenario(True))
    asyncio.run(scenario(False))


def test_page_repair_gets_all_detectable_constraints_in_one_feedback():
    from opennotelm.deck_content import check_content_basis
    from opennotelm.deck_schemas import SlideSpec
    from opennotelm.deck_validation import diagnose_page

    calls = []
    candidate = {
        "key_message": "Preserve the original message",
        "content_elements": [
            {
                "id": "main",
                "type": "statement",
                "text": "解释" * 100,
                "basis": "background",
                "citations": ["E1"],
            },
            {"id": "compare", "type": "comparison", "label": "对比"},
        ],
        "visual_direction": {
            "composition_intent": "clear",
            "hierarchy": ["main", "compare"],
            "visual_balance": "balanced",
            "image_role": "diagram",
            "background_direction": "plain",
            "emphasis": "main",
            "density": "low",
            "mood": "calm",
        },
        "asset_requests": [],
        "visual_relationships": [],
    }
    repaired = [
        {
            "id": "main",
            "type": "statement",
            "text": "原文说明",
            "basis": "source",
            "citations": ["E1"],
        }
    ]

    async def text(config, key, messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return json.dumps(candidate)
        data = json.loads(messages[1]["content"])
        assert "complete JSON object" in messages[0]["content"]
        assert "structured items" in data["validation_feedback"]
        assert "cannot" in data["validation_feedback"]
        assert "ceiling" in data["validation_feedback"]
        assert data["failed_paths"] == [
            ["content_elements"],
            ["visual_relationships"],
            ["visual_direction", "hierarchy"],
        ]
        # Gateways may return full JSON instead of patches. Removing a diagnosed element
        # must not leave stale descendant paths or dangling hierarchy references.
        return json.dumps(
            {
                **candidate,
                "key_message": "Unrequested change",
                "content_elements": repaired,
                "visual_direction": {**candidate["visual_direction"], "hierarchy": ["main"]},
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
            "Author page",
            {},
            SlideSpec,
            validate=check_content_basis,
            diagnose=lambda value: diagnose_page(value, allowed={"E1"}, budget=100),
            repair_format="full",
        )
    )
    assert result.key_message == candidate["key_message"] and len(calls) == 2
    assert result.visual_direction.hierarchy == ["main"]
    assert not diagnose_page(result.model_dump(), allowed={"E1"}, budget=100)


def test_unlocated_semantic_failure_requests_full_json_instead_of_an_empty_patch():
    calls = []
    value = dict(
        topic="Topic",
        goal="Goal",
        audience="Readers",
        language="zh-CN",
        slide_count=15,
        content_principles=["Grounded"],
    )

    async def text(config, key, messages, **kwargs):
        calls.append(messages)
        if len(calls) > 1:
            assert "Return the complete JSON object" in messages[0]["content"]
            return json.dumps({**value, "topic": "Corrected topic"})
        return json.dumps(value)

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

    def check(result):
        if result.topic == "Topic":
            raise ValueError("Use a more specific topic")

    result = asyncio.run(
        structured_completion(models, "Create brief", {}, DeckBrief, validate=check)
    )
    assert result.topic == "Corrected topic" and len(calls) == 2


def test_auto_repair_requests_only_the_bad_field_for_small_errors():
    from opennotelm.output_repair import FieldValidationError

    calls = []
    brief = dict(
        topic="Keep topic",
        goal="Keep goal",
        audience="Readers",
        language="incorrect",
        slide_count=15,
        content_principles=["Keep citations"],
    )

    async def text(config, key, messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return json.dumps(brief)
        assert "return only" in messages[0]["content"]
        assert "Return the complete JSON object" not in messages[0]["content"]
        return json.dumps({"updates": [{"path": ["language"], "value": "zh-CN"}]})

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

    def check(value):
        if value.language != "zh-CN":
            raise FieldValidationError("Use exact language code", [["language"]])

    result = asyncio.run(
        structured_completion(
            models,
            "Create brief",
            {},
            DeckBrief,
            validate=check,
            repair_format="auto",
        )
    )
    assert result.topic == brief["topic"] and result.language == "zh-CN" and len(calls) == 2
