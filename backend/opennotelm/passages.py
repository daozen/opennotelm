"""Readable evidence with exact, immutable source coordinates."""

from collections import defaultdict

from .chunking import split_block
from .reading import display_text


def project_passages(reading, blocks, maximum=1000):
    """Map reflowed PDF paragraphs back to raw offsets, including ligatures.

    Display whitespace may differ from PDF drawing operations. Every visible
    character must still match the next character of its original fact block.
    Oversized paragraphs split at sentence boundaries within the evidence budget.
    """
    facts = {block["id"]: block for block in blocks}
    streams = {
        block["id"]: [
            (char, offset)
            for offset, original in enumerate(block["text"])
            for char in display_text(original)
            if not char.isspace()
        ]
        for block in blocks
    }
    consumed = defaultdict(int)
    output = []
    for paragraph in reading:
        text, coordinates = "", []
        for part in paragraph["parts"]:
            identity = part["block_id"]
            value = display_text(part["text"])
            for char in value:
                if char.isspace():
                    coordinates.append(None)
                else:
                    position = consumed[identity]
                    stream = streams[identity]
                    if position >= len(stream) or stream[position][0] != char:
                        raise ValueError("Reading projection does not match source facts")
                    coordinates.append((identity, stream[position][1]))
                    consumed[identity] += 1
            text += value
        for window in split_block({"id": "display", "text": text}, maximum):
            spans = []
            for coordinate in coordinates[window.start : window.end]:
                if coordinate is None:
                    continue
                identity, offset = coordinate
                if spans and spans[-1]["block_id"] == identity:
                    spans[-1]["end_offset"] = offset + 1
                else:
                    spans.append(
                        {
                            "source_id": facts[identity]["source_id"],
                            "block_id": identity,
                            "start_offset": offset,
                            "end_offset": offset + 1,
                        }
                    )
            if spans and window.text.strip():
                output.append(
                    {
                        "text": window.text,
                        "spans": spans,
                        "page": paragraph["page_start"],
                        "type": paragraph["type"],
                    }
                )
    return output


def raw_passages(blocks, maximum=1000):
    return [
        {
            "text": span.text,
            "spans": [
                {
                    "source_id": block["source_id"],
                    "block_id": block["id"],
                    "start_offset": span.start,
                    "end_offset": span.end,
                }
            ],
            "page": block["page_start"],
            "type": block["type"],
        }
        for block in blocks
        for span in split_block(block, maximum)
    ]


def overlaps(left, right):
    return (
        left["source_id"] == right["source_id"]
        and left["block_id"] == right["block_id"]
        and left["start_offset"] < right["end_offset"]
        and right["start_offset"] < left["end_offset"]
    )


def select_passages(passages, hits):
    """Keep retrieval rank and merge duplicate hits in the same paragraph."""
    by_block = defaultdict(list)
    for index, passage in enumerate(passages):
        for span in passage["spans"]:
            by_block[span["block_id"]].append((index, span))
    selected, seen = [], set()
    for hit in hits:
        for index, span in by_block[hit["block_id"]]:
            if index not in seen and overlaps(span, hit):
                selected.append(passages[index])
                seen.add(index)
    return selected
