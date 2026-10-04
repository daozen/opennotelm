"""Fetch pinned native sources and the exact locked lxml sdist for a build stage."""

import argparse
import hashlib
import json
import tarfile
import tomllib
import urllib.request
from pathlib import Path


def unpack(archive: Path, destination: Path, expected: str) -> None:
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise ValueError("Native source checksum mismatch")
    with tarfile.open(archive) as source:
        source.extractall(destination, filter="data")


def fetch(root: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    sources = json.loads((root / "tools/native_xml_sources.json").read_text())
    locked = tomllib.loads((root / "uv.lock").read_text())
    lxml = next(p for p in locked["package"] if p["name"] == "lxml")
    sources["lxml"] = {
        "version": lxml["version"],
        "url": lxml["sdist"]["url"],
        "sha256": lxml["sdist"]["hash"].removeprefix("sha256:"),
        "license": "BSD-3-Clause",
    }
    for name, entry in sources.items():
        archive = output / f"{name}.archive"
        with urllib.request.urlopen(entry["url"], timeout=60) as response:
            archive.write_bytes(response.read())
        unpack(archive, output, entry["sha256"])
        archive.unlink()
    (output / "sources.json").write_text(json.dumps(sources, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fetch(args.root, args.output)
