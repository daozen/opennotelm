import { test, expect } from '@playwright/test';

test('fresh visitors match browser locales, while an explicit choice wins on another browser', async ({
  browser,
  request,
}, testInfo) => {
  const baseURL = testInfo.project.use.baseURL!;
  try {
    for (const [locale, language, direction] of [
      ['fr-CA', 'fr', 'ltr'],
      ['zh-HK', 'zh-TW', 'ltr'],
      ['ar-EG', 'ar', 'rtl'],
      ['it-IT', 'en', 'ltr'],
    ]) {
      const context = await browser.newContext({ locale, baseURL });
      try {
        const page = await context.newPage();
        let saved: string | null = null;
        // The suite shares a configured instance. Emulate the fresh GET contract;
        // explicit PUT still goes through the real preferences endpoint.
        await page.route('**/api/settings/preferences', async (route) => {
          if (route.request().method() === 'GET') {
            await route.fulfill({ json: { ui_language: saved, telemetry_enabled: false } });
          } else {
            const response = await route.fetch();
            expect(response.ok()).toBeTruthy();
            saved = (await response.json()).ui_language;
            await route.fulfill({ response });
          }
        });
        await page.goto('/');
        const picker = page.locator('.app-header select');
        await expect(picker).toBeEnabled();
        await expect(picker).toHaveValue(language);
        await expect(page.locator('html')).toHaveAttribute('lang', language);
        await expect(page.locator('html')).toHaveAttribute('dir', direction);
        expect(
          await page.evaluate(() => localStorage.getItem('opennotelm.ui-language')),
        ).toBeNull();
        await page.reload();
        await expect(picker).toBeEnabled();
        await expect(picker).toHaveValue(language);
        if (locale === 'fr-CA') {
          await picker.selectOption('de');
          await expect(picker).toBeEnabled();
          await expect(picker).toHaveValue('de');
          await page.reload();
          await expect(picker).toBeEnabled();
          await expect(picker).toHaveValue('de');
        }
      } finally {
        await context.close();
      }
    }
    const other = await browser.newContext({ locale: 'ja-JP', baseURL });
    try {
      const page = await other.newPage();
      await page.goto('/');
      await expect(page.locator('.app-header select')).toBeEnabled();
      await expect(page.locator('.app-header select')).toHaveValue('de');
    } finally {
      await other.close();
    }
  } finally {
    await request.put('/api/settings/preferences', { data: { ui_language: 'zh-CN' } });
  }
});
