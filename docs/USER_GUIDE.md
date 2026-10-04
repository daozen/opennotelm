# User guide

[简体中文](USER_GUIDE.zh-CN.md) · [Quick start](https://github.com/daozen/opennotelm/blob/main/docs/README.md) · [Installation, backup and recovery](DEPLOYMENT.md)

## Configure models

On first use, configure Language, Embedding and Image roles. Enter an API base URL,
model ID and key, then test and save each role. Enter an ID manually if model-list
lookup is unavailable. Optional server-side keys can be used with an empty key field;
saved keys are not echoed back. Capability tests can incur provider charges.

Language needs compatible chat and structured JSON; scans/illustrations additionally
need image input. Test image recognition separately. A chat model is not automatically
an embedding model: retrieval requires a vector endpoint with consistent dimensions.
Default whole-page Decks require an image-generation service. Roles can use different
services; short connection tests do not guarantee long-document or image-text quality.
After changing Embedding, monitor the overall/per-source rebuild and retry failures;
original documents and citations remain unchanged.

## Import and read

Create a notebook, then multi-select EPUB, PDF, DOCX, Markdown or text files. Results
are reported per item, with duplicate confirmation. Convert old `.doc` files to `.docx`
using trusted software before uploading. EPUB tables of contents, PDF bookmarks and
Word headings become chapter trees. A PDF without bookmarks does not get a fake
chapter for every page. Use previous/next chapter or PDF page controls and inspect
original images. OCR is model output: check exact quotes, numbers and diagrams.

For public web articles, paste one URL per line (up to 50). Saving article images is
optional and initially checked; the text is usable before background image processing
finishes. Imports preserve an HTML snapshot, execute no scripts and reuse no browser
login cookies. Login walls, dynamic-only pages and blocked image hotlinks may fail.
Image retry preserves successful saved originals and does not refetch the article HTML.
Only import material you have the right to use; do not bypass access restrictions.

## Ask questions and save knowledge

Chat answers use the selected evidence/scope. Open a citation to see its related
passage and jump to the original. Missing evidence is reported; general knowledge
is not presented as source evidence. Save/update knowledge pages; updates retain
the page's output language. New-content language follows the interface by default,
or can independently select any of the 12 languages. Original citations are not
translated. Changing interface language does not rewrite existing content. Requests
freeze the submitted language; saved interface choices override browser detection.

## Generate a Visual Deck

Select sources or expand a source's chapter tree. A parent includes its descendants;
overlapping scopes are deduplicated. Choose one combined Deck or separate Decks per
source/chapter and review counts/pages. Source-based naming is available for a single
source; chapter names include the book title, real hierarchy number and chapter title.

Additional instructions can specify depth, audience, language and visual style.
Explicit requests override presentation defaults, within factual/scope/technical limits.
Deck interpretation can use model knowledge, but background and analogies do not
pretend to have source citations. A chapter automatically uses the uploaded parent
book as background. Ask to stay within the chapter if you want to exclude that context.

Generation saves understanding, plan and page text before art direction, complete
images and PDF. Dependent stages remain ordered. Separate Decks and independent page
requests use bounded shared budgets; excessive concurrency may worsen rate limits.
First reading of a long book or many images can take time; later chapters reuse suitable
saved results. In Model settings adjust task count (1–8), shared provider requests
(1–20), and content/OCR/image concurrency (each 1–20). New work uses new settings;
running work keeps frozen settings.

## Review, revise and download

Click the image's left/right half or use ↑/↓ to change pages. Inputs/edit dialogs
keep their own keyboard behavior. Focus view enlarges the preview; Escape exits.
The saved text draft and citations are below the image. Editing text regenerates
that page. Content-rewrite copies reread sources; visual-optimization copies keep
text while choosing new visual direction. The original Deck remains available.

Stop queued/running Decks and later resume saved progress. Failed/partial Decks retain
completed pages. Check failure details/generation history before retrying. Deletion
requires confirmation and retains original sources. Renaming changes subsequent PDF
filenames. Batch download selects eligible current PDFs, with no new model/export calls;
ZIP limits are 100 Decks/512 MiB. Re-export existing PDFs for lossless size optimization
without generating new images.

Default PDFs contain complete image pages, not searchable/selectable body text.
Source images are inputs to understanding; final pages redraw them. Check image text,
chart numbers and quotes against drafts/originals before relying on or sharing them.

## Troubleshooting and privacy

| Symptom | Next step |
|---|---|
| Connection failure | Check container-to-host routing, API base URL, credentials, model ID and public provider status. |
| Missing OCR | Test language-model image input and inspect/retry per-image errors; image generation is not OCR. |
| Invalid structured output | Inspect the actual failed stage and safe validation rules; use a capable JSON/vision model. |
| Image failure | Check safe HTTP/error codes, image capability and rate limits; reduce shared concurrency and retry missing pages. |
| Wrong image text | Compare the draft with the image; revise/regenerate or use a more capable image model. |
| Web import failure | Check public accessibility; scripts/login/cookies and private-address imports are unsupported. |
| Instance lock | Find/stop the actual owner deliberately; never delete the lock to bypass it. |
| Upgrade failure | Preserve the current directory and restore the matching complete backup; never downgrade just code against a migrated database. |

Safe diagnostic downloads do not contain source text/prompts/keys, but inspect them
before sharing. Use self-written minimal samples, not private books, database dumps
or raw model responses. Statistics default off. With no receiver configured you can
save your choice, but nothing is sent externally; local queues are bounded. See
[privacy](PRIVACY.md) and [security](../SECURITY.md).
