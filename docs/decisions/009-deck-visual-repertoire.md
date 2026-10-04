# Coordinate a varied visual repertoire for complete image pages

The user approved whole-page image generation but found the page expressions too
similar. On 2026-10-02 we reviewed public slide/image-generation projects and the
saved real 15-page result. Fourteen saved page directions called for dark blue
surfaces; repeated two-platform spaces and luminous paths dominated the prompts.
See [the research and source comparisons](../research/deck-visual-expression.md).

New Decks use `deck-content-v5`. After all semantic content is authored, one
structured language-model call plans the deck's visual repertoire. It saves a
versioned `art_direction` in generation metadata, keyed by stable slide identity.
Palette, drawing materials and typography form the shared identity; explanatory
form, surface, viewpoint, text placement, subject, layout and reading path vary
per page. The 13-form vocabulary supplies meaning, not geometry or templates.
If any page's content is missing, visual planning waits for the content retry.

Specialized forms require prerequisites in the saved semantic content. Deck-level
validation rejects insufficient repertoire, repeated adjacent forms, excessive
single-form use, uniform framing and repeated layout descriptions disguised by
different names. Structured repair runs before any page-image calls. Source
excerpts orient this stage without becoming new display copy; final image prompts
still contain the complete unchanged text. Explicit user revisions override the
initial composition while preserving factual and copy constraints.

The coordinated direction replaces obsolete native-scene/layout prose in new image
prompts. The palette's background swatch is not a mandate to use the same background
on every page. Reading surfaces normally vary in one palette, and density controls
arrangement rather than character compression. An explicit user background choice
can retain a uniform surface. Surface counts are reported, not enforced as an
arbitrary color quota. Numeric charts are not synthesized from incomplete data.

Real-provider review showed that valid late JSON art metadata did not ensure that
the image followed the intended subject or structure. `whole-page-v3` therefore
puts a concrete per-page composition brief before the generic copy contract and
source data. The chosen subject, view, reading surface and spatial arrangement are
explicit first-priority instructions. Conceptual maps, sections and objects form
the main artwork; generic gaming scenery is not added without a requested subject.
This is an observed engineering adjustment, not a guarantee of model compliance.

The plan remains frozen on retry and page edits. Only this page's direction enters
its cache signature; editing another page or sorting the Deck cannot invalidate
siblings. If a content revision removes a specialized form's prerequisite, this
page resolves to a generic annotated-object direction instead of inventing a removed
quotation, number or relation. It does not replan other pages. The displayed plan
is explicitly the initial planning record, not a measurement of current bitmap
compliance after custom revisions.

V4 complete-image Decks keep `whole-page-v1` and their exact existing asset-signature
shape. V2/V3 native Decks remain compatible. Both paths can create a new independent
V5 copy using unchanged grounded content, source scope, narrative and style. The
copy requires configured language and image models before it is enqueued. It does
not replace or silently upgrade an existing Deck.

A new copy discards the source's art-direction map and plans against its new stable
slide identities. It follows the current ordered page records, including saved
deletions, rather than reviving deleted pages from the initial storyboard. Repertoire
requirements scale for shortened decks; the 10/15/20-page defaults are unchanged.

Generation-time API reads show authored pages while visual planning is pending,
without treating absent planning metadata as an asset-list error. Planning failure
preserves content and exposes retry. The UI offers the saved visual plan with
nontechnical bilingual labels and a visual-copy action for existing image Decks.

Plan diversity is not image diversity or text verification. Actual page/PDF review
and exact source/copy comparison remain required for real-provider acceptance.
The raster PDF and manual text-verification limitations from decision 008 remain.
