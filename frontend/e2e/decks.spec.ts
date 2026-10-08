import { test, expect } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import { writeFile } from 'node:fs/promises';

test('merged Deck creation preserves exact length, semantic slides, citations and restart persistence', async ({
  page,
  request,
}) => {
  test.setTimeout(90000);
  await request.post('/api/settings/models/test', {
    data: {
      role: 'image',
      base_url: 'http://127.0.0.1:4301/v1',
      api_key: 'test-only-key',
      model_id: 'test-model',
    },
  });
  expect(
    (
      await request.post('/api/settings/models/test', {
        data: {
          role: 'language',
          base_url: 'http://127.0.0.1:4301/v1',
          api_key: 'test-only-key',
          model_id: 'test-model',
        },
      })
    ).ok(),
  ).toBeTruthy();
  const title = `Deck 验收 ${Date.now()}`;
  const notebook = await (await request.post('/api/notebooks', { data: { title } })).json();
  await Promise.all([page.waitForResponse('**/api/settings/models'), page.goto('/')]);
  if (await page.getByRole('dialog').isVisible())
    await page.getByRole('button', { name: '关闭设置' }).click();
  await page.getByRole('button', { name: `打开 ${title}`, exact: true }).click();
  const [uploaded] = await Promise.all([
    page.waitForResponse('**/sources/upload'),
    page
      .getByLabel('上传资料')
      .setInputFiles(fileURLToPath(new URL('./fixtures/notes.md', import.meta.url))),
  ]);
  if ((await uploaded.json()).duplicate)
    await page.getByRole('button', { name: '添加已有资料' }).click();
  await expect(page.locator('.source-open').filter({ hasText: 'Learning' })).toBeEnabled({
    timeout: 15000,
  });
  await page.getByRole('button', { name: '生成 Visual Deck', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '生成 Visual Deck' });
  await expect(
    dialog.getByRole('group', { name: '页数', exact: true }).getByRole('radio'),
  ).toHaveCount(3);
  await expect(dialog.getByRole('radio', { name: '合并生成一份 Deck', exact: true })).toBeChecked();
  await expect(dialog.getByLabel('Deck 语言')).toBeVisible();
  await expect(dialog.getByLabel('Deck 内容范围')).toBeVisible();
  await dialog.getByRole('radio', { name: '10 页', exact: true }).check();
  await dialog.getByLabel('Deck 补充说明').fill('请帮助初学者理解学习与时间的关系。');
  await dialog.getByRole('button', { name: '开始生成', exact: true }).click();
  const deck = page.getByRole('region', { name: 'Visual Deck', exact: true });
  await expect(deck.getByText('10 / 10 页内容已保存', { exact: true })).toBeVisible({
    timeout: 20000,
  });
  await expect(deck.getByText('10 / 10 页预览已保存', { exact: true })).toBeVisible({
    timeout: 60000,
  });
  const pdfLink = deck.getByRole('link', { name: '下载 PDF · 10 页' });
  await expect(pdfLink).toBeVisible({ timeout: 15000 });
  const downloaded = page.waitForEvent('download');
  await pdfLink.click();
  await (await downloaded).saveAs('test-results/deck-final.pdf');
  const savedList = await (await request.get(`/api/notebooks/${notebook.id}/decks`)).json();
  const savedDeck = await (await request.get(`/api/decks/${savedList[0].id}`)).json();
  for (const slide of savedDeck.slides) {
    const image = await request.get(slide.render.image_url);
    await writeFile(`test-results/deck-page-${slide.ordinal + 1}.png`, await image.body());
  }
  await expect(deck.getByRole('navigation', { name: 'Deck 页面' }).getByRole('button')).toHaveCount(
    10,
  );
  await deck.getByRole('button', { name: '原文引用 1', exact: true }).click();
  await expect(page.getByRole('dialog', { name: '原文引用' })).toContainText(
    'Small improvements accumulate over time.',
  );
  await page.getByRole('button', { name: '关闭引用' }).click();
  await deck.getByRole('navigation', { name: 'Deck 页面' }).getByRole('button').nth(1).click();
  await expect(deck.locator('.rendered-page')).toBeVisible();
  await expect(deck.getByText('图片 1 / 1 已生成')).toBeVisible();
  expect(savedDeck.render_mode).toBe('generated_page');
  expect(
    savedDeck.slides.every(
      (s: { render: { text_layer: unknown[] } }) => s.render.text_layer.length === 0,
    ),
  ).toBeTruthy();
  await expect(deck.getByRole('link', { name: '预览 PDF' })).toBeVisible();
  await deck.getByText('查看页面文字稿', { exact: true }).click();
  await expect(deck.locator('.semantic-comparison')).toBeVisible();
  await deck.getByText('查看页面文字稿', { exact: true }).click();
  await page.screenshot({ path: 'test-results/deck-content.png', fullPage: true });
  const deckUrl = page.url();
  await page.reload();
  await expect(page).toHaveURL(deckUrl);
  await expect(deck.getByText('10 / 10 页内容已保存', { exact: true })).toBeVisible();
  await page.locator('.source-open').filter({ hasText: 'Learning' }).click();
  await expect(page.getByRole('region', { name: '资料阅读器' })).toBeVisible();
  await request.delete(`/api/notebooks/${notebook.id}`);
});

test('a failed image can retry and continue without it while preserving completed pages', async ({
  page,
  request,
}) => {
  test.setTimeout(90000);
  for (const role of ['language', 'image']) {
    const saved = await request.post('/api/settings/models/test', {
      data: {
        role,
        base_url: 'http://127.0.0.1:4301/v1',
        api_key: 'test-only-key',
        model_id: role === 'image' ? 'image-fails-after-probe' : 'test-model',
      },
    });
    expect(saved.ok()).toBeTruthy();
  }
  const title = `图片失败恢复 ${Date.now()}`;
  const notebook = await (await request.post('/api/notebooks', { data: { title } })).json();
  const uploaded = await (
    await request.post(`/api/notebooks/${notebook.id}/sources/upload`, {
      multipart: {
        file: {
          name: 'image-recovery.md',
          mimeType: 'text/markdown',
          buffer: Buffer.from(
            `# Recovery\n\nSmall improvements accumulate over time.\n\nDaily reflection helps learning.\n\n${title}`,
          ),
        },
      },
    })
  ).json();
  await expect
    .poll(async () => (await (await request.get(`/api/jobs/${uploaded.job.id}`)).json()).status)
    .toBe('completed');
  const created = await (
    await request.post(`/api/notebooks/${notebook.id}/decks`, {
      data: { slide_count: 10, scope: { kind: 'selected' }, render_mode: 'native' },
    })
  ).json();
  await page.goto('/');
  await page.getByRole('button', { name: `打开 ${title}`, exact: true }).click();
  await page.locator('.artifact-grid .deck-open').click();
  const deck = page.getByRole('region', { name: 'Visual Deck', exact: true });
  await expect(deck.getByRole('button', { name: '重试未完成页面' })).toBeEnabled({
    timeout: 60000,
  });
  const before = await (await request.get(`/api/decks/${created.id}`)).json();
  expect(before.status).toBe('partial');
  expect(before.slides.filter((s: { render?: unknown }) => s.render)).toHaveLength(9);
  await deck.getByRole('navigation', { name: 'Deck 页面' }).getByRole('button').nth(1).click();
  await expect(deck.getByText('图片 0 / 1 已生成')).toBeVisible();
  await deck.getByRole('button', { name: '重试本页', exact: true }).click();
  await expect(deck.getByRole('button', { name: '不使用失败的图片继续' })).toBeEnabled({
    timeout: 15000,
  });
  await page.screenshot({ path: 'test-results/deck-image-failure.png', fullPage: true });
  await deck.getByRole('button', { name: '不使用失败的图片继续' }).click();
  await expect(deck.getByText('10 / 10 页预览已保存', { exact: true })).toBeVisible({
    timeout: 20000,
  });
  await expect(deck.getByText('已选择不使用失败的图片继续。')).toBeVisible();
  const after = await (await request.get(`/api/decks/${created.id}`)).json();
  await expect(deck.getByRole('link', { name: '下载 PDF · 10 页' })).toBeVisible({
    timeout: 15000,
  });
  expect((await (await request.get(`/api/decks/${created.id}`)).json()).status).toBe('ready');
  for (let index = 0; index < 10; index++) {
    if (index !== 1) expect(after.slides[index]).toEqual(before.slides[index]);
  }
  await request.delete(`/api/notebooks/${notebook.id}`);
  await request.post('/api/settings/models/test', {
    data: {
      role: 'image',
      base_url: 'http://127.0.0.1:4301/v1',
      api_key: 'test-only-key',
      model_id: 'test-model',
    },
  });
});
