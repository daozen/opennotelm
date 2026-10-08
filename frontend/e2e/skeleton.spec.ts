import { test, expect } from '@playwright/test';

test('first setup, notebook CRUD, reader shell, and persisted reload', async ({
  page,
  request,
}) => {
  // Reset state through public APIs so this acceptance path is repeatable.
  await request.put('/api/settings/preferences', { data: { ui_language: 'zh-CN' } });
  const existing = await request.get('/api/notebooks');
  for (const notebook of await existing.json())
    await request.delete(`/api/notebooks/${notebook.id}`);
  await Promise.all([page.waitForResponse('**/api/settings/models'), page.goto('/')]);
  if (!(await page.getByRole('dialog').isVisible()))
    await page.getByText('模型设置', { exact: true }).click();
  for (const name of ['语言模型', 'Embedding 模型', '图片模型']) {
    const form = page
      .locator('form')
      .filter({ has: page.getByRole('heading', { name, exact: true }) });
    await form.getByLabel('服务地址').fill('http://127.0.0.1:4301/v1');
    await form.getByLabel('访问密钥', { exact: true }).fill('test-only-key');
    await form.getByLabel('模型 ID', { exact: true }).fill('test-model');
    await form.getByRole('button', { name: '测试并保存' }).click();
    await expect(form.getByText('能力测试通过，配置已安全保存。')).toBeVisible();
    await expect(form.getByLabel('访问密钥', { exact: true })).toHaveValue('');
  }
  await page.getByRole('button', { name: '开始使用' }).click();
  await page.getByRole('button', { name: '创建笔记本', exact: true }).first().click();
  await page.getByLabel('笔记本名称').fill('长期阅读');
  await page.getByLabel('描述（可选）').fill('理解比收藏更重要。');
  await page.getByRole('button', { name: '保存笔记本' }).click();
  await expect(page.getByRole('heading', { name: '长期阅读', exact: true })).toBeVisible();
  await page.screenshot({ path: 'test-results/notebooks.png', fullPage: true });
  await page.reload();
  await expect(page.getByRole('heading', { name: '长期阅读', exact: true })).toBeVisible();
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await page.getByRole('button', { name: '打开 长期阅读', exact: true }).click();
  await expect(page.getByRole('heading', { name: '创作空间', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '笔记本', exact: true }).click();
  await page.getByRole('button', { name: '管理 长期阅读', exact: true }).click();
  await page.getByRole('button', { name: '编辑名称与描述' }).click();
  await page.getByLabel('笔记本名称').fill('深入阅读');
  await page.getByRole('button', { name: '保存笔记本' }).click();
  await page.getByRole('button', { name: '管理 深入阅读', exact: true }).click();
  await page.getByRole('button', { name: '删除笔记本', exact: true }).click();
  await page.getByRole('dialog').getByRole('button', { name: '删除笔记本', exact: true }).click();
  await expect(page.getByRole('heading', { name: '深入阅读', exact: true })).not.toBeVisible();
});
