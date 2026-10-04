"""Check isolated browser startup/rendering, stopping at the first failure.

Run from a terminal or an approved test command, never repeatedly relaunch a
macOS GUI browser inside a restricted agent sandbox. No app data or models used.
"""

import argparse
import json
import os
import platform
from io import BytesIO

from opennotelm.browser_environment import check_local_test_ports
from PIL import Image
from playwright.sync_api import Error as BrowserError
from playwright.sync_api import sync_playwright
from pypdf import PdfReader

DOCUMENT = """<!doctype html><html><head><meta charset="utf-8"><style>
@page {size:20in 11.25in; margin:0}
body {margin:0; width:1920px; height:1080px; background:#fff; color:#24342f}
h1 {margin:0; padding:80px; font:48px sans-serif}
</style></head><body><h1>OpenNoteLM · 浏览器检查</h1></body></html>"""


def check_browser(executable=None, repeat=1):
    mode = "custom" if executable else "playwright-bundled-headless"
    result = {"ok": False, "browser": mode, "host_architecture": platform.machine()}
    try:
        check_local_test_ports()
    except OSError:
        return {
            **result,
            "error_code": "LOCAL_TEST_PORTS_UNAVAILABLE",
            "action": "Run browser checks in a terminal or an approved local-test command. "
            "No browser was started; do not retry in the same restricted environment.",
        }
    completed, stage = 0, "launch"
    try:
        with sync_playwright() as playwright:
            for _ in range(repeat):
                stage = "launch"
                browser = playwright.chromium.launch(
                    executable_path=executable, headless=True, timeout=20000
                )
                try:
                    stage = "render"
                    context = browser.new_context(
                        viewport={"width": 1920, "height": 1080},
                        java_script_enabled=False,
                        service_workers="block",
                    )
                    context.route("**/*", lambda route: route.abort())
                    page = context.new_page()
                    page.set_default_timeout(15000)
                    page.set_content(DOCUMENT, wait_until="load")
                    page.evaluate("document.fonts.ready")
                    png = page.screenshot()
                    pdf = page.pdf(width="20in", height="11.25in", print_background=True)
                    reader = PdfReader(BytesIO(pdf))
                    if (
                        Image.open(BytesIO(png)).size != (1920, 1080)
                        or len(reader.pages) != 1
                        or list(reader.pages[0].mediabox) != [0, 0, 1440, 810]
                        or "OpenNoteLM" not in reader.pages[0].extract_text()
                    ):
                        return {**result, "error_code": "BROWSER_RENDER_INVALID"}
                    result["browser_version"] = browser.version
                finally:
                    browser.close()
                completed += 1
    except (BrowserError, OSError):
        return {
            **result,
            "error_code": "BROWSER_START_FAILED" if stage == "launch" else "BROWSER_RENDER_FAILED",
            "completed": completed,
            "action": "Check execution permissions and install the browser matching Playwright. "
            "No automatic retry or fallback to your personal Chrome was attempted.",
        }
    return {**result, "ok": True, "completed": completed, "screenshot": True, "pdf": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, choices=range(1, 6), default=1)
    parser.add_argument("--frontend", action="store_true")
    args = parser.parse_args()
    variable = (
        "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH" if args.frontend else "RENDER_BROWSER_EXECUTABLE"
    )
    result = check_browser(os.getenv(variable) or None, args.repeat)
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
