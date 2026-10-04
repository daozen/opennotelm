# Separate Deck batches and hierarchical chapter selection

The 2026-10-03 request extends the existing merged chapter generation. The creation
dialog now chooses merged or separate generation, defaulting to merged. The original
single-Deck endpoint and saved Deck behavior remain compatible.

## Selection semantics

For the notebook's selected sources, the dialog can narrow the participating subset.
Separate mode creates one Deck per participating source in notebook source order.
For an individual EPUB, bookmarked PDF or DOCX, the directory is a selectable tree.
Parent selection covers its descendants, and deselecting a descendant makes the
ancestor partially selected. Expand/collapse and keyboard navigation retain choices.
Level selection replaces the selection with all chapters at that relative tree
level, including their descendants. It does not merely expand the display.

A selected parent creates one Deck containing its whole subtree. Parent/child
overlap is canonicalized before submission and on the server, so selecting a parent
does not also create redundant child Decks. To create one Deck per subsection, select
the subsection level or individual children. Deselecting a child removes its parent
scope and retains the other selected subtrees; parent-only introductory text is then
outside those subtree scopes. The dialog displays the exact number of Decks, pages
per Deck and total pages. Empty selections cannot generate. Missing directories
continue to use the whole source; PDF page-level bookmark limitations are unchanged.

EPUB tree display follows the document's directory order/depth; other formats use
parent relationships. Generation retains normalized source order and exact existing
section scopes. Existing non-heading EPUB anchor projections remain usable without
rewriting facts. A linked multi-section initial scope is restored rather than widened
to the whole source.

## Durable creation and failure behavior

`POST /api/notebooks/{notebook_id}/decks/batch` accepts the existing Deck options and
a required request key. All scopes are resolved, frozen and checked for readable
content before any Deck jobs are published. At most 100 independent Decks can be
created in one batch. A single SQLite transaction creates every Deck, enqueues its
job, and records a receipt in migration 015's `deck_batches` table. An interrupted
transaction leaves no partial batch. The receipt cascades with notebook deletion.

Repeated identical requests with the same key return the original batch and Deck
identities, even after restart or later source-selection changes. A changed body
with an already-used key is rejected. The dialog reuses its key after a failed
network response and generates a new key when the payload changes. Browser key
generation uses `crypto.getRandomValues`, which is available on the HTTP LAN origin.
Closing and reopening the dialog starts a new intentional creation request.
If a returned Deck has since been deleted, the retained receipt rejects replay with
`DECK_BATCH_DELETED`; see [decision 014](014-deck-controls-and-preview.md).

Each Deck has its own frozen scope, generation stages, citations, images, export
and retry. One failure does not stop queued siblings or rewrite completed Decks.
Jobs retain the application's single-heavy-job queue; equal timestamps use durable
insertion order rather than random ID order. Model image concurrency continues to
apply within each Deck. Source labels remain in the Deck library after AI titles
are generated, and queued jobs show a waiting state. Generated/rewrite copies do
not inherit membership in the original batch.

## Verification

Backend tests cover EPUB/PDF/Word scope separation, exact citations, overlap,
source ordering and frozen choices, retry without duplicated Decks, process restart,
invalid/empty/foreign selections, batch bounds, transaction rollback, independent
sibling failure/retry, notebook deletion and credential-free receipts. Frontend
tests cover mixed checkboxes, subtree exclusion, level selection, keyboard/collapse
behavior, linked scopes, mode switching, counts, source subsets and network retry
with bilingual draft preservation. The browser flow generates two source Decks and
two chapter Decks, checks independent PDFs and excluded content, then refreshes.
Docker acceptance records persistent batch identities and compares outputs after
both process restart and container recreation. All providers in these new acceptance
flows are isolated synthetic providers; no user material is sent to a real model.
