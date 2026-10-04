import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import DeckDiagnostics from './DeckDiagnostics';
import { api } from './api';
import { applyLanguage } from './i18n';
vi.mock('./api', async (original) => ({
  ...(await original<typeof import('./api')>()),
  api: vi.fn(),
}));
test('failure details load on demand, translate, show the page and support refresh/download', async () => {
  await applyLanguage('zh-CN');
  vi.mocked(api).mockResolvedValue({
    jobs: [],
    slides: [{ id: 'page', page: 7 }],
    attempts: [
      {
        id: 1,
        stage: 'SlideSpec',
        subject_id: 'page',
        outcome: 'invalid',
        attempt: 2,
        elapsed_ms: 6100,
        created_at: '2026-10-03T10:00:00Z',
        issues: [{ code: 'copy_budget', path: ['content_elements'] }],
      },
    ],
    omitted_attempts: 0,
  });
  render(<DeckDiagnostics deckId="deck" />);
  expect(api).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '查看失败详情' }));
  expect(await screen.findByText(/页面文字超过阅读预算/)).toBeVisible();
  expect(screen.getByText(/创作逐页内容 · 第 7 页/)).toBeVisible();
  expect(screen.getByText(/第 2 次尝试 · 6.1 秒/)).toBeVisible();
  expect(screen.getByRole('link', { name: '下载本 Deck 诊断报告' })).toHaveAttribute(
    'href',
    '/api/decks/deck/diagnostics?download=true',
  );
  fireEvent.click(screen.getByRole('button', { name: '刷新详情' }));
  await waitFor(() => expect(api).toHaveBeenCalledTimes(2));
  await applyLanguage('en');
  expect(await screen.findByText(/Page copy exceeds the reading budget/)).toBeVisible();
  expect(screen.getByText(new Date('2026-10-03T10:00:00Z').toLocaleString('en'))).toBeVisible();
  await applyLanguage('de');
  expect(screen.getByText(new Date('2026-10-03T10:00:00Z').toLocaleString('de'))).toBeVisible();
  expect(screen.getByText(/6,1/)).toBeVisible();
  await applyLanguage('zh-CN');
});
