import asyncio

import pytest
from opennotelm.schemas import ContentGenerationSettingsInput
from test_decks import create_deck, notebook_with_source
from test_decks import decks as decks


@pytest.mark.parametrize("limit", [1, 2, 20])
def test_authors_obey_snapshot_and_persist_source_order(decks, limit):
    client, state, _ = decks
    service = client.app.state.decks
    client.put("/api/settings/models/content-generation", json={"concurrency": limit})
    original = service.author
    active = peak = count = 0

    async def author(*args):
        nonlocal active, peak, count
        active += 1
        peak = max(peak, active)
        count += 1
        # Saved changes cannot alter the limit for an in-flight generation.
        service.content_generation_settings.save(ContentGenerationSettingsInput(concurrency=3))
        try:
            await asyncio.sleep(0.05)
            return await original(*args)
        finally:
            active -= 1

    service.author = author
    notebook, _ = notebook_with_source(client)
    deck, job = create_deck(client, notebook, count=20 if limit == 20 else 10)
    assert job["status"] == "completed", job
    assert peak == limit and active == 0 and count == len(deck["slides"])
    assert [s["ordinal"] for s in deck["slides"]] == list(range(count))
    assert deck["generation_metadata"]["content_generation_concurrency"] == limit
