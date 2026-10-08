import { test, expect } from '@playwright/test';

test('Deck and Podcast reuse saved instructions, preserve edits and keep histories separate', async ({
  page,
  request,
}) => {
  test.setTimeout(60000);
  for (const role of ['language', 'embedding', 'image']) {
    const response = await request.post('/api/settings/models/test', {
      data: {
        role,
        base_url: 'http://127.0.0.1:4301/v1',
        model_id: 'test-model',
        api_key: 'test-only-key',
      },
    });
    expect(response.ok()).toBeTruthy();
  }
  await request.put('/api/settings/preferences', { data: { ui_language: 'en' } });
  const notebook = await (
    await request.post('/api/notebooks', { data: { title: `Instructions ${Date.now()}` } })
  ).json();
  try {
    const uploaded = await (
      await request.post(`/api/notebooks/${notebook.id}/sources/upload`, {
        multipart: {
          file: {
            name: `instructions-${notebook.id}.txt`,
            mimeType: 'text/plain',
            buffer: Buffer.from(`Practice and reflection help learners improve. ${notebook.id}`),
          },
        },
      })
    ).json();
    await expect
      .poll(async () => (await (await request.get(`/api/jobs/${uploaded.job.id}`)).json()).status)
      .toBe('completed');
    const deckInstruction = `Explain the core idea clearly.\nUse a diagram. ${notebook.id}`;
    const podcastInstruction = `Discuss practical examples with two hosts. ${notebook.id}`;
    const scope = { kind: 'source', source_id: uploaded.source.id };
    let podcastId = '';
    for (const [kind, instruction, extra] of [
      ['decks', deckInstruction, { slide_count: 10 }],
      ['podcasts', podcastInstruction, { target_minutes: 5, script_only: true }],
    ] as const) {
      const response = await request.post(`/api/notebooks/${notebook.id}/${kind}`, {
        data: { scope, instruction, language: 'en', ...extra },
      });
      expect(response.ok()).toBeTruthy();
      const artifact = await response.json();
      if (kind === 'podcasts') podcastId = artifact.id;
      await request.post(`/api/${kind}/${artifact.id}/stop`, { data: {} });
    }
    await page.goto(`/notebooks/${notebook.id}`);
    if (await page.getByRole('dialog').isVisible())
      await page.getByRole('button', { name: 'Close settings', exact: true }).click();
    await page.getByRole('button', { name: 'Generate Visual Deck', exact: true }).click();
    let dialog = page.getByRole('dialog', { name: 'Generate Visual Deck' });
    let picker = dialog.getByLabel('Previous instructions');
    const deckOption = picker.locator('option').filter({ hasText: notebook.id });
    await expect(deckOption).toHaveCount(1);
    await picker.selectOption((await deckOption.getAttribute('value'))!);
    await expect(dialog.getByLabel('Deck instructions')).toHaveValue(deckInstruction);
    const edited = `${deckInstruction}\nAdd one concrete example.`;
    await dialog.getByLabel('Deck instructions').fill(edited);
    await dialog
      .getByRole('radio', { name: 'Generate separately for each source / chapter' })
      .check();
    const createdResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith(`/notebooks/${notebook.id}/decks/batch`) &&
        response.request().method() === 'POST',
    );
    await dialog.getByRole('button', { name: 'Start generating' }).click();
    const response = await createdResponse;
    expect(response.request().postDataJSON().instruction).toBe(edited);
    const batch = await response.json();
    await request.post(`/api/decks/${batch.decks[0].id}/stop`, { data: {} });
    await page.getByText('Generation instructions', { exact: true }).click();
    await expect(page.locator('.artifact-instruction-text')).toHaveText(edited);

    await page.goto(`/notebooks/${notebook.id}/podcasts/${podcastId}`);
    await page.getByText('Generation instructions', { exact: true }).click();
    await expect(page.locator('.artifact-instruction-text')).toHaveText(podcastInstruction);

    await page.getByRole('button', { name: 'Create Podcast', exact: true }).click();
    dialog = page.getByRole('dialog', { name: 'Create Podcast' });
    picker = dialog.getByLabel('Previous instructions');
    const podcastOption = picker.locator('option').filter({ hasText: notebook.id });
    await expect(podcastOption).toHaveCount(1);
    await expect(podcastOption).toContainText('Discuss practical examples');
    await picker.selectOption((await podcastOption.getAttribute('value'))!);
    await expect(dialog.getByLabel('Podcast instructions')).toHaveValue(podcastInstruction);
    await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
    await page.reload();
    await page.getByRole('button', { name: 'Generate Visual Deck', exact: true }).click();
    dialog = page.getByRole('dialog', { name: 'Generate Visual Deck' });
    picker = dialog.getByLabel('Previous instructions');
    await expect(picker.locator('option[title]').first()).toHaveAttribute('title', edited);
    await expect(dialog.getByLabel('Deck instructions')).toHaveValue('');
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(dialog.getByLabel('Previous instructions')).toBeVisible();
    await expect(dialog.getByLabel('Deck instructions')).toBeVisible();
    const fits = await dialog.evaluate((element) => element.scrollWidth <= element.clientWidth);
    expect(fits).toBeTruthy();
  } finally {
    await request.delete(`/api/notebooks/${notebook.id}`);
    await request.put('/api/settings/preferences', { data: { ui_language: 'zh-CN' } });
  }
});
