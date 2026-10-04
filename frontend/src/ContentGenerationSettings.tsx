import ModelConcurrencySettings from './ModelConcurrencySettings';

export default function ContentGenerationSettings() {
  return (
    <ModelConcurrencySettings
      endpoint="/settings/models/content-generation"
      sectionLabel="Deck 内容生成设置"
      label="Deck 内容生成并发数"
      help="同时解读的资料分段或创作的页面数量，1 为串行，最多 20。默认 2，保存后对新任务生效。"
      saveLabel="保存内容并发设置"
      defaultValue={2}
    />
  );
}
