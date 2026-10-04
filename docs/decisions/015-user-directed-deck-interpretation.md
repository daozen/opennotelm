# User-directed Deck interpretation

> 2026-10-03 文档整理：副本风格口径更新：本文早期描述的内容副本保留 shared style，后由 [016](016-content-adaptive-deck-style.md) 改为默认重新选择风格（显式 `restyle=false` 仍可保留）。内容/basis/用户优先规则继续适用。

The 2026-10-03 clarification allows model knowledge to deepen a Deck, especially
when the user asks for interpretation. Avoiding rigid labels such as “作者见解”,
“作者观点”, “解读边界” and “阅读边界” is a presentation default, not a prohibition
on substantive explanation. This supersedes the broader source-only wording in
decision 010 for Decks. Chat, Knowledge and source transformations retain their
existing source-grounded policies.

## Instruction precedence

Deck generation separates factual integrity and technical limits from presentation
defaults. Explicit user instructions override default depth, organization, editorial
scaffolding and text density. A page revision is the more specific instruction for
that page. Source passages, old dossiers, briefs and plans cannot introduce task
instructions or override the user's request. Selected scope, chosen page count,
output language, schema bounds and configured model context remain explicit API
contracts. Quotes and source IDs must remain authentic, and user assertions do not
become verified facts.

A small structured preference resolution happens before the first source reading.
It persists `source_only`, `include_editorial_notes` and `dense_text` in the existing
Deck metadata, so subsequent pages and task recovery share the same preferences.
Default values are false: model explanations are allowed, generic editorial panels
are omitted, and normal readable text budgets apply. Negating a label is not a
request to include it; asking for depth is not a request for dense pages. Page
revision preferences are resolved locally without changing the whole Deck.

## Interpretation and provenance

The Deck dossier receives the real supplemental instruction at every synthesis
level, plus source titles and selected chapter titles as bibliographic context.
It retains original quotations and citations while developing conceptual reasoning,
metaphors and useful contextual knowledge. Paragraph-by-paragraph requests guide
both reading and planning. Page authors receive the whole bounded dossier, not just
its heading. Accessible prose should preserve difficult ideas instead of replacing
them with generic self-help. Interpretations must respect source actions, speakers
and chronology. Dossier and author output remain within configured context bounds.

Saved semantic elements, list items and visual relationships have internal `basis`:

- `source`: actual source content, retaining supplied citations where required.
- `interpretation`: a reading anchored to the passages being interpreted; its
  citation identifies those passages rather than proving the reading is literal.
- `background`: relevant model knowledge, without invented original-source support.
- `analogy`: a clearly illustrative invented example, without source citations.

Items may inherit their parent basis. Background and analogy cannot carry or inherit
source citations; quotations require source basis. Source-only preferences reject
outside background and analogy while still allowing close reading of the supplied
passages. These checks validate structural provenance and do not establish the
truth of every model assertion. The model is instructed to omit doubtful specifics,
avoid invented references and phrase debatable readings naturally. This feature
uses model knowledge; it does not add automatic web research.

`basis` stays out of the visible image copy and UI prose. Useful explanation and
metaphor analysis are allowed; unsolicited editorial labels/boilerplate trigger a
repair. An explicit request for editorial notes overrides that presentation default.
Ordinary page budgets retain their 450-unit limit; explicitly requested dense pages
may use up to 900 units. Merely requesting detailed interpretation keeps normal
visual density.

## Existing Decks and reuse

New output records `source-interpretation-v2`; complete-image prompts use
`whole-page-v5`. Legacy prompt-version identities and completed output remain
compatible. Resume preserves saved progress rather than silently rewriting it.
Visual-only copies continue to preserve exact saved wording.

A content-rewritten copy refreshes the brief. At standard 10/15/20 lengths it also
regenerates the dossier and replans content before authoring, preserving the actual
saved page count and shared style. If the user manually shortened the Deck to another
length, it reuses the dossier and evidence IDs to preserve that page sequence while
refreshing the brief and wording; old source-only phrasing is context, not a stronger
instruction. It does not resurrect deleted pages. The original Deck stays intact. No database
migration or extra generation-mode UI is needed.

## Verification

Contract tests cover interpretation and uncited examples, source-only rejection,
explicit editorial overrides and negation, density limits, first-reading instruction
propagation, whole-dossier context, inherited citation rejection and hidden metadata.
Existing generated-page tests exercise rewritten copies, page edits, retries and
source preservation. Real-provider textual samples and acceptance results are
recorded in ACCEPTANCE.md; synthetic fixtures alone are not evidence of philosophical
accuracy or subjective explanation quality.
