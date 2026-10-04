"""Refresh locked package licenses from installed metadata and public registries."""

import importlib.metadata as metadata
import json
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path

from python_notices import runtime_names


def public_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def update(root: Path) -> None:
    locked = tomllib.loads((root / "uv.lock").read_text())
    python = {p["name"]: p for p in locked["package"]}
    target = root / "docs/DEPENDENCIES.json"
    previous = json.loads(target.read_text()) if target.exists() else {"packages": []}
    cached = {(p["ecosystem"], p["name"], p["version"]): p for p in previous["packages"]}
    rows = []
    for name in sorted(runtime_names(root)):
        version = python[name]["version"]
        old = cached.get(("pypi", name, version))
        if old:
            license_value = old["license"]
        else:
            try:
                dist = metadata.distribution(name)
                if dist.version != version:
                    raise metadata.PackageNotFoundError(name)
                license_value = dist.metadata.get("License-Expression") or dist.metadata.get(
                    "License"
                )
                if not license_value and any(
                    "MIT" in c for c in dist.metadata.get_all("Classifier", [])
                ):
                    license_value = "MIT"
            except metadata.PackageNotFoundError:
                info = public_json(f"https://pypi.org/pypi/{name}/{version}/json")["info"]
                license_value = info.get("license_expression") or info.get("license")
        if not license_value:
            raise ValueError(f"License requires manual review: {name}")
        rows.append(
            {
                "ecosystem": "pypi",
                "name": name,
                "version": version,
                "license": license_value,
                "url": f"https://pypi.org/project/{name}/{version}/",
                "source_url": f"https://pypi.org/project/{name}/{version}/#files",
                "scope": "runtime",
            }
        )
    lock = json.loads((root / "frontend/package-lock.json").read_text())
    for path, entry in sorted(lock["packages"].items()):
        if not path:
            continue
        name, version = path.rsplit("node_modules/", 1)[-1], entry["version"]
        license_value = entry.get("license")
        manifest = root / "frontend" / path / "package.json"
        if manifest.exists():
            license_value = json.loads(manifest.read_text()).get("license") or license_value
        if not license_value and ("npm", name, version) in cached:
            license_value = cached[("npm", name, version)]["license"]
        if not license_value:
            url = "https://registry.npmjs.org/" + urllib.parse.quote(name, safe="") + "/" + version
            license_value = public_json(url).get("license")
        if not license_value:
            raise ValueError(f"License requires manual review: {name}")
        rows.append(
            {
                "ecosystem": "npm",
                "name": name,
                "version": version,
                "license": license_value,
                "url": f"https://www.npmjs.com/package/{name}/v/{version}",
                "package_path": path,
                "scope": "development" if entry.get("dev") else "runtime",
            }
        )
    result = {
        "format": "OpenNoteLM dependency inventory v1",
        "note": "Locked application packages; native/browser/font/container components need "
        "their bundled notices too. License metadata is not a complete compliance opinion.",
        "packages": rows,
    }
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Updated {len(rows)} locked dependency entries; review new licenses before committing.")


if __name__ == "__main__":
    update(Path.cwd())
