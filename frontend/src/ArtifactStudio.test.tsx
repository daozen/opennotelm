import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import ArtifactStudio, { type StudioItem } from './ArtifactStudio';
import { applyLanguage } from './i18n';

const items: StudioItem[] = [
  {
    id: 'd',
    kind: 'deck',
    title: 'A deck',
    status: 'ready',
    statusLabel: '已完成',
    summary: '15 pages',
    download_available: true,
  },
  {
    id: 'p',
    kind: 'podcast',
    title: 'An episode',
    status: 'paused',
    jobStatus: 'cancelled',
    statusLabel: '已停止',
    summary: '10 minutes',
    resumable: true,
  },
  {
    id: 'm',
    kind: 'mindmap',
    title: 'A mind map',
    status: 'mindmap_mapping',
    jobStatus: 'running',
    statusLabel: '梳理概念关系',
    summary: '5 nodes',
  },
];
test('mixed artifacts share navigation, search, creation and stop/resume actions', async () => {
  await applyLanguage('en');
  const onOpen = vi.fn(),
    onFilter = vi.fn(),
    onCreate = vi.fn(),
    onDelete = vi.fn(),
    onAction = vi.fn().mockResolvedValue(undefined);
  render(
    <ArtifactStudio
      notebookId="n"
      items={items}
      onOpen={onOpen}
      onFilter={onFilter}
      onCreate={onCreate}
      onAction={onAction}
      onDelete={onDelete}
      canCreate
    />,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Create mind map' }));
  expect(onCreate).toHaveBeenCalledWith('mindmap');
  fireEvent.click(screen.getByRole('button', { name: /^Mind map A mind map/ }));
  expect(onOpen).toHaveBeenCalledWith(items[2]);
  fireEvent.click(screen.getByRole('button', { name: 'Stop generation' }));
  await waitFor(() => expect(onAction).toHaveBeenCalledWith(items[2], 'stop'));
  fireEvent.click(screen.getByRole('button', { name: 'Resume generation' }));
  await waitFor(() => expect(onAction).toHaveBeenCalledWith(items[1], 'resume'));
  fireEvent.change(screen.getByLabelText('Search artifacts'), { target: { value: 'episode' } });
  expect(screen.queryByText('A deck')).toBeNull();
  expect(screen.getByText('An episode')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Delete artifact · An episode' }));
  expect(onDelete).toHaveBeenCalledWith(items[1]);
  fireEvent.change(screen.getByLabelText('Artifact type'), { target: { value: 'mindmap' } });
  expect(onFilter).toHaveBeenCalledWith('mindmap');
});
test('action failures stay visible and filtering does not issue generation requests', async () => {
  await applyLanguage('en');
  const onAction = vi.fn().mockRejectedValue(new Error('errors.NETWORK_ERROR'));
  render(
    <ArtifactStudio
      notebookId="n"
      items={items}
      onOpen={vi.fn()}
      onFilter={vi.fn()}
      onCreate={vi.fn()}
      onAction={onAction}
      onDelete={vi.fn()}
      canCreate
    />,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Stop generation' }));
  expect(await screen.findByRole('alert')).toBeVisible();
  fireEvent.change(screen.getByLabelText('Artifact status'), { target: { value: 'attention' } });
  expect(screen.queryByText('A deck')).toBeNull();
  expect(screen.getByText('An episode')).toBeVisible();
  fireEvent.change(screen.getByLabelText('Artifact status'), { target: { value: 'ready' } });
  expect(screen.getByText('A deck')).toBeVisible();
  expect(screen.queryByText('An episode')).toBeNull();
  expect(onAction).toHaveBeenCalledTimes(1);
});
