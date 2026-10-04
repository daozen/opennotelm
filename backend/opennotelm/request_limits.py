"""Fair process-wide admission by provider origin, shared across roles and jobs."""

import asyncio
from collections import deque
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from .generation_attempts import JOB_DIAGNOSTICS


class RequestBudget:
    def __init__(self, limit):
        self.limit = limit
        self.active = 0
        self.waiters = {}
        self.order = deque()

    def pump(self):
        while self.order and self.active < self.limit():
            owner = self.order.popleft()
            pending = self.waiters[owner]
            future = pending.popleft()
            if pending:
                self.order.append(owner)
            else:
                del self.waiters[owner]
            if not future.cancelled():
                self.active += 1
                future.set_result(None)

    @asynccontextmanager
    async def slot(self):
        diagnostic = JOB_DIAGNOSTICS.get()
        owner = diagnostic[1] if diagnostic else "interactive"
        future = asyncio.get_running_loop().create_future()
        if owner not in self.waiters:
            self.waiters[owner] = deque()
            self.order.append(owner)
        self.waiters[owner].append(future)
        self.pump()
        acquired = False
        try:
            await asyncio.shield(future)
            acquired = True
            yield
        finally:
            # Cancellation after a grant but before await resumes also owns a slot.
            if acquired or (future.done() and not future.cancelled()):
                self.active -= 1
            else:
                future.cancel()
                pending = self.waiters.get(owner)
                if pending is not None:
                    pending.remove(future)
                    if not pending:
                        del self.waiters[owner]
                        self.order.remove(owner)
            self.pump()


class ProviderBudgets:
    def __init__(self, limit):
        self.limit, self.providers = limit, {}

    def slot(self, config):
        url = urlsplit(config.base_url)
        identity = (url.scheme, url.hostname, url.port or (443 if url.scheme == "https" else 80))
        if identity not in self.providers:
            self.providers[identity] = RequestBudget(self.limit)
        return self.providers[identity].slot()


class SharedStageBudget:
    """Bound preparation as well as requests, preserving each run's frozen limit.

    Active runs share the largest of their snapshots, never their sum. Lowering
    a setting cannot abruptly shrink a running pool or interrupt its operations.
    """

    def __init__(self):
        self.leases = {}
        self.budget = RequestBudget(lambda: max(self.leases.values(), default=1))

    @asynccontextmanager
    async def slot(self, limit):
        lease = object()
        self.leases[lease] = limit
        try:
            async with self.budget.slot():
                yield
        finally:
            self.leases.pop(lease)
