import { test, expect, type APIRequestContext, type Page } from '@playwright/test';
import { languages } from '../src/languages';
import { readFileSync } from 'node:fs';

const configure = async (request: APIRequestContext) => {
  for (const role of ['language', 'embedding', 'image']) {
    expect(
      (
        await request.post('/api/settings/models/test', {
          data: {
            role,
            base_url: 'http://127.0.0.1:4301/v1',
            api_key: 'test-only-key',
            model_id: 'test-model',
          },
        })
      ).ok(),
    ).toBeTruthy();
  }
};
const noOverflow = async (page: Page) => {
  const layout = await page.evaluate(() => ({
    width: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    overflowing: [...document.querySelectorAll('body *')]
      .map((el) => ({
        el: el.tagName + '.' + el.className,
        rect: el.getBoundingClientRect().toJSON(),
      }))
      .filter(
        ({ rect }) => rect.width > 0 && (rect.left < -1 || rect.right > window.innerWidth + 1),
      )
      .slice(0, 12),
  }));
  expect(layout.scrollWidth, JSON.stringify(layout)).toBeLessThanOrEqual(layout.width);
};
test.afterEach(async ({ request }) => {
  await request.put('/api/settings/preferences', { data: { ui_language: 'zh-CN' } });
});

test('dialogs support keyboard navigation and show deletion failures beside the action', async ({
  page,
  request,
}) => {
  await configure(request);
  const title = `交互检查 ${Date.now()}`;
  const notebook = await (await request.post('/api/notebooks', { data: { title } })).json();
  try {
    await page.goto('/');
    const create = page.getByRole('button', { name: '创建笔记本', exact: true }).first();
    await create.click();
    const dialog = page.getByRole('dialog', { name: '创建笔记本', exact: true });
    await expect(dialog.getByLabel('笔记本名称')).toBeFocused();
    await page.getByLabel('笔记本名称').fill('未提交的名称');
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
    await expect(create).toBeFocused();
    await page.getByRole('button', { name: `管理 ${title}` }).click();
    await page.getByRole('button', { name: '删除笔记本', exact: true }).click();
    const deletion = page.getByRole('dialog', { name: `删除「${title}」？` });
    await page.route(`**/api/notebooks/${notebook.id}`, async (route) => {
      if (route.request().method() === 'DELETE')
        await route.fulfill({ status: 500, json: { error: { code: 'NETWORK_ERROR' } } });
      else await route.continue();
    });
    await deletion.getByRole('button', { name: '删除笔记本', exact: true }).click();
    await expect(deletion.getByRole('alert')).toBeVisible();
    await deletion.getByRole('button', { name: '删除笔记本', exact: true }).focus();
    await page.keyboard.press('Tab');
    await expect(deletion.getByRole('button', { name: '取消' })).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(deletion).not.toBeVisible();
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible();
    await page.unroute(`**/api/notebooks/${notebook.id}`);
  } finally {
    await request.delete(`/api/notebooks/${notebook.id}`);
  }
});

test('small-screen sections keep chat drafts and open sources in the reading workspace', async ({
  page,
  request,
}) => {
  await configure(request);
  const notebook = await (
    await request.post('/api/notebooks', { data: { title: '平板与手机交互检查' } })
  ).json();
  try {
    const source = await (
      await request.post(`/api/notebooks/${notebook.id}/sources/upload`, {
        multipart: {
          file: {
            name: 'ui-review.md',
            mimeType: 'text/markdown',
            buffer: Buffer.from('# 可读原文\n\n这是一段用于验证阅读的完整原文。'),
          },
        },
      })
    ).json();
    if (source.duplicate) {
      expect(
        (await request.post(`/api/notebooks/${notebook.id}/sources/${source.source.id}`)).ok(),
      ).toBeTruthy();
    } else {
      await expect
        .poll(async () => (await (await request.get(`/api/jobs/${source.job.id}`)).json()).status)
        .toBe('completed');
    }
    await page.setViewportSize({ width: 1024, height: 768 });
    await page.goto(`/notebooks/${notebook.id}`);
    const sections = page.getByRole('navigation', { name: '工作区分区' });
    const question = page.getByLabel('向资料提问');
    await question.fill('尚未发送的完整问题');
    await sections.getByRole('button', { name: '资料与知识', exact: true }).click();
    await expect(question).not.toBeVisible();
    await expect(page.locator('#workspace-library')).toBeVisible();
    await sections.getByRole('button', { name: '创作空间', exact: true }).click();
    await expect(page.locator('#workspace-studio')).toBeVisible();
    await sections.getByRole('button', { name: '工作区', exact: true }).click();
    await expect(question).toHaveValue('尚未发送的完整问题');
    await question.fill('');
    await sections.getByRole('button', { name: '资料与知识', exact: true }).click();
    await page.locator('.source-open').click();
    await expect(page.getByRole('region', { name: '资料阅读器' })).toBeVisible();
    await expect(page.locator('.reader-content')).toContainText('完整原文');
    await expect(sections.getByRole('button', { name: '工作区', exact: true })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    for (const width of [1024, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      await noOverflow(page);
      await page.screenshot({ path: `test-results/ui-reader-${width}.png`, fullPage: true });
    }
    const deck = await (
      await request.post(`/api/notebooks/${notebook.id}/decks`, { data: { slide_count: 10 } })
    ).json();
    await expect
      .poll(async () => (await (await request.get(`/api/decks/${deck.id}`)).json()).status, {
        timeout: 60000,
      })
      .toBe('ready');
    await page.goto(`/notebooks/${notebook.id}/decks/${deck.id}`);
    const view = page.getByRole('region', { name: 'Visual Deck', exact: true });
    await expect(view.getByRole('link', { name: '下载 PDF · 10 页' })).toBeVisible();
    await expect(view.getByRole('button', { name: '重新解读并生成副本' })).not.toBeVisible();
    await view.locator('.deck-more-actions > summary').click();
    await expect(view.getByRole('button', { name: '重新解读并生成副本' })).toBeVisible();
    await view.locator('.deck-more-actions > summary').click();
    for (const width of [1440, 1024, 390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      await noOverflow(page);
      expect(
        (await page.locator('.deck-preview-stage').boundingBox())!.height,
      ).toBeGreaterThanOrEqual(768);
      await page.screenshot({ path: `test-results/ui-deck-${width}.png`, fullPage: true });
    }
  } finally {
    await request.delete(`/api/notebooks/${notebook.id}`);
  }
});

test('all twelve languages persist, keep model drafts and fit phone/tablet layouts, including Arabic RTL', async ({
  page,
  request,
}) => {
  test.setTimeout(120000);
  await configure(request);
  await page.goto('/');
  for (const language of languages) {
    await page.setViewportSize({ width: 390, height: 844 });
    const picker = page.locator('.app-header select');
    await expect(picker).toBeEnabled();
    await picker.selectOption(language.code);
    await expect(page.locator('html')).toHaveAttribute('lang', language.code);
    await expect(page.locator('html')).toHaveAttribute('dir', language.direction);
    await noOverflow(page);
    await page.reload();
    await expect(picker).toHaveValue(language.code);
    await expect(page.locator('html')).toHaveAttribute('lang', language.code);
    await page.locator('.header-actions > button').click();
    const settings = page.getByRole('dialog');
    await expect(settings).toBeVisible();
    await settings
      .locator('form')
      .first()
      .getByLabel(
        JSON.parse(
          readFileSync(new URL(`../src/locales/${language.code}.json`, import.meta.url), 'utf8'),
        )['模型 ID'],
        { exact: true },
      )
      .fill('unchanged-model-draft');
    await noOverflow(page);
    await page.setViewportSize({ width: 1024, height: 768 });
    await noOverflow(page);
    if (['ar', 'de', 'ja'].includes(language.code))
      await page.screenshot({
        path: `test-results/ui-settings-${language.code}.png`,
        fullPage: false,
      });
    await settings.locator('select').first().selectOption('en');
    await expect(
      settings.locator('form').first().getByLabel('Model ID', { exact: true }),
    ).toHaveValue('unchanged-model-draft');
    await settings.getByRole('button', { name: 'Close settings' }).click();
  }
});
