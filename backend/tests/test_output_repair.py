import asyncio

import pytest
from opennotelm.concurrency import bounded_map
from opennotelm.errors import AppError
from opennotelm.output_repair import apply_updates, normalize_citations
from opennotelm.visual_reading_cache import VisualReadingCache


def test_exact_known_citations_are_normalized_without_guessing_unknowns_or_quotes():
    value = "A [ [Ejob_98](#) ](#); B [Ejob_99](#); C [[ Ejob_98 ]]; [[FAKE]]; [12](#). “原文”"
    assert normalize_citations(value, {"Ejob_98", "Ejob_99"}) == (
        "A [[Ejob_98]]; B [[Ejob_99]]; C [[Ejob_98]]; [[FAKE]]; [12](#). “原文”"
    )
    assert (
        normalize_citations("[Ejob_98](https://example.com)", {"Ejob_98"})
        == "[Ejob_98](https://example.com)"
    )

    assert normalize_citations("[Ejob_98] [FAKE]", {"Ejob_98"}) == "[[Ejob_98]] [FAKE]"


def test_patch_preserves_valid_pages_and_rejects_unrelated_or_invalid_paths():
    candidate = {
        "slides": [{"title": "Keep exactly", "evidence_ids": ["BAD"]}, {"title": "Also keep"}]
    }
    paths = [["slides", 0, "evidence_ids"]]
    result = apply_updates(candidate, {"updates": [{"path": paths[0], "value": ["E1"]}]}, paths)
    assert result["slides"][0]["title"] == "Keep exactly"
    assert result["slides"][1] == candidate["slides"][1]
    assert candidate["slides"][0]["evidence_ids"] == ["BAD"]
    with pytest.raises(ValueError):
        apply_updates(candidate, {"updates": [{"path": ["slides"], "value": []}]}, paths)
    with pytest.raises(ValueError):
        apply_updates(candidate, {"updates": []}, paths)


def test_visual_cache_remaps_job_ids_and_invalidates_changed_inputs(tmp_path):
    one = VisualReadingCache(
        tmp_path, ["Eold_1"], {"material": [{"id": "Eold_1", "text": "source"}], "sha": "a"}
    )
    one.save("Verified diagram fact [[Eold_1]]")
    two = VisualReadingCache(
        tmp_path, ["Enew_1"], {"material": [{"id": "Enew_1", "text": "source"}], "sha": "a"}
    )
    assert one.path == two.path
    assert two.get() == "Verified diagram fact [[Enew_1]]"
    assert VisualReadingCache(tmp_path, ["Enew_1"], {"sha": "b"}).get() is None
    two.path.write_text("broken")
    assert two.get() is None
    assert not list(tmp_path.glob("*.tmp"))


def test_bounded_workers_keep_order_and_join_siblings_on_failure_and_cancel():
    async def scenario():
        active = peak = 0

        async def work(index, item):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep((5 - index) * 0.002)
                return item
            finally:
                active -= 1

        assert await bounded_map(list(range(5)), work, 2) == list(range(5))
        assert peak == 2 and active == 0
        started = asyncio.Event()

        async def failure(index, item):
            nonlocal active
            active += 1
            try:
                if index == 0:
                    await started.wait()
                    raise AppError("MODEL_TIMEOUT", "bounded provider error")
                started.set()
                await asyncio.sleep(10)
            finally:
                active -= 1

        with pytest.raises(AppError) as error:
            await bounded_map(list(range(5)), failure, 2)
        assert error.value.code == "MODEL_TIMEOUT" and active == 0
        task = asyncio.create_task(bounded_map(list(range(5)), work, 2))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert active == 0

    asyncio.run(scenario())
