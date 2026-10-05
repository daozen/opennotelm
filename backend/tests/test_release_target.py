"""Publishing never moves tags or uses unreviewed branch inputs."""

import importlib.util
import subprocess
from pathlib import Path

import httpx
import pytest

TOOLS = Path(__file__).resolve().parents[2] / "tools"
SHA = "a" * 40
TAG = "v0.1.0-beta.1"


@pytest.fixture
def target(monkeypatch):
    monkeypatch.syspath_prepend(str(TOOLS))
    spec = importlib.util.spec_from_file_location("release_target", TOOLS / "release_target.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def client_for(existing=None, release=False, conflict=False):
    calls = []
    created = False

    def respond(request):
        nonlocal created
        calls.append((request.method, request.url.path))
        path = request.url.path
        if "/releases/tags/" in path:
            return httpx.Response(200 if release else 404, json={})
        if "/git/ref/" in path:
            obj = existing or ({"type": "tag", "sha": "b" * 40} if created else None)
            return httpx.Response(200 if obj else 404, json={"object": obj})
        if request.method == "GET" and "/git/tags/" in path:
            return httpx.Response(200, json={"tag": TAG, "object": {"type": "commit", "sha": SHA}})
        if path.endswith("/git/tags"):
            return httpx.Response(201, json={"sha": "b" * 40})
        if path.endswith("/git/refs"):
            created = True
            return httpx.Response(422 if conflict else 201, json={})
        raise AssertionError(path)

    return httpx.Client(
        base_url="https://api.github.com", transport=httpx.MockTransport(respond)
    ), calls


def test_creates_annotated_tag_and_verifies_reference(target):
    client, calls = client_for()
    with client:
        target.ensure_tag(client, "owner/repo", SHA, TAG)
    assert [method for method, _ in calls] == ["GET", "GET", "POST", "POST", "GET"]


@pytest.mark.parametrize("obj", [{"type": "commit", "sha": SHA}, {"type": "tag", "sha": "c" * 40}])
def test_existing_lightweight_or_mismatched_tag_is_not_moved(target, obj):
    client, calls = client_for(existing=obj)
    if obj["type"] == "tag":

        def mismatch(request):
            calls.append((request.method, request.url.path))
            if "/releases/tags/" in request.url.path:
                return httpx.Response(404)
            if "/git/ref/" in request.url.path:
                return httpx.Response(200, json={"object": obj})
            return httpx.Response(
                200, json={"tag": TAG, "object": {"type": "commit", "sha": "d" * 40}}
            )

        client.close()
        client = httpx.Client(
            base_url="https://api.github.com", transport=httpx.MockTransport(mismatch)
        )
    with client, pytest.raises(ValueError):
        target.ensure_tag(client, "owner/repo", SHA, TAG)
    assert all(method == "GET" for method, _ in calls)


def test_matching_annotated_tag_can_resume_without_mutation(target):
    client, calls = client_for(existing={"type": "tag", "sha": "b" * 40})
    with client:
        target.ensure_tag(client, "owner/repo", SHA, TAG)
    assert all(method == "GET" for method, _ in calls)


def test_existing_draft_or_release_blocks_overwrite(target):
    client, calls = client_for(release=True)
    with client, pytest.raises(ValueError):
        target.ensure_tag(client, "owner/repo", SHA, TAG)
    assert len(calls) == 1


def test_concurrent_tag_conflict_fails_without_force_update(target):
    client, calls = client_for(conflict=True)
    with client, pytest.raises(ValueError):
        target.ensure_tag(client, "owner/repo", SHA, TAG)
    assert all(method != "PATCH" for method, _ in calls)


@pytest.mark.parametrize("commit", ["main", "a" * 39, "a" * 40 + ";echo", "A" * 40])
def test_requires_exact_sha_before_running_git(target, tmp_path, commit):
    with pytest.raises(ValueError):
        target.reviewed_target(tmp_path, commit, TAG)


def test_checkout_and_main_ancestry_are_required(target, tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion="0.1.0"\n')
    monkeypatch.setattr(
        subprocess, "check_output", lambda args, **kw: SHA if args[1] == "rev-parse" else "commit"
    )
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(a, 1))
    with pytest.raises(ValueError, match="protected main"):
        target.reviewed_target(tmp_path, SHA, TAG)
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **kw: "d" * 40)
    with pytest.raises(ValueError, match="Checkout"):
        target.reviewed_target(tmp_path, SHA, TAG)
