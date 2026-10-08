"""Fetch only the reviewed FFmpeg source and verify it before extraction."""

import hashlib
import json
import tarfile
import urllib.request
from pathlib import Path


def fetch(manifest: Path, output: Path) -> None:
    entry = json.loads(manifest.read_text())
    if entry["url"] != (
        f"https://deb.debian.org/debian/pool/main/f/ffmpeg/ffmpeg_{entry['version']}.orig.tar.xz"
    ):
        raise ValueError("Unexpected audio source host/path")
    with urllib.request.urlopen(entry["url"], timeout=60) as response:
        content = response.read(30 * 1024 * 1024 + 1)
    if len(content) > 30 * 1024 * 1024:
        raise ValueError("Audio source exceeds download limit")
    if hashlib.sha256(content).hexdigest() != entry["sha256"]:
        raise ValueError("Audio source checksum mismatch")
    output.mkdir(parents=True, exist_ok=True)
    archive = output / "ffmpeg.tar.xz"
    archive.write_bytes(content)
    try:
        with tarfile.open(archive) as source:
            source.extractall(output, filter="data")
    finally:
        archive.unlink()


if __name__ == "__main__":
    fetch(Path("tools/native_audio_source.json"), Path("sources"))
