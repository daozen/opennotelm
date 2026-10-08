import { test, expect } from '@playwright/test';
import type { Deck } from '../src/api';

test('edit, regenerate independent layers, AI revise, reorder and delete only affect the chosen page', async ({
  page,
  request,
}) => {
  test.setTimeout(120000);
  for (const role of ['language', 'embedding', 'image']) {
    expect(
      (
        await request.post('/api/settings/models/test', {
          data: {
            role,
            base_url: 'http://127.0.0.1:4301/v1',
            model_id: 'test-model',
            api_key: 'test-only-key',
          },
        })
      ).ok(),
    ).toBeTruthy();
  }
  const title = `逐页编辑 ${Date.now()}`;
  const notebook = await (await request.post('/api/notebooks', { data: { title } })).json();
  const upload = await (
    await request.post(`/api/notebooks/${notebook.id}/sources/upload`, {
      multipart: {
        file: {
          name: 'revision.md',
          mimeType: 'text/markdown',
          buffer: Buffer.from(
            `# ${title}\n\nDaily practice accumulates over time.\n\nReflection improves understanding.\n\nSmall progress becomes meaningful through consistency.`,
          ),
        },
      },
    })
  ).json();
  await expect
    .poll(async () => (await (await request.get(`/api/jobs/${upload.job.id}`)).json()).status)
    .toBe('completed');
  const created = await (
    await request.post(`/api/notebooks/${notebook.id}/decks`, {
      data: { slide_count: 10, render_mode: 'native' },
    })
  ).json();
  const read = async (): Promise<Deck> => (await request.get(`/api/decks/${created.id}`)).json();
  await page.goto('/');
  await page.getByRole('button', { name: `打开 ${title}`, exact: true }).click();
  await page.locator('.artifact-grid .deck-open').click();
  const viewer = page.getByRole('region', { name: 'Visual Deck', exact: true });
  await expect(viewer.getByRole('link', { name: '下载 PDF · 10 页' })).toBeVisible({
    timeout: 60000,
  });
  const original = await read();
  const selected = original.slides[1].id;
  await viewer.getByRole('navigation', { name: 'Deck 页面' }).getByRole('button').nth(1).click();
  const changed = async (prior: Deck) => {
    await expect
      .poll(
        async () => {
          const current = await read();
          return (
            current.job?.status === 'completed' &&
            current.pdf_export?.id !== prior.pdf_export?.id &&
            current.status === 'ready'
          );
        },
        { timeout: 20000 },
      )
      .toBeTruthy();
    const value = await read();
    for (const slide of value.slides)
      if (slide.id !== selected) expect(slide).toEqual(prior.slides.find((s) => s.id === slide.id));
    expect(value.style).toEqual(original.style);
    expect((await request.get(prior.pdf_export!.download_url!)).status()).toBe(409);
    await expect(viewer.getByRole('link', { name: '下载 PDF · 10 页' })).toBeVisible();
    return value;
  };
  await viewer.getByRole('button', { name: '编辑文字', exact: true }).click();
  const editor = page.getByRole('dialog', { name: '编辑本页文字' });
  await editor.getByLabel('标题 1', { exact: true }).fill('持续实践，让理解生长');
  await editor.getByRole('button', { name: '保存并更新本页' }).click();
  let saved = await changed(original);
  expect(saved.slides[1].assets).toEqual(original.slides[1].assets);
  expect(saved.slides[1].citations).toEqual(original.slides[1].citations);
  await expect(viewer.getByRole('navigation').getByText('持续实践，让理解生长')).toBeVisible();
  await viewer.getByRole('button', { name: '重做视觉', exact: true }).click();
  const visual = await changed(saved);
  expect(visual.slides[1].spec).toEqual(saved.slides[1].spec);
  expect(visual.slides[1].assets).toEqual(saved.slides[1].assets);
  saved = visual;
  await viewer.getByRole('button', { name: '重生成图片', exact: true }).click();
  const image = await changed(saved);
  expect(image.slides[1].spec).toEqual(saved.slides[1].spec);
  expect(image.slides[1].assets[0].id).not.toBe(saved.slides[1].assets[0].id);
  saved = image;
  await viewer.getByRole('button', { name: '重写内容', exact: true }).click();
  saved = await changed(saved);
  expect(saved.slides[1].spec!.content_elements[0].text).toContain('（修订）');
  await viewer.getByRole('button', { name: '用 AI 修改', exact: true }).click();
  await page.getByLabel('本页修改要求').fill('更多留白，让视觉层次更清楚。');
  await page.getByRole('button', { name: '开始修改本页' }).click();
  const revised = await changed(saved);
  expect(revised.slides[1].spec).toEqual(saved.slides[1].spec);
  await viewer.getByRole('button', { name: '上移本页', exact: true }).click();
  await expect.poll(async () => (await read()).slides[0].id).toBe(selected);
  await expect(viewer.getByRole('link', { name: '下载 PDF · 10 页' })).toBeVisible({
    timeout: 15000,
  });
  const reordered = await read();
  expect(reordered.slides.map((s) => s.render!.id).sort()).toEqual(
    revised.slides.map((s) => s.render!.id).sort(),
  );
  await viewer.getByRole('button', { name: '删除本页', exact: true }).click();
  await page.getByRole('button', { name: '确认删除页面' }).click();
  await expect(viewer.getByRole('link', { name: '下载 PDF · 9 页' })).toBeVisible({
    timeout: 15000,
  });
  const deleted = await read();
  expect(deleted.slides).toHaveLength(9);
  expect(deleted.slides.map((s) => s.render!.id).sort()).toEqual(
    reordered.slides
      .filter((s) => s.id !== selected)
      .map((s) => s.render!.id)
      .sort(),
  );
  expect((await request.get(reordered.pdf_export!.download_url!)).status()).toBe(409);
  await viewer.locator('.slide-actions').scrollIntoViewIfNeeded();
  await page.screenshot({ path: 'test-results/slide-revisions.png', fullPage: true });
  const deckUrl = page.url();
  await page.reload();
  await expect(page).toHaveURL(deckUrl);
  await expect(viewer.getByRole('link', { name: '下载 PDF · 9 页' })).toBeVisible();
  await request.delete(`/api/notebooks/${notebook.id}`);
});
