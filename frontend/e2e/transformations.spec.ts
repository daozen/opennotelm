import { test, expect } from '@playwright/test';
import { fileURLToPath } from 'node:url';

test('temporary summary and outline only become Knowledge after explicit save', async ({
  page,
  request,
}) => {
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
  const title = `临时理解 ${Date.now()}`;
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
  const source = page.locator('.source-open').filter({ hasText: 'Learning' });
  await expect(source).toBeEnabled({ timeout: 15000 });
  await source.click();
  await page.getByRole('button', { name: '总结本章节', exact: true }).click();
  const summary = page.getByRole('dialog', { name: '资料摘要', exact: true });
  await expect(summary.getByRole('button', { name: '保存为知识页' })).toBeVisible({
    timeout: 15000,
  });
  expect(await (await request.get(`/api/notebooks/${notebook.id}/knowledge`)).json()).toEqual([]);
  await summary.getByRole('button', { name: '查看引用 1', exact: true }).click();
  await expect(page.getByRole('dialog', { name: '原文引用' })).toContainText(
    'Small improvements accumulate over time.',
  );
  await page.getByRole('button', { name: '关闭引用' }).click();
  await page.screenshot({ path: 'test-results/temporary-summary.png', fullPage: true });
  await page.getByRole('button', { name: '关闭临时结果' }).click();
  expect(await (await request.get(`/api/notebooks/${notebook.id}/knowledge`)).json()).toEqual([]);
  await page.getByRole('button', { name: '本章节提纲', exact: true }).click();
  const outline = page.getByRole('dialog', { name: '资料提纲', exact: true });
  await expect(outline.getByRole('button', { name: '保存为知识页' })).toBeVisible({
    timeout: 15000,
  });
  await outline.getByRole('button', { name: '保存为知识页' }).click();
  await expect(
    page.getByRole('region', { name: '知识页' }).getByRole('button', { name: '编辑', exact: true }),
  ).toBeEnabled();
  expect(await (await request.get(`/api/notebooks/${notebook.id}/knowledge`)).json()).toHaveLength(
    1,
  );
  await request.delete(`/api/notebooks/${notebook.id}`);
});
