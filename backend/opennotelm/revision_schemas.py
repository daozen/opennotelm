from typing import Literal

from pydantic import Field

from .schemas import StrictModel


class RevisionInput(StrictModel):
    revision: int = Field(ge=0)
    action: Literal["content", "visual", "image", "revise"]
    instruction: str = Field(default="", max_length=4000)


class TextChange(StrictModel):
    ref: str = Field(min_length=1, max_length=100)
    text: str = Field(max_length=2500)


class EditTextInput(StrictModel):
    revision: int = Field(ge=0)
    changes: list[TextChange] = Field(min_length=1, max_length=160)


class OrderInput(StrictModel):
    revision: int = Field(ge=0)
    slide_ids: list[str] = Field(min_length=1, max_length=20)


class DeleteSlideInput(StrictModel):
    revision: int = Field(ge=0)


class RevisionDecision(StrictModel):
    target: Literal["content", "visual", "image"]
    reason: str = Field(min_length=1, max_length=500)
