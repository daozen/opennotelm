import Modal from './Modal';
import { t, useI18n } from './i18n';
import { useState } from 'react';
import { X } from 'lucide-react';
import { api, type Slide } from './api';
import { useGuardedNavigation, useUnsavedChanges } from './NavigationGuard';

const names: Record<string, string> = {
  headline: '标题',
  subheadline: '副标题',
  body: '正文',
  statement: '观点',
  quote: '引文',
  number: '数字',
  label: '标签',
  comparison: '对照',
  bullet_list: '要点',
  caption: '图注',
  source_note: '来源说明',
};

export function textFields(slide: Slide) {
  const result: { ref: string; label: string; item?: number; text: string; limit: number }[] = [];
  for (const element of slide.spec?.content_elements ?? []) {
    if (element.text.trim())
      result.push({
        ref: element.id,
        label: names[element.type] ?? '文字',
        text: element.text,
        limit: 2500,
      });
    if (element.label.trim())
      result.push({ ref: `${element.id}.label`, label: '标签', text: element.label, limit: 300 });
    element.items.forEach((item, index) => {
      if (item.label)
        result.push({
          ref: `${element.id}.item${index}.label`,
          label: '第 {{v1}} 项标签',
          item: index + 1,
          text: item.label,
          limit: 200,
        });
      result.push({
        ref: `${element.id}.item${index}.text`,
        label: '第 {{v1}} 项内容',
        item: index + 1,
        text: item.text,
        limit: 1200,
      });
    });
  }
  return result;
}

export default function SlideEditor({
  deckId,
  slide,
  mode,
  generatedPage = false,
  onClose,
  onSaved,
}: {
  deckId: string;
  slide: Slide;
  mode: 'text' | 'revise';
  generatedPage?: boolean;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  useI18n();
  const navigate = useGuardedNavigation();
  const dismiss = () => navigate(onClose);
  const [fields, setFields] = useState(() => textFields(slide));
  const [instruction, setInstruction] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const original = textFields(slide);
  const changes = fields
    .filter((field, index) => field.text !== original[index].text)
    .map(({ ref, text }) => ({ ref, text }));
  useUnsavedChanges(busy || changes.length > 0 || !!instruction.trim());
  return (
    <Modal onClose={dismiss} busy={busy}>
      <form
        className="small-dialog slide-editor"
        role="dialog"
        aria-modal="true"
        aria-labelledby="slide-edit-title"
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setError('');
          try {
            await api(
              `/decks/${deckId}/slides/${slide.id}/${mode === 'text' ? 'text' : 'revise'}`,
              {
                method: mode === 'text' ? 'PATCH' : 'POST',
                body: JSON.stringify(
                  mode === 'text'
                    ? { revision: slide.revision, changes }
                    : { revision: slide.revision, action: 'revise', instruction },
                ),
              },
            );
            await onSaved();
            onClose();
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="dialog-top">
          <h2 id="slide-edit-title">{mode === 'text' ? t('编辑本页文字') : t('用 AI 修改本页')}</h2>
          <button
            type="button"
            className="icon-button"
            aria-label={t('关闭页面编辑')}
            disabled={busy}
            onClick={dismiss}
          >
            <X size={19} />
          </button>
        </div>
        <p className="help">
          {mode === 'text'
            ? t(
                generatedPage
                  ? '保存后会重新生成包含新文字的完整页面，并更新 PDF。'
                  : '保存后会更新本页预览与 PDF。',
              )
            : t('描述你希望改变的内容或视觉表达。AI 会保留整套 Deck 的风格。')}
        </p>
        {mode === 'text' ? (
          <div className="slide-edit-fields">
            {fields.map((field, index) => (
              <label key={field.ref}>
                {t(field.label, { v1: field.item })}
                <textarea
                  aria-label={`${t(field.label, { v1: field.item })} ${index + 1}`}
                  value={field.text}
                  maxLength={field.limit}
                  rows={field.label === '标题' ? 2 : 3}
                  onChange={(event) =>
                    setFields(
                      fields.map((item, i) =>
                        i === index ? { ...item, text: event.target.value } : item,
                      ),
                    )
                  }
                />
              </label>
            ))}
          </div>
        ) : (
          <label>
            {t('修改要求')}
            <textarea
              aria-label={t('本页修改要求')}
              value={instruction}
              maxLength={4000}
              rows={5}
              required
              placeholder={t('例如：这一页文字太密，减少内容，用更直观的方式解释。')}
              onChange={(e) => setInstruction(e.target.value)}
            />
          </label>
        )}
        {error && (
          <p className="error" role="alert">
            {t(error)}
          </p>
        )}
        <div className="dialog-actions">
          <button type="button" className="button secondary" disabled={busy} onClick={dismiss}>
            {t('取消')}
          </button>
          <button
            className="button primary"
            disabled={busy || (mode === 'text' ? !changes.length : !instruction.trim())}
          >
            {busy ? t('正在提交…') : mode === 'text' ? t('保存并更新本页') : t('开始修改本页')}
          </button>
        </div>
      </form>
    </Modal>
  );
}
