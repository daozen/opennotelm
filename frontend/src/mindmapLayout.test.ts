import { expect, test } from 'vitest';
import type { MindMapNode } from './api';
import { labelDirection, labelLines, mapLayout, mapSvg } from './mindmapLayout';
const nodes: MindMapNode[] = [
  { id: 'r', parent_id: null, label: 'Root', detail: '', basis: 'structural', evidence_ids: [] },
  {
    id: 'a',
    parent_id: 'r',
    label: '文'.repeat(120),
    detail: '',
    basis: 'source',
    evidence_ids: ['E1'],
  },
  { id: 'b', parent_id: 'a', label: 'Leaf', detail: '', basis: 'source', evidence_ids: ['E1'] },
  {
    id: 'c',
    parent_id: 'r',
    label: '<script>alert("x")</script>',
    detail: '',
    basis: 'source',
    evidence_ids: ['E1'],
  },
];
test('long multilingual labels fit node height; collapsing removes only descendants', () => {
  const layout = mapLayout(nodes);
  expect(layout.nodes).toHaveLength(4);
  expect(layout.nodes[1].h).toBeGreaterThan(64);
  expect(labelLines(nodes[1].label).join('')).toBe(nodes[1].label);
  const collapsed = mapLayout(nodes, new Set(['a']));
  expect(collapsed.nodes.map((n) => n.node.id)).toEqual(['r', 'a', 'c']);
  expect(collapsed.nodes[2].y).toBeGreaterThan(collapsed.nodes[1].y + collapsed.nodes[1].h);
});
test('SVG export is a complete tree with escaped text and no active markup', () => {
  const svg = mapSvg(nodes, '<img src=x onerror="run()">');
  expect(svg).not.toContain('<script>');
  expect(svg).not.toContain('<img');
  expect(svg).toContain('Leaf');
  expect(svg).toContain('&lt;');
  expect(svg.match(/<rect x=/g)).toHaveLength(4);
  expect(labelLines('Review the learning experience')).toEqual([
    'Review the learning',
    'experience',
  ]);
  expect(labelDirection('التعلم والممارسة')).toBe('rtl');
  expect(mapSvg([{ ...nodes[0], label: 'التعلم والممارسة' }], 'Map')).toContain('direction="rtl"');
});
