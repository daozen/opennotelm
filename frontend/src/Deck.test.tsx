import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, test, vi } from 'vitest';
import DeckView from './Deck';
import { api, ApiError, type Deck, type Job } from './api';
import { applyLanguage } from './i18n';

vi.mock('./api', async (original) => ({
  ...(await original<typeof import('./api')>()),
  api: vi.fn(),
}));
beforeEach(() => {
  vi.mocked(api).mockReset();
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    },
  );
});
afterEach(() => vi.unstubAllGlobals());
const sample = (status: Job['status'] = 'queued'): Deck =>
  ({
    target_slide_count: 10,
    updated_at: '',
    revision: 0,
    id: 'deck',
    title: 'My Deck',
    status: status === 'cancelled' ? 'paused' : 'authoring',
    slide_count: 10,
    slides: [],
    job: { id: 'job', type: 'deck_generate', status, stage: 'authoring', progress: 0.4 },
  }) as Deck;

test('queued and running Decks can stop, preserve progress, and resume the same Deck', async () => {
  let current = sample();
  vi.mocked(api).mockImplementation(async (path) => {
    if (path.endsWith('/stop')) current = sample('cancelled');
    if (path.endsWith('/resume')) current = sample('queued');
    return current;
  });
  const changed = vi.fn();
  render(<DeckView id="deck" onBack={vi.fn()} onOpenSource={vi.fn()} onChanged={changed} />);
  fireEvent.click(await screen.findByRole('button', { name: '停止生成' }));
  await screen.findByRole('button', { name: '继续生成' });
  expect(screen.getByText('已停止，已保存的进度会保留。')).toBeVisible();
  expect(screen.getByText('生成已停止，点击继续生成以接着完成。')).toBeVisible();
  expect(screen.queryByText('重试未完成页面')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '继续生成' }));
  await waitFor(() => expect(api).toHaveBeenCalledWith('/decks/deck/resume', { method: 'POST' }));
  expect(changed).toHaveBeenCalledTimes(2);
});

test('all Decks have explicit deletion confirmation and keep the dialog open on failure', async () => {
  vi.mocked(api).mockImplementation(async (_path, init) => {
    if (init?.method === 'DELETE') throw new ApiError('NETWORK_ERROR');
    return sample('running');
  });
  const deleted = vi.fn();
  render(<DeckView id="deck" onBack={vi.fn()} onOpenSource={vi.fn()} onDeleted={deleted} />);
  fireEvent.click(await screen.findByRole('button', { name: '删除 Deck' }));
  const dialog = screen.getByRole('dialog', { name: '删除 Deck？' });
  expect(dialog).toHaveTextContent('原始资料会保留');
  fireEvent.click(screen.getByRole('button', { name: '取消' }));
  expect(api).not.toHaveBeenCalledWith('/decks/deck', { method: 'DELETE' });
  fireEvent.click(screen.getByRole('button', { name: '删除 Deck' }));
  fireEvent.click(screen.getByRole('button', { name: '确认删除 Deck' }));
  await screen.findByRole('alert');
  expect(deleted).not.toHaveBeenCalled();
  expect(screen.getByRole('dialog', { name: '删除 Deck？' })).toBeVisible();
  vi.mocked(api).mockResolvedValue(undefined);
  fireEvent.click(screen.getByRole('button', { name: '确认删除 Deck' }));
  await waitFor(() => expect(deleted).toHaveBeenCalledOnce());
});

test('focus preview follows language changes, traps focus and restores scrolling on Escape', async () => {
  const deck = sample('completed');
  deck.status = 'draft';
  deck.slides = [
    {
      id: 'slide',
      ordinal: 0,
      plan: { title: 'First', role: '', purpose: '', key_message: '' },
      revision: 0,
      render_current: false,
      citations: {},
      status: 'planned',
      assets: [],
    },
  ] as Deck['slides'];
  vi.mocked(api).mockResolvedValue(deck);
  render(<DeckView id="deck" onBack={vi.fn()} onOpenSource={vi.fn()} />);
  fireEvent.click(await screen.findByRole('button', { name: '专注预览' }));
  expect(screen.getByRole('dialog', { name: 'Deck 大图预览' })).toHaveFocus();
  expect(document.body.style.overflow).toBe('hidden');
  await act(() => applyLanguage('en'));
  expect(screen.getByRole('button', { name: 'Exit focus preview' })).toBeVisible();
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(screen.queryByRole('dialog', { name: 'Deck image preview' })).not.toBeInTheDocument();
  expect(document.body.style.overflow).toBe('');
  expect(screen.getByRole('button', { name: 'Focus preview' })).toHaveFocus();
});

const previewDeck = (): Deck => ({
  ...sample('completed'),
  status: 'ready',
  slide_count: 3,
  slides: ['First', 'Second', 'Third'].map((title, ordinal) => ({
    id: `page-${ordinal}`,
    ordinal,
    plan: { title, role: '', purpose: '', key_message: '' },
    revision: 0,
    render_current: true,
    render: {
      id: `render-${ordinal}`,
      image_url: `/preview-${ordinal}.png`,
      thumbnail_url: `/thumb-${ordinal}.png`,
      width: 1600,
      height: 900,
    },
    spec: {
      key_message: title,
      content_elements: [
        { id: 'headline', type: 'headline', text: title, label: '', items: [], citations: [] },
      ],
      asset_requests: [],
    },
    citations: {},
    status: 'ready',
    assets: [],
  })),
});

test('image regions and arrow keys navigate both previews and stop at the first/last page', async () => {
  vi.mocked(api).mockResolvedValue(previewDeck());
  const { unmount } = render(<DeckView id="deck" onBack={vi.fn()} onOpenSource={vi.fn()} />);
  await screen.findByRole('img', { name: 'First' });
  const previous = screen.getByRole('button', { name: '上一页 · 页面预览' });
  const next = screen.getByRole('button', { name: '下一页 · 页面预览' });
  expect(previous).toBeDisabled();
  expect(next).toBeEmptyDOMElement();
  fireEvent.keyDown(document, { key: 'ArrowUp' });
  expect(screen.getByRole('img', { name: 'First' })).toBeVisible();
  fireEvent.click(next);
  expect(screen.getByRole('img', { name: 'Second' })).toBeVisible();
  expect(screen.getByRole('link', { name: '查看高清页' })).toHaveAttribute(
    'href',
    '/preview-1.png',
  );
  fireEvent.keyDown(document, { key: 'ArrowDown' });
  expect(screen.getByRole('img', { name: 'Third' })).toBeVisible();
  expect(next).toBeDisabled();
  fireEvent.keyDown(document, { key: 'ArrowDown' });
  expect(screen.getByRole('img', { name: 'Third' })).toBeVisible();
  fireEvent.keyDown(document, { key: 'ArrowUp' });
  expect(screen.getByRole('img', { name: 'Second' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: '专注预览' }));
  fireEvent.click(previous);
  expect(screen.getByRole('img', { name: 'First' })).toBeVisible();
  fireEvent.keyDown(document, { key: 'ArrowDown' });
  expect(screen.getByRole('img', { name: 'Second' })).toBeVisible();
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(screen.queryByRole('dialog', { name: 'Deck 大图预览' })).not.toBeInTheDocument();
  unmount();
  expect(fireEvent.keyDown(document, { key: 'ArrowDown' })).toBe(true);
});

test('preview shortcuts preserve form controls, composing/modifier keys and open editors/dialogs', async () => {
  vi.mocked(api).mockResolvedValue(previewDeck());
  render(
    <>
      <input aria-label="Other input" />
      <select aria-label="Other select">
        <option>Choice</option>
      </select>
      <div contentEditable aria-label="Editable text" />
      <DeckView id="deck" onBack={vi.fn()} onOpenSource={vi.fn()} />
    </>,
  );
  await screen.findByRole('img', { name: 'First' });
  for (const name of ['Other input', 'Other select', 'Editable text'])
    expect(fireEvent.keyDown(screen.getByLabelText(name), { key: 'ArrowDown' })).toBe(true);
  for (const flags of [{ ctrlKey: true }, { shiftKey: true }, { isComposing: true }])
    expect(fireEvent.keyDown(document, { key: 'ArrowDown', ...flags })).toBe(true);
  const handled = new KeyboardEvent('keydown', {
    key: 'ArrowDown',
    bubbles: true,
    cancelable: true,
  });
  handled.preventDefault();
  fireEvent(document, handled);
  expect(screen.getByRole('img', { name: 'First' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: '编辑文字' }));
  expect(screen.getByRole('dialog', { name: '编辑本页文字' })).toBeVisible();
  expect(fireEvent.keyDown(document, { key: 'ArrowDown' })).toBe(true);
  expect(screen.getByLabelText('标题 1')).toHaveValue('First');
  fireEvent.click(screen.getByRole('button', { name: '取消' }));
  fireEvent.click(screen.getByRole('button', { name: '删除 Deck' }));
  expect(fireEvent.keyDown(document, { key: 'ArrowDown' })).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '取消' }));
  expect(screen.getByRole('img', { name: 'First' })).toBeVisible();
  fireEvent.keyDown(document, { key: 'ArrowDown' });
  expect(screen.getByRole('img', { name: 'Second' })).toBeVisible();
});

test('rename preserves drafts across languages, retries failures and updates the download name', async () => {
  const deck = {
    ...sample('completed'),
    status: 'draft',
    pdf_export: {
      id: 'p',
      status: 'ready',
      page_count: 10,
      file_size: 20,
      download_url: '/pdf/file',
      filename: 'My Deck.pdf',
    },
  };
  vi.mocked(api).mockImplementation(async (_path, init) => {
    if (init?.method === 'PATCH') throw new ApiError('NETWORK_ERROR');
    return deck;
  });
  const changed = vi.fn();
  render(<DeckView id="deck" onBack={vi.fn()} onOpenSource={vi.fn()} onChanged={changed} />);
  fireEvent.click(await screen.findByRole('button', { name: '重命名 Deck' }));
  fireEvent.change(screen.getByLabelText('Deck 名称'), { target: { value: '蜂蜜供品' } });
  await act(() => applyLanguage('en'));
  expect(screen.getByLabelText('Deck name')).toHaveValue('蜂蜜供品');
  fireEvent.click(screen.getByRole('button', { name: 'Save name' }));
  await screen.findByRole('alert');
  expect(screen.getByLabelText('Deck name')).toHaveValue('蜂蜜供品');
  expect(changed).not.toHaveBeenCalled();
  const renamed = {
    ...deck,
    title: '蜂蜜供品',
    pdf_export: { ...deck.pdf_export, filename: '蜂蜜供品.pdf' },
  };
  vi.mocked(api).mockResolvedValue(renamed);
  fireEvent.click(screen.getByRole('button', { name: 'Save name' }));
  await waitFor(() => expect(changed).toHaveBeenCalledOnce());
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: '蜂蜜供品' })).toBeVisible();
  expect(screen.getByRole('link', { name: 'Download PDF · Pages: 10' })).toHaveAttribute(
    'download',
    '蜂蜜供品.pdf',
  );
  expect(api).toHaveBeenCalledWith('/decks/deck', {
    method: 'PATCH',
    body: JSON.stringify({ title: '蜂蜜供品' }),
  });
});

test('rename is unavailable until a running Deck stops', async () => {
  vi.mocked(api).mockResolvedValue(sample('running'));
  render(<DeckView id="deck" onBack={vi.fn()} onOpenSource={vi.fn()} />);
  expect(await screen.findByRole('button', { name: '重命名 Deck' })).toBeDisabled();
});
