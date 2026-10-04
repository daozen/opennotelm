# Choose Deck visual language from content and communicative purpose

On 2026-10-03 the user reported that different subjects shared too much of the same
visual style. Comparing saved philosophy, Discord social-research and business pages
confirmed recurring warm paper, earth/moss palettes and painted scenic worlds.
This was partly an application bias: planning demanded custom illustrations, style
called for an editorial illustrated essay with tactile materials, and subsequent
art/image instructions reinforced drawing character and matte reading surfaces.
Composition variety did not test whether the graphic language suited another topic.

New Decks carry `content-adaptive-style-v1`. The existing style model call now receives
the actual user instruction, up to 16,000 characters of the research dossier and a
semantic page outline. Provisional scene suggestions do not preselect a medium.
It assesses the communication task, source character, audience, tone and explicit
style request; compares three content-specific directions; and chooses one complete
DeckStyleManifest. Candidates describe media, palette logic, typography, spatial
language, benefits and tradeoffs. They are not drawn from a fixed theme catalogue
or a topic-to-style mapping. The assessment is internal, never slide copy.

All candidates must support readability and factual integrity. Selection also considers
the source's emotional and rhetorical character, avoiding a universal preference for
vector diagrams just because relationships are easy to draw. Conceptual photographic
and painterly imagery is allowed without claiming to document actual source events.
Exact duplicate primary-medium descriptions are rejected through structured repair;
this limited check cannot measure actual aesthetic difference or semantic fit.

The selected medium and complete style reach the whole-deck art call. The new
`deck-art-v2` preserves explanatory-form prerequisites and repertoire checks, while
an intentionally flat system can vary geometry and text placement without three
forced camera viewpoints. Reading surfaces follow content and legibility; alternating
light/dark surfaces, physical materials, paper texture and scenic openings are optional.
The form catalogue describes explanatory relations, not a graphic medium.

`whole-page-v6` puts the chosen visual language before the image's copy contract and
passes both the selected direction and actual user instruction. It preserves the
original exact-copy, source-fact, quotation and relationship constraints. A user style
request can override presentation defaults, but cannot silently rewrite saved visible
copy or fabricate evidence. Image-model compliance still requires visual review.

New metadata freezes style and art on retry. Existing Decks keep their saved prompts,
styles and image signatures. The UI's visual-copy action now requests `restyle=true`:
it preserves ordered page content, scope and citations, discards inherited style/art
and compares new content-specific directions. The original Deck is unchanged.
For copies without content rewriting, API clients omitting the flag retain the
earlier style-preserving behavior. Content rewrites now reassess style by default,
including copies of legacy Decks. Clients can explicitly pass `restyle=false` to
preserve an existing identity. The UI requests restyling on both copy actions.
Public asset lists tolerate the interval where a copy has content but no style yet.

This content-rewrite default was corrected after a real user copy completed with
the old warm-paper style on 2026-10-03. The earlier UI updated only the visual-copy
entry; the content-copy entry omitted restyling and inherited the original style
verbatim, with no adaptive-style metadata. That was an entry-point omission, not
evidence of a fresh style decision or an image-model compliance failure. The
`restyled` field now records the current copy operation, overriding an ancestor's
value, so an explicitly style-preserving copy does not misreport fresh planning.

This changes prompts and planning, not the configured model, dependencies or data
schema. There is no random palette assignment, quota requiring unlike styles across
topics, automatic artwork acceptance or automatic raster-text verification. Closely
related material may legitimately share a visual language; different media are useful
only when they help convey the content.
