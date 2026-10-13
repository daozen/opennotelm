"""Bounded, source-grounded quiz and flashcard contracts."""

from typing import Literal

from pydantic import Field, field_validator

from .mindmap_schemas import MindMapInput
from .schemas import StrictModel


class StudyInput(MindMapInput):
    count: int = Field(default=10, ge=5, le=40)
    difficulty: Literal["mixed", "easy", "medium", "hard"] = "mixed"


class StudyBatchInput(StudyInput):
    request_key: str = Field(pattern=r"^[A-Za-z0-9_-]{8,80}$")


class Option(StrictModel):
    id: str = Field(pattern=r"^[A-D]$")
    text: str = Field(min_length=1, max_length=600)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Option text must not be blank")
        return value.strip()


class QuizQuestion(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    question: str = Field(min_length=1, max_length=1200)
    options: list[Option] = Field(min_length=4, max_length=4)
    correct_option_id: str = Field(pattern=r"^[A-D]$")
    explanation: str = Field(min_length=1, max_length=1600)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)


class Flashcard(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    front: str = Field(min_length=1, max_length=800)
    back: str = Field(min_length=1, max_length=1600)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)


class QuizContent(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    items: list[QuizQuestion] = Field(min_length=1, max_length=40)


class FlashcardContent(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    items: list[Flashcard] = Field(min_length=1, max_length=40)


class StudyResponseInput(StrictModel):
    item_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    choice: str = Field(min_length=1, max_length=20)
    revision: int = Field(ge=0)


class StudyResetInput(StrictModel):
    revision: int = Field(ge=0)


def validate_study(content, allowed, primary, count):
    if not content.title.strip():
        raise ValueError("Provide a meaningful title")
    if len(content.items) > count:
        raise ValueError("Do not exceed requested_count; use fewer items for small sources")
    ids, prompts = set(), set()
    for item in content.items:
        prompt = item.question if isinstance(item, QuizQuestion) else item.front
        if not prompt.strip() or item.id in ids or prompt.strip().casefold() in prompts:
            raise ValueError("Use distinct nonblank questions and unique item IDs")
        ids.add(item.id)
        prompts.add(prompt.strip().casefold())
        refs = set(item.evidence_ids)
        if refs - allowed or (primary and not refs.intersection(primary)):
            raise ValueError("Every item must cite registered evidence from the selected material")
        answer = item.explanation if isinstance(item, QuizQuestion) else item.back
        if not answer.strip():
            raise ValueError("Provide a meaningful explanation or answer")
        if isinstance(item, QuizQuestion):
            if {option.id for option in item.options} != {"A", "B", "C", "D"}:
                raise ValueError("Supply exactly four options with unique IDs A, B, C, D")
            if len({option.text.casefold() for option in item.options}) != 4:
                raise ValueError("Answer options must be distinct")
