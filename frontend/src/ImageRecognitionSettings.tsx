import ModelConcurrencySettings from './ModelConcurrencySettings';

export default function ImageRecognitionSettings() {
  return (
    <ModelConcurrencySettings
      endpoint="/settings/models/image-recognition"
      sectionLabel="图片识别设置"
      label="图片识别并发数"
      help="同时识别的资料图片数量，1 为串行，最多 20。保存后对新任务生效，正在识别的任务保持原设置。"
      saveLabel="保存识别并发设置"
      defaultValue={4}
    />
  );
}
