import { test, expect } from '@playwright/test';
import { fileURLToPath } from 'node:url';

test('chapter knowledge, citations, editing, source update, chat save and reload', async ({
  page,
  request,
}) => {
  for (const role of ['language', 'embedding'])
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
  const title = `知识验收 ${Date.now()}`;
  const notebook = await (await request.post('/api/notebooks', { data: { title } })).json();
  await Promise.all([page.waitForResponse('**/api/settings/models'), page.goto('/')]);
  if (await page.getByRole('dialog').isVisible())
    await page.getByRole('button', { name: '关闭设置' }).click();
  await page.getByRole('button', { name: `打开 ${title}`, exact: true }).click();
  const [uploaded] = await Promise.all([
    page.waitForResponse('**/sources/upload'),
    page
      .getByLabel('上传资料')
      .setInputFiles(fileURLToPath(new URL('./fixtures/book.epub', import.meta.url))),
  ]);
  if ((await uploaded.json()).duplicate)
    await page.getByRole('button', { name: '添加已有资料' }).click();
  const source = page.locator('.source-open').filter({ hasText: '长期思考' });
  await expect(source).toBeEnabled({ timeout: 15000 });
  await source.click();
  await page.getByRole('button', { name: '从本章节生成知识', exact: true }).click();
  const knowledge = page.getByRole('region', { name: '知识页' });
  await expect(knowledge.getByRole('button', { name: '编辑', exact: true })).toBeEnabled({
    timeout: 15000,
  });
  await expect(knowledge.locator('.knowledge-content')).toContainText('耐心的价值');
  await expect(knowledge.locator('.knowledge-content')).not.toContainText('长期复利');
  await knowledge.getByRole('button', { name: '查看引用 1', exact: true }).first().click();
  await expect(page.getByRole('dialog', { name: '原文引用' })).toContainText('长期思考');
  await page.getByRole('button', { name: '关闭引用' }).click();
  await knowledge.getByRole('button', { name: '编辑', exact: true }).click();
  await page.getByLabel('知识页标题', { exact: true }).fill('我的长期学习笔记');
  const body = page.getByLabel('知识页正文');
  await body.fill((await body.inputValue()) + '\n\n我的个人实践：每天回顾一次。');
  const rejectedNavigation = page.waitForEvent('dialog').then(async (dialog) => {
    expect(dialog.message()).toContain('未保存');
    await dialog.dismiss();
  });
  await page.getByRole('button', { name: '笔记本', exact: true }).click();
  await rejectedNavigation;
  await expect(body).toHaveValue(/我的个人实践/);
  await page.getByRole('button', { name: '保存知识页', exact: true }).click();
  await expect(knowledge.locator('.knowledge-content')).toContainText('我的个人实践');
  await page.getByRole('button', { name: '用所选资料更新', exact: true }).click();
  await expect(knowledge.locator('.knowledge-content')).toContainText('长期复利', {
    timeout: 15000,
  });
  await expect(knowledge.locator('.knowledge-content')).toContainText('我的个人实践');
  await page.screenshot({ path: 'test-results/knowledge-page.png', fullPage: true });
  const knowledgeUrl = page.url();
  await page.reload();
  await expect(page).toHaveURL(knowledgeUrl);
  await expect(knowledge.locator('.knowledge-content')).toContainText('我的个人实践');
  await page.getByRole('button', { name: '返回对话', exact: true }).click();
  await page.getByLabel('向资料提问').fill('长期复利的优势是什么？');
  await page.getByRole('button', { name: '发送问题', exact: true }).click();
  await expect(page.getByRole('button', { name: '保存为知识页', exact: true })).toBeVisible({
    timeout: 15000,
  });
  await page.getByRole('button', { name: '保存为知识页', exact: true }).click();
  await expect(knowledge.locator('.knowledge-content')).toContainText('长期复利');
  await expect(page.locator('.knowledge-list > button')).toHaveCount(2);
  await request.delete(`/api/notebooks/${notebook.id}`);
});
