"""Restore source Unicode when a system font maps a shared glyph to a radical/alias.

Chromium may emit one glyph for multiple Unicode characters. Preserve its positioning
and font metrics, cloning a font's ToUnicode mapping only for affected text runs.
This also handles a page containing both the character and its look-alike alias.
"""

import re
import unicodedata

from pypdf.generic import (
    ArrayObject,
    ByteStringObject,
    ContentStream,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)

from .errors import AppError


def no_space(text):
    return "".join(char for char in text if not char.isspace())


def source_characters(actual, expected):
    """Align shared-glyph aliases and expanded typographic ligatures to source text."""
    result, cursor = [], 0
    for character in actual:
        expanded = unicodedata.normalize("NFKC", character)
        if expected.startswith(character, cursor):
            replacement = character
        elif len(expanded) > 1 and expected.startswith(expanded, cursor):
            replacement = expanded
        else:
            replacement = expected[cursor : cursor + 1]
        result.append(replacement)
        cursor += len(replacement)
    if cursor != len(expected) or any(not item for item in result):
        raise AppError(
            "PDF_TEXT_INCOMPLETE",
            "The font did not preserve all source characters. Retry the page visual.",
        )
    return result


def font_mapping(font):
    if "/ToUnicode" not in font:
        # Base-14 fonts in generated helper PDFs use single-byte WinAnsi text.
        return 1, {bytes([i]): bytes([i]).decode("cp1252", errors="replace") for i in range(256)}
    cmap = font["/ToUnicode"].get_data().decode("ascii")
    mapping = {}
    for section in re.findall(r"beginbfchar(.*?)endbfchar", cmap, re.S):
        for code, value in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", section):
            mapping[bytes.fromhex(code)] = bytes.fromhex(value).decode("utf-16-be")
    for section in re.findall(r"beginbfrange(.*?)endbfrange", cmap, re.S):
        pattern = r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<([0-9A-Fa-f]+)>|\[([^\]]+)\])"
        for first, last, _, start, array in re.findall(pattern, section):
            width = len(first) // 2
            values = re.findall(r"<([0-9A-Fa-f]+)>", array) if array else []
            for offset, code in enumerate(range(int(first, 16), int(last, 16) + 1)):
                raw = (
                    bytes.fromhex(values[offset])
                    if array
                    else (int(start, 16) + offset).to_bytes(len(start) // 2, "big")
                )
                mapping[code.to_bytes(width, "big")] = raw.decode("utf-16-be")
    widths = {len(code) for code in mapping}
    if len(widths) != 1:
        raise AppError(
            "PDF_TEXT_ENCODING_UNSUPPORTED",
            "A font has an unsupported character map. Retry the page visual.",
        )
    return widths.pop(), mapping


def encoded_mapping(mapping, width):
    lines = [
        "/CIDInit /ProcSet findresource begin",
        "12 dict begin",
        "begincmap",
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        "/CMapName /OpenNoteLM-Source-Unicode def",
        "/CMapType 2 def",
        "1 begincodespacerange",
        f"<{'00' * width}> <{'FF' * width}>",
        "endcodespacerange",
    ]
    items = list(mapping.items())
    for start in range(0, len(items), 100):
        batch = items[start : start + 100]
        lines.append(f"{len(batch)} beginbfchar")
        lines.extend(f"<{code.hex()}> <{value.encode('utf-16-be').hex()}>" for code, value in batch)
        lines.append("endbfchar")
    lines.extend(["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"])
    stream = DecodedStreamObject()
    stream.set_data("\n".join(lines).encode("ascii"))
    return stream


def restore_source_unicode(page, text_layer, writer):
    expected = no_space("".join(item["text"] for item in text_layer))
    actual = no_space(page.extract_text())
    if actual == expected:
        return
    replacements = source_characters(actual, expected)
    cursor = 0
    cloned_fonts = {}

    def process(stream, resources, depth=0):
        nonlocal cursor
        if depth > 16:
            raise AppError("PDF_TEXT_ENCODING_UNSUPPORTED", "Unsupported nested text.")
        resources = resources.get_object()
        fonts = resources["/Font"] if "/Font" in resources else {}
        current_font, size = None, None
        output = []
        stack = []
        maps = {}

        def text_operations(value):
            nonlocal cursor
            raw = bytes(value) if isinstance(value, bytes) else value.original_bytes
            if not raw:
                return [([value], b"Tj")]
            font = fonts[current_font].get_object()
            if current_font not in maps:
                maps[current_font] = font_mapping(font)
            width, mapping = maps[current_font]
            rewritten = []
            font_in_use = current_font
            for index in range(0, len(raw), width):
                code = raw[index : index + width]
                original = mapping.get(code)
                if original is None:
                    raise AppError(
                        "PDF_TEXT_INCOMPLETE", "A rendered glyph has no Unicode mapping."
                    )
                length = len(no_space(original))
                desired = replacements[cursor : cursor + length]
                if len(desired) != length:
                    raise AppError("PDF_TEXT_INCOMPLETE", "The text and glyph counts differ.")
                cursor += length
                replacement = iter(desired)
                corrected = "".join(
                    char if char.isspace() else next(replacement) for char in original
                )
                chosen = current_font
                if corrected != original:
                    key = (id(resources), str(current_font), code, corrected)
                    chosen = cloned_fonts.get(key)
                    if chosen is None:
                        chosen = NameObject(f"/OpenNoteLMText{len(cloned_fonts)}")
                        clone = DictionaryObject(dict(font))
                        clone[NameObject("/ToUnicode")] = writer._add_object(
                            encoded_mapping({**mapping, code: corrected}, width)
                        )
                        fonts[chosen] = writer._add_object(clone)
                        cloned_fonts[key] = chosen
                if chosen != font_in_use:
                    rewritten.append(([chosen, size], b"Tf"))
                    font_in_use = chosen
                rewritten.append(([ByteStringObject(code)], b"Tj"))
            if font_in_use != current_font:
                rewritten.append(([current_font, size], b"Tf"))
            return rewritten

        for operands, operator in stream.operations:
            if operator == b"q":
                stack.append((current_font, size))
            elif operator == b"Q" and stack:
                current_font, size = stack.pop()
            elif operator == b"Tf":
                current_font, size = operands
            if operator == b"Tj":
                output.extend(text_operations(operands[0]))
            elif operator == b"TJ":
                for value in operands[0]:
                    if isinstance(value, (str, bytes)):
                        output.extend(text_operations(value))
                    else:
                        output.append(([ArrayObject([value])], b"TJ"))
            elif operator == b"Do" and "/XObject" in resources:
                form = resources["/XObject"][operands[0]]
                if form.get("/Subtype") == "/Form":
                    nested = process(
                        ContentStream(form, writer), form.get("/Resources", resources), depth + 1
                    )
                    replacement = DecodedStreamObject()
                    replacement.update(
                        {
                            k: v
                            for k, v in form.items()
                            if k not in {"/Filter", "/DecodeParms", "/Length"}
                        }
                    )
                    replacement.set_data(nested.get_data())
                    resources["/XObject"][operands[0]] = replacement
                output.append((operands, operator))
            elif operator in {b"'", b'"'}:
                raise AppError(
                    "PDF_TEXT_ENCODING_UNSUPPORTED", "Unsupported generated text operation."
                )
            else:
                output.append((operands, operator))
        stream.operations = output
        return stream

    page.replace_contents(process(page.get_contents(), page["/Resources"]))
    if cursor != len(actual) or no_space(page.extract_text()) != expected:
        raise AppError("PDF_TEXT_INCOMPLETE", "The original text could not be preserved exactly.")
