"""Vendor hotfixes fail closed on unexpected bytes, identities and runtime versions."""

import hashlib
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace

import pytest


def module():
    path = Path(__file__).resolve().parents[2] / "tools/install_debian_security.py"
    spec = importlib.util.spec_from_file_location("debian_security", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def review_module():
    path = Path(__file__).resolve().parents[2] / "tools/review_container_findings.py"
    spec = importlib.util.spec_from_file_location("container_review", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize(
    "url",
    [
        "http://deb.debian.org/debian/pool/main/e/expat/package.deb",
        "https://example.com/debian/pool/main/package.deb",
        "https://deb.debian.org/private/package.deb",
        "https://deb.debian.org/debian/pool/main/package.deb?key=example",
        "https://snapshot.debian.org/archive/debian/latest/pool/main/package.deb",
        "https://snapshot.debian.org/archive/debian/20260930T203251Z/pool/main/../private",
        "https://snapshot.debian.org/archive/debian/20260930T203251Z/pool/main/%2e%2e/private",
        "https://snapshot.debian.org.example.com/archive/debian/20260930T203251Z/pool/main/p.deb",
        "https://snapshot.debian.org:443/archive/debian/20260930T203251Z/pool/main/p.deb",
        "https://snapshot.debian.org/file/not-a-hash/p.deb",
    ],
)
def test_vendor_download_rejects_unreviewed_destinations_without_network(monkeypatch, url):
    helper = module()
    monkeypatch.setattr(helper.urllib.request, "build_opener", lambda *a: pytest.fail("network"))
    with pytest.raises(ValueError, match="host/path"):
        helper.verified_download({"url": url, "sha256": "0" * 64})


def test_vendor_download_requires_exact_reviewed_bytes(monkeypatch):
    helper = module()
    data = b"synthetic vendor package"
    monkeypatch.setattr(
        helper.urllib.request,
        "build_opener",
        lambda *a: SimpleNamespace(open=lambda *a, **k: io.BytesIO(data)),
    )
    entry = {"url": "https://deb.debian.org/debian/pool/main/package.deb", "sha256": "0" * 64}
    with pytest.raises(ValueError, match="checksum"):
        helper.verified_download(entry)
    entry["sha256"] = hashlib.sha256(data).hexdigest()
    assert helper.verified_download(entry) == data


def test_wrong_package_identity_cannot_reach_installer(monkeypatch, tmp_path):
    import json

    helper = module()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"packages": {"libexpat1": {"version": "2.9.0-1", "binaries": {"arm64": {}}}}})
    )
    monkeypatch.setattr(helper, "verified_download", lambda *a: b"synthetic package")
    monkeypatch.setattr(
        helper.subprocess,
        "check_output",
        lambda argv, **kwargs: "arm64\n" if argv[0] == "dpkg" else "Package: unexpected\n",
    )
    monkeypatch.setattr(helper.subprocess, "run", lambda *a, **k: pytest.fail("installation"))
    with pytest.raises(ValueError, match="identity"):
        helper.install(manifest, tmp_path / "notices")


def test_runtime_rejects_package_version_drift_before_native_probe(monkeypatch):
    helper = module()
    monkeypatch.setattr(helper.subprocess, "check_output", lambda *a, **k: "2.8.3-1\n")
    monkeypatch.setattr(helper.ctypes, "CDLL", lambda *a: pytest.fail("native probe"))
    with pytest.raises(ValueError, match="runtime"):
        helper.check_runtime({"packages": {"libexpat1": {"version": "2.9.0-1"}}})


def fixture_scan(version="2.9.0-1", advisory="CVE-2026-93990", ecosystem="debian"):
    return {
        "Results": [
            {"Type": "debian"},
            {
                "Type": ecosystem,
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": advisory,
                        "PkgName": "libexpat1",
                        "InstalledVersion": version,
                        "Severity": "HIGH",
                    }
                ],
            },
        ]
    }


def test_verified_vendor_fix_preserves_raw_record_and_expiry():
    import datetime as dt

    helper = review_module()
    scan = fixture_scan()
    report = helper.review(scan, {"libexpat1": "2.9.0-1"}, dt.date(2026, 10, 14))
    assert report["raw_counts"] == {"HIGH": 1}
    assert len(report["verified_fixed"]) == 1 and not report["unresolved"]
    assert len(scan["Results"][-1]["Vulnerabilities"]) == 1
    expired = helper.review(scan, {"libexpat1": "2.9.0-1"}, helper.EXPIRES)
    assert len(expired["unresolved"]) == 1 and not expired["verified_fixed"]


@pytest.mark.parametrize(
    "case", ["old_version", "new_advisory", "different_ecosystem", "unverified"]
)
def test_vendor_review_never_covers_other_versions_advisories_or_unverified_runtime(case):
    import datetime as dt

    helper = review_module()
    scan = fixture_scan(
        version="2.8.3-1" if case == "old_version" else "2.9.0-1",
        advisory="CVE-2026-99999" if case == "new_advisory" else "CVE-2026-93990",
        ecosystem="python-pkg" if case == "different_ecosystem" else "debian",
    )
    runtime = {} if case == "unverified" else {"libexpat1": "2.9.0-1"}
    report = helper.review(scan, runtime, dt.date(2026, 10, 14))
    assert len(report["unresolved"]) == 1 and not report["verified_fixed"]


@pytest.mark.parametrize("scan", [{}, {"Results": []}, {"Results": [{"Type": "python-pkg"}]}])
def test_vendor_review_rejects_missing_os_scan(scan):
    with pytest.raises(ValueError, match="complete Debian"):
        review_module().review(scan, {"libexpat1": "2.9.0-1"})


def scoped_review_fixture():
    import json

    helper = review_module()
    policy = {
        "reviewed": "2026-10-04",
        "expires": "2026-11-04",
        "advisories": {
            "CVE-2026-93990": {
                "packages": {"libexpat1": "2.8.3-1"},
                "guards": ["headless_cpu"],
                "status": "not_affected_in_supported_runtime",
                "evidence": "synthetic",
                "reason": "synthetic scoped applicability test",
            }
        },
    }
    applicability = {
        "source_verified": True,
        "policy_sha256": hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest(),
        "package_versions": {"libexpat1": "2.8.3-1"},
        "guards": {"headless_cpu": True},
    }
    return helper, fixture_scan(version="2.8.3-1"), policy, applicability


@pytest.mark.parametrize("change", ["none", "guard", "source", "package", "policy", "expired"])
def test_conditional_review_requires_all_exact_runtime_evidence(change):
    import datetime as dt

    helper, scan, policy, applicability = scoped_review_fixture()
    if change == "guard":
        applicability["guards"]["headless_cpu"] = False
    elif change == "source":
        applicability["source_verified"] = False
    elif change == "package":
        applicability["package_versions"] = {}
    elif change == "policy":
        applicability["policy_sha256"] = "0" * 64
    today = dt.date(2026, 11, 4) if change == "expired" else dt.date(2026, 10, 14)
    report = helper.review(scan, {}, today, applicability, policy)
    assert len(report["not_affected_in_supported_runtime"]) == (1 if change == "none" else 0)
    assert len(report["unresolved"]) == (0 if change == "none" else 1)


@pytest.mark.parametrize("change", ["added_module", "changed_module"])
def test_source_guard_requires_reassessment_after_runtime_changes(tmp_path, change):
    path = Path(__file__).resolve().parents[2] / "tools/probe_security_runtime.py"
    spec = importlib.util.spec_from_file_location("runtime_probe", path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    source = tmp_path / "backend/opennotelm"
    source.mkdir(parents=True)
    files = [source / "example.py", tmp_path / "pyproject.toml", tmp_path / "uv.lock"]
    for file in files:
        file.write_bytes(b"reviewed synthetic code")
    policy = {
        "runtime_sources": {
            str(p.relative_to(tmp_path)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
        }
    }
    if change == "added_module":
        (source / "new_module.py").write_bytes(b"unreviewed")
    else:
        files[0].write_bytes(b"changed unreviewed code")
    with pytest.raises(ValueError, match="review required"):
        helper.static_guards(tmp_path, policy)


@pytest.mark.parametrize(
    "url",
    [
        "https://snapshot.debian.org/archive/debian/20260930T203251Z/pool/main/e/expat/p.deb",
        "https://snapshot.debian.org/file/" + "a" * 40 + "/p.deb",
    ],
)
def test_snapshot_download_keeps_hash_and_size_checks(monkeypatch, url):
    helper = module()
    data = b"same original reviewed bytes"
    monkeypatch.setattr(
        helper.urllib.request,
        "build_opener",
        lambda *a: SimpleNamespace(open=lambda *a, **k: io.BytesIO(data)),
    )
    assert (
        helper.verified_download({"url": url, "sha256": hashlib.sha256(data).hexdigest()}) == data
    )
    with pytest.raises(ValueError, match="checksum"):
        helper.verified_download({"url": url, "sha256": "0" * 64})


@pytest.mark.parametrize(
    "target",
    [
        "http://snapshot.debian.org/file/" + "a" * 40,
        "https://example.com/package.deb",
        "http://127.0.0.1/private",
    ],
)
def test_debian_redirect_rejects_unapproved_destination_before_following(target):
    helper = module()
    request = helper.urllib.request.Request("https://deb.debian.org/debian/pool/main/p.deb")
    with pytest.raises(ValueError, match="host/path"):
        helper.DebianRedirectHandler().redirect_request(request, None, 302, "", {}, target)


def test_current_snapshot_manifest_pins_reviewed_fixed_expat():
    import json

    manifest = json.loads(
        (Path(__file__).resolve().parents[2] / "tools/debian_security_packages.json").read_text()
    )
    entry = manifest["packages"]["libexpat1"]
    assert entry["version"] == "2.9.0-1"
    assert (
        entry["binaries"]["arm64"]["sha256"]
        == "810a63c52c8ff78f30f04da8c78f133a34c24504caed3f9e673ddda0c878f53d"
    )
    assert (
        entry["binaries"]["amd64"]["sha256"]
        == "190d7f5e45f070c42a12f708fe417d6636cb45fae71175203168bb5c3695081b"
    )
    assert all(
        "20261006T024027Z" in p["url"] for p in [*entry["binaries"].values(), *entry["sources"]]
    )


@pytest.mark.parametrize("version", ["2.8.3-1", "2.8.5-2"])
def test_new_expat_advisory_never_whitelists_older_runtime(version):
    import datetime as dt

    helper = review_module()
    report = helper.review(
        fixture_scan(version, "CVE-2026-77214"), {"libexpat1": version}, dt.date(2026, 10, 14)
    )
    assert report["unresolved"] and not report["verified_fixed"]


def test_new_expat_fix_requires_exact_native_version_and_same_expiry():
    import datetime as dt

    helper = review_module()
    report = helper.review(
        fixture_scan("2.9.0-1", "CVE-2026-77214"), {"libexpat1": "2.9.0-1"}, dt.date(2026, 10, 14)
    )
    assert len(report["verified_fixed"]) == 1 and not report["unresolved"]
    report = helper.review(
        fixture_scan("2.9.0-1", "CVE-2026-77214"), {"libexpat1": "2.9.0-1"}, helper.EXPIRES
    )
    assert report["unresolved"] and not report["verified_fixed"]
