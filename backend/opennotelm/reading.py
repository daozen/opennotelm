"""A disposable reading projection; immutable source blocks remain citation facts."""

import math
import re
import unicodedata
from collections import defaultdict
from statistics import median

from pypdf import PdfReader

from .errors import AppError

READING_VERSION = "pdf-reflow-v1"


def display_text(text):
    # Normalize compatibility radicals/ligatures, preserving original punctuation.
    text = "".join(
        unicodedata.normalize("NFKC", c)
        if "\u2f00" <= c <= "\u2fdf" or "\uf900" <= c <= "\ufaff" or "\ufb00" <= c <= "\ufb06"
        else c
        for c in text
    )
    return "".join(c for c in text if not unicodedata.category(c).startswith("C") or c in "\n\t")


def characters(text):
    return re.sub(r"\s", "", display_text(text))


def raw_reading(blocks):
    return [
        {
            "type": b["type"],
            "page_start": b["page_start"],
            "parts": [{"block_id": b["id"], "text": b["text"]}],
            **({"image": b["metadata"]} if b.get("metadata", {}).get("image_id") else {}),
        }
        for b in blocks
    ]


def page_reading(page, blocks):
    positions, fragments = {}, []

    def visitor(text, cm, tm, font, size):
        if not text.strip():
            return
        x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
        y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        scale = math.hypot(tm[2] * cm[0] + tm[3] * cm[2], tm[2] * cm[1] + tm[3] * cm[3])
        position = (x, y, abs(size * scale))
        for paragraph in re.split(r"\n\s*\n", text):
            if paragraph.strip():
                fragments.append((paragraph.strip(), position))

    full_text = page.extract_text(visitor_text=visitor) or ""
    if len(fragments) == len(blocks) and all(
        f[0] == b["text"] for f, b in zip(fragments, blocks, strict=True)
    ):
        positions = {b["id"]: f[1] for f, b in zip(fragments, blocks, strict=True)}
    # Alignment must be exact after display-only whitespace/Unicode normalization.
    # Never associate a guessed source identity with different extracted text.
    labels = [b["id"] for b in blocks for _ in characters(b["text"])]
    original = "".join(characters(b["text"]) for b in blocks)
    if characters(full_text) != original:
        return raw_reading(blocks)
    lines, offset, blank = [], 0, False
    for raw_line in full_text.splitlines():
        text = re.sub(r"[\t ]+", " ", display_text(raw_line)).strip()
        if not text:
            blank = True
            continue
        parts = []
        for char in text:
            identity = labels[offset] if not char.isspace() else labels[max(0, offset - 1)]
            if not char.isspace():
                offset += 1
            if parts and parts[-1]["block_id"] == identity:
                parts[-1]["text"] += char
            else:
                parts.append({"block_id": identity, "text": char})
        points = [positions[p["block_id"]] for p in parts if p["block_id"] in positions]
        points = [p for p in points if all(math.isfinite(v) for v in p) and p[2] > 0]
        lines.append(
            {
                "text": text,
                "parts": parts,
                "blank": blank,
                "end": raw_line.rstrip().endswith("\x01"),
                "point": points[0] if points else None,
                "size": median(p[2] for p in points) if points else 12,
                "trailing_space": raw_line.endswith(" "),
            }
        )
        blank = False
    if not lines:
        return raw_reading(blocks)
    # Some exporters end every text operation with a newline even while drawing
    # adjacent glyphs on the same physical baseline. Reconstruct those lines first.
    joined = []
    for line in lines:
        previous_line = joined[-1] if joined else None
        tail = previous_line.get("tail", previous_line["point"]) if previous_line else None
        point = line["point"]
        same_line = bool(
            previous_line
            and tail
            and point
            and not line["blank"]
            and abs(tail[1] - point[1]) <= min(tail[2], point[2]) * 0.25
            and 0
            < point[0] - tail[0]
            <= tail[2] * (max(1, len(previous_line["parts"][-1]["text"])) * 1.2 + 1.5)
        )
        if same_line:
            if previous_line["trailing_space"]:
                previous_line["parts"].append(
                    {"block_id": line["parts"][0]["block_id"], "text": " "}
                )
                previous_line["text"] += " "
            previous_line["parts"].extend(line["parts"])
            previous_line["text"] += line["text"]
            previous_line["tail"] = point
            previous_line["end"] = line["end"]
            previous_line["trailing_space"] = line["trailing_space"]
        else:
            joined.append(line)
    lines = joined
    typical = median(line["size"] for line in lines for _ in range(len(line["text"])))
    longest = max(len(line["text"]) for line in lines)
    output, previous = [], None
    for line in lines:
        heading = len(line["text"]) < 160 and (
            line["size"] > typical * 1.2
            or bool(re.match(r"^(?:\d+(?:\.\d+)*\s|第.{1,12}[章节])", line["text"]))
        )
        kind = "heading" if heading else "paragraph"
        new = not previous or heading or output[-1]["type"] == "heading" or line["blank"]
        if previous:
            new |= previous["end"] or abs(line["size"] - previous["size"]) > typical * 0.15
            new |= bool(re.match(r"^(?:[•●▪]|[-*]\s|\d+[.)、]\s*)", line["text"]))
            if previous["point"] and line["point"]:
                x, y, _ = line["point"]
                px, py, _ = previous["point"]
                new |= abs(y - py) > max(line["size"], previous["size"]) * 2.3
                new |= x - px > typical * 0.8 or x < px - typical * 4
            new |= len(previous["text"]) < longest * 0.45 and previous["text"].endswith(
                (".", "。", "!", "！", "?", "？", ":", "：")
            )
        if new:
            output.append(
                {"type": kind, "page_start": blocks[0]["page_start"], "parts": list(line["parts"])}
            )
        else:
            # CJK soft line wraps do not add spaces. Latin words still need one.
            left, right = previous["text"][-1], line["text"][0]

            def cjk(c):
                return "\u2e80" <= c <= "\u9fff" or c in "，。；：！？、（）“”"

            if not (cjk(left) and cjk(right)):
                output[-1]["parts"].append({"block_id": line["parts"][0]["block_id"], "text": " "})
            output[-1]["parts"].extend(line["parts"])
        previous = line
    # Empty/control-only fact blocks remain addressable without displaying a glyph.
    represented = {p["block_id"] for item in output for p in item["parts"]}
    for block in blocks:
        if block["id"] not in represented:
            output[-1]["parts"].append({"block_id": block["id"], "text": ""})
    return output


def join_short_continuations(items):
    """Keep a sentence's short wrapped ending with its paragraph.

    A hanging indent can resemble a paragraph break. Only absorb a short,
    sentence-ending tail on the same page; headings and new list items stay apart.
    """
    result = []
    ending = re.compile(r"[。！？.!?；;][）)\]”’\"']*$")
    item_start = re.compile(
        r"^(?:[•●▪]|[-*]\s|[a-zA-Z]\.\s|\d+[.)、]\s*|[一二三四五六七八九十]+[、.])"
    )
    for item in items:
        text = "".join(part["text"] for part in item["parts"]).strip()
        previous = result[-1] if result else None
        previous_text = (
            "".join(part["text"] for part in previous["parts"]).rstrip() if previous else ""
        )
        if (
            previous
            and item["type"] == previous["type"] == "paragraph"
            and item["page_start"] == previous["page_start"]
            and 0 < len(text) <= 16
            and ending.search(text)
            and previous_text
            and not re.search(r"[。！？.!?；;：:]$", previous_text)
            and not item_start.match(text)
        ):
            left, right = previous_text[-1], text[0]
            # Preserve Latin word boundaries, without breaking CJK words.
            separator = (
                "" if "\u2e80" <= left <= "\u9fff" and "\u2e80" <= right <= "\u9fff" else " "
            )
            previous["parts"] += (
                [{"block_id": item["parts"][0]["block_id"], "text": separator}] if separator else []
            ) + item["parts"]
        else:
            result.append({**item, "parts": list(item["parts"])})
    return result


def pdf_reading(path, all_blocks, selected_blocks):
    pages = defaultdict(list)
    selected = {b["id"] for b in selected_blocks}
    for block in all_blocks:
        pages[block["page_start"]].append(block)
    required = sorted({b["page_start"] for b in selected_blocks})
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise AppError("PDF_ENCRYPTED", "The original PDF is password protected.")
        result = []
        for number in required:
            normal = [b for b in pages[number] if not b.get("metadata", {}).get("image_id")]
            visuals = [b for b in pages[number] if b.get("metadata", {}).get("image_id")]
            items = page_reading(reader.pages[number - 1], normal) if normal else []
            for item in [*items, *raw_reading(visuals)]:
                parts = [p for p in item["parts"] if p["block_id"] in selected]
                if parts:
                    result.append({**item, "parts": parts})
        return join_short_continuations(result)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("SOURCE_READING_FAILED", "The original PDF could not be opened.") from exc
