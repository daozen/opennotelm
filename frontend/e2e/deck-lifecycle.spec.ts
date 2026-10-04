import { expect, test } from '@playwright/test';
import type { Deck } from '../src/api';

test.use({ hasTouch: true });

test('stop queued and running Decks, resume saved pages, preview on tablets and delete independently', async ({
  page,
  request,
}) => {
  test.setTimeout(90000);
  const taskEndpoint = '/api/settings/models/task-concurrency';
  const taskSettings = await (await request.get(taskEndpoint)).json();
  // Exercise the queued controls deliberately; parallel batches have their own flow.
  await request.put(taskEndpoint, { data: { concurrency: 1 } });
  for (const role of ['language', 'embedding', 'image']) {
    expect(
      (
        await request.post('/api/settings/models/test', {
          data: {
            role,
            base_url: 'http://127.0.0.1:4301/v1',
            api_key: 'test-only-key',
            model_id: role === 'image' ? 'slow-images' : 'test-model',
          },
        })
      ).ok(),
    ).toBeTruthy();
  }
  await request.put('/api/settings/models/image-generation', { data: { concurrency: 2 } });
  const notebook = await (
    await request.post('/api/notebooks', { data: { title: `Deck controls ${Date.now()}` } })
  ).json();
  const upload = await (
    await request.post(`/api/notebooks/${notebook.id}/sources/upload`, {
      multipart: {
        file: {
          name: 'lifecycle.md',
          mimeType: 'text/markdown',
          buffer: Buffer.from(
            `# ${Date.now()}\n\nSmall improvements accumulate over time.\n\nDaily reflection helps learning.`,
          ),
        },
      },
    })
  ).json();
  await expect
    .poll(async () => (await (await request.get(`/api/sources/${upload.source.id}`)).json()).status)
    .toBe('indexed');
  const create = async () =>
    (
      await request.post(`/api/notebooks/${notebook.id}/decks`, { data: { slide_count: 10 } })
    ).json();
  const first: Deck = await create(),
    queued: Deck = await create();
  const read = async (id: string): Promise<Deck> => (await request.get(`/api/decks/${id}`)).json();
  const go = async (id: string) => page.goto(`/notebooks/${notebook.id}/decks/${id}`);
  const viewer = page.getByRole('region', { name: 'Visual Deck', exact: true });
  try {
    await go(queued.id);
    await expect(viewer.getByText('等待生成', { exact: true })).toBeVisible();
    await viewer.getByRole('button', { name: '停止生成', exact: true }).click();
    await expect(viewer.getByRole('button', { name: '继续生成', exact: true })).toBeVisible();
    expect((await read(queued.id)).job?.status).toBe('cancelled');
    await go(first.id);
    await expect
      .poll(async () => (await read(first.id)).slides.filter((s) => s.render).length)
      .toBeGreaterThan(0);
    await viewer.getByRole('button', { name: '停止生成', exact: true }).click();
    await expect(viewer.getByRole('button', { name: '继续生成', exact: true })).toBeVisible();
    const saved = await read(first.id);
    expect(saved.job?.status).toBe('cancelled');
    const renders = saved.slides.filter((s) => s.render).map((s) => [s.id, s.render!.id]);
    expect(renders.length).toBeGreaterThan(0);
    expect(renders.length).toBeLessThan(10);
    await page.reload();
    await expect(viewer.getByRole('button', { name: '继续生成', exact: true })).toBeVisible();
    await viewer.getByRole('button', { name: '继续生成', exact: true }).click();
    await expect.poll(async () => (await read(first.id)).status, { timeout: 30000 }).toBe('ready');
    const ready = await read(first.id);
    expect(ready.job?.id).toBe(first.job?.id);
    for (const [slide, render] of renders)
      expect(ready.slides.find((s) => s.id === slide)!.render!.id).toBe(render);
    expect((await read(queued.id)).job?.status).toBe('cancelled');
    expect((await request.get(ready.pdf_export!.download_url)).ok()).toBeTruthy();
    for (const size of [
      { width: 1440, height: 900 },
      { width: 1024, height: 768 },
      { width: 768, height: 1024 },
      { width: 390, height: 844 },
    ]) {
      await page.setViewportSize(size);
      const stage = viewer.locator('.deck-preview-stage');
      await expect
        .poll(async () => (await stage.boundingBox())!.height)
        .toBeGreaterThanOrEqual(size.height - 40);
      await stage.scrollIntoViewIfNeeded();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
      ).toBeTruthy();
      const clickImage = async (right: boolean) => {
        const image = viewer.locator('.deck-page-image');
        await image.scrollIntoViewIfNeeded();
        const bounds = (await image.boundingBox())!;
        const x = bounds.x + bounds.width * (right ? 0.75 : 0.25);
        const y = bounds.y + bounds.height / 2;
        if (size.width < 700) await page.touchscreen.tap(x, y);
        else await page.mouse.click(x, y);
      };
      // Use actual image coordinates: transparent controls must respond to mouse/touch hits.
      await clickImage(true);
      await expect(page).toHaveURL(new RegExp(`slide=${ready.slides[1].id}`));
      await expect(stage).toContainText('第 2 / 10 页');
      await page.keyboard.press('ArrowDown');
      await expect(stage).toContainText('第 3 / 10 页');
      await page.keyboard.press('ArrowUp');
      await expect(page).toHaveURL(new RegExp(`slide=${ready.slides[1].id}`));
      if (size.width === 1024) {
        await page.reload();
        await expect(stage).toContainText('第 2 / 10 页');
      }
      await clickImage(false);
      await expect(stage).toContainText('第 1 / 10 页');
      await page.keyboard.press('ArrowUp');
      await expect(stage).toContainText('第 1 / 10 页');
      await viewer.getByRole('button', { name: '专注预览', exact: true }).click();
      const focus = page.getByRole('dialog', { name: 'Deck 大图预览' });
      await expect(focus).toBeVisible();
      const bounds = await focus.boundingBox();
      expect(bounds!.y).toBe(0);
      expect(bounds!.height).toBe(size.height);
      const preview = focus.locator('.slide-content');
      expect((await preview.boundingBox())!.height).toBeGreaterThan(
        size.height - (size.width < 700 ? 210 : 100),
      );
      const image = await focus.locator('.rendered-page').boundingBox();
      expect(image!.y + image!.height).toBeLessThanOrEqual(size.height);
      await focus.getByRole('button', { name: '下一页', exact: true }).click();
      await expect(focus).toContainText('第 2 / 10 页');
      await focus.getByRole('button', { name: '上一页', exact: true }).click();
      await expect(focus).toContainText('第 1 / 10 页');
      await clickImage(true);
      await expect(focus).toContainText('第 2 / 10 页');
      await page.keyboard.press('ArrowDown');
      await expect(focus).toContainText('第 3 / 10 页');
      await page.keyboard.press('ArrowUp');
      await expect(focus).toContainText('第 2 / 10 页');
      await clickImage(false);
      await expect(focus).toContainText('第 1 / 10 页');
      await focus.locator('.slide-list > button').last().click();
      await expect(focus).toContainText('第 10 / 10 页');
      await clickImage(true);
      await page.keyboard.press('ArrowDown');
      await expect(focus).toContainText('第 10 / 10 页');
      await page.keyboard.press('ArrowUp');
      await expect(focus).toContainText('第 9 / 10 页');
      await focus.locator('.slide-list > button').first().click();
      await expect(focus).toContainText('第 1 / 10 页');
      if (size.width === 1024) {
        // Editors and evidence must remain operable above the focus-preview layer.
        await focus.getByRole('button', { name: '编辑文字', exact: true }).click();
        const editor = page.getByRole('dialog', { name: '编辑本页文字' });
        await expect(editor.getByLabel('标题 1', { exact: true })).toBeVisible();
        await editor.getByLabel('标题 1', { exact: true }).press('ArrowDown');
        await expect(page).toHaveURL(new RegExp(`slide=${ready.slides[0].id}`));
        await editor.getByRole('button', { name: '取消', exact: true }).click();
        await focus.locator('.slide-sources').getByRole('button').first().click();
        await page.getByRole('button', { name: '关闭引用', exact: true }).click();
        await focus.locator('.slide-content').evaluate((el) => {
          el.scrollTop = 0;
        });
      }
      if (size.width === 1024) await page.screenshot({ path: 'test-results/deck-ipad-focus.png' });
      if (size.width === 390) await page.screenshot({ path: 'test-results/deck-mobile-focus.png' });
      await page.keyboard.press('Escape');
      await expect(focus).not.toBeVisible();
      await expect(viewer.getByRole('button', { name: '专注预览', exact: true })).toBeFocused();
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    // Cancel is a safe no-op; deleting a stopped sibling preserves the ready Deck.
    await go(queued.id);
    await viewer.getByRole('button', { name: '删除 Deck', exact: true }).click();
    await page
      .getByRole('dialog', { name: '删除 Deck？' })
      .getByRole('button', { name: '取消' })
      .click();
    expect((await request.get(`/api/decks/${queued.id}`)).ok()).toBeTruthy();
    await viewer.getByRole('button', { name: '删除 Deck', exact: true }).click();
    await page.getByRole('button', { name: '确认删除 Deck', exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/notebooks/${notebook.id}$`));
    expect((await request.get(`/api/decks/${queued.id}`)).status()).toBe(404);
    expect((await request.get(ready.pdf_export!.download_url)).ok()).toBeTruthy();
    // Studio also provides deletion without opening the Deck.
    await expect(page.locator('.deck-card')).toHaveCount(1);
    await page
      .locator('.deck-card')
      .getByRole('button', { name: /^删除 Deck ·/ })
      .click();
    await page.getByRole('button', { name: '确认删除 Deck', exact: true }).click();
    await expect(page.locator('.deck-card')).toHaveCount(0);
    expect((await request.get(`/api/decks/${first.id}`)).status()).toBe(404);
    expect((await request.get(ready.pdf_export!.download_url)).status()).toBe(404);
    expect((await request.get(`/api/sources/${upload.source.id}`)).ok()).toBeTruthy();
  } finally {
    await request.put(taskEndpoint, { data: { concurrency: taskSettings.concurrency } });
    for (const id of [first.id, queued.id]) await request.delete(`/api/decks/${id}`);
    await request.delete(`/api/notebooks/${notebook.id}`);
  }
});
