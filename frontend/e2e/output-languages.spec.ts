import { test, expect } from '@playwright/test';
import { languages } from '../src/languages';

test('new content follows the interface or an explicit choice across chat, knowledge, summary, outline and Deck', async ({
  page,
  request,
}) => {
  test.setTimeout(120000);
  await request.put('/api/settings/preferences', { data: { ui_language: 'zh-CN' } });
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
  const notebook = await (
    await request.post('/api/notebooks', { data: { title: `Output languages ${Date.now()}` } })
  ).json();
  try {
    const imported = await (
      await request.post(`/api/notebooks/${notebook.id}/sources/upload`, {
        multipart: {
          file: {
            name: 'language-source.txt',
            mimeType: 'text/plain',
            buffer: Buffer.from(
              `耐心意味着保持长期思考。长期复利最大的优势来自时间跨度。测试批次：${notebook.id}。`,
            ),
          },
        },
      })
    ).json();
    await expect
      .poll(async () => (await (await request.get(`/api/jobs/${imported.job.id}`)).json()).status)
      .toBe('completed');
    await page.goto(`/notebooks/${notebook.id}`);
    const output = page.locator('.output-language-picker select');
    await expect(output).toHaveValue('interface');
    await expect(output.locator('option')).toHaveCount(13);
    const ui = page.locator('.app-header select');
    await ui.selectOption('en');
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await page.getByLabel('Ask your sources').fill('保持草稿');
    await output.selectOption('fr');
    await ui.selectOption('ar');
    await expect(output).toHaveValue('fr');
    await expect(page.locator('.chat-composer textarea')).toHaveValue('保持草稿');
    await ui.selectOption('zh-CN');
    let answers = 0;
    const ask = async (code: string, choice: string) => {
      await output.selectOption(choice);
      await page.getByLabel('向资料提问').fill('长期复利的优势是什么？');
      const outgoing = page.waitForRequest(
        (req) => req.method() === 'POST' && req.url().endsWith('/chat'),
      );
      await page.getByRole('button', { name: '发送问题', exact: true }).click();
      expect((await outgoing).postDataJSON().language).toBe(code);
      answers++;
      await expect
        .poll(async () => {
          const result = await (await request.get(`/api/notebooks/${notebook.id}/chat`)).json();
          return result.messages.filter((m: { role: string }) => m.role === 'assistant').length;
        })
        .toBe(answers);
      await expect(page.locator('.chat-progress')).toHaveCount(0);
    };
    await ask('zh-CN', 'interface');
    for (const language of languages) await ask(language.code, language.code);
    await output.selectOption('hi');
    await page
      .getByRole('navigation', { name: '笔记本内容' })
      .getByRole('button', { name: /^知识/ })
      .click();
    const knowledgeRequest = page.waitForRequest(
      (req) => req.method() === 'POST' && req.url().endsWith('/knowledge'),
    );
    const knowledgeResponse = page.waitForResponse(
      (res) => res.request().method() === 'POST' && res.url().endsWith('/knowledge'),
    );
    await page.getByRole('button', { name: '生成知识页', exact: true }).click();
    expect((await knowledgeRequest).postDataJSON().language).toBe('hi');
    const createdResponse = await knowledgeResponse;
    expect(createdResponse.ok()).toBeTruthy();
    const created = await createdResponse.json();
    await expect
      .poll(async () => (await (await request.get(`/api/jobs/${created.job.id}`)).json()).status)
      .toBe('completed');
    expect(
      (await (await request.get(`/api/knowledge/${created.page.id}`)).json()).generation_metadata
        .language,
    ).toBe('hi');
    await expect(page.locator('.knowledge-content')).not.toBeEmpty();
    await page
      .getByRole('navigation', { name: '笔记本内容' })
      .getByRole('button', { name: '资料', exact: true })
      .click();
    await page.locator('.source-open').first().click();
    for (const [code, kind, label] of [
      ['ar', 'summary', '总结整份资料'],
      ['ja', 'outline', '整份资料提纲'],
    ]) {
      await output.selectOption(code);
      const transformationRequest = page.waitForRequest(
        (req) => req.method() === 'POST' && req.url().endsWith('/transformations'),
      );
      await page.getByRole('button', { name: label, exact: true }).click();
      const body = (await transformationRequest).postDataJSON();
      expect(body.language).toBe(code);
      expect(body.kind).toBe(kind);
      await expect(page.locator('.transformation-content')).toBeVisible();
      await page.getByRole('button', { name: '关闭临时结果' }).click();
    }
    await output.selectOption('ko');
    await page.getByRole('button', { name: '生成 Visual Deck', exact: true }).click();
    const deck = page.getByRole('dialog', { name: '生成 Visual Deck' });
    await expect(deck.getByLabel('Deck 语言')).toHaveValue('ko');
    await expect(deck.getByLabel('Deck 语言').locator('option')).toHaveCount(12);
    await deck.getByRole('button', { name: '取消', exact: true }).click();
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(output).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
    ).toBeTruthy();
    await page.screenshot({ path: 'test-results/output-language-mobile.png', fullPage: true });
  } finally {
    await request.put('/api/settings/preferences', { data: { ui_language: 'zh-CN' } });
    await request.delete(`/api/notebooks/${notebook.id}`);
  }
});
