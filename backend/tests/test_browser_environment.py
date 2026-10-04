import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import conftest
import pytest
from playwright.sync_api import Error as BrowserError

spec = importlib.util.spec_from_file_location(
    "browser_check", Path(__file__).resolve().parents[2] / "tools" / "browser_check.py"
)
browser_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser_check)


def test_preflight_denied_does_not_start_browser(monkeypatch):
    ports = Mock(side_effect=PermissionError("private environment detail"))
    startup = Mock()
    monkeypatch.setattr(browser_check, "check_local_test_ports", ports)
    monkeypatch.setattr(browser_check, "sync_playwright", startup)
    result = browser_check.check_browser(repeat=3)
    assert result["ok"] is False
    assert result["error_code"] == "LOCAL_TEST_PORTS_UNAVAILABLE"
    assert "No browser was started" in result["action"]
    assert "private environment detail" not in str(result)
    startup.assert_not_called()


def test_browser_failure_stops_after_one_attempt_without_exception_details(monkeypatch):
    launch = Mock(side_effect=BrowserError("private process details"))
    context = Mock()
    context.__enter__ = Mock(return_value=SimpleNamespace(chromium=SimpleNamespace(launch=launch)))
    context.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(browser_check, "check_local_test_ports", Mock())
    monkeypatch.setattr(browser_check, "sync_playwright", Mock(return_value=context))
    result = browser_check.check_browser(repeat=3)
    assert result["error_code"] == "BROWSER_START_FAILED"
    assert result["completed"] == 0
    assert "private process details" not in str(result)
    launch.assert_called_once_with(executable_path=None, headless=True, timeout=20000)


def test_render_failure_closes_browser_without_relaunch(monkeypatch):
    browser = Mock()
    browser.new_context.side_effect = BrowserError("private render details")
    launch = Mock(return_value=browser)
    context = Mock()
    context.__enter__ = Mock(return_value=SimpleNamespace(chromium=SimpleNamespace(launch=launch)))
    context.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(browser_check, "check_local_test_ports", Mock())
    monkeypatch.setattr(browser_check, "sync_playwright", Mock(return_value=context))
    result = browser_check.check_browser(repeat=3)
    assert result["error_code"] == "BROWSER_RENDER_FAILED"
    assert "private render details" not in str(result)
    launch.assert_called_once()
    browser.close.assert_called_once()


def test_mac_browser_collection_fails_before_running_tests(monkeypatch):
    monkeypatch.setattr(conftest.sys, "platform", "darwin")
    ports = Mock(side_effect=PermissionError())
    monkeypatch.setattr(conftest, "check_local_test_ports", ports)
    session = SimpleNamespace(items=[SimpleNamespace(get_closest_marker=lambda _: True)])
    with pytest.raises(pytest.UsageError, match="No browser was started"):
        conftest.pytest_collection_finish(session)
    ports.assert_called_once()


@pytest.mark.parametrize("platform, browser_selected", [("darwin", False), ("linux", True)])
def test_unit_only_and_non_mac_collection_remain_available(monkeypatch, platform, browser_selected):
    monkeypatch.setattr(conftest.sys, "platform", platform)
    ports = Mock(side_effect=PermissionError())
    monkeypatch.setattr(conftest, "check_local_test_ports", ports)
    session = SimpleNamespace(
        items=[SimpleNamespace(get_closest_marker=lambda _: browser_selected)]
    )
    conftest.pytest_collection_finish(session)
    ports.assert_not_called()
