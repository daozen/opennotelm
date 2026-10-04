import { expect, test } from '@playwright/test';
import { fileURLToPath } from 'node:url';

test('Word images and scanned PDF can be read, cited and used in batch chapter Decks', async ({
  page,
  request,
}) => {
  test.setTimeout(120000);
  for (const role of ['language', 'embedding', 'image']) {
    const saved = await request.post('/api/settings/models/test', {
      data: {
        role,
        base_url: 'http://127.0.0.1:4301/v1',
        api_key: 'test-only-key',
        model_id: 'test-model',
      },
    });
    expect(saved.ok()).toBeTruthy();
  }
  const title = `图片与章节验收 ${Date.now()}`;
  const notebook = await (await request.post('/api/notebooks', { data: { title } })).json();
  try {
    await Promise.all([page.waitForResponse('**/api/settings/models'), page.goto('/')]);
    await page.getByRole('button', { name: '模型设置', exact: true }).click();
    const language = page
      .locator('.model-form')
      .filter({ has: page.getByRole('heading', { name: '语言模型', exact: true }) });
    await language.getByRole('button', { name: '测试图片识别', exact: true }).click();
    await expect(language.getByRole('status')).toContainText('图片识别能力测试通过');
    await page.getByRole('button', { name: '关闭设置' }).click();
    await page.getByRole('button', { name: `打开 ${title}`, exact: true }).click();
    let wordId = '';
    let scanId = '';
    for (const [filename, expected] of [
      ['illustrated.docx', '每日复盘帮助积累经验。'],
      ['scan-with-toc.pdf', 'Patient learning compounds over time.'],
    ]) {
      const uploaded = page.waitForResponse('**/sources/upload');
      await page
        .getByLabel('上传资料')
        .setInputFiles(fileURLToPath(new URL(`./fixtures/${filename}`, import.meta.url)));
      const result = await (await uploaded).json();
      const id = result.source.id;
      if (filename.endsWith('.docx')) wordId = id;
      else scanId = id;
      if (result.duplicate) await page.getByRole('button', { name: '添加已有资料' }).click();
      await expect
        .poll(async () => (await (await request.get(`/api/sources/${id}`)).json()).status)
        .toBe('indexed');
      const savedSource = await (await request.get(`/api/sources/${id}`)).json();
      await page.locator('.source-open').filter({ hasText: savedSource.title }).click();
      await expect(page.locator('.reader-format')).toHaveText(
        filename.endsWith('.docx') ? 'DOCX' : 'PDF',
      );
      await expect(page.locator('.reader-title h3')).toHaveText(savedSource.title);
      await expect(page.getByLabel('目录 / 章节', { exact: true })).toBeEnabled();
      await page.getByLabel('目录 / 章节', { exact: true }).selectOption({ label: '整份资料' });
      await expect(page.locator('.reader-content')).toContainText(expected);
      await expect(page.locator('.source-image img').first()).toBeVisible();
      await page.locator('.source-image img').first().scrollIntoViewIfNeeded();
      await expect
        .poll(() =>
          page
            .locator('.source-image img')
            .first()
            .evaluate((img) => (img as HTMLImageElement).naturalWidth),
        )
        .toBeGreaterThan(0);
      await expect(page.locator('.source-image').first()).toContainText('请结合原图核对');
      await page
        .locator('.source-image')
        .first()
        .screenshot({ path: `test-results/${filename}-reader.png` });
    }
    await page.getByRole('button', { name: '生成 Visual Deck', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: '生成 Visual Deck' });
    await dialog.getByLabel('Deck 内容范围').selectOption(`source:${scanId}`);
    await dialog.getByRole('checkbox', { name: '只使用所选章节' }).check();
    await expect(dialog.getByRole('button', { name: '开始生成', exact: true })).toBeDisabled();
    await dialog.getByRole('button', { name: '选择全部', exact: true }).click();
    await expect(dialog.getByRole('checkbox', { name: /章节 · Chapter/ })).toHaveCount(2);
    await dialog.getByRole('button', { name: '清空章节选择', exact: true }).click();
    await expect(dialog.getByRole('button', { name: '开始生成', exact: true })).toBeDisabled();
    await dialog.getByLabel('Deck 内容范围').selectOption(`source:${wordId}`);
    await dialog.getByRole('checkbox', { name: '只使用所选章节' }).check();
    await dialog.getByRole('checkbox', { name: '章节 · 第二章 练习', exact: true }).check();
    await dialog.getByRole('radio', { name: '10 页', exact: true }).check();
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBeTruthy();
    const checkbox = await dialog
      .getByRole('checkbox', { name: '章节 · 第二章 练习', exact: true })
      .boundingBox();
    const label = await dialog.getByText('第二章 练习', { exact: true }).boundingBox();
    expect(checkbox!.x).toBeLessThan(label!.x);
    expect(Math.abs(checkbox!.y - label!.y)).toBeLessThan(10);
    await page.screenshot({ path: 'test-results/chapter-selection-mobile.png' });
    await page.setViewportSize({ width: 1440, height: 1000 });
    const create = page.waitForResponse(
      (res) => res.request().method() === 'POST' && res.url().endsWith('/decks'),
    );
    await dialog.getByRole('button', { name: '开始生成', exact: true }).click();
    const created = await (await create).json();
    await expect(page.getByRole('link', { name: '下载 PDF · 10 页', exact: true })).toBeVisible({
      timeout: 60000,
    });
    const deck = await (await request.get(`/api/decks/${created.id}`)).json();
    expect(deck.source_scope.kind).toBe('nodes');
    expect(deck.source_scope.node_ids).toHaveLength(1);
    const blocks = await (await request.get(`/api/sources/${wordId}/blocks`)).json();
    const used = blocks.filter((b: { id: string }) =>
      deck.generation_metadata.block_ids.includes(b.id),
    );
    expect(used.some((b: { text: string }) => b.text.includes('每日复盘'))).toBeTruthy();
    expect(used.some((b: { text: string }) => b.text.includes('长期复利'))).toBeFalsy();
    await page.getByRole('button', { name: '原文引用 1', exact: true }).click();
    await expect(page.getByRole('dialog', { name: '原文引用' })).toContainText('第二章');
    await page.getByRole('button', { name: '关闭引用' }).click();
    await page.reload();
    await expect(page.getByRole('link', { name: '下载 PDF · 10 页', exact: true })).toBeVisible();
  } finally {
    await request.delete(`/api/notebooks/${notebook.id}`);
  }
});
