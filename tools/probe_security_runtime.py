"""Verify the exact supported server runtime, without data mounts or model calls."""

import asyncio
import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path

from lxml import etree
from opennotelm.renderer import SERVER_BROWSER_ARGS
from playwright.async_api import async_playwright


def static_guards(root: Path, policy: dict) -> dict:
    actual_files = sorted(
        str(path.relative_to(root)) for path in (root / "backend/opennotelm").rglob("*.py")
    ) + ["pyproject.toml", "uv.lock"]
    if set(actual_files) != set(policy["runtime_sources"]):
        raise ValueError("Runtime source inventory changed; applicability review required")
    for name, expected in policy["runtime_sources"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Runtime source changed; applicability review required")
    versions = {}
    for advisory in policy["advisories"].values():
        for package, version in advisory["packages"].items():
            actual = subprocess.check_output(
                ["dpkg-query", "--show", "--showformat=${Version}", package], text=True
            ).strip()
            if actual != version:
                raise ValueError("System package changed; applicability review required")
            versions[package] = actual
    status = dict(
        line.split(":", 1)
        for line in Path("/proc/self/status").read_text().splitlines()
        if ":" in line
    )
    nonprivileged = (
        os.getuid() == 10001
        and all(
            int(status[key].strip(), 16) == 0 for key in ("CapEff", "CapPrm", "CapInh", "CapAmb")
        )
        and status["NoNewPrivs"].strip() == "1"
        and not os.access("/etc", os.W_OK)
        and not any(
            line.strip() and not line.lstrip().startswith("#")
            for line in Path("/etc/fstab").read_text().splitlines()
        )
    )
    absent = all(
        not (directory / binary).exists()
        for directory in [Path("/usr/bin"), Path("/usr/sbin"), Path("/usr/lib/systemd")]
        for binary in (
            "mount",
            "umount",
            "nsenter",
            "infocmp",
            "cupsd",
            "cups-browsed",
            "lp",
            "systemd-homed",
            "setfacl",
        )
    )
    absent = (
        absent
        and importlib.util.find_spec("libxml2") is None
        and not any(Path("/usr").rglob("Archive/Tar.pm"))
    )
    native_xml = etree.LIBXML_VERSION == (2, 15, 4) and etree.LIBXSLT_VERSION == (1, 1, 45)
    return {
        "source_verified": True,
        "policy_sha256": hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest(),
        "package_versions": versions,
        "guards": {
            "nonprivileged": nonprivileged,
            "component_absence": absent,
            "native_xml": native_xml,
        },
    }


async def browser_guard() -> bool:
    if (
        SERVER_BROWSER_ARGS != ["--disable-gpu", "--disable-software-rasterizer"]
        or any(
            os.environ.get(key)
            for key in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "RENDER_BROWSER_EXECUTABLE")
        )
        or Path("/dev/dri").exists()
        or Path("/tmp/.X11-unix").exists()
    ):
        return False
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, args=SERVER_BROWSER_ARGS)
        try:
            context = await browser.new_context(java_script_enabled=False, service_workers="block")
            await context.route("**/*", lambda route: route.abort())
            page = await context.new_page()
            await page.set_content(
                "<html><body><h1>OpenNoteLM 浏览器检查</h1>"
                '<svg width="400" height="200"><rect width="400" height="200" fill="#345645"/>'
                '<text x="20" y="80" fill="white">CPU render</text></svg></body></html>'
            )
            await page.screenshot()
            await page.pdf()
            processes = 0
            for proc in Path("/proc").iterdir():
                if not proc.name.isdigit():
                    continue
                try:
                    command = (proc / "cmdline").read_bytes()
                except FileNotFoundError:
                    continue
                if b"chrome" not in command and int(proc.name) != os.getpid():
                    continue
                # Unreadable participating process maps fail the probe; no guessed success.
                maps = (proc / "maps").read_text()
                if "libLLVM" in maps or "libxml2.so" in maps or "libgallium" in maps:
                    return False
                processes += 1
            return processes >= 3
        finally:
            await browser.close()


async def main() -> None:
    policy = json.loads(Path("/app/tools/container_runtime_review.json").read_text())
    report = static_guards(Path("/app"), policy)
    report["guards"]["headless_cpu"] = await browser_guard()
    if not all(report["guards"].values()):
        raise ValueError("Supported runtime security conditions are not satisfied")
    # Public component metadata only; no commands, maps, source text or environment values.
    print(json.dumps(report))


if __name__ == "__main__":
    asyncio.run(main())
