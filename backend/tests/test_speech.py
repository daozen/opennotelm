import asyncio
import base64

import httpx
import pytest
from audio_factory import sample_wav
from opennotelm import audio
from opennotelm.errors import AppError
from opennotelm.request_limits import ProviderBudgets
from opennotelm.schemas import ModelInput
from opennotelm.speech_adapter import SpeechAdapter


def test_compatible_and_native_speech_keep_roles_and_return_real_audio_bytes():
    async def scenario():
        requests = []

        def handle(request):
            import json

            body = json.loads(request.content)
            requests.append(body)
            if request.url.path.endswith("interactions"):
                return httpx.Response(
                    200,
                    json={
                        "steps": [
                            {
                                "type": "model_output",
                                "content": [
                                    {
                                        "type": "audio",
                                        "data": base64.b64encode(sample_wav()).decode(),
                                    }
                                ],
                            }
                        ]
                    },
                )
            return httpx.Response(200, content=sample_wav())

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            adapter = SpeechAdapter(client, ProviderBudgets(lambda: 2))
            config = ModelInput(
                base_url="http://local/v1", model_id="speech", voice_a="Ryan", voice_b="Vivian"
            )
            assert (
                await adapter.generate(config, "", [{"speaker": "B", "text": "One sentence."}])
                == sample_wav()
            )
            assert requests[-1]["voice"] == "Vivian"
            config.speech_protocol = "gemini"
            assert (
                await adapter.generate(
                    config, "", [{"speaker": "A", "text": "One."}, {"speaker": "B", "text": "Two."}]
                )
                == sample_wav()
            )
            assert requests[-1]["generation_config"]["speech_config"]["speakers"] == [
                {"speaker": "A", "voice": "Ryan"},
                {"speaker": "B", "voice": "Vivian"},
            ]
            assert requests[-1]["input"][0]["content"][1]["annotations"][0]["speaker"] == "B"

    asyncio.run(scenario())


def test_rate_limit_releases_provider_slot_before_retry_and_cancellation(monkeypatch):
    async def scenario():
        entered = asyncio.Event()
        budget = ProviderBudgets(lambda: 1)
        config = ModelInput(base_url="http://local/v1", model_id="speech")

        async def delay(seconds):
            assert budget.providers[("http", "local", 80)].active == 0
            entered.set()
            await asyncio.Event().wait()

        monkeypatch.setattr("opennotelm.speech_adapter.asyncio.sleep", delay)
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(429))
        ) as client:
            adapter = SpeechAdapter(client, budget)
            task = asyncio.create_task(
                adapter.generate(config, "", [{"speaker": "A", "text": "Test"}])
            )
            await asyncio.wait_for(entered.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert budget.providers[("http", "local", 80)].active == 0

    asyncio.run(scenario())


def test_bad_provider_content_is_not_exposed():
    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(400, text="PRIVATE_SOURCE_SENTINEL")
            )
        ) as client:
            adapter = SpeechAdapter(client, ProviderBudgets(lambda: 1))
            with pytest.raises(AppError, match="SPEECH_CONFIG_INVALID") as error:
                await adapter.generate(
                    ModelInput(base_url="http://local/v1", model_id="speech"),
                    "",
                    [{"speaker": "A", "text": "Test"}],
                )
            assert "PRIVATE_SOURCE_SENTINEL" not in error.value.message

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "body",
    [
        [],
        {"steps": [None]},
        {"steps": [{"type": "model_output", "content": [{"type": "audio", "data": "invalid"}]}]},
    ],
)
def test_malformed_native_speech_is_a_safe_actionable_failure(body):
    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))
        ) as client:
            adapter = SpeechAdapter(client, ProviderBudgets(lambda: 1))
            with pytest.raises(AppError, match="SPEECH_OUTPUT_INVALID"):
                await adapter.generate(
                    ModelInput(
                        base_url="http://local/v1", model_id="speech", speech_protocol="gemini"
                    ),
                    "",
                    [{"speaker": "A", "text": "Private text"}],
                )

    asyncio.run(scenario())


def test_audio_rejects_playlists_and_handles_owned_paths_with_apostrophes(tmp_path):
    async def scenario():
        root = tmp_path / "speaker's files"
        chunk = root / "chunks" / "voice.wav"
        with pytest.raises(AppError, match="SPEECH_OUTPUT_INVALID"):
            await audio.normalize(b"ffconcat version 1.0\nfile 'file:///private/audio.wav'", chunk)
        assert not chunk.exists()
        await audio.normalize(sample_wav(), chunk)
        result = root / "episode.mp3"
        assert len(await audio.assemble([chunk], result)) == 64
        assert result.stat().st_size > 0

    asyncio.run(scenario())
