import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import EmbeddingIndexes from './EmbeddingIndexes';

const status = {
  configured: true,
  total: 3,
  counts: { ready: 1, queued: 0, running: 1, failed: 1, pending: 0 },
  sources: [
    { source_id: 'one', title: '已完成的书', state: 'ready', progress: 1 },
    { source_id: 'two', title: '待重建的书', state: 'running', progress: 0.6 },
    {
      source_id: 'three',
      title: '失败的书',
      state: 'failed',
      progress: 0,
      error_code: 'MODEL_TIMEOUT',
    },
  ],
};

describe('Embedding indexes', () => {
  it('shows source progress, useful errors and retries only failures without saving the model', async () => {
    const fetch = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async () => new Response(JSON.stringify(status)));
    render(<EmbeddingIndexes refreshKey={0} />);
    expect(
      await screen.findByText('可用于问答 1 / 3 · 排队 0 · 重建中 1 · 失败 1'),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByText('查看各资料进度与更多操作'));
    expect(screen.getByText('正在重建 · 60%')).toBeInTheDocument();
    expect(screen.getByText(/模型服务响应超时/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重新计算全部索引' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '重试失败项' }));
    await screen.findByText('索引重建已加入后台队列，关闭设置后仍会继续。');
    expect(fetch).toHaveBeenCalledWith(
      '/api/settings/models/embedding/indexes/rebuild',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ mode: 'failed' }) }),
    );
    expect(fetch.mock.calls.every(([url]) => !String(url).endsWith('/models/test'))).toBe(true);
  });

  it('refreshes after a model save and can recalculate usable indexes explicitly', async () => {
    let value = { ...status, counts: { ready: 3, queued: 0, running: 0, failed: 0, pending: 0 } };
    const fetch = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async () => new Response(JSON.stringify(value)));
    const { rerender } = render(<EmbeddingIndexes refreshKey={0} />);
    await screen.findByText('可用于问答 3 / 3 · 排队 0 · 重建中 0 · 失败 0');
    expect(screen.getByRole('button', { name: '重建待处理索引' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: '重试失败项' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByText('查看各资料进度与更多操作'));
    fireEvent.click(screen.getByRole('button', { name: '重新计算全部索引' }));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        '/api/settings/models/embedding/indexes/rebuild',
        expect.objectContaining({ body: JSON.stringify({ mode: 'all' }) }),
      ),
    );
    value = { ...status, counts: { ready: 0, queued: 3, running: 0, failed: 0, pending: 0 } };
    rerender(<EmbeddingIndexes refreshKey={1} />);
    await screen.findByText('可用于问答 0 / 3 · 排队 3 · 重建中 0 · 失败 0');
  });

  it('cleans up polling when settings close and reports request failures', async () => {
    const fetch = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(
        new Response(JSON.stringify({ error: { code: 'NETWORK_ERROR' } }), { status: 502 }),
      );
    const { unmount } = render(<EmbeddingIndexes refreshKey={0} />);
    await screen.findByRole('alert');
    unmount();
    vi.useFakeTimers();
    const count = fetch.mock.calls.length;
    vi.advanceTimersByTime(5000);
    expect(fetch).toHaveBeenCalledTimes(count);
    vi.useRealTimers();
  });
});
