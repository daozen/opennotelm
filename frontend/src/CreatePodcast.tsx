import Modal from './Modal';
import { languages, t, useI18n } from './i18n';
import { useRef, useState } from 'react';
import { X } from 'lucide-react';
import {
  api,
  type Podcast,
  type MindMap,
  type DeckScope,
  type Source,
  type KnowledgePage,
} from './api';
import ChapterSelection from './ChapterSelection';
import ArtifactInstructions from './ArtifactInstructions';

type CreateProps = {
  notebookId: string;
  initialScope: DeckScope;
  initialLabel: string;
  initialLanguage?: string;
  sources: Source[];
  pages: KnowledgePage[];
  onClose: () => void;
};
export default function CreatePodcast({
  onCreated,
  ...props
}: CreateProps & { onCreated: (podcast: Podcast, count?: number) => void }) {
  return (
    <CreateTextArtifact
      {...props}
      kind="podcast"
      onCreated={(value, count) => onCreated(value as Podcast, count)}
    />
  );
}
export function CreateMindMap({
  onCreated,
  ...props
}: CreateProps & { onCreated: (map: MindMap, count?: number) => void }) {
  return (
    <CreateTextArtifact
      {...props}
      kind="mindmap"
      onCreated={(value, count) => onCreated(value as MindMap, count)}
    />
  );
}
function CreateTextArtifact({
  notebookId,
  initialScope,
  initialLabel,
  initialLanguage,
  sources,
  pages,
  onClose,
  onCreated,
  kind,
}: CreateProps & {
  kind: 'podcast' | 'mindmap';
  onCreated: (artifact: Podcast | MindMap, count?: number) => void;
}) {
  const isMap = kind === 'mindmap';
  const endpoint = isMap ? 'mindmaps' : 'podcasts';
  const uiLanguage = useI18n();
  const options: { key: string; label: string; scope: DeckScope }[] = [
    {
      key: 'selected',
      label: t('所选资料（{{v1}} 份）', { v1: sources.filter((s) => s.enabled).length }),
      scope: { kind: 'selected' },
    },
    ...(initialScope.kind === 'node'
      ? [{ key: 'chapter', label: initialLabel, scope: initialScope }]
      : []),
    ...sources
      .filter((s) => s.parser_version)
      .map((source) => ({
        key: `source:${source.id}`,
        label: t('资料 · {{v1}}', { v1: source.title }),
        scope: { kind: 'source' as const, source_id: source.id },
      })),
    ...pages
      .filter((p) => p.content_markdown)
      .map((page) => ({
        key: `knowledge:${page.id}`,
        label: t('知识 · {{v1}}', { v1: page.title }),
        scope: { kind: 'knowledge' as const, knowledge_page_id: page.id },
      })),
  ];
  const initial =
    initialScope.kind === 'knowledge'
      ? `knowledge:${initialScope.knowledge_page_id}`
      : initialScope.kind === 'source' || initialScope.kind === 'nodes'
        ? `source:${initialScope.source_id}`
        : initialScope.kind === 'node'
          ? 'chapter'
          : 'selected';
  const [selection, setSelection] = useState(initial);
  const [count, setCount] = useState(10);
  const [format, setFormat] = useState('dialogue');
  const [scriptOnly, setScriptOnly] = useState(false);
  const [language, setLanguage] = useState<string>(initialLanguage ?? uiLanguage);
  const [instruction, setInstruction] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<'merged' | 'separate'>('merged');
  const [titleMode, setTitleMode] = useState<'auto' | 'source'>('auto');
  const [sourceChoices, setSourceChoices] = useState(
    initialScope.source_ids ??
      sources.filter((source) => source.enabled).map((source) => source.id),
  );
  const submitted = useRef<{ body: string; key: string } | undefined>(undefined);
  const [chapterChoice, setChapterChoice] = useState<{ scope?: DeckScope; valid: boolean }>({
    valid: true,
  });
  const option = options.find((o) => o.key === selection);
  const chapterSource = sources.find((s) => s.id === option?.scope.source_id);
  const selectedSources = sources.filter(
    (source) => source.enabled && sourceChoices.includes(source.id),
  );
  const scope =
    selection === 'selected'
      ? { kind: 'selected' as const, source_ids: selectedSources.map((source) => source.id) }
      : (chapterChoice.scope ?? option?.scope);
  const separateCount =
    scope?.kind === 'selected'
      ? selectedSources.length
      : scope?.kind === 'nodes'
        ? (scope.node_ids?.length ?? 0)
        : 1;
  const episodeCount = mode === 'separate' ? separateCount : 1;
  const sourceNaming =
    scope?.kind !== 'knowledge' &&
    (mode === 'separate' ||
      (scope?.kind === 'selected'
        ? selectedSources.length === 1
        : scope?.kind === 'nodes'
          ? scope.node_ids?.length === 1
          : !!scope));
  const invalid =
    !option ||
    !chapterChoice.valid ||
    (selection === 'selected' &&
      (!selectedSources.length || selectedSources.some((source) => !source.parser_version))) ||
    (mode === 'separate' && episodeCount > 100);
  return (
    <Modal onClose={onClose} busy={busy}>
      <form
        className="small-dialog deck-create"
        role="dialog"
        aria-modal="true"
        aria-labelledby="deck-create-title"
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setError('');
          try {
            if (invalid) return;
            const payload = {
              scope,
              ...(!isMap ? { target_minutes: count, format, script_only: scriptOnly } : {}),
              language,
              instruction,
              title_mode: sourceNaming ? titleMode : 'auto',
            };
            if (mode === 'separate') {
              const body = JSON.stringify(payload);
              if (submitted.current?.body !== body)
                submitted.current = {
                  body,
                  // getRandomValues also works on the user's HTTP LAN origin.
                  key: [...crypto.getRandomValues(new Uint8Array(16))]
                    .map((v) => v.toString(16).padStart(2, '0'))
                    .join(''),
                };
              const batch = await api<{ podcasts?: Podcast[]; mindmaps?: MindMap[] }>(
                `/notebooks/${notebookId}/${endpoint}/batch`,
                {
                  method: 'POST',
                  body: JSON.stringify({ ...payload, request_key: submitted.current.key }),
                },
              );
              const items = isMap ? batch.mindmaps! : batch.podcasts!;
              onCreated(items[0], items.length);
            } else {
              const podcast = await api<Podcast | MindMap>(`/notebooks/${notebookId}/${endpoint}`, {
                method: 'POST',
                body: JSON.stringify(payload),
              });
              onCreated(podcast, 1);
            }
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="dialog-top">
          <h2 id="deck-create-title">{t(isMap ? '生成思维导图' : '生成 Podcast')}</h2>
          <button
            type="button"
            className="icon-button"
            aria-label={t(isMap ? '关闭思维导图创建' : '关闭 Podcast 创建')}
            disabled={busy}
            onClick={onClose}
          >
            <X size={19} />
          </button>
        </div>
        <p className="help">
          {t(
            isMap
              ? '梳理核心概念与关系，支持展开分支和查看原文出处。'
              : '基于资料生成有出处的解说，支持双人对话与单人讲述。',
          )}
        </p>
        <p className="help">
          {t(
            isMap
              ? '先完整阅读所选资料，再生成可交互的概念层级。'
              : '先阅读资料、编写台词，再逐段合成语音；已完成的部分可继续使用。',
          )}
        </p>
        <fieldset className="deck-options" disabled={busy}>
          <fieldset className="deck-generation-mode">
            <legend>{t('生成方式')}</legend>
            <label>
              <input
                type="radio"
                name="generation-mode"
                checked={mode === 'merged'}
                onChange={() => setMode('merged')}
              />
              {t(isMap ? '合并生成一份思维导图' : '合并生成一期 Podcast')}
            </label>
            <label>
              <input
                type="radio"
                name="generation-mode"
                checked={mode === 'separate'}
                onChange={() => setMode('separate')}
              />
              {t('每份资料 / 章节分别生成')}
            </label>
          </fieldset>
          <label>
            {t('内容范围')}
            <select
              aria-label={t(isMap ? '思维导图内容范围' : 'Podcast 内容范围')}
              value={selection}
              onChange={(e) => {
                setSelection(e.target.value);
                setChapterChoice({ valid: true });
              }}
            >
              {options.map((option) => (
                <option key={option.key} value={option.key}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          {selection === 'selected' && (
            <fieldset className="generation-sources">
              <legend>{t('选择参与生成的资料')}</legend>
              <div className="generation-source-options">
                {sources
                  .filter((source) => source.enabled)
                  .map((source) => (
                    <label key={source.id}>
                      <input
                        type="checkbox"
                        aria-label={t('资料 · {{v1}}', { v1: source.title })}
                        checked={sourceChoices.includes(source.id)}
                        onChange={(event) =>
                          setSourceChoices((ids) =>
                            event.target.checked
                              ? [...ids, source.id]
                              : ids.filter((id) => id !== source.id),
                          )
                        }
                      />
                      <span>
                        {source.title}
                        {!source.parser_version && ` · ${t('等待解析')}`}
                      </span>
                    </label>
                  ))}
              </div>
              <p className="help">
                {t('从笔记本中已勾选的资料选择；单份资料的章节可在内容范围中选择。')}
              </p>
            </fieldset>
          )}
          {chapterSource && ['epub', 'pdf', 'docx'].includes(chapterSource.type) && (
            <ChapterSelection
              key={selection}
              source={chapterSource}
              initialNode={option?.scope.node_id}
              initialNodes={
                initialScope.kind === 'nodes' && chapterSource.id === initialScope.source_id
                  ? initialScope.node_ids
                  : undefined
              }
              mode={mode}
              onChange={(scope, valid) => setChapterChoice({ scope, valid })}
            />
          )}
          <fieldset className="deck-generation-mode">
            <legend>{t(isMap ? '思维导图名称' : 'Podcast 名称')}</legend>
            <label>
              <input
                type="radio"
                name="deck-title-mode"
                checked={!sourceNaming || titleMode === 'auto'}
                onChange={() => setTitleMode('auto')}
              />
              {t('由 AI 拟定名称')}
            </label>
            <label>
              <input
                type="radio"
                name="deck-title-mode"
                checked={sourceNaming && titleMode === 'source'}
                disabled={!sourceNaming}
                onChange={() => setTitleMode('source')}
              />
              {t('使用资料 / 章节名称')}
            </label>
            <p className="help">
              {t(
                isMap
                  ? '每份导图只使用一个来源时可沿用来源名称。'
                  : '每期节目只使用一个来源时可沿用来源名称。',
              )}{' '}
              {t('章节命名格式：资料名称-目录序号-章节名称（子章节如 1.2）。')}
            </p>
          </fieldset>
          {!isMap && (
            <>
              <fieldset className="deck-length">
                <legend>{t('目标时长')}</legend>
                {[5, 10, 20, 30, 60].map((length) => (
                  <label key={length}>
                    <input
                      type="radio"
                      name="slide-count"
                      value={length}
                      checked={count === length}
                      onChange={() => setCount(length)}
                    />
                    {t('约 {{minutes}} 分钟', { minutes: length })}
                  </label>
                ))}
              </fieldset>
              <label>
                {t('节目形式')}
                <select value={format} onChange={(e) => setFormat(e.target.value)}>
                  <option value="dialogue">{t('双人对话')}</option>
                  <option value="solo">{t('单人讲述')}</option>
                </select>
              </label>
              <label className="checkbox-line">
                <input
                  type="checkbox"
                  checked={scriptOnly}
                  onChange={(e) => setScriptOnly(e.target.checked)}
                />
                <span>{t('先生成台词，稍后合成音频')}</span>
              </label>
              <p className="help">
                {t('时长是近似目标，实际长度取决于内容与语速。长节目需要更多生成时间。')}
              </p>
            </>
          )}
          <label>
            {t('语言')}
            <select
              aria-label={t(isMap ? '思维导图语言' : 'Podcast 语言')}
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              {languages.map((item) => (
                <option key={item.code} value={item.code} lang={item.code}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        </fieldset>
        <p className="help deck-generation-summary" role="status">
          {t(
            isMap
              ? '将生成 {{count}} 份思维导图。'
              : '将生成 {{count}} 期节目，每期约 {{minutes}} 分钟。',
            {
              count: episodeCount,
              minutes: count,
            },
          )}
        </p>
        {mode === 'separate' && (
          <p className="help">
            {t(
              isMap
                ? '每份导图独立排队，可分别停止或继续；每批最多 100 份。'
                : '每期节目独立排队，可分别停止或继续；每批最多 100 期。',
            )}
          </p>
        )}
        <ArtifactInstructions
          kind={kind}
          value={instruction}
          onChange={setInstruction}
          disabled={busy}
        />
        {error && (
          <p className="error" role="alert">
            {t(error)}
          </p>
        )}
        <div className="dialog-actions">
          <button type="button" className="button secondary" onClick={onClose} disabled={busy}>
            {t('取消')}
          </button>
          <button className="button primary" disabled={busy || invalid}>
            {busy ? t('正在创建…') : t('开始生成')}
          </button>
        </div>
      </form>
    </Modal>
  );
}
