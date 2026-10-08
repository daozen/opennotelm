import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import Reader from './Reader';
import { api } from './api';

vi.mock('./api', () => ({ api: vi.fn() }));

test('completed recognition refreshes the open chapter and offers recognition for legacy PDF warnings', async () => {
  let recognized = false;
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith('/nodes')
      ? [
          { id: 'root', type: 'document', title: 'Scan', depth: 0 },
          { id: 'chapter', type: 'chapter', title: '第一章', depth: 1 },
        ]
      : [
          {
            type: 'paragraph',
            parts: [{ block_id: 'body', text: recognized ? '新识别的段落。' : '原生文字。' }],
          },
        ],
  );
  const source = {
    id: 'scan',
    type: 'pdf',
    title: 'Scan',
    status: 'indexed',
    original_filename: 'scan.pdf',
    enabled: true,
    updated_at: 'before-recognition',
    metadata: { warnings: ['No extractable text on pages: 2. OCR is unsupported.'] },
  };
  const ask = vi.fn();
  const view = render(
    <Reader source={source} initialNodeId="chapter" onClose={() => {}} onAsk={ask} />,
  );
  expect(await screen.findByText('原生文字。')).toBeVisible();
  expect(screen.getByText('无法提取以下页面的原生文字：2。可尝试识别文档图片。')).toBeVisible();
  expect(screen.getByRole('button', { name: '识别文档图片' })).toBeEnabled();
  recognized = true;
  view.rerender(
    <Reader
      source={{ ...source, updated_at: 'after-recognition' }}
      initialNodeId="chapter"
      onClose={() => {}}
      onAsk={ask}
    />,
  );
  expect(await screen.findByText('新识别的段落。')).toBeVisible();
  expect(screen.queryByText('原生文字。')).toBeNull();
  expect(screen.getByLabelText('目录 / 章节')).toHaveValue('chapter');
  fireEvent.click(screen.getByRole('button', { name: '就本章节提问' }));
  expect(ask).toHaveBeenCalledWith(
    { kind: 'node', source_id: 'scan', node_id: 'chapter' },
    '第一章',
  );
});

test('web images can be added later, keep the body readable and expose download failures', async () => {
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith('/nodes')
      ? [{ id: 'root', type: 'document', title: 'Article', depth: 0 }]
      : [
          { type: 'paragraph', parts: [{ block_id: 'body', text: 'Article body' }] },
          {
            type: 'image',
            parts: [{ block_id: 'image', text: '' }],
            image: {
              image_url: '/api/sources/web/media/image',
              original_image_url: '/api/sources/web/media/image/original',
              extraction: 'vision',
              recognition_status: 'failed',
              error_code: 'WEB_ACCESS_DENIED',
            },
          },
        ],
  );
  const source = {
    id: 'web',
    type: 'web',
    title: 'Article',
    status: 'indexed',
    original_filename: 'webpage.html',
    enabled: true,
  };
  const view = render(<Reader source={source} onClose={() => {}} onAsk={() => {}} />);
  expect(await screen.findByText('Article body')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: '保存并识别网页图片' }));
  await waitFor(() =>
    expect(vi.mocked(api)).toHaveBeenCalledWith('/sources/web/recognize-images', {
      method: 'POST',
    }),
  );
  view.rerender(
    <Reader
      source={{
        ...source,
        metadata: { save_images: true, web_images_status: 'queued' },
        job: {
          id: 'job',
          type: 'source_web_images',
          status: 'running',
          stage: 'fetching_images',
          progress: 0.2,
        },
      }}
      onClose={() => {}}
      onAsk={() => {}}
    />,
  );
  expect(screen.getByRole('button', { name: '重新处理网页图片' })).toBeDisabled();
  expect(screen.getByText('正在下载网页图片，正文已可阅读。')).toBeVisible();
  expect(screen.getByText('Article body')).toBeVisible();
  expect(screen.getByRole('link', { name: '下载原图' })).toHaveAttribute(
    'href',
    '/api/sources/web/media/image/original',
  );
  expect(screen.getByText(/网站拒绝访问/)).toBeVisible();
});

test('PDF citation opens its whole page with inline anchors, readable text and controls', async () => {
  const scroll = vi.fn();
  vi.spyOn(Element.prototype, 'scrollIntoView').mockImplementation(scroll);
  vi.mocked(api).mockImplementation(async (path) => {
    if (path.endsWith('/nodes'))
      return [
        { id: 'root', type: 'document', title: 'PDF', depth: 0 },
        { id: 'page1', type: 'page', title: 'Page 1', depth: 1, start_page: 1 },
        { id: 'fake', type: 'heading', title: '字', depth: 2, start_page: 1 },
        { id: 'page2', type: 'page', title: 'Page 2', depth: 1, start_page: 2 },
      ];
    if (path.endsWith('/blocks')) return [{ id: 'target', node_id: 'fake', page_start: 2 }];
    return [
      {
        type: 'paragraph',
        page_start: 2,
        parts: [
          { block_id: 'before', text: '连续阅读的' },
          { block_id: 'target', text: '原文' },
          { block_id: 'target', text: '。<script>unsafe()</script>' },
        ],
      },
    ];
  });
  const { container } = render(
    <Reader
      source={{
        id: 'pdf',
        type: 'pdf',
        title: 'PDF',
        status: 'indexed',
        original_filename: 'pdf.pdf',
        enabled: true,
      }}
      initialBlockId="target"
      onClose={() => {}}
    />,
  );
  await waitFor(() =>
    expect(container.querySelector('.reader-content p:last-child')).toHaveTextContent(
      '连续阅读的原文。<script>unsafe()</script>',
    ),
  );
  expect(api).toHaveBeenCalledWith('/sources/pdf/reading?node_id=page2');
  expect(screen.getByLabelText('页码')).toHaveValue(2);
  expect(screen.queryByRole('option', { name: '字' })).toBeNull();
  expect(container.querySelectorAll('#block-target')).toHaveLength(1);
  expect(container.querySelectorAll('.citation-highlight')).toHaveLength(2);
  expect(container.querySelector('script')).toBeNull();
  await waitFor(() => expect(scroll).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText('正文大小'), { target: { value: '20' } });
  expect(container.querySelector('article')).toHaveStyle({ fontSize: '20px' });
  fireEvent.click(screen.getByRole('button', { name: '展开阅读' }));
  expect(container.querySelector('.reader')).toHaveClass('reader-expanded');
  fireEvent.click(screen.getByRole('button', { name: '收起阅读' }));
  expect(container.querySelector('.reader')).not.toHaveClass('reader-expanded');
});

test('restores linked chapters, follows history changes and normalizes deleted chapter IDs', async () => {
  vi.mocked(api).mockImplementation(async (path) => {
    if (path.endsWith('/nodes'))
      return [
        { id: 'page1', type: 'page', title: 'Page 1', depth: 1, start_page: 1 },
        { id: 'page2', type: 'page', title: 'Page 2', depth: 1, start_page: 2 },
      ];
    return [
      {
        type: 'paragraph',
        page_start: path.endsWith('page2') ? 2 : 1,
        parts: [
          { block_id: 'body', text: path.endsWith('page2') ? '第二页正文。' : '第一页正文。' },
        ],
      },
    ];
  });
  const source = {
    id: 'pdf',
    type: 'pdf',
    title: 'PDF',
    status: 'indexed',
    original_filename: 'pdf.pdf',
    enabled: true,
  };
  const location = vi.fn();
  const view = render(
    <Reader source={source} initialNodeId="page2" onLocationChange={location} onClose={() => {}} />,
  );
  await waitFor(() => expect(screen.getByLabelText('页码')).toHaveValue(2));
  expect(await screen.findByText('第二页正文。')).toBeVisible();
  view.rerender(
    <Reader source={source} initialNodeId="page1" onLocationChange={location} onClose={() => {}} />,
  );
  expect(await screen.findByText('第一页正文。')).toBeVisible();
  view.rerender(
    <Reader
      source={source}
      initialNodeId="deleted-node"
      onLocationChange={location}
      onClose={() => {}}
    />,
  );
  await waitFor(() => expect(location).toHaveBeenCalledWith('page1', undefined, true));
  expect(screen.getByLabelText('页码')).toHaveValue(1);
});

test('a source without chapters finishes loading instead of remaining in a spinner', async () => {
  vi.mocked(api).mockResolvedValue([]);
  render(
    <Reader
      source={{
        id: 'empty',
        type: 'text',
        title: 'Empty',
        status: 'parsed',
        original_filename: 'empty.txt',
        enabled: true,
      }}
      onClose={() => {}}
    />,
  );
  expect(await screen.findByText('这一章节没有可显示的正文。')).toBeVisible();
  expect(screen.queryByRole('status')).toBeNull();
});

test('real chapter navigation continues from the footer, stops at boundaries and keeps exact scope', async () => {
  const nodes = [
    { id: 'root', type: 'document', title: 'Book', depth: 0 },
    { id: 'first', parent_id: 'root', type: 'chapter', title: '第一章', depth: 1 },
    { id: 'duplicate', parent_id: 'first', type: 'heading', title: '第一章', depth: 2 },
    { id: 'subsection', parent_id: 'duplicate', type: 'heading', title: '小节', depth: 3 },
    { id: 'second', parent_id: 'root', type: 'chapter', title: '第二章', depth: 1 },
  ];
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith('/nodes')
      ? nodes
      : [
          {
            type: 'paragraph',
            parts: [
              {
                block_id: path.endsWith('second') ? 'b' : 'a',
                text: path.endsWith('second') ? '第二章正文。' : '第一章正文。',
              },
            ],
          },
        ],
  );
  const location = vi.fn(),
    ask = vi.fn();
  const view = render(
    <Reader
      source={{
        id: 'book',
        type: 'epub',
        title: 'Book',
        status: 'indexed',
        original_filename: 'book.epub',
        enabled: true,
      }}
      onClose={() => {}}
      onLocationChange={location}
      onAsk={ask}
    />,
  );
  await screen.findByText('第一章正文。');
  const footer = view.container.querySelector('.reading-turns-bottom')!;
  expect(footer.querySelector('button')).toBeDisabled();
  fireEvent.click(footer.querySelectorAll('button')[1]);
  expect(await screen.findByText('第二章正文。')).toBeVisible();
  expect(location).toHaveBeenCalledWith('second');
  expect(view.container.querySelector('.reading-turns-bottom button:last-child')).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: '就本章节提问' }));
  expect(ask).toHaveBeenCalledWith(
    { kind: 'node', source_id: 'book', node_id: 'second' },
    '第二章',
  );
  await waitFor(() => expect(view.container.querySelector('article')).toHaveFocus());
});

test('PDF pages are separate page controls; real bookmarks alone populate the table of contents', async () => {
  const nodes = [
    { id: 'root', type: 'document', title: 'PDF', depth: 0 },
    {
      id: 'intro',
      parent_id: 'root',
      type: 'chapter',
      title: '真正的引言',
      depth: 1,
      start_page: 1,
    },
    {
      id: 'conclusion',
      parent_id: 'root',
      type: 'chapter',
      title: '真正的结语',
      depth: 1,
      start_page: 2,
    },
    { id: 'page1', parent_id: 'intro', type: 'page', title: 'Page 1', depth: 2, start_page: 1 },
    {
      id: 'page2',
      parent_id: 'conclusion',
      type: 'page',
      title: 'Page 2',
      depth: 2,
      start_page: 2,
    },
    { id: 'glyph', parent_id: 'page1', type: 'heading', title: '字', depth: 3 },
  ];
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith('/nodes')
      ? nodes
      : [
          {
            type: 'paragraph',
            page_start: /(?:conclusion|page2)$/.test(path) ? 2 : 1,
            parts: [{ block_id: 'text', text: '段落正文。' }],
          },
        ],
  );
  render(
    <Reader
      source={{
        id: 'pdf',
        type: 'pdf',
        title: 'PDF',
        status: 'indexed',
        original_filename: 'book.pdf',
        enabled: true,
      }}
      initialNodeId="page2"
      onClose={() => {}}
    />,
  );
  await waitFor(() => expect(screen.getByLabelText('目录 / 章节')).toHaveValue('conclusion'));
  expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(
    expect.arrayContaining(['真正的引言', '真正的结语']),
  );
  expect(screen.queryByRole('option', { name: 'Page 1' })).toBeNull();
  expect(screen.queryByRole('option', { name: '字' })).toBeNull();
  await waitFor(() => expect(screen.getByLabelText('页码')).toHaveValue(2));
});

test('plain text without authored sections does not manufacture a directory or chapter actions', async () => {
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith('/nodes')
      ? [{ id: 'root', type: 'document', title: 'Notes', depth: 0 }]
      : [{ type: 'paragraph', parts: [{ block_id: 'a', text: '没有目录的短文。' }] }],
  );
  const ask = vi.fn();
  render(
    <Reader
      source={{
        id: 'notes',
        type: 'text',
        title: 'Notes',
        status: 'indexed',
        original_filename: 'notes.txt',
        enabled: true,
      }}
      onClose={() => {}}
      onAsk={ask}
    />,
  );
  await screen.findByText('没有目录的短文。');
  expect(screen.queryByLabelText('目录 / 章节')).toBeNull();
  expect(screen.queryByRole('button', { name: '下一章' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '就整份资料提问' }));
  expect(ask).toHaveBeenCalledWith({ kind: 'source', source_id: 'notes' }, 'Notes');
});

test('another citation on the same page resolves without leaving the reader loading', async () => {
  const scroll = vi.spyOn(Element.prototype, 'scrollIntoView');
  vi.mocked(api).mockImplementation(async (path) => {
    if (path.endsWith('/nodes'))
      return [{ id: 'page', type: 'page', title: 'Page 1', depth: 1, start_page: 1 }];
    if (path.endsWith('/blocks'))
      return [
        { id: 'one', node_id: 'page', page_start: 1 },
        { id: 'two', node_id: 'page', page_start: 1 },
      ];
    return [
      {
        type: 'paragraph',
        parts: [
          { block_id: 'one', text: '前段正文。' },
          { block_id: 'two', text: '后段正文。' },
        ],
      },
    ];
  });
  const source = {
    id: 'pdf',
    type: 'pdf',
    title: 'PDF',
    status: 'indexed',
    original_filename: 'book.pdf',
    enabled: true,
  };
  const view = render(
    <Reader source={source} initialNodeId="page" initialBlockId="one" onClose={() => {}} />,
  );
  await waitFor(() =>
    expect(view.container.querySelector('#block-one')).toHaveClass('citation-highlight'),
  );
  scroll.mockClear();
  view.rerender(
    <Reader source={source} initialNodeId="page" initialBlockId="two" onClose={() => {}} />,
  );
  await waitFor(() =>
    expect(view.container.querySelector('#block-two')).toHaveClass('citation-highlight'),
  );
  expect(screen.queryByRole('status')).toBeNull();
  expect(view.container.querySelector('#block-one')).not.toHaveClass('citation-highlight');
  await waitFor(() => expect(scroll).toHaveBeenCalled());
});

test('synchronizing a locally selected node into the URL preserves the focused article', async () => {
  vi.mocked(api).mockImplementation(async (path) =>
    path.endsWith('/nodes')
      ? [
          { id: 'p1', type: 'page', title: 'Page 1', start_page: 1, depth: 1 },
          { id: 'p2', type: 'page', title: 'Page 2', start_page: 2, depth: 1 },
        ]
      : [
          {
            type: 'paragraph',
            parts: [{ block_id: 'body', text: path.endsWith('p2') ? '第二页' : '第一页' }],
          },
        ],
  );
  const source = {
    id: 'pdf',
    type: 'pdf',
    title: 'PDF',
    status: 'indexed',
    original_filename: 'book.pdf',
    enabled: true,
  };
  const view = render(<Reader source={source} initialNodeId="p1" onClose={() => {}} />);
  await screen.findByText('第一页');
  fireEvent.click(view.container.querySelector('.reading-turns-bottom button:last-child')!);
  await screen.findByText('第二页');
  const article = view.container.querySelector('article');
  await waitFor(() => expect(article).toHaveFocus());
  const requests = vi.mocked(api).mock.calls.length;
  view.rerender(<Reader source={source} initialNodeId="p2" onClose={() => {}} />);
  expect(view.container.querySelector('article')).toBe(article);
  expect(article).toHaveFocus();
  expect(api).toHaveBeenCalledTimes(requests);
});
