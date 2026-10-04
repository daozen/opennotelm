"""Add verified embedded XML components without replacing OS-package findings."""

import argparse
import json
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
    lxml_ref = f"pkg:pypi/lxml@{sources['lxml']['version']}"
    if not any(c.get("bom-ref") == lxml_ref for c in bom["components"]):
        raise ValueError("SBOM does not contain the verified lxml distribution")
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sbom", type=Path, required=True)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = enrich(json.loads(args.sbom.read_text()), json.loads(args.native.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
