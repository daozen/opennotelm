"""Render bilingual release notes with version-pinned GitHub documentation links."""

import argparse
import re
from pathlib import Path, PurePosixPath

from release_check import validate_tag


def render(root: Path, tag: str) -> str:
    validate_tag(tag, tag[1:].split("-", 1)[0])
    source = root / "docs/releases/first-beta.md"
    text = source.read_text()

    def replace(match: re.Match) -> str:
        target = match.group(1)
        if re.match(r"[a-zA-Z][\w+.-]*:", target) or target.startswith("#"):
            return match.group(0)
        resolved = (source.parent / target).resolve().relative_to(root.resolve())
        return f"](https://github.com/daozen/opennotelm/blob/{tag}/{PurePosixPath(resolved)})"

    return re.sub(r"\]\(([^)]+)\)", replace, text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(Path.cwd(), args.tag))
