import { t, useI18n } from './i18n';
import { useEffect, useState } from 'react';
import { Download } from 'lucide-react';
import { api } from './api';

type TelemetryStatus = { enabled: boolean; configured: boolean; queued_events: number };

export default function PrivacySettings() {
  useI18n();
  const [status, setStatus] = useState<TelemetryStatus>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  useEffect(() => {
    let active = true;
    api<TelemetryStatus>('/settings/telemetry')
      .then((value) => {
        if (active) setStatus(value);
      })
      .catch((e: Error) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  async function change(enabled: boolean) {
    const previous = status;
    if (status) setStatus({ ...status, enabled });
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const preferences = await api<{ telemetry_enabled: boolean }>('/settings/preferences', {
        method: 'PUT',
        body: JSON.stringify({ telemetry_enabled: enabled }),
      });
      if (previous) {
        setStatus({
          ...previous,
          enabled: preferences.telemetry_enabled,
          queued_events: preferences.telemetry_enabled ? previous.queued_events : 0,
        });
      }
      setMessage('统计偏好已保存。');
    } catch (e) {
      setStatus(previous);
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="privacy-settings" aria-label={t('隐私与诊断')}>
      <h3>{t('隐私与诊断')}</h3>
      <label className="checkbox-line">
        <input
          type="checkbox"
          checked={status?.enabled ?? false}
          disabled={busy || !status}
          onChange={(e) => void change(e.target.checked)}
        />
        {t('允许匿名使用统计')}
      </label>
      <p className="help">
        {t(
          '默认关闭。仅统计功能使用、资料格式、耗时区间和错误码，不发送资料内容、文件名、对话、提示词、模型地址或密钥。关闭后会清空尚未发送的统计。',
        )}
      </p>
      {status && !status.configured && (
        <p className="help">
          {t(
            '本实例尚未配置统计接收服务，仍可保存选择。勾选后仅在本地暂存匿名统计，配置接收服务后才会发送。',
          )}
        </p>
      )}
      {message && (
        <p className="help" role="status">
          {t(message)}
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {t(error)}
        </p>
      )}
      <a
        className="button secondary"
        href="/api/diagnostics"
        download="opennotelm-diagnostics.json"
      >
        <Download size={15} /> {t('下载诊断报告')}
      </a>
      <p className="help">
        {t(
          '报告包含应用与解析器版本、模型 ID、任务状态、错误码和检索分数摘要，不包含你的资料正文或密钥。可下载后自行检查与分享。',
        )}
      </p>
    </section>
  );
}
