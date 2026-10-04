"""Extract article structure from saved HTML without executing scripts/resources."""

import json
import logging
import re
from pathlib import Path
from urllib.parse import urljoin

from trafilatura import bare_extraction
from trafilatura.settings import use_config
from trafilatura.utils import load_html

from .documents import Document, DocumentBlock, DocumentImage, DocumentNode, stable_id
from .errors import AppError

WEB_PARSER_VERSION = "web-v1"

# Extractor warnings can interpolate original URLs/metadata. Keep operational
# errors in our typed job records instead of emitting third-party content logs.
for package in ("trafilatura", "htmldate", "courlan", "justext"):
    logger = logging.getLogger(package)
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    for name in list(logging.Logger.manager.loggerDict):
        if name == package or name.startswith(package + "."):
            logging.getLogger(name).disabled = True


class WebParser:
    def __init__(self, max_images=50):
        self.max_images = max_images

    def parse(self, path: Path, source_id: str, title: str, save_images=False) -> Document:
        manifest = json.loads(path.with_name("web.json").read_text())
        config = use_config()
        config.set("DEFAULT", "MAX_TREE_SIZE", "100000")
        extracted = bare_extraction(
            path.read_bytes(),
            url=manifest["final_url"],
            include_comments=False,
            include_tables=True,
            include_images=True,
            include_links=True,
            include_formatting=True,
            with_metadata=True,
            config=config,
        )
        if extracted is None or extracted.body is None:
            raise AppError("WEB_NO_CONTENT", "No readable article was found on this page.")
        title = extracted.title or title
        root_id = stable_id(source_id, "root")
        document = Document(
            title,
            [DocumentNode(root_id, None, "document", title, 0, 0)],
            [],
            {
                **manifest,
                "author": extracted.author,
                "published_date": extracted.date,
                "site_name": extracted.sitename,
                "extractor": "trafilatura",
            },
        )
        stack = [(0, root_id)]
        positions = {}
        for index, element in enumerate(extracted.body):
            kind = element.tag
            value = "".join(element.itertext()).strip()
            if kind == "head":
                match = re.fullmatch(r"h([1-6])", element.get("rend", ""))
                depth = int(match[1]) if match else 2
                while stack[-1][0] >= depth:
                    stack.pop()
                node_id = stable_id(source_id, f"web:heading:{index}")
                document.nodes.append(
                    DocumentNode(
                        node_id, stack[-1][1], "heading", value, depth, len(document.nodes)
                    )
                )
                stack.append((depth, node_id))
                kind = "heading"
            elif kind == "table":
                value = "\n".join(
                    "\t".join("".join(cell.itertext()).strip() for cell in row)
                    for row in element
                    if row.tag == "row"
                )
            elif kind == "list":
                value = "\n".join("".join(item.itertext()).strip() for item in element)
                kind = "list"
            elif kind == "graphic":
                # Preserve the description as source text, never infer an unseen image.
                value = element.get("alt") or element.get("title") or ""
                kind = "caption"
            else:
                kind = {"p": "paragraph", "quote": "quote", "code": "code"}.get(kind, "paragraph")
            if value:
                document.blocks.append(
                    DocumentBlock(
                        stable_id(source_id, f"web:body:{index}"),
                        stack[-1][1],
                        kind,
                        len(document.blocks),
                        value,
                        {"url": manifest["final_url"], "snapshot_index": index},
                    )
                )
            raw_text = "".join(element.itertext()).strip()
            if raw_text:
                positions.setdefault(raw_text, (len(document.blocks) - 1, stack[-1][1], index))
        if not any(
            b.type not in ("heading", "caption") and b.text.strip() for b in document.blocks
        ):
            raise AppError("WEB_NO_CONTENT", "No readable article was found on this page.")
        if save_images:
            self.collect_images(
                path.read_bytes(), manifest["final_url"], config, document, source_id, positions
            )
        return document

    def collect_images(self, html, url, config, document, source_id, positions):
        # A second extraction discovers images without changing published text IDs/offsets.
        # Synthetic image URLs also let the extractor retain extensionless CDN/srcset images.
        tree = load_html(html)
        if tree is None:
            return
        references = {}
        base = tree.find(".//base")
        image_base = urljoin(url, base.get("href", "")) if base is not None else url
        for index, element in enumerate(tree.iter("img")):
            if element.get("aria-hidden") == "true":
                continue
            try:
                if (
                    0 < int(element.get("width", "0")) <= 32
                    and 0 < int(element.get("height", "0")) <= 32
                ):
                    continue
            except ValueError:
                pass
            if re.search(
                r"(?:^|[\s_-])(logo|avatar|icon|emoji|tracking)(?:$|[\s_-])",
                element.get("class", ""),
                re.I,
            ):
                continue
            src = element.get("data-src") or element.get("data-original") or element.get("src")
            srcset = element.get("data-srcset") or element.get("srcset", "")
            parent = element.getparent()
            if parent is not None and parent.tag == "picture":
                for source in parent.iter("source"):
                    if source.get("type", "") not in (
                        "",
                        "image/png",
                        "image/jpeg",
                        "image/webp",
                        "image/gif",
                        "image/avif",
                    ):
                        continue
                    candidate_set = source.get("data-srcset") or source.get("srcset", "")
                    if candidate_set:
                        srcset = candidate_set
                        break
            candidates = []
            for candidate in srcset.split(","):
                parts = candidate.strip().split()
                if len(parts) == 1:
                    candidates.append((1, parts[0]))
                elif len(parts) == 2 and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?[wx]", parts[1]):
                    candidates.append((float(parts[1][:-1]), parts[0]))
            if candidates:
                src = max(candidates)[1]
            if not src:
                continue
            token = f"https://opennotelm.invalid/image-{index}.png"
            references[token] = (
                index,
                urljoin(image_base, src),
                element.get("alt") or element.get("title") or "",
            )
            # No request is ever sent to this address. The original reference is saved separately.
            element.attrib.clear()
            element.set("src", token)
        extracted = bare_extraction(
            tree,
            url=url,
            include_comments=False,
            include_tables=True,
            include_images=True,
            include_links=True,
            include_formatting=True,
            with_metadata=False,
            config=config,
        )
        if extracted is None or extracted.body is None:
            return
        position = (-1, document.nodes[0].id, 0)
        found = 0
        seen = set()
        for element in extracted.body:
            position = positions.get("".join(element.itertext()).strip(), position)
            for graphic in element.iter("graphic"):
                reference = references.get(graphic.get("src"))
                if reference is None or reference[0] in seen:
                    continue
                seen.add(reference[0])
                found += 1
                if len(document.images) >= self.max_images:
                    continue
                index, image_url, alt = reference
                document.images.append(
                    DocumentImage(
                        stable_id(source_id, f"web:image:{index}"),
                        position[1],
                        position[0] + 0.5 + 0.4 * len(document.images) / (self.max_images + 1),
                        {
                            "url": url,
                            "snapshot_index": position[2],
                            "image_index": index,
                            "source_image_url": image_url,
                            "alt": alt,
                        },
                    )
                )
        document.metadata["web_image_limit_skipped"] = max(0, found - len(document.images))
