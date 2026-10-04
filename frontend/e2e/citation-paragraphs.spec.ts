import { test, expect } from '@playwright/test';
import { fileURLToPath } from 'node:url';

const paragraph =
  '这是按字绘制的中文资料，阅读时应该恢复完整段落。保留原始引用，才能准确返回资料中的位置。';

test('fragmented PDF chat cites a complete paragraph, deduplicates glyphs, jumps to the original page and survives reload', async ({
  page,
  request,
}) => {
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
  const title = `段落引用验收 ${Date.now()}`;
  const notebook = await (await request.post('/api/notebooks', { data: { title } })).json();
  await page.goto('/');
  await page.getByRole('button', { name: `打开 ${title}`, exact: true }).click();
  const [upload] = await Promise.all([
    page.waitForResponse('**/sources/upload'),
    page
      .getByLabel('上传资料')
      .setInputFiles(fileURLToPath(new URL('./fixtures/glyphs.pdf', import.meta.url))),
  ]);
  const imported = await upload.json();
  if (imported.duplicate) await page.getByRole('button', { name: '添加已有资料' }).click();
  const source = page.locator('.source-open').filter({ hasText: '连续阅读测试' });
  await expect(source).toBeEnabled({ timeout: 15000 });
  await source.click();
  const reader = page.getByRole('region', { name: '资料阅读器' });
  await reader.getByLabel('页码', { exact: true }).fill('2');
  await reader.getByRole('button', { name: '转到', exact: true }).click();
  await expect(reader.locator('.page-marker')).toHaveText('第 2 页');
  await reader.getByRole('button', { name: '就本页提问' }).click();
  await page.getByLabel('向资料提问').fill('请解释完整段落');
  await page.getByRole('button', { name: '发送问题' }).click();
  await expect(page.locator('.message-assistant')).toContainText(paragraph, { timeout: 15000 });
  await page.getByRole('button', { name: '查看引用 1', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '原文引用' });
  await expect(dialog.locator('blockquote')).toHaveCount(1);
  await expect(dialog.locator('blockquote')).toHaveText(paragraph);
  await expect(dialog).toContainText('第 2 页');
  await page.screenshot({ path: 'test-results/citation-complete-paragraph.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await dialog.locator('blockquote').evaluate((el) => el.scrollWidth <= el.clientWidth),
  ).toBeTruthy();
  await page.screenshot({ path: 'test-results/citation-complete-paragraph-mobile.png' });
  await dialog.getByRole('button', { name: '打开原文' }).click();
  await expect(reader.locator('.content-block p').first()).toHaveText(paragraph);
  await expect(reader.locator('.page-marker')).toHaveText('第 2 页');
  await expect(reader.locator('.citation-highlight').first()).toBeInViewport();
  const citationUrl = page.url();
  await page.reload();
  await expect(page).toHaveURL(citationUrl);
  await expect(reader.locator('.page-marker')).toHaveText('第 2 页');
  await expect(reader.locator('.citation-highlight').first()).toBeInViewport();
  await reader.getByRole('button', { name: '返回对话', exact: true }).click();
  await page.getByRole('button', { name: '查看引用 1', exact: true }).click();
  await expect(dialog.locator('blockquote')).toHaveText(paragraph);
  await request.delete(`/api/notebooks/${notebook.id}`);
});
