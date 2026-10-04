import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';

test('separate source and hierarchical chapter Decks retain independent exports and scopes', async ({
  page,
  request,
}) => {
  test.setTimeout(180000);
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
  const title = `分别生成与目录树 ${Date.now()}`;
  const notebook = await (await request.post('/api/notebooks', { data: { title } })).json();
  const upload = await (
    await request.post(`/api/notebooks/${notebook.id}/sources/upload`, {
      multipart: {
        file: {
          name: 'hierarchy.pdf',
          mimeType: 'application/pdf',
          buffer: await readFile(
            fileURLToPath(new URL('./fixtures/hierarchy.pdf', import.meta.url)),
          ),
        },
      },
    })
  ).json();
  const other = await (
    await request.post(`/api/notebooks/${notebook.id}/sources/upload`, {
      multipart: {
        file: {
          name: 'other.md',
          mimeType: 'text/markdown',
          buffer: Buffer.from(
            `# Other ${Date.now()}\n\nOTHER_ONLY: small improvements accumulate over time.`,
          ),
        },
      },
    })
  ).json();
  for (const result of [upload, other]) {
    if (result.duplicate)
      await request.post(`/api/notebooks/${notebook.id}/sources/${result.source.id}`, { data: {} });
    await expect
      .poll(
        async () => (await (await request.get(`/api/sources/${result.source.id}`)).json()).status,
      )
      .toBe('indexed');
  }
  const read = async (id: string) => (await request.get(`/api/decks/${id}`)).json();
  const waitDecks = async (batch: { decks: { id: string }[] }) => {
    for (const deck of batch.decks)
      await expect
        .poll(
          async () => {
            const result = await read(deck.id);
            return result.status === 'ready' && result.job?.status === 'completed';
          },
          { timeout: 60000 },
        )
        .toBeTruthy();
  };
  try {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(`/notebooks/${notebook.id}`);
    await expect(page.locator('.source-open')).toHaveCount(2);
    await page.getByRole('button', { name: '生成 Visual Deck', exact: true }).click();
    let dialog = page.getByRole('dialog', { name: '生成 Visual Deck' });
    await dialog.getByRole('radio', { name: '每份资料 / 章节分别生成' }).check();
    await dialog.getByRole('radio', { name: '使用资料 / 章节名称' }).check();
    await dialog.getByRole('radio', { name: '10 页', exact: true }).check();
    await expect(dialog).toContainText('将生成 2 份 Deck，每份 10 页，共 20 页。');
    const posted = page.waitForResponse(
      (r) => r.request().method() === 'POST' && r.url().endsWith('/decks/batch'),
    );
    await dialog.getByRole('button', { name: '开始生成', exact: true }).click();
    const firstResponse = await posted;
    expect(firstResponse.status()).toBe(202);
    const sources = await firstResponse.json();
    const notebookSources = await (
      await request.get(`/api/notebooks/${notebook.id}/sources`)
    ).json();
    expect(
      sources.decks.map((d: { source_scope: { source_id: string } }) => d.source_scope.source_id),
    ).toEqual(notebookSources.map((source: { id: string }) => source.id));
    const retry = await request.post(`/api/notebooks/${notebook.id}/decks/batch`, {
      data: firstResponse.request().postDataJSON(),
    });
    expect((await retry.json()).decks.map((d: { id: string }) => d.id)).toEqual(
      sources.decks.map((d: { id: string }) => d.id),
    );
    await waitDecks(sources);
    await expect(page.locator('.deck-library .deck-open')).toHaveCount(2);
    for (const created of sources.decks) {
      const deck = await read(created.id);
      expect(deck.title).toBe(
        notebookSources.find((s: { id: string }) => s.id === created.source_scope.source_id).title,
      );
      expect(deck.generation_metadata.source_ids).toEqual([created.source_scope.source_id]);
      expect((await request.get(deck.pdf_export.download_url)).ok()).toBeTruthy();
    }
    await page.reload();
    await expect(page.locator('.deck-library .deck-open')).toHaveCount(2);
    await page.getByRole('button', { name: '生成 Visual Deck', exact: true }).click();
    dialog = page.getByRole('dialog', { name: '生成 Visual Deck' });
    await dialog.getByLabel('Deck 内容范围').selectOption(`source:${upload.source.id}`);
    await dialog.getByRole('radio', { name: '每份资料 / 章节分别生成' }).check();
    await dialog.getByRole('radio', { name: '使用资料 / 章节名称' }).check();
    await dialog.getByRole('checkbox', { name: '只使用所选章节' }).check();
    const tree = dialog.getByRole('tree', { name: '章节目录' });
    await tree.getByRole('checkbox', { name: '章节 · Part One', exact: true }).check();
    await expect(
      tree.getByRole('checkbox', { name: '章节 · Section Beta', exact: true }),
    ).toBeChecked();
    await tree.getByRole('checkbox', { name: '章节 · Section Alpha', exact: true }).uncheck();
    await expect(
      tree.getByRole('checkbox', { name: '章节 · Part One', exact: true }),
    ).toHaveAttribute('aria-checked', 'mixed');
    await dialog.getByLabel('按目录层级选择').selectOption('2');
    await expect(
      tree.getByRole('checkbox', { name: '章节 · Detail Alpha', exact: true }),
    ).toBeChecked();
    await expect(dialog).toContainText('已选 2 个章节，分别生成 2 份 Deck。');
    await dialog.getByRole('radio', { name: '10 页', exact: true }).check();
    await page.screenshot({ path: 'test-results/deck-batch-tree.png' });
    await page.setViewportSize({ width: 390, height: 844 });
    await tree.scrollIntoViewIfNeeded();
    expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBeTruthy();
    const box = await tree
      .getByRole('checkbox', { name: '章节 · Section Alpha', exact: true })
      .boundingBox();
    const text = await tree.getByText('Section Alpha · 第 2 页', { exact: true }).boundingBox();
    expect(box!.x).toBeLessThan(text!.x);
    expect(Math.abs(box!.y - text!.y)).toBeLessThan(10);
    await page.screenshot({ path: 'test-results/deck-batch-tree-mobile.png' });
    await page.setViewportSize({ width: 1440, height: 1000 });
    const secondPost = page.waitForResponse(
      (r) => r.request().method() === 'POST' && r.url().endsWith('/decks/batch'),
    );
    await dialog.getByRole('button', { name: '开始生成', exact: true }).click();
    const chapters = await (await secondPost).json();
    expect(chapters.decks).toHaveLength(2);
    await waitDecks(chapters);
    const blocks = await (await request.get(`/api/sources/${upload.source.id}/blocks`)).json();
    const contents: string[] = [];
    for (const created of chapters.decks) {
      const deck = await read(created.id);
      contents.push(
        blocks
          .filter((b: { id: string }) => deck.generation_metadata.block_ids.includes(b.id))
          .map((b: { text: string }) => b.text)
          .join('\n'),
      );
      expect(deck.pdf_export.page_count).toBe(10);
    }
    expect(contents[0]).toContain('ALPHA_ONLY');
    expect(contents[0]).toContain('ALPHA_DETAIL');
    expect(contents[0]).not.toContain('BETA_ONLY');
    expect(contents[1]).toContain('BETA_ONLY');
    expect(contents.join(' ')).not.toContain('PARENT_INTRO');
    expect(contents.join(' ')).not.toContain('GAMMA_EXCLUDED');
    await expect(page.locator('.deck-library .deck-open')).toHaveCount(4);
    await page.reload();
    await expect(page.locator('.deck-library .deck-open')).toHaveCount(4);
    await expect(page.getByRole('link', { name: '下载 PDF · 10 页', exact: true })).toBeVisible();
    const current = await read(chapters.decks[0].id);
    const manifest = await (await request.get(`/api/decks/${current.id}/sources`)).json();
    const selectedChapter = manifest.sources[0].chapters[0];
    expect(selectedChapter.number).toBe('1.1');
    expect(current.title).toBe(
      `${manifest.sources[0].title}-${selectedChapter.number}-${selectedChapter.title}`,
    );
    const sourceNamedDownload = page.waitForEvent('download');
    await page.getByRole('link', { name: '下载 PDF · 10 页', exact: true }).click();
    expect((await sourceNamedDownload).suggestedFilename()).toBe(`${current.title}.pdf`);
    const originalPdf = await (await request.get(current.pdf_export.download_url)).body();
    await page.getByText('查看 Deck 来源', { exact: true }).click();
    await expect(page.locator('.deck-sources')).toContainText(manifest.sources[0].title);
    const chapterLink = page
      .locator('.deck-sources')
      .getByRole('button', { name: selectedChapter.path.join(' › '), exact: true });
    await expect(chapterLink).toBeEnabled();
    await chapterLink.click();
    await expect(page).toHaveURL(
      new RegExp(`/sources/${upload.source.id}.*block=${selectedChapter.first_block_id}`),
    );
    await page.goBack();
    await page.getByRole('button', { name: '重命名 Deck' }).click();
    const rename = page.getByRole('dialog', { name: '重命名 Deck' });
    await rename.getByLabel('Deck 名称').fill('蜂蜜供品 · 深入解读');
    await rename.getByRole('button', { name: '保存名称' }).click();
    await expect(
      page.getByRole('heading', { name: '蜂蜜供品 · 深入解读', exact: true }),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByRole('heading', { name: '蜂蜜供品 · 深入解读', exact: true }),
    ).toBeVisible();
    const downloaded = page.waitForEvent('download');
    await page.getByRole('link', { name: '下载 PDF · 10 页', exact: true }).click();
    expect((await downloaded).suggestedFilename()).toBe('蜂蜜供品 · 深入解读.pdf');
    const renamed = await read(current.id);
    expect(renamed.pdf_export.id).toBe(current.pdf_export.id);
    expect(await (await request.get(renamed.pdf_export.download_url)).body()).toEqual(originalPdf);
    // Download saved artifacts together, with native browser streaming and frozen names.
    const studio = page.locator('#workspace-studio');
    await studio.getByRole('button', { name: '批量下载', exact: true }).click();
    await studio.getByRole('checkbox', { name: '选择全部可下载文件', exact: true }).check();
    await expect(studio.getByRole('button', { name: '下载所选（4）', exact: true })).toBeEnabled();
    const bundleDownload = page.waitForEvent('download');
    await studio.getByRole('button', { name: '下载所选（4）', exact: true }).click();
    const zipped = await bundleDownload;
    expect(zipped.suggestedFilename()).toBe(`${title}.zip`);
    const zipBytes = await readFile((await zipped.path())!);
    const extracted = JSON.parse(
      execFileSync(
        '../.venv/bin/python',
        [
          '-c',
          'import sys,json,hashlib,io,zipfile; z=zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read())); print(json.dumps({n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}))',
        ],
        { input: zipBytes },
      ).toString(),
    );
    expect(Object.keys(extracted)).toHaveLength(4);
    expect(extracted['蜂蜜供品 · 深入解读.pdf']).toBe(
      createHash('sha256').update(originalPdf).digest('hex'),
    );
    for (const created of [...sources.decks, ...chapters.decks]) {
      const saved = await read(created.id);
      const bytes = await (await request.get(saved.pdf_export.download_url)).body();
      expect(extracted[saved.pdf_export.filename]).toBe(
        createHash('sha256').update(bytes).digest('hex'),
      );
    }
    await expect(studio.getByRole('link', { name: '下载 ZIP', exact: true })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('button', { name: '演示文稿', exact: true }).click();
    expect(await studio.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBeTruthy();
    await page.screenshot({
      path: 'test-results/artifact-batch-download-mobile.png',
      fullPage: true,
    });
    await studio.getByRole('button', { name: '取消选择', exact: true }).click();
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.getByRole('button', { name: '工作区', exact: true }).click();
    await page.getByText('查看 Deck 来源', { exact: true }).click();
    await expect(page.locator('.deck-sources')).toContainText(selectedChapter.title);
    expect(
      await page.locator('.deck-view').evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBeTruthy();
    await page.screenshot({ path: 'test-results/deck-names-sources-tablet.png', fullPage: true });
  } finally {
    await request.delete(`/api/notebooks/${notebook.id}`);
  }
});
