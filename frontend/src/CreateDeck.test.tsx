import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import { CreateDeck } from './Deck';
import { api, ApiError, type Source } from './api';
import { applyLanguage } from './i18n';

vi.mock('./api', async (original) => ({
  ...(await original<typeof import('./api')>()),
  api: vi.fn(),
}));
beforeEach(() => vi.mocked(api).mockReset());
const sources: Source[] = ['first', 'second'].map((id) => ({
  id,
  type: 'pdf',
  title: id,
  enabled: true,
  status: 'indexed',
  original_filename: `${id}.pdf`,
  parser_version: 'pdf-v1',
}));

test('source batches show counts, keep drafts across languages and reuse the submission key after a network failure', async () => {
  vi.mocked(api)
    .mockRejectedValueOnce(new ApiError('NETWORK_ERROR'))
    .mockResolvedValueOnce({ batch_id: 'batch', decks: [{ id: 'd1' }, { id: 'd2' }] });
  const created = vi.fn();
  render(
    <CreateDeck
      notebookId="book"
      initialScope={{ kind: 'selected' }}
      initialLabel="Sources"
      sources={sources}
      pages={[]}
      onClose={() => {}}
      onCreated={created}
    />,
  );
  expect(screen.getByText('将生成 1 份 Deck，每份 15 页，共 15 页。')).toBeVisible();
  fireEvent.click(screen.getByRole('radio', { name: '每份资料 / 章节分别生成' }));
  expect(screen.getByText('将生成 2 份 Deck，每份 15 页，共 30 页。')).toBeVisible();
  fireEvent.change(screen.getByLabelText('Deck 补充说明'), {
    target: { value: 'Keep this draft' },
  });
  fireEvent.click(screen.getByRole('button', { name: '开始生成' }));
  await screen.findByRole('alert');
  expect(created).not.toHaveBeenCalled();
  const first = JSON.parse(vi.mocked(api).mock.calls[0][1]!.body as string);
  expect(vi.mocked(api).mock.calls[0][0]).toBe('/notebooks/book/decks/batch');
  expect(first.scope.source_ids).toEqual(['first', 'second']);
  expect(first.request_key).toMatch(/^[a-f0-9]{32}$/);
  await act(() => applyLanguage('en'));
  expect(
    screen.getByRole('radio', { name: 'Generate separately for each source / chapter' }),
  ).toBeChecked();
  expect(screen.getByLabelText('Deck instructions')).toHaveValue('Keep this draft');
  fireEvent.click(screen.getByRole('button', { name: 'Start generating' }));
  await waitFor(() => expect(created).toHaveBeenCalledWith({ id: 'd1' }, 2));
  expect(JSON.parse(vi.mocked(api).mock.calls[1][1]!.body as string).request_key).toBe(
    first.request_key,
  );
});

test('merged generation keeps its original endpoint and excludes unchecked sources', async () => {
  vi.mocked(api).mockResolvedValue({ id: 'merged' });
  render(
    <CreateDeck
      notebookId="book"
      initialScope={{ kind: 'selected' }}
      initialLabel="Sources"
      sources={sources}
      pages={[]}
      onClose={() => {}}
      onCreated={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByRole('checkbox', { name: '资料 · second' }));
  fireEvent.click(screen.getByRole('button', { name: '开始生成' }));
  await waitFor(() => expect(api).toHaveBeenCalledWith('/notebooks/book/decks', expect.anything()));
  const payload = JSON.parse(vi.mocked(api).mock.calls.at(-1)![1]!.body as string);
  expect(payload.scope).toEqual({ kind: 'selected', source_ids: ['first'] });
  expect(payload.request_key).toBeUndefined();
});

test('empty chapter choices block generation and switching mode retains the tree selection', async () => {
  vi.mocked(api).mockResolvedValue([
    { id: 'a', type: 'chapter', title: 'Alpha', depth: 1 },
    { id: 'b', type: 'chapter', title: 'Beta', depth: 1 },
  ]);
  render(
    <CreateDeck
      notebookId="book"
      initialScope={{ kind: 'nodes', source_id: 'first', node_ids: ['b'] }}
      initialLabel="Chapters"
      sources={sources}
      pages={[]}
      onClose={() => {}}
      onCreated={vi.fn()}
    />,
  );
  expect(await screen.findByRole('checkbox', { name: '章节 · Beta' })).toBeChecked();
  expect(screen.getByLabelText('Deck 内容范围')).toHaveValue('source:first');
  fireEvent.click(screen.getByRole('button', { name: '清空章节选择' }));
  expect(screen.getByRole('button', { name: '开始生成' })).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox', { name: '章节 · Alpha' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '章节 · Beta' }));
  fireEvent.click(screen.getByRole('radio', { name: '每份资料 / 章节分别生成' }));
  expect(screen.getByText('将生成 2 份 Deck，每份 15 页，共 30 页。')).toBeVisible();
  expect(screen.getByRole('checkbox', { name: '章节 · Alpha' })).toBeChecked();
  expect(screen.getByRole('checkbox', { name: '章节 · Beta' })).toBeChecked();
});

test('source naming is restricted per Deck and included in both generation modes', async () => {
  vi.mocked(api).mockResolvedValue({ batch_id: 'batch', decks: [{ id: 'd1' }] });
  render(
    <CreateDeck
      notebookId="book"
      initialScope={{ kind: 'selected' }}
      initialLabel="Sources"
      sources={sources}
      pages={[]}
      onClose={() => {}}
      onCreated={vi.fn()}
    />,
  );
  const sourceName = screen.getByRole('radio', { name: '使用资料 / 章节名称' });
  expect(sourceName).toBeDisabled();
  fireEvent.click(screen.getByRole('radio', { name: '每份资料 / 章节分别生成' }));
  expect(sourceName).toBeEnabled();
  fireEvent.click(sourceName);
  fireEvent.click(screen.getByRole('button', { name: '开始生成' }));
  await waitFor(() =>
    expect(api).toHaveBeenCalledWith('/notebooks/book/decks/batch', expect.anything()),
  );
  expect(JSON.parse(vi.mocked(api).mock.calls.at(-1)![1]!.body as string).title_mode).toBe(
    'source',
  );
  fireEvent.click(screen.getByRole('radio', { name: '合并生成一份 Deck' }));
  expect(sourceName).toBeDisabled();
  expect(screen.getByRole('radio', { name: '由 AI 拟定名称' })).toBeChecked();
  fireEvent.click(screen.getByRole('checkbox', { name: '资料 · second' }));
  expect(sourceName).toBeEnabled();
  vi.mocked(api).mockResolvedValue({ id: 'merged' });
  fireEvent.click(screen.getByRole('button', { name: '开始生成' }));
  await waitFor(() => expect(api).toHaveBeenCalledWith('/notebooks/book/decks', expect.anything()));
  expect(JSON.parse(vi.mocked(api).mock.calls.at(-1)![1]!.body as string).title_mode).toBe(
    'source',
  );
});
