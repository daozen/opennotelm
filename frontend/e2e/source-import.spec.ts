import { test, expect } from '@playwright/test';

test('multiple files keep successful siblings, report errors and queue duplicate confirmations', async ({
  page,
  request,
}) => {
  const title = `Batch import ${Date.now()}`;
  const notebook = await (await request.post('/api/notebooks', { data: { title } })).json();
  try {
    await Promise.all([page.waitForResponse('**/api/settings/models'), page.goto('/')]);
    if (await page.getByRole('dialog').isVisible())
      await page.getByRole('button', { name: '关闭设置' }).click();
    await page.getByRole('button', { name: `打开 ${title}`, exact: true }).click();
    const selectedFiles = [
      {
        name: `first-${Date.now()}.txt`,
        mimeType: 'text/plain',
        buffer: Buffer.from('First unique source ' + Date.now()),
      },
      {
        name: 'unsupported.doc',
        mimeType: 'application/msword',
        buffer: Buffer.from('Invalid document'),
      },
      {
        name: `second-${Date.now()}.txt`,
        mimeType: 'text/plain',
        buffer: Buffer.from('Second unique source ' + Date.now()),
      },
    ];
    await page.getByLabel('上传资料').setInputFiles(selectedFiles);
    await expect(page.getByText('本次添加：2 成功，1 失败，0 已存在')).toBeVisible();
    await expect(page.locator('.source-item')).toHaveCount(2);
    await expect(page.getByRole('button', { name: '重试上传', exact: true })).toBeVisible();
    const duplicateFiles = [selectedFiles[0], selectedFiles[2]];
    await expect(page.getByRole('button', { name: '添加资料', exact: true })).toBeEnabled();
    await page.getByLabel('上传资料').setInputFiles(duplicateFiles);
    await expect(page.getByText('还有 1 项重复资料待确认')).toBeVisible();
    await page.getByRole('button', { name: '添加已有资料', exact: true }).click();
    await expect(page.getByRole('dialog', { name: '资料已存在', exact: true })).toBeVisible();
    await page.getByRole('button', { name: '添加已有资料', exact: true }).click();
    await expect(page.getByRole('dialog')).not.toBeVisible();
    await expect(page.locator('.source-item')).toHaveCount(2);
  } finally {
    await request.delete(`/api/notebooks/${notebook.id}`);
  }
});

test('URL entry supports batches, bounded input and clear errors on mobile', async ({
  page,
  request,
}) => {
  const title = `Web import ${Date.now()}`;
  const notebook = await (await request.post('/api/notebooks', { data: { title } })).json();
  try {
    await page.goto(`/notebooks/${notebook.id}`);
    if (await page.getByRole('dialog').isVisible())
      await page.getByRole('button', { name: '关闭设置' }).click();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('button', { name: '资料与知识', exact: true }).click();
    await page.getByRole('button', { name: '导入网页', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: '导入网页' });
    await expect(dialog.getByRole('checkbox', { name: '保存正文图片' })).toBeChecked();
    await dialog.screenshot({ path: 'test-results/web-images-option-mobile.png' });
    await dialog.getByRole('checkbox', { name: '保存正文图片' }).uncheck();
    await dialog
      .getByLabel('网页地址')
      .fill('file:///etc/passwd\nhttp://127.0.0.1:8317/\nfile:///etc/passwd');
    await expect(dialog.getByRole('button', { name: '导入 2 个网页' })).toBeEnabled();
    expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBeTruthy();
    await dialog.screenshot({ path: 'test-results/web-import-mobile.png' });
    await dialog.getByRole('button', { name: '导入 2 个网页' }).click();
    await expect(page.getByText('本次添加：0 成功，2 失败，0 已存在')).toBeVisible();
    await expect(page.getByRole('list', { name: '资料导入结果' })).toContainText(
      '请输入有效的 HTTP 或 HTTPS 网址',
    );
    await expect(page.locator('.source-item')).toHaveCount(0);
    await page.getByRole('button', { name: '导入网页', exact: true }).click();
    await expect(dialog.getByRole('checkbox', { name: '保存正文图片' })).not.toBeChecked();
    await expect(dialog.getByLabel('网页地址')).toHaveValue(
      'file:///etc/passwd\nhttp://127.0.0.1:8317/',
    );
    await dialog
      .getByLabel('网页地址')
      .fill(Array.from({ length: 51 }, (_, i) => `https://example.com/${i}`).join('\n'));
    await expect(dialog.getByRole('button', { name: '导入 51 个网页' })).toBeDisabled();
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
  } finally {
    await request.delete(`/api/notebooks/${notebook.id}`);
  }
});
