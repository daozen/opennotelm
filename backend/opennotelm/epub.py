import posixpath
import re
import stat
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
from zipfile import BadZipFile, ZipFile

from bs4 import BeautifulSoup
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from .documents import Document, DocumentBlock, DocumentImage, DocumentNode, stable_id
from .errors import AppError

PARSER_VERSION = "epub-v1"


def safe_reference(base: str, href: str) -> tuple[str, str]:
    url = urlsplit(href)
    if url.scheme or url.netloc or url.query:
        raise AppError(
            "EPUB_UNSAFE_REFERENCE", "The book references unsupported external resources."
        )
    path = unquote(url.path)
    if "\\" in path or "\x00" in path or path.startswith("/"):
        raise AppError("EPUB_UNSAFE_PATH", "The book contains an unsafe resource path.")
    joined = posixpath.normpath(posixpath.join(posixpath.dirname(base), path)) if path else base
    if joined.startswith("../") or joined in ("..", "."):
        raise AppError("EPUB_UNSAFE_PATH", "The book contains a path outside its archive.")
    return joined, unquote(url.fragment)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


class EpubParser:
    def __init__(
        self,
        max_entries=10000,
        max_uncompressed_bytes=400 * 1024 * 1024,
        max_entry_bytes=20 * 1024 * 1024,
        max_compression_ratio=1000,
    ):
        self.max_entries = max_entries
        self.max_uncompressed_bytes = max_uncompressed_bytes
        self.max_entry_bytes = max_entry_bytes
        self.max_compression_ratio = max_compression_ratio

    def validate_archive(self, archive: ZipFile) -> None:
        entries = archive.infolist()
        if (
            len(entries) > self.max_entries
            or sum(e.file_size for e in entries) > self.max_uncompressed_bytes
        ):
            raise AppError("EPUB_ZIP_LIMIT", "The book exceeds safe archive size limits.")
        seen = set()
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in entry.filename
                or entry.filename in seen
                or stat.S_ISLNK(entry.external_attr >> 16)
            ):
                raise AppError("EPUB_UNSAFE_PATH", "The book contains unsafe archive paths.")
            if (
                entry.file_size > self.max_entry_bytes
                or entry.file_size / max(1, entry.compress_size) > self.max_compression_ratio
                or entry.flag_bits & 1
            ):
                raise AppError(
                    "EPUB_ZIP_LIMIT", "The book contains oversized or encrypted resources."
                )
            seen.add(entry.filename)

    def xml(self, archive: ZipFile, path: str):
        return ET.fromstring(archive.read(path))

    def toc(self, archive: ZipFile, opf_path: str, manifest: dict, spine) -> list[dict]:
        nav = next((i for i in manifest.values() if "nav" in i.get("properties", "").split()), None)
        if nav:
            path, _ = safe_reference(opf_path, nav["href"])
            soup = BeautifulSoup(archive.read(path), "html.parser")
            container = next(
                (n for n in soup.find_all("nav") if "toc" in n.get("epub:type", "").split()), None
            )
            if container:
                entries = []
                for anchor in container.find_all("a", href=True):
                    try:
                        href, fragment = safe_reference(path, anchor["href"])
                    except AppError:
                        continue
                    depth = len([p for p in anchor.parents if p.name in ("ol", "ul")])
                    entries.append(
                        {
                            "title": clean_text(anchor.get_text(" ")),
                            "href": href,
                            "fragment": fragment,
                            "depth": depth,
                        }
                    )
                return entries
        ncx_id = spine.get("toc")
        ncx = manifest.get(ncx_id) or next(
            (i for i in manifest.values() if i.get("media-type") == "application/x-dtbncx+xml"),
            None,
        )
        if ncx:
            path, _ = safe_reference(opf_path, ncx["href"])
            root = self.xml(archive, path)
            entries = []

            def visit(parent, depth):
                for point in parent.findall("{*}navPoint"):
                    label = point.find("{*}navLabel/{*}text")
                    content = point.find("{*}content")
                    if content is not None:
                        href, fragment = safe_reference(path, content.attrib["src"])
                        entries.append(
                            {
                                "title": clean_text(label.text or "") if label is not None else "",
                                "href": href,
                                "fragment": fragment,
                                "depth": depth,
                            }
                        )
                    visit(point, depth + 1)

            nav_map = root.find("{*}navMap")
            if nav_map is not None:
                visit(nav_map, 1)
            return entries
        return []

    def parse(self, path: Path, source_id: str) -> Document:
        try:
            with ZipFile(path) as archive:
                self.validate_archive(archive)
                container = self.xml(archive, "META-INF/container.xml")
                rootfile = container.find(".//{*}rootfile")
                if rootfile is None:
                    raise ValueError
                opf_path, _ = safe_reference("root", rootfile.attrib["full-path"])
                package = self.xml(archive, opf_path)
                title_node = package.find(".//{*}metadata/{*}title")
                title = clean_text(title_node.text or "") if title_node is not None else path.stem
                manifest = {
                    i.attrib["id"]: i.attrib for i in package.findall("{*}manifest/{*}item")
                }
                spine = package.find("{*}spine")
                if spine is None:
                    raise ValueError
                toc = self.toc(archive, opf_path, manifest, spine)
                root_id = stable_id(source_id, "root")
                document = Document(
                    title,
                    [DocumentNode(root_id, None, "document", title, 0, 0)],
                    [],
                    {"toc": toc, "parser_version": PARSER_VERSION},
                )
                resources = {}
                toc_sections = []
                for index, ref in enumerate(spine.findall("{*}itemref")):
                    item = manifest[ref.attrib["idref"]]
                    if item.get("media-type") not in ("application/xhtml+xml", "text/html"):
                        continue
                    href, _ = safe_reference(opf_path, item["href"])
                    soup = BeautifulSoup(archive.read(href), "html.parser")
                    for unsafe in soup.find_all(
                        ["script", "style", "head", "iframe", "object", "embed", "svg", "form"]
                    ):
                        unsafe.decompose()
                    heading = soup.find(re.compile("^h[1-6]$"))
                    chapter_title = next(
                        (t["title"] for t in toc if t["href"] == href and not t["fragment"]),
                        clean_text(heading.get_text(" ")) if heading else f"Chapter {index + 1}",
                    )
                    chapter_id = stable_id(source_id, f"node:{href}")
                    document.nodes.append(
                        DocumentNode(
                            chapter_id,
                            root_id,
                            "chapter",
                            chapter_title,
                            1,
                            len(document.nodes),
                            metadata={"href": href, "spine_index": index},
                        )
                    )
                    positions = self.extract_blocks(
                        soup.body or soup, document, source_id, href, index, chapter_id
                    )
                    current_id = chapter_id
                    after_ordinal = (
                        min(
                            (position[1] - 1 for position in positions.values()),
                            default=len(document.blocks) - 1,
                        )
                        + 0.5
                    )
                    image_index = 0
                    content_positions, element_positions, element_ordinals = [], {}, {}
                    for position, image in enumerate(soup.descendants):
                        element_ordinals[id(image)] = position
                        if getattr(image, "attrs", None):
                            anchor = image.get("id") or image.get("name")
                            if anchor:
                                element_positions[anchor] = image
                        if id(image) in positions:
                            current_id, ordinal = positions[id(image)]
                            after_ordinal = ordinal + 0.5
                            content_positions.append((position, document.blocks[ordinal].id))
                        if getattr(image, "name", None) != "img" or not image.get("src"):
                            continue
                        try:
                            resource, _ = safe_reference(href, image["src"])
                        except AppError:
                            continue  # Never fetch external images or unsafe relative paths.
                        if resource not in archive.namelist():
                            continue
                        if resource not in resources:
                            resources[resource] = archive.read(resource)
                        document.images.append(
                            DocumentImage(
                                stable_id(source_id, f"epub:image:{href}:{image_index}"),
                                current_id,
                                after_ordinal,
                                {"href": href, "spine_index": index, "image_index": image_index},
                                data=resources[resource],
                            )
                        )
                        image_index += 1
                        content_positions.append((position, document.images[-1].id))
                    entries = [
                        entry for entry in toc if entry["href"] == href and entry["fragment"]
                    ]

                    def boundary(
                        entry,
                        element_positions=element_positions,
                        positions=positions,
                        element_ordinals=element_ordinals,
                    ):
                        element = element_positions.get(entry["fragment"])
                        if element is None:
                            return None
                        ancestor = next(
                            (p for p in [element, *element.parents] if id(p) in positions), element
                        )
                        return element_ordinals.get(id(ancestor))

                    boundaries = [(entry, boundary(entry)) for entry in entries]
                    for toc_index, (entry, start) in enumerate(boundaries):
                        if start is None:
                            continue
                        end = next(
                            (
                                next_start
                                for other, next_start in boundaries[toc_index + 1 :]
                                if next_start is not None
                                and next_start > start
                                and other["depth"] <= entry["depth"]
                            ),
                            float("inf"),
                        )
                        toc_sections.append(
                            {
                                **entry,
                                "block_ids": [
                                    identity
                                    for position, identity in content_positions
                                    if start <= position < end
                                ],
                            }
                        )
                if not document.blocks and not document.images:
                    raise AppError("EPUB_NO_TEXT", "The book contains no readable text.")
                document.metadata["toc_sections"] = toc_sections
                return document
        except AppError:
            raise
        except (
            BadZipFile,
            KeyError,
            ValueError,
            OSError,
            DefusedXmlException,
            ET.ParseError,
            RuntimeError,
        ) as exc:
            raise AppError(
                "EPUB_PARSE_FAILED", "The EPUB structure could not be parsed. Check the file."
            ) from exc

    def extract_blocks(self, body, document, source_id, href, spine_index, chapter_id):
        stack = [(1, chapter_id)]
        positions = {}
        tags = body.find_all(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "blockquote", "ul", "ol", "pre", "table"]
        )
        for element in tags:
            if any(
                parent.name in ("blockquote", "ul", "ol", "pre", "table")
                for parent in element.parents
            ):
                continue
            name = element.name
            text = element.get_text("\n" if name in ("pre", "table") else " ", strip=True)
            if name in ("ul", "ol"):
                text = "\n".join(
                    f"• {clean_text(li.get_text(' '))}"
                    for li in element.find_all("li", recursive=False)
                )
            elif name != "pre":
                text = clean_text(text) if name != "table" else text
            if not text:
                continue
            block_id = stable_id(source_id, f"block:{href}:{len(document.blocks)}")
            if name.startswith("h") and len(name) == 2 and name[1].isdigit():
                depth = int(name[1]) + 1
                while stack[-1][0] >= depth:
                    stack.pop()
                node_id = stable_id(source_id, f"node:{href}:{len(document.nodes)}")
                document.nodes.append(
                    DocumentNode(
                        node_id,
                        stack[-1][1],
                        "heading",
                        text,
                        depth,
                        len(document.nodes),
                        metadata={"href": href, "element_id": element.get("id")},
                    )
                )
                stack.append((depth, node_id))
                kind = "heading"
            else:
                kind = {
                    "p": "paragraph",
                    "blockquote": "quote",
                    "ul": "list",
                    "ol": "list",
                    "pre": "code",
                    "table": "table",
                }[name]
            document.blocks.append(
                DocumentBlock(
                    block_id,
                    stack[-1][1],
                    kind,
                    len(document.blocks),
                    text,
                    {
                        "href": href,
                        "spine_index": spine_index,
                        "element_id": element.get("id"),
                        "block_index": len(document.blocks),
                    },
                )
            )
            positions[id(element)] = (stack[-1][1], len(document.blocks) - 1)
        if not tags:
            text = clean_text(body.get_text(" ", strip=True))
            if text:
                document.blocks.append(
                    DocumentBlock(
                        stable_id(source_id, f"block:{href}:fallback"),
                        chapter_id,
                        "paragraph",
                        len(document.blocks),
                        text,
                        {"href": href, "spine_index": spine_index},
                    )
                )
        return positions
