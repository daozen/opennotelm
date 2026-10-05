# 039 — Explicit Deck output-language propagation

Date: 2026-10-05. Supplements [034](034-content-output-languages.md).

The output language is frozen at submission. A matching `DeckBrief.language` code
alone does not make the prose follow that language. Deck-specific synthesis had no
explicit language instruction, narrative planning only received the language buried
inside the brief, and authoring referred vaguely to the requested language while
being told to follow potentially mixed-language plans and dossiers.

Pass the language through source synthesis, every narrative/content stage and their
structural repairs. Explicitly name the language in each system instruction and
provide it as a top-level input. Earlier wording, source data, internal visual
directions and multilingual examples are context, not output-language instructions.
An old plan's meaning may guide writing; its language must not override the selected
language. Original quotations, proper names and code remain exact; honor explicit
bilingual/multilingual requests while using the selected language for primary prose.

The user preferred correcting generation at its source to adding strong validation.
There is **no script-based rejection, forced translation, language-identification
model call or additional language-repair loop**. Existing schema, factual-integrity,
citation and context-budget checks remain. Real-model language accuracy must still
be verified within authorized document/endpoint scope. Existing Decks are not
automatically rewritten.

生成语言须直接传递到理解、规划、写作及结构修复。源文、旧规划和美术描述只提供
上下文，不决定新文字的语言；保留准确引文、专名、代码和明确要求的双语展示。
按用户要求从指令链修正，不增加文字体系强制校验、翻译或语言判别调用。

Regression checks cover all supported language instructions, preservation of the
language contract during structural repairs and unchanged original citations.
