"""Reduced audio builds must fail closed on format, linkage and source drift."""

import hashlib
import importlib.util
import io
import tarfile
from pathlib import Path

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parents[2] / "tools" / f"{name}.py"
    )
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def evidence():
    return {
        "version": "ffmpeg version 7.1.5 Copyright FFmpeg\nconfiguration: "
        "--disable-everything --disable-autodetect --disable-network --enable-libmp3lame",
        "protocols": {"file", "pipe"},
        "formats": {"wav", "mp3", "flac", "ogg", "concat"},
        "codecs": {"pcm_s16le", "mp3", "mp3float", "flac", "vorbis", "opus"},
        "linkage": "libm.so.6 => /lib/libm.so.6\nlibc.so.6 => /lib/libc.so.6\n"
        "libmp3lame.so.0 => /lib/libmp3lame.so.0",
    }


def test_reduced_runtime_accepts_only_reviewed_audio_evidence():
    load("check_audio_runtime").validate(**evidence())


@pytest.mark.parametrize(
    "change",
    [
        "version",
        "configuration",
        "gpl",
        "network",
        "xml_format",
        "svg_codec",
        "xml_link",
        "missing_lib",
    ],
)
def test_reduced_runtime_rejects_unsafe_or_unreviewed_components(change):
    args = evidence()
    if change == "version":
        args["version"] = args["version"].replace("7.1.5", "7.1.4")
    elif change == "configuration":
        args["version"] = args["version"].replace("--disable-autodetect", "")
    elif change == "gpl":
        args["version"] += " --enable-gpl"
    elif change == "network":
        args["protocols"].add("http")
    elif change == "xml_format":
        args["formats"].add("dash")
    elif change == "svg_codec":
        args["codecs"].add("librsvg")
    elif change == "xml_link":
        args["linkage"] += "\nlibxml2.so.2 => /lib/libxml2.so.2"
    else:
        args["linkage"] += "\nlibmp3lame.so.0 => not found"
    with pytest.raises(ValueError, match="Audio runtime"):
        load("check_audio_runtime").validate(**args)


def test_audio_source_rejects_wrong_hash_before_extraction(monkeypatch, tmp_path):
    import json

    helper = load("fetch_audio_source")
    manifest = tmp_path / "source.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "7.1.5",
                "url": "https://deb.debian.org/debian/pool/main/f/ffmpeg/ffmpeg_7.1.5.orig.tar.xz",
                "sha256": "0" * 64,
            }
        )
    )
    monkeypatch.setattr(
        helper.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"not an archive")
    )
    with pytest.raises(ValueError, match="checksum"):
        helper.fetch(manifest, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_audio_source_rejects_archive_escape(monkeypatch, tmp_path):
    import json

    helper = load("fetch_audio_source")
    content = io.BytesIO()
    with tarfile.open(fileobj=content, mode="w") as archive:
        member = tarfile.TarInfo("../escaped")
        member.size = 4
        archive.addfile(member, io.BytesIO(b"test"))
    raw = content.getvalue()
    manifest = tmp_path / "source.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "7.1.5",
                "url": "https://deb.debian.org/debian/pool/main/f/ffmpeg/ffmpeg_7.1.5.orig.tar.xz",
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    )
    monkeypatch.setattr(helper.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(raw))
    with pytest.raises(tarfile.OutsideDestinationError):
        helper.fetch(manifest, tmp_path / "output")
    assert not (tmp_path / "escaped").exists()


def test_audio_sbom_keeps_os_components_and_requires_runtime_evidence(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "check_xml_runtime", load("check_xml_runtime"))
    helper = load("native_xml_sbom")
    os_component = {"bom-ref": "os-xml", "name": "libxml2", "version": "2.9.14"}
    bom = {"components": [os_component.copy()]}
    report = {
        "restricted_audio": True,
        "binary_sha256": "b" * 64,
        "source": {
            "version": "7.1.5",
            "license": "LGPL-2.1-or-later",
            "url": "https://example.com/ffmpeg.tar.xz",
            "sha256": "a" * 64,
        },
    }
    result = helper.enrich_audio(bom, report)
    assert result["components"][0] == os_component
    audio = result["components"][1]
    assert audio["hashes"][0]["content"] == "b" * 64
    assert audio["externalReferences"][0]["hashes"][0]["content"] == "a" * 64
    with pytest.raises(ValueError, match="already recorded"):
        helper.enrich_audio(result, report)
    with pytest.raises(ValueError, match="probe"):
        helper.enrich_audio({"components": []}, {**report, "restricted_audio": False})
