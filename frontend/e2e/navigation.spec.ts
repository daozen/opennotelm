import { test, expect, type APIRequestContext } from '@playwright/test';
import { readFileSync } from 'node:fs';

async function prepare(request: APIRequestContext, title: string, filename: string) {
  for (const role of ['language', 'embedding', 'image']) {
    expect(
      (
        await request.post('/api/settings/models/test', {
          data: {
            role,
            base_url: 'http://127.0.0.1:4301/v1',
            model_id: 'test-model',
            api_key: 'test-only-key',
          },
        })
      ).ok(),
    ).toBeTruthy();
  }
  const notebook = await (await request.post('/api/notebooks', { data: { title } })).json();
  const upload = await (
    await request.post(`/api/notebooks/${notebook.id}/sources/upload`, {
      multipart: {
        file: {
          name: filename,
          mimeType: 'application/octet-stream',
          buffer: readFileSync(new URL(`./fixtures/${filename}`, import.meta.url)),
        },
      },
    })
  ).json();
  if (upload.duplicate)
    expect(
      (await request.post(`/api/notebooks/${notebook.id}/sources/${upload.source.id}`)).ok(),
    ).toBeTruthy();
  await expect
    .poll(async () => (await (await request.get(`/api/sources/${upload.source.id}`)).json()).status)
    .toBe('indexed');
  return { notebook, source: await (await request.get(`/api/sources/${upload.source.id}`)).json() };
}

test('notebook and PDF chapter deep links survive reload, new tabs and history; chat scope and missing links are explicit', async ({
  page,
  request,
  context,
}) => {
  const title = `导航位置 ${Date.now()}`;
  const { notebook, source } = await prepare(request, title, 'glyphs.pdf');
  try {
    await page.goto('/');
    await expect(page.locator('.card-open').filter({ hasText: title })).toHaveAttribute(
      'href',
      `/notebooks/${notebook.id}`,
    );
    await page.getByRole('button', { name: `打开 ${title}`, exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/notebooks/${notebook.id}$`));
    await page.reload();
    await expect(page.locator('.workspace-top h2')).toHaveText(title);
    await page.locator('.source-open').filter({ hasText: source.title }).click();
    const reader = page.getByRole('region', { name: '资料阅读器' });
    const pageNumber = reader.getByLabel('页码', { exact: true });
    await expect(pageNumber).toHaveValue('1');
    await pageNumber.fill('2');
    await reader.getByRole('button', { name: '转到', exact: true }).click();
    await expect(reader.locator('.page-marker')).toHaveText('第 2 页');
    const chapterUrl = page.url();
    expect(chapterUrl).toContain(`/sources/${source.id}?node=`);
    await page.reload();
    await expect(reader.locator('.page-marker')).toHaveText('第 2 页');
    await page.goBack();
    await expect(reader.locator('.page-marker')).toHaveText('第 1 页');
    await page.goForward();
    await expect(reader.locator('.page-marker')).toHaveText('第 2 页');
    const shared = await context.newPage();
    await shared.goto(chapterUrl);
    await expect(
      shared.getByRole('region', { name: '资料阅读器' }).locator('.page-marker'),
    ).toHaveText('第 2 页');
    await shared.close();
    await reader.getByRole('button', { name: '就本页提问', exact: true }).click();
    expect(new URL(page.url()).searchParams.get('scopeSource')).toBe(source.id);
    expect(new URL(page.url()).searchParams.get('scopeNode')).toBeTruthy();
    await page.reload();
    await expect(page.locator('.active-scope')).toContainText('第 2 页');
    const question = page.getByLabel('向资料提问');
    await question.fill('尚未发送的问题');
    const scopedUrl = page.url();
    const rejected = page.waitForEvent('dialog').then((dialog) => dialog.dismiss());
    await page.evaluate(() => window.history.back());
    await rejected;
    await expect(page).toHaveURL(scopedUrl);
    await expect(question).toHaveValue('尚未发送的问题');
    await question.fill('');
    await page.evaluate(() => window.history.back());
    await expect(reader.locator('.page-marker')).toHaveText('第 2 页');
    await page.goto(`/notebooks/${notebook.id}/sources/missing-source`);
    await expect(page.locator('.chat-panel [role=alert]')).toBeVisible();
    await page.getByRole('button', { name: '返回对话', exact: true }).click();
    await expect(page.getByLabel('向资料提问')).toBeVisible();
    const scan = await (
      await request.post(`/api/notebooks/${notebook.id}/sources/upload`, {
        multipart: {
          file: {
            name: 'scanned.pdf',
            mimeType: 'application/pdf',
            buffer: readFileSync(new URL('./fixtures/scanned.pdf', import.meta.url)),
          },
        },
      })
    ).json();
    await expect
      .poll(async () => (await (await request.get(`/api/sources/${scan.source.id}`)).json()).status)
      .toBe('failed');
    await page.goto(`/notebooks/${notebook.id}/sources/${scan.source.id}`);
    await expect(page.locator('.chat-panel [role=alert]')).toContainText('没有可读文字或页面图片');
    await page.getByRole('button', { name: '返回对话', exact: true }).click();
    await page.goto('/notebooks/deleted-notebook');
    await expect(page.getByRole('alert')).toContainText('此页面不存在');
    await page.getByRole('button', { name: '返回笔记本列表' }).click();
    await expect(page).toHaveURL(/\/$/);
    await page.goto('/unknown-page');
    await expect(page.getByRole('alert')).toContainText('此页面不存在');
  } finally {
    await request.delete(`/api/notebooks/${notebook.id}`);
  }
});

test('knowledge and stable Deck page links restore; cancelled browser back preserves edits and accepted back leaves them', async ({
  page,
  request,
}) => {
  test.setTimeout(120000);
  const title = `内容导航 ${Date.now()}`;
  const { notebook, source } = await prepare(request, title, 'notes.md');
  try {
    await page.goto(`/notebooks/${notebook.id}/sources/${source.id}`);
    const reader = page.getByRole('region', { name: '资料阅读器' });
    await reader.getByRole('button', { name: '从本章节生成知识', exact: true }).click();
    const knowledge = page.getByRole('region', { name: '知识页' });
    await expect(knowledge.getByRole('button', { name: '编辑', exact: true })).toBeEnabled({
      timeout: 15000,
    });
    const knowledgeUrl = page.url();
    expect(knowledgeUrl).toContain('/knowledge/');
    await page.reload();
    await expect(knowledge.getByRole('button', { name: '编辑', exact: true })).toBeEnabled();
    await knowledge.getByRole('button', { name: '编辑', exact: true }).click();
    const body = page.getByLabel('知识页正文');
    const original = await body.inputValue();
    await body.fill(original + '\n\n不应意外丢失的草稿。');
    await page.getByRole('button', { name: '生成 Visual Deck', exact: true }).click();
    await expect(page.getByRole('dialog', { name: '生成 Visual Deck' })).toBeVisible();
    await page.getByRole('button', { name: '关闭 Deck 创建' }).click();
    await expect(body).toHaveValue(/不应意外丢失/);
    await page
      .getByRole('navigation', { name: '笔记本内容' })
      .getByRole('button', { name: '资料', exact: true })
      .click();
    await expect(body).toHaveValue(/不应意外丢失/);
    await page.goBack(); // only the sidebar tab changes
    await expect(page).toHaveURL(knowledgeUrl);
    await expect(body).toHaveValue(/不应意外丢失/);
    const cancelled = page.waitForEvent('dialog').then((dialog) => dialog.dismiss());
    await page.evaluate(() => window.history.back());
    await cancelled;
    await expect(page).toHaveURL(knowledgeUrl);
    await expect(body).toHaveValue(/不应意外丢失/);
    const accepted = page.waitForEvent('dialog').then((dialog) => dialog.accept());
    await page.evaluate(() => window.history.back());
    await accepted;
    await expect(reader).toBeVisible();
    await page.goForward();
    await expect(knowledge.locator('.knowledge-content')).not.toContainText('不应意外丢失');
    const created = await (
      await request.post(`/api/notebooks/${notebook.id}/decks`, {
        data: { slide_count: 10, render_mode: 'native' },
      })
    ).json();
    await page.goto(`/notebooks/${notebook.id}/decks/${created.id}`);
    const deck = page.getByRole('region', { name: 'Visual Deck', exact: true });
    await expect(deck.getByRole('link', { name: '下载 PDF · 10 页' })).toBeVisible({
      timeout: 60000,
    });
    const slides = deck.getByRole('navigation', { name: 'Deck 页面' }).getByRole('button');
    await slides.nth(1).click();
    const deckUrl = page.url();
    const slideId = new URL(deckUrl).searchParams.get('slide');
    expect(slideId).toBeTruthy();
    await page.reload();
    await expect(slides.nth(1)).toHaveClass(/active/);
    await expect(page).toHaveURL(deckUrl);
    await deck.getByRole('button', { name: '编辑文字', exact: true }).click();
    await page
      .getByRole('dialog', { name: '编辑本页文字' })
      .locator('textarea')
      .first()
      .fill('未保存的幻灯片');
    const rejected = page.waitForEvent('dialog').then((dialog) => dialog.dismiss());
    await page.evaluate(() => window.history.back());
    await rejected;
    await expect(page).toHaveURL(deckUrl);
    await expect(
      page.getByRole('dialog', { name: '编辑本页文字' }).locator('textarea').first(),
    ).toHaveValue('未保存的幻灯片');
    const allowed = page.waitForEvent('dialog').then((dialog) => dialog.accept());
    await page.evaluate(() => window.history.back());
    await allowed;
    await expect(page.getByRole('dialog', { name: '编辑本页文字' })).not.toBeVisible();
    await expect(slides.first()).toHaveClass(/active/);
    await page.goForward();
    await expect(slides.nth(1)).toHaveClass(/active/);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: 'test-results/navigation-mobile.png', fullPage: true });
  } finally {
    await request.delete(`/api/notebooks/${notebook.id}`);
  }
});
