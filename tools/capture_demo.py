"""Capture real UI screenshots using only disposable data and local test providers."""

import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from browser_check import check_browser
from playwright.sync_api import expect, sync_playwright


def wait_job(client: httpx.Client, job_id: str) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        response.raise_for_status()
        state = response.json()["status"]
        if state == "completed":
            return
        if state in {"failed", "stopped"}:
            raise RuntimeError("Synthetic demo job did not complete")
        time.sleep(0.2)
    raise TimeoutError("Synthetic demo job timed out")


def capture(root: Path, frontend: Path, output: Path) -> None:
    for port in (4310, 4311):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))
    preflight = check_browser()
    if not preflight["ok"]:
        raise RuntimeError("Browser preflight failed; no retry attempted")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="opennotelm-public-demo-") as temp:
        work = Path(temp)
        env = {k: v for k, v in os.environ.items() if not k.endswith("API_KEY")}
        env.update(
            DATA_DIR=str(work / "data"),
            FRONTEND_DIR=str(frontend.resolve()),
            TELEMETRY_PROJECT_TOKEN="",
            ALLOWED_HOSTS="localhost,127.0.0.1",
        )
        processes = []
        with (work / "server.log").open("w") as log:
            try:
                for module, directory, port in (
                    ("mock_provider:app", "backend/tests", 4311),
                    ("opennotelm.main:app", "backend", 4310),
                ):
                    processes.append(
                        subprocess.Popen(
                            [
                                sys.executable,
                                "-m",
                                "uvicorn",
                                module,
                                "--app-dir",
                                str(root / directory),
                                "--host",
                                "127.0.0.1",
                                "--port",
                                str(port),
                                "--no-access-log",
                            ],
                            env=env,
                            stdout=log,
                            stderr=log,
                        )
                    )
                with httpx.Client(base_url="http://127.0.0.1:4310", timeout=30) as client:
                    deadline = time.monotonic() + 30
                    while True:
                        try:
                            client.get("/api/health").raise_for_status()
                            break
                        except httpx.HTTPError:
                            if time.monotonic() > deadline:
                                raise TimeoutError("Demo server did not start") from None
                            time.sleep(0.2)
                    for role in ("language", "embedding", "image"):
                        response = client.post(
                            "/api/settings/models/test",
                            json={
                                "role": role,
                                "base_url": "http://127.0.0.1:4311/v1",
                                "api_key": "test-only-key",
                                "model_id": "test-model",
                            },
                        )
                        response.raise_for_status()
                    client.put(
                        "/api/settings/preferences", json={"ui_language": "zh-CN"}
                    ).raise_for_status()
                    notebook = client.post(
                        "/api/notebooks", json={"title": "Learning lab · 学习工作台"}
                    )
                    notebook.raise_for_status()
                    nid = notebook.json()["id"]
                    uploaded = client.post(
                        f"/api/notebooks/{nid}/sources/upload",
                        files={
                            "file": (
                                "learning.epub",
                                (root / "frontend/e2e/fixtures/book.epub").read_bytes(),
                                "application/epub+zip",
                            ),
                        },
                    )
                    uploaded.raise_for_status()
                    wait_job(client, uploaded.json()["job"]["id"])
                    with sync_playwright() as playwright:
                        browser = playwright.chromium.launch(headless=True)
                        try:
                            page = browser.new_page(
                                viewport={"width": 1440, "height": 960}, locale="zh-CN"
                            )
                            page.goto(f"http://127.0.0.1:4310/notebooks/{nid}")
                            if page.get_by_role("dialog").is_visible():
                                page.get_by_role("button", name="关闭设置", exact=True).click()
                            page.get_by_label("向资料提问").fill("长期复利的优势是什么？")
                            page.get_by_role("button", name="发送问题", exact=True).click()
                            expect(page.locator(".message-assistant")).to_contain_text(
                                "长期复利最大的优势来自时间跨度。",
                                timeout=15000,
                            )
                            page.screenshot(path=str(output / "workspace.zh-CN.png"))
                            client.put(
                                "/api/settings/preferences", json={"ui_language": "en"}
                            ).raise_for_status()
                            page.reload()
                            expect(page.locator("html")).to_have_attribute("lang", "en")
                            expect(page.locator(".message-assistant")).to_be_visible()
                            page.screenshot(path=str(output / "workspace.png"))
                        finally:
                            browser.close()
            finally:
                for process in reversed(processes):
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
    print("Captured English/Chinese UI; synthetic inputs, no real model or user-data access.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", type=Path, default=Path("frontend/dist"))
    parser.add_argument("--output", type=Path, default=Path("docs/images"))
    args = parser.parse_args()
    capture(Path.cwd(), args.frontend, args.output)
