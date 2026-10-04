import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Download } from 'lucide-react';
import { api } from './api';
import { t, useI18n } from './i18n';

export type DownloadableArtifact = {
  id: string;
  kind: 'deck';
  title: string;
  download_available?: boolean;
};

export default function ArtifactBatchDownload<T extends DownloadableArtifact>({
  notebookId,
  items,
  renderItem,
}: {
  notebookId: string;
  items: T[];
  renderItem: (item: T, selection: ReactNode) => ReactNode;
}) {
  useI18n();
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [download, setDownload] = useState<{ download_url: string; filename: string }>();
  const pending = useRef<AbortController | null>(null);
  const available = items.filter((item) => item.download_available);
  const keys = available.map((item) => `${item.kind}:${item.id}`);
  const effective = selected.filter((key) => keys.includes(key));
  const all = keys.length > 0 && effective.length === keys.length;
  const availability = keys.join('|');
  useEffect(() => {
    setSelected((current) => current.filter((key) => availability.split('|').includes(key)));
    setDownload(undefined);
  }, [availability]);
  useEffect(() => () => pending.current?.abort(), []);
  const toggle = (key: string) => {
    setDownload(undefined);
    setSelected((current) =>
      current.includes(key) ? current.filter((id) => id !== key) : [...current, key],
    );
  };
  return (
    <>
      {items.length > 0 && (
        <div className="artifact-download-controls">
          {!selecting ? (
            <button
              className="button secondary"
              onClick={() => {
                setSelecting(true);
                setError('');
              }}
            >
              <Download size={15} /> {t('批量下载')}
            </button>
          ) : (
            <>
              <label className="checkbox-line">
                <input
                  type="checkbox"
                  checked={all}
                  disabled={busy || !keys.length}
                  ref={(element) => {
                    if (element) element.indeterminate = effective.length > 0 && !all;
                  }}
                  onChange={() => {
                    setSelected(all ? [] : keys);
                    setDownload(undefined);
                  }}
                />
                {t('选择全部可下载文件')}
              </label>
              <p className="help">
                {t('已有当前版本 PDF 的 Deck 可以下载；生成中或尚未导出的 Deck 暂不可选。')}
              </p>
              <p className="help">{t('每次最多下载 100 份、总大小 512 MB，请按需分批选择。')}</p>
              <div className="artifact-download-actions">
                <button
                  className="button primary"
                  disabled={busy || !effective.length || effective.length > 100}
                  onClick={async () => {
                    if (pending.current) return;
                    const controller = new AbortController();
                    pending.current = controller;
                    setBusy(true);
                    setError('');
                    setDownload(undefined);
                    try {
                      const result = await api<{ download_url: string; filename: string }>(
                        `/notebooks/${notebookId}/artifacts/download`,
                        {
                          method: 'POST',
                          signal: controller.signal,
                          body: JSON.stringify({
                            items: items
                              .filter((item) => effective.includes(`${item.kind}:${item.id}`))
                              .map((item) => ({ kind: item.kind, id: item.id })),
                          }),
                        },
                      );
                      if (controller.signal.aborted) return;
                      setDownload(result);
                      const link = document.createElement('a');
                      link.href = result.download_url;
                      link.download = result.filename;
                      document.body.append(link);
                      link.click();
                      link.remove();
                    } catch (e) {
                      if (!controller.signal.aborted) setError((e as Error).message);
                    } finally {
                      pending.current = null;
                      if (!controller.signal.aborted) setBusy(false);
                    }
                  }}
                >
                  <Download size={15} />{' '}
                  {busy ? t('正在打包…') : t('下载所选（{{count}}）', { count: effective.length })}
                </button>
                <button
                  className="button ghost"
                  disabled={busy}
                  onClick={() => {
                    setSelecting(false);
                    setSelected([]);
                    setError('');
                    setDownload(undefined);
                  }}
                >
                  {t('取消选择')}
                </button>
              </div>
              {download && (
                <p className="help" role="status">
                  {t('文件已打包。若下载未开始，可点击此处：')}{' '}
                  <a href={download.download_url} download={download.filename}>
                    {t('下载 ZIP')}
                  </a>
                </p>
              )}
              {error && (
                <p className="error" role="alert">
                  {t(error)}
                </p>
              )}
            </>
          )}
        </div>
      )}
      {items.map((item) =>
        renderItem(
          item,
          selecting ? (
            <label className="artifact-selection">
              <input
                type="checkbox"
                checked={effective.includes(`${item.kind}:${item.id}`)}
                disabled={busy || !item.download_available}
                aria-label={t('选择下载 · {{title}}', { title: item.title })}
                onChange={() => toggle(`${item.kind}:${item.id}`)}
              />
              {!item.download_available && <span>{t('暂无可下载文件')}</span>}
            </label>
          ) : null,
        ),
      )}
    </>
  );
}
