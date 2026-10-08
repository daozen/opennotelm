from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from .config import (
    MAX_CONTENT_GENERATION_CONCURRENCY,
    MAX_IMAGE_GENERATION_CONCURRENCY,
    MAX_IMAGE_RECOGNITION_CONCURRENCY,
)
from .languages import OutputLanguage

ModelRole = Literal["language", "embedding", "image", "speech"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NotebookInput(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title cannot be blank")
        return value.strip()


class ModelInput(StrictModel):
    base_url: str = Field(max_length=2048)
    api_key: SecretStr = SecretStr("")
    use_saved_key: bool = False
    api_key_source: ModelRole | None = None
    model_id: str = Field(min_length=1, max_length=200)
    max_context_tokens: int = Field(default=16000, ge=2048, le=2_000_000)
    speech_protocol: Literal["openai", "gemini"] = "openai"
    voice_a: str = Field(default="alloy", min_length=1, max_length=100)
    voice_b: str = Field(default="nova", min_length=1, max_length=100)

    @field_validator("base_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlsplit(value.strip())
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Use an http(s) API base URL without credentials, query or fragment")
        return value.strip().rstrip("/")

    @field_validator("model_id", "voice_a", "voice_b")
    @classmethod
    def clean_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Model ID and voices cannot be blank")
        return value.strip()


class ModelTestInput(ModelInput):
    role: ModelRole


class IndexRebuildInput(StrictModel):
    mode: Literal["missing", "failed", "all"] = "missing"


class ContentGenerationSettingsInput(StrictModel):
    concurrency: int = Field(strict=True, ge=1, le=MAX_CONTENT_GENERATION_CONCURRENCY)


class TaskConcurrencyInput(StrictModel):
    concurrency: int = Field(strict=True, ge=1, le=8)


class ModelRequestConcurrencyInput(StrictModel):
    concurrency: int = Field(strict=True, ge=1, le=20)


class SpeechGenerationSettingsInput(StrictModel):
    concurrency: int = Field(strict=True, ge=1, le=20)


class ImageRecognitionSettingsInput(StrictModel):
    concurrency: int = Field(strict=True, ge=1, le=MAX_IMAGE_RECOGNITION_CONCURRENCY)


class ImageGenerationSettingsInput(StrictModel):
    concurrency: int = Field(strict=True, ge=1, le=MAX_IMAGE_GENERATION_CONCURRENCY)


class PreferencesInput(StrictModel):
    telemetry_enabled: bool | None = None
    ui_language: OutputLanguage | None = None

    @field_validator("telemetry_enabled", "ui_language", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("Preference values cannot be null")
        return value
