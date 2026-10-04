"""Release builds verify embedded native libraries independently of pip metadata."""

import hashlib
import importlib.util
import io
import sys
import tarfile
from pathlib import Path

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parents[2] / "tools" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_embedded_xml_version_checked_even_when_python_package_unchanged():
    checker = load("check_xml_runtime")
    manifest = {"libxml2": {"version": "2.15.4"}, "libxslt": {"version": "1.1.45"}}
    checker.validate(manifest, (2, 15, 4), (2, 15, 4), (1, 1, 45))
    for compiled, runtime, xslt in [
        ((2, 14, 6), (2, 14, 6), (1, 1, 45)),
        ((2, 15, 4), (2, 14, 6), (1, 1, 45)),
        ((2, 15, 4), (2, 15, 4), (1, 1, 43)),
    ]:
        with pytest.raises(ValueError, match="XML runtime"):
            checker.validate(manifest, compiled, runtime, xslt)


def test_native_download_checksum_is_checked_before_extracting(tmp_path):
    fetcher = load("fetch_xml_sources")
    source = tmp_path / "source.tar"
    source.write_bytes(b"not an archive")
    with pytest.raises(ValueError, match="checksum"):
        fetcher.unpack(source, tmp_path / "output", "0" * 64)
    assert not (tmp_path / "output").exists()


def test_xml_manifest_cannot_downgrade_security_baseline():
    checker = load("check_xml_runtime")
    manifest = {"libxml2": {"version": "2.14.6"}, "libxslt": {"version": "1.1.45"}}
    with pytest.raises(ValueError, match="security baseline"):
        checker.validate(manifest, (2, 14, 6), (2, 14, 6), (1, 1, 45))


def test_native_source_archive_cannot_escape_build_directory(tmp_path):
    fetcher = load("fetch_xml_sources")
    source = tmp_path / "source.tar"
    with tarfile.open(source, "w") as archive:
        entry = tarfile.TarInfo("../escaped")
        entry.size = 4
        archive.addfile(entry, io.BytesIO(b"data"))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(tarfile.OutsideDestinationError):
        fetcher.unpack(source, tmp_path / "output", digest)
    assert not (tmp_path / "escaped").exists()


def test_native_sbom_adds_embedded_versions_without_overwriting_os_package(monkeypatch):
    monkeypatch.setitem(sys.modules, "check_xml_runtime", load("check_xml_runtime"))
    sbom = load("native_xml_sbom")
    os_component = {"bom-ref": "os-xml", "name": "libxml2", "version": "2.9.14"}
    bom = {"components": [os_component.copy(), {"bom-ref": "pkg:pypi/lxml@6.1.3"}]}
    sources = {
        name: {
            "version": version,
            "url": "https://example.com/source",
            "sha256": "a" * 64,
            "license": "MIT",
        }
        for name, version in [("libxml2", "2.15.4"), ("libxslt", "1.1.45")]
    }
    report = {
        "sources": {**sources, "lxml": {"version": "6.1.3"}},
        "libxml2_compiled": [2, 15, 4],
        "libxml2_runtime": [2, 15, 4],
        "libxslt_runtime": [1, 1, 45],
    }
    result = sbom.enrich(bom, report)
    assert result["components"][0] == os_component
    assert len(result["dependencies"][0]["dependsOn"]) == 2
    assert len(result["components"]) == 4
    with pytest.raises(ValueError, match="already recorded"):
        sbom.enrich(result, report)


def test_native_sbom_rejects_different_python_distribution(monkeypatch):
    monkeypatch.setitem(sys.modules, "check_xml_runtime", load("check_xml_runtime"))
    sbom = load("native_xml_sbom")
    report = {
        "sources": {
            "lxml": {"version": "6.1.3"},
            "libxml2": {"version": "2.15.4"},
            "libxslt": {"version": "1.1.45"},
        },
        "libxml2_compiled": [2, 15, 4],
        "libxml2_runtime": [2, 15, 4],
        "libxslt_runtime": [1, 1, 45],
    }
    with pytest.raises(ValueError, match="lxml distribution"):
        sbom.enrich({"components": [{"bom-ref": "pkg:pypi/lxml@6.0.2"}]}, report)
