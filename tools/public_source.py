"""Export a reviewed file tree without private documentation or private Git ancestry."""

import argparse
import io
import json
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

POLICY_PATH = "tools/public_docs.json"
PRIVATE_MARKER = ".private-workspace"


def parse_policy(raw):
    policy = json.loads(raw)
    if not isinstance(policy, dict):
        raise ValueError("Unsupported public documentation policy")
    if policy.get("version") != 1 or not isinstance(policy.get("documents"), list):
        raise ValueError("Unsupported public documentation policy")
    documents = policy["documents"]
    if any(
        not isinstance(p, str)
        or not p
        or p.startswith("/")
        or ".." in PurePosixPath(p).parts
        or str(PurePosixPath(p)) != p
        for p in documents
    ):
        raise ValueError("Invalid public documentation path")
    return set(documents)


def load_policy(root):
    return parse_policy((root / POLICY_PATH).read_text())


def internal_file(name, documents):
    path = PurePosixPath(name)
    if PRIVATE_MARKER in path.parts or any(p in {"internal", "private"} for p in path.parts):
        return True
    return (
        name.startswith("docs/") or path.suffix.lower() in {".md", ".rst"}
    ) and name not in documents


def runtime_file(name):
    parts = PurePosixPath(name).parts
    if not parts or any(
        p in {".git", "data", ".venv", ".release-work", ".local-services", "node_modules", "dist"}
        for p in parts
    ):
        return True
    if any(p.startswith((".e2e-data", ".docker-acceptance-data")) for p in parts):
        return True
    filename = parts[-1]
    return (
        filename.startswith(".env") and filename != ".env.example"
    ) or filename.lower().endswith((".sqlite", ".sqlite3", ".db", ".pem", ".key"))


def export(root, destination, ref="HEAD"):
    root, destination = root.resolve(), destination.resolve()
    if destination == root or root.is_relative_to(destination):
        raise ValueError("Export must not overwrite the source checkout")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Choose a new or empty export directory")
    commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", "--end-of-options", ref + "^{commit}"], cwd=root, text=True
    ).strip()
    # Use the committed policy, never an unreviewed working-tree modification.
    raw_policy = subprocess.check_output(["git", "show", f"{commit}:{POLICY_PATH}"], cwd=root)
    documents = parse_policy(raw_policy)
    content = subprocess.check_output(["git", "archive", "--format=tar", commit], cwd=root)
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    with tarfile.open(fileobj=io.BytesIO(content)) as archive:
        for entry in archive:
            name = entry.name
            if entry.isdir() or internal_file(name, documents) or runtime_file(name):
                continue
            if not entry.isfile() or name.startswith("/") or ".." in PurePosixPath(name).parts:
                raise ValueError("Public exports cannot contain symlinks or unsafe paths")
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(archive.extractfile(entry).read())
            target.chmod(0o755 if entry.mode & 0o111 else 0o644)
            count += 1
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        f"Exported {export(args.root, args.output, args.ref)} public files; no Git history copied."
    )
