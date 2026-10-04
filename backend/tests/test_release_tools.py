"""Release guards protect private data and the version boundary."""

import importlib.util
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
