# 第三方许可声明说明

[English and original license texts](../THIRD_PARTY_NOTICES.md)

项目 MIT 仅覆盖自有代码，依赖和内置组件保留原有条款。
[锁定依赖清单](DEPENDENCIES.json)包括直接/间接应用包及声明许可；
开发和其他平台专用包不一定包含在实际运行镜像中。

- 发布附件复制 Python 运行依赖及前端生产依赖的许可/版权原文，不翻译替换。
- 前端声明位于 frontend/dist/third-party，镜像 Python 声明在 /app/licenses/python
  及安装包元数据中。
- PDFium 与原生库的构建声明随 pypdfium2 保留；Playwright Node driver、Chromium、
  Debian 和字体各有许可。Chromium 还提供 chrome://credits，Debian/Noto 声明在
  /usr/share/doc 等安装位置。应用包清单不覆盖全部系统/浏览器/原生组件，
  镜像发布另生成每平台 SBOM 与来源证明。
- certifi 使用 MPL-2.0；tld 提供 MPL/GPL/LGPL 选项，本分发选择 MPL-1.1。
  未修改其文件，附件提供按 uv.lock 哈希核对的准确上游源码，清单也含源码地址。
  不要移除声明或获取对应源码的途径。
- Docker 重编译的 lxml 底层库将 libxml2/libxslt/libexslt 版权原文及来源哈希保存在
  /app/licenses/native-xml；发布附件也包含这些原样底层源码和许可。
- 两项固定的 Debian 安全修复保留完整版权/许可文本于 /app/licenses/debian-security；
  发布附件包含对应原始源码、Debian 打包文件及声明。ACL 保留 LGPL-2.1-or-later，
  不因应用使用 MIT 而改为 MIT。
- 原生 Deck 中复制的 Lucide 几何保留英文声明中的完整 ISC/Feather 版权信息。

上游元数据不是完整法律审计。新增依赖、修改 copyleft 文件、分发模型权重或素材时需再核对。
仓库不分发模型权重、用户书籍、用户生成 Deck 或凭据。公开示例/测试是合成资料，
来源说明与测试文件同存。许可法律文本保留英文原文，本页仅说明，不替代条款。

镜像另外将所安装 Chromium 的内置完整许可页和条款保存到 `/app/licenses/browser/`；仅访问内置页面，不访问外网或用户资料。

开发分支的 Podcast 使用外部 FFmpeg。原生安装使用用户已安装的版本；开发镜像安装
Debian FFmpeg，并保留 `/usr/share/doc/` 中的原许可。FFmpeg/编解码组件各自保留
LGPL/GPL 等条款，不继承本项目 MIT。新镜像公开发布前必须重新核对 SBOM、许可和
对应源码分发；以前镜像的审核不能覆盖此次变化。

可选 Qwen3-TTS 在独立本地环境安装，不随应用镜像或发布附件分发运行环境、模型权重。
所选官方代码和模型声明 Apache-2.0，其他依赖各有许可；自行再分发时需另行核对。
配置和固定模型版本见 [Qwen3-TTS](QWEN_TTS.md)。

容器的音频工具由固定哈希的 FFmpeg 原始源码精简编译，采用 LGPL 组件并使用 Debian
LAME 库；原始声明保存在 `/app/licenses/native-audio/` 和 `/usr/share/doc/`，发布附件
包含准确 FFmpeg 原始源码。原生安装的 FFmpeg 仍遵循其构建所启用组件的许可。
