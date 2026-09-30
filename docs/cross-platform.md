# 跨平台部署

## 通用插件层

安装 Node.js 22+、Python 3.10+、Git，以及支持 `codex plugin` 的 Codex CLI。Codex 桌面应用需已登录，至少添加一个本地项目。

1. 克隆仓库并执行 `npm ci`。
2. 执行 `npm run setup -- --dry-run` 检查运行时路径。
3. 执行 `npm run setup` 注册 `project-navigator@project-navigation-local`。
4. Windows/Linux 执行 `npm start` 并保留终端；macOS 用生成的 `Codex 资料库.app`。
5. 正常重开 Codex，从插件菜单打开“项目导航”。首次实质工作使用随插件安装的 project-records Skill 建卡。

安装器生成的 `data/install-marketplace/` 包含本机专用 MCP 配置；其中使用绝对程序路径，避免 GUI 应用 PATH 与终端不同。不要上传这个目录。项目数据仍仅存在本机。

PowerShell 自定义 Python：

```powershell
$env:PROJECT_NAVIGATOR_PYTHON = 'C:\Python313\python.exe'
$env:CODEX_CLI = 'C:\path\to\codex.exe'
npm run setup
npm start
```

Linux/macOS 自定义 Python：

```sh
PROJECT_NAVIGATOR_PYTHON=/usr/bin/python3 npm run setup
```

## 桌面旁按钮与草稿桥接

该层使用回环调试端口 `127.0.0.1:9333`。先正常关闭 Codex，再用其实际可执行文件加上以下参数启动：

```text
--remote-debugging-address=127.0.0.1 --remote-debugging-port=9333
```

Windows 使用现有 `scripts/windows-start-for-test.ps1` 和 `scripts/windows-preflight.ps1`，具体参数见 [Windows 检测](windows-preflight.md)。Linux 的可执行文件和启动方式由实际安装包决定，不能照抄 macOS 的 `.app` 路径。

停止前台资料服务后，可运行 `npm start -- --desktop` 启动接入监管器。不要同时运行两份监听 47832 的资料服务。端口可连通只证明接入条件成立，不等于选择器、组件和草稿接口通过验收。

非 macOS 上“在此项目开始工作”默认禁用。适配任务应先只读核对当前桌面构建，再验证：项目主页、无项目数据泄漏、草稿工作目录、卡片背景、用户发送后项目归属、关闭导航恢复聊天。不得仅凭内部字段读回就认定成功。

## 文件与文档能力

- 文本、Markdown、JSON、图片预览共用代码；非 macOS 图片使用有大小上限的原图预览。
- 文件位置：macOS Finder、Windows Explorer、Linux `xdg-open`。
- 非 macOS 的“添加文件”使用 Python tkinter；未安装时会提示，也可让 Agent 用 `registerResource` 登记。
- Word/Excel/PDF 正文提取有平台依赖，缺失工具会报告错误；适配时按 `project_search.py` 的实际依赖补齐，不能把空结果当成成功。
- 当前 Codex 数据发现针对 `.codex/state_5.sqlite` 和桌面项目表；客户端数据结构改变时需调整，数据库保持只读。

Windows/Linux 尚未在真实设备完成验收。可将本文件交给该机器上的 Codex，先检测再适配，不需要修改或上传个人聊天数据。
