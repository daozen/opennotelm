# Readable PDF text without rewriting citation facts

Existing PDF exports can emit one text operation per glyph or word. Treating those
callbacks as paragraphs produces single-character reading blocks and false heading
nodes. The reader must display coherent lines and paragraphs while retaining all
existing citation identities, offsets, node scopes and saved derived artifacts.

The `/api/sources/{id}/reading` endpoint returns a disposable reading projection.
PDF text is re-extracted locally from the original file, aligned against immutable
blocks after display-only whitespace/compatibility-glyph normalization, and split
into inline parts carrying original block IDs. Exact alignment is required; different
extracted text falls back to the saved blocks instead of guessing citation anchors.
No source block, node, citation, retrieval index or existing artifact is rewritten.

The text and current transformation matrices yield physical baseline positions and
font sizes. Adjacent glyph operations on a shared baseline become one line. Font
changes, vertical gaps, indentation, explicit paragraph gaps and list starts bound
paragraphs; soft wraps retain Latin word spacing and avoid inserting CJK spaces.
Compatibility radicals/ligatures are normalized only for display, preserving source
punctuation. Control characters remain immutable facts with non-painted anchors.
All page boundaries and original block IDs remain represented.

PDF navigation retains native outlines and pages, excluding fragment-derived heading
nodes. A citation to any old fragment opens its containing original page and highlights
the inline anchor. The default reader uses 18px body text, adjustable to 16/20px, with
an optional expanded view that uses normal document scrolling. EPUB/Markdown/TXT
retain their existing semantic block boundaries, code and list/table formatting.

This is heuristic text reflow, not OCR or exact page-layout reconstruction. Complex
columns/tables/rotated text can still need improvement. Parser upgrades must not
replace immutable facts referenced by saved citations as a side effect of reading.
