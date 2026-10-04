import { render, screen, fireEvent } from '@testing-library/react';
import { expect, test, vi } from 'vitest';
import { KnowledgeMarkdown } from './Knowledge';

test('knowledge markdown keeps citations interactive without loading external content or HTML', () => {
  const onCitation = vi.fn();
  const page = {
    id: 'page',
    notebook_id: 'notebook',
    title: 'Safe knowledge',
    revision: 1,
    updated_at: '',
    generation_metadata: {},
    content_markdown:
      '# A heading\n\nSupported fact [[E1]].\n\n![tracker](https://invalid.example/track)\n\n<iframe src="https://invalid.example"></iframe>\n\n<script>secret()</script>\n\n[link](javascript:alert(1))',
    citations: { E1: 'citation1' },
  };
  const { container } = render(<KnowledgeMarkdown page={page} onCitation={onCitation} />);
  expect(screen.getByRole('heading', { name: 'A heading' })).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: '查看引用 1' }));
  expect(onCitation).toHaveBeenCalledWith('citation1');
  expect(container.querySelector('img, iframe, script, a')).toBeNull();
});
