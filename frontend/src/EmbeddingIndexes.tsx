import { useEffect, useState } from 'react';
import { LoaderCircle, RefreshCw } from 'lucide-react';
import { api } from './api';
import { t, useI18n } from './i18n';

type IndexStatus = {
  configured: boolean;
  total: number;
  counts: Record<'ready' | 'queued' | 'running' | 'failed' | 'pending', number>;
  sources: {
    source_id: string;
    title: string;
    state: 'ready' | 'queued' | 'running' | 'failed' | 'pending';
    progress: number;
    error_code?: string;
  }[];
};
const endpoint = '/settings/models/embedding/indexes';
const states = {
  ready: '可用于问答',
  queued: '等待重建',
  running: '正在重建',
  failed: '重建失败',
  pending: '需要重建',
};

export default function EmbeddingIndexes({ refreshKey }: { refreshKey: number }) {
  useI18n();
  const [status, setStatus] = useState<IndexStatus>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const data = await api<IndexStatus>(endpoint);
        if (disposed) return;
        setStatus(data);
        setError('');
      } catch (e) {
        if (!disposed) setError((e as Error).message);
      } finally {
        if (!disposed) timer = setTimeout(() => void refresh(), 2000);
      }
    }
    void refresh();
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [refreshKey]);

  async function rebuild(mode: 'missing' | 'failed' | 'all') {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const data = await api<IndexStatus>(`${endpoint}/rebuild`, {
        method: 'POST',
        body: JSON.stringify({ mode }),
      });
      setStatus(data);
      setMessage('索引重建已加入后台队列，关闭设置后仍会继续。');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const active = (status?.counts.queued ?? 0) + (status?.counts.running ?? 0);
  return (
    <section className="embedding-indexes" aria-label={t('资料检索索引')}>
      <h4>{t('资料检索索引')}</h4>
      <p className="help">
        {t(
          '更换模型并保存后，自动重建已解析资料的检索索引。原始资料、引用、知识页和演示文稿保持不变。',
        )}
      </p>
      <p className="help">
        {t('重建会把已解析文字发送给 Embedding 服务，可能产生费用；无需重新解析或识别图片。')}
      </p>
      {status?.configured && (
        <>
          <p role="status">
            {t('可用于问答 {{v1}} / {{v2}} · 排队 {{v3}} · 重建中 {{v4}} · 失败 {{v5}}', {
              v1: status.counts.ready,
              v2: status.total,
              v3: status.counts.queued,
              v4: status.counts.running,
              v5: status.counts.failed,
            })}
          </p>
          {status.total === 0 && <p className="help">{t('暂无需要建立索引的已解析资料。')}</p>}
          {status.total > 0 && (
            <>
              <div className="index-actions">
                <button
                  type="button"
                  className="button secondary"
                  disabled={busy || !(status.counts.pending + status.counts.failed)}
                  onClick={() => void rebuild('missing')}
                >
                  {busy ? <LoaderCircle className="spin" size={14} /> : <RefreshCw size={14} />}
                  {t('重建待处理索引')}
                </button>
                {!!status.counts.failed && (
                  <button
                    type="button"
                    className="button secondary"
                    disabled={busy}
                    onClick={() => void rebuild('failed')}
                  >
                    {t('重试失败项')}
                  </button>
                )}
              </div>
              <details>
                <summary>{t('查看各资料进度与更多操作')}</summary>
                <ul className="index-source-list">
                  {status.sources.map((source) => (
                    <li key={source.source_id}>
                      <strong>{source.title}</strong>
                      <span>
                        {t(states[source.state])}
                        {source.state === 'running' && ` · ${Math.round(source.progress * 100)}%`}
                      </span>
                      {source.error_code && (
                        <p className="error">{t(`errors.${source.error_code}`)}</p>
                      )}
                    </li>
                  ))}
                </ul>
                <p className="help">
                  {t(
                    '若服务在相同模型名称下更换了实际模型，可重新计算全部索引。此操作也会重建当前可用的索引。',
                  )}
                </p>
                <button
                  type="button"
                  className="button secondary"
                  disabled={busy || active > 0}
                  onClick={() => void rebuild('all')}
                >
                  {t('重新计算全部索引')}
                </button>
              </details>
            </>
          )}
        </>
      )}
      {error && (
        <p className="error" role="alert">
          {t(error)}
        </p>
      )}
      {message && (
        <p className="help" role="status">
          {t(message)}
        </p>
      )}
    </section>
  );
}
