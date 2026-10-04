import ModelConcurrencySettings from './ModelConcurrencySettings';

export default function ImageGenerationSettings() {
  return (
    <ModelConcurrencySettings
      endpoint="/settings/models/image-generation"
      sectionLabel="图片生成设置"
      label="图片生成并发数"
      help="同时生成的图片数量，1 为串行，最多 20。保存后对新任务生效，正在生成的任务保持原设置。"
      saveLabel="保存并发设置"
      defaultValue={2}
    />
  );
}
