# Chapter continuation and page navigation

Status: accepted, 2026-10-02

A reader must continue from the current chapter without reopening a selector.
A PDF page and a drawing-derived heading are reading locations, not a table of
contents. The existing parser already retains actual PDF outline chapters, EPUB
spine chapters and authored Markdown headings; no fact-layer migration is needed.

The reader uses chapter nodes when available. Inline EPUB headings do not create
additional chapter stops or duplicate chapter titles. A document without chapter
nodes uses authored headings for text/Markdown navigation. PDF drawing headings
never populate its directory. A PDF without an outline has no directory selector.

Previous/next chapter controls appear above and below the text. Without chapters,
PDF controls become previous/next page. Boundary buttons are disabled. Moving from
the footer scrolls and focuses the new text, allowing keyboard reading to continue.
PDF page navigation stays separate: a bounded page input with Go, and independent
previous/next page controls when chapter navigation exists. A page selected by
citation or page input highlights its containing chapter in the directory.

Chapter/page changes retain the stable node ID in the existing source URL. Refresh,
new tabs and browser history restore that location. Exact citation links still
resolve the original block anchor, including successive citations on the same page.
Location resolution and body loading have independent state so resolving another
anchor does not leave an already loaded page in a spinner.

Question and generation actions identify their actual scope: this chapter, this
page or the entire source. The document root uses source scope. Original nodes,
blocks, citation offsets and saved content remain untouched; old imports benefit
from this presentation change immediately. Navigation strings support both UI
languages without translating document content.

Limitations: PDF navigation uses the embedded outline, without inferring a table
of contents from typography. EPUB chapter continuation follows the imported spine;
inline subheadings remain visible in the body. Reconstructing a more complex EPUB
fragment-based outline or inferring chapters for an unstructured PDF is separate
work, not a prerequisite for reliable continuation.
