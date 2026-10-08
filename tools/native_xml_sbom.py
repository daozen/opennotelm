"""Add verified embedded XML components without replacing OS-package findings."""

import argparse
import json
import re
from pathlib import Path

from check_xml_runtime import validate


def enrich(bom: dict, report: dict) -> dict:
    sources = report["sources"]
    validate(
        sources,
        tuple(report["libxml2_compiled"]),
        tuple(report["libxml2_runtime"]),
        tuple(report["libxslt_runtime"]),
    )
    version = sources["lxml"]["version"]
    lxml_purl = f"pkg:pypi/lxml@{version}"
    matches = [c for c in bom["components"] if c.get("purl", c.get("bom-ref")) == lxml_purl]
    if any(not c.get("bom-ref") for c in matches):
        raise ValueError("SBOM does not contain the verified lxml distribution")
    # A BOM reference identifies a component; it need not equal its package URL.
    # Trivy uses UUID references when an installation cache duplicates a package.
    paths = {
        c["bom-ref"]: [
            p["value"]
            for p in c.get("properties", [])
            if p.get("name") == "aquasecurity:trivy:FilePath"
        ]
        for c in matches
    }
    if any(paths.values()):
        matches = [
            c
            for c in matches
            if any(
                re.fullmatch(
                    rf"/?app/\.venv/lib/python[\d.]+/site-packages/lxml-{re.escape(version)}\.dist-info/METADATA",
                    path,
                )
                for path in paths[c["bom-ref"]]
            )
        ]
    if len(matches) != 1 or not matches[0].get("bom-ref"):
        raise ValueError("SBOM does not contain the verified lxml distribution")
    lxml_ref = matches[0]["bom-ref"]
    refs = []
    for name in ("libxml2", "libxslt"):
        entry = sources[name]
        ref = f"pkg:generic/{name}@{entry['version']}?qualifier=opennotelm-static"
        if any(c.get("bom-ref") == ref for c in bom["components"]):
            raise ValueError("Embedded XML components already recorded")
        refs.append(ref)
        bom["components"].append(
            {
                "bom-ref": ref,
                "type": "library",
                "name": name,
                "version": entry["version"],
                "purl": ref,
                "licenses": [{"license": {"id": entry["license"]}}],
                "properties": [{"name": "opennotelm:linkage", "value": "static-in-lxml"}],
                "externalReferences": [
                    {
                        "type": "distribution",
                        "url": entry["url"],
                        "hashes": [{"alg": "SHA-256", "content": entry["sha256"]}],
                    }
                ],
            }
        )
    dependencies = bom.setdefault("dependencies", [])
    for dependency in dependencies:
        if dependency["ref"] == lxml_ref:
            dependency.setdefault("dependsOn", []).extend(refs)
            break
    else:
        dependencies.append({"ref": lxml_ref, "dependsOn": refs})
    return bom


def enrich_audio(bom: dict, audio: dict) -> dict:
    if audio.get("restricted_audio") is not True:
        raise ValueError("Audio runtime has not passed the reduced-build probe")
    source = audio["source"]
    ref = f"pkg:generic/ffmpeg@{source['version']}?qualifier=opennotelm-audio"
    if any(c.get("bom-ref") == ref for c in bom["components"]):
        raise ValueError("Audio component already recorded")
    bom["components"].append(
        {
            "bom-ref": ref,
            "type": "application",
            "name": "ffmpeg",
            "version": source["version"],
            "purl": ref,
            "cpe": f"cpe:2.3:a:ffmpeg:ffmpeg:{source['version']}:*:*:*:*:*:*:*",
            "licenses": [{"license": {"id": source["license"]}}],
            "hashes": [{"alg": "SHA-256", "content": audio["binary_sha256"]}],
            "externalReferences": [
                {
                    "type": "distribution",
                    "url": source["url"],
                    "hashes": [{"alg": "SHA-256", "content": source["sha256"]}],
                }
            ],
        }
    )
    return bom


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sbom", type=Path, required=True)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = enrich(json.loads(args.sbom.read_text()), json.loads(args.native.read_text()))
    if args.audio:
        result = enrich_audio(result, json.loads(args.audio.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
