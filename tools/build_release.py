"""Create reviewable release assets from a clean committed tree; never publish."""

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import tomllib
import urllib.request
from pathlib import Path

from python_notices import collect
from release_check import check, validate_tag


def archive(directory: Path, destination: Path, prefix: str) -> None:
    with destination.open("wb") as output, gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for path in sorted(directory.rglob("*")):
                if not path.is_file():
                    continue
                if path.is_symlink():
                    raise ValueError("Release assets cannot contain symlinks")
                data = path.read_bytes()
                info = tarfile.TarInfo(f"{prefix}/{path.relative_to(directory).as_posix()}")
                info.size = len(data)
                info.mode = 0o644
                info.mtime = 0
                tar.addfile(info, io.BytesIO(data))


def build(root: Path, output: Path, tag: str) -> list[Path]:
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    validate_tag(tag, version)
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=root)
    if status:
        raise ValueError("Commit reviewed changes before creating release assets")
    errors = check(root, tag)
    if errors:
        raise ValueError("Release checks failed: " + "; ".join(errors))
    output.mkdir(parents=True, exist_ok=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    prefix = f"opennotelm-{tag[1:]}"
    files = []
    source = output / f"{prefix}-source.tar.gz"
    with tempfile.TemporaryDirectory() as temp:
        staging = Path(temp)
        # git archive excludes ignored and untracked runtime/user files by construction.
        content = subprocess.check_output(["git", "archive", "HEAD"], cwd=root)
        with tarfile.open(fileobj=io.BytesIO(content)) as tar:
            tar.extractall(staging / "source", filter="data")
        archive(staging / "source", source, prefix)
        files.append(source)
        notices = staging / "notices"
        collect(root, notices / "python")
        subprocess.run(
            [
                "node",
                str(root / "tools/npm_notices.mjs"),
                str(root / "frontend"),
                str(notices / "npm"),
            ],
            check=True,
        )
        # Retain complete unmodified source distributions for file-copyleft dependencies.
        sources = staging / "upstream-sources"
        sources.mkdir()
        packages = tomllib.loads((root / "uv.lock").read_text())["package"]
        upstreams = []
        for package in packages:
            if package["name"] not in {"certifi", "tld", "lxml"}:
                continue
            sdist = package["sdist"]
            if not sdist["url"].startswith("https://files.pythonhosted.org/"):
                raise ValueError("Unexpected upstream source host")
            upstreams.append((package["name"], sdist["url"], sdist["hash"]))
        native = json.loads((root / "tools/native_xml_sources.json").read_text())
        for name, entry in native.items():
            if not entry["url"].startswith("https://download.gnome.org/sources/"):
                raise ValueError("Unexpected native source host")
            upstreams.append((name, entry["url"], "sha256:" + entry["sha256"]))
        debian = json.loads((root / "tools/debian_security_packages.json").read_text())
        for name, entry in debian["packages"].items():
            for source_entry in entry["sources"]:
                if not source_entry["url"].startswith("https://deb.debian.org/debian/pool/main/"):
                    raise ValueError("Unexpected Debian security source host")
                upstreams.append(
                    ("debian-" + name, source_entry["url"], "sha256:" + source_entry["sha256"])
                )
        for name, url, expected_hash in upstreams:
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read(30 * 1024 * 1024 + 1)
            if len(data) > 30 * 1024 * 1024:
                raise ValueError("Upstream source exceeds the download limit")
            if "sha256:" + hashlib.sha256(data).hexdigest() != expected_hash:
                raise ValueError("Upstream source checksum mismatch")
            (sources / url.rsplit("/", 1)[-1]).write_bytes(data)
            if name in native:
                with tarfile.open(fileobj=io.BytesIO(data)) as tar:
                    copyright_text = tar.extractfile(
                        f"{name}-{native[name]['version']}/Copyright"
                    ).read()
                target = notices / "native-xml" / f"{name}-Copyright"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(copyright_text)
            elif name.startswith("debian-") and url.endswith(".debian.tar.xz"):
                with tarfile.open(fileobj=io.BytesIO(data)) as tar:
                    copyright_text = tar.extractfile("debian/copyright").read()
                target = notices / "debian-security" / (name.removeprefix("debian-") + "-copyright")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(copyright_text)
            elif name.startswith("debian-") and ".orig.tar." in url:
                with tarfile.open(fileobj=io.BytesIO(data)) as tar:
                    for member in tar.getmembers():
                        if member.isfile() and Path(member.name).name.startswith("COPYING"):
                            target = (
                                notices / "debian-security" / (name + "-" + Path(member.name).name)
                            )
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_bytes(tar.extractfile(member).read())
        (notices / "native-xml/sources.json").write_text(json.dumps(native, indent=2) + "\n")
        (notices / "debian-security/packages.json").write_text(json.dumps(debian, indent=2) + "\n")
        notices_asset = output / f"{prefix}-third-party-notices.tar.gz"
        archive(notices, notices_asset, "third-party-notices")
        files.append(notices_asset)
        source_notices = output / f"{prefix}-third-party-sources.tar.gz"
        archive(sources, source_notices, "upstream-sources")
        files.append(source_notices)
    inventory = output / f"{prefix}-dependency-inventory.json"
    inventory_data = json.loads((root / "docs/DEPENDENCIES.json").read_text())
    inventory_data["native_container_components"] = native
    inventory_data["debian_security_packages"] = debian
    inventory.write_text(json.dumps(inventory_data, ensure_ascii=False, indent=2) + "\n")
    files.append(inventory)
    metadata = output / "release-manifest.json"
    metadata.write_text(
        json.dumps(
            {
                "tag": tag,
                "app_version": version,
                "commit": commit,
                "license": "MIT",
                "assets": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
            },
            indent=2,
        )
        + "\n"
    )
    files.append(metadata)
    checksums = output / "SHA256SUMS"
    checksums.write_text(
        "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in files)
    )
    files.append(checksums)
    return files


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", type=Path, default=Path(".release-work/assets"))
    args = parser.parse_args()
    for asset in build(Path.cwd(), args.output.resolve(), args.tag):
        print(asset.name)
