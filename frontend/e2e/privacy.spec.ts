import { test, expect } from '@playwright/test';

test('statistics choice remains available when the receiver is unconfigured', async ({
  page,
  request,
}) => {
  await request.put('/api/settings/preferences', { data: { telemetry_enabled: false } });
  // Isolate the front-end configured=false contract; the fixture's receiver stays local.
  await page.route('**/api/settings/telemetry', async (route) => {
    const response = await route.fetch();
    await route.fulfill({ json: { ...(await response.json()), configured: false } });
  });
  await page.goto('/');
  if (!(await page.getByRole('dialog').isVisible()))
    await page.getByRole('button', { name: '模型设置', exact: true }).click();
  const privacy = page.getByRole('region', { name: '隐私与诊断' });
  const toggle = privacy.getByRole('checkbox', { name: '允许匿名使用统计' });
  await expect(toggle).toBeEnabled();
  await expect(privacy.getByText(/勾选后仅在本地暂存匿名统计/)).toBeVisible();
  await toggle.check();
  await expect(privacy.getByRole('status')).toHaveText('统计偏好已保存。');
  await page.reload();
  if (!(await page.getByRole('dialog').isVisible()))
    await page.getByRole('button', { name: '模型设置', exact: true }).click();
  await expect(toggle).toBeChecked();
  await toggle.uncheck();
  await expect(privacy.getByRole('status')).toHaveText('统计偏好已保存。');
  expect((await (await request.get('/api/settings/preferences')).json()).telemetry_enabled).toBe(
    false,
  );
  await page.screenshot({ path: 'test-results/privacy-no-receiver.png', fullPage: true });
});

test('anonymous statistics are opt-in, persist, clear on disable and diagnostics omit content', async ({
  page,
  request,
}) => {
  await request.put('/api/settings/preferences', { data: { telemetry_enabled: false } });
  await page.goto('/');
  if (!(await page.getByRole('dialog').isVisible()))
    await page.getByRole('button', { name: '模型设置', exact: true }).click();
  const privacy = page.getByRole('region', { name: '隐私与诊断' });
  const toggle = privacy.getByRole('checkbox', { name: '允许匿名使用统计' });
  await expect(toggle).not.toBeChecked();
  await toggle.check();
  await expect
    .poll(
      async () => (await (await request.get('/api/settings/preferences')).json()).telemetry_enabled,
    )
    .toBe(true);
  await page.reload();
  if (!(await page.getByRole('dialog').isVisible()))
    await page.getByRole('button', { name: '模型设置', exact: true }).click();
  await expect(toggle).toBeChecked();
  const notebook = await (
    await request.post('/api/notebooks', { data: { title: 'PRIVATE_NOTEBOOK_SENTINEL' } })
  ).json();
  const report = await request.get('/api/diagnostics');
  const text = await report.text();
  expect(report.ok()).toBeTruthy();
  expect(text).not.toContain('PRIVATE_NOTEBOOK_SENTINEL');
  expect(text).not.toContain('test-only-key');
  expect(text).not.toContain('test-only-telemetry-token');
  expect(text).not.toContain('http://127.0.0.1:4301');
  const download = page.waitForEvent('download');
  await privacy.getByRole('link', { name: '下载诊断报告' }).click();
  expect((await download).suggestedFilename()).toBe('opennotelm-diagnostics.json');
  await toggle.uncheck();
  await expect
    .poll(async () => (await (await request.get('/api/settings/telemetry')).json()).enabled)
    .toBe(false);
  expect((await (await request.get('/api/settings/telemetry')).json()).queued_events).toBe(0);
  await page.screenshot({ path: 'test-results/privacy-settings.png', fullPage: true });
  await request.delete(`/api/notebooks/${notebook.id}`);
});
