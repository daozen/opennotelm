import { test, expect } from '@playwright/test';
import { fileURLToPath } from 'node:url';

test('glyph-level PDF reads as paragraphs with adjustable size and expanded width', async ({
  page,
  request,
}) => {
  const notebook = await (
    await request.post('/api/notebooks', { data: { title: '连续阅读验收' } })
  ).json();
  await page.goto('/');
  await page.getByRole('button', { name: '打开 连续阅读验收', exact: true }).click();
  const uploaded = page.waitForResponse('**/sources/upload');
  await page
    .getByLabel('上传资料')
    .setInputFiles(fileURLToPath(new URL('./fixtures/glyphs.pdf', import.meta.url)));
  const result = await (await uploaded).json();
  if (result.duplicate) await page.getByRole('button', { name: '添加已有资料' }).click();
  await expect(page.locator('.source-open').filter({ hasText: '连续阅读测试' })).toBeEnabled();
  await page.locator('.source-open').filter({ hasText: '连续阅读测试' }).click();
  const reader = page.getByRole('region', { name: '资料阅读器' });
  await expect(reader.locator('.content-block p').first()).toContainText(
    '这是按字绘制的中文资料，阅读时应该恢复完整段落。',
  );
  await expect(reader.getByRole('heading', { name: '第1页连续阅读' })).toBeVisible();
  await expect(reader.locator('.content-block')).toHaveCount(3);
  const originalWidth = (await reader.locator('.reader-content').boundingBox())!.width;
  await reader.getByRole('button', { name: '展开阅读' }).click();
  expect((await reader.locator('.reader-content').boundingBox())!.width).toBeGreaterThan(
    originalWidth,
  );
  await reader.getByLabel('正文大小').selectOption('20');
  await expect(reader.locator('.content-block p').first()).toHaveCSS('font-size', '20px');
  await expect(reader.getByRole('button', { name: '收起阅读' })).toBeVisible();
  await expect(reader.getByLabel('目录 / 章节')).toHaveCount(0);
  await reader
    .locator('.reading-turns-top')
    .getByRole('button', { name: '下一页', exact: true })
    .click();
  await expect(reader.getByRole('heading', { name: '第2页连续阅读' })).toBeVisible();
  await expect(reader.locator('.page-marker')).toHaveCount(1);
  await expect(reader.locator('.page-marker')).toHaveText('第 2 页');
  await expect(reader.locator('.content-block p').first()).toBeInViewport();
  await expect(
    reader.locator('.reading-turns-top').getByRole('button', { name: '下一页' }),
  ).toBeDisabled();
  const secondPageUrl = page.url();
  await page.reload();
  await expect(page).toHaveURL(secondPageUrl);
  await expect(reader.getByRole('heading', { name: '第2页连续阅读' })).toBeVisible();
  await reader.locator('.reading-turns-bottom').getByRole('button', { name: '上一页' }).click();
  await expect(reader.getByRole('heading', { name: '第1页连续阅读' })).toBeVisible();
  await expect(
    reader.locator('.reading-turns-top').getByRole('button', { name: '上一页' }),
  ).toBeDisabled();
  await reader.getByLabel('页码', { exact: true }).fill('2');
  await reader.getByRole('button', { name: '转到', exact: true }).click();
  await expect(reader.getByRole('heading', { name: '第2页连续阅读' })).toBeVisible();
  await reader.getByRole('button', { name: '展开阅读' }).click();
  await page.screenshot({ path: 'test-results/reflow-reader-expanded.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await reader.locator('.reader-content').evaluate((el) => el.scrollWidth <= el.clientWidth),
  ).toBeTruthy();
  await page.screenshot({ path: 'test-results/reflow-reader-mobile.png', fullPage: true });
  await request.delete(`/api/notebooks/${notebook.id}`);
});
