"""Supported output languages; only validated codes become generation instructions."""

from typing import Literal

OutputLanguage = Literal[
    "zh-CN", "en", "zh-TW", "ja", "ko", "es", "fr", "de", "pt-BR", "ru", "ar", "hi"
]
LANGUAGE_NAMES = {
    "zh-CN": "Simplified Chinese",
    "en": "English",
    "zh-TW": "Traditional Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt-BR": "Brazilian Portuguese",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
}


def output_instruction(language: str | None) -> str:
    if language not in LANGUAGE_NAMES:
        return ""
    return (
        f"Write the generated title and explanatory prose in {LANGUAGE_NAMES[language]} "
        f"(output language code: {language}). This explicit output language overrides the "
        "question or source language. Preserve citation IDs, original-source quotations, "
        "proper names and literal code; never translate a quotation and present it as "
        "verbatim original text. Do not add facts when translating."
    )
