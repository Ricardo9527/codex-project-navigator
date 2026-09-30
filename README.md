# Codex Project Navigator

在 Codex 中按项目浏览目录、工作卡片、成果文件和来源对话。界面使用 OpenAI Apps SDK UI；项目记录保存在各项目自己的 `.project-library/record.json`，Codex 数据库与会话文件只读。

## macOS 安装

需要已安装并登录的 Codex 桌面版、Node.js 22+、Python 3.10+ 和 Git。应用默认从 `/Applications/ChatGPT.app` 或 `/Applications/Codex.app` 查找；命令行工具优先使用桌面应用附带的 Codex CLI。

```sh
git clone https://github.com/Ricardo9527/codex-project-navigator.git
cd codex-project-navigator
npm ci
npm run setup
```

安装脚本会探测本机 Node/Python 路径，生成本机专用插件配置，注册项目导航插件和项目记录 Skill，构建 **Codex 资料库.app**，并安装用户级资料库服务。配置、缓存和启动器均保存在忽略目录，不需要修改源码中的路径。

安装结束后，**正常退出 Codex，再打开仓库中的 `Codex 资料库.app`**。以后也从这个启动器打开：它启用本地接入端口，项目旁会出现导航按钮。把仓库保留在安装时的位置；移动后重新运行 `npm run setup`。

- 项目旁导航按钮进入该项目主页；页面内通过目录和卡片浏览。
- 卡片底部“在此项目开始工作”携带卡片背景，进入完整原生新聊天；由你选择模型并发送。
- Codex 自带的右下角浮动聊天不会自动绑定导航项目。项目工作请使用卡片底部按钮。
- 尚无记录的项目显示空主页。开始实质工作时，让 Codex 使用插件内的 `project-records` Skill 建立记录。
- 安装后若插件或界面仍是旧版本，正常退出并重新打开 Codex；仅刷新记录不会重建已加载聊天的 MCP 连接。

可先运行 `npm run setup -- --dry-run` 查看将使用的程序路径与操作；`--configure-only` 仅生成本机配置，不注册插件或安装启动项。自定义应用路径用 `CODEX_APP`，CLI 路径用 `CODEX_CLI`，Python 路径用 `PROJECT_NAVIGATOR_PYTHON`。

## Windows / Linux

同样可以克隆仓库并部署官方插件：

```sh
npm ci
npm run setup
npm start
```

需要本机安装 Python、Node.js 和可运行 `codex plugin` 的 Codex CLI。`npm start` 在这两个系统以前台方式运行本地资料服务；保持终端开启，再重开 Codex 使用插件菜单中的“项目导航”。安装器不改写系统自启动配置。

Windows 的项目旁按钮接入先按 [接入检测](docs/windows-preflight.md) 操作；完整步骤及 Linux 说明见 [跨平台部署](docs/cross-platform.md)。原生项目草稿接入在非 macOS 平台默认不可用，需核对该平台桌面构建后再适配。

## 验证范围

| 能力 | macOS | Windows / Linux |
| --- | --- | --- |
| 卡片、目录、搜索、预览的代码与测试 | 已验证 | 共用实现，待实机验收 |
| 本机配置生成、插件启动、Mac 启动器构建 | 已验证 | 部署入口已提供，待实机验收 |
| 项目旁按钮、带背景进入原生项目草稿 | 已在开发机验收 | 待适配 |

原生草稿桥接当前核对过 Codex `26.928.20755` 和 `26.928.21956`；其他构建会明确报告需要适配。官方插件页面本身不使用桌面内部 React 组件，项目旁按钮和草稿桥接仍依赖运行时接入。**不能保证所有未来 Codex 版本免适配，也未宣称 Windows/Linux 已完成实机验证。**

## 日常使用与维护

```sh
npm test
```

更新源码后执行 `npm ci && npm run setup`，再正常重开 Codex。macOS 移除自动接入：

```sh
python3 scripts/install-agent.py --uninstall
```

插件在 Codex 插件管理中单独卸载。项目记录保留在原项目中。

代码入口：`experimental/project-navigator/`（MCP 与官方 UI）、`web/`（内容组件和桌面桥接）、`scripts/setup.mjs`（安装）、`library.py` 与 `project_records.py`（资料服务）、`skills/project-records/`（记录规则）。

仓库不含开发者的私人项目记录、缓存、聊天、密钥或旧私有 Git 历史。Apache-2.0；第三方组件见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## Maintenance batch recovery

Daily coverage saves preserve an active maintenance batch. To finish a task using a replacement checkpoint, pass `completedBatchId` to `finishMaintenance`; the service verifies the target HEAD, original thread coverage, and file scope before completing the task.
