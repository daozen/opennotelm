import i18next, { type TOptions } from 'i18next';
import { initReactI18next, useTranslation } from 'react-i18next';
import zh from './locales/zh-CN.json';
import en from './locales/en.json';
import lang0 from './locales/zh-TW.json';
import lang1 from './locales/ja.json';
import lang2 from './locales/ko.json';
import lang3 from './locales/es.json';
import lang4 from './locales/fr.json';
import lang5 from './locales/de.json';
import lang6 from './locales/pt-BR.json';
import lang7 from './locales/ru.json';
import lang8 from './locales/ar.json';
import lang9 from './locales/hi.json';

import { languages, isUiLanguage, detectBrowserLanguage, type UiLanguage } from './languages';
export { languages, isUiLanguage, type UiLanguage } from './languages';
export const languageCacheKey = 'opennotelm.ui-language';
function cachedLanguage(): UiLanguage {
  try {
    const value = localStorage.getItem(languageCacheKey);
    return isUiLanguage(value) ? value : detectBrowserLanguage();
  } catch {
    return detectBrowserLanguage();
  }
}
export const translationCatalogs: Record<UiLanguage, Record<string, string>> = {
  'zh-CN': zh,
  en,
  'zh-TW': lang0,
  ja: lang1,
  ko: lang2,
  es: lang3,
  fr: lang4,
  de: lang5,
  'pt-BR': lang6,
  ru: lang7,
  ar: lang8,
  hi: lang9,
};
export const i18n = i18next.createInstance();
void i18n.use(initReactI18next).init({
  resources: Object.fromEntries(
    Object.entries(translationCatalogs).map(([code, translation]) => [code, { translation }]),
  ),
  lng: cachedLanguage(),
  fallbackLng: 'en',
  supportedLngs: languages.map((language) => language.code),
  load: 'currentOnly',
  initAsync: false,
  keySeparator: false,
  nsSeparator: false,
  interpolation: { escapeValue: false }, // React escapes interpolated text.
});

export function t(key: string, options?: TOptions): string {
  return i18n.t(key, options);
}
export function useI18n(): UiLanguage {
  useTranslation(undefined, { i18n });
  return isUiLanguage(i18n.language) ? i18n.language : detectBrowserLanguage();
}
export async function applyLanguage(language: UiLanguage, cache = true) {
  await i18n.changeLanguage(language);
  try {
    if (cache)
      localStorage.setItem(languageCacheKey, language); // Only a saved UI language is cached.
    else localStorage.removeItem(languageCacheKey);
  } catch {
    /* Server preferences still work when browser storage is disabled. */
  }
}
function updateDocument() {
  document.documentElement.lang = i18n.language;
  document.documentElement.dir =
    languages.find((language) => language.code === i18n.language)?.direction ?? 'ltr';
  document.title = `OpenNoteLM · ${t('知识工作台')}`;
}
i18n.on('languageChanged', updateDocument);
updateDocument();

export function errorKey(code?: string): string {
  const key = `errors.${code ?? 'UNKNOWN_ERROR'}`;
  return i18n.exists(key) ? key : '请求失败，请重试。';
}
export function errorText(value?: { error_code?: string; error_message?: string }): string {
  return t(errorKey(value?.error_code));
}
