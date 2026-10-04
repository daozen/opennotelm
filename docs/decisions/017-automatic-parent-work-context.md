# Read selected chapters in their parent work

A chapter Deck previously received its book title, selected section titles and complete
selected text. It could draw on model knowledge, but it did not read the uploaded book's
other chapters. Book-level interpretation therefore depended on the model recognizing
the title and remembering the work, rather than the supplied edition.

For source `node` / `nodes` Deck scopes, interpretation now automatically reads the
entire parent source and creates a compact source-grounded reading map. Long works use
the existing full-scope hierarchical synthesis, preserving original evidence IDs through
reductions. Section titles and actual TOC ancestor paths accompany material. EPUB reading
nodes may be flat even when its navigation is nested; the source TOC supplies the
part/section ancestry rather than inferred chunk boundaries. Processing groups must not
be mistaken for book parts or reported as missing uploaded chapters. The map covers central questions,
distinctive concepts, development, imagery and tensions; it does not replace the selected
chapter's close reading. Full-source Decks already read their entire source and avoid this
additional pass. Knowledge snapshots retain their original scope and content contract.

The selected chapter remains the primary material. Bibliographic identity, ancestor paths,
a bounded representative outline and the reading map are explicitly separate context DATA.
Useful connections can integrate naturally into the dossier, narrative and page content,
without author-opinion or reading-boundary headings. Source claims about other chapters use
those chapters' supplied evidence packets; model background stays uncited. Context cannot
fabricate quotations or source references. Synthesis must retain citations to primary
material, preventing an output containing only background citations from passing validation.
The citation validator verifies IDs/provenance, not the semantic truth of every explanation.
Page authors retain the full explanatory prose, but only their page-specific evidence IDs
remain exposed as citation markers in that prose and work map. Unsupported-ID feedback
lists the actual permitted IDs. Added internal citation markers in visible copy are repaired
into metadata, while literal markers already in the source may remain. This avoids a failure
observed in real samples: an author copied valid book-context IDs absent from its page evidence.

The map is cached once per source in a rebuildable `work_context_cache` table. The hash
includes normalized text, original block IDs, structural titles/parents/order, parser,
language-model endpoint/ID/context budget and synthesis prompts/versions. Chapter selection,
indexing timestamps and chapter-specific requests are excluded, so sibling and batch Decks
reuse it. Evidence IDs use a short work namespace, separate from primary chapter IDs.
A chapter scope has one parent source; these IDs are local to its frozen dossier,
while each packet retains source/block IDs and exact offsets. This reduces transcription
errors observed with long hexadecimal evidence IDs in real model output.

A source or model change invalidates it; permanent source deletion cascades its
cache. Job checkpoint prefixes isolate whole-work synthesis from chapter synthesis, so
interrupted reading can resume without overwriting either stage. API secrets are excluded.

Optional context is bounded separately from primary evidence packing. Large outlines and
many-work summaries explicitly record omissions; complete summary paragraphs are pruned
rather than truncating citation markers. The full uploaded work is read to build the map,
but its complete text is not retransmitted for every page or chapter. Interpretation remains
limited by summary compression and model ability; this is not an exhaustive scholarly index.
Different parent works are kept separate and unrelated notebook sources are not included.

Explicit user requests override this contextual default. The existing preference call gains
`chapter_only`, enabled only by an explicit prohibition on wider work context. Merely selecting
a chapter does not enable it. `source_only` excludes outside model knowledge and invented
examples; uploaded parent-work evidence remains source material unless `chapter_only` is
also requested. Chat, Knowledge and transformations keep their existing scope behavior.

Completed Decks, stopped-task resume and visual-only copies retain frozen understanding.
New chapter generation and content-rewritten copies at supported standard lengths use the
new mechanism. Manually shortened nonstandard Decks retain their existing dossier/sequence
under the existing safeguard. Existing originals are not rewritten during an application
upgrade. The first chapter for an uncached work incurs additional language-model calls;
subsequent chapters reuse the map.
