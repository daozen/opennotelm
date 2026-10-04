import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';
import SourceImport from './SourceImport';
import { applyLanguage } from './i18n';

vi.mock('./api', async (original) => ({
  ...(await original<typeof import('./api')>()),
  api: vi.fn(),
}));
const mockedApi = vi.mocked(api);

beforeEach(async () => {
  vi.clearAllMocks();
  await applyLanguage('zh-CN');
});

describe('source imports', () => {
  it('confirms duplicates in input order and releases uploads before a slow refresh', async () => {
    let finishFirst = () => {};
    const refresh = new Promise<void>(() => {});
    mockedApi.mockImplementation(async (_path, init) => {
      const file = (init!.body as FormData).get('file') as File;
      if (file.name === 'first.txt')
        await new Promise<void>((resolve) => {
          finishFirst = resolve;
        });
      return { duplicate: true, source: { id: file.name, title: file.name } };
    });
    render(<SourceImport notebookId="n" onImported={() => refresh} />);
    fireEvent.change(screen.getByLabelText('上传资料'), {
      target: { files: [new File(['a'], 'first.txt'), new File(['b'], 'second.txt')] },
    });
    await waitFor(() => expect(mockedApi).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    finishFirst();
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('first.txt');
    expect(screen.getByLabelText('上传资料')).toBeEnabled();
    expect(screen.getByText('还有 1 项重复资料待确认')).toBeInTheDocument();
  });
  it('uploads at most three files concurrently and preserves each result row', async () => {
    let active = 0;
    let peak = 0;
    const finish: (() => void)[] = [];
    mockedApi.mockImplementation(async (_path, init) => {
      const file = (init!.body as FormData).get('file') as File;
      active += 1;
      peak = Math.max(peak, active);
      await new Promise<void>((resolve) => finish.push(resolve));
      active -= 1;
      return { duplicate: false, source: { id: file.name } };
    });
    render(<SourceImport notebookId="n" onImported={async () => {}} />);
    fireEvent.change(screen.getByLabelText('上传资料'), {
      target: { files: Array.from({ length: 5 }, (_, i) => new File([String(i)], `${i}.txt`)) },
    });
    await waitFor(() => expect(finish).toHaveLength(3));
    finish.splice(0).forEach((resolve) => resolve());
    await waitFor(() => expect(finish).toHaveLength(2));
    finish.splice(0).forEach((resolve) => resolve());
    await screen.findByText('本次添加：5 成功，0 失败，0 已存在');
    expect(peak).toBe(3);
    expect(active).toBe(0);
  });
  it('uploads all selected files, preserves partial success and can retry a failed file', async () => {
    const refreshed = vi.fn().mockResolvedValue(undefined);
    let badAttempts = 0;
    mockedApi.mockImplementation(async (_path, init) => {
      const file = (init!.body as FormData).get('file') as File;
      if (file.name === 'bad.txt' && badAttempts++ === 0) throw new Error('errors.SOURCE_EMPTY');
      return { duplicate: false, source: { id: file.name } };
    });
    render(<SourceImport notebookId="n" onImported={refreshed} />);
    const input = screen.getByLabelText('上传资料');
    expect(input).toHaveAttribute('multiple');
    fireEvent.change(input, {
      target: {
        files: [
          new File(['one'], 'one.txt'),
          new File([], 'bad.txt'),
          new File(['three'], 'three.txt'),
        ],
      },
    });
    await screen.findByText('本次添加：2 成功，1 失败，0 已存在');
    expect(mockedApi).toHaveBeenCalledTimes(3);
    expect(refreshed).toHaveBeenCalledTimes(2);
    fireEvent.click(screen.getByRole('button', { name: '重试上传' }));
    await screen.findByText('本次添加：3 成功，0 失败，0 已存在');
    expect(mockedApi).toHaveBeenCalledTimes(4);
  });

  it('keeps every duplicate in a queue rather than replacing the previous one', async () => {
    mockedApi.mockImplementation(async (path, init) => {
      if (path.endsWith('/upload')) {
        const file = (init!.body as FormData).get('file') as File;
        return { duplicate: true, source: { id: file.name, title: file.name } };
      }
      return {};
    });
    render(<SourceImport notebookId="n" onImported={async () => {}} />);
    fireEvent.change(screen.getByLabelText('上传资料'), {
      target: { files: [new File(['a'], 'a.txt'), new File(['b'], 'b.txt')] },
    });
    await screen.findByText('还有 1 项重复资料待确认');
    expect(screen.getByRole('dialog')).toHaveTextContent('a.txt');
    fireEvent.click(screen.getByRole('button', { name: '添加已有资料' }));
    await waitFor(() => expect(screen.getByRole('dialog')).toHaveTextContent('b.txt'));
    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(mockedApi).toHaveBeenCalledWith('/notebooks/n/sources/a.txt', { method: 'POST' });
  });

  it('releases the duplicate dialog before a slow source-list refresh finishes', async () => {
    mockedApi.mockImplementation(async (path) =>
      path.endsWith('/upload')
        ? { duplicate: true, source: { id: 'existing', title: 'Existing' } }
        : {},
    );
    let finishRefresh = () => {};
    const slowRefresh = new Promise<void>((resolve) => {
      finishRefresh = resolve;
    });
    let refreshCalls = 0;
    render(
      <SourceImport
        notebookId="n"
        onImported={() => (++refreshCalls === 1 ? Promise.resolve() : slowRefresh)}
      />,
    );
    fireEvent.change(screen.getByLabelText('上传资料'), {
      target: { files: [new File(['a'], 'a.txt')] },
    });
    await screen.findByRole('dialog', { name: '资料已存在' });
    fireEvent.click(screen.getByRole('button', { name: '添加已有资料' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(document.querySelector('[inert]')).toBeNull();
    finishRefresh();
  });

  it('submits deduplicated URL lines and keeps rejected URLs for correction', async () => {
    mockedApi.mockResolvedValue({
      results: [
        { index: 0, duplicate: false, source: { id: 'web' } },
        { index: 1, error_code: 'WEB_URL_INVALID' },
      ],
    });
    render(<SourceImport notebookId="n" onImported={async () => {}} />);
    fireEvent.click(screen.getByRole('button', { name: '导入网页' }));
    const dialog = screen.getByRole('dialog', { name: '导入网页' });
    fireEvent.change(within(dialog).getByLabelText('网页地址'), {
      target: {
        value: ' https://example.com/article\nhttps://example.com/article\nfile:///private\n',
      },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: '导入 2 个网页' }));
    await screen.findByText('本次添加：1 成功，1 失败，0 已存在');
    expect(mockedApi).toHaveBeenCalledWith('/notebooks/n/sources/urls', {
      method: 'POST',
      body: JSON.stringify({
        urls: ['https://example.com/article', 'file:///private'],
        save_images: true,
      }),
    });
    fireEvent.click(screen.getByRole('button', { name: '导入网页' }));
    expect(screen.getByLabelText('网页地址')).toHaveValue('file:///private');
  });

  it('preserves URL draft on a request failure and bounds the batch', async () => {
    mockedApi.mockRejectedValue(new Error('errors.NETWORK_ERROR'));
    render(<SourceImport notebookId="n" onImported={async () => {}} />);
    fireEvent.click(screen.getByRole('button', { name: '导入网页' }));
    const field = screen.getByLabelText('网页地址');
    fireEvent.change(field, { target: { value: 'https://example.com/' } });
    fireEvent.click(screen.getByRole('button', { name: '导入 1 个网页' }));
    await waitFor(() => expect(screen.getByRole('alert')).toBeVisible());
    expect(field).toHaveValue('https://example.com/');
    fireEvent.change(field, {
      target: {
        value: Array.from({ length: 51 }, (_, i) => `https://example.com/${i}`).join('\n'),
      },
    });
    expect(screen.getByRole('button', { name: '导入 51 个网页' })).toBeDisabled();
    expect(mockedApi).toHaveBeenCalledTimes(1);
  });

  it('can import text only and retains the image choice after a request failure', async () => {
    mockedApi.mockRejectedValueOnce(new Error('errors.NETWORK_ERROR')).mockResolvedValueOnce({
      results: [{ index: 0, duplicate: false, source: { id: 'web' } }],
    });
    render(<SourceImport notebookId="n" onImported={async () => {}} />);
    fireEvent.click(screen.getByRole('button', { name: '导入网页' }));
    const checkbox = screen.getByRole('checkbox', { name: '保存正文图片' });
    expect(checkbox).toBeChecked();
    fireEvent.click(checkbox);
    fireEvent.change(screen.getByLabelText('网页地址'), {
      target: { value: 'https://example.com/' },
    });
    fireEvent.click(screen.getByRole('button', { name: '导入 1 个网页' }));
    await screen.findByRole('alert');
    expect(checkbox).not.toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: '导入 1 个网页' }));
    await screen.findByText('本次添加：1 成功，0 失败，0 已存在');
    expect(mockedApi).toHaveBeenLastCalledWith('/notebooks/n/sources/urls', {
      method: 'POST',
      body: JSON.stringify({ urls: ['https://example.com/'], save_images: false }),
    });
  });
});
