import re
from pathlib import Path

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
from markdown_it.tree import SyntaxTreeNode

from .documents import Document, DocumentBlock, DocumentNode, stable_id
from .errors import AppError

TEXT_PARSER_VERSION = "text-v1"
MARKDOWN_PARSER_VERSION = "markdown-v1"


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return raw.decode("utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig")
    except UnicodeError as exc:
        raise AppError(
            "TEXT_ENCODING_UNSUPPORTED", "Save the text as UTF-8 or UTF-16 and upload again."
        ) from exc


def html_text(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    for tag in soup.find_all(["script", "style", "iframe", "object", "embed", "form"]):
        tag.decompose()
    for tag in soup.find_all("br"):
        tag.replace_with("\n")
    return soup.get_text().strip()


def node_text(node: SyntaxTreeNode) -> str:
    if node.type == "inline":
        # Sanitize the complete inline fragment: script bodies can span tokens.
        return html_text(MarkdownIt("commonmark").renderInline(node.content))
    if node.type in ("html_inline", "html_block"):
        return html_text(node.content)
    if node.type in ("text", "code_inline", "code_block", "fence"):
        return node.content
    if node.type in ("softbreak", "hardbreak"):
        return "\n"
    parts = [node_text(child) for child in node.children]
    if node.type in ("bullet_list", "ordered_list"):
        return "\n".join(f"• {part.strip()}" for part in parts if part.strip())
    separator = (
        "\t"
        if node.type == "tr"
        else "\n"
        if node.type in ("table", "thead", "tbody", "blockquote")
        else ""
    )
    return separator.join(parts)


class TextParser:
    def parse(self, path: Path, source_id: str, title: str) -> Document:
        text = read_text(path).replace("\r\n", "\n").replace("\r", "\n")
        root_id = stable_id(source_id, "root")
        document = Document(title, [DocumentNode(root_id, None, "document", title, 0, 0)], [])
        for match in re.finditer(r"\S[^\n]*(?:\n(?!\s*\n)[^\n]*)*", text):
            content = match.group().strip()
            start = text.count("\n", 0, match.start()) + 1
            end = text.count("\n", 0, match.end()) + 1
            document.blocks.append(
                DocumentBlock(
                    stable_id(source_id, f"line:{start}"),
                    root_id,
                    "paragraph",
                    len(document.blocks),
                    content,
                    {"line_start": start, "line_end": end},
                )
            )
        if not document.blocks:
            raise AppError("SOURCE_NO_TEXT", "The file contains no readable text.")
        return document


class MarkdownParser:
    def parse(self, path: Path, source_id: str, title: str) -> Document:
        text = read_text(path)
        tree = SyntaxTreeNode(MarkdownIt("commonmark").enable("table").parse(text))
        root_id = stable_id(source_id, "root")
        document = Document(title, [DocumentNode(root_id, None, "document", title, 0, 0)], [])
        stack = [(0, root_id)]
        found_title = False
        for item in tree.children:
            content = node_text(item).strip("\n")
            if not content.strip():
                continue
            line_start, line_end = item.map or (0, 0)
            kind = {
                "heading": "heading",
                "fence": "code",
                "code_block": "code",
                "blockquote": "quote",
                "bullet_list": "list",
                "ordered_list": "list",
                "table": "table",
            }.get(item.type, "paragraph")
            if kind == "heading":
                depth = int(item.tag[1])
                while stack[-1][0] >= depth:
                    stack.pop()
                node_id = stable_id(source_id, f"heading:{line_start}")
                document.nodes.append(
                    DocumentNode(
                        node_id,
                        stack[-1][1],
                        "heading",
                        content,
                        depth,
                        len(document.nodes),
                        metadata={"line_start": line_start + 1},
                    )
                )
                stack.append((depth, node_id))
                if depth == 1 and not found_title:
                    document.title = content
                    document.nodes[0].title = content
                    found_title = True
            document.blocks.append(
                DocumentBlock(
                    stable_id(source_id, f"line:{line_start}"),
                    stack[-1][1],
                    kind,
                    len(document.blocks),
                    content,
                    {"line_start": line_start + 1, "line_end": line_end},
                )
            )
        if not document.blocks:
            raise AppError("SOURCE_NO_TEXT", "The file contains no readable text.")
        return document
