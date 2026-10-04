/** Stable locale codes shared by preferences, the picker and acceptance checks. */
export const languages = [
  { code: 'zh-CN', name: '简体中文', direction: 'ltr' },
  { code: 'en', name: 'English', direction: 'ltr' },
  { code: 'zh-TW', name: '繁體中文', direction: 'ltr' },
  { code: 'ja', name: '日本語', direction: 'ltr' },
  { code: 'ko', name: '한국어', direction: 'ltr' },
  { code: 'es', name: 'Español', direction: 'ltr' },
  { code: 'fr', name: 'Français', direction: 'ltr' },
  { code: 'de', name: 'Deutsch', direction: 'ltr' },
  { code: 'pt-BR', name: 'Português (Brasil)', direction: 'ltr' },
  { code: 'ru', name: 'Русский', direction: 'ltr' },
  { code: 'ar', name: 'العربية', direction: 'rtl' },
  { code: 'hi', name: 'हिन्दी', direction: 'ltr' },
] as const;
export type UiLanguage = (typeof languages)[number]['code'];
export function isUiLanguage(value: unknown): value is UiLanguage {
  return languages.some((language) => language.code === value);
}

/** Resolve the browser's ordered BCP 47 preferences to an available catalog. */
export function matchPreferredLanguage(preferences: readonly string[]): UiLanguage {
  for (const value of preferences) {
    try {
      const locale = new Intl.Locale(value.replaceAll('_', '-'));
      if (locale.language === 'zh') {
        if (locale.script === 'Hant') return 'zh-TW';
        if (locale.script === 'Hans') return 'zh-CN';
        return ['TW', 'HK', 'MO'].includes(locale.region ?? '') ? 'zh-TW' : 'zh-CN';
      }
      const matched = languages.find((item) => item.code.split('-')[0] === locale.language);
      if (matched) return matched.code;
    } catch {
      // A malformed preference must not prevent trying the next language.
    }
  }
  return 'en';
}

export function detectBrowserLanguage(): UiLanguage {
  if (typeof navigator === 'undefined') return 'en';
  return matchPreferredLanguage([...(navigator.languages ?? []), navigator.language]);
}
