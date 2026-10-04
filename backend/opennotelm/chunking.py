import math
import re
from dataclasses import dataclass

from .documents import stable_id

CHUNKER_VERSION = "paragraph-v1"


def estimate_tokens(text: str) -> int:
    """Conservative UTF-8 estimate for unknown compatible-model tokenizers."""
    return max(1, math.ceil(len(text.encode("utf-8")) / 3))


@dataclass
class Span:
    block_id: str
    start: int
    end: int
    text: str


@dataclass
class Chunk:
    id: str
    source_id: str
    node_id: str
    ordinal: int
    text: str
    spans: list[Span]


def split_block(block: dict, maximum: int) -> list[Span]:
    text = block["text"]
    spans = []
    start = 0
    while start < len(text):
        end = min(len(text), start + maximum * 3)
        while estimate_tokens(text[start:end]) > maximum:
            end = start + max(1, (end - start) * 3 // 4)
        if end < len(text):
            boundaries = list(re.finditer(r"[。！？.!?\n]\s*", text[start:end]))
            if boundaries and boundaries[-1].end() > (end - start) // 2:
                end = start + boundaries[-1].end()
        spans.append(Span(block["id"], start, end, text[start:end]))
        start = end
    return spans


def make_chunks(
    source_id: str, blocks: list[dict], target=700, maximum=1000, overlap=100
) -> list[Chunk]:
    chunks: list[Chunk] = []
    pending: list[Span] = []
    node_id = ""

    def flush():
        if pending:
            text = "\n\n".join(span.text for span in pending)
            ordinal = len(chunks)
            chunks.append(
                Chunk(
                    stable_id(source_id, f"{CHUNKER_VERSION}:{ordinal}"),
                    source_id,
                    node_id,
                    ordinal,
                    text,
                    list(pending),
                )
            )

    for block in blocks:
        for span in split_block(block, maximum):
            if pending and (
                node_id != block["node_id"]
                or estimate_tokens("\n\n".join(s.text for s in pending)) >= target
                or estimate_tokens("\n\n".join(s.text for s in [*pending, span])) > maximum
            ):
                same_node = node_id == block["node_id"]
                flush()
                last = pending[-1]
                # Keep a precise source span for overlap; never cite chunk-relative offsets.
                suffix = last.text[-overlap * 3 :]
                while suffix and estimate_tokens(suffix) > overlap:
                    suffix = suffix[len(suffix) // 4 + 1 :]
                pending = (
                    [Span(last.block_id, last.end - len(suffix), last.end, suffix)]
                    if same_node and suffix
                    else []
                )
                if estimate_tokens("\n\n".join(s.text for s in [*pending, span])) > maximum:
                    pending = []
            node_id = block["node_id"]
            pending.append(span)
    flush()
    return chunks
