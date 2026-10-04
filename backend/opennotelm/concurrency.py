"""Fixed worker pools: stable result order, joined cancellation, bounded active calls."""

import asyncio
from contextvars import ContextVar

from .errors import AppError

CONTENT_CONCURRENCY = ContextVar("deck_content_concurrency", default=1)


async def bounded_map(items, function, limit):
    results = [None] * len(items)
    pending = iter(enumerate(items))

    async def worker():
        for index, item in pending:
            results[index] = await function(index, item)

    try:
        async with asyncio.TaskGroup() as group:
            for _ in range(min(limit, len(items))):
                group.create_task(worker())
    except ExceptionGroup as errors:
        # Preserve an actionable provider error after all sibling tasks have joined.
        def leaves(group):
            for error in group.exceptions:
                if isinstance(error, ExceptionGroup):
                    yield from leaves(error)
                else:
                    yield error

        failures = list(leaves(errors))
        if failures and all(isinstance(e, AppError) for e in failures):
            raise failures[0] from errors
        raise
    return results


async def joined_thread(function, *args):
    """A cancelled source job must wait until native decoding releases its files."""
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await asyncio.gather(task, return_exceptions=True)
        raise
