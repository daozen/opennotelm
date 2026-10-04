import asyncio
import json
import time

import httpx
from opennotelm.gateway import ModelGateway
from opennotelm.generation_attempts import JOB_DIAGNOSTICS, RESPONSE_METADATA, record_attempt
from opennotelm.output_repair import FieldValidationError
from opennotelm.schemas import ModelInput


def test_model_usage_is_task_local_under_out_of_order_requests():
    async def scenario():
        async def provider(request):
            index = int(json.loads(request.content)["messages"][0]["content"])
            await asyncio.sleep(0.01 if index == 1 else 0)
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": str(index)}, "finish_reason": "stop"}],
                    "usage": {"completion_tokens": index, "unsafe_provider_field": "PRIVATE"},
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(provider)) as client:
            gateway = ModelGateway(client)

            async def call(index):
                await gateway.text(
                    ModelInput(base_url="https://example.com/v1", model_id="test"),
                    "",
                    [{"role": "user", "content": str(index)}],
                )
                return RESPONSE_METADATA.get()

            results = await asyncio.gather(call(1), call(2))
            assert [r["completion_tokens"] for r in results] == [1, 2]
            assert all("unsafe_provider_field" not in r for r in results)

    asyncio.run(scenario())


def test_diagnostic_attempts_never_store_content_unknown_field_names_or_rejected_values(client):
    jobs = client.app.state.jobs
    job = jobs.enqueue("deck_generate", "diagnostic", {})
    token = JOB_DIAGNOSTICS.set((client.app.state.db, job["id"]))
    metadata = RESPONSE_METADATA.set({"finish_reason": "stop", "completion_tokens": 12})
    try:
        record_attempt(
            "DeckPlan",
            time.monotonic(),
            1,
            outcome="invalid",
            errors=[
                FieldValidationError(
                    "PRIVATE_SOURCE_VALUE", [["PRIVATE_FIELD"], ["slides", 0, "evidence_ids"]]
                )
            ],
        )
        record_attempt("deck", time.monotonic(), 0, outcome="visual_cache_hit")
    finally:
        JOB_DIAGNOSTICS.reset(token)
        RESPONSE_METADATA.reset(metadata)
    report = client.get("/api/diagnostics").json()
    assert "PRIVATE" not in json.dumps(report)
    attempt = next(a for a in report["generation_attempts"] if a["stage"] == "DeckPlan")
    assert attempt["field_paths"] == [["slides", 0, "evidence_ids"]]
    assert attempt["validation_codes"] == ["field"]
    cached = next(a for a in report["generation_attempts"] if a["stage"] == "deck")
    assert "completion_tokens" not in cached


def test_attempt_details_include_safe_schema_rules_and_transport_failures(client):
    from types import SimpleNamespace

    import pytest
    from opennotelm.deck_art import PageArt
    from opennotelm.errors import AppError
    from opennotelm.structured import structured_completion
    from pydantic import ValidationError

    jobs = client.app.state.jobs
    job = jobs.enqueue("deck_generate", "diagnostic", {})
    token = JOB_DIAGNOSTICS.set((client.app.state.db, job["id"]))
    try:
        try:
            PageArt.model_validate({"scene": "PRIVATE" * 100, "PRIVATE_FIELD": "SECRET"})
        except ValidationError as error:
            record_attempt("DeckArt", time.monotonic(), 1, outcome="invalid", errors=[error])

        async def failing(request):
            return httpx.Response(429, json={"error": "PRIVATE_PROVIDER_RESPONSE"})

        async def run():
            async with httpx.AsyncClient(transport=httpx.MockTransport(failing)) as transport:
                models = SimpleNamespace(
                    configured=lambda role: (
                        ModelInput(base_url="https://secret.example/v1", model_id="test"),
                        "SECRET_KEY",
                    ),
                    public_configs=lambda: {
                        "models": {
                            "language": {"capabilities": {"structured_output": "json_object"}}
                        }
                    },
                    gateway=ModelGateway(transport),
                )
                with pytest.raises(AppError):
                    await structured_completion(models, "PRIVATE_PROMPT", {}, PageArt)

        asyncio.run(run())
    finally:
        JOB_DIAGNOSTICS.reset(token)
    report = client.get("/api/diagnostics").json()
    assert not any(
        secret in json.dumps(report) for secret in ("PRIVATE", "SECRET", "secret.example")
    )
    failed = next(a for a in report["generation_attempts"] if a["outcome"] == "request_failed")
    assert failed["http_status"] == 429 and failed["error_code"] == "MODEL_CONNECTION_FAILED"
    invalid = next(a for a in report["generation_attempts"] if a["outcome"] == "invalid")
    assert {"code": "string_too_long", "path": ["scene"], "max_length": 220} in invalid["issues"]


def test_corrupt_attempt_metadata_is_filtered_and_copy_counts_survive():
    from opennotelm.generation_attempts import safe_attempt, safe_validation

    metadata = {
        "outcome": ["PRIVATE"],
        "issues": [{"code": {"PRIVATE": "SECRET"}, "path": ["PRIVATE"]}],
        "field_paths": None,
        "validation_codes": {"PRIVATE": "SECRET"},
        "error_code": [],
        "prompt_tokens": "SECRET",
        "source": "PRIVATE",
        "http_status": 429,
    }
    assert "PRIVATE" not in json.dumps(safe_attempt(metadata))
    assert safe_attempt(metadata)["http_status"] == 429
    values = safe_validation(
        [
            FieldValidationError(
                "PRIVATE",
                [["content_elements"]],
                progress=50,
                details={"ceiling": 300, "source": "PRIVATE"},
            )
        ]
    )
    assert values["issues"] == [
        {
            "code": "copy_budget",
            "path": ["content_elements"],
            "max_length": 300,
            "actual_length": 350,
        }
    ]
    assert "PRIVATE" not in json.dumps(values)
