# Codex Project Navigator

按项目整理卡片、成果文件与来源对话，并从卡片继续工作。项目记录保存在每个用户自己的 `.project-library/record.json`；原有文件和 Codex 会话仍由用户管理。

## 状态

这是基于 macOS Codex 桌面版开发的源代码。界面接入使用当前安装版本的内部 DOM 和组件，Codex 更新后可能需要适配。**Windows 接入与安装尚未完成**；Windows 用户先运行 [接入检测](docs/windows-preflight.md)，再按 [Windows 适配任务](docs/windows-port.md) 继续。

## 交给 Codex 接手

克隆此仓库，在自己的 Codex 中打开它，然后发送：

> 请按 `AGENTS.md` 和 `docs/windows-port.md`，先运行 Windows 接入检测，再完成 Windows 版安装、文件操作和桌面界面适配。只使用本机测试项目验证，不读取或上传个人聊天。完成必要测试及真实窗口验收。

检测结果决定下一步改哪里；不能把 `CONNECTABLE` 当成完整功能已通过。项目内容分类和日常维护规则见 [project-records Skill](skills/project-records/SKILL.md)。

## 源码

- `library.py`、`project_records.py`：项目目录、Git 与聊天整理位置。
- `conversation_assets.py`、`delivery_audit.py`：对话交付线索与成果缺口。
- `web/`：项目导航页面与 Codex 桌面界面接入。卡片可收录 HTTPS 链接，用于打开公开仓库等网页成果。
- `scripts/`：本地服务管理、命令行和桌面启动辅助工具。
- `tests/`：使用临时项目与模拟数据库的测试。

macOS 源码验证需要 Python 3.10+ 与 Node.js 22+：

```sh
npm ci --ignore-scripts
npm test
```

本仓库不包含用户的项目记录、聊天数据库、图片、密钥或安装包。仓库内的 `LICENSE` 为 Apache-2.0；复用组件及其许可见 [第三方说明](THIRD_PARTY_NOTICES.md)。
