import { test, expect } from '@playwright/test';

for (const kind of ['quiz', 'flashcards'] as const) {
  test(`${kind} supports creation, source citations, persistent learning, exports and responsive navigation`, async ({
    page,
    request,
  }) => {
    test.setTimeout(90000);
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));
    for (const role of ['language', 'embedding', 'image']) {
      await request.post('/api/settings/models/test', {
        data: { role, base_url: 'http://127.0.0.1:4301/v1', model_id: 'test-model' },
      });
    }
    await request.put('/api/settings/preferences', { data: { ui_language: 'en' } });
    const notebook = await (
      await request.post('/api/notebooks', { data: { title: `Study ${kind} ${Date.now()}` } })
    ).json();
    const resource = kind === 'quiz' ? 'quizzes' : 'flashcards';
    try {
      const uploaded = await (
        await request.post(`/api/notebooks/${notebook.id}/sources/upload`, {
          multipart: {
            file: {
              name: `practice-${Date.now()}.txt`,
              mimeType: 'text/plain',
              buffer: Buffer.from(
                `Practice strengthens learning. Reflection improves the next attempt. ${Date.now()}`,
              ),
            },
          },
        })
      ).json();
      await expect
        .poll(async () => (await (await request.get(`/api/jobs/${uploaded.job.id}`)).json()).status)
        .toBe('completed');
      await page.goto(`/notebooks/${notebook.id}/artifacts`);
      if (await page.getByRole('dialog', { name: 'Model settings' }).isVisible())
        await page.getByRole('button', { name: 'Close settings', exact: true }).click();
      const createLabel = kind === 'quiz' ? 'Create quiz' : 'Create flashcards';
      await page.getByRole('button', { name: createLabel, exact: true }).click();
      const dialog = page.getByRole('dialog', { name: createLabel });
      await dialog
        .getByLabel(kind === 'quiz' ? 'Quiz instructions' : 'Flashcard instructions')
        .fill('Explain simply. Use sources.');
      await dialog.getByLabel('Maximum items').selectOption('5');
      await expect(
        dialog.getByLabel(kind === 'quiz' ? 'Quiz language' : 'Flashcard language'),
      ).toHaveValue('en');
      await dialog.getByRole('button', { name: 'Start generating' }).click();
      const view = page.getByRole('region', {
        name: kind === 'quiz' ? 'Quiz' : 'Flashcards',
        exact: true,
      });
      // section has an accessible name and is therefore a region.
      await expect(view).toBeVisible();
      await expect(view.getByRole('link', { name: 'Download study material' })).toBeVisible();
      const studyUrl = page.url();
      const id = new URL(studyUrl).pathname.split('/').at(-1)!;
      if (kind === 'quiz') {
        await expect(view.getByRole('button', { name: 'Submit answer' })).toBeDisabled();
        await expect(
          view.getByText(
            'Practice strengthens learning, while reflection improves the next attempt.',
          ),
        ).toHaveCount(0);
        await view.getByRole('radio', { name: 'B. Avoiding reflection' }).check();
        await view.getByRole('button', { name: 'Submit answer' }).click();
        await expect(view.getByText('Correct answer: A', { exact: false })).toBeVisible();
        await view.getByRole('button', { name: 'Next item', exact: true }).click();
        await expect(page).toHaveURL(kind === 'quiz' ? /item=Q2/ : /item=F2/);
        await view.getByRole('radio', { name: 'A. Practice' }).check();
        await view.getByRole('button', { name: 'Previous item', exact: true }).click();
        await view.getByRole('button', { name: 'Next item', exact: true }).click();
        await expect(view.getByRole('radio', { name: 'A. Practice' })).toBeChecked();
        await view.getByRole('button', { name: 'Submit answer' }).click();
      } else {
        const flip = view.getByRole('button', { name: 'Show answer', exact: true });
        await flip.focus();
        await page.keyboard.press('Space');
        await expect(
          view.getByRole('button', { name: 'Show question', exact: true }),
        ).toContainText('Practice and reflection support learning.');
        await view.getByRole('button', { name: 'Mastered', exact: true }).click();
        await expect(page).toHaveURL(kind === 'quiz' ? /item=Q2/ : /item=F2/);
        await view.getByRole('button', { name: 'Show answer', exact: true }).click();
        await view.getByRole('button', { name: 'Review again', exact: true }).click();
      }
      const saved = await (await request.get(`/api/${resource}/${id}`)).json();
      expect(Object.keys(saved.progress.responses)).toHaveLength(2);
      await page.reload();
      await expect(view).toBeVisible();
      await expect(view.getByRole('button', { name: 'Next item', exact: true })).toBeVisible();
      expect((await (await request.get(`/api/${resource}/${id}`)).json()).progress).toEqual(
        saved.progress,
      );
      await view.getByRole('button', { name: 'Previous item', exact: true }).click();
      if (kind === 'flashcards')
        await view.getByRole('button', { name: 'Show answer', exact: true }).click();
      await view.getByRole('button', { name: 'Source citation 1', exact: true }).click();
      await expect(page.getByRole('dialog', { name: 'Source citation' })).toContainText(
        'Practice strengthens learning.',
      );
      await page.getByRole('button', { name: 'Close citation' }).click();
      await page.setViewportSize({ width: 768, height: 1024 });
      await expect(view).toBeVisible();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      ).toBeTruthy();
      await page.screenshot({ path: `test-results/${kind}-tablet.png`, fullPage: true });
      await page.setViewportSize({ width: 390, height: 844 });
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      ).toBeTruthy();
      await page.screenshot({ path: `test-results/${kind}-phone.png`, fullPage: true });
      const download = page.waitForEvent('download');
      await view.getByRole('link', { name: 'Download study material' }).click();
      expect((await download).suggestedFilename()).toMatch(/\.md$/);
      await view.getByRole('button', { name: 'Rename', exact: true }).click();
      const rename = page.getByRole('dialog', { name: 'Rename artifact' });
      await rename.getByLabel('Title', { exact: true }).fill('My learning set');
      await rename.getByRole('button', { name: 'Save name' }).click();
      await expect(view.getByRole('heading', { name: 'My learning set' })).toBeVisible();
      // Explicit reset is confirmed, then preserves generated content.
      await view.getByRole('button', { name: 'Start again', exact: true }).click();
      await page
        .getByRole('alertdialog', { name: 'Reset study progress?' })
        .getByRole('button', { name: 'Start again' })
        .click();
      await expect
        .poll(
          async () =>
            Object.keys(
              (await (await request.get(`/api/${resource}/${id}`)).json()).progress.responses,
            ).length,
        )
        .toBe(0);
      await view.getByRole('button', { name: 'Back to Studio', exact: true }).click();
      await page.getByLabel('Artifact type').selectOption(kind);
      await expect(page).toHaveURL(new RegExp(`type=${kind}`));
      await page.reload();
      await expect(page.getByLabel('Artifact type')).toHaveValue(kind);
      await expect(page.locator('.artifact-card')).toHaveCount(1);
      await page.getByRole('button', { name: 'Batch download', exact: true }).click();
      await page.getByLabel('Select all downloadable files').check();
      const bundle = page.waitForEvent('download');
      await page.getByRole('button', { name: 'Download selected (1)', exact: true }).click();
      expect((await bundle).suggestedFilename()).toMatch(/\.zip$/);
      await page.getByRole('button', { name: 'Cancel selection', exact: true }).click();
      await page.getByRole('button', { name: /Delete artifact · My learning set/ }).click();
      await page
        .getByRole('alertdialog', { name: 'Delete artifact?' })
        .getByRole('button', { name: 'Confirm delete' })
        .click();
      await expect(page.locator('.artifact-card')).toHaveCount(0);
      expect(errors).toEqual([]);
    } finally {
      const studies = await (await request.get(`/api/notebooks/${notebook.id}/${resource}`)).json();
      for (const study of studies) await request.delete(`/api/${resource}/${study.id}`);
      await request.delete(`/api/notebooks/${notebook.id}`);
      await request.put('/api/settings/preferences', { data: { ui_language: 'zh-CN' } });
    }
  });
}
