import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import PodcastView from './Podcast';
import { api, ApiError, type Podcast } from './api';

vi.mock('./api', async (original) => ({
  ...(await original<typeof import('./api')>()),
  api: vi.fn(),
}));
beforeEach(() => {
  vi.mocked(api).mockReset();
});

const episode: Podcast = {
  id: 'episode',
  title: 'Learning through practice',
  status: 'script_ready',
  input: { target_minutes: 5, language: 'en', format: 'dialogue', script_only: true },
  revision: 0,
  segments: [],
  audio: null,
  notebook_id: 'notebook',
  download_available: false,
  job: null,
  saved_audio_chunks: 0,
};

test('deletion failures preserve the episode and confirmation; retry accepts an empty response', async () => {
  let fail = true;
  vi.mocked(api).mockImplementation(async (_path, init) => {
    if (init?.method === 'DELETE') {
      if (fail) throw new ApiError('NETWORK_ERROR');
      return undefined;
    }
    return episode;
  });
  const deleted = vi.fn();
  const changed = vi.fn();
  render(
    <PodcastView
      id={episode.id}
      onBack={vi.fn()}
      onChanged={changed}
      onDeleted={deleted}
      onOpenSource={vi.fn()}
      onOpenKnowledge={vi.fn()}
    />,
  );
  fireEvent.click(await screen.findByRole('button', { name: '删除' }));
  const dialog = screen.getByRole('alertdialog', { name: '删除 Podcast' });
  expect(within(dialog).getByRole('button', { name: '取消' })).toHaveFocus();
  fireEvent.click(within(dialog).getByRole('button', { name: '取消' }));
  expect(api).not.toHaveBeenCalledWith('/podcasts/episode', { method: 'DELETE' });
  fireEvent.click(screen.getByRole('button', { name: '删除' }));
  const confirmation = screen.getByRole('alertdialog', { name: '删除 Podcast' });
  fireEvent.click(within(confirmation).getByRole('button', { name: '删除' }));
  expect(await within(confirmation).findByRole('alert')).toBeVisible();
  expect(screen.getByRole('heading', { name: episode.title })).toBeInTheDocument();
  expect(deleted).not.toHaveBeenCalled();
  expect(changed).not.toHaveBeenCalled();
  fail = false;
  fireEvent.click(within(confirmation).getByRole('button', { name: '删除' }));
  await waitFor(() => expect(deleted).toHaveBeenCalledOnce());
  // DELETE's 204 response must never be treated as a new, empty episode.
  expect(screen.queryByText('加载中…')).not.toBeInTheDocument();
  expect(changed).not.toHaveBeenCalled();
});

test('renaming opens an accessible dialog and preserves the draft when saving fails', async () => {
  vi.mocked(api).mockImplementation(async (_path, init) => {
    if (init?.method === 'PATCH') throw new ApiError('NETWORK_ERROR');
    return episode;
  });
  render(
    <PodcastView
      id={episode.id}
      onBack={vi.fn()}
      onChanged={vi.fn()}
      onDeleted={vi.fn()}
      onOpenSource={vi.fn()}
      onOpenKnowledge={vi.fn()}
    />,
  );
  fireEvent.click(await screen.findByRole('button', { name: '重命名' }));
  const dialog = screen.getByRole('dialog', { name: '重命名' });
  const title = within(dialog).getByLabelText('Podcast 名称');
  expect(title).toHaveFocus();
  fireEvent.change(title, { target: { value: 'New episode name' } });
  fireEvent.click(within(dialog).getByRole('button', { name: '保存' }));
  expect(await within(dialog).findByRole('alert')).toBeVisible();
  expect(title).toHaveValue('New episode name');
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
