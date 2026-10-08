import type { MindMapNode } from './api';

export function labelLines(text: string): string[] {
  const result: string[] = [];
  let line = '',
    width = 0;
  for (const char of text.replace(/\s+/g, ' ')) {
    const size = /[^\u0000-\u00ff]/.test(char) ? 2 : 1;
    if (width + size > 25) {
      const space = line.lastIndexOf(' ');
      if (space > 0) {
        result.push(line.slice(0, space));
        line = line.slice(space + 1);
        width = [...line].reduce((sum, c) => sum + (/[^\u0000-\u00ff]/.test(c) ? 2 : 1), 0);
      } else {
        result.push(line);
        line = '';
        width = 0;
      }
    }
    if (!line && char === ' ') continue;
    line += char;
    width += size;
  }
  if (line) result.push(line);
  return result;
}
export function mapLayout(nodes: MindMapNode[], collapsed: Set<string> = new Set()) {
  const children = new Map<string | null, MindMapNode[]>();
  for (const node of nodes)
    children.set(node.parent_id, [...(children.get(node.parent_id) ?? []), node]);
  const placed: {
    node: MindMapNode;
    x: number;
    y: number;
    h: number;
    lines: string[];
    branch: number;
    children: number;
  }[] = [];
  const sizes = new Map<string, number>();
  const height = (node: MindMapNode): number => {
    const own = Math.max(64, labelLines(node.label).length * 20 + 24);
    const kids = collapsed.has(node.id) ? [] : (children.get(node.id) ?? []);
    const total = Math.max(own, kids.reduce((sum, child) => sum + height(child) + 20, 0) - 20);
    sizes.set(node.id, total);
    return total;
  };
  const root = children.get(null)?.[0];
  if (!root) return { nodes: placed, width: 280, height: 200 };
  height(root);
  const visit = (node: MindMapNode, depth: number, top: number, branch: number) => {
    const lines = labelLines(node.label),
      h = Math.max(64, lines.length * 20 + 24),
      size = sizes.get(node.id)!;
    placed.push({
      node,
      x: 28 + depth * 280,
      y: top + (size - h) / 2,
      h,
      lines,
      branch,
      children: children.get(node.id)?.length ?? 0,
    });
    let y = top;
    if (!collapsed.has(node.id))
      for (const [index, child] of (children.get(node.id) ?? []).entries()) {
        visit(child, depth + 1, y, depth === 0 ? index : branch);
        y += sizes.get(child.id)! + 20;
      }
  };
  visit(root, 0, 28, 0);
  return {
    nodes: placed,
    width: Math.max(...placed.map((n) => n.x)) + 252,
    height: sizes.get(root.id)! + 56,
  };
}
export const labelDirection = (label: string): 'rtl' | 'ltr' =>
  /^[^A-Za-z\u0590-\u08ff]*[\u0590-\u08ff]/.test(label) ? 'rtl' : 'ltr';
export const branchColors = ['#315b48', '#526ca3', '#975d3c', '#7b5798', '#377986', '#95683a'];
export function mapSvg(nodes: MindMapNode[], title: string) {
  const layout = mapLayout(nodes);
  const escape = (s: string) =>
    s.replace(
      /[&<>"']/g,
      (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[c]!,
    );
  const connections = layout.nodes
    .flatMap((n) => {
      const parent = layout.nodes.find((p) => p.node.id === n.node.parent_id);
      return parent
        ? [
            `<path d="M${parent.x + 224},${parent.y + parent.h / 2} C${parent.x + 252},${parent.y + parent.h / 2} ${n.x - 28},${n.y + n.h / 2} ${n.x},${n.y + n.h / 2}" fill="none" stroke="#bacbbb" stroke-width="2"/>`,
          ]
        : [];
    })
    .join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${layout.width}" height="${layout.height}" viewBox="0 0 ${layout.width} ${layout.height}"><title>${escape(title)}</title><rect width="100%" height="100%" fill="#fafbf7"/>${connections}${layout.nodes.map((n) => `<g><rect x="${n.x}" y="${n.y}" width="224" height="${n.h}" rx="12" fill="white" stroke="${branchColors[n.branch % branchColors.length]}" stroke-width="2"/><text x="${n.x + (labelDirection(n.node.label) === 'rtl' ? 210 : 14)}" y="${n.y + 28}" font-family="system-ui,sans-serif" font-size="14" fill="#263b30" direction="${labelDirection(n.node.label)}" text-anchor="start">${n.lines.map((line, i) => `<tspan x="${n.x + (labelDirection(n.node.label) === 'rtl' ? 210 : 14)}" dy="${i ? 20 : 0}">${escape(line)}</tspan>`).join('')}</text></g>`).join('')}</svg>`;
}
