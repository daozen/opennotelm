import Modal from './Modal';
import ModelConcurrencySettings from './ModelConcurrencySettings';
import { t, useI18n } from './i18n';
import { useState } from 'react';
import { Check, ChevronRight, LoaderCircle, Settings2, X } from 'lucide-react';
import { api, type ModelConfig, type ModelRole, type ModelSettings } from './api';
import PrivacySettings from './PrivacySettings';
import LanguageSettings from './LanguageSettings';
import ImageGenerationSettings from './ImageGenerationSettings';
import ImageRecognitionSettings from './ImageRecognitionSettings';
import ContentGenerationSettings from './ContentGenerationSettings';
import TaskSettings from './TaskSettings';
import EmbeddingIndexes from './EmbeddingIndexes';

const labels: Record<ModelRole, [string, string]> = {
  language: ['语言模型', '用于问答、知识整理和幻灯片规划'],
  embedding: ['Embedding 模型', '用于建立索引和检索原始资料'],
  image: ['图片模型', '用于生成帮助理解内容的视觉素材'],
  speech: ['语音模型（可选）', '用于 Podcast 语音合成；不影响其他功能'],
};
const roles: ModelRole[] = ['language', 'embedding', 'image', 'speech'];

function ModelForm({
  role,
  saved,
  language,
  onSaved,
}: {
  role: ModelRole;
  saved?: ModelConfig;
  language?: ModelConfig;
  onSaved: (data: ModelSettings) => void;
}) {
  useI18n();
  const [url, setUrl] = useState(saved?.base_url ?? 'https://api.openai.com/v1');
  const [key, setKey] = useState('');
  const [model, setModel] = useState(saved?.model_id ?? '');
  const [context, setContext] = useState(saved?.max_context_tokens ?? 16000);
  const [protocol, setProtocol] = useState(String(saved?.capabilities.speech_protocol ?? 'openai'));
  const [voiceA, setVoiceA] = useState(String(saved?.capabilities.voice_a ?? 'alloy'));
  const [voiceB, setVoiceB] = useState(String(saved?.capabilities.voice_b ?? 'nova'));
  const [busy, setBusy] = useState('');
  const [message, setMessage] = useState('');
  const [modelCount, setModelCount] = useState(0);
  const [options, setOptions] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [sameEndpoint, setSameEndpoint] = useState(false);
  const [indexRefresh, setIndexRefresh] = useState(0);
  const payload = () => ({
    role,
    base_url: sameEndpoint && language ? language.base_url : url,
    api_key: key,
    use_saved_key: !key && !!saved && !sameEndpoint,
    api_key_source: sameEndpoint && !key ? 'language' : null,
    model_id: model || 'discovery',
    max_context_tokens: context,
    ...(role === 'speech' ? { speech_protocol: protocol, voice_a: voiceA, voice_b: voiceB } : {}),
  });
  async function discover() {
    setBusy('discover');
    setError('');
    setMessage('');
    try {
      const data = await api<{ models: string[]; message?: string }>('/settings/models/discover', {
        method: 'POST',
        body: JSON.stringify(payload()),
      });
      setOptions(data.models);
      setModelCount(data.models.length);
      setMessage(
        data.message
          ? '模型服务未提供模型列表，可手动输入 ID。'
          : '发现 {{v1}} 个模型，仍可手动输入 ID。',
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy('');
    }
  }
  async function test(event: React.FormEvent) {
    event.preventDefault();
    setBusy('test');
    setError('');
    setMessage('');
    try {
      const data = await api<ModelSettings>('/settings/models/test', {
        method: 'POST',
        body: JSON.stringify(payload()),
      });
      setKey('');
      onSaved(data);
      if (role === 'embedding') setIndexRefresh((value) => value + 1);
      setMessage('能力测试通过，配置已安全保存。');
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy('');
    }
  }
  return (
    <form className="model-form" onSubmit={test}>
      <div className="model-heading">
        <span className="step-number">{roles.indexOf(role) + 1}</span>
        <div>
          <h3>{t(labels[role][0])}</h3>
          <p>{t(labels[role][1])}</p>
        </div>
        {saved && (
          <span className="badge">
            <Check size={14} /> {t('已验证')}
          </span>
        )}
      </div>
      {role === 'embedding' && language && (
        <label className="checkbox-line">
          <input
            type="checkbox"
            checked={sameEndpoint}
            onChange={(e) => {
              setSameEndpoint(e.target.checked);
              setKey('');
            }}
          />{' '}
          {t('使用语言模型的 Endpoint 与 API Key')}
        </label>
      )}
      <label>
        {t('服务地址')}
        <input
          type="url"
          required
          value={sameEndpoint && language ? language.base_url : url}
          disabled={sameEndpoint}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://…/v1"
        />
      </label>
      <label>
        {t('访问密钥')}
        <input
          type="password"
          autoComplete="off"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          placeholder={
            saved && !sameEndpoint
              ? t('留空以使用已保存的 Key')
              : t('本地无鉴权服务或环境变量配置可留空')
          }
        />
      </label>
      <div className="model-picker">
        <label>
          {t('模型 ID')}
          <input
            required
            value={model}
            onChange={(e) => setModel(e.target.value)}
            list={`${role}-models`}
            placeholder={t('输入模型 ID')}
          />
        </label>
        <button type="button" className="button secondary" onClick={discover} disabled={!!busy}>
          {t('发现模型')}
        </button>
      </div>
      <datalist id={`${role}-models`}>
        {options.map((id) => (
          <option key={id} value={id} />
        ))}
      </datalist>
      {role === 'language' && (
        <label>
          {t('上下文预算（tokens）')}
          <input
            type="number"
            min={2048}
            max={2000000}
            required
            value={context}
            onChange={(e) => setContext(Number(e.target.value))}
          />
        </label>
      )}
      {role === 'speech' && (
        <>
          <label>
            {t('语音接口类型')}
            <select value={protocol} onChange={(e) => setProtocol(e.target.value)}>
              <option value="openai">OpenAI-compatible Speech</option>
              <option value="gemini">Gemini Native Speech (Interactions)</option>
            </select>
          </label>
          <label>
            {t('声音 A')}
            <input
              required
              maxLength={100}
              value={voiceA}
              onChange={(e) => setVoiceA(e.target.value)}
              placeholder="Ryan / alloy"
            />
          </label>
          <label>
            {t('声音 B')}
            <input
              required
              maxLength={100}
              value={voiceB}
              onChange={(e) => setVoiceB(e.target.value)}
              placeholder="Vivian / nova"
            />
          </label>
          <p className="help">
            {t('填写服务支持的声音 ID。兼容接口按角色分段合成，原生接口可在一段中合成对话。')}
          </p>
          <p className="help">
            {t(
              '语音语言取决于服务能力。Qwen3-TTS 不支持阿拉伯语和印地语；可改用支持这些语言的服务。',
            )}
          </p>
          <ModelConcurrencySettings
            endpoint="/settings/models/speech-generation"
            sectionLabel="语音并发设置"
            label="同时合成的音频段数"
            help="本地单个语音模型建议设为 1；提高并发前请确认服务容量。新节目使用保存的设置。"
            saveLabel="保存语音并发设置"
            defaultValue={2}
          />
        </>
      )}
      {role === 'image' && <ImageGenerationSettings />}
      {role === 'language' && (
        <>
          <ImageRecognitionSettings />
          <ContentGenerationSettings />
        </>
      )}
      {role === 'language' && saved && (
        <div className="vision-model-test">
          <button
            type="button"
            className="button secondary"
            disabled={
              !!busy ||
              url !== saved.base_url ||
              model !== saved.model_id ||
              context !== saved.max_context_tokens ||
              !!key
            }
            onClick={async () => {
              setBusy('vision');
              setError('');
              setMessage('');
              try {
                const result = await api<ModelSettings>('/settings/models/vision-test', {
                  method: 'POST',
                });
                onSaved(result);
                setMessage('图片识别能力测试通过。');
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy('');
              }
            }}
          >
            {t(saved.capabilities.vision_input ? '重新测试图片识别' : '测试图片识别')}
          </button>
          <p className="help">{t('测试已保存的语言模型能否读取图片，用于文档插图和扫描 PDF。')}</p>
        </div>
      )}
      {role === 'image' && (
        <p className="help">{t('测试会生成一张小图片，可能产生模型服务费用。')}</p>
      )}
      {error && (
        <p className="error" role="alert">
          {t(error)}
        </p>
      )}
      {message && (
        <p className="help" role="status">
          {t(message, { v1: modelCount })}
        </p>
      )}
      <button className="button primary" disabled={!!busy || !model.trim()}>
        {busy && <LoaderCircle className="spin" size={16} />}{' '}
        {busy === 'test' ? t('正在测试能力…') : t('测试并保存')}
      </button>
      {role === 'embedding' && <EmbeddingIndexes refreshKey={indexRefresh} />}
    </form>
  );
}

export default function Setup({
  settings,
  onSaved,
  onClose,
}: {
  settings: ModelSettings;
  onSaved: (data: ModelSettings) => void;
  onClose: () => void;
}) {
  useI18n();
  return (
    <Modal onClose={onClose}>
      <section
        className="setup-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="setup-title"
      >
        <div className="dialog-top">
          <span className="eyebrow">
            <Settings2 size={15} /> {t('YOUR MODELS, YOUR WORKSPACE')}
          </span>
          <button className="icon-button" onClick={onClose} aria-label={t('关闭设置')}>
            <X size={20} />
          </button>
        </div>
        <LanguageSettings />
        <h2 id="setup-title">{t('连接你的 AI 模型')}</h2>
        <p className="dialog-description">
          {t('资料留在本地。问答和生成时，所选资料会发送到你配置的模型服务。')}
        </p>
        <div className="setup-models">
          {roles.map((role) => (
            <ModelForm
              key={role}
              role={role}
              saved={settings.models[role]}
              language={settings.models.language}
              onSaved={onSaved}
            />
          ))}
        </div>
        <TaskSettings />
        <PrivacySettings />
        <footer>
          <span>{t('API Key 加密保存，不会保存在浏览器中。')}</span>
          <button className="button primary" onClick={onClose} disabled={!settings.setup_complete}>
            {t('开始使用')}
            <ChevronRight size={16} />
          </button>
        </footer>
      </section>
    </Modal>
  );
}
