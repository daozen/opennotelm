import type { SourceNode } from './api';

// PDF pages and inferred drawing headings are locations, not a table of contents.
export function readingSections(type: string, nodes: SourceNode[]) {
  const chapters = nodes.filter((node) => node.type === 'chapter');
  // EPUB chapter headings duplicate the spine chapter and must not be extra stops.
  return chapters.length || type === 'pdf'
    ? chapters
    : nodes.filter((node) => node.type === 'heading');
}

export function sectionForNode(
  node: SourceNode | undefined,
  sections: SourceNode[],
  nodes: SourceNode[],
) {
  const seen = new Set<string>();
  while (node && !seen.has(node.id)) {
    if (sections.some((section) => section.id === node!.id)) return node;
    seen.add(node.id);
    node = nodes.find((candidate) => candidate.id === node!.parent_id);
  }
  return undefined;
}
