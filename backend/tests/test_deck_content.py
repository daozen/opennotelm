from types import SimpleNamespace

import pytest
from opennotelm.config import Settings
from opennotelm.deck_content import check_content_basis, check_source_content
from opennotelm.deck_schemas import SlideContentElement
from test_decks import create_deck, notebook_with_source
from test_decks import decks as decks  # noqa: F401


def copy(text, *, label="", kind="statement"):
    return SimpleNamespace(
        content_elements=[SimpleNamespace(text=text, label=label, type=kind, items=[])]
    )


@pytest.mark.parametrize(
    "text,label",
    [
        ("额外说明", "作者见解"),
        ("额外说明", "解读边界"),
        ("这不是此处独立验证的普遍定论。", ""),
        ("This is not independently verified.", ""),
    ],
)
def test_added_editorial_copy_requires_repair(text, label):
    with pytest.raises(ValueError):
        check_source_content(copy(text, label=label), [{"text": "原文讨论资产与选择。"}])


def test_original_content_and_quotation_are_preserved():
    evidence = [{"text": "作者见解。研究样本为 12 人。这不是独立验证的结果。"}]
    check_source_content(copy("作者见解"), evidence)
    check_source_content(copy("研究样本为 12 人。这不是独立验证的结果。"), evidence)
    check_source_content(copy("解读边界", kind="quote"), evidence)
    with pytest.raises(ValueError):
        check_source_content(copy("原文内容", label="解读边界", kind="quote"), evidence)


def test_substantive_metaphor_explanation_is_allowed_without_editorial_labels():
    evidence = [{"text": "资产好像桌子，参与者聚在一起。"}]
    check_source_content(copy("作者用桌子比喻资产。", kind="caption"), evidence)
    check_source_content(copy("资产好像桌子，参与者聚在一起。"), evidence)


def test_explicit_editorial_request_can_override_default_labels():
    evidence = [{"text": "原文讨论资产与选择。"}]
    check_source_content(
        copy("这里可以有不同的理解。", label="解读边界"),
        evidence,
        include_editorial_notes=True,
    )


def basis_spec(**element):
    return SimpleNamespace(
        content_elements=[SlideContentElement(id="idea", type="statement", text="解释", **element)],
        visual_relationships=[],
    )


def test_interpretation_anchors_and_uncited_background_are_distinct():
    check_content_basis(basis_spec(basis="interpretation", citations=["E1"]))
    check_content_basis(basis_spec(basis="background"))
    check_content_basis(basis_spec(basis="analogy"))
    with pytest.raises(ValueError, match="cannot cite"):
        check_content_basis(basis_spec(basis="background", citations=["E1"]))
    with pytest.raises(ValueError, match="need supplied"):
        check_content_basis(basis_spec(basis="interpretation"))
    check_content_basis(basis_spec(basis="interpretation", citations=["E1"]), source_only=True)
    with pytest.raises(ValueError, match="source-only"):
        check_content_basis(basis_spec(basis="background"), source_only=True)


def test_invented_example_cannot_inherit_source_citations_from_a_list():
    spec = basis_spec(
        citations=["E1"],
        items=[{"text": "比如设想一个场景", "basis": "analogy"}],
    )
    with pytest.raises(ValueError, match="cannot cite"):
        check_content_basis(spec)


def test_author_repairs_added_commentary_before_saving(decks):
    client, state, _ = decks
    notebook, _ = notebook_with_source(client)
    state["added_editorial_note"] = True
    deck, job = create_deck(client, notebook, 10)
    assert job["status"] == "completed"
    authors = [
        c
        for c in state["calls"]
        if c.get("messages", [{}])[0].get("content", "").startswith("Author one SlideSpec")
    ]
    assert len(authors) == 11
    assert any("previous JSON failed" in c["messages"][0]["content"] for c in authors)
    assert "解读边界" not in str(deck["slides"][0]["spec"])


def test_image_concurrency_is_configurable_and_bounded(monkeypatch):
    monkeypatch.setenv("IMAGE_GENERATION_CONCURRENCY", "1")
    assert Settings().image_generation_concurrency == 1
    monkeypatch.setenv("IMAGE_GENERATION_CONCURRENCY", "20")
    assert Settings().image_generation_concurrency == 20
    for value in (0, -1, 21):
        with pytest.raises(ValueError, match="between 1 and 20"):
            Settings(image_generation_concurrency=value)


def test_preflight_reports_independent_errors_without_mutating_candidate():
    from copy import deepcopy

    from opennotelm.deck_validation import diagnose_page

    candidate = {
        "content_elements": [
            {"type": "statement", "text": "解释" * 100, "basis": "background", "citations": ["E1"]},
            {"type": "comparison", "text": "标题", "citations": ["UNKNOWN"]},
        ]
    }
    original = deepcopy(candidate)
    errors = diagnose_page(candidate, allowed={"E1"}, budget=100)
    assert len(errors) == 3
    assert any("cannot" in str(e) for e in errors)
    assert any("supplied page evidence" in str(e) for e in errors)
    assert any(e.progress is not None for e in errors)
    assert candidate == original
    assert diagnose_page(None, allowed={"E1"}, budget=100) == []
