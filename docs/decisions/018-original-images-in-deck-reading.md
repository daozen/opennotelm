# Read original source images during Deck generation

Date: 2026-10-03

## Problem

Image recognition transcripts are useful searchable material, but can lose spatial
relationships, shapes, colors, diagram structure and photographic detail. Deck reading and
page authorship previously received only those transcripts. They did not see source pixels.

## Decision

Deck dossiers and automatic whole-work reading now attach the corresponding original
source-media images to their first reading requests. PDF embedded figures, rasterized
scan/vector pages, and the existing DOCX/EPUB image blocks use the same provenance path.
Image evidence is kept separate from adjacent text evidence. Attachments are associated
with their exact source/block IDs and supplied citation IDs; a chapter's primary reading
cannot silently acquire another chapter's pixels. Whole-work reading is a separate pass
with its own evidence namespace and remains subject to explicit chapter-only restrictions.

Every eligible image is read during the initial synthesis, in groups limited by both
image count (at most four) and estimated context usage. Large collections are reduced as
grounded prose after this first visual reading. Transfers use high-detail images bounded
to 1600px, with a conservative 3072-token allowance per image; the saved source media
remains unchanged. This is not a guarantee of provider token accounting or OCR accuracy.
If context cannot fit even one image, generation reports the existing context-budget
error instead of quietly discarding the image.

Page authors then see originals associated with that page's evidence, up to four per
request and fewer if needed to leave room for prose, schema and output. Additional images
are explicitly listed as not reattached; their dossier findings
remain available. The visual-reading policy asks for observed structure and relationships
in `visual_direction`, without making the source's aesthetic a mandatory Deck style.
For pages citing primary source images, art direction and the final text-to-image prompt
also receive compact source visual guidance from this authored direction. Image-aware
page signatures include this guidance/version.

Original-media checksums enter synthesis checkpoint keys and whole-work cache keys.
Cached prose can be reused without storing base64 images in SQLite or re-reading pixels
on a successful checkpoint. Source files are read off the event loop, checked for
containment in the internal media directory and checked against the collected checksum
before attachment. External document image URLs are never fetched by this path.

An image with an available original but an empty transcript can supply visual evidence.
Its citation uses zero text offsets and returns the original image with an empty quote;
it does not fabricate OCR text. This exception only applies to an empty image block with
available registered media. Ordinary text still requires a nonempty exact span. The
internal visual placeholder is forbidden in visible slide copy. Sources still need to
complete the existing ingestion workflow before they can be selected.

Document text, visible image text, images and summaries remain untrusted data. Instructions
inside them cannot override the actual user request. An unsupported visual endpoint or
missing original fails explicitly and can be retried; there is no automatic transcript-only
downgrade. General Knowledge/Chat generation retains its existing text-only contract.

## Limits and compatibility

This change directly improves content interpretation and visual planning. The final image
adapter still calls `images/generations` with a textual page prompt: it does not send
original bitmaps to an image-editing endpoint or embed originals into the generated page.
Generated diagrams are reconstructions, not exact documentary reproductions. Exact chart,
photograph or screenshot preservation requires a separate original-asset composition path.

Existing completed Decks stay frozen. New Decks and standard-length content rewrites use
the new reading path. Manually shortened content copies retain their existing safeguard
against automatic replanning. Visual-only copies reuse saved interpretation; they cannot
recover content that the old dossier never read. Original images cannot compensate for
files which have not been parsed/extracted, tiny figures excluded by the existing parser,
or details illegible at the bounded transfer resolution.

## Validation

Regression cases cover original pixels reaching dossier/page authors despite an incomplete
transcript, chapter/foreign-source isolation, whole-work reuse, reading every image in
bounded batches, checksum invalidation, multimodal repair/retry, missing originals,
captionless-image citations, rejection of zero-width text citations, and guidance reaching
art direction/final page generation and PDF export. Native rendering uses the existing
renderer suite. Real model validation is recorded in `docs/ACCEPTANCE.md`.
