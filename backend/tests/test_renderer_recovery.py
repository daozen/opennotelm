"""Transient browser recovery keeps bounded attempts and cancellation semantics."""

import asyncio

import pytest
from opennotelm.errors import AppError
from opennotelm.renderer import recover_transient_browser
from playwright.async_api import Error as BrowserError
from playwright.async_api import TimeoutError as BrowserTimeout


@pytest.mark.parametrize(
    "cause",
    [
        BrowserTimeout("Page.screenshot: Timeout exceeded"),
        BrowserError("Target page, context or browser has been closed"),
        BrowserError("Page crashed"),
    ],
)
def test_transient_failure_reuses_same_inputs_once(cause):
    calls = []
    payload = object()

    @recover_transient_browser
    async def render(value):
        calls.append(value)
        if len(calls) == 1:
            raise AppError("RENDER_BROWSER_FAILED", "Safe message") from cause
        return {"complete": True}

    assert asyncio.run(render(payload)) == {"complete": True}
    assert calls == [payload, payload]


def test_repeated_browser_failure_remains_actionable_and_bounded():
    calls = []

    @recover_transient_browser
    async def render():
        calls.append(True)
        raise AppError("RENDER_BROWSER_FAILED", "Safe message") from BrowserTimeout("timeout")

    with pytest.raises(AppError, match="RENDER_BROWSER_FAILED"):
        asyncio.run(render())
    assert len(calls) == 2


@pytest.mark.parametrize(
    "code,cause",
    [
        ("RENDER_BROWSER_FAILED", BrowserError("Executable doesn't exist")),
        ("RENDER_LAYOUT_INVALID", BrowserTimeout("timeout")),
        ("MODEL_TIMEOUT", BrowserTimeout("timeout")),
        ("RENDER_BROWSER_FAILED", None),
    ],
)
def test_configuration_layout_and_model_failures_do_not_retry(code, cause):
    calls = []

    @recover_transient_browser
    async def render():
        calls.append(True)
        raise AppError(code, "Safe message") from cause

    with pytest.raises(AppError):
        asyncio.run(render())
    assert len(calls) == 1


def test_cancellation_is_not_retried_and_joins_cleanup():
    calls, joined = [], []

    @recover_transient_browser
    async def render():
        calls.append(True)
        try:
            raise asyncio.CancelledError()
        finally:
            joined.append(True)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(render())
    assert calls == joined == [True]
