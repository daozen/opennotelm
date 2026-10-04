import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, test, vi } from 'vitest';
import TaskSettings from './TaskSettings';
import { applyLanguage } from './i18n';

beforeEach(async () => {
  await applyLanguage('zh-CN');
});

test('loads and saves independent task and provider budgets with distinct limits', async () => {
  const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
    const task = String(url).endsWith('/task-concurrency');
    return new Response(
      JSON.stringify({
        concurrency:
          init?.method === 'PUT' ? JSON.parse(init.body as string).concurrency : task ? 3 : 8,
        min_concurrency: 1,
        max_concurrency: task ? 8 : 20,
      }),
    );
  });
  render(<TaskSettings />);
  const task = screen.getByLabelText('同时处理任务数');
  const requests = screen.getByLabelText('每个模型服务的总请求并发数');
  await waitFor(() => expect(task).toBeEnabled());
  expect(task.querySelectorAll('option')).toHaveLength(8);
  expect(requests.querySelectorAll('option')).toHaveLength(20);
  fireEvent.change(task, { target: { value: '2' } });
  fireEvent.click(screen.getByText('保存任务设置'));
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      '/api/settings/models/task-concurrency',
      expect.objectContaining({ method: 'PUT', body: JSON.stringify({ concurrency: 2 }) }),
    ),
  );
  fireEvent.change(requests, { target: { value: '4' } });
  fireEvent.click(screen.getByText('保存请求设置'));
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      '/api/settings/models/request-concurrency',
      expect.objectContaining({ method: 'PUT', body: JSON.stringify({ concurrency: 4 }) }),
    ),
  );
});
