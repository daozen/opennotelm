"""Exercise the optional HTTP adapter without installing Torch/model weights in the app."""

import importlib.util
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from audio_factory import sample_wav
from fastapi import HTTPException
from fastapi.testclient import TestClient

spec = importlib.util.spec_from_file_location(
    "local_qwen_adapter", Path(__file__).parents[2] / "tools/qwen_tts_server.py"
)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def test_policy_keeps_voice_seed_across_texts_and_rejects_unsupported_language():
    options, seed = adapter.inference_options(adapter.SPEECH_POLICY, "zh-CN", "Uncle_Fu")
    assert options["language"] == "Chinese"
    assert options["temperature"] < 0.9
    assert options["subtalker_temperature"] < 0.9
    assert seed == adapter.inference_options(adapter.SPEECH_POLICY, "zh-TW", "uncle_fu")[1]
    assert seed != adapter.inference_options(adapter.SPEECH_POLICY, "zh-CN", "Serena")[1]
    assert adapter.inference_options(None, "zh-CN", "Serena") == (
        {"language": "Auto", "max_new_tokens": 2048},
        None,
    )
    for policy, language in (("unknown", "en"), (adapter.SPEECH_POLICY, "ar")):
        with pytest.raises(HTTPException) as error:
            adapter.inference_options(policy, language, "Serena")
        assert error.value.status_code == 400


def test_optional_service_preserves_roles_and_rejects_invalid_policy_safely(monkeypatch):
    import sys

    class Model:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

        def get_supported_speakers(self):
            return ["Uncle_Fu", "Serena"]

        def get_supported_languages(self):
            return ["Auto", "Chinese", "English"]

    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            float32="float32",
            set_num_threads=lambda n: None,
            backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False)),
        ),
    )
    monkeypatch.setitem(sys.modules, "qwen_tts", SimpleNamespace(Qwen3TTSModel=Model))
    calls, active = [], 0
    lock = threading.Lock()

    def synthesize(model, data, options, seed):
        nonlocal active
        with lock:
            active += 1
            assert active == 1
        calls.append((data.voice, options, seed))
        with lock:
            active -= 1
        return sample_wav()

    monkeypatch.setattr(adapter, "generate_audio", synthesize)
    body = {"model": adapter.MODEL_ID, "input": "PRIVATE_TEXT_SENTINEL", "voice": "Uncle_Fu"}
    with TestClient(adapter.create_app()) as client:
        legacy = client.post("/v1/audio/speech", json=body)
        assert legacy.status_code == 200
        assert calls[-1][1]["language"] == "Auto"
        assert calls[-1][2] is None
        headers = {
            "X-OpenNoteLM-Speech-Policy": adapter.SPEECH_POLICY,
            "X-OpenNoteLM-Speech-Language": "zh-CN",
        }
        for voice in ("Uncle_Fu", "Serena", "uncle_fu"):
            result = client.post("/v1/audio/speech", json={**body, "voice": voice}, headers=headers)
            assert result.status_code == 200
            assert result.content == sample_wav()
        assert [item[0] for item in calls] == ["Uncle_Fu", "Uncle_Fu", "Serena", "uncle_fu"]
        assert calls[1][2] == calls[3][2] != calls[2][2]
        assert client.get("/health").json()["pending"] == 0
        bad = client.post(
            "/v1/audio/speech", json=body, headers={**headers, "X-OpenNoteLM-Speech-Language": "ar"}
        )
        assert bad.status_code == 400
        assert "PRIVATE_TEXT_SENTINEL" not in bad.text
        assert len(calls) == 4


def test_seeded_inference_restores_random_states_even_when_model_raises(monkeypatch):
    import sys
    from contextlib import contextmanager

    state = {"cpu": 11, "mps": 22}

    @contextmanager
    def fork_rng():
        previous = state["cpu"]
        try:
            yield
        finally:
            state["cpu"] = previous

    def seed(value):
        state.update(cpu=value, mps=value)

    def set_mps(value):
        state["mps"] = value

    fake_torch = SimpleNamespace(
        backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: True)),
        mps=SimpleNamespace(get_rng_state=lambda: state["mps"], set_rng_state=set_mps),
        random=SimpleNamespace(fork_rng=fork_rng),
        manual_seed=seed,
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "soundfile", SimpleNamespace())

    class FailedModel:
        def generate_custom_voice(self, **kwargs):
            assert state == {"cpu": 123, "mps": 123}
            raise RuntimeError("Inference failed")

    data = adapter.SpeechRequest(model=adapter.MODEL_ID, input="Test", voice="Serena")
    with pytest.raises(RuntimeError):
        adapter.generate_audio(FailedModel(), data, {"language": "Chinese"}, 123)
    assert state == {"cpu": 11, "mps": 22}
