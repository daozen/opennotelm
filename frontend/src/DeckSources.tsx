import { useState } from 'react';
import { api, type DeckSources as Sources } from './api';
import { t, useI18n } from './i18n';

export default function DeckSources({
  id,
  kind = 'deck',
  onOpenSource,
  onOpenKnowledge,
}: {
  id: string;
  kind?: 'deck' | 'podcast' | 'mindmap';
  onOpenSource: (sourceId: string, blockId: string) => Promise<void>;
  onOpenKnowledge?: (pageId: string) => void;
}) {
  useI18n();
  const [sources, setSources] = useState<Sources>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const openSource = async (sourceId: string, blockId: string) => {
    setError('');
    try {
      await onOpenSource(sourceId, blockId);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const load = async () => {
    setLoading(true);
    setError('');
    try {
      setSources(
        await api<Sources>(
          `/${kind === 'podcast' ? 'podcasts' : kind === 'mindmap' ? 'mindmaps' : 'decks'}/${id}/sources`,
        ),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };
  return (
    <details
      className="deck-sources"
      onToggle={(event) => {
        if (event.currentTarget.open && !loading) void load();
      }}
    >
      <summary>
        {t(
          kind === 'podcast'
            ? '查看节目来源'
            : kind === 'mindmap'
              ? '查看导图来源'
              : '查看 Deck 来源',
        )}
      </summary>
      {loading && <p role="status">{t('加载中…')}</p>}
      {error && (
        <p className="error" role="alert">
          {t(error)}{' '}
          <button className="button ghost" onClick={() => void load()}>
            {t('重试')}
          </button>
        </p>
      )}
      {sources && (
        <div className="deck-sources-content">
          <p className="help">{t('以下名称记录了生成时选用的资料与知识页。')}</p>
          {sources.historical && (
            <p className="help">{t('旧 Deck 的来源名称根据仍保留的资料还原。')}</p>
          )}
          {sources.knowledge.map((item) => (
            <div key={item.id} className="deck-source-entry">
              <button
                className="button ghost"
                disabled={!item.available || !onOpenKnowledge}
                onClick={() => onOpenKnowledge?.(item.id)}
              >
                {t('知识 · {{v1}}', { v1: item.title })}
              </button>
              <span className="help">
                {t('生成时为第 {{revision}} 版', { revision: item.revision })}
              </span>
              {!item.available && <span className="help">{t('来源已不可用')}</span>}
            </div>
          ))}
          {sources.sources.map((source) => (
            <div key={source.id} className="deck-source-entry">
              <div className="deck-source-title">
                <button
                  className="button ghost"
                  disabled={!source.available || !source.first_block_id}
                  onClick={() => void openSource(source.id, source.first_block_id!)}
                >
                  {source.title ?? t('来源已不可用')}
                </button>
                <span className="help">
                  {source.selection === 'whole'
                    ? t('整份资料')
                    : source.selection === 'chapters'
                      ? t('选定章节')
                      : t('知识页引用的原始资料')}
                </span>
                {!source.available && <span className="help">{t('来源已不可用')}</span>}
              </div>
              {source.whole_work_background && (
                <p className="help">{t('同时结合了整份资料的背景。')}</p>
              )}
              {!!source.chapters.length && (
                <ul>
                  {source.chapters.map((chapter) => (
                    <li key={chapter.id}>
                      <button
                        className="button ghost"
                        disabled={!chapter.available || !chapter.first_block_id}
                        onClick={() => void openSource(source.id, chapter.first_block_id!)}
                      >
                        {chapter.path.join(' › ')}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </details>
  );
}
