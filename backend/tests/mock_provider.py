"""Deterministic provider used ONLY by browser integration tests."""

import asyncio
import copy

from fastapi import FastAPI, HTTPException
from grounded_provider import completion, embedding
from image_factory import image_response

app = FastAPI()


@app.post("/batch/")
def telemetry():
    # Acceptance-only receiver; no event storage or external transmission.
    return {"status": "ok"}


@app.get("/v1/models")
def models():
    return {"data": [{"id": "test-model"}]}


@app.post("/v1/chat/completions")
def chat(payload: dict):
    # Deck interpretation can now attach originals. Only the transcription/probe
    # paths should receive synthetic OCR output; other fixtures consume JSON text.
    messages = payload["messages"]
    content = messages[-1]["content"]
    if (
        isinstance(content, list)
        and messages[0]["role"] != "user"
        and not messages[0]["content"].startswith("Transcribe one document image")
    ):
        payload = copy.deepcopy(payload)
        payload["messages"][-1]["content"] = content[0]["text"]
    return {"choices": [{"message": {"content": completion(payload)}}]}


@app.post("/v1/embeddings")
async def embeddings(payload: dict):
    if payload["input"] != ["OpenNoteLM capability test"]:
        if payload.get("model") == "slow-embeddings":
            await asyncio.sleep(1)
        if payload.get("model") == "embedding-fails-after-probe":
            raise HTTPException(503, "Synthetic embedding failure")
    return {
        "data": [
            {"index": i, "embedding": embedding(text)} for i, text in enumerate(payload["input"])
        ]
    }


@app.post("/v1/images/generations")
async def images(payload: dict):
    if (
        payload.get("model") == "slow-images"
        and payload.get("prompt") != "A simple blue circle on a white background."
    ):
        await asyncio.sleep(0.8)
    if (
        payload.get("model") == "image-fails-after-probe"
        and payload.get("prompt") != "A simple blue circle on a white background."
    ):
        raise HTTPException(503, "Synthetic image failure")
    return image_response(payload.get("size"))
