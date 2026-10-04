import asyncio
import threading
from io import BytesIO
from types import SimpleNamespace

import pytest
from opennotelm.documents import Document, DocumentBlock, DocumentImage
from opennotelm.errors import AppError
from opennotelm.schemas import ImageRecognitionSettingsInput
from opennotelm.source_vision import Recognition, SourceVisionService, joined_thread
from PIL import Image


def setup_service(client, settings):
    config = SimpleNamespace(model_id="vision-test")
    calls = []

    def configured(role):
        calls.append(role)
        return config, "test-only-key"

    service = SourceVisionService(
        SimpleNamespace(db=client.app.state.db, configured=configured), settings
    )
    source = {"id": "concurrency-source", "file_uri": "sources/unused.pdf"}
    (settings.data_dir / "sources" / source["id"]).mkdir()
    return service, source, calls


def document(values):
    images = []
    for index, value in enumerate(values):
        output = BytesIO()
        Image.new("RGB", (32, 32), (value, 0, 0)).save(output, format="PNG")
        images.append(DocumentImage(str(index), "chapter", index + 0.5, {}, output.getvalue()))
    return Document(
        "test",
        [],
        [DocumentBlock("text", "chapter", "paragraph", 0, "Original text", {})],
        images=images,
    )


def color(data):
    with Image.open(BytesIO(data)) as image:
        return image.getpixel((0, 0))[0]


def result(value):
    return Recognition(paragraphs=[f"Recognized {value}"], description="")


@pytest.mark.parametrize("limit", [1, 4, 20])
def test_limits_snapshot_order_and_monotonic_progress(client, settings, limit):
    service, source, configured = setup_service(client, settings)
    service.recognition_settings.save(ImageRecognitionSettingsInput(concurrency=limit))
    doc = document(range(25))
    progress, finished = [], []
    active = peak = 0
    second_finished = asyncio.Event()

    async def recognize(config, key, data, kind):
        nonlocal active, peak
        active += 1
        peak = max(active, peak)
        # A settings edit during the first request must not resize an active pool.
        service.recognition_settings.save(ImageRecognitionSettingsInput(concurrency=1))
        value = color(data)
        try:
            if limit > 1 and value == 0:
                await second_finished.wait()
            await asyncio.sleep(0.01 + (25 - value) * 0.001)
            finished.append(value)
            if value == 1:
                second_finished.set()
            return result(value)
        finally:
            active -= 1

    service.recognize = recognize
    asyncio.run(
        service.enrich(source, doc, SimpleNamespace(progress=lambda *p: progress.append(p)))
    )
    assert peak == limit
    assert active == 0
    assert configured == ["language"]
    assert doc.metadata["image_recognition_concurrency"] == limit
    assert [b.text for b in doc.blocks] == ["Original text"] + [
        f"Recognized {i}" for i in range(25)
    ]
    assert [b.ordinal for b in doc.blocks] == list(range(26))
    assert [i["id"] for i in doc.metadata["images"]] == [str(i) for i in range(25)]
    assert [p[1] for p in progress] == sorted(p[1] for p in progress)
    assert progress[-1][1] == pytest.approx(0.39)
    if limit > 1:
        assert finished != list(range(25))


def test_concurrent_duplicates_share_results_and_retry_only_failed_images(client, settings):
    service, source, configured = setup_service(client, settings)
    calls = []
    fail = True

    async def recognize(config, key, data, kind):
        value = color(data)
        calls.append(value)
        await asyncio.sleep(0.005)
        if fail and value == 2:
            raise AppError("MODEL_TIMEOUT", "test timeout", 502)
        return result(value)

    service.recognize = recognize
    context = SimpleNamespace(progress=lambda *args: None)
    first = document([1, 1, 2, 3, 1])
    asyncio.run(service.enrich(source, first, context))
    assert sorted(calls) == [1, 2, 3]
    assert first.metadata["image_failures"] == 1
    assert len(first.metadata["images"]) == 5
    fail = False
    second = document([1, 1, 2, 3, 1])
    asyncio.run(service.enrich(source, second, context))
    assert sorted(calls) == [1, 2, 2, 3]
    assert second.metadata["image_failures"] == 0
    assert not list((settings.data_dir / "sources" / source["id"] / "media").glob("*.tmp"))
    configured.clear()
    asyncio.run(service.enrich(source, document([1, 1, 2, 3, 1]), context))
    assert configured == []  # Published recognition facts survive unavailable credentials.


def test_cancel_joins_workers_and_preserves_completed_checkpoints(client, settings):
    service, source, _ = setup_service(client, settings)
    service.recognition_settings.save(ImageRecognitionSettingsInput(concurrency=3))
    calls = []
    active = 0
    cancel_run = True

    async def run():
        saved = asyncio.Event()

        async def recognize(config, key, data, kind):
            nonlocal active
            value = color(data)
            calls.append(value)
            active += 1
            try:
                if cancel_run and value != 0:
                    await asyncio.Event().wait()
                return result(value)
            finally:
                active -= 1

        def progress(stage, fraction):
            if fraction > 0.15:
                saved.set()

        service.recognize = recognize
        task = asyncio.create_task(
            service.enrich(source, document(range(6)), SimpleNamespace(progress=progress))
        )
        await asyncio.wait_for(saved.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert active == 0

    asyncio.run(run())
    cancelled_calls = list(calls)
    cancel_run = False
    doc = document(range(6))
    asyncio.run(service.enrich(source, doc, SimpleNamespace(progress=lambda *args: None)))
    assert calls.count(0) == 1
    assert set(calls[len(cancelled_calls) :]) == set(range(1, 6))
    assert doc.metadata["image_failures"] == 0


def test_cancel_waits_for_native_decoder_to_release_files():
    started, release, finished = threading.Event(), threading.Event(), threading.Event()

    def decode():
        started.set()
        assert release.wait(2)
        finished.set()

    async def run():
        task = asyncio.create_task(joined_thread(decode))
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()

    asyncio.run(run())
