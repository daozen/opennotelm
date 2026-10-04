import { test, expect } from '@playwright/test';
import { fileURLToPath } from 'node:url';

test('grounded chat, source citation preview, reader jump and unavailable originals', async ({
  page,
  request,
}) => {
  for (const role of ['language', 'embedding', 'image']) {
    const result = await request.post('/api/settings/models/test', {
      data: {
        role,
        base_url: 'http://127.0.0.1:4301/v1',
        api_key: 'test-only-key',
        model_id: 'test-model',
      },
    });
    expect(result.ok()).toBeTruthy();
  }
  const notebook = await (
    await request.post('/api/notebooks', { data: { title: '引用验收' } })
  ).json();
  await Promise.all([page.waitForResponse('**/api/settings/models'), page.goto('/')]);
  if (await page.getByRole('dialog').isVisible())
    await page.getByRole('button', { name: '关闭设置' }).click();
  await page.getByRole('button', { name: '打开 引用验收', exact: true }).click();
  const [uploaded] = await Promise.all([
    page.waitForResponse('**/sources/upload'),
    page
      .getByLabel('上传资料')
      .setInputFiles(fileURLToPath(new URL('./fixtures/book.epub', import.meta.url))),
  ]);
  const sourceResult = await uploaded.json();
  if (sourceResult.duplicate) await page.getByRole('button', { name: '添加已有资料' }).click();
  await expect(page.locator('.source-open').getByText('可用于问答', { exact: true })).toBeVisible({
    timeout: 15000,
  });
  await page.getByLabel('向资料提问').fill('长期复利的优势是什么？');
  await page.getByRole('button', { name: '发送问题' }).click();
  await expect(page.locator('.message-assistant')).toContainText(
    '长期复利最大的优势来自时间跨度。',
    { timeout: 15000 },
  );
  await page.getByRole('button', { name: '查看引用 1', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '原文引用' });
  await expect(dialog.getByRole('heading', { name: '长期思考' })).toBeVisible();
  await expect(dialog.locator('blockquote')).toHaveText('长期复利最大的优势来自时间跨度。');
  await page.screenshot({ path: 'test-results/citation-preview.png', fullPage: true });
  await dialog.getByRole('button', { name: '打开原文' }).click();
  await expect(page.locator('.citation-highlight')).toHaveText('长期复利最大的优势来自时间跨度。');
  await page.getByRole('button', { name: '就本章节提问' }).click();
  await expect(page.locator('.active-scope')).toContainText('增长');
  await page.getByLabel('向资料提问').fill('这个章节的重点是什么？');
  await page.getByRole('button', { name: '发送问题' }).click();
  await expect(page.locator('.message-assistant')).toHaveCount(2, { timeout: 15000 });
  await page.reload();
  await expect(page).toHaveURL(new RegExp(`/notebooks/${notebook.id}`));
  await expect(page.locator('.message-assistant')).toHaveCount(2);
  await request.delete(`/api/sources/${sourceResult.source.id}`);
  await page.getByRole('button', { name: '查看引用 1', exact: true }).first().click();
  await expect(page.getByRole('dialog')).toContainText('Original source unavailable');
  await request.delete(`/api/notebooks/${notebook.id}`);
});
