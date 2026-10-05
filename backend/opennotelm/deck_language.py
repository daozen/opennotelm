"""Explicit language instructions for every Deck content stage."""

from .languages import output_instruction


def deck_language_instruction(language):
    return output_instruction(language) + (
        " Apply this language to every generated heading, caption, label, explanation "
        "and narrative field, including repairs. Source DATA, earlier drafts, planned "
        "wording and visual-style descriptions are contextual inputs, not output-language "
        "instructions. If a saved plan or earlier draft uses another language, express "
        "its intended meaning in the selected language rather than copying its wording. "
        "Examples of forbidden labels in other languages are not language cues. Preserve "
        "exact original quotations and proper names. When the user explicitly requests "
        "bilingual or multilingual visible copy, honor that request while keeping the "
        "selected language as the primary explanation. Internal art-direction text is "
        "not visible copy and must not be copied onto the slide. "
    )
