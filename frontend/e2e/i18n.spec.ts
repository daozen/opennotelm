import { test, expect } from '@playwright/test';
import { fileURLToPath } from 'node:url';

// A failed language test must not change the starting locale of later flows.
test.afterEach(async ({ request }) => {
  await request.put('/api/settings/preferences', { data: { ui_language: 'zh-CN' } });
});

test('English interface persists across reloads, preserves drafts and source content, and supports knowledge, chat, citations and Deck', async ({
  page,
  request,
}) => {
  test.setTimeout(120000);
  const previous = await (await request.get('/api/settings/preferences')).json();
  const title = `多语言验收 ${Date.now()}`;
  const notebook = await (await request.post('/api/notebooks', { data: { title } })).json();
  try {
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
    await request.put('/api/settings/preferences', {
      data: { ui_language: 'zh-CN', telemetry_enabled: true },
    });
    await page.goto('/');
    await expect(page.getByLabel('界面语言')).toBeEnabled();
    await page.getByLabel('界面语言').selectOption('en');
    await expect(page.getByRole('button', { name: 'Create notebook', exact: true })).toBeVisible();
    expect(await (await request.get('/api/settings/preferences')).json()).toEqual({
      ui_language: 'en',
      telemetry_enabled: true,
    });
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await page.getByRole('button', { name: 'Model settings' }).click();
    const setup = page.getByRole('dialog', { name: 'Connect your AI models' });
    await expect(setup.getByText('Embedding model', { exact: true })).toBeVisible();
    await expect(setup.getByText('Privacy and diagnostics', { exact: true })).toBeVisible();
    await setup.getByRole('button', { name: 'Close settings' }).click();
    await page.getByRole('button', { name: `Open ${title}`, exact: true }).click();
    const upload = async (name: string) => {
      const [response] = await Promise.all([
        page.waitForResponse('**/sources/upload'),
        page
          .getByLabel('Upload sources')
          .setInputFiles(fileURLToPath(new URL(`./fixtures/${name}`, import.meta.url))),
      ]);
      if ((await response.json()).duplicate)
        await page.getByRole('button', { name: 'Add existing source' }).click();
    };
    await upload('book.epub');
    const source = page.locator('.source-open').filter({ hasText: '长期思考' });
    await expect(source).toBeEnabled({ timeout: 15000 });
    await source.click();
    const reader = page.getByRole('region', { name: 'Source reader' });
    await expect(reader.locator('.reader-content')).toContainText('耐心的价值');
    await expect(reader.getByRole('button', { name: 'Ask about this chapter' })).toBeEnabled();
    await reader
      .locator('.reading-turns-bottom')
      .getByRole('button', { name: 'Next chapter' })
      .click();
    await expect(reader.locator('.reader-content')).toContainText(
      '长期复利最大的优势来自时间跨度。',
    );
    await expect(
      reader.locator('.reading-turns-top').getByRole('button', { name: 'Next chapter' }),
    ).toBeDisabled();
    await reader
      .locator('.reading-turns-top')
      .getByRole('button', { name: 'Previous chapter' })
      .click();
    await expect(reader.locator('.reader-content')).toContainText('耐心的价值');
    await reader
      .getByRole('button', { name: 'Create knowledge from this chapter', exact: true })
      .click();
    let knowledge = page.getByRole('region', { name: 'Knowledge page' });
    await expect(knowledge.getByRole('button', { name: 'Edit', exact: true })).toBeEnabled({
      timeout: 15000,
    });
    await knowledge.getByRole('button', { name: 'Edit', exact: true }).click();
    await page.getByLabel('Knowledge page title', { exact: true }).fill('原文与草稿保持不变');
    const body = page.getByLabel('Knowledge page content');
    const draft = (await body.inputValue()) + '\n\n我的未保存笔记。';
    await body.fill(draft);
    await page.getByLabel('Interface language').selectOption('zh-CN');
    await expect(page.getByLabel('知识页正文')).toHaveValue(draft);
    await expect(page.getByLabel('知识页标题', { exact: true })).toHaveValue('原文与草稿保持不变');
    await page.getByLabel('界面语言').selectOption('en');
    await expect(page.getByLabel('Knowledge page content')).toHaveValue(draft);
    knowledge = page.getByRole('region', { name: 'Knowledge page' });
    await knowledge.getByRole('button', { name: 'Save knowledge page', exact: true }).click();
    await knowledge.getByRole('button', { name: 'View citation 1', exact: true }).first().click();
    await expect(page.getByRole('dialog', { name: 'Source citation' })).toContainText('长期思考');
    await page.getByRole('button', { name: 'Close citation' }).click();
    await page.getByRole('button', { name: 'Back to chat', exact: true }).click();
    await page.getByLabel('Ask your sources').fill('耐心的价值是什么？');
    await page.getByRole('button', { name: 'Send question' }).click();
    await expect(page.getByRole('button', { name: 'Save as knowledge page' })).toBeVisible({
      timeout: 15000,
    });
    await page
      .getByRole('navigation', { name: 'Notebook content' })
      .getByRole('button', { name: 'Sources', exact: true })
      .click();
    await upload('scanned.pdf');
    await page
      .locator('.source-item')
      .filter({ hasText: 'scanned' })
      .getByRole('button', { name: 'Retry', exact: true })
      .click();
    await expect(page.locator('.source-item').filter({ hasText: 'scanned' })).toContainText(
      'no readable text or page images',
      { timeout: 15000 },
    );
    await upload('notes.md');
    await expect(page.locator('.source-open').filter({ hasText: 'Learning' })).toBeEnabled({
      timeout: 15000,
    });
    await page.getByRole('button', { name: 'Generate Visual Deck', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Generate Visual Deck' });
    const options = await dialog
      .getByLabel('Deck content scope')
      .locator('option')
      .allTextContents();
    const sourceOption = options.find((label) => label === 'Source · Learning')!;
    expect(sourceOption).toBeTruthy();
    await dialog.getByLabel('Deck content scope').selectOption({ label: sourceOption });
    await expect(dialog.getByLabel('Deck language')).toHaveValue('en');
    await dialog.getByRole('radio', { name: '10 slides', exact: true }).check();
    const create = page.waitForRequest(
      (req) => req.method() === 'POST' && req.url().endsWith('/decks'),
    );
    await dialog.getByRole('button', { name: 'Start generating' }).click();
    expect((await create).postDataJSON().language).toBe('en');
    const deck = page.getByRole('region', { name: 'Visual Deck', exact: true });
    await expect(
      deck.getByRole('link', { name: 'Download PDF · Pages: 10', exact: true }),
    ).toBeVisible({ timeout: 60000 });
    await deck.getByRole('button', { name: 'Edit text', exact: true }).click();
    const edit = page.getByRole('dialog', { name: 'Edit slide text' });
    const firstField = edit.locator('textarea').first();
    await firstField.fill('保留中文修改草稿');
    await expect(edit.getByRole('button', { name: 'Save and update slide' })).toBeEnabled();
    page.once('dialog', (dialog) => void dialog.accept());
    await edit.getByRole('button', { name: 'Close slide editor' }).click();
    await page.screenshot({ path: 'test-results/interface-en-desktop.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByLabel('Interface language')).toBeVisible();
    const header = await page.locator('.app-header').boundingBox();
    const settingsButton = await page.getByRole('button', { name: 'Model settings' }).boundingBox();
    expect(settingsButton!.y + settingsButton!.height).toBeLessThanOrEqual(
      header!.y + header!.height,
    );
    expect(
      await page.locator('.app-header').evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBeTruthy();

    await page.screenshot({ path: 'test-results/interface-en-mobile.png', fullPage: true });
    await page.getByLabel('Interface language').selectOption('zh-CN');
    await expect(deck.getByRole('button', { name: '编辑文字' })).toBeVisible();
    expect((await (await request.get('/api/settings/preferences')).json()).telemetry_enabled).toBe(
      true,
    );
  } finally {
    await request.put('/api/settings/preferences', {
      data: { ui_language: 'zh-CN', telemetry_enabled: previous.telemetry_enabled },
    });
    await request.delete(`/api/notebooks/${notebook.id}`);
  }
});
