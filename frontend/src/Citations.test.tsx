import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { CitationPreview } from './Citations';

const paragraph =
  '这是按字绘制的中文资料，阅读时应该恢复完整段落。保留原始引用，才能准确返回资料中的位置。';
const span = {
  source_id: 'source',
  block_id: 'original-glyph',
  available: true,
  quote: '原',
  page: 2,
};

describe('Citation paragraph preview', () => {
  it('shows one complete paragraph for an old glyph citation and opens its exact original anchor', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 'old',
          available: true,
          spans: [span],
          passages: [
            {
              source_id: 'source',
              source_title: '原始 PDF',
              page: 2,
              anchor_block_id: 'original-glyph',
              available: true,
              text: paragraph,
            },
          ],
        }),
      ),
    );
    const onOpen = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    render(<CitationPreview id="old" onOpen={onOpen} onClose={onClose} />);
    const dialog = await screen.findByRole('dialog', { name: '原文引用' });
    await within(dialog).findByText(paragraph);
    expect(dialog.querySelectorAll('blockquote')).toHaveLength(1);
    expect(within(dialog).queryByText('原', { exact: true })).toBeNull();
    expect(within(dialog).getByText('第 2 页')).toBeVisible();
    fireEvent.click(within(dialog).getByRole('button', { name: '打开原文' }));
    await waitFor(() => expect(onOpen).toHaveBeenCalledWith('source', 'original-glyph'));
    expect(onClose).toHaveBeenCalledOnce();
  });
  it('keeps unavailable sources visible without an open-source action', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          id: 'deleted',
          available: false,
          spans: [{ ...span, available: false }],
          passages: [{ source_id: 'source', available: false, anchor_block_id: 'original-glyph' }],
        }),
      ),
    );
    render(<CitationPreview id="deleted" onOpen={vi.fn()} onClose={vi.fn()} />);
    expect(
      await screen.findByText('原始资料已不可用（Original source unavailable）。'),
    ).toBeVisible();
    expect(screen.queryByRole('button', { name: '打开原文' })).toBeNull();
  });
});
