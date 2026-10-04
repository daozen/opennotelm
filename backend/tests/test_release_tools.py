"""Release guards protect private data and the version boundary."""

import importlib.util
import io
import tarfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "release_check", Path(__file__).resolve().parents[2] / "tools/release_check.py"
)
assert spec and spec.loader
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.mark.parametrize(
    "name",
    [
        "data/book.pdf",
        ".release-work/history-secrets.json",
        ".env.production",
        "notes/database.sqlite3",
        "frontend/node_modules/package/index.js",
    ],
)
def test_release_rejects_private_and_runtime_files(name):
    assert release.forbidden_file(name)


@pytest.mark.parametrize("name", [".env.example", "backend/tests/test_secrets.py", "LICENSE"])
def test_release_allows_safe_public_files(name):
    assert not release.forbidden_file(name)


@pytest.mark.parametrize("tag", ["main", "v0.2.0", "v0.1.0;echo secret", "v0.1.0-unknown.1"])
def test_release_rejects_wrong_versions_and_shell_payloads(tag):
    with pytest.raises(ValueError):
        release.validate_tag(tag, "0.1.0")


def test_release_accepts_beta_tag_with_matching_base_version():
    release.validate_tag("v0.1.0-beta.1", "0.1.0")


@pytest.fixture
def release_builder(monkeypatch):
    tools = Path(__file__).resolve().parents[2] / "tools"
    monkeypatch.syspath_prepend(str(tools))
    spec = importlib.util.spec_from_file_location("release_builder", tools / "build_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_detached_signature_is_retained_without_archive_parsing(release_builder):
    data = b"synthetic detached signature, not a tar archive"
    assert release_builder.debian_notices("debian-libacl1", "acl.orig.tar.xz.asc", data) == []
    assert release_builder.debian_notices("debian-libacl1", "acl.dsc", data) == []


def test_release_retains_complete_debian_and_upstream_notices(release_builder):
    data = b"complete synthetic copyright\nincluding all notices\n"
    for filename, url, expected in [
        ("acl-2.4.0/COPYING.LGPL", "acl.orig.tar.xz", "debian-libacl1-COPYING.LGPL"),
        ("debian/copyright", "acl.debian.tar.xz", "libacl1-copyright"),
    ]:
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:xz") as tar:
            entry = tarfile.TarInfo(filename)
            entry.size = len(data)
            tar.addfile(entry, io.BytesIO(data))
        assert release_builder.debian_notices("debian-libacl1", url, output.getvalue()) == [
            (expected, data)
        ]


def test_release_corrupt_archive_fails_instead_of_omitting_notices(release_builder):
    with pytest.raises(tarfile.ReadError):
        release_builder.debian_notices("debian-libacl1", "acl.orig.tar.xz", b"invalid archive")
