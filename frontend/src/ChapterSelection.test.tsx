import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import ChapterSelection from './ChapterSelection';
import { api, type Source } from './api';

vi.mock('./api', () => ({ api: vi.fn() }));
const source: Source = {
  id: 'book',
  type: 'pdf',
  title: 'Book',
  original_filename: 'book.pdf',
  status: 'parsed',
  enabled: true,
};
const nodes = [
  { id: 'a', type: 'chapter', title: 'First', depth: 1, start_page: 1 },
  { id: 'b', type: 'chapter', title: 'Second', depth: 1, start_page: 5 },
  { id: 'page', type: 'page', title: 'Page', depth: 2 },
];

test('batch selection, empty validation and disabling chapter filter use the correct scope', async () => {
  vi.mocked(api).mockResolvedValue(nodes);
  const changed = vi.fn();
  render(<ChapterSelection source={source} initialNode="a" onChange={changed} />);
  await screen.findByRole('checkbox', { name: '章节 · First' });
  expect(screen.queryByRole('checkbox', { name: '章节 · Page' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '选择全部' }));
  expect(changed).toHaveBeenLastCalledWith(
    { kind: 'nodes', source_id: 'book', node_ids: ['a', 'b'] },
    true,
  );
  fireEvent.click(screen.getByRole('button', { name: '清空章节选择' }));
  expect(changed).toHaveBeenLastCalledWith(
    { kind: 'nodes', source_id: 'book', node_ids: [] },
    false,
  );
  fireEvent.click(screen.getByRole('checkbox', { name: '只使用所选章节' }));
  expect(changed).toHaveBeenLastCalledWith({ kind: 'source', source_id: 'book' }, true);
});

test('a PDF without an outline uses the entire source rather than making pages into chapters', async () => {
  vi.mocked(api).mockResolvedValue(nodes.filter((n) => n.type === 'page'));
  const changed = vi.fn();
  render(<ChapterSelection source={source} onChange={changed} />);
  await screen.findByText('这份资料没有可选择的章节目录，将使用整份资料。');
  expect(changed).toHaveBeenLastCalledWith({ kind: 'source', source_id: 'book' }, true);
});

test('EPUB navigation anchors map to real nodes and loading can recover', async () => {
  vi.mocked(api)
    .mockRejectedValueOnce(new Error('请求失败，请重试。'))
    .mockResolvedValue([
      { id: 'a', type: 'chapter', title: 'First', depth: 1, metadata: { href: 'a.xhtml' } },
      {
        id: 'b',
        type: 'heading',
        title: 'Topic',
        depth: 2,
        metadata: { href: 'a.xhtml', element_id: 'topic' },
      },
      {
        id: 'other',
        type: 'chapter',
        title: 'Not in TOC',
        depth: 1,
        metadata: { href: 'other.xhtml' },
      },
    ]);
  render(
    <ChapterSelection
      source={{
        ...source,
        type: 'epub',
        metadata: {
          toc: [
            { href: 'a.xhtml', fragment: '' },
            { href: 'a.xhtml', fragment: 'topic' },
          ],
        },
      }}
      onChange={vi.fn()}
    />,
  );
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: '重试' }));
  await waitFor(() =>
    expect(screen.getByRole('checkbox', { name: '只使用所选章节' })).toBeEnabled(),
  );
  fireEvent.click(screen.getByRole('checkbox', { name: '只使用所选章节' }));
  expect(screen.getByRole('checkbox', { name: '章节 · Topic' })).toBeVisible();
  expect(screen.queryByText('Not in TOC')).toBeNull();
});

test('tree parents cover descendants, exclusions become mixed and directory levels define separate Decks', async () => {
  vi.mocked(api).mockResolvedValue([
    { id: 'p', type: 'chapter', title: 'Parent', depth: 1 },
    { id: 'a', parent_id: 'p', type: 'chapter', title: 'Alpha', depth: 2 },
    { id: 'detail', parent_id: 'a', type: 'chapter', title: 'Detail', depth: 3 },
    { id: 'b', parent_id: 'p', type: 'chapter', title: 'Beta', depth: 2 },
    { id: 'q', type: 'chapter', title: 'Other', depth: 1 },
  ]);
  const changed = vi.fn();
  render(<ChapterSelection source={source} mode="separate" onChange={changed} />);
  fireEvent.click(await screen.findByRole('checkbox', { name: '只使用所选章节' }));
  const parent = screen.getByRole('checkbox', { name: '章节 · Parent' });
  const alpha = screen.getByRole('checkbox', { name: '章节 · Alpha' });
  const beta = screen.getByRole('checkbox', { name: '章节 · Beta' });
  fireEvent.click(parent);
  expect(changed).toHaveBeenLastCalledWith(
    { kind: 'nodes', source_id: 'book', node_ids: ['p'] },
    true,
  );
  expect(alpha).toBeChecked();
  expect(beta).toBeChecked();
  fireEvent.click(alpha);
  expect(parent).toBePartiallyChecked();
  expect(changed).toHaveBeenLastCalledWith(
    { kind: 'nodes', source_id: 'book', node_ids: ['b'] },
    true,
  );
  fireEvent.change(screen.getByLabelText('按目录层级选择'), { target: { value: '2' } });
  expect(changed).toHaveBeenLastCalledWith(
    { kind: 'nodes', source_id: 'book', node_ids: ['a', 'b'] },
    true,
  );
  expect(screen.getByText('已选 2 个章节，分别生成 2 份 Deck。')).toBeVisible();
  expect(screen.getByRole('checkbox', { name: '章节 · Detail' })).toBeChecked();
  fireEvent.click(screen.getByRole('button', { name: '折叠目录 · Parent' }));
  expect(screen.queryByRole('checkbox', { name: '章节 · Alpha' })).toBeNull();
  expect(screen.getByText('已选 2 个章节，分别生成 2 份 Deck。')).toBeVisible();
  parent.focus();
  fireEvent.keyDown(parent, { key: 'ArrowRight' });
  fireEvent.keyDown(parent, { key: 'ArrowDown' });
  expect(screen.getByRole('checkbox', { name: '章节 · Alpha' })).toHaveFocus();
  fireEvent.keyDown(screen.getByRole('checkbox', { name: '章节 · Beta' }), { key: 'ArrowLeft' });
  expect(parent).toHaveFocus();
  fireEvent.change(screen.getByLabelText('按目录层级选择'), { target: { value: '1' } });
  expect(changed).toHaveBeenLastCalledWith(
    { kind: 'nodes', source_id: 'book', node_ids: ['p', 'q'] },
    true,
  );
});

test('linked multi-chapter choices are restored without widening to the entire source', async () => {
  vi.mocked(api).mockResolvedValue(nodes);
  const changed = vi.fn();
  render(<ChapterSelection source={source} initialNodes={['b']} onChange={changed} />);
  expect(await screen.findByRole('checkbox', { name: '章节 · Second' })).toBeChecked();
  expect(screen.getByRole('checkbox', { name: '章节 · First' })).not.toBeChecked();
  expect(changed).toHaveBeenLastCalledWith(
    { kind: 'nodes', source_id: 'book', node_ids: ['b'] },
    true,
  );
});
