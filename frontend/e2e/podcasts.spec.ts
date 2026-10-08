import { test, expect } from '@playwright/test';

test.afterEach(async ({ request }) => {
  await request.put('/api/settings/preferences', { data: { ui_language: 'zh-CN' } });
});

test('podcast duration, script editing, playback navigation, citations and downloads', async ({
  page,
  request,
}) => {
  test.setTimeout(60000);
  const pageErrors: string[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  for (const role of ['language', 'speech']) {
    const configured = await request.post('/api/settings/models/test', {
      data: {
        role,
        base_url: 'http://127.0.0.1:4301/v1',
        model_id: 'test-model',
        voice_a: 'Ryan',
        voice_b: 'Vivian',
      },
    });
    expect(configured.ok()).toBeTruthy();
  }
  await request.put('/api/settings/preferences', { data: { ui_language: 'en' } });
  const notebook = await (
    await request.post('/api/notebooks', { data: { title: `Podcast ${Date.now()}` } })
  ).json();
  const uploaded = await (
    await request.post(`/api/notebooks/${notebook.id}/sources/upload`, {
      multipart: {
        file: {
          name: `learning-${Date.now()}.txt`,
          mimeType: 'text/plain',
          buffer: Buffer.from(
            `Practice strengthens learning. Reflection helps a learner improve the next attempt. Session ${Date.now()}.`,
          ),
        },
      },
    })
  ).json();
  await expect
    .poll(async () => (await (await request.get(`/api/jobs/${uploaded.job.id}`)).json()).status)
    .toBe('completed');
  await page.goto(`/notebooks/${notebook.id}`);
  if (await page.getByRole('dialog').isVisible())
    await page.getByRole('button', { name: 'Close settings', exact: true }).click();
  await page.getByRole('button', { name: 'Create Podcast', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Create Podcast' });
  for (const minutes of [10, 30, 60])
    await expect(
      dialog.getByRole('radio', { name: `About ${minutes} minutes`, exact: true }),
    ).toBeVisible();
  await dialog.getByRole('radio', { name: 'About 5 minutes', exact: true }).check();
  await dialog.getByLabel('Write the script first, generate audio later').check();
  await dialog.getByRole('button', { name: 'Start generating', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Generate audio', exact: true })).toBeVisible({
    timeout: 20000,
  });
  await expect(page.locator('.podcast-segment')).toHaveCount(3);
  const url = page.url();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Episode script', exact: true })).toBeVisible();
  expect(page.url()).toBe(url);
  await page
    .locator('.podcast-segment')
    .first()
    .getByRole('button', { name: 'Edit script' })
    .click();
  await page
    .locator('.podcast-segment textarea')
    .first()
    .fill('Practice helps you learn through repeated attempts.');
  await page.getByRole('button', { name: 'Save script' }).click();
  await page.getByRole('button', { name: 'Generate audio', exact: true }).click();
  await expect(page.getByRole('link', { name: 'Download audio', exact: true })).toBeVisible({
    timeout: 20000,
  });
  // Keep the short synthetic audio playing while testing navigation and dialogs.
  await page.locator('.podcast-player audio').evaluate((audio: HTMLAudioElement) => {
    audio.loop = true;
  });
  await page.getByRole('button', { name: 'Play audio', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Audio player' })).toBeVisible();
  await page.getByLabel('Playback speed').selectOption('1.5');
  await page
    .getByRole('navigation', { name: 'Episode chapters' })
    .getByRole('button')
    .last()
    .click();
  await page.getByRole('button', { name: 'View citation 1', exact: true }).first().click();
  await expect(page.getByRole('dialog', { name: 'Source citation' })).toContainText(
    'Practice strengthens learning.',
  );
  await page.getByRole('button', { name: 'Close citation' }).click();
  const downloaded = page.waitForEvent('download');
  await page.getByRole('link', { name: 'Download audio', exact: true }).click();
  expect((await downloaded).suggestedFilename()).toMatch(/\.mp3$/);
  await page.screenshot({ path: 'test-results/podcast-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 820, height: 1180 });
  await page.screenshot({ path: 'test-results/podcast-tablet.png', fullPage: true });
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
  ).toBeTruthy();
  await page.getByRole('button', { name: 'Back to Studio', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Audio player' })).toBeVisible();
  const audio = await page.locator('.podcast-player audio').elementHandle();
  const audioSource = await audio!.evaluate((element: HTMLAudioElement) => element.currentSrc);
  for (const viewport of [
    { width: 1440, height: 700 },
    { width: 820, height: 700 },
    { width: 390, height: 700 },
  ]) {
    await page.setViewportSize(viewport);
    const sections = page.getByRole('navigation', { name: 'Workspace sections' });
    if (await sections.isVisible())
      await sections.getByRole('button', { name: 'Studio', exact: true }).click();
    await page.getByRole('button', { name: 'Create Podcast', exact: true }).click();
    const scriptOnly = dialog.getByLabel('Write the script first, generate audio later');
    await scriptOnly.scrollIntoViewIfNeeded();
    const checkboxLayout = await scriptOnly.evaluate((input) => {
      const checkbox = input.getBoundingClientRect();
      const label = input.closest('label')!;
      const text = label.querySelector('span')!.getBoundingClientRect();
      return { aligned: Math.abs(checkbox.top - text.top) < 5, gap: text.left - checkbox.right };
    });
    expect(checkboxLayout.aligned).toBe(true);
    expect(checkboxLayout.gap).toBeGreaterThanOrEqual(6);
    await scriptOnly.locator('..').locator('span').click();
    await expect(scriptOnly).toBeChecked();
    await scriptOnly.uncheck();
    expect(await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(
      true,
    );
    for (const name of ['Cancel', 'Start generating']) {
      const action = dialog.getByRole('button', { name, exact: true });
      await action.scrollIntoViewIfNeeded();
      // An inert player still paints over the footer but is skipped by hit testing.
      // Temporarily enable its hit testing to check the actual visual stacking.
      expect(
        await action.evaluate((element) => {
          const rect = element.getBoundingClientRect();
          const background = document
            .querySelector('.podcast-player')
            ?.closest<HTMLElement>('[inert]');
          if (background) background.inert = false;
          try {
            return element.contains(
              document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2),
            );
          } finally {
            if (background) background.inert = true;
          }
        }),
        `${name} must receive clicks at ${viewport.width}px`,
      ).toBeTruthy();
      await action.click({ trial: true });
    }
    await expect
      .poll(() => audio!.evaluate((element: HTMLAudioElement) => element.paused))
      .toBe(false);
    expect(
      await audio!.evaluate((element: HTMLAudioElement) => ({
        sameElement: element === document.querySelector('.podcast-player audio'),
        source: element.currentSrc,
        rate: element.playbackRate,
        backgroundInert: !!element.closest('[inert]'),
      })),
    ).toEqual({ sameElement: true, source: audioSource, rate: 1.5, backgroundInert: true });
    await page.screenshot({ path: `test-results/podcast-dialog-${viewport.width}.png` });
    await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(dialog).not.toBeVisible();
    expect(await audio!.evaluate((element) => !!element.closest('[inert]'))).toBe(false);
  }
  await page.setViewportSize({ width: 1440, height: 700 });
  await page.goto(url);
  const view = page.getByRole('region', { name: 'Podcast', exact: true });
  await view.getByRole('button', { name: 'Rename', exact: true }).click();
  const rename = page.getByRole('dialog', { name: 'Rename', exact: true });
  const renamedTitle = `Renamed episode ${Date.now()}`;
  await rename.getByLabel('Podcast name').fill(renamedTitle);
  await rename.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(rename).not.toBeVisible();
  await expect(view.getByRole('heading', { name: renamedTitle })).toBeVisible();
  await page.locator('.podcast-player audio').evaluate((element: HTMLAudioElement) => {
    element.loop = true;
  });
  await view.getByRole('button', { name: 'Play audio', exact: true }).click();
  let failDelete = true;
  await page.route(`**/api/podcasts/${new URL(url).pathname.split('/').at(-1)}`, async (route) => {
    if (route.request().method() === 'DELETE' && failDelete)
      await route.fulfill({ status: 500, json: { error: { code: 'NETWORK_ERROR' } } });
    else await route.continue();
  });
  await view.getByRole('button', { name: 'Delete', exact: true }).click();
  const deletion = page.getByRole('alertdialog', { name: 'Delete Podcast' });
  await expect(deletion.getByRole('button', { name: 'Cancel' })).toBeFocused();
  await deletion.getByRole('button', { name: 'Delete', exact: true }).click();
  await expect(deletion.getByRole('alert')).toBeVisible();
  expect(page.url()).toBe(url);
  await deletion.getByRole('button', { name: 'Cancel' }).click();
  await expect(view.getByRole('heading', { name: renamedTitle })).toBeVisible();
  await expect(page.getByRole('region', { name: 'Audio player' })).toBeVisible();
  expect(
    await page
      .locator('.podcast-player audio')
      .evaluate((element: HTMLAudioElement) => element.paused),
  ).toBe(false);
  // A successful 204 must navigate back and immediately remove the Studio card.
  failDelete = false;
  await view.getByRole('button', { name: 'Delete', exact: true }).click();
  await deletion.getByRole('button', { name: 'Delete', exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/notebooks/${notebook.id}/artifacts$`));
  await expect(page.locator('.artifact-grid .deck-open', { hasText: renamedTitle })).toHaveCount(0);
  await expect(page.getByRole('region', { name: 'Audio player' })).not.toBeVisible();
  expect(pageErrors).toEqual([]);
});
