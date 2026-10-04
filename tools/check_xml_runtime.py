"""Check actual XML libraries, including statically embedded wheel components."""

import argparse
import json
from pathlib import Path


def validate(manifest: dict, compiled: tuple, runtime: tuple, xslt: tuple) -> None:
    expected_xml = tuple(int(p) for p in manifest["libxml2"]["version"].split("."))
    expected_xslt = tuple(int(p) for p in manifest["libxslt"]["version"].split("."))
    if expected_xml < (2, 15, 4) or expected_xslt < (1, 1, 45):
        raise ValueError("XML manifest is below the reviewed security baseline")
    if compiled != expected_xml or runtime != expected_xml or xslt != expected_xslt:
        raise ValueError("XML runtime differs from reviewed native source versions")


if __name__ == "__main__":
    from lxml import etree

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    sources = json.loads(Path("/app/licenses/native-xml/sources.json").read_text())
    if etree.LXML_VERSION[:3] != tuple(int(p) for p in sources["lxml"]["version"].split(".")):
        raise ValueError("lxml runtime differs from locked source version")
    validate(sources, etree.LIBXML_COMPILED_VERSION, etree.LIBXML_VERSION, etree.LIBXSLT_VERSION)
    if args.json:
        print(
            json.dumps(
                {
                    "sources": sources,
                    "libxml2_compiled": etree.LIBXML_COMPILED_VERSION,
                    "libxml2_runtime": etree.LIBXML_VERSION,
                    "libxslt_runtime": etree.LIBXSLT_VERSION,
                }
            )
        )
    else:
        print("Reviewed XML runtime:", etree.LIBXML_VERSION, etree.LIBXSLT_VERSION)
