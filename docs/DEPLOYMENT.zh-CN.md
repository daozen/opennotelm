# 安装、升级与恢复

[English](DEPLOYMENT.md)

## 从源码启动

安装 Docker 与 Compose，克隆仓库，复制 `.env.example` 为 `.env`，
在根目录执行 `docker compose up -d --build`。打开 http://localhost:3000 配置模型。
`docker compose ps` 和 `docker compose logs --tail 100 app` 可检查状态，分享前请脱敏。

镜像带 Chromium 和 Noto 字体，不需要额外数据库/Redis。应用以非 root 用户运行；
初始化仅修正挂载数据目录本身的所有权，恢复旧文件时应确保 UID/GID 10001 可访问，
不要将整个目录设为所有人可写。原生开发见[贡献规范](../CONTRIBUTING.zh-CN.md)，
不是桌面安装包；macOS 可使用 Docker Desktop 或已配置的 Colima。
当前 cryptography 不再提供 Intel macOS 预构建 wheel，原生安装可能需要上游构建依赖；
这类机器优先使用 Docker Linux amd64 镜像。可安装平台不等于已全部完成验收。
Docker 构建另外重编译并核对 lxml 内置 XML 库；原生 `uv sync` 不会应用该替换。
默认 Compose 删除应用额外权限并禁止权限提升；启动失败时不要直接删除这些防护。
当前镜像未解决安全项见[安全核查](CONTAINER_SECURITY_REVIEW.md)。

## 已发布镜像

**只有对应版本发布、GHCR 镜像设为公开后才能使用。** 工作流准备 Linux amd64/arm64
镜像并记录 digest；发布前仍可源码构建。在 `.env` 中指定版本，例如：

```dotenv
OPENNOTELM_IMAGE=ghcr.io/daozen/opennotelm:0.1.0-beta.2
```

```sh
docker compose pull
docker compose up -d --no-build
```

更严格的固定可使用 `ghcr.io/daozen/opennotelm@sha256:<published-digest>`。
不要依赖 `latest` 升级。发布附件包含源码、校验值、依赖声明/清单和 Compose 设置。

## 配置与可信内网

`.env.example` 提供安全默认值。优先通过界面设置模型，也支持可选的服务器密钥环境项。
界面已保存并发优先于环境初值；`.env` 由 Compose 读取，原生 Uvicorn 不自动读取它。

默认监听 `127.0.0.1`。允许可信内网时设置明确的本机绑定地址，并把访问地址加入
`ALLOWED_HOSTS`，在网络/系统层限制访问。没有登录鉴权，任何可访问者都能读取资料和
设置；Allowed Hosts 不是访问权限控制，不要向公网转发端口。
容器内 localhost 无法访问宿主模型；Docker Desktop 可用 host.docker.internal，
其他运行时可能需要配置 host gateway，请逐角色测试。

## 完整备份

1. 先完成或主动停止任务，保留检查点；主动停止的 Deck 重启后仍保持停止。
2. 执行 `docker compose down` 停服，不删除数据目录。
3. 将实际配置的**整个数据目录**复制到受保护位置，包含数据库、原文件、产物、
   `secrets/` 和加密主密钥。
4. 同时保存代码提交或镜像版本/digest。恢复演练用独立数据/端口，不调用付费模型。

只复制在线数据库不是完整备份，相关文件和密钥必须匹配。丢失主密钥无法读取已保存
凭据，备份访问权限应与原数据同样受保护。

## 升级与回退

停服并完整备份后，切换已审查的源码标签并构建，或更换固定镜像并拉取。
源码用 `docker compose up -d --build`，镜像用 `docker compose up -d --no-build`。
启动自动迁移，确认健康、既有笔记本、下载和配置后再继续主动停止的任务。
每目录只有一个进程，禁止原生/容器双开或多个 workers；验证结束前保留完整旧备份。

回退时停止新实例，另外保留其数据，恢复对应旧版本的完整备份并启动旧代码/镜像。
核对所有权和密钥。**不要用旧代码打开已迁移的新数据库**，数据库和文件一起恢复。
不要删除实例锁绕过仍在运行的持有者。
恢复的中断任务可能继续并调用模型，演练时应隔离模型访问，除非这些请求符合预期。

候选运行镜像使用 Debian 13/Trixie 上的 Python 3.12。镜像安全状态单独记录在[准备状态](RELEASE_STATUS.md)，功能测试通过不代表漏洞记录已解决。
