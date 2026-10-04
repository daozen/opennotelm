import base64
import json
import math
from io import BytesIO

import httpx
from PIL import Image, ImageDraw

from .errors import AppError
from .generation_attempts import RESPONSE_METADATA
from .image_adapter import OpenAIImagesAdapter
from .request_limits import ProviderBudgets
from .schemas import ModelInput


class ModelGateway:
    """Only layer allowed to communicate with AI endpoints."""

    def __init__(self, client: httpx.AsyncClient, request_limit=None):
        self.client = client
        self.budgets = ProviderBudgets(request_limit or (lambda: 8))
        self.images = OpenAIImagesAdapter(client, budgets=self.budgets)

    async def request(self, config: ModelInput, key: str, path: str, payload=None):
        async with self.budgets.slot(config):
            return await self._request(config, key, path, payload)

    async def _request(self, config: ModelInput, key: str, path: str, payload=None):
        try:
            response = await self.client.request(
                "GET" if payload is None else "POST",
                f"{config.base_url}/{path}",
                headers={"Authorization": f"Bearer {key}"} if key else {},
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as exc:
            raise AppError(
                "MODEL_TIMEOUT", "The model request timed out. Retry the test.", 502
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            if isinstance(exc, httpx.HTTPStatusError):
                RESPONSE_METADATA.set({"http_status": exc.response.status_code})
            raise AppError(
                "MODEL_CONNECTION_FAILED",
                "The endpoint request failed. Check URL, key and model.",
                502,
            ) from exc

    async def text(
        self,
        config: ModelInput,
        key: str,
        messages: list,
        structured: bool = False,
        max_output_tokens: int | None = None,
    ):
        RESPONSE_METADATA.set({})
        payload = {"model": config.model_id, "messages": messages}
        if max_output_tokens is not None:
            payload["max_tokens"] = max_output_tokens
        if structured:
            payload["response_format"] = {"type": "json_object"}
        result = await self.request(config, key, "chat/completions", payload)
        try:
            choice = result["choices"][0]
            if not isinstance(choice, dict):
                raise ValueError
            usage = result.get("usage")
            usage = usage if isinstance(usage, dict) else {}
            RESPONSE_METADATA.set(
                {
                    "finish_reason": choice.get("finish_reason")
                    if choice.get("finish_reason")
                    in ("stop", "length", "content_filter", "tool_calls")
                    else "unknown",
                    **{
                        name: usage[name]
                        for name in ("prompt_tokens", "completion_tokens", "total_tokens")
                        if type(usage.get(name)) is int and 0 <= usage[name] <= 10_000_000
                    },
                }
            )
            value = choice["message"]["content"]
            if not isinstance(value, str) or not value.strip():
                raise ValueError
            return value
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AppError("MODEL_RESPONSE_INVALID", "The model did not return text.", 502) from exc

    async def structured_probe(self, config: ModelInput, key: str):
        messages = [{"role": "user", "content": 'Return exactly this JSON object: {"ok":true}'}]
        mode = "json_object"
        try:
            output = await self.text(config, key, messages, structured=True)
        except AppError as error:
            if error.code != "MODEL_CONNECTION_FAILED":
                raise
            # Compatible endpoints may only support prompt-required JSON.
            mode = "prompt_json"
            output = await self.text(config, key, messages)
        for attempt in range(2):
            try:
                value = json.loads(output)
                if value == {"ok": True}:
                    return mode
            except (ValueError, TypeError):
                pass
            if attempt == 0:
                output = await self.text(
                    config,
                    key,
                    messages
                    + [
                        {
                            "role": "user",
                            "content": 'Repair the output. Only return {"ok":true}, no prose.',
                        }
                    ],
                )
        raise AppError(
            "MODEL_STRUCTURED_OUTPUT_INVALID", "The model failed the structured JSON test.", 502
        )

    async def embeddings(self, config: ModelInput, key: str, texts: list[str]) -> list[list[float]]:
        result = await self.request(
            config, key, "embeddings", {"model": config.model_id, "input": texts}
        )
        try:
            data = sorted(result["data"], key=lambda item: item["index"])
            if len(data) != len(texts) or [d["index"] for d in data] != list(range(len(texts))):
                raise ValueError
            vectors = [item["embedding"] for item in data]
            dimension = len(vectors[0])
            if not dimension or dimension > 65536:
                raise ValueError
            for vector in vectors:
                if (
                    len(vector) != dimension
                    or not all(
                        isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v)
                        for v in vector
                    )
                    or not any(v != 0 for v in vector)
                ):
                    raise ValueError
            return vectors
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AppError(
                "EMBEDDING_OUTPUT_INVALID", "The endpoint returned invalid vectors.", 502
            ) from exc

    async def vision_probe(self, config, key):
        picture = Image.new("RGB", (600, 200), "white")
        ImageDraw.Draw(picture).text((35, 65), "VISION 27", fill="black", font_size=60)
        raw = BytesIO()
        picture.save(raw, format="PNG")
        result = await self.text(
            config,
            key,
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Read the large text in this image. Return only that text.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64,"
                                + base64.b64encode(raw.getvalue()).decode()
                            },
                        },
                    ],
                }
            ],
            max_output_tokens=128,
        )
        if "".join(result.upper().split()).strip('"`') != "VISION27":
            raise AppError(
                "MODEL_VISION_UNAVAILABLE",
                "The saved language model did not pass the image-reading test.",
                502,
            )
        return True

    async def test(self, role: str, config: ModelInput, key: str) -> dict:
        if role == "language":
            await self.text(config, key, [{"role": "user", "content": "Reply with OK."}])
            mode = await self.structured_probe(config, key)
            return {"connection": True, "text_generation": True, "structured_output": mode}
        if role == "embedding":
            vectors = await self.embeddings(config, key, ["OpenNoteLM capability test"])
            return {"connection": True, "embedding_output": True, "dimensions": len(vectors[0])}
        await self.images.generate(config, key, "A simple blue circle on a white background.")
        return {"connection": True, "image_generation": True}
