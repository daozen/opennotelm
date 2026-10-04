import { test, expect } from '@playwright/test';
import { fileURLToPath } from 'node:url';

test('EPUB import, chapter reader, selection, duplicate reuse and safe content', async ({
  page,
  request,
}) => {
  const response = await request.post('/api/notebooks', { data: { title: 'EPUB 阅读验收' } });
  const notebook = await response.json();
  await Promise.all([page.waitForResponse('**/api/settings/models'), page.goto('/')]);
  if (await page.getByRole('dialog').isVisible())
    await page.getByRole('button', { name: '关闭设置' }).click();
  await page.getByRole('button', { name: '打开 EPUB 阅读验收', exact: true }).click();
  const [uploaded] = await Promise.all([
    page.waitForResponse('**/sources/upload'),
    page
      .getByLabel('上传资料')
      .setInputFiles(fileURLToPath(new URL('./fixtures/book.epub', import.meta.url))),
  ]);
  if ((await uploaded.json()).duplicate)
    await page.getByRole('button', { name: '添加已有资料' }).click();
  const source = page.locator('.source-open').filter({ hasText: '长期思考' });
  await expect(source).toBeEnabled({ timeout: 10000 });
  await source.click();
  await expect(
    page.getByText('耐心意味着允许小的进步经过长期积累。', { exact: true }),
  ).toBeVisible();
  await page
    .locator('.reading-turns-bottom')
    .getByRole('button', { name: '下一章', exact: true })
    .click();
  await expect(page.getByText('长期复利最大的优势来自时间跨度。', { exact: true })).toBeVisible();
  await expect(page.locator('.reader iframe, .reader img, .reader script')).toHaveCount(0);
  await expect(page.getByText('EXFILTRATE_SECRET()')).not.toBeVisible();
  await Promise.all([
    page.waitForResponse(
      (response) => response.request().method() === 'PATCH' && response.url().includes('/sources/'),
    ),
    page.getByRole('checkbox', { name: '选择 长期思考', exact: true }).uncheck(),
  ]);
  await page.screenshot({ path: 'test-results/epub-reader.png', fullPage: true });
  const readingUrl = page.url();
  await page.reload();
  await expect(page).toHaveURL(readingUrl);
  await expect(page.getByRole('region', { name: '资料阅读器' })).toBeVisible();
  await expect(
    page.getByRole('checkbox', { name: '选择 长期思考', exact: true }),
  ).not.toBeChecked();
  await page
    .getByLabel('上传资料')
    .setInputFiles(fileURLToPath(new URL('./fixtures/book.epub', import.meta.url)));
  await expect(page.getByRole('heading', { name: '资料已存在', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '添加已有资料' }).click();
  await expect(page.getByRole('heading', { name: '资料已存在', exact: true })).not.toBeVisible();
  await expect(page.locator('.source-item')).toHaveCount(1);
  await request.delete(`/api/notebooks/${notebook.id}`);
});
