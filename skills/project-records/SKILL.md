---
name: project-records
description: 在完成重要工作、形成决定或留下待续事项时维护项目目录和卡片；也用于手动更新、定期增量补漏及单独授权的旧项目首次整理。不用于普通问答的逐轮收尾。
---

# 项目记录

`.project-library/record.json` 是项目目录和卡片的统一来源。详细内容沿用 README、设计文档与工作记录，在目录中引用它们。

源码 CLI 为本 Skill 目录下 `../../scripts/libraryctl.py`。安装路径为符号链接时先解析真实目录。`--project` 接受项目 ID、名称或绝对目录；服务不可用可用 `--offline`。

## 日常工作

开始实质工作时读相关记录，核对需要的真实文件和当前版本。新项目缺少入口时调用 `ensureRecord`，沿用或建立 Git，按实际内容起步。全新项目的首个工作阶段完成后，按下方首次整理流程保存可靠基线，完成导航身份接入，并接入独立周检。

日常维护是主要入口，手动更新和周检用于补漏。完成一项工作、形成重要决定或留下待续事项时，先判断这件工作的对象和目的：与已有卡片相同就更新该卡片的当前说明、决定、成果入口与来源；能够独立找回、分享或继续推进的工作就新建卡片，必要时关联原卡片。不要只追加日志而让“当前情况”停在旧版本，也不要等到定期整理才为独立工作建卡。普通问答和没有实质变化的讨论不需要读写记录，也不需要收尾凭据或专门汇报整理动作。中断之后，从已有记录与工作区接续。

新卡片先归入合适的现有末级分类；确有不同的稳定子组、现有目录已不方便查找时才建立子分类，并同步调整原先直属父级的卡片。没有合适的一级主题时再建立新分类。目录帮助浏览，卡片代表独立工作；不按 commit、文件数量或固定层级自动增加分类和卡片。

## 日常维护表单

日常维护优先使用 Agent 可调用的 `prepare_daily_record` 与 `save_daily_record`。同名 CLI 动作为 `prepareDailyRecord`、`saveDailyRecord`。准备一次、提交本次增量；不读取整份项目记录、不写临时拼装脚本、不启动 prepareBatch，也不为新增成果修完整个历史。现有 saveRecord 用于专门的历史整理，不再作为日常入口。

- Agent 判断维护时机。连续试稿在阶段结束、选定方向或切换工作时集中登记，未定稿也可保存；不逐张图触发。
- 准备时提供 projectId、当前 threadId、目标 cardId（多张可用 cardIds）。程序返回轻量分类/卡片索引、选中卡片当前说明、本条聊天的增量成果和固定 scopeId；成果分页沿同一 scopeId、nextOffset 接续，不重新解析聊天。只新增卡片可不选 cardId。
- 提交填写 scopeId、updates、threadCoverage。updates 仅包含本次变化：cardId；必要的 changes（title、summary、categoryId、notes）；选中的 deliveries（assetId，必要时 label）。程序填写文件、真实消息位置、交付时间及来源关系。没有变化的旧字段不重写。
- 新卡片省略 cardId，changes 必须含 title、summary、categoryId；其他机械字段由程序建立。已有分类直接沿用，只检查本次涉及的归属；确需新增目录时传 categories（id、title、可选 parentId），不借日常维护全量调整目录。
- threadCoverage 必须明确：complete 表示当前上下文已完整处理准备时固定范围内的所有有意义内容，程序才推进到该范围终点；unchanged 只登记本次卡片与成果，保留原聊天处理位置。登记了图片不等于整段聊天已整理，旧前段尚未处理时不得选 complete，也不因此强制日常重读历史。
- 导入文件或旧资料没有真实消息来源时，用 files（path、sourceReason；项目外需 external=true）明确来源及实际缺失，不能编造消息 ID。此声明与真实聊天交付区分，不要求补齐无关旧缺口。
- 本次选定的 generated_images 成果由程序保存到项目 assets/deliveries，保留原图来源；只对本次需要匹配的同大小文件计算并缓存内容哈希。副本去重不删除来源与跨卡片用途，不改变采用状态。
- 一次提交同次登记卡片、成果、来源、实际聊天覆盖与可选 commits（完整业务 SHA）。保存失败不推进位置；相同 scopeId 和相同内容可安全重试。真正的同字段并发冲突按错误重新准备，不读取并重写无关卡片。
- 表单程序自动记录调用起止、后端耗时、成功/失败、输入字节、说明行数和成果数量，保存在本机 data 索引；不记录提示词或文件正文，不增加每轮操作。仅在评估维护成本时使用 read_daily_timing / CLI dailyTiming，日常不额外调用计时工具。后端耗时不等于 Agent 维护总耗时；检查图片、组织文字及另存已有提示词等活动，按实际会话时间线核对，时间间隔不直接归为“思考”或“纯维护”。
- 工具返回简短保存结果，不再回整份记录。普通问答不维护。用户实际采用由 adoptResource 单独确认，不能自动把最新成果标为采用。

CLI 示例（技能目录下 ../../scripts/libraryctl.py）：

```sh
python3 CLI_PATH prepareDailyRecord --project PROJECT_PATH --json '{"threadId":"当前对话ID","cardId":"已有卡片ID"}'
python3 CLI_PATH saveDailyRecord --project PROJECT_PATH --json '{"scopeId":"准备结果的scopeId","threadCoverage":"complete","updates":[{"cardId":"已有卡片ID","changes":{"notes":["本轮已完成，待确认。"]},"deliveries":[{"assetId":"准备结果的assetId"}]}]}'
```

工具定义尚未在当前会话刷新时，直接用上述 CLI 传结构化参数；不因此退回全记录脚本。未涉及 commit 时省略 commits。提交业务改动后通过同一入口登记对应 SHA，再提交项目记录自身，不另启动全项目整理。

目录依据项目内容决定，用 `parentId` 表达层级。父级只汇总子分类，卡片仅归入末级分类；新增子分类时同步调整原先直属父级的卡片。层级按内容需要决定，不强求每条路径一样深。来源使用真实对话 ID 和标题。文件存在不等于用户采用；状态有证据才写。

## 分类与顺序

先根据项目用途选择主要分类依据。同一级尽量使用相同依据：有明确工作流程时按调研、设计、实现、验证等实际顺序组织；无阶段顺序时按稳定主题或工作对象组织。维护、参考与历史等辅助内容通常放在主要工作之后，不强行套通用模板，也不把任务状态与工作主题混为同一级分类。

目录和卡片的数组顺序就是展示顺序。目录优先遵守有意义的工作流程；同一主题内的卡片按对象、章节或工作关系排列。卡片内成果仍按实际交付时间倒序，选用状态独立。已有目录的小幅增量优先沿用原结构，不能每次维护重新洗牌。

只有一个目录下确实形成几个清楚、稳定且方便查找的子组时才建立二级；不要只为数量整齐或固定层数而拆分。直接工作的名称是卡片，不为了每张卡片套一层文件夹。父级负责汇总，末级放卡片。

项目首页已经承担用途与当前概况；“项目总览”类目录需检查是否重复。若内容实际是架构说明、使用指南等，按实际用途命名。维护时保留用户已调整的分类及顺序；manualCategoryOrder=true 保护现有分类相对顺序，分类 manualFields 保护明确的人工修改字段。

## 卡片归属与内容验收

整理以找回工作和成果为目标，确认用途、归属、来源、版本关系和文件入口即可。读取必要内容，不主动开展剧情、字幕、翻译或代码质量审校，也不为编写目录运行原项目全套检查。对话中已有的未解决问题照实保留；发现文件不同可保留版本入口，不展开业务细节。用户要求版本对比或审校时才进行对应检查；只读取局部时说明范围，不把局部发现写成完整差异清单。

整理一段资料时，先从用户要求与相关正文确认“对象是什么、要完成什么”，再查询已有卡片及其来源，决定补充还是新建。标题、目录名和文件格式只作线索，不能代替这一步；同一对话可以有多件工作，同一工作也可能跨多个对话。

同一对象、同一工作目的默认补充已有卡片。翻译、导出、校对、修订及不同语言版本通常归在这项工作的详情和成果中；单独交付一个文件不构成拆卡理由。只有对象或用途独立、可以单独理解和找回时才另建卡片，必要时关联所属工作。可复用工具与使用它完成的制作分别记录。

名称应让用户认出具体工作，摘要说明目的。例如“老头乐字幕制作”聚合中文字幕、英文翻译和后续导出；确有必要单列时仍写明“《老头乐》英文字幕翻译”并关联主卡片。格式、数量和处理步骤放进详情。摘要用一句日常用语说明在做什么；详情优先引用已有文档，只补继续工作必需的决定和待续事项，不逐卡片扩写长篇历史。

保存前按实际内容核对：名称能否识别对象与工作；是否把同一件事拆散，或仅因同一对话而误合并；摘要是否表达目的；文件、版本、来源是否放在正确工作下。代码校验通过不能替代这些内容判断。

工作归属与文件版本分别处理。归属已明确时，将待核对的文件留在该工作内，说明具体版本疑点；归属不明时保留线索并标明待核对，不凭格式独立建卡，也不编造作品名。合并卡片时沿用主卡片 ID，保留文件、版本疑点和来源，修正相关引用；检查已打开旧卡片的页面能正常更新。

历史整理先读 `record` 获取 `revision`，再用 `saveRecord` 提交完整记录；日常维护使用增量表单，不提交整份记录。保留 `manualFields`，保存失败明确说明。

## 更新与每周检查

每个项目固定一条管理对话，以 record.json 的 maintenanceThreadId 绑定。手动更新与每周唤醒复用该对话，同一时间只执行一个维护任务；完成后保留，仅归档、删除或用户明确更换时新建。

目标是让用户能找回已经做过的工作。每个项目的独立周检只维护本项目，错峰运行。定时任务调用本项目 `prepareBatch --maintenance-thread current`，登记维护会话并取得完整待整理清单；手动更新遵守相同的完整性要求。`noChanges` 时不改项目记录，直接结束。

待整理范围包括已整理 commit 之后的新提交、发生变化的未提交文件、已登记成果的变化，以及所有未覆盖的对话。对话不按创建时间或项目基线日期排除。没有标记已查看的旧对话也必须处理。

一次更新完成本次清单。可以分段读取、按主题聚合、逐步保存，已保存的成果立即供页面读取；分段不能成为主动停止的理由。没有每次提交数、对话数、文件数或用时的完成配额。避免同时处理多个项目，优先读取变更摘要和相关内容，已经整理过的部分不重复全量阅读。

- `prepareBatch` 返回 `baseline`、`targetHead`、`head`、`batchId`、`initialReview`、清单路径与各类数量，不把巨大清单塞进一条消息。用 `reviewScope` 按类型与 offset 读取，直到每类 `nextOffset` 为 null；分页只控制读取，不缩小本次任务范围。对话优先读取 `reviewedUntil` 之后的消息；该值为 0 时尚未查看，按实际内容整理。必要时只回看相关背景。
- 对话正文使用 `reviewThread`，提供 batchId、threadId 和 offset，按 nextOffset 接续读取；每页保留完整连续文本，避免反复自写提取脚本或只截每条消息的开头与结尾。必要的长文档按章节读取，明确已读范围。
- `reviewedThreads` 只登记实际查看过的对话，使用清单提供的 `updated_at`。不能用当前时间替代，以免遗漏执行期间的新消息。
- 全部处理完成后调用 `checkpoint`，提供 `batchId`、`complete: true`、本次 `head` 作为 `expectedHead`、保存后的 `expectedRevision`。未完成不能推进整理位置，也不能将任务标为完成。返回的 recordRevision 是更新整理点后的新版本；后续写入先读最新记录。已整理位置保存在 `reviewState`，由工具维护，Agent 不手工改写。整理期间出现的新提交会留在待处理范围。
- 出现真实阻塞时保留已保存记录，明确剩余内容和具体原因。上下文压缩或分段处理后继续接续本次工作，不把余项安排到下一周。
- 检查点只提交项目记录及其忽略规则，不包含其他暂存工作，不自动 push。

从页面更新启动的任务，完整处理清单后用提供的 jobId 调用 `finishMaintenance`；确实阻塞则标记 `state: failed` 并说明剩余事项。维护对话不建立为业务卡片。整理完成、无变化或失败时均保留维护线程，由用户手动归档。维护线程身份继续登记，用于排除业务卡片和业务增量。日常业务对话不因更新记录而归档，也不需要维护任务状态。

日常 coverage 的资源快照更新不改变批次基线；完成批次时仍使用原 batchId。旧批次校验失效而确需重新获取清单时，读完替代清单并完成 checkpoint 后，可在原任务的 finishMaintenance 请求中传 `completedBatchId`。工具核对当前检查点、相同目标 HEAD、原对话覆盖位置和文件范围，再保存原批次与替代批次的关联；未覆盖原范围不能完成。

## 成果缺口补漏

手动更新和独立周检的 prepareBatch 同时生成 deliveryGaps，包含未登记的对话交付、文件失效和缺少来源。这一步不受 reviewedThreads 的已读标记限制。程序复用按会话文件变更缓存的交付清单，不重复全量阅读已处理正文。

用 reviewScope 的 kind=deliveryGaps 读取本批缺口；也可用 reviewDeliveryGaps 单独检查当前项目。沿 gap 的 cardId、threadId、assetId 和来源定位具体工作：登记遗漏交付用 registerDelivery，已登记的资源缺少来源则补 origin，旧路径失效时查相关对话的生成路径或后续版本。优先处理最新成果的缺口，不重新审校剧情或生产成果。

确认只是引用材料或已登记的相同成果时，用 resolveDeliveryGap 记录 reference 或 duplicate，后者须提供已有 cardId/resourceId；确实无法找回时记录 unavailable。必须给出具体 reason 和本次 gap signature、expectedRevision。文件存在的未归卡成果不能用 unavailable 跳过。无法找回项仍保留可见说明与来源；证据未变时不反复要求同一次处理，有新文件或线索时会重新进入清单。

登记或补好入口后缺口自动消失。提交 checkpoint 前，本批每个缺口需已修复或已有明确处理结论；“对话已读、文件列表已遍历”不能替代这一步。不要宣称所有历史资料绝无遗漏；报告本批补回项和未找回项。新项目不单独做历史迁移，只维护当前工作；旧项目首次启用此方法时补现存缺口。

## 新项目导航接入

首次建立仓库与导航时，记录保存后还需完成项目身份接入。Codex 桌面 `list_projects` 返回的 projectId 与资料库 projectId 可能不同；以实际项目绝对路径匹配，不按名称猜测，也不将一种 ID 当成另一种 ID。

1. 调用桌面 `list_projects`，按项目路径取得桌面 projectId；通过本 Skill 的 CLI `record` 取得同一路径的资料库 projectId。
2. 核对本 Skill 真实目录下 `../../data/projects.json`。按规范化绝对路径查找本项目；缺少时补充本项目的 id、name、path，沿用资料库 ID。保留其他登记与已有字段，并将桌面 ID 写入本项目的 desktopId。两种 ID 相同时无需额外映射。
3. 用桌面 ID 调用项目导航 `read_navigation`，确认返回同一项目路径及已保存的目录、卡片；再以同一个桌面 ID 调用本地 API 的 openNavigation 打开入口。若运行服务尚未加载映射，只重新接入 `local.codex.project-library`，保持 Codex 与聊天运行。
4. 登记、读取或打开失败时，保留具体错误与实际请求 ID，继续定位责任层；不将“请刷新项目列表”提示当成根因或修复方案。后台检查通过只证明身份解析和打开请求通过，实际页面显示须经桌面检查或用户确认；未确认时记录“桌面显示待确认”。

此步骤只处理当前新项目的登记与入口，不扩大为全部项目维护。全新项目未完成身份接入时，不宣称导航已可用。

## 首次整理与周检接入

首次整理与更新使用同一个 `prepareBatch` 入口。缺少 Git 和记录时工具会初始化；`initialReview: true` 时还提供 initialFiles，包含未忽略的已有文件。旧版只有样本或未保存完整覆盖状态的项目，也会提供 initialFiles 补齐清单。先按目录和已有关联确认覆盖范围；已有成果和文档可复用，不逐行重审所有代码，也不重复生产。结合已有对话与成果组织目录，不重跑原生产流程。读取所有必要分页，覆盖本次范围后，用同样的 batchId / complete / expectedHead / expectedRevision 调用 checkpoint。首次或更新都不能在没看完时标记完成。

首次基线建立后，调用 `automationPlan`。如果 `needsCreate` 和 `needsUpdate` 均为 false，保留已有任务。否则用返回的完整 arguments 调用原生 automation_update，把 heartbeat 绑定到固定管理对话，保留原时间、暂停状态。更换管理对话后重新调用 automationPlan 并改绑，不能创建独立 cron 聊天。创建成功后读最新 record，用 `linkAutomation` 登记返回的 automationId；它会校验归属并提交记录。不手写 Codex 自动化配置文件。新项目独立周检的接入已由本系统工作约定授权，无需再让用户逐个安排。

工具不可用或配置失败时明确保留“周检未接入”的状态，不把创建请求当成已成功运行。定时任务不创建新的定时任务；已存在的暂停任务也不自动恢复。

## 成果登记与采用

成果按实际交付时间从新到旧展示，即使收录不全也优先展示已找到的新成果。选用和时间排序独立；不能把“最新交付”当成“已定稿”。已知更晚成果尚未找回时，明确缺失及来源，不把旧版称为最新。

读取对话时同时核对工具交付的成果。reviewThread 首页附带 assets 和 assetCount；使用 reviewAssets 按 threadId / offset 读取完整成果清单，包括 Codex 生成目录中的图像。对于已整理但漏附件的旧对话也要补查，不因 reviewedThreads 已登记而跳过此次成果补漏。registerDelivery 按 threadId、assetId、cardId、expectedRevision 登记经过来源校验的交付，并保留 origin（threadId/turnId/itemId）和 deliveredAt。文件不在项目目录不是遗漏它的理由。

每项已识别交付都应有预览/文件入口及来源消息。历史版本同样保留入口；找不到文件则标明缺失并保留来源。完成验收对照实际交付与卡片入口，不以“文件清单全部归类、对话已读”替代。只需核对相关交付，不扩展到内容质量审校。

文件名称说明内容与用途，不使用目录路径、点号或格式充当名称；group 仅用于同一成果不同格式，不按存放目录合并。README、manifest 等通用文件名应根据实际内容补充用途。辅助文件不需要用户逐个确认。

默认遵守 Git 忽略规则，不扫描缓存、依赖和密钥。明确需要保留的项目外成果，用 `registerResource` 登记单个文件，提供 cardId、path、expectedRevision；仅在用户已提供或明确选定该文件时传 external=true。外部入口保存在同一份记录，不授予整个外部目录访问范围。不要直接改写 externalFiles。

用户确认采用后调用 `adoptResource`，绑定当前文件内容指纹；取消选用传 adoption=review。仅 role=result 提供选用，说明、来源清单、制作过程等辅助文件使用 process。选用可以多选，不改变时间排序，也不自动隐藏其他版本。同名文件覆盖后会显示待确认，旧版采用事实保留。不要自行把未确认结果标为采用，也不要手改 acceptedFingerprint。历史资料不是新的操作授权。

## 命令

```sh
python3 CLI_PATH record --project PROJECT_PATH
python3 CLI_PATH prepareBatch --project PROJECT_PATH
# 独立周检任务使用：
python3 CLI_PATH prepareBatch --project PROJECT_PATH --maintenance-thread current
python3 CLI_PATH reviewScope --project PROJECT_PATH --json '{"batchId":"...","kind":"pendingThreads","offset":0}'
python3 CLI_PATH reviewThread --project PROJECT_PATH --json '{"batchId":"...","threadId":"...","offset":0}'
python3 CLI_PATH reviewAssets --project PROJECT_PATH --json '{"threadId":"...","offset":0}'
python3 CLI_PATH registerDelivery --project PROJECT_PATH --json '{"threadId":"...","assetId":"...","cardId":"...","expectedRevision":"..."}'
python3 CLI_PATH reviewDeliveryGaps --project PROJECT_PATH
python3 CLI_PATH resolveDeliveryGap --project PROJECT_PATH --json '{"gapId":"...","signature":"...","status":"unavailable","reason":"具体线索与未找到的结果","expectedRevision":"..."}'
python3 CLI_PATH saveRecord --project PROJECT_PATH --json - < update.json
python3 CLI_PATH checkpoint --project PROJECT_PATH --json '{"batchId":"...","complete":true,"expectedHead":"本批head","expectedRevision":"保存后revision","message":"docs: update project records"}'
```

reviewScope 的 kind 为 commits、pendingThreads、workingTree、changedResources、initialFiles 或 deliveryGaps。

记录格式见 [记录字段](references/record-format.md)。`revision` 仅用于并发校验；Git 是内容版本来源，batchId 标识本次完整待处理范围。
