# 0.2.1 迁移修复

- 更新直接启动对应项目的整理任务；使用该任务模型支持的专用上下文配置，不修改项目的全局配置。
- 卡片工作附带唯一关联标识；本地监管器从新对话的原生上下文中核对项目与标识后，登记回卡片来源。不会修改 Codex 数据库。
- 恢复记录、维护状态和检查点的自动同步，空项目的整理按钮接入同一更新流程。
- 文件选择保留五分钟等待；服务错误保留具体业务原因。
- 修正关闭 SDK 弹窗后的 Escape 行为，恢复 MCP 工具结果指定卡片。
- 来源消息定位接回已核对的桌面构建；未知版本会明确报错。
- 背景附件是打开草稿时的快照，附带最新项目记录位置和工作前核对提示，不承诺附件实时变化。
- Windows 文件锁采用平台实现，消除导入 fcntl 时立即失败的问题；跨平台仍需真实机器验收。

回归测试和临时数据 UI 检查通过。实际整理完成、新卡片聊天发送回写及精确来源跳转仍需在目标机器验收。只读内部字段或工具清单不作为这些流程成功的凭据。

精确来源补充验证：先用原生搜索游标加载目标历史，再分别按文本消息搜索键和工具块定位键定位。两条较早的真实来源已通过视区及焦点验收；回归覆盖目标轮次、目标消息和错误轮次拒绝。无需重启即可由本地定位桥接读取更新。

## Desktop 26.928.31416 (build 12553)

Added module matching for native project drafts, maintenance task creation, and exact source navigation. Contract checks pass against the downloaded bundle; actual desktop behavior after installing this build remains to be verified. Tests accept `CODEX_DESKTOP_ASAR` to check a staged update without installing it.

Legacy source records may omit message IDs. Navigation now locates the recorded turn using its actual search result, or opens the conversation when no turn is recorded. Labels distinguish message, turn and conversation navigation. The legacy Metadata source was verified on the desktop with its target visible. Reload the MCP connection to load the updated tool input schema.

## Desktop 26.930.31730 (build 12947)

Added build-specific module and export mappings for project drafts, maintenance creation and source navigation. Contract checks pass against the downloaded update; behavior in the updated desktop still awaits verification. Previous build support is preserved.

## Desktop 26.930.51102 (build 13100)

Added updated module matching, native draft export nIt and Scope resolver B7t, preserving earlier builds. Downloaded bundle contract checks pass; actual updated desktop behavior awaits verification. Code differences are summarized in `Codex_26.930.51102_更新核对.md`.

Native drafts now use the registered desktopId when it differs from the project library ID, while verifying the actual desktop root. Cross-identity and wrong-root regressions pass; the complete MCP draft-preparation path was verified. No test message was submitted.

## Desktop 26.1002.52244 (build 13536)

Remapped project draft, task creation, Scope and source-navigation exports; also added 26.930.61225 matching. Contract checks cover the downloaded build and the installed build, including delayed RPC access. Actual updated desktop actions await verification. See `Codex_26.1002.52244_更新核对.md` for observed package changes.

## Desktop 26.1007.21159 (build 20052)

Remapped draft/task creation, Scope access and source navigation. The real desktop-project atom contract is checked without relying on its minified constructor name; export aliases containing $ are supported in contract checks. Previous builds remain supported. New-bundle contracts and installed-build regressions pass; actual updated desktop acceptance is pending.
