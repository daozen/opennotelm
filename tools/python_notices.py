"""Copy runtime dependency and native component notices without personal paths."""

import argparse
import importlib.metadata as metadata
import json
import re
import shutil
import tomllib
from pathlib import Path


def runtime_names(root: Path) -> set[str]:
    project = tomllib.loads((root / "pyproject.toml").read_text())
    locked = tomllib.loads((root / "uv.lock").read_text())
    packages = {p["name"]: p for p in locked["package"]}
    names: set[str] = set()

    def visit(name: str) -> None:
        name = re.sub(r"[-_.]+", "-", name.lower())
        if name in names:
            return
        names.add(name)
        for dependency in packages[name].get("dependencies", []):
            visit(dependency["name"])

    for requirement in project["project"]["dependencies"]:
        visit(re.split(r"[<>=!\[; ]", requirement)[0])
    return names


def collect(root: Path, output: Path) -> list[dict]:
    output.mkdir(parents=True, exist_ok=True)
    packages = []
    for name in sorted(runtime_names(root)):
        try:
            distribution = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            # Lock includes conditional packages not installed on this platform.
            continue
        files = []
        destination = output / f"{name}@{distribution.version}"
        for entry in distribution.files or []:
            parts = entry.parts
            is_notice = any(p.lower() in ("licenses", "build_licenses") for p in parts)
            is_notice |= bool(
                re.match(r"^(license|licence|copying|notice)(\.|$)", entry.name, re.I)
            )
            if not is_notice:
                continue
            source = Path(distribution.locate_file(entry))
            if not source.is_file():
                continue
            # Keep distribution-relative names, never absolute machine paths.
            relative = Path(*[p for p in parts if p not in ("..", ".")])
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            files.append(relative.as_posix())
        if not files:
            raise ValueError(f"Missing runtime license text: {name}")
        packages.append({"name": name, "version": distribution.version, "notices": sorted(files)})
    (output / "index.json").write_text(json.dumps(packages, indent=2) + "\n")
    return packages


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path(".release-work/notices/python"))
    args = parser.parse_args()
    print(f"Preserved notices for {len(collect(args.root, args.output))} Python runtime packages.")
