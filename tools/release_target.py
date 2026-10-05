"""Validate a reviewed main commit and create an immutable annotated release tag."""

import argparse
import os
import re
import subprocess
import tomllib
from pathlib import Path

import httpx
from release_check import validate_tag


def reviewed_target(root: Path, commit: str, tag: str) -> None:
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("An exact 40-character commit SHA is required")
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    validate_tag(tag, version)

    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=root, text=True).strip()

    if git("rev-parse", "HEAD") != commit or git("cat-file", "-t", commit) != "commit":
        raise ValueError("Checkout does not match the reviewed commit")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "refs/remotes/origin/main"],
        cwd=root,
        capture_output=True,
    )
    if result.returncode:
        raise ValueError("Release commit must belong to protected main")


def ensure_tag(client: httpx.Client, repository: str, commit: str, tag: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid repository name")
    if not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Invalid commit SHA")
    validate_tag(tag, tag[1:].split("-", 1)[0])
    prefix = f"/repos/{repository}"

    def request(method: str, path: str, payload=None, allow_missing=False):
        response = client.request(method, prefix + path, json=payload)
        if allow_missing and response.status_code == 404:
            return None
        if response.status_code not in {200, 201}:
            raise ValueError(f"GitHub release operation failed (HTTP {response.status_code})")
        return response.json()

    # A completed or draft release cannot be overwritten by a rerun.
    if request("GET", f"/releases/tags/{tag}", allow_missing=True) is not None:
        raise ValueError("A release already exists; inspect it rather than overwrite it")
    reference = request("GET", f"/git/ref/tags/{tag}", allow_missing=True)
    if reference is not None:
        if reference["object"]["type"] != "tag":
            raise ValueError("Existing release tag must be annotated")
        annotation = request("GET", f"/git/tags/{reference['object']['sha']}")
        if (
            annotation["object"]["type"] != "commit"
            or annotation["object"]["sha"] != commit
            or annotation["tag"] != tag
        ):
            raise ValueError("Existing tag does not match the reviewed commit")
        return
    annotation = request(
        "POST",
        "/git/tags",
        {"tag": tag, "message": f"OpenNoteLM {tag}", "object": commit, "type": "commit"},
    )
    request("POST", "/git/refs", {"ref": f"refs/tags/{tag}", "sha": annotation["sha"]})
    # Verify the published object, including concurrent creation conflicts.
    reference = request("GET", f"/git/ref/tags/{tag}")
    if reference["object"]["type"] != "tag" or reference["object"]["sha"] != annotation["sha"]:
        raise ValueError("Published tag differs from the created annotation")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--create-tag", action="store_true")
    args = parser.parse_args()
    try:
        reviewed_target(Path.cwd(), args.commit, args.tag)
        if args.create_tag:
            with httpx.Client(
                base_url="https://api.github.com",
                headers={
                    "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                ensure_tag(client, os.environ["GITHUB_REPOSITORY"], args.commit, args.tag)
        print("Reviewed release target verified.")
    except (ValueError, KeyError, httpx.HTTPError, subprocess.SubprocessError):
        raise SystemExit(
            "Release target validation or tag creation failed; no tag was moved."
        ) from None
