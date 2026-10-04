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
- 原生 Deck 中复制的 Lucide 几何保留英文声明中的完整 ISC/Feather 版权信息。

上游元数据不是完整法律审计。新增依赖、修改 copyleft 文件、分发模型权重或素材时需再核对。
仓库不分发模型权重、用户书籍、用户生成 Deck 或凭据。公开示例/测试是合成资料，
来源说明与测试文件同存。许可法律文本保留英文原文，本页仅说明，不替代条款。

镜像另外将所安装 Chromium 的内置完整许可页和条款保存到 `/app/licenses/browser/`；仅访问内置页面，不访问外网或用户资料。
