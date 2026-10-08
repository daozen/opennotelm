"""Podcast contracts. Minutes are editorial targets, not an exact-duration guarantee."""

from typing import Literal

from pydantic import Field, field_validator

from .deck_schemas import DeckScope, DeckTitleInput
from .languages import OutputLanguage
from .schemas import StrictModel


class PodcastInput(StrictModel):
    scope: DeckScope = Field(default_factory=DeckScope)
    target_minutes: Literal[5, 10, 20, 30, 60] = 10
    format: Literal["dialogue", "solo"] = "dialogue"
    language: OutputLanguage = "en"
    instruction: str = Field(default="", max_length=4000)
    title_mode: Literal["auto", "source"] = "auto"
    script_only: bool = False


class PodcastBatchInput(PodcastInput):
    request_key: str = Field(pattern=r"^[A-Za-z0-9_-]{8,80}$")


class PodcastSection(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    focus: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(min_length=1, max_length=12)


class PodcastPlan(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    sections: list[PodcastSection] = Field(min_length=3, max_length=30)


class PodcastTurn(StrictModel):
    speaker: Literal["A", "B"]
    text: str = Field(min_length=1, max_length=3500)
    basis: Literal["source", "interpretation", "background", "analogy", "conversation"]
    evidence_ids: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Speech cannot be empty")
        return value.strip()


class PodcastScript(StrictModel):
    turns: list[PodcastTurn] = Field(min_length=1, max_length=30)


class PodcastEdit(PodcastScript):
    revision: int = Field(ge=1)


PodcastTitleInput = DeckTitleInput
