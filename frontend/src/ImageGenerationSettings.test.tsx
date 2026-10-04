import { StrictMode } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ImageGenerationSettings from './ImageGenerationSettings';

const settings = { concurrency: 2, min_concurrency: 1, max_concurrency: 20 };

describe('Image generation settings', () => {
  it('saves 20 or 1 independently of model testing', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, options) => {
      const value = options?.body ? JSON.parse(String(options.body)) : settings;
      return new Response(JSON.stringify({ ...settings, ...value }));
    });
    render(<ImageGenerationSettings />);
    const select = screen.getByLabelText('图片生成并发数');
    await waitFor(() => expect(select).toBeEnabled());
    expect(select).toHaveValue('2');
    expect(screen.getAllByRole('option')).toHaveLength(20);
    expect(screen.getByText('保存并发设置')).toBeDisabled();
    for (const concurrency of [20, 1]) {
      fireEvent.change(select, { target: { value: String(concurrency) } });
      fireEvent.click(screen.getByText('保存并发设置'));
      await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('并发设置已保存。'));
      expect(fetch).toHaveBeenLastCalledWith(
        '/api/settings/models/image-generation',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ concurrency }),
        }),
      );
      expect(screen.getByText('保存并发设置')).toBeDisabled();
    }
    expect(fetch.mock.calls.every(([url]) => url === '/api/settings/models/image-generation')).toBe(
      true,
    );
  });

  it('retains the draft after a failed save and allows retry', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch');
    fetch.mockResolvedValueOnce(new Response(JSON.stringify(settings)));
    fetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: { code: 'NETWORK_ERROR' } }), { status: 502 }),
    );
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({ ...settings, concurrency: 20 })));
    render(<ImageGenerationSettings />);
    const select = screen.getByLabelText('图片生成并发数');
    await waitFor(() => expect(select).toBeEnabled());
    fireEvent.change(select, { target: { value: '20' } });
    fireEvent.click(screen.getByText('保存并发设置'));
    expect(await screen.findByRole('alert')).toHaveTextContent('网络连接失败');
    expect(select).toHaveValue('20');
    expect(screen.getByText('保存并发设置')).toBeEnabled();
    fireEvent.click(screen.getByText('保存并发设置'));
    expect(await screen.findByRole('status')).toHaveTextContent('并发设置已保存。');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('does not allow saving when loading fails and can reload', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch');
    fetch.mockRejectedValueOnce(new TypeError('Failed to fetch'));
    fetch.mockResolvedValueOnce(new Response(JSON.stringify({ ...settings, concurrency: 7 })));
    render(<ImageGenerationSettings />);
    expect(await screen.findByRole('alert')).toHaveTextContent('网络连接失败');
    expect(screen.getByLabelText('图片生成并发数')).toBeDisabled();
    fireEvent.click(screen.getByText('重试'));
    await waitFor(() => expect(screen.getByLabelText('图片生成并发数')).toBeEnabled());
    expect(screen.getByLabelText('图片生成并发数')).toHaveValue('7');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});

it('ignores a superseded settings load instead of overwriting the user choice', async () => {
  let resolveOld!: (value: Response) => void;
  vi.spyOn(globalThis, 'fetch')
    .mockImplementationOnce(
      () =>
        new Promise<Response>((resolve) => {
          resolveOld = resolve;
        }),
    )
    .mockResolvedValueOnce(new Response(JSON.stringify(settings)));
  render(
    <StrictMode>
      <ImageGenerationSettings />
    </StrictMode>,
  );
  const select = screen.getByLabelText('图片生成并发数');
  await waitFor(() => expect(select).toBeEnabled());
  fireEvent.change(select, { target: { value: '20' } });
  await act(async () => {
    resolveOld(new Response(JSON.stringify(settings)));
  });
  expect(select).toHaveValue('20');
  expect(screen.getByText('保存并发设置')).toBeEnabled();
});
