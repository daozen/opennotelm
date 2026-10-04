import { expect, test } from '@playwright/test';

test('switching embeddings rebuilds indexes only, exposes failures, and survives closing settings', async ({
  page,
  request,
}) => {
  const config = (model_id: string) => ({
    role: 'embedding',
    model_id,
    base_url: 'http://127.0.0.1:4301/v1',
    api_key: 'test-only-key',
  });
  const endpoint = '/api/settings/models/embedding/indexes';
  const notebook = await (
    await request.post('/api/notebooks', { data: { title: `Index rebuild ${Date.now()}` } })
  ).json();
  await request.put('/api/settings/preferences', { data: { ui_language: 'zh-CN' } });
  for (const role of ['language', 'embedding', 'image']) {
    expect(
      (
        await request.post('/api/settings/models/test', { data: { ...config('test-model'), role } })
      ).ok(),
    ).toBeTruthy();
  }
  const uploaded = await (
    await request.post(`/api/notebooks/${notebook.id}/sources/upload`, {
      multipart: {
        file: {
          name: 'index-switch.txt',
          mimeType: 'text/plain',
          buffer: Buffer.from(`Stable source facts ${Date.now()}. Learning compounds over time.`),
        },
      },
    })
  ).json();
  const source = uploaded.source.id;
  const sourcesEndpoint = `/api/notebooks/${notebook.id}/sources`;
  await expect
    .poll(async () => (await (await request.get(sourcesEndpoint)).json())[0].status)
    .toBe('indexed');
  const blocks = await (await request.get(`/api/sources/${source}/blocks`)).json();
  try {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('/');
    if (!(await page.getByRole('dialog').isVisible()))
      await page.getByRole('button', { name: '模型设置' }).click();
    const form = page.getByRole('dialog').locator('form').filter({ hasText: 'Embedding 模型' });
    await form.getByLabel('模型 ID').fill('slow-embeddings');
    await form.getByRole('button', { name: '测试并保存', exact: true }).click();
    const indexes = form.getByRole('region', { name: '资料检索索引' });
    await expect(indexes.getByRole('status').first()).toContainText('重建中');
    await page.getByRole('button', { name: '关闭设置' }).click();
    await expect
      .poll(async () => {
        const result = await (await request.get(endpoint)).json();
        return result.counts.ready === result.total;
      })
      .toBeTruthy();
    expect(await (await request.get(`/api/sources/${source}/blocks`)).json()).toEqual(blocks);
    await page.getByRole('button', { name: '模型设置' }).click();
    await form.getByLabel('模型 ID').fill('embedding-fails-after-probe');
    await form.getByRole('button', { name: '测试并保存', exact: true }).click();
    await expect(indexes.getByRole('button', { name: '重试失败项' })).toBeVisible({
      timeout: 15000,
    });
    await indexes.getByText('查看各资料进度与更多操作').click();
    await expect(indexes.getByText('重建失败', { exact: true }).first()).toBeVisible();
    await indexes.getByRole('button', { name: '重试失败项' }).click();
    await expect(indexes.getByText('索引重建已加入后台队列，关闭设置后仍会继续。')).toBeVisible();
    await form.getByLabel('模型 ID').fill('test-model');
    await form.getByRole('button', { name: '测试并保存', exact: true }).click();
    await expect
      .poll(async () => {
        const result = await (await request.get(endpoint)).json();
        return result.counts.ready === result.total;
      })
      .toBeTruthy();
    await page.reload();
    await page.getByRole('button', { name: '模型设置' }).click();
    await expect(indexes.getByRole('button', { name: '重建待处理索引' })).toBeDisabled();
    await indexes.getByText('查看各资料进度与更多操作').click();
    const previousIdentity = (await (await request.get('/api/settings/models')).json()).models
      .embedding.capabilities.index_signature;
    const [recalculated] = await Promise.all([
      page.waitForResponse('**/api/settings/models/embedding/indexes/rebuild'),
      indexes.getByRole('button', { name: '重新计算全部索引' }).click(),
    ]);
    expect(recalculated.ok()).toBeTruthy();
    await expect
      .poll(async () => {
        const result = await (await request.get(endpoint)).json();
        return result.counts.ready === result.total;
      })
      .toBeTruthy();
    expect(
      (await (await request.get('/api/settings/models')).json()).models.embedding.capabilities
        .index_signature,
    ).not.toBe(previousIdentity);
    expect(await (await request.get(`/api/sources/${source}/blocks`)).json()).toEqual(blocks);
    await page.setViewportSize({ width: 390, height: 844 });
    await indexes.scrollIntoViewIfNeeded();
    await expect(indexes).toBeVisible();
    expect(
      await page.getByRole('dialog').evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBeTruthy();
    await page.screenshot({ path: 'test-results/embedding-indexes-mobile.png' });
  } finally {
    await request.post('/api/settings/models/test', { data: config('test-model') });
    await expect
      .poll(async () => {
        const result = await (await request.get(endpoint)).json();
        return result.counts.ready === result.total;
      })
      .toBeTruthy();
    await request.delete(`/api/notebooks/${notebook.id}`);
    await request.delete(`/api/sources/${source}`);
  }
});
