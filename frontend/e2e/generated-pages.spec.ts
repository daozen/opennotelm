import { test, expect } from '@playwright/test';
import type { Deck } from '../src/api';

test('whole-page copies preserve the original, text edits regenerate one page, and failures retry', async ({
  page,
  request,
}) => {
  test.setTimeout(120000);
  const configure = async (role: string, model = 'test-model') => {
    expect(
      (
        await request.post('/api/settings/models/test', {
          data: {
            role,
            base_url: 'http://127.0.0.1:4301/v1',
            model_id: model,
            api_key: 'test-only-key',
          },
        })
      ).ok(),
    ).toBeTruthy();
  };
  for (const role of ['language', 'embedding', 'image']) await configure(role);
  const title = `整页生成 ${Date.now()}`;
  const notebook = await (await request.post('/api/notebooks', { data: { title } })).json();
  const upload = await (
    await request.post(`/api/notebooks/${notebook.id}/sources/upload`, {
      multipart: {
        file: {
          name: 'whole-pages.md',
          mimeType: 'text/markdown',
          buffer: Buffer.from(
            `# ${title}\n\nSmall improvements accumulate over time.\n\nDaily reflection helps learning.`,
          ),
        },
      },
    })
  ).json();
  await expect
    .poll(async () => (await (await request.get(`/api/jobs/${upload.job.id}`)).json()).status)
    .toBe('completed');
  const original = await (
    await request.post(`/api/notebooks/${notebook.id}/decks`, {
      data: { slide_count: 10, render_mode: 'native' },
    })
  ).json();
  const readOriginal = async () => (await request.get(`/api/decks/${original.id}`)).json();
  await expect
    .poll(
      async () => {
        const value = await readOriginal();
        return value.status === 'ready' && value.job?.status === 'completed';
      },
      { timeout: 60000 },
    )
    .toBeTruthy();
  const baseline = await readOriginal();
  await page.goto(`/notebooks/${notebook.id}/decks/${original.id}`);
  const viewer = page.getByRole('region', { name: 'Visual Deck', exact: true });
  await viewer.locator('.deck-more-actions > summary').click();
  await viewer.getByRole('button', { name: '生成整页副本', exact: true }).click();
  await expect(page).not.toHaveURL(new RegExp(original.id));
  await expect(viewer.getByRole('link', { name: '下载 PDF · 10 页' })).toBeVisible({
    timeout: 30000,
  });
  const deckId = new URL(page.url()).pathname.split('/').at(-1)!;
  const read = async (): Promise<Deck> => (await request.get(`/api/decks/${deckId}`)).json();
  const generated = await read();
  expect(generated.render_mode).toBe('generated_page');
  expect(generated.generation_metadata?.restyled).toBe(true);
  expect(generated.generation_metadata?.visual_style_version).toBe('content-adaptive-style-v1');
  expect(Object.keys(generated.art_direction!.metrics.forms).length).toBeGreaterThanOrEqual(5);
  expect(Object.keys(generated.art_direction!.metrics.viewpoints).length).toBeGreaterThanOrEqual(3);
  await viewer.getByText('查看视觉编排', { exact: true }).click();
  await expect(viewer.locator('.deck-visual-plan')).toContainText('实际画面仍需逐页核对');
  await viewer.locator('.deck-more-actions > summary').click();
  await expect(
    viewer.getByRole('button', { name: '仅更新视觉，生成副本', exact: true }),
  ).toBeEnabled();
  expect(await readOriginal()).toEqual(baseline);
  await expect(viewer.getByRole('button', { name: '重生成图片', exact: true })).toHaveCount(0);
  await expect(viewer.getByRole('link', { name: '预览 PDF', exact: true })).toBeVisible();
  // A long thumbnail rail must never scroll the preview out of the workspace.
  await page.setViewportSize({ width: 1440, height: 900 });
  await viewer.getByText('查看视觉编排', { exact: true }).click();
  const rail = viewer.getByRole('navigation', { name: 'Deck 页面' });
  const preview = viewer.locator('.slide-content');
  await expect.poll(() => rail.evaluate((el) => el.scrollHeight > el.clientHeight)).toBeTruthy();
  const workspace = page.locator('.chat-panel');
  const initialScroll = await workspace.evaluate((el) => el.scrollTop);
  await preview.evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  await rail.evaluate((el) => {
    el.scrollTop = el.scrollHeight;
  });
  await rail.getByRole('button').last().click();
  await expect.poll(() => preview.evaluate((el) => el.scrollTop)).toBe(0);
  await expect.poll(() => workspace.evaluate((el) => el.scrollTop)).toBe(initialScroll);
  await expect(rail.getByRole('button').last()).toHaveAttribute('aria-current', 'page');
  await expect(rail.getByRole('button').last()).toBeInViewport();
  await expect
    .poll(() =>
      rail.evaluate((el) => {
        const active = el.querySelector('.active')!.getBoundingClientRect();
        const bounds = el.getBoundingClientRect();
        return active.top >= bounds.top && active.bottom <= bounds.bottom + 1;
      }),
    )
    .toBeTruthy();
  const imageBounds = await preview.locator('.rendered-page').boundingBox();
  expect(imageBounds!.y).toBeGreaterThan(0);
  expect(imageBounds!.y).toBeLessThan(900);
  const previewBounds = await preview.boundingBox();
  expect(imageBounds!.y + imageBounds!.height).toBeLessThanOrEqual(
    previewBounds!.y + previewBounds!.height,
  );
  await page.screenshot({ path: 'test-results/deck-independent-scroll.png' });
  await expect(rail.getByRole('button').last()).toBeInViewport();
  await rail.getByRole('button').first().click();
  const selected = generated.slides[0];
  await viewer.getByRole('button', { name: '编辑文字', exact: true }).click();
  const editor = page.getByRole('dialog', { name: '编辑本页文字' });
  await expect(editor).toContainText('重新生成包含新文字的完整页面');
  await editor.getByLabel('标题 1', { exact: true }).fill('完整页面的新标题');
  await editor.getByRole('button', { name: '保存并更新本页' }).click();
  await expect
    .poll(
      async () => {
        const value = await read();
        return (
          value.status === 'ready' &&
          value.job?.status === 'completed' &&
          value.pdf_export?.status === 'ready' &&
          value.pdf_export.id !== generated.pdf_export?.id
        );
      },
      { timeout: 20000 },
    )
    .toBeTruthy();
  await expect(viewer.getByRole('link', { name: '下载 PDF · 10 页' })).toBeVisible();
  const edited = await read();
  expect(edited.slides[0].assets[0].id).not.toBe(selected.assets[0].id);
  expect(edited.slides[0].citations).toEqual(selected.citations);
  expect(edited.slides.slice(1)).toEqual(generated.slides.slice(1));
  await viewer.getByText('查看页面文字稿', { exact: true }).click();
  await expect(viewer.locator('.slide-text-details')).toContainText('完整页面的新标题');
  await configure('image', 'image-fails-after-probe');
  await viewer.getByRole('button', { name: '重做视觉', exact: true }).click();
  await expect(viewer.getByRole('button', { name: '重试本页', exact: true })).toBeEnabled({
    timeout: 15000,
  });
  await expect(viewer.getByRole('button', { name: '不使用失败的图片继续' })).toHaveCount(0);
  await expect(viewer.locator('.rendered-page')).toBeVisible();
  await viewer.getByRole('button', { name: '查看失败详情', exact: true }).click();
  const details = viewer.getByRole('region', { name: '失败详情' });
  await expect(details.getByText('模型请求失败', { exact: false }).first()).toBeVisible();
  await expect(details.getByRole('link', { name: '下载本 Deck 诊断报告' })).toBeVisible();
  const diagnosticResponse = await request.get(`/api/decks/${deckId}/diagnostics`);
  expect(diagnosticResponse.ok()).toBeTruthy();
  expect(
    (await diagnosticResponse.json()).attempts.some(
      (attempt: { outcome: string; subject_id?: string }) =>
        attempt.outcome === 'request_failed' && attempt.subject_id === selected.id,
    ),
  ).toBeTruthy();
  await configure('image');
  await viewer.getByRole('button', { name: '重试本页', exact: true }).click();
  await expect
    .poll(
      async () => {
        const value = await read();
        return value.status === 'ready' && value.job?.status === 'completed';
      },
      { timeout: 20000 },
    )
    .toBeTruthy();
  expect((await read()).slides.slice(1)).toEqual(generated.slides.slice(1));
  const address = page.url();
  await page.reload();
  await expect(page).toHaveURL(address);
  await expect(viewer.getByText('查看页面文字稿', { exact: true })).toBeVisible();
  await expect(viewer.getByText('查看视觉编排', { exact: true })).toBeVisible();
  const refinedBaseline = await read();
  await viewer.locator('.deck-more-actions > summary').click();
  await viewer.getByRole('button', { name: '仅更新视觉，生成副本', exact: true }).click();
  await expect(page).not.toHaveURL(new RegExp(deckId));
  await expect(viewer.getByRole('link', { name: '下载 PDF · 10 页' })).toBeVisible({
    timeout: 30000,
  });
  expect(await read()).toEqual(refinedBaseline);
  await viewer.locator('.deck-more-actions > summary').click();
  await viewer.getByRole('button', { name: '重新解读并生成副本', exact: true }).click();
  await expect(viewer.getByRole('link', { name: '下载 PDF · 10 页' })).toBeVisible({
    timeout: 30000,
  });
  const contentCopyId = new URL(page.url()).pathname.split('/').at(-1)!;
  const contentCopy = await (await request.get(`/api/decks/${contentCopyId}`)).json();
  expect(contentCopy.generation_metadata.rewritten_content).toBeTruthy();
  expect(contentCopy.generation_metadata.restyled).toBe(true);
  expect(contentCopy.generation_metadata.visual_style_version).toBe('content-adaptive-style-v1');
  expect(contentCopy.art_direction.version).toBe('deck-art-v2');
  expect(await read()).toEqual(refinedBaseline);
  await page.screenshot({ path: 'test-results/generated-page-editor.png', fullPage: true });
  await request.delete(`/api/notebooks/${notebook.id}`);
});
