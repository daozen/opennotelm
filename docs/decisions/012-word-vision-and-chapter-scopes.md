# Word, source images and batch chapter scopes

> 2026-10-03 文档整理：后续扩展：本文的串行图片识别由 [019](019-controlled-image-recognition.md) 改为可配置固定 worker 池；合并章节由 [013](013-separate-decks-and-chapter-tree.md) 扩展为合并/分别与树状选择。

The user's 2026-10-02 request extends the original V0.1 contract: DOCX, source-image
recognition, scanned PDFs and chapter selection are now in scope. Legacy `.doc`
conversion is explicitly deferred. Multiple chapters initially combined into one
Deck. The user's 2026-10-03 extension adds an optional separate-generation mode and
a directory tree; see [decision 013](013-separate-decks-and-chapter-tree.md).

## Import and recognition

DOCX is read as bounded, validated OOXML with defused XML parsing. Main-body
paragraphs, heading styles, lists, tables and embedded raster images are extracted.
No Word fields or external image relationships are executed or downloaded.
Headers, footnotes, tracked-change semantics and embedded Office charts are not
full Word layout reconstruction. PDFs retain native text and bookmarks; pages with
little extractable text are rendered locally using PDFium. Native raster figures
and pages containing several painted vector paths also enter recognition.

Source-image input uses the saved **language model**, through multimodal Chat
Completions (`image_url` with a local PNG data URL). The image-generation model is
not used for OCR. Optional “Test image recognition” reads an image whose answer is
absent from the text prompt; text/JSON capability alone does not imply vision.
The compatibility gateway implements the documented [image-input protocol](https://developers.openai.com/api/docs/guides/images-vision).

Recognition transcribes visible paragraphs/tables in their original language and
describes visible figure relationships. The image is untrusted data. It is not
allowed to issue instructions or request external fetches. Responses have bounded
schemas and one formatting repair. These checks do not establish OCR accuracy.
The reader and citations show the original image and label AI-derived content;
uncertain or failed recognition remains visible. Complex layouts, poor scans and
handwriting depend on the configured model and require checking the original.

PNG previews and successful transcripts are stored beside the immutable upload.
Checksums, recognition version and stable image IDs make retries resumable; repeated
identical images reuse recognition. Corrupt checkpoints can be retried. A partially
recognized document still exposes its native text. A scan with no usable transcript
fails with a retry action while preserving readable original page images.
OCR currently processes source images sequentially. Deck image concurrency settings
still apply to page generation, not document recognition.

Existing imports are not silently sent to a model on upgrade. “Recognize document
images” explicitly upgrades an existing import. Text block IDs and exact offsets
remain unchanged; published successful transcripts survive later model changes.
Changing the normalized content atomically invalidates its old chunk/index links.
An unchanged retry retains both facts and the index.

PDFium calls are guarded by a process-wide lock because the library is
[not thread-safe](https://pypdfium2.readthedocs.io/en/stable/readme.html).
Image previews are bounded to 2400 pixels and decoded raster input to 40 MP.
Original files remain available locally; normalized previews do not replace them.

## Directory scopes

Deck creation can select, select all or clear PDF bookmark chapters, EPUB directory
entries, or DOCX headings. Empty selections cannot start a generation. PDFs without
bookmarks do not invent a chapter per page. PDF bookmarks have page-level ranges;
multiple bookmarks on the same page cannot isolate exact lines within that page.

`Scope(kind="nodes", source_id, node_ids)` resolves a union in source order. Parent
and descendant overlap is deduplicated when freezing the scope. Saved Decks and
retries retain that scope. Unknown or foreign source/node IDs are rejected before
provider work. EPUB directory anchors on non-heading elements receive disposable
section projections, bounded by the following directory anchor. Paragraphs are
kept whole. Older imported block identities are never rewritten to add directory
navigation. Shared retrieval chunks are filtered at block level to keep adjacent
unselected chapters out of provider-facing evidence.

## Upgrade and deployment

Migration 014 expands `sources.type` with `docx`. It uses SQLite's documented
[table rebuild](https://www.sqlite.org/lang_altertable.html) with foreign keys disabled
outside the transaction, explicit integrity verification, rollback on failure and
restoration of the deletion trigger. Upgrade tests preserve source references,
normalized blocks and deletion behavior. Rehearse on a backup of existing data
before deployment; older binaries cannot open the newer schema.

Docker installs PDFium from the pinned lockfile. Browser/runtime dependencies are
cached separately from application code. Test fixtures and temporary acceptance
data use isolated applications on ports 4300/4302 or 4303; the user's 3000 application
is not browser-automated.
