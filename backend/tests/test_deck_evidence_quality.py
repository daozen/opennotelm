from collections import Counter

from opennotelm.chunking import estimate_tokens
from opennotelm.deck_schemas import PlannedSlide
from opennotelm.synthesis import SynthesisService


def block(identity, text, *, source="paper", node="section", page=1):
    return {"id": identity, "text": text, "source_id": source, "node_id": node, "page_start": page}


def test_fragmented_pdf_passage_keeps_full_context_and_exact_original_spans():
    blocks = [
        block(str(i), text)
        for i, text in enumerate(
            [
                "The participant followed",
                "a server invitation.",
                "It led to a",
                "fraudulent trade link.",
                "They then warned their friends.",
            ]
        )
    ]
    packets = SynthesisService(None, None).evidence(blocks, "job", 16000)
    assert len(packets) == 1
    assert all(b["text"] in packets[0]["text"] for b in blocks)
    assert [span["block_id"] for span in packets[0]["spans"]] == [b["id"] for b in blocks]
    for span, original in zip(packets[0]["spans"], blocks, strict=True):
        assert original["text"][span["start_offset"] : span["end_offset"]] == original["text"]


def test_evidence_never_bridges_source_chapter_or_page_boundaries():
    blocks = [
        block("1", "one"),
        block("2", "two", page=2),
        block("3", "three", page=2, node="other"),
        block("4", "four", page=2, node="other", source="other-paper"),
    ]
    packets = SynthesisService(None, None).evidence(blocks, "job", 16000)
    assert len(packets) == 4
    assert [p["text"] for p in packets] == ["one", "two", "three", "four"]


def test_long_evidence_is_bounded_without_losing_or_duplicating_source_characters():
    original = block("long", "原文事实与解释。" * 1800)
    packets = SynthesisService(None, None).evidence([original], "job", 16000)
    offsets = Counter()
    restored = []
    for packet in packets:
        assert estimate_tokens(packet["text"]) <= 800
        for span in packet["spans"]:
            offsets.update(range(span["start_offset"], span["end_offset"]))
            restored.append(original["text"][span["start_offset"] : span["end_offset"]])
    assert "".join(restored) == original["text"]
    assert set(offsets) == set(range(len(original["text"])))
    assert all(count == 1 for count in offsets.values())


def test_saved_v1_storyboards_remain_readable():
    value = PlannedSlide.model_validate(
        {
            "index": 1,
            "title": "Opening",
            "role": "opening",
            "purpose": "Explain",
            "key_message": "A grounded message",
            "evidence_ids": ["E1"],
        }
    )
    assert value.teaching_points == [] and value.visual_mode == "diagram"
