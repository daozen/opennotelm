# Paragraph evidence and readable citation context

PDF drawing callbacks are immutable source facts, sometimes one glyph each.
Reflowing the Reader alone left retrieval emitting one evidence ID per glyph, and
saved citation popups slicing that one-glyph span. Citation display and model
context must use readable paragraphs while keeping precise original provenance.

`SourceService.passages` uses the existing aligned PDF reading projection for only
the hit pages. It maps every visible character back to its raw block/offset, with
explicit handling of compatibility characters, ligatures and display whitespace.
Unknown/mismatched identities cannot produce guessed coordinates. Paragraphs larger
than 1000 estimated tokens split at sentence boundaries when available. Other
formats use their saved semantic paragraph blocks with the same bounded splitting.

Retrieval keeps its ranked index hits and expands them to paragraph evidence,
deduplicating hits that belong to the same paragraph. Source/page/node scope still
limits the expansion, including frozen queued questions. Evidence IDs now represent
paragraphs containing multiple exact raw spans. Existing indexes remain valid;
source blocks and nodes are not reparsed or migrated. Traces identify the evidence
presentation version. Normal context budgeting still applies.

`GET /api/citations/{id}` retains the original `spans` and exact sliced `quote`
contract. The additional `passages` field supplies paragraph text, page/source
location, underlying coordinates and the original cited anchor for opening the
Reader. The client displays passages, merging multiple glyph references into one
paragraph preview. This also fixes previously saved citations without rewriting
answers, citation rows, source files, vectors or derived artifacts. Source deletion
preserves citation identity and displays an unavailable-source state. Failed reflow
falls back to the precise saved quote rather than inventing context.

The shared PDF projection also rejoins a short wrapped sentence ending on the same
page. For example, an actual imported source split “有效” from “期；”; it now reads
“有效期；”. The merge excludes headings, new list items, already completed sentences
and page boundaries. These heuristics improve readable text, not OCR or exact page
layout reconstruction; complex layouts still require explicit evidence checks.
