# Direct content and concurrent whole-page generation

> 2026-10-03 文档整理：取代范围：图片并发 1–4 已由 [011](011-image-concurrency-model-settings.md) 改为 1–20；Deck 过度 source-only/禁止引申措辞已由 [015](015-user-directed-deck-interpretation.md) 取代。默认省略生硬元说明和独立滚动仍有效。

Status: Accepted, 2026-10-02.

The existing narrative and page-author prompts explicitly requested interpretations,
scholarly caveats and cover source notes. These became saved SlideSpec text, then
the image model painted that text. The reviewed legacy 20-page Deck includes added
warnings such as “不是独立验证的市场规律” and “不是此处独立验证的普遍定论”.
An image-prompt-only change cannot remove already authored text.

Apply a direct-source-content policy to brief, narrative and page authoring. Present
the original ideas directly; preserve actual factual scope and source quotations,
but do not add author-opinion headings, interpretation-boundary panels, disclaimers
or captions describing the author's metaphors from outside. Check common Chinese
and English meta-copy patterns against the supplied original evidence. Invalid
generated copy receives structured repair feedback before persistence. This check
is deliberately limited: it is not a semantic proof or automatic OCR.

New Decks record `content_policy_version=source-content-v1`. Their complete-image
prompts use `whole-page-v4`, with an explicit no-extra-visible-text rule. Legacy
Decks retain their prompt versions and signatures. The existing visual-copy action
continues to reuse text. A separate “重写内容副本” action uses
`POST /api/decks/{id}/generated-copy?rewrite_content=true`: reuse original scope,
understanding, ordered narrative and style; create new page IDs; reauthor all page
text; rebuild citations from the original evidence; then coordinate art and images.
Original Decks, images and PDF exports remain untouched.

Once all text and the whole-deck art plan are saved, whole-page image/render workers
run under one semaphore. `IMAGE_GENERATION_CONCURRENCY` defaults to 2, validates
1–4, and is passed through Docker Compose. The application still runs one heavy
job at a time; native browser composition stays serial. Completion-based progress
is monotonic even when pages finish out of order. Normal page failures preserve
successful siblings and block export until retried. TaskGroup cancels and awaits
all outstanding workers on shutdown or an unexpected error. PDF order follows
saved ordinals rather than request completion order.

The Deck viewer constrains its main content area, scrolls thumbnails and the right
preview independently, reveals the selected thumbnail without scrolling ancestors,
and resets only the right preview on page selection. ResizeObserver keeps selected
navigation visible across viewport changes and fits the whole preview image in the
remaining pane space. High-resolution originals still open from the image link;
transcripts, citations and page actions remain accessible by scrolling the right
pane. Narrative/style/visual-plan details are collapsed initially. On small screens
the thumbnail rail scrolls horizontally. All added controls are bilingual.
