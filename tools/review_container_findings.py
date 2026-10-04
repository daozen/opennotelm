"""Retain raw findings; recognize only five independently verified vendor fixes."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path

EXPIRES = dt.date(2026, 11, 4)
# The October 5 (Asia/Shanghai) review started on October 4 UTC.
REVIEWED = dt.date(2026, 10, 4)
FIXED = {
    "CVE-2026-54369": ("libacl1", "2.4.0-1"),
    "CVE-2026-66046": ("libexpat1", "2.8.5-2"),
    "CVE-2026-76956": ("libexpat1", "2.8.5-2"),
    "CVE-2026-76957": ("libexpat1", "2.8.5-2"),
    "CVE-2026-93990": ("libexpat1", "2.8.5-2"),
}


def review(
    scan: dict,
    runtime: dict,
    today: dt.date | None = None,
    applicability: dict | None = None,
    policy: dict | None = None,
) -> dict:
    # The standalone image scanner also supports macOS's system Python 3.9.
    today = today or dt.datetime.now(dt.timezone.utc).date()  # noqa: UP017
    if not isinstance(scan.get("Results"), list) or not any(
        result.get("Type") == "debian" for result in scan["Results"]
    ):
        raise ValueError("Expected a complete Debian container vulnerability scan")
    verified, not_affected, unresolved, counts = [], [], [], collections.Counter()
    for result in scan.get("Results", []):
        for row in result.get("Vulnerabilities", []):
            counts[row["Severity"]] += 1
            if row["Severity"] not in {"HIGH", "CRITICAL"}:
                continue
            advisory = row["VulnerabilityID"]
            entry = {
                "advisory": advisory,
                "package": row["PkgName"],
                "version": row["InstalledVersion"],
                "severity": row["Severity"],
            }
            expected = FIXED.get(advisory)
            if (
                REVIEWED <= today < EXPIRES
                and result.get("Type") == "debian"
                and expected == (entry["package"], entry["version"])
                and runtime.get(entry["package"]) == entry["version"]
            ):
                entry["status"] = "verified_vendor_fix"
                entry["evidence"] = "https://security-tracker.debian.org/tracker/" + advisory
                verified.append(entry)
            elif (
                policy is not None
                and applicability is not None
                and dt.date.fromisoformat(policy["reviewed"])
                <= today
                < dt.date.fromisoformat(policy["expires"])
                and applicability.get("source_verified") is True
                and applicability.get("policy_sha256")
                == hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest()
                and result.get("Type") == "debian"
                and (decision := policy["advisories"].get(advisory)) is not None
                and decision["packages"].get(entry["package"]) == entry["version"]
                and applicability.get("package_versions", {}).get(entry["package"])
                == entry["version"]
                and all(
                    applicability.get("guards", {}).get(guard) is True
                    for guard in decision["guards"]
                )
            ):
                entry.update(
                    status=decision["status"],
                    evidence=decision["evidence"],
                    reason=decision["reason"],
                )
                not_affected.append(entry)
            else:
                unresolved.append(entry)
    return {
        "review_date": today.isoformat(),
        "review_expires": EXPIRES.isoformat(),
        "raw_counts": dict(sorted(counts.items())),
        "verified_fixed": verified,
        "not_affected_in_supported_runtime": not_affected,
        "unresolved": unresolved,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scan", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--applicability", type=Path)
    parser.add_argument("--policy", type=Path)
    args = parser.parse_args()
    report = review(
        json.loads(args.scan.read_text()),
        json.loads(args.runtime.read_text()),
        applicability=json.loads(args.applicability.read_text()) if args.applicability else None,
        policy=json.loads(args.policy.read_text()) if args.policy else None,
    )
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print("Container raw vulnerability findings by severity:", report["raw_counts"])
    print("Independently verified vendor fixes:", len(report["verified_fixed"]))
    print(
        "Not affected in the verified supported runtime:",
        len(report["not_affected_in_supported_runtime"]),
    )
    remaining = collections.Counter(row["severity"] for row in report["unresolved"])
    print("Unresolved high/critical records:", dict(sorted(remaining.items())))
    if report["unresolved"]:
        raise SystemExit("Review and resolve remaining high/critical findings before publishing.")
