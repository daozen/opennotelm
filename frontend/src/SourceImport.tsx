import { useRef, useState } from 'react';
import { Globe, LoaderCircle, Plus } from 'lucide-react';
import { api, type Source } from './api';
import Modal from './Modal';
import { errorKey, t, useI18n } from './i18n';

type ImportRow = {
  name: string;
  status: 'waiting' | 'uploading' | 'added' | 'duplicate' | 'failed';
  error?: string;
  file?: File;
};
type Result = { duplicate?: boolean; source?: Source; error_code?: string; index?: number };
const statusLabels = {
  waiting: '等待上传',
  uploading: '正在上传…',
  added: '已加入，后台处理中',
  duplicate: '资料已存在',
  failed: '上传失败',
};

export default function SourceImport({
  notebookId,
  onImported,
}: {
  notebookId: string;
  onImported: () => Promise<void>;
}) {
  useI18n();
  const input = useRef<HTMLInputElement>(null);
  const busyRef = useRef(false);
  const [busy, setBusy] = useState(false);
  const [rows, setRows] = useState<ImportRow[]>([]);
  const [duplicates, setDuplicates] = useState<Source[]>([]);
  const [duplicateBusy, setDuplicateBusy] = useState(false);
  const [duplicateError, setDuplicateError] = useState('');
  const [webOpen, setWebOpen] = useState(false);
  const [urls, setUrls] = useState('');
  const [webError, setWebError] = useState('');
  const [webBusy, setWebBusy] = useState(false);
  const [saveWebImages, setSaveWebImages] = useState(true);
  const [notice, setNotice] = useState('');
  const duplicate = duplicates[0];
  const urlList = [
    ...new Set(
      urls
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean),
    ),
  ];

  function queueDuplicate(source: Source) {
    setDuplicates((current) =>
      current.some((item) => item.id === source.id) ? current : [...current, source],
    );
  }
  function dismissDuplicate() {
    setDuplicates((current) => current.slice(1));
    setDuplicateError('');
  }
  function update(index: number, patch: Partial<ImportRow>) {
    setRows((current) => current.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  }
  async function uploadFile(file: File, index: number, confirmDuplicate = true) {
    update(index, { status: 'uploading', error: undefined });
    const body = new FormData();
    body.append('file', file);
    try {
      const result = await api<Result>(`/notebooks/${notebookId}/sources/upload`, {
        method: 'POST',
        body,
      });
      update(index, { status: result.duplicate ? 'duplicate' : 'added', file: undefined });
      if (confirmDuplicate && result.duplicate && result.source) queueDuplicate(result.source);
      // Refresh never holds an upload worker or the file picker, including sync failures.
      void Promise.resolve()
        .then(onImported)
        .catch(() => {});
      return result.duplicate ? result.source : undefined;
    } catch (e) {
      update(index, { status: 'failed', error: (e as Error).message });
    }
  }
  async function uploadFiles(files: File[]) {
    if (busyRef.current) return;
    if (files.length > 50) {
      setNotice('每次最多添加 50 项资料，请分批上传。');
      return;
    }
    busyRef.current = true;
    setBusy(true);
    setNotice('');
    setRows(files.map((file) => ({ name: file.name, status: 'waiting', file })));
    try {
      const pending = files.entries();
      const duplicates: (Source | undefined)[] = new Array(files.length);
      await Promise.all(
        Array.from({ length: Math.min(3, files.length) }, async () => {
          for (const [index, file] of pending)
            duplicates[index] = await uploadFile(file, index, false);
        }),
      );
      for (const source of duplicates) if (source) queueDuplicate(source);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }
  async function retryFile(file: File, index: number) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      await uploadFile(file, index);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }
  async function importWeb() {
    if (webBusy || busyRef.current || !urlList.length || urlList.length > 50) return;
    busyRef.current = true;
    setWebBusy(true);
    setWebError('');
    setNotice('');
    try {
      const result = await api<{ results: Result[] }>(`/notebooks/${notebookId}/sources/urls`, {
        method: 'POST',
        body: JSON.stringify({ urls: urlList, save_images: saveWebImages }),
      });
      setRows(
        result.results.map((item, index) => ({
          name: urlList[item.index ?? index],
          status: item.error_code ? 'failed' : item.duplicate ? 'duplicate' : 'added',
          error: item.error_code ? errorKey(item.error_code) : undefined,
        })),
      );
      for (const item of result.results) {
        if (item.duplicate && item.source) queueDuplicate(item.source);
      }
      const rejected = result.results.filter((item) => item.error_code);
      setUrls(rejected.map((item) => urlList[item.index!]).join('\n'));
      setWebOpen(false);
      await onImported().catch(() => {});
    } catch (e) {
      setWebError((e as Error).message);
    } finally {
      busyRef.current = false;
      setWebBusy(false);
    }
  }
  return (
    <>
      <input
        ref={input}
        type="file"
        multiple
        disabled={busy || webBusy}
        accept=".epub,.pdf,.docx,.md,.markdown,.txt"
        className="visually-hidden"
        aria-label={t('上传资料')}
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          e.target.value = '';
          if (files.length) void uploadFiles(files);
        }}
      />
      <button
        className="button secondary add-source"
        disabled={busy || webBusy}
        onClick={() => input.current?.click()}
      >
        {busy ? <LoaderCircle className="spin" size={15} /> : <Plus size={16} />}
        {busy ? t('正在上传…') : t('添加资料')}
      </button>
      <p className="source-help">{t('可多选文件')} · EPUB / PDF / Word (.docx) / Markdown / TXT</p>
      <button
        className="button secondary add-source"
        disabled={busy || webBusy}
        onClick={() => {
          setWebError('');
          setWebOpen(true);
        }}
      >
        <Globe size={16} />
        {t('导入网页')}
      </button>
      {notice && (
        <p className="error" role="alert">
          {t(notice)}
        </p>
      )}
      {!!rows.length && (
        <details
          className="import-results"
          open={busy || rows.some((row) => row.status === 'failed')}
        >
          <summary>
            {t('本次添加：{{added}} 成功，{{failed}} 失败，{{duplicate}} 已存在', {
              added: rows.filter((row) => row.status === 'added').length,
              failed: rows.filter((row) => row.status === 'failed').length,
              duplicate: rows.filter((row) => row.status === 'duplicate').length,
            })}
          </summary>
          <ul aria-label={t('资料导入结果')} aria-live="polite">
            {rows.map((row, index) => (
              <li key={`${index}:${row.name}`}>
                <strong dir="auto">{row.name}</strong>
                <span className={row.status === 'failed' ? 'error' : 'muted'}>
                  {t(row.error ?? statusLabels[row.status])}
                </span>
                {row.status === 'failed' && row.file && (
                  <button
                    className="button ghost"
                    disabled={busy || webBusy}
                    onClick={() => void retryFile(row.file!, index)}
                  >
                    {t('重试上传')}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}
      {webOpen && (
        <Modal onClose={() => setWebOpen(false)} busy={webBusy}>
          <section
            className="small-dialog web-import-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="web-import-title"
          >
            <h2 id="web-import-title">{t('导入网页')}</h2>
            <p id="web-import-help">
              {t('每行填写一个网址，最多 50 个。将保存网页正文快照，可用于阅读、问答和生成 Deck。')}
            </p>
            <label>
              {t('网页地址')}
              <textarea
                data-modal-focus
                aria-describedby="web-import-help"
                rows={7}
                placeholder="https://example.com/article"
                value={urls}
                onChange={(e) => setUrls(e.target.value)}
                disabled={webBusy}
              />
            </label>
            <p className="muted">
              {t(
                '支持公开的 HTTP / HTTPS 页面。需要登录、仅有视频或依赖脚本加载正文的页面可能无法导入。',
              )}
            </p>
            <label className="web-image-option">
              <input
                type="checkbox"
                checked={saveWebImages}
                disabled={webBusy}
                onChange={(event) => setSaveWebImages(event.target.checked)}
              />
              {t('保存正文图片')}
            </label>
            <p className="help">
              {t(
                '正文先导入，图片随后下载并识别，供阅读、问答和 Deck 使用。图片识别会调用已配置的语言模型，可能产生费用；取消勾选时仅保留文字说明。',
              )}
            </p>
            <p className="help">
              {t('已有网页会复用保存的正文；勾选此项可补充图片，不重新抓取正文。')}
            </p>
            {urlList.length > 50 && (
              <p className="error" role="alert">
                {t('每次最多添加 50 项资料，请分批上传。')}
              </p>
            )}
            {webError && (
              <p className="error" role="alert">
                {t(webError)}
              </p>
            )}
            <div className="dialog-actions">
              <button
                className="button secondary"
                disabled={webBusy}
                onClick={() => setWebOpen(false)}
              >
                {t('取消')}
              </button>
              <button
                className="button primary"
                disabled={webBusy || !urlList.length || urlList.length > 50}
                onClick={() => void importWeb()}
              >
                {webBusy ? t('正在提交…') : t('导入 {{count}} 个网页', { count: urlList.length })}
              </button>
            </div>
          </section>
        </Modal>
      )}
      {duplicate && (
        <Modal onClose={dismissDuplicate} busy={duplicateBusy}>
          <section
            className="small-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="duplicate-title"
          >
            <h2 id="duplicate-title">{t('资料已存在')}</h2>
            <p>
              {t('「{{v1}}」已在本地资料库中。可直接添加到当前笔记本，无需重复解析。', {
                v1: duplicate.title,
              })}
            </p>
            {duplicates.length > 1 && (
              <p>{t('还有 {{count}} 项重复资料待确认', { count: duplicates.length - 1 })}</p>
            )}
            {duplicateError && (
              <p className="error" role="alert">
                {t(duplicateError)}
              </p>
            )}
            <div className="dialog-actions">
              <button
                className="button secondary"
                disabled={duplicateBusy}
                onClick={dismissDuplicate}
              >
                {t('取消')}
              </button>
              <button
                className="button primary"
                disabled={duplicateBusy}
                onClick={async () => {
                  if (duplicateBusy) return;
                  setDuplicateBusy(true);
                  setDuplicateError('');
                  try {
                    await api(`/notebooks/${notebookId}/sources/${duplicate.id}`, {
                      method: 'POST',
                    });
                    dismissDuplicate();
                    await onImported().catch(() => {});
                  } catch (e) {
                    setDuplicateError((e as Error).message);
                  } finally {
                    setDuplicateBusy(false);
                  }
                }}
              >
                {t('添加已有资料')}
              </button>
            </div>
          </section>
        </Modal>
      )}
    </>
  );
}
