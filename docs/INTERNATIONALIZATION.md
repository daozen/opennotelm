# Interface languages

OpenNoteLM supports Simplified Chinese (`zh-CN`), English (`en`), Traditional Chinese (`zh-TW`), Japanese (`ja`), Korean (`ko`), Spanish (`es`), French (`fr`), German (`de`), Brazilian Portuguese (`pt-BR`), Russian (`ru`), Arabic (`ar`) and Hindi (`hi`).
On first use, match `navigator.languages` (then `navigator.language`) against
supported catalogs in preference order. Browsers generally inherit the operating
system's language, but an explicit browser preference takes precedence. Map
regional variants to available languages; Chinese Hans/Hant scripts take priority
over region, and TW/HK/MO use Traditional Chinese when no script is given. The
only Portuguese catalog is Brazilian Portuguese. Skip malformed/unsupported
preferences; fall back to English when none match. No OS or server locale is read.
Use the language selector in the application header or model setup dialog. A
successful selection applies immediately and survives reloads and server restarts.
Changing language preserves open readers, selected scope, model form fields and
unsaved Knowledge/slide drafts. Source text, notebook names, questions, answers,
Knowledge content, Deck plans/images and exported PDFs remain in their original
language. The notebook's **New content language** selector defaults to following the
interface and can independently choose any of the same 12 languages. It controls
new Chat answers, Knowledge pages, summaries, outlines and the initial Deck language;
the Deck dialog can override its own language. The choice is local to the open
workspace, not a new persisted global preference. Each submission freezes its
resolved language, so switching the interface while a job waits does not change it.
Knowledge updates retain the saved page language. Verbatim source quotations and
citation offsets remain original; the source-grounded content contracts still apply.
Legacy API requests without a language retain question/source-language behavior.
See [decision 034](decisions/034-content-output-languages.md).

## Persistence and compatibility

`GET /api/settings/preferences` returns `ui_language` and `telemetry_enabled`.
`PUT` accepts partial updates and returns the merged preferences. Missing values
are preserved; unsupported languages, explicit nulls and unknown fields are
rejected. An absent saved language returns `ui_language: null`, allowing browser detection.
Privacy-only updates do not invent or persist a default language; explicit nulls
in PUT are still rejected. Automatic choices are not persisted, while an existing
saved language always takes precedence, including choices stored by older versions.
See [decision 035](decisions/035-browser-default-language.md).
Updates merge transactionally under the telemetry send lock, so changing locale
never opts a user into or out of usage statistics. These are instance preferences
in this single-user application, not per-account settings.

The browser caches only a saved language under `opennotelm.ui-language` to avoid a
Chinese flash on refresh. Server preferences are authoritative once loaded; an unset preference clears stale cached locale and uses current browser preferences.
When saving fails, the previous language stays selected and a localized error is
shown. Disabled browser storage does not prevent server persistence. Document
language/title and date formatting follow the selection; source values remain
unchanged.

## Translation maintenance

Translations are bundled locally through i18next/react-i18next; no translation
service or runtime download is used. All 12 `frontend/src/locales/*.json` catalogs
use complete source phrases as keys, with interpolation for user content/counts.
Avoid assembling translated sentences from fragments. `useI18n()` subscribes a
component to language changes; `t()` resolves its current language. Store keys
and interpolation data for persistent status/error state, not already translated
strings. Never retroactively translate user/model-authored content. Localize the typed insufficient-evidence system status without changing its canonical stored text; identical user-authored text is left untouched. React escapes interpolated
values; this feature adds no HTML rendering.

API/job error codes have friendly translations under `errors.CODE`. Unknown
codes use a safe localized fallback, and diagnostic codes remain available.
Provider exception messages are not rendered. PDF extraction warnings retain
page numbers and get a localized presentation without changing stored metadata.

When adding a language, update supported languages, the preference schema,
resources, controls and tests. Translation tests check key/parameter parity.
Browser acceptance exercises English model settings, reader, Chat, citations,
Knowledge edit/save, locale switching with drafts, Deck generation/export/edit,
reload persistence, privacy consent preservation and mobile controls. Backend tests
cover restart persistence, old preferences, invalid input and independent updates.

`frontend/src/languages.ts` owns locale codes, native names and direction. Arabic sets the document to RTL; logical CSS spacing and directional navigation icons follow it. Source text uses its own direction and page images are never mirrored. Resources are bundled locally, including the cached locale at startup. Locale selection does not call a translation service. New translations were model-assisted and checked for key/parameter completeness; native-speaking contributors can improve phrasing. The UI review/browser acceptance entry is documented in UI_REVIEW.md.
