import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import DeckSources from './DeckSources';
import { api, ApiError, type DeckSources as Sources } from './api';
vi.mock('./api', async (original) => ({
  ...(await original<typeof import('./api')>()),
  api: vi.fn(),
}));
beforeEach(() => vi.mocked(api).mockReset());
const sample: Sources = {
  historical: false,
  knowledge: [{ id: 'k', title: 'Saved knowledge title', revision: 3, available: true }],
  sources: [
    {
      id: 's',
      title: 'My book',
      type: 'pdf',
      selection: 'chapters',
      first_block_id: 'b1',
      available: true,
      whole_work_background: true,
      chapters: [
        {
          id: 'n',
          title: 'Chapter',
          path: ['Part', 'Chapter'],
          first_block_id: 'b2',
          available: true,
        },
      ],
    },
  ],
};
const expand = () => {
  const details = screen.getByText('查看 Deck 来源').closest('details')!;
  details.open = true;
  fireEvent(details, new Event('toggle'));
};
test('sources load on demand and retain chapter paths, knowledge revision and navigation', async () => {
  vi.mocked(api).mockResolvedValue(sample);
  const openSource = vi.fn(),
    openKnowledge = vi.fn();
  render(<DeckSources id="deck" onOpenSource={openSource} onOpenKnowledge={openKnowledge} />);
  expect(api).not.toHaveBeenCalled();
  expand();
  fireEvent.click(await screen.findByRole('button', { name: 'Part › Chapter' }));
  expect(openSource).toHaveBeenCalledWith('s', 'b2');
  fireEvent.click(screen.getByRole('button', { name: 'My book' }));
  expect(openSource).toHaveBeenCalledWith('s', 'b1');
  fireEvent.click(screen.getByRole('button', { name: '知识 · Saved knowledge title' }));
  expect(openKnowledge).toHaveBeenCalledWith('k');
  expect(screen.getByText('生成时为第 3 版')).toBeVisible();
  expect(screen.getByText('同时结合了整份资料的背景。')).toBeVisible();
});
test('source errors can retry and unavailable historical names remain visible', async () => {
  vi.mocked(api).mockRejectedValue(new ApiError('NETWORK_ERROR'));
  render(<DeckSources id="deck" onOpenSource={vi.fn()} />);
  expand();
  await screen.findByRole('alert');
  vi.mocked(api).mockResolvedValue({
    ...sample,
    historical: true,
    sources: sample.sources.map((s) => ({
      ...s,
      available: false,
      chapters: s.chapters.map((c) => ({ ...c, available: false })),
    })),
  });
  fireEvent.click(screen.getByRole('button', { name: '重试' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'My book' })).toBeDisabled());
  expect(screen.getByRole('button', { name: 'Part › Chapter' })).toBeDisabled();
  expect(screen.getByText('旧 Deck 的来源名称根据仍保留的资料还原。')).toBeVisible();
});
