import { expect, test } from 'vitest';
import { languages, matchPreferredLanguage } from './languages';

test.each(languages)('matches supported catalog $code', ({ code }) => {
  expect(matchPreferredLanguage([code])).toBe(code);
});

test.each([
  ['en-GB', 'en'],
  ['fr-CA', 'fr'],
  ['es-MX', 'es'],
  ['pt-PT', 'pt-BR'],
  ['pt', 'pt-BR'],
  ['zh', 'zh-CN'],
  ['zh-SG', 'zh-CN'],
  ['zh-HK', 'zh-TW'],
  ['zh-MO', 'zh-TW'],
  ['zh-Hant', 'zh-TW'],
  ['zh-Hant-CN', 'zh-TW'],
  ['zh-Hans-HK', 'zh-CN'],
  ['zh_TW', 'zh-TW'],
  ['ja-JP-u-ca-japanese', 'ja'],
  ['HI-in', 'hi'],
])('maps browser locale %s to %s', (browser, expected) => {
  expect(matchPreferredLanguage([browser])).toBe(expected);
});

test('respects language preference order, skips invalid or unsupported values, and falls back to English', () => {
  expect(matchPreferredLanguage(['it-IT', '', 'invalid_locale_!', 'ko-KR', 'en'])).toBe('ko');
  expect(matchPreferredLanguage(['de-DE', 'fr-FR'])).toBe('de');
  expect(matchPreferredLanguage(['it-IT', 'nl-NL'])).toBe('en');
  expect(matchPreferredLanguage([])).toBe('en');
});
