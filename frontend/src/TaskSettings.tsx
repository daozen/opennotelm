import ModelConcurrencySettings from './ModelConcurrencySettings';

export default function TaskSettings() {
  return (
    <>
      <ModelConcurrencySettings
        endpoint="/settings/models/task-concurrency"
        sectionLabel="任务处理设置"
        label="同时处理任务数"
        help="资料解析和 Deck 等任务共享此额度。默认 3，最多 8；同一资料或 Deck 的修改仍按顺序处理。降低额度不会中断正在处理的任务。"
        saveLabel="保存任务设置"
        defaultValue={3}
      />
      <ModelConcurrencySettings
        endpoint="/settings/models/request-concurrency"
        sectionLabel="模型服务请求设置"
        label="每个模型服务的总请求并发数"
        help="同一服务地址的识图、内容、生图和索引请求共享此上限，避免多个任务叠加。默认 8，最多 20；保存后用于后续请求，已发出的请求继续完成。"
        saveLabel="保存请求设置"
        defaultValue={8}
      />
    </>
  );
}
