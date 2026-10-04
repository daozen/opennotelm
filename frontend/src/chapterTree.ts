import type { Source, SourceNode } from './api';

export type ChapterBranch = { node: SourceNode; children: ChapterBranch[]; level: number };

export function chapterTree(source: Source, all: SourceNode[], initial: string[] = []) {
  let nodes = all.filter(
    (n) => n.type === (['docx', 'web'].includes(source.type) ? 'heading' : 'chapter'),
  );
  let tocOrder = false;
  if (source.type === 'epub' && source.metadata?.toc?.length) {
    const mapped = source.metadata.toc.flatMap((entry) => {
      const node = all.find(
        (n) =>
          n.metadata?.href === entry.href &&
          (entry.fragment ? n.metadata?.element_id === entry.fragment : n.type === 'chapter'),
      );
      return node
        ? [{ ...node, title: entry.title || node.title, depth: entry.depth ?? node.depth }]
        : [];
    });
    if (mapped.length) {
      nodes = mapped.filter((n, i) => mapped.findIndex((other) => other.id === n.id) === i);
      tocOrder = true;
    }
  }
  nodes = [
    ...all.filter((n) => initial.includes(n.id) && !nodes.some((c) => c.id === n.id)),
    ...nodes,
  ];
  const index = new Map(nodes.map((n, i) => [n.id, i]));
  const byId = new Map(all.map((n) => [n.id, n]));
  const branches = new Map(
    nodes.map((node) => [node.id, { node, children: [], level: 1 } as ChapterBranch]),
  );
  const roots: ChapterBranch[] = [],
    stack: SourceNode[] = [];
  for (const [position, node] of nodes.entries()) {
    while (stack.length && stack.at(-1)!.depth >= node.depth) stack.pop();
    let parent = node.parent_id;
    const seen = new Set<string>([node.id]);
    while (parent && !index.has(parent) && !seen.has(parent)) {
      seen.add(parent);
      parent = byId.get(parent)?.parent_id;
    }
    if (tocOrder || (!node.parent_id && !parent)) parent = stack.at(-1)?.id;
    const container =
      parent && (index.get(parent) ?? position) < position ? branches.get(parent) : undefined;
    const branch = branches.get(node.id)!;
    branch.level = container ? container.level + 1 : 1;
    (container?.children ?? roots).push(branch);
    stack.push(node);
  }
  return roots;
}

export function flattenChapters(tree: ChapterBranch[]): ChapterBranch[] {
  return tree.flatMap((branch) => [branch, ...flattenChapters(branch.children)]);
}

export function selectedChapters(tree: ChapterBranch[], chosen: string[]): string[] {
  const selected = new Set(chosen);
  return tree.flatMap((branch) =>
    selected.has(branch.node.id) ? [branch.node.id] : selectedChapters(branch.children, chosen),
  );
}

export function coverChapters(tree: ChapterBranch[], selected: string[]): string[] {
  const requested = new Set(selected);
  return tree.flatMap((branch) =>
    requested.has(branch.node.id)
      ? flattenChapters([branch]).map((b) => b.node.id)
      : coverChapters(branch.children, selected),
  );
}
