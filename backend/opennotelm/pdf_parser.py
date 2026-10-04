import logging
import re
from pathlib import Path
from statistics import median

from pypdf import PdfReader

from .documents import Document, DocumentBlock, DocumentImage, DocumentNode, stable_id
from .errors import AppError

PDF_PARSER_VERSION = "pdf-v1"
# Third-party parser warnings may include fragments of hostile document content.
logging.getLogger("pypdf").setLevel(logging.CRITICAL)


class PdfParser:
    def __init__(
        self,
        max_pages=5000,
        min_text_characters=40,
        min_readable_fraction=0.2,
        include_images=False,
    ):
        self.max_pages = max_pages
        self.min_text_characters = min_text_characters
        self.min_readable_fraction = min_readable_fraction
        self.include_images = include_images

    def parse(self, path: Path, source_id: str, title: str) -> Document:
        try:
            return self._parse(path, source_id, title)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                "PDF_PARSE_FAILED", "The PDF could not be parsed. Check that the file is valid."
            ) from exc

    def _parse(self, path, source_id, title):
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise AppError(
                "PDF_ENCRYPTED",
                "Password-protected PDFs are not supported. Upload an unlocked copy.",
            )
        if len(reader.pages) > self.max_pages:
            raise AppError("PDF_PAGE_LIMIT", "The PDF exceeds the configured page limit.")
        metadata_title = reader.metadata.title if reader.metadata else None
        title = str(metadata_title).strip() if metadata_title else title
        root_id = stable_id(source_id, "root")
        document = Document(
            title,
            [DocumentNode(root_id, None, "document", title, 0, 0)],
            [],
            {"page_count": len(reader.pages), "warnings": []},
        )
        outlines = []

        def add_outline(items, parent_id, depth):
            last = parent_id
            for item in items:
                if isinstance(item, list):
                    add_outline(item, last, depth + 1)
                    continue
                page_number = reader.get_destination_page_number(item)
                if page_number is None or page_number < 0:
                    continue
                node_id = stable_id(source_id, f"outline:{len(document.nodes)}")
                node = DocumentNode(
                    node_id,
                    parent_id,
                    "chapter",
                    str(item.title),
                    depth,
                    len(document.nodes),
                    start_page=page_number + 1,
                )
                document.nodes.append(node)
                outlines.append(node)
                last = node_id

        add_outline(reader.outline, root_id, 1)
        for index, node in enumerate(outlines):
            next_node = next((n for n in outlines[index + 1 :] if n.depth <= node.depth), None)
            node.end_page = (
                max(node.start_page, next_node.start_page - 1) if next_node else len(reader.pages)
            )
        readable_pages, blank_pages = 0, []
        total_characters = 0
        for page_index, page in enumerate(reader.pages):
            page_number = page_index + 1
            fragments = []

            def visitor(text, cm, tm, font, size, fragments=fragments):
                if text.strip():
                    fragments.append((text, float(size)))

            full_text = page.extract_text(visitor_text=visitor) or ""
            characters = len(re.sub(r"\s", "", full_text))
            total_characters += characters
            if characters >= self.min_text_characters:
                readable_pages += 1
            if not characters:
                blank_pages.append(page_number)
            matching = [n for n in outlines if n.start_page <= page_number <= n.end_page]
            parent = (
                max(matching, key=lambda n: (n.start_page, n.depth, n.ordinal))
                if matching
                else document.nodes[0]
            )
            page_id = stable_id(source_id, f"page:{page_number}")
            document.nodes.append(
                DocumentNode(
                    page_id,
                    parent.id,
                    "page",
                    f"Page {page_number}",
                    parent.depth + 1,
                    len(document.nodes),
                    start_page=page_number,
                    end_page=page_number,
                )
            )
            current_id = page_id
            typical_size = median([size for _, size in fragments]) if fragments else 12
            for text, size in fragments:
                for paragraph in re.split(r"\n\s*\n", text):
                    paragraph = paragraph.strip()
                    if not paragraph:
                        continue
                    heading = len(paragraph) < 160 and (
                        size > typical_size * 1.2
                        or bool(re.match(r"^(?:\d+(?:\.\d+)*\s|第.{1,12}[章节])", paragraph))
                    )
                    if heading and paragraph not in {n.title for n in matching}:
                        current_id = stable_id(
                            source_id, f"heading:{page_number}:{len(document.blocks)}"
                        )
                        document.nodes.append(
                            DocumentNode(
                                current_id,
                                page_id,
                                "heading",
                                paragraph,
                                parent.depth + 2,
                                len(document.nodes),
                                start_page=page_number,
                                end_page=page_number,
                            )
                        )
                    document.blocks.append(
                        DocumentBlock(
                            stable_id(source_id, f"block:{len(document.blocks)}"),
                            current_id,
                            "heading" if heading else "paragraph",
                            len(document.blocks),
                            paragraph,
                            {"page": page_number, "block_index": len(document.blocks)},
                            page_number,
                            page_number,
                        )
                    )
            if self.include_images:
                images = list(page.images)
                contents = page.get_contents()
                painted = contents and any(
                    operator in (b"Do", b"S", b"s", b"f", b"f*", b"B", b"b", b"Tj", b"TJ")
                    for _, operator in contents.operations
                )
                if characters < self.min_text_characters and (images or painted):
                    document.images.append(
                        DocumentImage(
                            stable_id(source_id, f"pdf:scan:{page_number}"),
                            page_id,
                            len(document.blocks) - 0.5,
                            {"page": page_number},
                            page=page_number,
                            kind="scan",
                        )
                    )
                elif images:
                    for image_index, image in enumerate(images):
                        if min(image.image.size) < 80:
                            continue
                        document.images.append(
                            DocumentImage(
                                stable_id(source_id, f"pdf:image:{page_number}:{image_index}"),
                                page_id,
                                len(document.blocks) - 0.5,
                                {"page": page_number, "image_index": image_index},
                                data=image.data,
                                page=page_number,
                            )
                        )
                elif (
                    contents
                    and sum(
                        operator in (b"S", b"s", b"f", b"f*", b"B", b"b")
                        for _, operator in contents.operations
                    )
                    >= 3
                ):
                    # Charts built from PDF paths have no raster image object.
                    document.images.append(
                        DocumentImage(
                            stable_id(source_id, f"pdf:figure-page:{page_number}"),
                            page_id,
                            len(document.blocks) - 0.5,
                            {"page": page_number, "vector_figure": True},
                            page=page_number,
                        )
                    )
        if not document.images and (
            total_characters < self.min_text_characters
            or not reader.pages
            or readable_pages / len(reader.pages) < self.min_readable_fraction
        ):
            raise AppError(
                "PDF_NO_READABLE_CONTENT" if self.include_images else "PDF_NO_TEXT_LAYER",
                "The PDF contains no readable text or page images."
                if self.include_images
                else (
                    "This PDF appears to be scanned or image-based. "
                    "OCR is not supported in this version."
                ),
            )
        if blank_pages and not self.include_images:
            document.metadata["warnings"].append(
                f"No extractable text on pages: {', '.join(map(str, blank_pages))}. "
                "OCR is not supported.",
            )
        return document
