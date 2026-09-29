# 记录字段

项目字段：`version: 1`、`projectId`、`about`、`history`、`historyCardId`、`categories`、`cards`、`reviewedThreads`、`coverage`、`coverageDetail`。

目录：`id`、`title`、`description`；有父目录时加 `parentId`。不能循环。有子分类的目录只负责汇总，卡片的 categoryIds 只能指向末级分类。

卡片必需字段：`id`、`title`、`summary`、`categoryIds`、`kind`、`icon`、`caption`、`resources`、`sources`、`sections`、`records`、`requirements`、`related`。空集合用 `[]`。

可选：`status`、`attention`（文字数组）、`quickStart`、`resourceHeading`、`manualFields`。状态有依据才写；长期工具和知识不必标成进行中或完成。

文件：`id`、`label`、`path`、`format`、`role`、`note`。`role` 为 `result`、`process` 或 `preview`；路径默认相对项目根目录。`source: skill` 指向 `~/.codex/skills/` 下的 `SKILL.md`。`group` 合并同一成果的不同格式；`previewId` 关联另一个资源。图片用 `format: 图片`，可加 `versionGroup`、`versionLabel`、`adoption: accepted`（仅明确采用时）。

对话来源：`id`、真实 `title`、`label`。说明段：`title`、`paragraphs`（文字数组）。工作记录：`date`、`text`。`related` 为卡片 ID 数组。

`reviewedThreads` 是实际已整理完成的对话 ID 到 `updated_at` 的映射；它随 Git 提交保存，不是第二套版本系统。

`record` API 返回的 `revision`、`recordPath` 与资源 `exists` 是实时信息，写回时由服务移除。Git commit 保存内容版本；revision 仅用于防止并发覆盖。

## 工具维护的字段

`reviewState` 保存已整理业务 commit、分支、工作区与登记成果指纹及 lastScope。它与目录一起进入 Git，缓存丢失后仍能恢复。检查点写入前的业务 HEAD 是整理位置，保存记录自身的提交不作为新业务变化。Agent 保留此字段，用 checkpoint 更新。

`externalFiles` 是已明确登记的外部单文件映射；资源以 `source: external`、`path: 映射ID` 引用。通过 registerResource 建立，不直接手写任意外部路径。

`acceptedFingerprint` 与 `adoptionHistory` 由 adoptResource 维护。读取时的 effectiveAdoption、versionChanged、versionUnverified 和 exists 是运行时结果，不手工写入。

`maintenanceAutomation` 记录已核实的独立周检 ID 与状态，由 linkAutomation 写入。

成果交付时间为 deliveredAt（ISO 日期时间）；origin 保存 threadId、turnId、itemId 和必要的请求线索。来源字段来自实际交付，不猜测。图片按交付时间排序，缺少交付时间时以文件更新时间辅助排序并标明依据。process 文件不提供选用。


分类数组顺序为页面顺序；有流程的项目按工作阶段组织，同一级分类依据保持一致。`manualCategoryOrder: true` 保护已有分类相对顺序；分类的 `manualFields` 列出用户修改的字段，Agent 保存时保留这些值。

`deliveryReview` 由 `resolveDeliveryGap` 维护，按缺口 ID 保存证据签名、处理结论、理由和来源。结论为 reference、duplicate 或 unavailable；duplicate 指向已有卡片及资源，unavailable 在页面保留说明。证据变化后重新进入补漏清单。Agent 不手工推进此字段以跳过未处理成果。

`prepareBatch` 的 deliveryGaps 与 Git、对话增量一起形成本次待办。用 `reviewScope` 分页读取；已读旧对话仍参与缓存交付清单与已登记成果的对照。


## 日常维护覆盖

`reviewedCommits` 由 saveRecord 的 coverage 参数维护，映射完整业务 commit ID 到卡片 ID 数组；增量检查仅跳过逐项登记的提交，不推高全项目基线。已有完整检查点继续生效，无须重登记旧历史。

日常 `reviewThread` 可省略 batchId，提供 threadId；返回 reviewedUntil、updated_at 与分页正文。后续分页传 until 固定读取上界。saveRecord 的可选参数示例：

```json
{
  "expectedRevision": "读取 record 返回的 revision",
  "record": "完整项目记录对象",
  "coverage": {
    "cardIds": ["本次已更新当前状态的卡片ID"],
    "commits": ["完整的40位业务commit ID"],
    "thread": {"id": "对话ID", "reviewedUntil": 0, "updated_at": 123}
  }
}
```

commits 和 thread 均可省略；位置必须来自 reviewThread 的实际返回值。程序在同次保存中校验并登记，保存失败不推进位置。关联卡片的资源指纹同时更新，后续文件再次变化仍进入补漏；缺文件或缺来源仍由 deliveryGaps 检查。无须改卡片的聊天可以使用空 cardIds；登记业务 commit 必须关联有效卡片。
