import { test, expect } from '@playwright/test';
import { fileURLToPath } from 'node:url';

test('PDF, Markdown and TXT reader with empty PDF failure', async ({ page, request }) => {
  const title = `多格式阅读验收 ${Date.now()}`;
  const response = await request.post('/api/notebooks', { data: { title } });
  const notebook = await response.json();
  await Promise.all([page.waitForResponse('**/api/settings/models'), page.goto('/')]);
  if (await page.getByRole('dialog').isVisible())
    await page.getByRole('button', { name: '关闭设置' }).click();
  await page.getByRole('button', { name: `打开 ${title}`, exact: true }).click();
  for (const [file, title, expected] of [
    ['notes.md', 'Learning', 'Safe content.'],
    ['notes.txt', 'notes', 'Practice daily.'],
    ['text.pdf', 'Patient learning', 'Page 1: Small improvements accumulate over time.'],
  ]) {
    const [uploaded] = await Promise.all([
      page.waitForResponse('**/sources/upload'),
      page
        .getByLabel('上传资料')
        .setInputFiles(fileURLToPath(new URL(`./fixtures/${file}`, import.meta.url))),
    ]);
    if ((await uploaded.json()).duplicate)
      await page.getByRole('button', { name: '添加已有资料' }).click();
    const source = page.locator('.source-open').filter({ hasText: title });
    await expect(source).toBeEnabled({ timeout: 10000 });
    await source.click();
    await expect(page.getByText(expected, { exact: true })).toBeVisible();
    await expect(page.locator('.reader script, .reader iframe, .reader img')).toHaveCount(0);
  }
  await expect(page.locator('.reader-content .page-marker').first()).toBeVisible();
  await expect(page.locator('.reader-content .page-marker').first()).toHaveText('第 1 页');
  const chapter = page.getByLabel('目录 / 章节', { exact: true });
  const options = await chapter.locator('option').evaluateAll((options) =>
    options.map((option) => ({
      text: option.textContent?.trim(),
      value: (option as HTMLOptionElement).value,
    })),
  );
  expect(options.map((option) => option.text)).toEqual(['整份资料', '1. Time', '2. Practice']);
  await expect(
    page.locator('.reading-turns-top').getByRole('button', { name: '上一章' }),
  ).toBeDisabled();
  await page.locator('.reading-turns-bottom').getByRole('button', { name: '下一章' }).click();
  await expect(
    page.getByText('Page 2: Small improvements accumulate over time.', { exact: true }),
  ).toBeVisible();
  await expect(chapter).toHaveValue(options.find((o) => o.text === '2. Practice')!.value);
  await expect(
    page.locator('.reading-turns-top').getByRole('button', { name: '下一章' }),
  ).toBeDisabled();
  await expect(page.locator('.reader-content')).toBeFocused();
  await page.getByLabel('页码', { exact: true }).fill('1');
  await page.getByRole('button', { name: '转到', exact: true }).click();
  await expect(chapter).toHaveValue(options.find((o) => o.text === '1. Time')!.value);
  await expect(page.getByRole('button', { name: '就本页提问', exact: true })).toBeEnabled();
  await expect(
    page.getByText('Page 1: Small improvements accumulate over time.', { exact: true }),
  ).toBeVisible();
  await expect(page.locator('.reader-content')).toBeFocused();
  await expect(page.locator('.reader-content .content-block').first()).toBeInViewport();
  await page.screenshot({ path: 'test-results/pdf-reader.png' });
  const [scanned] = await Promise.all([
    page.waitForResponse('**/sources/upload'),
    page
      .getByLabel('上传资料')
      .setInputFiles(fileURLToPath(new URL('./fixtures/scanned.pdf', import.meta.url))),
  ]);
  if ((await scanned.json()).duplicate)
    await page.getByRole('button', { name: '添加已有资料' }).click();
  const failed = page.locator('.source-item').filter({ hasText: 'scanned' });
  if ((await scanned.json()).duplicate)
    await failed.getByRole('button', { name: '重试', exact: true }).click();
  await expect(failed.getByText(/没有可读文字或页面图片/)).toBeVisible({ timeout: 10000 });
  await expect(failed.getByRole('button', { name: '重试', exact: true })).toBeEnabled();
  await request.delete(`/api/notebooks/${notebook.id}`);
});
