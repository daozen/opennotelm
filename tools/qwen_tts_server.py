"""Local OpenAI-compatible Speech adapter for official Qwen3-TTS CustomVoice weights.

Run with the isolated environment described in docs/QWEN_TTS.md. No source text is logged.
"""

import asyncio
import hashlib
import io
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

MODEL_ID = "Qwen3-TTS-12Hz-0.6B-CustomVoice"
SPEECH_POLICY = "podcast-stable-v1"
LANGUAGES = {
    "zh-CN": "Chinese",
    "zh-TW": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "de": "German",
    "fr": "French",
    "ru": "Russian",
    "pt-BR": "Portuguese",
    "es": "Spanish",
}
ROOT = Path(
    os.environ.get(
        "QWEN_TTS_ROOT", str(Path(__file__).resolve().parents[1] / ".local-services/qwen3-tts")
    )
)


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str
    input: str = Field(min_length=1, max_length=3500)
    voice: str = "Vivian"
    response_format: str = "wav"


def inference_options(policy, language, speaker):
    if policy is None:
        return {"language": "Auto", "max_new_tokens": 2048}, None
    if policy != SPEECH_POLICY:
        raise HTTPException(400, "Unsupported speech policy.")
    if language not in LANGUAGES:
        raise HTTPException(400, "Choose a language supported by this local model.")
    # A voice has one seed across requests; request order/text hash must not change it.
    seed = int.from_bytes(hashlib.sha256(speaker.lower().encode()).digest()[:4], "big")
    return {
        "language": LANGUAGES[language],
        "max_new_tokens": 2048,
        "do_sample": True,
        "temperature": 0.7,
        "top_p": 0.9,
        "subtalker_dosample": True,
        "subtalker_temperature": 0.7,
        "subtalker_top_p": 0.9,
    }, seed


def generate_audio(model, data, options, seed):
    import soundfile
    import torch

    # Called under the inference lock. fork_rng doesn't save the MPS generator, so
    # preserve it explicitly too; failed/cancelled calls must not perturb legacy jobs.
    if seed is None:
        waveforms, rate = model.generate_custom_voice(
            text=data.input, speaker=data.voice, **options
        )
    else:
        mps_state = torch.mps.get_rng_state() if torch.backends.mps.is_available() else None
        try:
            with torch.random.fork_rng():
                torch.manual_seed(seed)
                waveforms, rate = model.generate_custom_voice(
                    text=data.input, speaker=data.voice, **options
                )
        finally:
            if mps_state is not None:
                torch.mps.set_rng_state(mps_state)
    output = io.BytesIO()
    soundfile.write(output, waveforms[0], rate, format="WAV", subtype="PCM_16")
    return output.getvalue()


def create_app():
    @asynccontextmanager
    async def lifespan(app):
        import torch
        from qwen_tts import Qwen3TTSModel

        torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))
        device = os.environ.get(
            "QWEN_TTS_DEVICE", "mps" if torch.backends.mps.is_available() else "cpu"
        )
        app.state.model = await asyncio.to_thread(
            Qwen3TTSModel.from_pretrained,
            str(ROOT / "model"),
            device_map=device,
            dtype=torch.float32,
            attn_implementation="sdpa",
            local_files_only=True,
        )
        app.state.device = device
        app.state.speakers = sorted(app.state.model.get_supported_speakers())
        app.state.languages = sorted(app.state.model.get_supported_languages())
        app.state.lock = asyncio.Lock()
        app.state.pending = 0
        yield

    app = FastAPI(lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        return JSONResponse(
            {"error": "Check speech model, voice, format and input length."}, status_code=422
        )

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "device": app.state.device,
            "pending": app.state.pending,
            "speech_policies": [SPEECH_POLICY],
        }

    @app.get("/v1/models")
    async def models():
        return {
            "object": "list",
            "data": [{"id": MODEL_ID, "object": "model", "owned_by": "local"}],
        }

    @app.get("/v1/voices")
    async def voices():
        return {"voices": app.state.speakers, "languages": app.state.languages}

    @app.post("/v1/audio/speech")
    async def speech(
        data: SpeechRequest,
        policy: Annotated[str | None, Header(alias="X-OpenNoteLM-Speech-Policy")] = None,
        language: Annotated[str | None, Header(alias="X-OpenNoteLM-Speech-Language")] = None,
    ):
        if data.model not in (MODEL_ID, "Qwen/" + MODEL_ID) or data.response_format != "wav":
            raise HTTPException(400, "Choose this service's model and WAV format.")
        if data.voice.lower() not in {s.lower() for s in app.state.speakers}:
            raise HTTPException(400, "Unsupported voice. See /v1/voices.")
        if re.search(r"[\u0600-\u06ff\u0900-\u097f]", data.input):
            raise HTTPException(400, "Arabic and Hindi are not supported by this model.")
        if not data.input.strip():
            raise HTTPException(400, "Speech input cannot be blank.")
        options, seed = inference_options(policy, language, data.voice)
        if app.state.pending >= 8:
            raise HTTPException(
                429, "The local speech queue is full.", headers={"Retry-After": "2"}
            )
        app.state.pending += 1
        try:
            async with app.state.lock:
                # Join inference on cancellation before another request uses the model.
                task = asyncio.create_task(
                    asyncio.to_thread(generate_audio, app.state.model, data, options, seed)
                )
                try:
                    result = await asyncio.shield(task)
                except asyncio.CancelledError:
                    await asyncio.gather(task, return_exceptions=True)
                    raise
                except Exception:
                    raise HTTPException(502, "Local speech synthesis failed.") from None
            return Response(result, media_type="audio/wav", headers={"Cache-Control": "no-store"})
        finally:
            app.state.pending -= 1

    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8320, access_log=False)
