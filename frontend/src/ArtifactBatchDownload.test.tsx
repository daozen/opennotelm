import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import ArtifactBatchDownload, { type DownloadableArtifact } from './ArtifactBatchDownload';
import { applyLanguage } from './i18n';

const items: DownloadableArtifact[] = [
  { id: 'one', kind: 'deck', title: 'First chapter', download_available: true },
  { id: 'two', kind: 'deck', title: 'Second chapter', download_available: true },
  { id: 'waiting', kind: 'deck', title: 'Still generating', download_available: false },
];
const view = (entries = items) => (
  <ArtifactBatchDownload
    notebookId="book"
    items={entries}
    renderItem={(item, selection) => (
      <div key={item.id}>
        {selection}
        <span>{item.title}</span>
      </div>
    )}
  />
);

test('selects available items, prepares once, and uses a normal download link without loading ZIP bytes', async () => {
  const clicked = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(
      JSON.stringify({
        filename: 'Book.zip',
        download_url: '/api/artifact-downloads/token/file',
      }),
    ),
  );
  render(view());
  fireEvent.click(screen.getByText('批量下载'));
  expect(screen.getByLabelText('选择下载 · Still generating')).toBeDisabled();
  fireEvent.click(screen.getByLabelText('选择全部可下载文件'));
  fireEvent.click(screen.getByText('下载所选（2）'));
  await waitFor(() => expect(clicked).toHaveBeenCalledOnce());
  expect(fetch).toHaveBeenCalledOnce();
  expect(JSON.parse(fetch.mock.calls[0][1]!.body as string)).toEqual({
    items: [
      { kind: 'deck', id: 'one' },
      { kind: 'deck', id: 'two' },
    ],
  });
  expect(screen.getByRole('link', { name: '下载 ZIP' })).toHaveAttribute('download', 'Book.zip');
  expect(screen.getByRole('link', { name: '下载 ZIP' })).toHaveAttribute(
    'href',
    '/api/artifact-downloads/token/file',
  );
});

test('preserves selection across language and polling updates, removes unavailable items, and shows actionable errors', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(
      JSON.stringify({
        error: {
          code: 'ARTIFACT_NOT_READY',
          message: 'raw unsafe detail',
        },
      }),
      { status: 409 },
    ),
  );
  const result = render(view());
  fireEvent.click(screen.getByText('批量下载'));
  fireEvent.click(screen.getByLabelText('选择下载 · First chapter'));
  result.rerender(view(items.map((item) => ({ ...item }))));
  expect(screen.getByText('下载所选（1）')).toBeEnabled();
  await act(() => applyLanguage('en'));
  expect(screen.getByLabelText('Select for download · First chapter')).toBeChecked();
  fireEvent.click(screen.getByText('Download selected (1)'));
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Finish generating or export it first',
  );
  expect(screen.queryByText('raw unsafe detail')).not.toBeInTheDocument();
  result.rerender(view([items[1], items[2]]));
  expect(screen.getByText('Download selected (0)')).toBeDisabled();
});

test('prevents duplicate requests while packaging and aborts pending preparation on unmount', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(() => {}));
  const result = render(view());
  fireEvent.click(screen.getByText('批量下载'));
  fireEvent.click(screen.getByLabelText('选择下载 · First chapter'));
  fireEvent.click(screen.getByText('下载所选（1）'));
  expect(screen.getByText('正在打包…')).toBeDisabled();
  expect(screen.getByText('取消选择')).toBeDisabled();
  expect(fetch).toHaveBeenCalledOnce();
  const signal = fetch.mock.calls[0][1]!.signal;
  result.unmount();
  expect(signal!.aborted).toBe(true);
});

test('bounds large selections and supports clearing all items', () => {
  render(
    view(
      Array.from({ length: 101 }, (_, index) => ({
        ...items[0],
        id: String(index),
        title: String(index),
      })),
    ),
  );
  fireEvent.click(screen.getByText('批量下载'));
  fireEvent.click(screen.getByLabelText('选择全部可下载文件'));
  expect(screen.getByText('下载所选（101）')).toBeDisabled();
  fireEvent.click(screen.getByLabelText('选择下载 · 0'));
  expect(screen.getByText('下载所选（100）')).toBeEnabled();
  fireEvent.click(screen.getByText('取消选择'));
  expect(screen.getByText('批量下载')).toBeVisible();
});
