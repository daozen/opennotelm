from opennotelm.chunking import estimate_tokens, make_chunks


def test_long_multilingual_blocks_preserve_every_character_and_offsets():
    text = "Long paragraph. 中文原文不能丢失。🙂 " * 300
    blocks = [{"id": "original", "node_id": "section", "text": text}]
    chunks = make_chunks("source", blocks, target=100, maximum=150, overlap=20)
    covered = set()
    for chunk in chunks:
        assert estimate_tokens(chunk.text) <= 150
        for span in chunk.spans:
            assert text[span.start : span.end] == span.text
            covered.update(range(span.start, span.end))
    assert covered == set(range(len(text)))
    assert [c.id for c in chunks] == [
        c.id for c in make_chunks("source", blocks, target=100, maximum=150, overlap=20)
    ]


def test_chunk_overlap_never_crosses_nodes():
    blocks = [
        {"id": str(i), "node_id": "a" if i < 4 else "b", "text": "word " * 40} for i in range(8)
    ]
    chunks = make_chunks("source", blocks, target=100, maximum=200, overlap=20)
    lookup = {b["id"]: b for b in blocks}
    for chunk in chunks:
        assert all(lookup[s.block_id]["node_id"] == chunk.node_id for s in chunk.spans)
    assert any(span.start > 0 for chunk in chunks for span in chunk.spans)
