import { expect, test } from '@playwright/test';

for (const {
  kind,
  sectionLabel,
  label,
  saveLabel,
  englishLabel,
  englishSaveLabel,
  initial,
  roleLabel,
  maximum = 20,
} of [
  {
    kind: 'image-generation',
    sectionLabel: '图片生成设置',
    label: '图片生成并发数',
    saveLabel: '保存并发设置',
    englishLabel: 'Image generation concurrency',
    englishSaveLabel: 'Save concurrency',
    initial: 2,
    roleLabel: '图片模型',
  },
  {
    kind: 'content-generation',
    sectionLabel: 'Deck 内容生成设置',
    label: 'Deck 内容生成并发数',
    saveLabel: '保存内容并发设置',
    englishLabel: 'Deck content generation concurrency',
    englishSaveLabel: 'Save content concurrency',
    initial: 2,
    roleLabel: '语言模型',
  },
  {
    kind: 'image-recognition',
    sectionLabel: '图片识别设置',
    label: '图片识别并发数',
    saveLabel: '保存识别并发设置',
    englishLabel: 'Image recognition concurrency',
    englishSaveLabel: 'Save recognition concurrency',
    initial: 4,
    roleLabel: '语言模型',
  },
  {
    kind: 'task-concurrency',
    sectionLabel: '任务处理设置',
    label: '同时处理任务数',
    saveLabel: '保存任务设置',
    englishLabel: 'Concurrent tasks',
    englishSaveLabel: 'Save task settings',
    initial: 3,
    maximum: 8,
    roleLabel: '',
  },
  {
    kind: 'request-concurrency',
    sectionLabel: '模型服务请求设置',
    label: '每个模型服务的总请求并发数',
    saveLabel: '保存请求设置',
    englishLabel: 'Total concurrent requests per service',
    englishSaveLabel: 'Save request settings',
    initial: 8,
    roleLabel: '',
  },
]) {
  test(`${kind} concurrency saves its maximum without model testing and survives language changes and reload`, async ({
    page,
    request,
  }) => {
    const endpoint = `/api/settings/models/${kind}`;
    const previous = await (await request.get(endpoint)).json();
    const preferences = await (await request.get('/api/settings/preferences')).json();
    for (const role of ['language', 'embedding', 'image']) {
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
    }
    const models = await (await request.get('/api/settings/models')).json();
    const capabilityTests: string[] = [];
    page.on('request', (req) => {
      if (req.url().endsWith('/settings/models/test')) capabilityTests.push(req.url());
    });
    try {
      await request.put('/api/settings/preferences', { data: { ui_language: 'zh-CN' } });
      await request.put(endpoint, { data: { concurrency: initial } });
      await page.setViewportSize({ width: 1440, height: 1000 });
      await page.goto('/');
      await page.getByRole('button', { name: '模型设置' }).click();
      const dialog = page.getByRole('dialog');
      const section = dialog.getByRole('region', { name: sectionLabel });
      if (roleLabel) await expect(section.locator('xpath=ancestor::form')).toContainText(roleLabel);
      const select = section.getByLabel(label);
      await expect(select).toBeEnabled();
      await expect(select).toHaveValue(String(initial));
      await expect(select.locator('option')).toHaveCount(maximum);
      await select.selectOption(String(maximum));
      await section.getByRole('button', { name: saveLabel }).click();
      await expect(section.getByRole('status')).toHaveText('并发设置已保存。');
      expect((await (await request.get(endpoint)).json()).concurrency).toBe(maximum);
      expect(await (await request.get('/api/settings/models')).json()).toEqual(models);
      expect(await (await request.get('/api/settings/preferences')).json()).toEqual({
        ...preferences,
        ui_language: 'zh-CN',
      });
      expect(capabilityTests).toHaveLength(0);
      await page.screenshot({ path: `test-results/${kind}-settings.png` });

      // Keep an unsaved concurrency choice when translating the surrounding form.
      await select.selectOption('1');
      await dialog.getByLabel('界面语言').selectOption('en');
      await expect(dialog.getByLabel(englishLabel)).toHaveValue('1');
      await expect(dialog.getByRole('button', { name: englishSaveLabel })).toBeEnabled();
      await dialog.getByRole('button', { name: 'Close settings' }).click();
      await page.reload();
      await page.getByRole('button', { name: 'Model settings' }).click();
      await expect(dialog.getByLabel(englishLabel)).toHaveValue(String(maximum));
      await expect(dialog.getByRole('button', { name: englishSaveLabel })).toBeDisabled();
      expect(capabilityTests).toHaveLength(0);
      await page.setViewportSize({ width: 390, height: 844 });
      await dialog.getByLabel(englishLabel).scrollIntoViewIfNeeded();
      await expect(dialog.getByLabel(englishLabel)).toBeVisible();
      expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBeTruthy();
      await page.screenshot({ path: `test-results/${kind}-settings-mobile.png` });
    } finally {
      await request.put(endpoint, { data: { concurrency: previous.concurrency } });
      await request.put('/api/settings/preferences', {
        data: { ...preferences, ui_language: 'zh-CN' },
      });
    }
  });
}
