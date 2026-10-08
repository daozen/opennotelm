"""Verify the exact reduced audio binary and reject network, XML and graphics support."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def validate(version: str, protocols: set, formats: set, codecs: set, linkage: str) -> None:
    if not version.startswith("ffmpeg version 7.1.5 "):
        raise ValueError("Audio runtime differs from reviewed source version")
    required = {"--disable-everything", "--disable-autodetect", "--disable-network"}
    if not required <= set(version.split()):
        raise ValueError("Audio runtime lacks reduced-build configuration")
    if any(
        flag in version
        for flag in ("--enable-gpl", "--enable-nonfree", "--enable-libxml2", "--enable-librsvg")
    ):
        raise ValueError("Audio runtime enables unreviewed components")
    if protocols != {"file", "pipe"}:
        raise ValueError("Audio runtime enables unexpected protocols")
    if formats != {"wav", "mp3", "flac", "ogg", "concat"}:
        raise ValueError("Audio runtime enables unexpected demuxers")
    if not {"pcm_s16le", "mp3", "flac", "vorbis", "opus"} <= codecs or any(
        not name.startswith("pcm_") and name not in {"mp3", "mp3float", "flac", "vorbis", "opus"}
        for name in codecs
    ):
        raise ValueError("Audio runtime enables unexpected decoders")
    # ldd is run only on our own pinned build, never uploaded/provider binaries.
    linked = set(re.findall(r"\b(lib[^\s/]+\.so(?:\.[\d]+)*)", linkage))
    if "not found" in linkage or not linked <= {"libm.so.6", "libc.so.6", "libmp3lame.so.0"}:
        raise ValueError("Audio runtime links unexpected system libraries")


def probe(binary=Path("/usr/local/bin/ffmpeg"), licenses=Path("/app/licenses/native-audio")):
    def run(*args):
        return subprocess.check_output([str(binary), "-hide_banner", *args], text=True)

    source = json.loads((licenses / "source.json").read_text())
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    if digest != (licenses / "binary.sha256").read_text().strip():
        raise ValueError("Audio runtime binary does not match built artifact")
    version = subprocess.check_output([str(binary), "-version"], text=True)
    protocols = set()
    for line in run("-protocols").splitlines():
        if line.startswith("  "):
            protocols.add(line.strip())
    formats = {
        name
        for line in run("-demuxers").splitlines()
        if (match := re.match(r"^ D\s+(\S+)\s", line)) and match[1] != "="
        for name in match[1].split(",")
    }
    codecs = {
        match[1]
        for line in run("-decoders").splitlines()
        if (match := re.match(r"^ [VAS][.A-Z]{5}\s+(\S+)\s", line)) and match[1] != "="
    }
    linkage = subprocess.check_output(["ldd", str(binary)], text=True)
    validate(version, protocols, formats, codecs, linkage)
    if source["version"] != "7.1.5" or source["license"] != "LGPL-2.1-or-later":
        raise ValueError("Audio source identity differs from reviewed build")
    return {"source": source, "binary_sha256": digest, "restricted_audio": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = probe()
    print(json.dumps(result) if args.json else "Reduced audio runtime verified.")
