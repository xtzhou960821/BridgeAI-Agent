# BridgeAI-Agent Architecture White Paper

# 第七章 Memory 与项目上下文设计

| 项目 | 内容 |
|---|---|
| 文档名称 | BridgeAI-Agent Architecture White Paper |
| 章节 | 第七章 Memory 与项目上下文设计 |
| 版本 | V1.0 |
| 状态 | 正式版 |
| 适用范围 | 桥梁与道路巡检 AI Agent |
| 默认开发环境 | Mac Studio / Apple M3 Ultra / 512GB 统一内存 |
| 权威记忆存储 | PostgreSQL（本地部署） |
| 语义检索 | Qdrant 独立 Memory 集合或等价受控索引 |
| 对象存储 | MinIO 或兼容 S3 的受控对象存储 |
| 编制日期 | 2026-07-29 |

---

## 7.1 本章目标

本章定义 BridgeAI-Agent 的 Memory 与项目上下文架构，包括记忆分类、作用域、来源、候选提取、确认发布、检索排序、上下文压缩、权限隔离、生命周期、遗忘机制、服务协议和评测要求。

Memory 的目标不是让大语言模型无限保留对话，而是让 Agent 在桥梁与道路巡检任务中持续获得范围正确、来源明确、版本有效、权限允许、可以更正的项目上下文。

本章重点解决以下问题：

1. 当前任务的阶段摘要、关键 Tool 结果和人工复核如何在中断后继续使用；
2. 同一桥梁或道路项目的术语、构件别名、报告规则和经确认修订如何跨任务复用；
3. 用户与组织偏好如何继承、覆盖、撤销，并避免覆盖系统安全策略；
4. 哪些内容可以自动形成候选记忆，哪些内容必须绑定业务事实或人工确认；
5. 如何区分 Memory、LangGraph Checkpoint、Workflow State、RAG 和业务数据库；
6. 如何通过作用域、权限、状态和风险过滤防止跨项目泄漏及错误记忆召回；
7. 如何在有限 Token 预算内完成检索、去重、压缩、裁剪和上下文清单记录；
8. 如何处理来源冲突、人工更正、过期、撤销、项目归档和删除传播；
9. 如何建立可量化、可回归、可审计的 Memory 评测与实施基线。

本章的最终产出是 BridgeAI-Agent 第一阶段 Memory Service 和 Context Builder 的工程设计基线，而不是某个记忆框架的使用说明，也不是完整数据库物理设计。

## 7.2 Memory 的定位与职责边界

BridgeAI-Agent 中的 Memory 是一个受作用域、来源、权限、风险和生命周期约束的上下文服务。

其正式定位为：

> 从当前任务、同一项目、用户与组织配置以及经验证的运行经验中，选取对当前节点有用的上下文，在不复制权威业务事实、不替代工程证据的前提下，为 Agent 提供可追溯、可修订、可遗忘的 Context Pack。

Memory 不直接执行病害识别、裂缝测量、构件定位或统计计算；这些工作仍由专业 Tool 完成。Memory 也不决定正式技术状况等级、处治方案、设备控制和报告签发；这些高风险动作由确定性策略、业务服务和人工复核控制。

### 7.2.1 五类状态与知识能力的区别

| 能力 | 保存对象 | 典型问题 | 权威来源 | 主要章节 |
|---|---|---|---|---|
| LangGraph Checkpoint | thread 范围内的图状态快照和待处理写入 | “该线程从哪个节点恢复？” | Checkpointer 内部状态 | 第五章 |
| Workflow State | 当前运行所需字段、结果标识、错误和复核状态 | “本次任务还缺哪个步骤？” | Checkpoint 与 Workflow 业务表 | 第五章 |
| Memory | 任务摘要、项目上下文、偏好、修订和运行经验 | “该项目上次确认了哪套构件命名？” | Memory 权威记录及来源引用 | 本章 |
| RAG | 规范、标准、指南、案例和项目知识片段 | “该类病害需要引用哪些条款？” | 已发布知识版本与 Evidence Pack | 第六章 |
| 业务数据 | 桥梁、道路、构件、病害、检测、报告和复核记录 | “本次检测发现多少处裂缝？” | PostgreSQL 业务表 | 第八章 |

Checkpoint 可以帮助同一 thread 恢复，但不能替代跨 thread 项目记忆。项目记忆可以保存“构件编码 A-03 在本项目报告中显示为 3 号横隔板”的已确认映射，但构件本身的几何、类型和检测记录仍从业务数据读取。

RAG Evidence Pack 可以成为 Memory 的来源引用，但规范正文和条款状态继续由 RAG 管理。当 Agent 再次需要工程依据时，应按当前权限、版本和适用范围重新读取 RAG 证据，不把旧摘要视为仍然有效的规范条款。

### 7.2.2 责任矩阵

| 组件或角色 | 负责 | 不负责 |
|---|---|---|
| Agent | 表达当前任务意图、使用 Context Pack、提出低风险候选、解释冲突并决定是否追问或送审 | 直接读写记忆表、绕过权限、把记忆当成工程证据 |
| Memory Manager | 分类候选、调用 Memory Service、管理反馈和更正流程 | 自行确认高风险项目事实 |
| Context Builder | 建立作用域、调用检索、执行预算与压缩、生成 Context Manifest | 修改权威记忆、把被裁剪内容悄然写回 |
| Policy Engine | 校验操作权限、风险门、确认门和可调用能力 | 生成自然语言摘要或执行语义检索 |
| Workflow | 产生受控事件、保存结果标识、安排确认、补偿和人工复核 | 在 State 中长期保存完整项目历史 |
| Memory Service | 权限过滤、读写契约、状态迁移、版本、审计、检索和删除编排 | 决定病害等级或处治方案 |
| 业务服务 | 提供桥梁、构件、病害、检测和复核等权威事实 | 保存对话摘要和用户表达偏好 |
| RAG Service | 提供带版本、定位和权限的外部知识证据 | 保存用户偏好或线程进度 |
| PostgreSQL | 保存权威记忆、来源关系、权限、状态、版本和审计 | 保存大体积对话归档或充当语义检索的唯一实现 |
| 语义索引 | 在已授权作用域内提供相似记忆候选 | 充当权限、版本和删除状态的唯一权威源 |
| MinIO | 保存长文本快照、归档和大体积 Context Artifact | 保存状态机和授权关系 |
| 人工复核者 | 确认或否定高风险候选、处理冲突、批准跨项目经验发布 | 人工审批每一条低风险显式偏好 |

### 7.2.3 四条强制边界

1. **事实边界：** 项目记忆保存摘要和稳定引用，不复制桥梁、构件、病害、检测和报告业务事实。
2. **证据边界：** Memory 可以提示既往做法，但不能替代规范原文、检测数据和正式签发记录。
3. **执行边界：** Memory 结果不能直接触发正式评定、处治决策、设备控制或报告签发。
4. **恢复边界：** Checkpoint 负责 thread 状态恢复；Memory 负责经治理的跨步骤、跨任务和跨项目周期上下文。

### 7.2.4 与后续章节的关系

- 第八章定义 Memory 相关实体的完整 PostgreSQL Schema、索引、约束和迁移；
- 第九章定义 Memory 能力通过 MCP 暴露时的工具和资源规范；
- 第十章定义 Context Pack 进入 Prompt 后的消息分层和结构化输出；
- 第十一章定义记忆查看、更正、撤销、确认和审计页面；
- 第十二章定义摘要模型、Embedding 模型和相关评测生命周期；
- 第十三章定义生产部署、密钥、网络、备份、监控和安全基线。

## 7.3 典型巡检应用场景

### 7.3.1 同一桥梁多期巡检

某桥每年开展定期检查。不同批次影像、设备、检测班组和模型版本可能变化，但项目中的构件别名、拍摄分区、报告章节和既往人工修订需要持续复用。

| 项目 | 设计 |
|---|---|
| 触发事件 | 新建同一资产的巡检任务 |
| 召回内容 | 构件别名、项目术语、报告规则、已确认历史修订、既往失败模式 |
| 权威来源 | 项目配置、业务实体 ID、人工复核、已签发报告 |
| 自动化程度 | 自动召回；新增项目事实只生成候选 |
| 人工复核点 | 构件映射变化、历史结论与本次数据冲突、处治状态变化 |

Memory 只提供“如何理解和处理这个项目”的上下文。历史病害数量、坐标、量测和处治状态必须实时查询业务数据。

### 7.3.2 任务中断恢复与跨班组交接

无人机影像处理可能持续数小时，任务也可能在人工复核处等待数天。交接班人员需要快速了解任务目标、已完成步骤、异常、关键 Tool 结果和未决事项。

| 项目 | 设计 |
|---|---|
| 触发事件 | 阶段完成、Interrupt、重试耗尽、人员交接 |
| 召回内容 | 阶段摘要、关键结果引用、人工复核状态、未决事项、降级原因 |
| 权威来源 | Workflow 事件、ToolResult、workflow_reviews、Checkpoint 标识 |
| 自动化程度 | 可自动生成任务摘要候选，经确定性字段校验后启用 |
| 人工复核点 | 摘要与 Workflow State 不一致、关键结果缺失或来源不可读 |

恢复执行仍以 Checkpoint 和 Workflow 业务状态为准。任务记忆用于解释和交接，不能改变恢复节点。

### 7.3.3 人工修订复用

人工复核者纠正了构件定位、病害术语、重复病害合并或报告表达。后续同项目任务应优先看到这一修订，避免重复犯错。

| 项目 | 设计 |
|---|---|
| 触发事件 | workflow_reviews 完成或签发报告形成修订 |
| 召回内容 | 修订前后值、适用对象、原因、确认者、有效期和来源 |
| 权威来源 | 人工复核记录、业务记录版本、签发报告 |
| 自动化程度 | 复核事件自动形成候选；通过作用域和字段校验后发布 |
| 人工复核点 | 修订试图跨项目生效、与新业务事实冲突、适用范围不明确 |

人工修订的优先级高于模型自动摘要，但仍受有效期、项目作用域和最新业务事实约束。

### 7.3.4 报告与交付偏好继承

不同项目可能采用不同模板、单位、命名、图表样式和复核流程。用户也可能有个人显示偏好。

| 项目 | 设计 |
|---|---|
| 触发事件 | 用户明确保存偏好、项目配置发布、组织默认值更新 |
| 召回内容 | 报告模板 ID、单位制、文件命名、术语、通知和显示选项 |
| 权威来源 | 用户明确操作、项目配置、组织配置 |
| 自动化程度 | 低风险显式偏好可以直接生效；系统推断只生成候选 |
| 人工复核点 | 偏好影响复核阈值、数据范围、签发流程或安全策略 |

系统安全策略、强制复核、权限和法规约束不得被任何偏好覆盖。

### 7.3.5 模型、设备与 Workflow 运行经验

同一模型在夜间、逆光、雨雾、特定桥型或特定相机上可能表现不同。系统可以记录经过评测确认的适用性与失败模式，辅助 Tool Router 和人工风险判断。

| 项目 | 设计 |
|---|---|
| 触发事件 | 离线评测发布、真实任务复盘、故障分析结论确认 |
| 召回内容 | 模型版本、设备、环境、适用范围、已知失败、推荐补充检查 |
| 权威来源 | 评测报告、故障单、人工复盘 |
| 自动化程度 | 评测任务生成候选；由模型管理员或领域负责人确认 |
| 人工复核点 | 经验影响生产模型选择、高风险病害或跨项目发布 |

运行经验只能调整候选排序、模型路由或风险提示，不得作为桥梁状态和病害结论的证据。

### 7.3.6 项目归档、撤权与删除

项目结束、成员离组、合同保留期变化或用户提出删除请求时，系统需要停止不再适用的记忆召回，并清理派生内容。

| 项目 | 设计 |
|---|---|
| 触发事件 | 项目归档、角色撤销、保留策略到期、删除申请批准 |
| 处理对象 | 权威记忆、对象快照、语义索引、缓存、派生摘要 |
| 权威来源 | 项目状态、权限事件、保留策略和删除工单 |
| 自动化程度 | 立即停止召回；后台执行可重试清理 |
| 人工复核点 | 法定或合同保留冲突、共享来源仍被其他项目使用 |

清理未完成时，目标记忆必须保持不可召回。必要审计只保留不含原文的最小墓碑。

## 7.4 设计原则

### 7.4.1 Source Before Memory

每条可用记忆必须知道来自哪里。高风险项目事实必须关联业务数据、人工复核或签发报告；没有来源的模型陈述只能留在候选或隔离状态。

### 7.4.2 Candidate by Default

自动提取、模型总结和运行归纳默认创建候选记忆。只有通过对应风险门、权限校验和确认流程的内容才能进入 active。

### 7.4.3 Permission Before Recall

组织、项目、用户、角色和敏感级别过滤必须在语义召回前执行。不得先召回越权候选，再依赖模型隐藏。

### 7.4.4 Structured Fact First

可由稳定字段表达的资产 ID、构件 ID、版本、数值、单位、时间和状态，优先以结构化字段或业务引用传递；自然语言摘要只用于解释。

### 7.4.5 Scope Isolation

任务、项目、用户、组织和系统作用域必须显式存在。默认禁止跨项目共享；跨项目经验经脱敏、审批后发布到组织级运行经验。

### 7.4.6 Immutable Revision

已发布记忆不原地覆盖。更正产生新版本、替代关系和审计事件，使历史任务能够恢复当时使用的上下文。

### 7.4.7 Budgeted Context

上下文按节点和模型预算构建。系统规则、权限、安全边界和当前目标优先保留；低价值历史和重复摘要可以裁剪。

### 7.4.8 Explicit Forgetting

保留、归档、撤销、失效、墓碑和删除是正式生命周期状态。删除不仅是数据库操作，还必须传播到索引、缓存、Artifact 和派生摘要。

### 7.4.9 Local First

项目数据、记忆内容、Embedding 和摘要默认在受控本地环境处理。若使用外部服务，必须经过数据分类、脱敏、授权和审计。

### 7.4.10 Auditable by Default

每次写入、确认、召回、裁剪、压缩、更正、撤销和删除都产生可关联事件。仅保存最终 Prompt 而不保存 Context Manifest，不能满足本系统的审计要求。

### 7.4.11 Graceful Degradation

Memory 故障不能迫使系统绕过权限或伪造上下文。系统应退化为 Workflow State、权威业务数据和 RAG，并将缺少项目记忆显式传递给 Agent 或人工复核者。

## 7.5 记忆分类、作用域与风险分级

### 7.5.1 记忆类型

| 类型 | 主要内容 | 默认作用域 | 可否直接作为工程证据 |
|---|---|---|---|
| 任务记忆 | 阶段摘要、结果引用、人工复核、未决事项、降级原因 | task | 否 |
| 项目记忆 | 术语、构件别名、报告规则、已确认修订、项目特殊约束 | project | 否，需回到来源 |
| 用户与组织偏好 | 语言、单位、模板、命名、通知和显示选项 | user / organization | 否 |
| 运行经验记忆 | 模型适用性、失败模式、Tool 组合和 Workflow 经验 | project / organization / system | 否 |

规范、标准、病害知识和处治案例不作为 Memory 类型，继续由 RAG 管理。第三章中的“领域记忆”在本章收敛为：可引用的行业知识进入 RAG；经评测确认的模型经验、错误模式和标注经验进入运行经验记忆。

### 7.5.2 作用域

| 作用域 | 主键 | 典型内容 | 默认可见范围 |
|---|---|---|---|
| task | task_id | 本次任务阶段摘要和未决事项 | 当前任务授权成员 |
| project | project_id | 项目术语、报告规则和确认修订 | 当前项目授权成员 |
| user | user_id | 用户明确偏好 | 用户本人及受控服务 |
| organization | organization_id | 组织模板和经审批经验 | 组织内获授权角色 |
| system | system namespace | 全局安全策略和已发布运行基线 | 受控系统组件 |

一个 MemoryRecord 只能有一个主作用域，但可以携带 organization_id、project_id、task_id 和 user_id 作为过滤维度。主作用域决定其生命周期和默认继承方式。

### 7.5.3 作用域继承

普通偏好按以下顺序解析：

```text
系统强制策略
   ↓ 不可覆盖
当前任务明确指令
   ↓
项目配置
   ↓
用户偏好
   ↓
组织默认值
   ↓
产品默认值
```

当前任务指令可以覆盖报告语言等普通项目配置，但不能覆盖系统安全策略、项目数据权限、强制人工复核和正式交付约束。出现同级冲突时不按最近时间盲目覆盖，而是根据配置版本、来源权威性和人工确认状态处理。

### 7.5.4 风险分级

| 等级 | 示例 | 发布要求 | 使用限制 |
|---|---|---|---|
| low | 显示语言、列表排序、用户明确选择的导出格式 | 明确用户操作或规则校验 | 不得影响权限和安全 |
| medium | 报告章节、项目术语、单位制、任务摘要 | 来源绑定和确定性校验 | 冲突时提示或回退 |
| high | 构件别名映射、模型适用性、项目复核规则、历史修订 | 权威来源或人工确认 | 使用时显示来源和版本 |
| critical | 正式等级、处治结论、签发状态、设备控制授权 | 不作为普通 Memory 自动发布 | 只能引用权威业务记录并强制复核 |

风险等级由内容类型、来源、作用域和潜在影响共同决定，不由模型置信度单独决定。critical 信息原则上只保存权威记录引用和必要摘要，不保存可被 Agent 误当成执行指令的自由文本。

### 7.5.5 敏感级别

风险表示“内容错误会造成多大影响”，敏感级别表示“内容泄漏会造成多大影响”。两者分别建模。项目内部资料、人员信息、未签发报告和安全缺陷可以具有不同敏感级别，即使其业务风险较低也必须执行访问控制和日志脱敏。

## 7.6 总体架构

BridgeAI-Agent Memory 由事件采集、候选处理、权威存储、检索索引、上下文组装、治理控制和审计观测组成。

```text
用户明确操作／Workflow 事件／ToolResult／人工复核／报告签发／评测发布
                               │
                               ▼
                    Memory Event Collector
                               │
                               ▼
     ┌──────────────── Candidate Processing Pipeline ────────────────┐
     │ 分类 → 作用域 → 去重 → 风险 → 来源绑定 → 校验 → 确认／隔离 │
     └───────────────────────────┬────────────────────────────────────┘
                                 │
                   ┌─────────────┼─────────────┐
                   ▼             ▼             ▼
             PostgreSQL        MinIO       Outbox / Index Worker
             权威记录与审计     Artifact            │
                                                   ▼
                                         Memory Semantic Index
                                           与 RAG 集合隔离
                                                   │
                          ┌────────────────────────┘
                          ▼
         Policy Engine → Memory Service → 结构化检索／语义召回
                          │
                          ▼
                   Context Builder
         权限 → 排序 → 冲突检查 → 预算 → 压缩 → Manifest
                          │
                          ▼
                 Agent / Workflow Node
                          │
                          ▼
              Tool / RAG / Human Review
                          │
                          └──→ 反馈、更正、撤销、遗忘
```

### 7.6.1 核心组件

| 组件 | 输入 | 输出 | 关键约束 |
|---|---|---|---|
| Memory Event Collector | Workflow、Tool、复核、用户和评测事件 | 标准 MemoryEvent | 只采集白名单事件，不保存全部原始对话 |
| Candidate Extractor | MemoryEvent 和允许的上下文 | 候选内容、类型、作用域和来源 | 模型只能提出 candidate |
| Validator | 候选、来源、权限、业务记录 | 校验结果和风险门 | 高风险来源缺失时阻断 |
| Memory Service | 结构化读写请求 | MemoryRecord 或操作结果 | 状态迁移和审计唯一入口 |
| Index Worker | 已提交的 Outbox 事件 | 索引增删改结果 | 幂等、可重放、可重建 |
| Retrieval Engine | 授权过滤和查询 | 候选记忆 | 过滤先于语义检索 |
| Context Builder | 当前节点、预算、候选记忆 | ContextPack 和 ContextManifest | 不修改权威记忆 |
| Policy Engine | 操作者、作用域、动作和风险 | allow / deny / review | 权限异常默认拒绝 |
| Audit & Evaluation | 全链路事件和样例标签 | 审计记录、指标和回归结果 | 不记录不必要敏感正文 |

### 7.6.2 写入路径

1. Collector 只接收登记过的事件类型，并为事件分配 event_id、trace_id、organization_id 和发生时间。
2. Candidate Extractor 生成候选内容、结构化事实、建议作用域、风险等级和来源引用。
3. 系统执行作用域校验、权限校验、敏感级别识别、内容哈希、重复检测和提示注入检测。
4. Validator 根据记忆类型和风险决定规则确认、人工确认、拒绝或隔离。
5. Memory Service 在 PostgreSQL 事务内写入 MemoryRecord、来源关系、状态事件和 Outbox。
6. 大型快照先按受控对象键写入 MinIO，再将 artifact_id、version_id 和哈希写入权威记录。
7. Index Worker 消费事务提交后的 Outbox，更新独立 Memory 索引；失败可重放，不回滚已经合法发布的权威记录。

### 7.6.3 读取路径

1. Context Builder 根据 task_id、project_id、user_id、organization_id、当前节点和风险目标构造查询。
2. Policy Engine 生成不可由模型修改的授权过滤条件。
3. Memory Service 先读取 PostgreSQL 中可召回状态和精确匹配，再按需调用语义索引。
4. Retrieval Engine 对候选执行版本折叠、去重、排序、冲突和来源可用性检查。
5. Context Builder 按预算保留结构化事实、关键摘要和来源引用，生成 ContextPack。
6. ContextManifest 保存本次查询、候选、使用、裁剪、压缩、版本和哈希，用于复现。

### 7.6.4 反馈路径

Agent 不直接修改记忆。用户、复核者或 Workflow 通过结构化反馈表达 accepted、ignored、corrected、rejected 或 reported。更正创建新版本；否定产生负向记录；越权或污染报告进入隔离和安全事件流程。

### 7.6.5 控制面与数据面

控制面负责 Schema、记忆类型、风险规则、权限策略、确认门、保留策略、索引版本、Embedding 配置、压缩策略和评测版本。

数据面负责事件采集、候选处理、记忆读写、检索、Context Pack 构建、反馈和审计。普通 Agent 和 Tool 只能调用被授权的数据面接口，不能修改控制面配置。

### 7.6.6 LangGraph 适配边界

LangGraph 当前将 thread 内状态交给 Checkpointer 持久化，并通过 Store 接口支持跨 thread 的命名空间数据。BridgeAI-Agent 可以使用 PostgresStore 或其他 BaseStore 实现作为框架适配层，但必须在外层保持自己的 MemoryRecord、Policy Engine、版本、审计和删除语义。

框架 Store 的 put、search、TTL 或语义索引能力不能自动证明以下条件已经满足：

- 调用者拥有项目权限；
- 内容具有有效工程来源；
- 记忆已经通过风险确认门；
- 权限撤销和删除已经传播到全部派生物；
- 历史任务可以恢复当时使用的业务版本。

因此，LangGraph Store 是可替换的访问适配，不是 BridgeAI Memory 业务治理的唯一权威实现。

## 7.7 统一记忆对象与数据契约

### 7.7.1 核心 Pydantic 契约

以下示例表达稳定业务语义。完整数据库类型、索引和迁移由第八章定义。

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    TASK = "task_memory"
    PROJECT = "project_memory"
    PREFERENCE = "preference_memory"
    OPERATIONAL = "operational_memory"


class MemoryStatus(str, Enum):
    CANDIDATE = "candidate"
    VALIDATING = "validating"
    REVIEW_PENDING = "review_pending"
    ACTIVE = "active"
    CONFLICTED = "conflicted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    REVOKED = "revoked"
    QUARANTINED = "quarantined"
    TOMBSTONED = "tombstoned"
    DELETED = "deleted"


class MemoryRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MemoryScope(BaseModel):
    scope_type: Literal["task", "project", "user", "organization", "system"]
    scope_id: str = Field(min_length=1)
    organization_id: str = Field(min_length=1)
    project_id: str | None = None
    task_id: str | None = None
    user_id: str | None = None
    namespace: tuple[str, ...]


class SourceRef(BaseModel):
    source_type: Literal[
        "business_record",
        "workflow_event",
        "tool_result",
        "human_review",
        "signed_report",
        "user_action",
        "evaluation_report",
        "rag_evidence",
    ]
    source_id: str = Field(min_length=1)
    source_version: str | None = None
    relation: Literal["supports", "corrects", "supersedes", "derived_from"]
    immutable_hash: str | None = None
    captured_at: datetime


class MemoryRecord(BaseModel):
    memory_id: str
    memory_type: MemoryType
    scope: MemoryScope
    content: str = Field(min_length=1)
    summary: str | None = None
    structured_facts: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[SourceRef] = Field(min_length=1)

    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: MemoryRiskLevel
    validation_status: Literal[
        "unverified",
        "rule_validated",
        "source_verified",
        "human_confirmed",
    ]
    status: MemoryStatus = MemoryStatus.CANDIDATE

    owner_id: str
    visibility: Literal["private", "project", "organization", "system"]
    allowed_roles: list[str] = Field(default_factory=list)
    sensitivity: Literal["public", "internal", "confidential", "restricted"]

    valid_from: datetime
    valid_until: datetime | None = None
    supersedes_id: str | None = None
    retention_policy: str
    deletion_status: Literal[
        "none", "pending", "partial", "complete", "blocked"
    ] = "none"

    embedding_model_version: str | None = None
    index_version: str | None = None
    schema_version: str = "memory-record.v1"

    created_by: str
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None = None
```

### 7.7.2 字段规则

1. memory_id 是不可复用的稳定标识；修订不得沿用原 memory_id。
2. source_refs 至少包含一项。用户偏好也必须关联 user_action 审计事件。
3. confidence 表示候选提取或验证信号，不表示工程事实正确概率，也不替代 risk_level。
4. structured_facts 只放可验证字段，不存密码、访问令牌、原始大文件和任意可执行指令。
5. content 和 summary 受敏感级别控制；日志默认只记录哈希、长度和标识，不复制 restricted 正文。
6. valid_until 为空表示尚无预定失效时间，不表示永久有效；项目归档和来源状态变化仍可使其失效。
7. allowed_roles 是应用层授权输入之一，不替代项目成员关系、RLS 或服务端 Policy Engine。
8. embedding_model_version 和 index_version 只描述派生索引，可为空；权威记忆不依赖向量存在。

### 7.7.3 命名空间

推荐命名空间由系统字段构造：

```text
(organization_id, project_id_or_global, scope_type, scope_id, memory_type)
```

不得把用户输入、项目名称或原始文件名直接拼接为命名空间和对象键。框架适配层可以把该元组映射为 LangGraph Store namespace，但所有读写仍必须经过 Policy Engine。

### 7.7.4 项目记忆示例

```json
{
  "memory_id": "mem_01K1C7M8V6M3Q20D5D6A9X7H4P",
  "memory_type": "project_memory",
  "scope": {
    "scope_type": "project",
    "scope_id": "project_bridge_2026_017",
    "organization_id": "org_001",
    "project_id": "project_bridge_2026_017",
    "task_id": null,
    "user_id": null,
    "namespace": [
      "org_001",
      "project_bridge_2026_017",
      "project",
      "project_bridge_2026_017",
      "project_memory"
    ]
  },
  "content": "本项目报告中，构件编码 HG-03 显示为“3号横隔板”。",
  "structured_facts": {
    "component_id": "component_HG_03",
    "report_display_name": "3号横隔板"
  },
  "source_refs": [
    {
      "source_type": "human_review",
      "source_id": "review_2026_00418",
      "source_version": "2",
      "relation": "supports",
      "immutable_hash": "sha256:...",
      "captured_at": "2026-07-29T14:00:00+08:00"
    }
  ],
  "confidence": 1.0,
  "risk_level": "high",
  "validation_status": "human_confirmed",
  "status": "active",
  "visibility": "project",
  "sensitivity": "internal",
  "schema_version": "memory-record.v1"
}
```

示例省略了部分审计和生命周期字段，仅用于说明项目记忆保存显示映射和来源引用，不复制完整构件业务记录。

### 7.7.5 契约演进

MemoryRecord 的 schema_version 与数据库迁移版本、API 版本和索引版本分别管理。新增可选字段可以向后兼容；改变状态语义、作用域或权限规则必须发布新 Schema 版本并提供迁移、回滚和历史读取策略。

## 7.8 记忆来源与写入触发

## 7.9 候选提取与处理流水线

## 7.10 校验、确认、发布与版本管理

## 7.11 存储、索引与职责分工

## 7.12 检索、过滤、排序与去重

## 7.13 Context Builder 与 Token 预算

## 7.14 上下文压缩与摘要

## 7.15 项目上下文设计

## 7.16 任务记忆设计

## 7.17 用户与组织偏好设计

## 7.18 反馈、冲突、更正与负向记忆

## 7.19 生命周期、保留与遗忘机制

## 7.20 Memory Service/Tool 协议

## 7.21 与 Agent、Workflow 和 RAG 集成

## 7.22 权限、隐私与记忆污染防护

## 7.23 缓存、性能、降级与资源控制

## 7.24 可观测性、审计与异常恢复

## 7.25 评测与测试体系

## 7.26 第一阶段实施范围与架构决策

## 7.27 本章结论

## 参考资料

## 修订记录
