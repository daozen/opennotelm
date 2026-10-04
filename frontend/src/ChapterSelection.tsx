import { useEffect, useRef, useState, type KeyboardEvent, type InputHTMLAttributes } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { api, type Scope, type Source, type SourceNode } from './api';
import {
  chapterTree,
  coverChapters,
  flattenChapters,
  selectedChapters,
  type ChapterBranch,
} from './chapterTree';
import { t, useI18n } from './i18n';

function ChapterCheckbox({
  mixed,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { mixed: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (input.current) input.current.indeterminate = mixed;
  }, [mixed]);
  return (
    <input {...props} ref={input} type="checkbox" aria-checked={mixed ? 'mixed' : props.checked} />
  );
}

export default function ChapterSelection({
  source,
  initialNode,
  initialNodes,
  mode = 'merged',
  onChange,
}: {
  source: Source;
  initialNode?: string;
  initialNodes?: string[];
  mode?: 'merged' | 'separate';
  onChange: (scope: Scope | undefined, valid: boolean) => void;
}) {
  useI18n();
  const initial = initialNodes ?? (initialNode ? [initialNode] : []);
  const [tree, setTree] = useState<ChapterBranch[]>([]);
  const [busy, setBusy] = useState(true),
    [error, setError] = useState('');
  const [enabled, setEnabled] = useState(initial.length > 0);
  const [chosen, setChosen] = useState<string[]>(initial);
  const [collapsed, setCollapsed] = useState<string[]>([]);
  const [retry, setRetry] = useState(0);
  const change = useRef(onChange);
  change.current = onChange;
  useEffect(() => {
    let active = true;
    setBusy(true);
    setError('');
    change.current(undefined, false);
    api<SourceNode[]>(`/sources/${source.id}/nodes`)
      .then((all) => {
        if (!active) return;
        const directory = chapterTree(source, all, initial);
        const picked = coverChapters(directory, chosen);
        setTree(directory);
        setChosen(picked);
        setCollapsed(
          flattenChapters(directory)
            .filter((b) => b.level > 1 && b.children.length)
            .map((b) => b.node.id),
        );
        change.current(
          enabled && directory.length
            ? { kind: 'nodes', source_id: source.id, node_ids: selectedChapters(directory, picked) }
            : { kind: 'source', source_id: source.id },
          !enabled || !directory.length || picked.length > 0,
        );
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [source.id, retry]);
  const all = flattenChapters(tree);
  function update(useChapters: boolean, values: string[]) {
    setEnabled(useChapters);
    setChosen(values);
    const roots = selectedChapters(tree, values);
    change.current(
      useChapters
        ? { kind: 'nodes', source_id: source.id, node_ids: roots }
        : { kind: 'source', source_id: source.id },
      !useChapters || roots.length > 0,
    );
  }
  function toggle(branch: ChapterBranch, checked: boolean) {
    const subtree = flattenChapters([branch]).map((b) => b.node.id);
    if (checked) update(true, [...new Set([...chosen, ...subtree])]);
    else {
      // A partially selected ancestor must not bring excluded children back into its scope.
      const ancestors = all
        .filter((b) => flattenChapters(b.children).some((c) => c.node.id === branch.node.id))
        .map((b) => b.node.id);
      update(
        true,
        chosen.filter((id) => !subtree.includes(id) && !ancestors.includes(id)),
      );
    }
  }
  function expand(id: string) {
    setCollapsed((values) =>
      values.includes(id) ? values.filter((v) => v !== id) : [...values, id],
    );
  }
  function keyboard(event: KeyboardEvent<HTMLUListElement>) {
    if (!(event.target instanceof HTMLInputElement)) return;
    const inputs = [
      ...event.currentTarget.querySelectorAll<HTMLInputElement>('input[data-chapter-id]'),
    ];
    const index = inputs.indexOf(event.target);
    const branch = all.find(
      (b) => b.node.id === (event.target as HTMLInputElement).dataset.chapterId,
    );
    if (!branch) return;
    let target: HTMLInputElement | undefined;
    if (event.key === 'ArrowDown') target = inputs[index + 1];
    else if (event.key === 'ArrowUp') target = inputs[index - 1];
    else if (event.key === 'Home') target = inputs[0];
    else if (event.key === 'End') target = inputs.at(-1);
    else if (event.key === 'ArrowRight' && branch.children.length) {
      if (collapsed.includes(branch.node.id)) expand(branch.node.id);
      else target = inputs[index + 1];
    } else if (event.key === 'ArrowLeft') {
      if (branch.children.length && !collapsed.includes(branch.node.id)) expand(branch.node.id);
      else {
        const parent = all.find((b) => b.children.includes(branch));
        target = inputs.find((input) => input.dataset.chapterId === parent?.node.id);
      }
    } else return;
    event.preventDefault();
    target?.focus();
  }
  function branches(items: ChapterBranch[]) {
    return items.map((branch) => {
      const selected = chosen.includes(branch.node.id);
      const mixed =
        !selected && flattenChapters(branch.children).some((b) => chosen.includes(b.node.id));
      const opened = !collapsed.includes(branch.node.id);
      return (
        <li
          key={branch.node.id}
          role="treeitem"
          aria-label={branch.node.title}
          aria-level={branch.level}
          aria-expanded={branch.children.length ? opened : undefined}
        >
          <div className="chapter-tree-row">
            {branch.children.length ? (
              <button
                type="button"
                className="icon-button chapter-toggle"
                aria-label={t(opened ? '折叠目录 · {{title}}' : '展开目录 · {{title}}', {
                  title: branch.node.title,
                })}
                onClick={() => expand(branch.node.id)}
              >
                {opened ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>
            ) : (
              <span className="chapter-toggle-spacer" />
            )}
            <label>
              <ChapterCheckbox
                data-chapter-id={branch.node.id}
                aria-label={t('章节 · {{title}}', { title: branch.node.title })}
                mixed={mixed}
                checked={selected}
                onChange={(e) => toggle(branch, e.target.checked)}
              />
              <span>
                {branch.node.title}
                {branch.node.start_page
                  ? ` · ${t('第 {{v1}} 页', { v1: branch.node.start_page })}`
                  : ''}
              </span>
            </label>
          </div>
          {opened && branch.children.length > 0 && (
            <ul role="group" style={branch.level >= 6 ? { paddingLeft: 0 } : undefined}>
              {branches(branch.children)}
            </ul>
          )}
        </li>
      );
    });
  }
  if (busy)
    return (
      <p role="status" className="help">
        {t('正在读取目录…')}
      </p>
    );
  if (error)
    return (
      <div>
        <p className="error" role="alert">
          {t(error)}
        </p>
        <button type="button" className="button ghost" onClick={() => setRetry((v) => v + 1)}>
          {t('重试')}
        </button>
      </div>
    );
  if (!tree.length)
    return <p className="help">{t('这份资料没有可选择的章节目录，将使用整份资料。')}</p>;
  return (
    <fieldset className="chapter-selection">
      <legend>{t('章节范围')}</legend>
      <label className="checkbox-line">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => update(e.target.checked, chosen)}
        />
        {t('只使用所选章节')}
      </label>
      {enabled && (
        <>
          <div className="chapter-selection-actions">
            <button
              type="button"
              className="button ghost"
              onClick={() =>
                update(
                  true,
                  all.map((b) => b.node.id),
                )
              }
            >
              {t('选择全部')}
            </button>
            <button type="button" className="button ghost" onClick={() => update(true, [])}>
              {t('清空章节选择')}
            </button>
            <button type="button" className="button ghost" onClick={() => setCollapsed([])}>
              {t('展开全部')}
            </button>
            <button
              type="button"
              className="button ghost"
              onClick={() =>
                setCollapsed(all.filter((b) => b.children.length).map((b) => b.node.id))
              }
            >
              {t('折叠全部')}
            </button>
          </div>
          <label className="chapter-level-choice">
            {t('按目录层级选择')}
            <select
              aria-label={t('按目录层级选择')}
              value=""
              onChange={(e) => {
                const level = Number(e.target.value);
                update(
                  true,
                  coverChapters(
                    tree,
                    all.filter((b) => b.level === level).map((b) => b.node.id),
                  ),
                );
                setCollapsed([]);
              }}
            >
              <option value="" disabled>
                {t('选择层级…')}
              </option>
              {[...new Set(all.map((b) => b.level))].map((level) => (
                <option key={level} value={level}>
                  {t('第 {{level}} 级目录', { level })}
                </option>
              ))}
            </select>
          </label>
          <ul
            className="chapter-options chapter-tree"
            role="tree"
            aria-label={t('章节目录')}
            onKeyDown={keyboard}
          >
            {branches(tree)}
          </ul>
          <p className="help">
            {t(
              mode === 'separate'
                ? '已选 {{count}} 个章节，分别生成 {{count}} 份 Deck。'
                : '已选 {{count}} 个章节，合并生成一份 Deck。',
              { count: selectedChapters(tree, chosen).length },
            )}
          </p>
          <p className="help">{t('父目录包含下级内容；分别生成时，所选父目录对应一份 Deck。')}</p>
        </>
      )}
    </fieldset>
  );
}
