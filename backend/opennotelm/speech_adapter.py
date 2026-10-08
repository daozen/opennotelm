"""Bounded server-only Speech protocols; never log speech text or provider bodies."""

import asyncio
import base64
import json
import time

import httpx

from .errors import AppError
from .generation_attempts import RESPONSE_METADATA, record_attempt

MAX_RESPONSE_BYTES = 32 * 1024 * 1024
SPEECH_POLICY = "podcast-stable-v1"


class SpeechAdapter:
    def __init__(self, client, budgets):
        self.client, self.budgets = client, budgets

    async def generate(self, config, key, turns, *, language=None, policy=None):
        if config.speech_protocol == "gemini":
            names = list(dict.fromkeys(turn["speaker"] for turn in turns))
            voices = {"A": config.voice_a, "B": config.voice_b}
            speech = (
                {
                    "speakers": [{"speaker": name, "voice": voices[name]} for name in names],
                    "mode": "conversational",
                }
                if len(names) == 2
                else [{"voice": voices[names[0]]}]
            )
            path = "interactions"
            headers = {"x-goog-api-key": key} if key else {}
            payload = {
                "model": config.model_id,
                "input": [
                    {
                        "type": "user_input",
                        "content": [
                            {
                                "type": "text",
                                "text": turn["text"],
                                "annotations": [
                                    {"type": "speech_metadata", "speaker": turn["speaker"]}
                                ],
                            }
                            for turn in turns
                        ],
                    }
                ],
                "response_format": {"type": "audio"},
                "generation_config": {"speech_config": speech},
            }
        else:
            if len(turns) != 1:
                raise AppError(
                    "SPEECH_PROTOCOL_INVALID",
                    "This speech protocol accepts one speaker per request.",
                )
            path = "audio/speech"
            headers = {"Authorization": f"Bearer {key}"} if key else {}
            # Optional HTTP extensions used by our local adapter. Standard Speech bodies
            # stay portable; providers that don't implement these headers can ignore them.
            if policy:
                headers["X-OpenNoteLM-Speech-Policy"] = policy
                if language:
                    headers["X-OpenNoteLM-Speech-Language"] = language
            payload = {
                "model": config.model_id,
                "input": turns[0]["text"],
                "voice": config.voice_a if turns[0]["speaker"] == "A" else config.voice_b,
                "response_format": "wav",
            }
        started = time.monotonic()
        RESPONSE_METADATA.set({})
        for attempt in range(3):
            try:
                async with self.budgets.slot(config):
                    async with self.client.stream(
                        "POST", f"{config.base_url}/{path}", headers=headers, json=payload
                    ) as response:
                        RESPONSE_METADATA.set({"http_status": response.status_code})
                        if response.status_code == 429 or response.status_code >= 500:
                            record_attempt(
                                "podcast_speech",
                                started,
                                attempt + 1,
                                outcome="request_failed",
                                error_code="SPEECH_RATE_LIMITED"
                                if response.status_code == 429
                                else "SPEECH_CONNECTION_FAILED",
                            )
                            if attempt < 2:
                                try:
                                    delay = min(
                                        15,
                                        max(
                                            0.2,
                                            float(response.headers.get("retry-after", 2**attempt)),
                                        ),
                                    )
                                except ValueError:
                                    delay = 2**attempt
                            else:
                                raise AppError(
                                    "SPEECH_RATE_LIMITED"
                                    if response.status_code == 429
                                    else "SPEECH_CONNECTION_FAILED",
                                    (
                                        "The speech service is busy or unavailable. "
                                        "Saved audio can be resumed."
                                    ),
                                    502,
                                )
                        elif response.is_error:
                            record_attempt(
                                "podcast_speech",
                                started,
                                attempt + 1,
                                outcome="request_failed",
                                error_code="SPEECH_CONFIG_INVALID",
                            )
                            raise AppError(
                                "SPEECH_CONFIG_INVALID",
                                (
                                    "The service rejected the model, voice or request. "
                                    "Check speech settings."
                                ),
                                502,
                            )
                        else:
                            data = bytearray()
                            async for part in response.aiter_bytes():
                                if len(data) + len(part) > MAX_RESPONSE_BYTES:
                                    raise AppError(
                                        "SPEECH_OUTPUT_INVALID",
                                        "The speech response exceeded the safe size limit.",
                                        502,
                                    )
                                data.extend(part)
                            if config.speech_protocol == "gemini":
                                body = json.loads(data)
                                audio = [
                                    part
                                    for step in body.get("steps", [])
                                    if step.get("type") == "model_output"
                                    for part in step.get("content", [])
                                    if part.get("type") == "audio"
                                ]
                                if len(audio) != 1:
                                    raise ValueError
                                data = base64.b64decode(audio[-1]["data"], validate=True)
                            if not data or bytes(data[:1]) in (b"{", b"<"):
                                raise ValueError
                            record_attempt("podcast_speech", started, attempt + 1, outcome="valid")
                            return bytes(data)
                await asyncio.sleep(delay)
            except httpx.TimeoutException as exc:
                record_attempt(
                    "podcast_speech",
                    started,
                    attempt + 1,
                    outcome="request_failed",
                    error_code="SPEECH_TIMEOUT",
                )
                if attempt == 2:
                    raise AppError(
                        "SPEECH_TIMEOUT",
                        "The speech request timed out. Resume to retry missing audio.",
                        502,
                    ) from exc
                await asyncio.sleep(2**attempt)
            except httpx.HTTPError as exc:
                raise AppError(
                    "SPEECH_CONNECTION_FAILED", "The speech endpoint could not be reached.", 502
                ) from exc
            except (ValueError, TypeError, KeyError, AttributeError) as exc:
                raise AppError(
                    "SPEECH_OUTPUT_INVALID", "The service did not return usable audio.", 502
                ) from exc
        raise AppError("SPEECH_CONNECTION_FAILED", "Speech generation failed.", 502)
