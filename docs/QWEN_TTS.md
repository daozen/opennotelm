# Local Qwen3-TTS / 本地 Qwen3-TTS

Qwen3-TTS's official package exposes Python inference and a demo, not an
OpenAI-compatible Speech HTTP server. OpenNoteLM includes a small optional adapter
for its **0.6B CustomVoice** model. It implements `GET /v1/models`,
`GET /v1/voices` and `POST /v1/audio/speech`, returning WAV audio. This is our
adapter, not an upstream claim of OpenAI API support.

官方包提供 Python 推理和演示应用，没有自带 OpenAI-compatible Speech HTTP 服务。
本项目的可选适配服务将 **0.6B CustomVoice** 接到兼容接口，返回 WAV 音频。
不支持任意 OpenAI 参数、实时流式语音、声音克隆或所有 Qwen 模型变体。

Sources / 来源：[official code](https://github.com/QwenLM/Qwen3-TTS)、
[model card](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice)。
The model revision is pinned in the installer. The model card declares Apache-2.0;
weights and inference dependencies retain their own terms and are not bundled in
OpenNoteLM's application image or source release.

## Apple Silicon setup / Apple Silicon 安装

Requirements: Python 3.12, uv, sufficient free disk/memory and internet access for
the initial download. The tested setup uses an Apple Silicon Mac with 24 GB RAM,
MPS and PyTorch SDPA. CPU is available when MPS is unavailable, but can be much slower.
The isolated environment and model live under ignored `.local-services/qwen3-tts/`.
The model download is approximately 2.3 GB; dependencies need additional space.

安装需要 Python 3.12、uv 和首次下载网络；使用独立环境，不会把 PyTorch 加入主应用。
已在 24 GB Apple Silicon Mac 上使用 MPS/SDPA 验证。无 GPU 时使用 CPU，速度不能等同。

```bash
bash tools/setup_qwen_tts.sh
bash tools/run_qwen_tts.sh
```

Keep the service running separately from the application. It listens only on
`127.0.0.1:8320`, performs one inference at a time and bounds waiting requests.
Stopping a Podcast joins application work and retains completed audio. A local
inference already executing may finish before the service accepts another request.
The service does not log submitted text or returned audio. Startup warnings about
optional FlashAttention/SoX are not evidence that CustomVoice inference failed.

服务与应用分别运行，仅监听本机；单次推理串行，排队数量受限。停止 Podcast 后保留已完成
音频；已经在推理线程中的请求可能需要等本段结束后才释放模型。服务不记录提交的台词。
首次加载需时间；以 `/health` 返回正常及实际语音测试为准。

## Voice consistency / 分段声音一致性

New Podcasts send optional `X-OpenNoteLM-Speech-Policy: podcast-stable-v1` and
`X-OpenNoteLM-Speech-Language` headers. This adapter uses the episode's language,
a fixed seed per preset voice, and temperature 0.7 / top-p 0.9 for both talker and
subtalker. Sampling stays enabled. CPU/CUDA/MPS random states are restored after
each profiled inference; requests remain serialized. Calls without the policy
retain the old Auto-language/default-sampling behavior. Standard Speech request
bodies stay unchanged; other compatible providers may ignore these extensions.

新节目明确传入语言、按预设声音固定 seed 并降低采样随机性；旧节目沿用原策略与缓存，
升级不会重写已生成的 MP3。后台服务使用 Application Support 下的适配器副本，更新
仓库代码本身不会更新正在运行的服务；无活动任务时备份旧适配器并更新、重启该服务。

This reduces uncontrolled variation; it does **not** provide an acoustic voice
anchor or guarantee speaker identity across different texts. The 0.6B CustomVoice
model does not support instruction-based style control. If perceptual drift persists,
the stronger follow-up is a reviewed Base-model adapter reusing one reference prompt
per synthetic speaker, which requires different weights and separate acceptance.
See the [upstream model table and reference-prompt API](https://github.com/QwenLM/Qwen3-TTS#python-package-usage).

固定 seed 能让相同输入更可复现，不能证明不同台词的音色完全一致。0.6B 不支持风格指令；
不能通过添加“保持声音不变”的文字假装解决。更强的固定参考音频方案尚未实现。

## Application settings / 应用模型设置

| Field / 字段 | Value / 填写值 |
|---|---|
| Protocol / 接口 | OpenAI-compatible Speech |
| Base URL / 服务地址 | `http://127.0.0.1:8320/v1` |
| Model / 模型 | `Qwen3-TTS-12Hz-0.6B-CustomVoice` |
| Voice A / 声音 A | `Ryan` |
| Voice B / 声音 B | `Vivian` |
| Key / 密钥 | Empty for this loopback service / 本地服务留空 |
| Speech concurrency / 语音并发 | `1` |

Test and save checks both voices with short audio samples. Available voices and
languages are listed by `/v1/voices`. Qwen supports Chinese, English, Japanese,
Korean, German, French, Russian, Portuguese, Spanish and Italian. **Arabic and Hindi
are not supported**; select a speech provider that supports them. Interface/script
language support does not imply a particular speech model supports every language.

测试会实际生成两种声音的短音频。Qwen 支持中、英、日、韩、德、法、俄、葡、西、意语；
**不支持阿拉伯语和印地语**。应用文字支持的语言与模型语音能力不同。

The URL is relative to the **application server**, not the user's browser. A Docker
container's `127.0.0.1` is the container itself. If the app runs in Docker, use a
reachable host service address appropriate to your Docker networking and verify it
from the container. Do not expose this unauthenticated loopback adapter publicly.
For other hardware, use the official Qwen installation instructions and a reviewed
compatible server; this installer deliberately does not guess CUDA/driver versions.

地址由应用服务器访问；Docker 中的 `127.0.0.1` 指向容器，不能直接等同于宿主机。
容器部署时须按运行环境配置可达地址并验证，不要直接将无鉴权的本地适配器暴露公网。
其他硬件请使用官方安装方式，本脚本不自动安装或调整 GPU 驱动。
## Optional background service / 可选后台服务

After stopping any manually started copy, macOS users can run
`bash tools/install_qwen_service.sh`. This installs a per-user LaunchAgent which
starts on login and keeps the loopback service available. To remove it, stop
`org.opennotelm.qwen3-tts` with `launchctl bootout` in your GUI domain and delete
the matching file from `~/Library/LaunchAgents/`; model files remain local.
The installer clones the optional runtime/model into
`~/Library/Application Support/OpenNoteLM/Qwen3-TTS/` so the background service
does not require access to a privacy-protected Documents checkout. No application
data or credentials are copied. Its `logs/service.log` contains operational messages.

停止手工启动的同端口服务后，macOS 可运行上述安装脚本，注册当前用户的登录后台服务。
它只监听本机地址，不安装系统守护进程。移除后台服务不会删除模型或应用资料。
安装器将可选运行环境和模型复制到用户的 Application Support，避免为后台进程授予
整个 Documents 的访问权限；不复制应用资料或密钥。
