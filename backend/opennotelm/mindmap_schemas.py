"""Flat, bounded tree contracts avoid recursive model schemas and unbounded layouts."""

from typing import Literal

from pydantic import Field, field_validator

from .deck_schemas import DeckScope
from .languages import OutputLanguage
from .schemas import StrictModel


class MindMapInput(StrictModel):
    scope: DeckScope = Field(default_factory=DeckScope)
    language: OutputLanguage = "en"
    instruction: str = Field(default="", max_length=4000)
    title_mode: Literal["auto", "source"] = "auto"


class MindMapBatchInput(MindMapInput):
    request_key: str = Field(pattern=r"^[A-Za-z0-9_-]{8,80}$")


class MindMapNode(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    parent_id: str | None
    label: str = Field(min_length=1, max_length=120)
    detail: str = Field(default="", max_length=1200)
    basis: Literal["structural", "source", "interpretation", "background", "analogy"]
    evidence_ids: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("label")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Node labels must not be blank")
        return value.strip()


class MindMapTree(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    nodes: list[MindMapNode] = Field(min_length=3, max_length=120)


def validate_tree(tree, allowed, *, source_only=False, primary=()):
    nodes = {n.id: n for n in tree.nodes}
    if len(nodes) != len(tree.nodes):
        raise ValueError("Node IDs must be unique")
    roots = [n for n in tree.nodes if n.parent_id is None]
    if len(roots) != 1:
        raise ValueError("Return exactly one root with parent_id=null")
    parents = {n.parent_id for n in tree.nodes}
    used = set()
    for node in tree.nodes:
        seen, current = set(), node
        while current:
            if current.id in seen or len(seen) >= 6:
                raise ValueError("Use a connected tree without cycles, at most six levels deep")
            seen.add(current.id)
            if current.parent_id is None:
                break
            if current.parent_id not in nodes:
                raise ValueError("Each parent_id must identify a supplied node")
            current = nodes[current.parent_id]
        refs = set(node.evidence_ids)
        used.update(refs)
        if refs - allowed:
            raise ValueError("Use only registered original evidence IDs")
        if node.basis in ("source", "interpretation") and not refs:
            raise ValueError("Source-derived nodes need original evidence IDs")
        if node.basis in ("background", "analogy", "structural") and refs:
            raise ValueError("Outside knowledge and structural labels cannot claim source evidence")
        if node.basis == "structural" and (node.detail or node.id not in parents):
            raise ValueError("Structural labels group children, with no factual detail")
        if source_only and node.basis in ("background", "analogy"):
            raise ValueError("The user requested source-only content")
    if not used or (primary and not used.intersection(primary)):
        raise ValueError("Include source-grounded nodes from the selected material")
