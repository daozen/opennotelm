import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Setup from './Setup';

describe('Setup', () => {
  it('keeps custom model entry available when discovery fails and clears the key after success', async () => {
    const onSaved = vi.fn();
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
      const responses: Record<string, unknown> = {
        '/api/settings/telemetry': { enabled: false, configured: false, queued_events: 0 },
        '/api/settings/models/content-generation': {
          concurrency: 2,
          min_concurrency: 1,
          max_concurrency: 20,
        },
        '/api/settings/models/image-recognition': {
          concurrency: 4,
          min_concurrency: 1,
          max_concurrency: 20,
        },
        '/api/settings/models/image-generation': {
          concurrency: 2,
          min_concurrency: 1,
          max_concurrency: 20,
        },
        '/api/settings/models/discover': { models: [], message: '请输入自定义 Model ID' },
        '/api/settings/models/test': { setup_complete: false, models: {} },
      };
      return new Response(JSON.stringify(responses[String(url)]));
    });
    render(
      <Setup
        settings={{ setup_complete: false, models: {} }}
        onSaved={onSaved}
        onClose={vi.fn()}
      />,
    );
    const form = screen.getByText('语言模型').closest('form')!;
    const fields = within(form);
    fireEvent.click(fields.getByText('发现模型'));
    await fields.findByText('模型服务未提供模型列表，可手动输入 ID。');
    fireEvent.change(fields.getByLabelText('模型 ID'), { target: { value: 'custom-model' } });
    fireEvent.change(fields.getByLabelText('访问密钥'), { target: { value: 'private-key' } });
    fireEvent.click(fields.getByText('测试并保存'));
    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
    expect(fields.getByLabelText('访问密钥')).toHaveValue('');
    expect(screen.getByText('开始使用')).toBeDisabled();
  });
  it('shows failed capability tests and allows retry', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) =>
      String(url).endsWith('/image-recognition') || String(url).endsWith('/content-generation')
        ? new Response(JSON.stringify({ concurrency: 4, min_concurrency: 1, max_concurrency: 20 }))
        : new Response(
            JSON.stringify({
              error: { code: 'MODEL_TIMEOUT', message: '连接超时，请重试。' },
            }),
            { status: 502 },
          ),
    );
    render(
      <Setup
        settings={{ setup_complete: false, models: {} }}
        onSaved={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    const fields = within(screen.getByText('语言模型').closest('form')!);
    fireEvent.change(fields.getByLabelText('模型 ID'), { target: { value: 'model' } });
    fireEvent.click(fields.getByText('测试并保存'));
    expect(await fields.findByRole('alert')).toHaveTextContent('模型服务响应超时');
    expect(fields.getByText('测试并保存')).toBeEnabled();
  });
});
