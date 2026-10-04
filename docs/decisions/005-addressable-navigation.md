# Addressable notebook navigation

Previously, application and workspace views were React component state. Every
refresh returned to the notebook list; chapters, knowledge pages, Deck slides and
chapter-scoped questions lost their navigation context. The URL is now the source
of truth for saved document locations, with a small typed History API adapter and
no new routing dependency.

Canonical paths:

- `/` — notebook list.
- `/notebooks/{id}` — notebook conversation.
- `/notebooks/{id}/sources/{sourceId}?node={nodeId}&block={blockId}` — source
  chapter/page and optional exact citation anchor.
- `/notebooks/{id}/knowledge/{pageId}` — saved knowledge page.
- `/notebooks/{id}/decks/{deckId}?slide={slideId}` — a stable slide identity, retained
  when pages are reordered. Missing/deleted slide IDs fall back to the first page.

The `tab` query parameter retains the library panel when it differs from the view's
default. `scopeSource` / `scopeNode` retain explicit question scope through refresh,
Reader navigation and history. Scope labels are reloaded from source facts and
localized. A removed scope remains explicit and can be reset; it never silently
becomes a broader valid question scope. URLs contain resource IDs, not document
text, questions, model configuration or secrets.

Push history entries for user navigation, chapter and slide changes. Replace the
current entry for initial chapter/slide resolution, so loading a view does not
require extra Back clicks. Identical addresses do not create duplicate entries.
The notebook title is reflected in the document title; notebook cards also expose
real links for normal new-tab/bookmark behavior. Workspace instances reset when
notebook identity changes; stale source fetches and completed creation requests
must not overwrite a newer location.

History transitions use the same draft guard as in-app navigation. Unsaved
knowledge edits, slide text/revision drafts and unsent questions warn before a
view is left. Cancelling browser Back restores the exact history entry and keeps
the mounted draft. Accepted slide navigation closes the old editor. Sidebar tab
changes keep the view/draft and need no discard confirmation. Reload/tab-close
uses the browser's native before-unload warning for registered drafts.
Opening/cancelling the Deck creation dialog likewise retains the current editor;
discard confirmation belongs to the eventual view change, avoiding repeated prompts.

Unknown paths and deleted notebooks have an explicit recovery link to the list.
Unavailable source links offer a return to conversation. Unparsed/failed sources
show their pending/error state rather than an indefinite Reader spinner. An empty
chapter list also finishes loading. Returning to the list through browser history
refreshes notebook counts. Initial notebook load failures retain the requested URL
and retry controls rather than displaying the list under a notebook address.
Knowledge and Deck views
retain their error/back controls. Missing chapter IDs normalize to an available
chapter. The existing FastAPI frontend fallback already serves nested paths;
missing API routes continue returning JSON errors. Vite and the production Docker
image are tested with direct nested requests, including page refresh and new tabs.

Settings, creation dialogs and temporary transformation previews remain transient
UI actions rather than saved document destinations. No source data migration,
model call, reimport or artifact regeneration is required to adopt these routes.
