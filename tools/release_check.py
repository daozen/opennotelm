"""Fail closed on accidental private files, stale licenses and broken release links."""

import argparse
import json
import re
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import unquote

from public_source import internal_file, load_policy, runtime_file


def project_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return sorted(set(filter(None, result.stdout.decode().split("\0"))))


def forbidden_file(name: str) -> bool:
    return runtime_file(name)


def history_errors(root: Path, documents: set[str]) -> list[str]:
    paths = (
        subprocess.check_output(
            [
                "git",
                "log",
                "--all",
                "--format=",
                "--name-only",
                "-z",
                "--root",
                "-m",
                "--no-renames",
                "--diff-filter=AM",
            ],
            cwd=root,
        )
        .decode()
        .split("\0")
    )
    return [
        f"Non-public path in Git history: {name}"
        for name in sorted(set(paths))
        if name and (runtime_file(name) or internal_file(name, documents))
    ]


def validate_tag(tag: str, version: str) -> None:
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?", tag):
        raise ValueError("Use a version tag such as v0.1.0-beta.1")
    if tag[1:].split("-", 1)[0] != version:
        raise ValueError("Release tag base version does not match application metadata")


def check(root: Path, tag: str | None = None, *, history=False) -> list[str]:
    errors = []
    try:
        documents = load_policy(root)
    except (OSError, ValueError, KeyError, TypeError):
        return ["Missing or invalid public documentation policy"]
    files = project_files(root)
    for name in files:
        if forbidden_file(name):
            errors.append(f"Private/runtime file included: {name}")
        if internal_file(name, documents):
            errors.append(f"Internal/unreviewed document included: {name}")
        if (root / name).is_symlink():
            errors.append(f"Symlink included in public source: {name}")
    project = tomllib.loads((root / "pyproject.toml").read_text())["project"]
    package = json.loads((root / "frontend/package.json").read_text())
    lock = json.loads((root / "frontend/package-lock.json").read_text())
    if project.get("license") != "MIT" or package.get("license") != "MIT":
        errors.append("Project metadata must keep the chosen MIT license")
    if package["version"] != project["version"] or lock["version"] != project["version"]:
        errors.append("Python/frontend/lock versions differ")
    if lock["packages"][""]["license"] != "MIT":
        errors.append("Frontend lock metadata must retain MIT")
    if tag:
        try:
            validate_tag(tag, project["version"])
        except ValueError as error:
            errors.append(str(error))
    for name in files:
        if not name.endswith(".md") or not (root / name).is_file():
            continue
        text = (root / name).read_text()
        if re.search(r"/Users/[^/\s]+/|192\.168\.\d+\.\d+", text):
            errors.append(f"Personal machine path/address in public documentation: {name}")
        for target in re.findall(r"\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)", text):
            target = unquote(target.strip("<>").split("#", 1)[0])
            if not target or re.match(r"[a-zA-Z][\w+.-]*:", target):
                continue
            destination = (root / name).parent / target
            if not destination.exists():
                errors.append(f"Missing local documentation target: {name} -> {target}")
    for path in sorted((root / ".github/workflows").glob("*.yml")):
        text = path.read_text()
        for action in re.findall(r"uses:\s*([^\s#]+)", text):
            if not action.startswith("./") and not re.fullmatch(r"[^@]+@[a-f0-9]{40}", action):
                errors.append(f"Action is not pinned to a commit: {path.name}")
        if not re.search(r"^permissions:", text, re.M):
            errors.append(f"Workflow lacks explicit permissions: {path.name}")
    inventory = json.loads((root / "docs/DEPENDENCIES.json").read_text())
    for row in inventory["packages"]:
        if not row.get("license"):
            errors.append(f"Missing dependency license: {row['name']}")
    locked_python = {
        p["name"]: p["version"] for p in tomllib.loads((root / "uv.lock").read_text())["package"]
    }
    locked_npm = {}
    for name, entry in lock["packages"].items():
        if name:
            locked_npm[(name.rsplit("node_modules/", 1)[-1], entry["version"])] = True
    for row in inventory["packages"]:
        if row["ecosystem"] == "pypi" and locked_python.get(row["name"]) != row["version"]:
            errors.append(f"Stale Python dependency inventory: {row['name']}")
        if row["ecosystem"] == "npm" and (row["name"], row["version"]) not in locked_npm:
            errors.append(f"Stale npm dependency inventory: {row['name']}")
    npm_inventory = {
        (r["name"], r["version"]) for r in inventory["packages"] if r["ecosystem"] == "npm"
    }
    if set(locked_npm) - npm_inventory:
        errors.append("Dependency inventory does not cover every locked npm package version")
    if history:
        errors.extend(history_errors(root, documents))
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--tag")
    parser.add_argument(
        "--history", action="store_true", help="Also reject non-public Git ancestors"
    )
    args = parser.parse_args()
    failures = check(args.root.resolve(), args.tag, history=args.history)
    for failure in failures:
        print(failure)
    if failures:
        raise SystemExit(1)
    print("Public source, MIT metadata, dependency versions and local links checked.")
