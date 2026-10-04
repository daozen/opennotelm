from dataclasses import dataclass, field
from uuid import NAMESPACE_URL, uuid5


def stable_id(source_id: str, location: str) -> str:
    return uuid5(NAMESPACE_URL, f"opennotelm:{source_id}:{location}").hex


@dataclass
class DocumentNode:
    id: str
    parent_id: str | None
    type: str
    title: str
    depth: int
    ordinal: int
    start_page: int | None = None
    end_page: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class DocumentBlock:
    id: str
    node_id: str
    type: str
    ordinal: int
    text: str
    location: dict
    page_start: int | None = None
    page_end: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class DocumentImage:
    id: str
    node_id: str
    after_ordinal: float
    location: dict
    data: bytes | None = None
    page: int | None = None
    kind: str = "figure"


@dataclass
class Document:
    title: str
    nodes: list[DocumentNode]
    blocks: list[DocumentBlock]
    metadata: dict = field(default_factory=dict)
    images: list[DocumentImage] = field(default_factory=list)
