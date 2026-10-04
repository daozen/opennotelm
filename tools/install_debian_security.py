"""Install only checksum-pinned compatible vendor fixes during the container build."""

import argparse
import ctypes
import hashlib
import json
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


def verified_download(entry: dict) -> bytes:
    url = urlsplit(entry["url"])
    if (
        url.scheme != "https"
        or url.netloc != "deb.debian.org"
        or not url.path.startswith("/debian/pool/main/")
        or url.query
        or url.fragment
    ):
        raise ValueError("Unexpected Debian security package host/path")
    with urllib.request.urlopen(entry["url"], timeout=60) as response:
        data = response.read(30 * 1024 * 1024 + 1)
    if len(data) > 30 * 1024 * 1024:
        raise ValueError("Debian security package exceeds download limit")
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError("Debian security package checksum mismatch")
    return data


def check_runtime(manifest: dict) -> dict:
    installed = {}
    for name, entry in manifest["packages"].items():
        version = subprocess.check_output(
            ["dpkg-query", "--show", "--showformat=${Version}", name], text=True
        ).strip()
        if version != entry["version"]:
            raise ValueError("Debian security runtime differs from pinned package")
        installed[name] = version
    # Check the files against the installed vendor package metadata as well.
    if subprocess.check_output(["dpkg", "--verify", *manifest["packages"]], text=True).strip():
        raise ValueError("Debian security package files differ from installed vendor bytes")
    expat = ctypes.CDLL("libexpat.so.1")
    expat.XML_ExpatVersion.restype = ctypes.c_char_p
    if expat.XML_ExpatVersion() != b"expat_2.8.5":
        raise ValueError("Loaded system Expat differs from reviewed fixed version")
    return installed


def install(manifest_path: Path, output: Path) -> None:
    manifest = json.loads(manifest_path.read_text())
    architecture = subprocess.check_output(["dpkg", "--print-architecture"], text=True).strip()
    with tempfile.TemporaryDirectory() as temp:
        files = []
        for name, entry in manifest["packages"].items():
            if architecture not in entry["binaries"]:
                raise ValueError("Unsupported Debian security package architecture")
            binary = entry["binaries"][architecture]
            path = Path(temp) / (name + ".deb")
            path.write_bytes(verified_download(binary))
            # Validate package identity before any installation, even with a valid hash.
            actual = subprocess.check_output(
                ["dpkg-deb", "--field", str(path), "Package", "Version", "Architecture"],
                text=True,
            )
            expected = (
                f"Package: {name}\nVersion: {entry['version']}\nArchitecture: {architecture}\n"
            )
            if actual != expected:
                raise ValueError("Downloaded Debian package identity mismatch")
            files.append(str(path))
        subprocess.run(
            [
                "dpkg",
                *[f"--path-include=/usr/share/doc/{name}/*" for name in manifest["packages"]],
                "--install",
                *files,
            ],
            check=True,
        )
    if subprocess.check_output(["dpkg", "--audit"], text=True).strip():
        raise ValueError("Debian package dependencies are not satisfied")
    check_runtime(manifest)
    output.mkdir(parents=True, exist_ok=True)
    for name in manifest["packages"]:
        shutil.copyfile(Path("/usr/share/doc") / name / "copyright", output / (name + "-copyright"))
    shutil.copytree("/usr/share/common-licenses", output / "common-licenses", dirs_exist_ok=True)
    (output / "packages.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=Path("tools/debian_security_packages.json")
    )
    parser.add_argument("--output", type=Path, default=Path("/app/licenses/debian-security"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        print(json.dumps(check_runtime(json.loads(args.manifest.read_text()))))
    else:
        install(args.manifest, args.output)
