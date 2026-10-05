# 26.930.31730 → 26.930.51102 更新核对

基于官方安装包代码对比，构建 12947 → 13100；功能效果尚未在新版窗口验证。

- 自动任务：下次运行提示优先使用 nextRunNominalAt，再使用 nextRunAt；无实际下次运行时间时仍返回空。函数 Sbo、ADo。
- Pages：增加 HTTPS/WSS broker 地址分类；快照 journal 将 ws.chatgpt.com 归一为 chatgpt.com，再生成 HTTP 地址。函数 $Ot、ekt 与 journal 构造器。
- 发送：beforeSendRequest 回调增加 optimisticSteer 状态；消息显示通知识别该状态。函数 Jrn、KDn。
- 草稿：保留输入的函数增加 clearSavedDraft/discardRetainedDraft 参数；提交流程与结果未知分支增加相关处理。函数 Bgr、Jat、mct；具体用户体验改善未实测。
- 构建：遥测 buildCommitSha 更新；依赖声明和界面 defaultMessage 声明无新增或删除。

已适配：核心模块匹配、草稿 tIt→nIt、Scope 解析 z7t→B7t；其他所用导出名未变化。新包契约检查及当前版本回归通过，实际新版点击待验收。

对比覆盖核心 initial/shared/primary 模块与界面消息声明；上述为确认的局部逻辑差异，不是完整发行说明。
