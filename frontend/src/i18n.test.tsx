import { readFileSync, readdirSync } from 'node:fs';
import ts from 'typescript';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import LanguageSettings, { LanguagePreferencesProvider } from './LanguageSettings';
import Setup from './Setup';
import SlideEditor from './SlideEditor';
import { api, type Slide } from './api';
import {
  applyLanguage,
  errorKey,
  i18n,
  languageCacheKey,
  languages,
  translationCatalogs,
  t,
} from './i18n';
import en from './locales/en.json';
import zh from './locales/zh-CN.json';

const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

describe('language preferences', () => {
  it('loads the saved language, saves only the language field, and keeps the previous language on failure', async () => {
    const fetch = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(reply({ ui_language: 'en', telemetry_enabled: true }));
    render(
      <LanguagePreferencesProvider>
        <LanguageSettings />
      </LanguagePreferencesProvider>,
    );
    await waitFor(() => expect(screen.getByLabelText('Interface language')).toBeEnabled());
    expect(document.documentElement.lang).toBe('en');
    expect(document.title).toBe('OpenNoteLM · Knowledge workspace');
    fetch.mockResolvedValueOnce(reply({ ui_language: 'zh-CN', telemetry_enabled: true }));
    fireEvent.change(screen.getByLabelText('Interface language'), { target: { value: 'zh-CN' } });
    await waitFor(() => expect(screen.getByLabelText('界面语言')).toBeEnabled());
    expect(fetch.mock.calls[1][1]?.body).toBe(JSON.stringify({ ui_language: 'zh-CN' }));
    expect(localStorage.getItem(languageCacheKey)).toBe('zh-CN');
    fetch.mockResolvedValueOnce(reply({ error: { code: 'UNKNOWN_ERROR' } }, 500));
    fireEvent.change(screen.getByLabelText('界面语言'), { target: { value: 'en' } });
    expect(await screen.findByRole('alert')).toHaveTextContent('语言保存失败');
    expect(screen.getByLabelText('界面语言')).toHaveValue('zh-CN');
    expect(localStorage.getItem(languageCacheKey)).toBe('zh-CN');
  });

  it('can change language when browser storage is unavailable', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('disabled');
    });
    await applyLanguage('en');
    expect(i18n.language).toBe('en');
    expect(document.documentElement.lang).toBe('en');
  });
});

describe('translated UI keeps editable content', () => {
  it('preserves model drafts and translates an existing error when switching languages', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) =>
      String(url).endsWith('/image-recognition') || String(url).endsWith('/content-generation')
        ? reply({ concurrency: 4, min_concurrency: 1, max_concurrency: 20 })
        : reply(
            { error: { code: 'MODEL_TIMEOUT', message: 'Raw provider message must not render' } },
            502,
          ),
    );
    render(
      <Setup
        settings={{ setup_complete: false, models: {} }}
        onSaved={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    const fields = within(screen.getByText('语言模型').closest('form')!);
    fireEvent.change(fields.getByLabelText('模型 ID'), { target: { value: '我的-model' } });
    fireEvent.change(fields.getByLabelText('访问密钥'), { target: { value: 'draft-key' } });
    fireEvent.click(fields.getByText('测试并保存'));
    await fields.findByRole('alert');
    await act(() => applyLanguage('en'));
    expect(fields.getByText('Language model')).toBeVisible();
    expect(fields.getByLabelText('Model ID')).toHaveValue('我的-model');
    expect(fields.getByLabelText('API Key')).toHaveValue('draft-key');
    expect(fields.getByRole('alert')).toHaveTextContent('The model service timed out');
    expect(screen.queryByText('Raw provider message must not render')).toBeNull();
  });

  it('translates slide field labels while retaining the current text draft', async () => {
    const slide = {
      id: 'slide',
      revision: 1,
      spec: {
        content_elements: [
          {
            id: 'e',
            type: 'bullet_list',
            text: '',
            label: '',
            items: [{ label: '原文标签', text: '原文内容', citations: [] }],
            citations: [],
          },
        ],
      },
    } as unknown as Slide;
    render(
      <SlideEditor deckId="deck" slide={slide} mode="text" onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    fireEvent.change(screen.getByLabelText('第 1 项内容 2'), {
      target: { value: '尚未保存的中文草稿' },
    });
    await act(() => applyLanguage('en'));
    expect(screen.getByLabelText('Item 1 content 2')).toHaveValue('尚未保存的中文草稿');
    expect(screen.getByLabelText('Item 1 label 1')).toHaveValue('原文标签');
    expect(screen.getByRole('button', { name: 'Save and update slide' })).toBeEnabled();
  });

  it('uses a localized safe fallback for unknown error codes and network failures', async () => {
    await applyLanguage('en');
    expect(t(errorKey('NEW_PROVIDER_CODE'))).toBe('Request failed. Please try again.');
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new Error('private network detail'));
    await expect(api('/anything')).rejects.toMatchObject({
      code: 'NETWORK_ERROR',
      message: 'errors.NETWORK_ERROR',
    });
  });
});

describe('translation resources', () => {
  it('contains every interface translation key and dynamic label in both catalogs', () => {
    for (const filename of readdirSync('src').filter(
      (name) => name.endsWith('.tsx') && !name.includes('.test.'),
    )) {
      const source = ts.createSourceFile(
        filename,
        readFileSync(`src/${filename}`, 'utf8'),
        ts.ScriptTarget.Latest,
        true,
        ts.ScriptKind.TSX,
      );
      const visit = (node: ts.Node) => {
        if (
          ts.isStringLiteral(node) &&
          (/[\u3400-\u9fff]/.test(node.text) ||
            (ts.isCallExpression(node.parent) && node.parent.expression.getText(source) === 't'))
        ) {
          expect(zh, `${filename}: ${node.text}`).toHaveProperty([node.text]);
          expect(en, `${filename}: ${node.text}`).toHaveProperty([node.text]);
        }
        ts.forEachChild(node, visit);
      };
      visit(source);
    }
  });

  it('covers the same keys with matching interpolation parameters and complete English text', () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(zh).sort());
    const variables = (text: string) =>
      [...text.matchAll(/\{\{([^}]+)\}\}/g)].map((match) => match[1]).sort();
    for (const key of Object.keys(zh) as (keyof typeof zh)[]) {
      expect(en[key].trim(), key).not.toBe('');
      expect(variables(en[key]), key).toEqual(variables(zh[key]));
      expect(en[key], key).not.toMatch(/[\u3400-\u9fff]/);
    }
  });
});

describe('all supported locales', () => {
  it('bundles complete translations with identical parameters for every supported language', () => {
    const variables = (value: string) =>
      [...value.matchAll(/\{\{([^}]+)\}\}/g)].map((match) => match[1]).sort();
    expect(languages).toHaveLength(12);
    expect(Object.keys(translationCatalogs).sort()).toEqual(
      languages.map((language) => language.code).sort(),
    );
    for (const { code } of languages) {
      const catalog = translationCatalogs[code];
      expect(Object.keys(catalog).sort(), code).toEqual(Object.keys(en).sort());
      for (const [key, value] of Object.entries(catalog)) {
        expect(value.trim(), `${code}: ${key}`).not.toBe('');
        if (!['zh-CN', 'zh-TW', 'ja', 'ko'].includes(code))
          expect(value, `${code}: ${key}`).not.toMatch(/[\u3400-\u9fff]/);
        expect(variables(value), `${code}: ${key}`).toEqual(variables(en[key as keyof typeof en]));
      }
    }
  });
  it('sets Arabic right-to-left direction and restores left-to-right with other languages', async () => {
    await applyLanguage('ar');
    expect(document.documentElement.lang).toBe('ar');
    expect(document.documentElement.dir).toBe('rtl');
    expect(t('创建笔记本')).not.toBe('创建笔记本');
    await applyLanguage('ja');
    expect(document.documentElement.lang).toBe('ja');
    expect(document.documentElement.dir).toBe('ltr');
  });
});

it('detects browser preferences when no language is saved, without persisting automatic choices', async () => {
  vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['it-IT', 'fr-CA']);
  vi.spyOn(navigator, 'language', 'get').mockReturnValue('it-IT');
  localStorage.setItem(languageCacheKey, 'zh-CN');
  const fetch = vi
    .spyOn(globalThis, 'fetch')
    .mockResolvedValue(reply({ ui_language: null, telemetry_enabled: false }));
  render(
    <LanguagePreferencesProvider>
      <LanguageSettings />
    </LanguagePreferencesProvider>,
  );
  await waitFor(() => expect(i18n.language).toBe('fr'));
  expect(localStorage.getItem(languageCacheKey)).toBeNull();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][1]?.method).toBeUndefined();
});

it('prioritizes a saved selection over browser preferences and respects its direction', async () => {
  vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['ja-JP']);
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    reply({ ui_language: 'ar', telemetry_enabled: false }),
  );
  render(
    <LanguagePreferencesProvider>
      <LanguageSettings />
    </LanguagePreferencesProvider>,
  );
  await waitFor(() => expect(i18n.language).toBe('ar'));
  expect(document.documentElement.dir).toBe('rtl');
  expect(localStorage.getItem(languageCacheKey)).toBe('ar');
});
