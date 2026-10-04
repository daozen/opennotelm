"""Read OOXML body content without executing Word fields or external relationships."""

from pathlib import Path
from zipfile import BadZipFile, ZipFile

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from .documents import Document, DocumentBlock, DocumentImage, DocumentNode, stable_id
from .epub import EpubParser, safe_reference
from .errors import AppError

DOCX_PARSER_VERSION = "docx-v1"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DocxParser:
    def __init__(self, archive_validator=None):
        self.archive_validator = archive_validator or EpubParser()

    def parse(self, path: Path, source_id: str, title: str) -> Document:
        try:
            with ZipFile(path) as archive:
                try:
                    self.archive_validator.validate_archive(archive)
                except AppError as error:
                    raise AppError(
                        "DOCX_UNSAFE_ARCHIVE", "The Word archive is unsafe or too large."
                    ) from error
                root = ET.fromstring(archive.read("word/document.xml"))
                styles = {}
                if "word/styles.xml" in archive.namelist():
                    styles = {
                        s.get(W + "styleId"): s
                        for s in ET.fromstring(archive.read("word/styles.xml")).findall(W + "style")
                    }
                node_id = stable_id(source_id, "root")
                doc = Document(title, [DocumentNode(node_id, None, "document", title, 0, 0)], [])
                stack = [(0, node_id)]
                resources = {}
                relationships = {}
                if "word/_rels/document.xml.rels" in archive.namelist():
                    relationships = {
                        r.get("Id"): r
                        for r in ET.fromstring(archive.read("word/_rels/document.xml.rels"))
                    }

                def style_depth(identity, seen):
                    if not identity or identity in seen or identity not in styles:
                        return None
                    seen.add(identity)
                    style = styles[identity]
                    level = depth(style.find(W + "pPr"), seen)
                    if level:
                        return level
                    # Word's standard heading IDs survive translated UI names.
                    if identity.lower().startswith("heading") and identity[-1:].isdigit():
                        return int(identity[-1]) or None
                    parent = style.find(W + "basedOn")
                    return style_depth(parent.get(W + "val"), seen) if parent is not None else None

                def depth(properties, seen=None):
                    if properties is None:
                        return None
                    outline = properties.find(W + "outlineLvl")
                    if outline is not None:
                        value = int(outline.get(W + "val", "9"))
                        return value + 1 if 0 <= value < 9 else None
                    style_ref = properties.find(W + "pStyle")
                    identity = style_ref.get(W + "val") if style_ref is not None else None
                    return style_depth(identity, set() if seen is None else seen)

                def text(element):
                    return "".join(
                        n.text or "" if n.tag == W + "t" else "\t" if n.tag == W + "tab" else "\n"
                        for n in element.iter()
                        if n.tag in (W + "t", W + "tab", W + "br", W + "cr")
                    ).strip()

                body = root.find(W + "body")
                if body is None:
                    raise ValueError("Missing body")
                for index, item in enumerate(body):
                    if item.tag == W + "p":
                        value = text(item)
                        properties = item.find(W + "pPr")
                        level = depth(properties)
                        kind = "paragraph"
                        if level and value:
                            while stack[-1][0] >= level:
                                stack.pop()
                            identity = stable_id(source_id, f"docx:heading:{index}")
                            doc.nodes.append(
                                DocumentNode(
                                    identity, stack[-1][1], "heading", value, level, len(doc.nodes)
                                )
                            )
                            stack.append((level, identity))
                            kind = "heading"
                        elif properties is not None and properties.find(W + "numPr") is not None:
                            kind = "list"
                    elif item.tag == W + "tbl":
                        value = "\n".join(
                            "\t".join(
                                "\n".join(text(p) for p in cell.findall(W + "p"))
                                for cell in row.findall(W + "tc")
                            )
                            for row in item.findall(W + "tr")
                        ).strip()
                        kind = "table"
                    else:
                        continue
                    if value:
                        doc.blocks.append(
                            DocumentBlock(
                                stable_id(source_id, f"docx:body:{index}"),
                                stack[-1][1],
                                kind,
                                len(doc.blocks),
                                value,
                                {"part": "word/document.xml", "body_index": index},
                            )
                        )
                    for image_index, blip in enumerate(
                        item.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}blip")
                    ):
                        relation = relationships.get(
                            blip.get(
                                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
                            )
                        )
                        if relation is None or relation.get("TargetMode") == "External":
                            continue
                        try:
                            href, _ = safe_reference(
                                "word/document.xml", relation.get("Target", "")
                            )
                        except AppError as error:
                            raise AppError(
                                "DOCX_UNSAFE_ARCHIVE",
                                "The Word document contains an unsafe image reference.",
                            ) from error
                        if href not in resources:
                            resources[href] = archive.read(href)
                        doc.images.append(
                            DocumentImage(
                                stable_id(source_id, f"docx:image:{index}:{image_index}"),
                                stack[-1][1],
                                len(doc.blocks) - 0.5,
                                {
                                    "part": "word/document.xml",
                                    "body_index": index,
                                    "image_index": image_index,
                                },
                                data=resources[href],
                            )
                        )
                if not doc.blocks and not doc.images:
                    raise AppError("SOURCE_NO_TEXT", "The Word document contains no readable text.")
                return doc
        except AppError:
            raise
        except (
            BadZipFile,
            KeyError,
            ValueError,
            OSError,
            DefusedXmlException,
            ET.ParseError,
        ) as error:
            raise AppError("DOCX_PARSE_FAILED", "The Word document could not be parsed.") from error
