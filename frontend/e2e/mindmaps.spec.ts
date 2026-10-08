import { test, expect } from '@playwright/test';

test('mind maps and the shared Studio support addressable viewing, citations, history, export and responsive navigation', async ({
  page,
  request,
}) => {
  test.setTimeout(90000);
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await request.post('/api/settings/models/test', {
    data: { role: 'language', base_url: 'http://127.0.0.1:4301/v1', model_id: 'test-model' },
  });
  await request.put('/api/settings/preferences', { data: { ui_language: 'en' } });
  const notebook = await (
    await request.post('/api/notebooks', { data: { title: `Mind maps ${Date.now()}` } })
  ).json();
  try {
    for (const name of ['Practice', 'Reflection']) {
      const uploaded = await (
        await request.post(`/api/notebooks/${notebook.id}/sources/upload`, {
          multipart: {
            file: {
              name: `${name}-${Date.now()}.txt`,
              mimeType: 'text/plain',
              buffer: Buffer.from(
                `${name}: practice strengthens learning. Reflection improves the next attempt. ${Date.now()}.`,
              ),
            },
          },
        })
      ).json();
      await expect
        .poll(async () => (await (await request.get(`/api/jobs/${uploaded.job.id}`)).json()).status)
        .toBe('completed');
    }
    await page.goto(`/notebooks/${notebook.id}/artifacts`);
    if (await page.getByRole('dialog', { name: 'Model settings' }).isVisible())
      await page.getByRole('button', { name: 'Close settings', exact: true }).click();
    await page.getByRole('button', { name: 'Create mind map', exact: true }).click();
    const dialog = page.getByRole('dialog', { name: 'Create mind map' });
    await expect(dialog.getByLabel('Mind map language')).toHaveValue('en');
    await expect(dialog.getByText('Target duration', { exact: true })).toHaveCount(0);
    await dialog
      .getByLabel('Mind map instructions')
      .fill('Explain the key ideas clearly.\nConnect concepts.');
    await dialog.getByRole('button', { name: 'Start generating' }).click();
    const canvas = page.getByRole('group', { name: 'Mind map canvas' });
    await expect(canvas).toBeVisible();
    await expect(page.getByRole('button', { name: 'Download SVG', exact: true })).toBeVisible();
    await canvas.getByRole('button', { name: 'Practice', exact: true }).click();
    await expect(page).toHaveURL(/\/mindmaps\/.+node=practice/);
    const url = page.url();
    await page.reload();
    await expect(canvas).toBeVisible();
    expect(page.url()).toBe(url);
    await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
    const zoom = await page.locator('.mindmap-tools > span').textContent();
    for (let poll = 0; poll < 2; poll++)
      await page.waitForResponse((response) => /\/api\/mindmaps\/[a-f0-9]+$/.test(response.url()));
    await expect(page.locator('.mindmap-tools > span')).toHaveText(zoom!);
    await canvas.scrollIntoViewIfNeeded();
    await canvas.hover({ position: { x: 180, y: 160 } });
    const box = (await canvas.boundingBox())!;
    const anchor = { x: box.x + 180, y: box.y + 160 };
    const pose = () =>
      canvas.evaluate((svg) => {
        const matrix = (svg.firstElementChild as SVGGElement).transform.baseVal.consolidate()!
          .matrix;
        return { scale: matrix.a, x: matrix.e, y: matrix.f };
      });
    const initialPose = await pose();
    const scroll = await page.evaluate(() => scrollY);
    await page.mouse.wheel(0, -80);
    await expect.poll(async () => (await pose()).scale).toBeGreaterThan(initialPose.scale);
    const wheelPose = await pose();
    expect((180 - wheelPose.x) / wheelPose.scale).toBeCloseTo(
      (180 - initialPose.x) / initialPose.scale,
      3,
    );
    expect((160 - wheelPose.y) / wheelPose.scale).toBeCloseTo(
      (160 - initialPose.y) / initialPose.scale,
      3,
    );
    expect(await page.evaluate(() => scrollY)).toBe(scroll);
    await page.mouse.wheel(0, 80);
    await expect.poll(async () => (await pose()).scale).toBeCloseTo(initialPose.scale, 3);
    const browserScale = await page.evaluate(() => ({
      ratio: devicePixelRatio,
      viewport: visualViewport!.scale,
    }));
    // Chromium delivers native trackpad pinch as Ctrl+wheel.
    const prevented = await canvas.evaluate((svg, point) => {
      return !svg.dispatchEvent(
        new WheelEvent('wheel', {
          bubbles: true,
          cancelable: true,
          ctrlKey: true,
          deltaY: -12,
          clientX: point.x,
          clientY: point.y,
        }),
      );
    }, anchor);
    expect(prevented).toBe(true);
    await expect.poll(async () => (await pose()).scale).toBeGreaterThan(initialPose.scale);
    const pinchPose = await pose();
    expect((180 - pinchPose.x) / pinchPose.scale).toBeCloseTo(
      (180 - initialPose.x) / initialPose.scale,
      3,
    );
    expect(
      await page.evaluate(() => ({ ratio: devicePixelRatio, viewport: visualViewport!.scale })),
    ).toEqual(browserScale);
    // Exercise Safari's cumulative gesture scale and avoid double zoom from wheel events.
    await canvas.evaluate((svg, point) => {
      const gesture = (type: string, scale: number) => {
        const event = Object.assign(new Event(type, { bubbles: true, cancelable: true }), {
          scale,
          clientX: point.x,
          clientY: point.y,
        });
        if (svg.dispatchEvent(event)) throw new Error('Native gesture was not intercepted');
      };
      gesture('gesturestart', 1);
      gesture('gesturechange', 1.2);
      svg.dispatchEvent(new WheelEvent('wheel', { cancelable: true, ctrlKey: true, deltaY: -30 }));
      gesture('gesturechange', 1.4);
      gesture('gestureend', 1.4);
    }, anchor);
    await expect.poll(async () => (await pose()).scale).toBeCloseTo(pinchPose.scale * 1.4, 3);
    expect(
      await page.evaluate(() =>
        document.body.dispatchEvent(new WheelEvent('wheel', { cancelable: true, deltaY: 10 })),
      ),
    ).toBe(true);
    for (const direction of [-1, 1]) {
      await canvas.evaluate((svg, direction) => {
        for (let i = 0; i < 40; i++)
          svg.dispatchEvent(
            new WheelEvent('wheel', { cancelable: true, deltaY: direction, deltaMode: 2 }),
          );
      }, direction);
      await expect.poll(async () => (await pose()).scale).toBeCloseTo(direction < 0 ? 2.5 : 0.08);
    }
    await page.getByRole('button', { name: 'Fit to canvas', exact: true }).click();
    await page
      .locator('.mindmap-node-detail')
      .getByRole('button', { name: 'Source citation 1' })
      .click();
    await expect(page.getByRole('dialog', { name: 'Source citation' })).toContainText(
      'practice strengthens learning.',
    );
    await page.getByRole('button', { name: 'Close citation' }).click();
    await canvas.getByRole('button', { name: 'Collapse Reflection' }).click();
    await expect(
      canvas.getByRole('button', { name: 'Review the attempt', exact: true }),
    ).toHaveCount(0);
    await canvas.getByRole('button', { name: 'Expand Reflection' }).click();
    await expect(
      canvas.getByRole('button', { name: 'Review the attempt', exact: true }),
    ).toBeVisible();
    const download = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download SVG' }).click();
    expect((await download).suggestedFilename()).toMatch(/\.svg$/);
    await page.getByText('Generation instructions', { exact: true }).click();
    await expect(page.locator('.artifact-instruction-text')).toHaveText(
      'Explain the key ideas clearly.\nConnect concepts.',
    );
    await page.screenshot({ path: 'test-results/mindmap-desktop.png', fullPage: true });
    await page.getByRole('button', { name: 'Focus preview', exact: true }).click();
    const focus = page.getByRole('dialog', { name: 'Mind map focus preview' });
    await expect(focus).toBeVisible();
    const focusCanvas = focus.getByRole('group', { name: 'Mind map canvas' });
    const focusZoom = await focus.locator('.mindmap-tools > span').textContent();
    await focusCanvas.hover();
    await page.mouse.wheel(0, -80);
    await expect(focus.locator('.mindmap-tools > span')).not.toHaveText(focusZoom!);
    await page.keyboard.press('Escape');
    await expect(focus).toHaveCount(0);
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(canvas).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBeTruthy();
    await page.getByRole('button', { name: 'Text outline', exact: true }).click();
    await expect(page.locator('.mindmap-outline')).toContainText('Review the attempt');
    await page.screenshot({ path: 'test-results/mindmap-phone.png', fullPage: true });
    await page.getByRole('button', { name: 'Back to Studio', exact: true }).click();
    await expect(page).toHaveURL(/\/artifacts/);
    await page.getByLabel('Artifact type').selectOption('mindmap');
    await expect(page).toHaveURL(/type=mindmap/);
    await page.reload();
    await expect(page.getByLabel('Artifact type')).toHaveValue('mindmap');
    await page.getByLabel('Search artifacts').fill('notfound');
    await expect(page.getByText('No matching artifacts')).toBeVisible();
    await page.getByLabel('Search artifacts').fill('');
    await page.getByRole('button', { name: 'Create mind map', exact: true }).click();
    await dialog.getByLabel('Previous instructions').selectOption('0');
    await expect(dialog.getByLabel('Mind map instructions')).toHaveValue(
      'Explain the key ideas clearly.\nConnect concepts.',
    );
    await dialog
      .getByRole('radio', { name: 'Generate separately for each source / chapter' })
      .check();
    await dialog.getByRole('radio', { name: 'Use source / chapter name' }).check();
    await dialog.getByRole('button', { name: 'Start generating' }).click();
    await expect
      .poll(
        async () =>
          (await (await request.get(`/api/notebooks/${notebook.id}/mindmaps`)).json()).filter(
            (m: { status: string }) => m.status === 'completed',
          ).length,
      )
      .toBe(3);
    await page.getByRole('button', { name: 'All artifacts', exact: true }).click();
    await expect(page.locator('.artifact-card')).toHaveCount(3);
    await page.getByRole('button', { name: 'Batch download', exact: true }).click();
    await expect(page.locator('.artifact-selection input:enabled')).toHaveCount(3);
    await page.getByLabel('Select all downloadable files').check();
    const bundle = page.waitForEvent('download');
    await page.getByRole('button', { name: 'Download selected (3)', exact: true }).click();
    expect((await bundle).suggestedFilename()).toMatch(/\.zip$/);
    await page.getByRole('button', { name: 'Cancel selection', exact: true }).click();
    let rejectDelete = true;
    await page.route('**/api/mindmaps/*', async (route) => {
      if (route.request().method() === 'DELETE' && rejectDelete) {
        rejectDelete = false;
        await route.fulfill({ status: 503, json: { error: { code: 'NETWORK_ERROR' } } });
      } else await route.continue();
    });
    await page
      .locator('.artifact-card')
      .first()
      .getByRole('button', { name: /Delete artifact ·/ })
      .click();
    await page
      .getByRole('alertdialog', { name: 'Delete artifact?' })
      .getByRole('button', { name: 'Confirm delete', exact: true })
      .click();
    const deletion = page.getByRole('alertdialog', { name: 'Delete artifact?' });
    await expect(deletion.getByRole('alert')).toBeVisible();
    await expect(page).toHaveURL(/\/artifacts/);
    await expect(page.locator('.artifact-card')).toHaveCount(3);
    await deletion.getByRole('button', { name: 'Confirm delete', exact: true }).click();
    await expect(page.locator('.artifact-card')).toHaveCount(2);
    expect(errors).toEqual([]);
  } finally {
    const maps = await (await request.get(`/api/notebooks/${notebook.id}/mindmaps`)).json();
    for (const map of maps) await request.delete(`/api/mindmaps/${map.id}`);
    await request.delete(`/api/notebooks/${notebook.id}`);
    await request.put('/api/settings/preferences', { data: { ui_language: 'zh-CN' } });
  }
});
