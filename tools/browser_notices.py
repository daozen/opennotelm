"""Retain the installed full browser's built-in credits and terms during image build."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def collect(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        # Only the isolated build container runs as root. No data mount, external
        # pages or personal browser profile is involved in this build operation.
        browser = playwright.chromium.launch(
            channel="chromium", headless=True, args=["--no-sandbox"]
        )
        try:
            page = browser.new_page()
            documents = {}
            for name in ("credits", "terms"):
                page.goto(f"chrome://{name}")
                content = page.content()
                if len(content) < 1000:
                    raise ValueError(f"Incomplete browser {name}")
                if name == "credits" and content.count("<pre") < 100:
                    raise ValueError("Browser credits omit full license text")
                (output / f"{name}.html").write_text(content)
                documents[name] = len(content.encode())
            (output / "index.json").write_text(
                json.dumps({"browser_version": browser.version, "documents": documents}, indent=2)
                + "\n"
            )
        finally:
            browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    collect(parser.parse_args().output)
