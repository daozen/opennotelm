import asyncio
from types import SimpleNamespace

from opennotelm.schemas import ModelInput
from test_models import config


def test_oversized_synthesis_gets_actionable_repair_and_only_valid_output_is_cached(client):
    assert client.post("/api/settings/models/test", json=config()).status_code == 200
    calls = []

    async def text(model, key, messages, **kwargs):
        calls.append([dict(message) for message in messages])
        if len(calls) == 1:
            return "文" * 2800 + "[[E1]]"
        # This valid cited reduction exceeds the old arbitrary 1800-token ceiling,
        # but fits both the allocated output reserve and the total context budget.
        return "# Concise synthesis\n\n" + "文" * 2100 + " [[E1]]"

    client.app.state.models.gateway.text = text
    synthesis = client.app.state.knowledge.synthesis
    context = SimpleNamespace(job={"id": "repair-test"})
    # A real queued job provides the FK required by synthesis checkpoints.
    with client.app.state.db.connect() as conn:
        conn.execute(
            "INSERT INTO jobs(id,type,entity_id,status,stage,payload_json,created_at) "
            "VALUES ('repair-test','knowledge_generate','test','completed','completed',"
            "'{}','2026-01-01')"
        )
    output = asyncio.run(
        synthesis.complete(
            [{"id": "E1", "text": "Source-grounded insight"}],
            ModelInput(base_url="https://example.com/v1", model_id="test"),
            "",
            context,
            "reduce",
            compact=True,
        )
    )
    assert "Concise synthesis" in output
    assert len(calls) == 2
    assert "within 7998 UTF-8 bytes" in calls[0][0]["content"]
    assert "English words" in calls[0][0]["content"]
    assert "at most 7998 UTF-8 bytes" in calls[1][0]["content"]
    with client.app.state.db.connect() as conn:
        saved = conn.execute(
            "SELECT content FROM synthesis_checkpoints WHERE job_id='repair-test'"
        ).fetchone()[0]
    assert saved == output
    assert "文" * 2800 not in saved


def test_actual_token_count_accepts_complete_chinese_output_but_rejects_truncation(client):
    import pytest
    from opennotelm.errors import AppError
    from opennotelm.generation_attempts import RESPONSE_METADATA

    assert client.post("/api/settings/models/test", json=config()).status_code == 200
    synthesis = client.app.state.knowledge.synthesis
    with client.app.state.db.connect() as conn:
        conn.execute(
            "INSERT INTO jobs(id,type,entity_id,status,stage,payload_json,created_at) "
            "VALUES ('measured-test','deck_generate','test','completed','completed','{}','now')"
        )
    context = SimpleNamespace(job={"id": "measured-test"})
    count = 0
    truncated = False

    async def text(*args, **kwargs):
        nonlocal count
        count += 1
        RESPONSE_METADATA.set(
            {"completion_tokens": 2600, "finish_reason": "length" if truncated else "stop"}
        )
        # Estimate exceeds 2666, actual usage does not. It is not truncated or oversized.
        return "文" * 2800 + " [[E1]]"

    client.app.state.models.gateway.text = text

    async def complete(step):
        return await synthesis.complete(
            [{"id": "E1", "text": "Original"}],
            ModelInput(base_url="https://example.com/v1", model_id="test"),
            "",
            context,
            step,
            True,
        )

    assert asyncio.run(complete("valid")).endswith("[[E1]]")
    assert count == 1
    truncated = True
    with pytest.raises(AppError):
        asyncio.run(complete("truncated"))
    assert count == 3


def test_language_is_in_every_reduction_and_checkpoint_signature(client):
    import json

    from opennotelm.citations import CITATION_PATTERN

    assert client.post("/api/settings/models/test", json=config()).status_code == 200
    synthesis = client.app.state.knowledge.synthesis
    calls = []

    async def text(model, key, messages, **kwargs):
        calls.append(messages)
        request = json.loads(messages[-1]["content"])
        item = request["material"][0]
        marker = item.get("id") or item["evidence_ids"][0]
        return f"# Output\n\nShort explanation [[{marker}]]"

    client.app.state.models.gateway.text = text
    with client.app.state.db.connect() as conn:
        conn.execute(
            "INSERT INTO jobs(id,type,entity_id,status,stage,payload_json,created_at) "
            "VALUES ('lang-reduction','knowledge_generate','test','completed',"
            "'completed','{}','now')"
        )
    context = SimpleNamespace(job={"id": "lang-reduction"}, progress=lambda *args: None)
    blocks = [
        {
            "id": f"b{i}",
            "source_id": "s",
            "node_id": "n",
            "text": "Original material. " * 150,
            "type": "paragraph",
            "page_start": 1,
        }
        for i in range(12)
    ]
    output, evidence, metadata = asyncio.run(synthesis.run(blocks, context, output_language="ja"))
    assert metadata["reduction_levels"] > 0
    assert metadata["language"] == "ja"
    for call in calls:
        assert "Japanese" in call[0]["content"]
        assert json.loads(call[-1]["content"])["output_language"] == "ja"
    assert set(CITATION_PATTERN.findall(output)) <= {e["id"] for e in evidence}
    previous_calls = len(calls)
    asyncio.run(synthesis.run(blocks, context, output_language="ja"))
    assert len(calls) == previous_calls
    asyncio.run(synthesis.run(blocks, context, output_language="ar"))
    assert len(calls) > previous_calls
    assert all("Arabic" in call[0]["content"] for call in calls[previous_calls:])
