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

Memory 不监听并保存全部会话、日志和中间状态。只有登记在 Memory Event Catalog 中的事件可以进入候选流水线。

### 7.8.1 来源类型

| 来源类型 | 典型对象 | 可形成的记忆 | 默认确认方式 |
|---|---|---|---|
| user_action | 用户点击“保存偏好”、明确更正 | 偏好、术语、显示规则 | 低风险可规则确认 |
| workflow_event | 阶段完成、Interrupt、重试耗尽、任务结束 | 任务摘要、未决事项、降级原因 | 确定性字段校验 |
| tool_result | 检测、测量、GIS、报告 Tool 输出 | 结果引用、运行经验候选 | 不复制结果；高风险需复核 |
| human_review | 复核通过、驳回、修订和签发 | 项目修订、负向记忆、复核规则 | 来源有效时可发布 |
| signed_report | 已签发报告及其数据包 | 报告规则、经确认项目表达 | 绑定报告版本 |
| business_record | 资产、构件、病害或配置变化 | 稳定引用、失效触发 | 业务服务校验 |
| evaluation_report | 模型、设备和 Workflow 评测发布 | 运行经验 | 模型管理员或领域负责人确认 |
| rag_evidence | Evidence Pack 和检索结果 | 查询线索、证据引用 | 不复制规范正文 |

每个来源必须有稳定 source_id。可变对象还必须有 source_version 或不可变哈希。来源不存在、调用者无权访问或版本不可解析时，不得发布关联高风险记忆。

### 7.8.2 事件白名单

第一阶段建议登记以下事件：

| 事件名 | 触发点 | 主要候选 |
|---|---|---|
| memory.preference_saved | 用户明确保存设置 | 用户偏好 |
| workflow.stage_completed | Workflow 稳定节点完成 | 任务阶段摘要 |
| workflow.interrupted | 人工复核或外部条件导致暂停 | 交接摘要和未决事项 |
| workflow.completed | 任务完成 | 任务总结和项目候选 |
| review.completed | 人工复核完成 | 修订、否定和项目规则 |
| report.signed | 正式报告签发 | 报告模板和项目表达 |
| project.archived | 项目归档 | 停止默认召回和保留评估 |
| project.permission_changed | 成员或角色变化 | 缓存失效和权限重算 |
| business.fact_changed | 权威业务事实修订 | 关联记忆重新校验 |
| evaluation.published | 评测结果发布 | 运行经验候选 |
| deletion.approved | 删除申请批准 | 撤销、墓碑和清理任务 |

事件版本必须登记。未知事件版本进入死信或人工处理，不以宽松解析继续写入。

### 7.8.3 写入触发矩阵

| 内容 | 自动候选 | 规则确认 | 人工确认 | 禁止写入 |
|---|---:|---:|---:|---:|
| 用户明确选择的显示语言 | 是 | 是 | 否 | 否 |
| 模型从对话推测的个人偏好 | 是 | 否 | 是，由用户确认 | 否 |
| Workflow 阶段摘要 | 是 | 是，需字段一致 | 异常时 | 否 |
| ToolResult 完整正文或影像 | 否 | 否 | 否 | 是，保存引用或 Artifact |
| 人工复核修订 | 是 | 来源与作用域校验 | 跨项目或冲突时 | 否 |
| 构件业务事实 | 仅生成引用候选 | 否 | 来源冲突时 | 禁止复制为权威副本 |
| 规范条款正文 | 否 | 否 | 否 | 是，由 RAG 管理 |
| 已发布模型失败模式 | 是 | 来源校验 | 是 | 否 |
| 密码、令牌、私钥 | 否 | 否 | 否 | 是 |
| 未签发的 critical 工程结论 | 否 | 否 | 否 | 是 |

### 7.8.4 写入时机

记忆提取不应在每个 Token 或每条日志后运行。推荐在稳定业务边界触发：

- 用户完成明确设置；
- Workflow 进入稳定 Checkpoint 后；
- ToolResult 已持久化并获得 execution_id 后；
- 人工复核事务提交后；
- 报告签发和项目归档后；
- 评测报告正式发布后。

这样可以避免重复提取未完成状态，也便于使用 event_id 和版本建立幂等键。

## 7.9 候选提取与处理流水线

### 7.9.1 状态流转

```text
captured
   ↓
classified
   ↓
deduplicated
   ↓
risk_assessed
   ↓
source_bound
   ↓
validating
   ├──→ rejected
   ├──→ conflicted
   ├──→ quarantined
   └──→ review_pending ──→ active
                 │
                 └──────→ rejected
```

流水线内部步骤可以重试，但业务状态迁移必须由 Memory Service 执行并写入事件记录。Extractor、Embedding Worker 和索引客户端不得自行把候选标记为 active。

### 7.9.2 处理步骤

1. **捕获：** 校验事件类型、版本、签名、组织、项目和操作者。
2. **分类：** 识别记忆类型、主作用域、业务实体、敏感级别和建议风险。
3. **最小化：** 删除无业务价值的寒暄、重复日志和不应长期保存的敏感内容。
4. **提取：** 生成 content、summary、structured_facts 和 source_refs。
5. **去重：** 比较事件 ID、内容哈希、结构化事实、来源和当前有效版本。
6. **风险评估：** 规则优先确定风险下限，模型只能提高风险或建议复核，不能降低强制等级。
7. **来源绑定：** 核对业务记录、ToolResult、Review 或报告是否存在且调用者有权访问。
8. **安全检查：** 将会话、外部文件和模型输出按不可信内容处理，识别提示注入、越权指令和秘密信息。
9. **验证与确认：** 按 7.10 的矩阵进入规则确认、人工确认、冲突、拒绝或隔离。
10. **持久化与索引：** 先提交 PostgreSQL 权威记录，再通过 Outbox 更新派生索引。

### 7.9.3 MemoryProposalInput

```python
from typing import Any, Literal

from pydantic import BaseModel, Field


class MemoryProposalInput(BaseModel):
    event_id: str
    trace_id: str
    task_id: str | None = None
    requested_type: MemoryType
    requested_scope: MemoryScope
    content: str = Field(min_length=1, max_length=16000)
    summary: str | None = Field(default=None, max_length=2000)
    structured_facts: dict[str, Any] = Field(default_factory=dict)
    source_refs: list[SourceRef] = Field(min_length=1)
    proposed_risk: MemoryRiskLevel
    extraction_method: Literal[
        "explicit_user",
        "deterministic_rule",
        "model_extraction",
        "human_review",
        "system_evaluation",
    ]
    extractor_version: str
    schema_version: str = "memory-proposal.v1"
```

客户端不得提交 status、validation_status、allowed_roles、confidence 最终值和发布时间。这些字段由服务端根据权限、来源和确认流程计算。

### 7.9.4 幂等设计

候选幂等键由以下字段规范化后计算：

```text
sha256(
    organization_id
    + primary_scope
    + event_id
    + requested_type
    + extractor_version
    + normalized_content_hash
)
```

同一幂等键重复提交时：

- 已成功：返回现有 memory_id 和状态；
- 正在处理：返回 accepted 和 retry_after；
- 上次失败且可重试：复用原处理记录继续；
- 内容哈希不同：视为事件版本冲突，不覆盖原候选。

### 7.9.5 去重与合并

去重分三层：

1. **精确重复：** 同 event_id、来源、类型和内容哈希，直接复用。
2. **结构化重复：** structured_facts 的业务主键和有效字段相同，折叠为同一版本或更新 last_observed_at。
3. **语义近似：** 只用于发现候选，不自动合并。高风险近似内容必须比较来源和适用范围。

任务阶段摘要可以增量更新候选，但一旦发布为 active，后续修订必须创建新版本。

### 7.9.6 事务与补偿

PostgreSQL 事务包含候选记录、来源关系、状态事件、审计记录和 Outbox。MinIO 与语义索引不参与同一数据库事务：

- Artifact 写入失败：候选不进入 active，并记录可重试任务；
- PostgreSQL 提交成功、索引失败：权威记录保持有效，Outbox 重试；
- 索引成功、后续权限变化：先在 PostgreSQL 使其不可召回，再提交删除或更新事件；
- 补偿多次失败：进入死信，产生告警，不绕过权限继续召回。

### 7.9.7 提示注入隔离

候选提取 Prompt 必须把事件正文标记为数据，不允许其中的自然语言修改系统规则、作用域、风险、Tool 权限或确认状态。疑似“忽略规则”“扩大权限”“调用删除”等指令性内容进入 quarantined，并保存安全标签而不是继续作为上下文传播。

## 7.10 校验、确认、发布与版本管理

### 7.10.1 校验门

候选至少经过以下检查：

| 校验 | 失败处理 |
|---|---|
| Schema 与字段长度 | rejected，返回字段错误 |
| 事件类型和版本 | 拒绝未知版本或进入死信 |
| 操作者权限 | 拒绝且不暴露目标记忆存在性 |
| 作用域完整性 | rejected；project 记忆必须有 project_id |
| 来源存在性和版本 | high/critical 阻断；低风险进入待补充来源 |
| 来源访问权限 | rejected 并记录安全事件 |
| 内容最小化和敏感信息 | 脱敏、隔离或拒绝 |
| 重复和版本关系 | 复用、折叠或创建修订 |
| 与 active 记忆冲突 | conflicted，不自动覆盖 |
| 与权威业务事实冲突 | conflicted 并强制复核 |
| 提示注入和可执行指令 | quarantined |
| 有效期与项目状态 | 过期或归档项目不默认发布 |

### 7.10.2 确认矩阵

| 记忆类型与风险 | 最低确认要求 | 可发布状态 |
|---|---|---|
| 用户明确 low 偏好 | user_action + 权限校验 | active |
| 模型推断的 low 偏好 | 用户明确确认 | active |
| medium 任务摘要 | Workflow 字段比对、来源可读 | active |
| medium 项目术语 | 项目配置或人工确认 | active |
| high 构件映射与历史修订 | 业务记录或 human_review | active |
| high 运行经验 | 已发布评测 + 负责人确认 | active |
| critical 工程结论 | 不作为普通记忆发布；仅保存权威引用 | active 引用记录 |
| 来源冲突或适用范围不明 | 人工处理冲突 | active / rejected |

人工确认操作必须记录 reviewer_id、review_id、前后值、理由、时间和权限快照。确认者不能审批自己无权访问的来源，也不能借确认把项目记忆发布到组织作用域。

### 7.10.3 状态语义

| 状态 | 是否可默认召回 | 说明 |
|---|---:|---|
| candidate | 否 | 已接收但未完成验证 |
| validating | 否 | 正在校验来源、权限、风险和重复 |
| review_pending | 否 | 等待用户或人工复核 |
| active | 是 | 已发布且仍满足权限、有效期和来源要求 |
| conflicted | 否 | 与现有记忆或业务事实冲突 |
| rejected | 否 | 不满足发布条件 |
| superseded | 否 | 已被明确新版本替代 |
| expired | 否 | 超过有效期或适用条件 |
| revoked | 否 | 因权限、安全或人工操作立即停止使用 |
| quarantined | 否 | 疑似污染、越权或安全问题 |
| tombstoned | 否 | 正文已移除或待清理，仅保留最小审计 |
| deleted | 否 | 允许删除的内容和派生物已完成清理 |

只有 active 可以进入普通 Context Pack。诊断和管理界面可在单独权限下查询其他状态，但不得把它们送给普通 Agent。

### 7.10.4 发布事务

发布 active 至少需要在同一 PostgreSQL 事务内完成：

1. 锁定候选当前版本；
2. 重新检查来源、权限和项目状态；
3. 写入最终风险、确认方式和有效期；
4. 如果替代旧版本，将旧版本标记为 superseded；
5. 写入状态事件和审计记录；
6. 写入索引 Outbox；
7. 提交事务。

索引完成不是 PostgreSQL 发布事务的一部分。索引尚未同步时，结构化检索仍可读取 active 记录；语义召回必须等待 index_status 为 ready。

### 7.10.5 版本与替代

每次语义更正创建新 memory_id。版本关系至少支持：

- supersedes：新版本完全替代旧版本；
- corrects：修正旧版本中的明确错误；
- narrows：缩小适用范围；
- extends：补充内容但不否定旧版本；
- derived_from：由多个来源或记忆归纳。

同一逻辑记忆可以使用 memory_family_id 聚合版本。历史 Context Manifest 始终引用具体 memory_id，不自动漂移到最新版本。

### 7.10.6 冲突处理

冲突检测至少比较：

- 相同业务实体和字段出现不同值；
- 相同项目规则具有重叠有效期；
- 人工修订与最新业务事实不一致；
- 不同来源对模型适用性给出相反结论；
- 用户偏好与项目强制配置冲突。

冲突记录保留双方来源、版本、作用域和检测规则。系统不得以 Embedding 相似度、模型投票或“最新创建时间”自动裁决 high/critical 冲突。

### 7.10.7 来源变化传播

业务事实修订、报告撤签、评测撤回、项目权限变化或 RAG 证据失效时，Source Monitor 生成重新校验事件：

- 来源仍有效且内容不受影响：更新检查时间；
- 内容需要修订：创建新候选；
- 来源已撤回：立即 revoke 关联记忆；
- 适用范围变化：expire 原版本并创建窄化候选；
- 无法自动判断：进入 conflicted 或 review_pending。

## 7.11 存储、索引与职责分工

### 7.11.1 存储职责矩阵

| 组件 | 权威职责 | 主要用途 | 不承担 |
|---|---|---|---|
| PostgreSQL | MemoryRecord、来源、权限、状态、版本、反馈、删除任务和审计 | 事务、精确检索、治理和恢复 | 大型归档、唯一语义检索 |
| Qdrant 或等价索引 | 无业务权威职责 | 已授权作用域内的语义候选召回 | 唯一 ACL、版本和删除状态 |
| MinIO | 大型 Context Artifact 的版本化原件 | 长摘要、会话归档、报告附件和导出包 | 状态机、权限关系、排序逻辑 |
| LangGraph Store | 无独立业务权威职责 | 框架节点访问 Memory Service 的适配 | 绕过 BridgeAI Schema 和 Policy |
| LangGraph Checkpointer | thread 状态快照 | Interrupt、恢复、时间旅行和故障恢复 | 跨 thread 项目记忆 |
| Redis | 无业务权威职责 | 短时查询、授权和 Context Pack 缓存 | 长期记忆和删除证明 |
| Workflow State | 当前运行权威快照 | memory_id、摘要和 Manifest 引用 | 完整历史、向量和大文件 |

### 7.11.2 PostgreSQL 概念实体

第八章再给出完整 DDL。本章约定以下代表性实体：

| 实体 | 作用 |
|---|---|
| memory_records | 记忆内容、类型、作用域、风险、状态和有效期 |
| memory_sources | 来源引用、版本、哈希和可用状态 |
| memory_relations | supersedes、corrects、derived_from 等关系 |
| memory_acl_bindings | 项目、角色、用户和敏感级别授权 |
| memory_events | 状态迁移和领域事件 |
| memory_feedback | 接受、忽略、更正、否定和举报 |
| memory_context_manifests | 每次上下文组装的输入、裁剪和哈希 |
| memory_deletion_jobs | 撤销、墓碑和派生物清理进度 |
| memory_outbox | 索引、缓存和生命周期异步事件 |

建议使用独立 bridgeai_memory Schema，与 bridgeai_workflow、知识库和业务 Schema 分离。应用服务角色不得成为表所有者；Row-Level Security 可以作为纵深防御，但不替代应用层授权。

### 7.11.3 语义索引载荷

语义索引只保存召回和过滤所需的最小载荷：

```json
{
  "memory_id": "mem_01K1C7M8V6M3Q20D5D6A9X7H4P",
  "organization_id": "org_001",
  "project_id": "project_bridge_2026_017",
  "scope_type": "project",
  "scope_id": "project_bridge_2026_017",
  "memory_type": "project_memory",
  "status": "active",
  "risk_level": "high",
  "sensitivity": "internal",
  "acl_version": "acl_42",
  "memory_version": "3",
  "valid_from": "2026-07-29T14:00:00+08:00",
  "valid_until": null,
  "index_version": "memory-index.v1"
}
```

organization_id、project_id、scope_type、scope_id、memory_type、status、sensitivity 和 acl_version 应建立适合精确过滤的 Payload Index。索引中不保存密码、令牌、完整 ACL 成员列表和不必要的 restricted 正文。

### 7.11.4 Memory 与 RAG 索引隔离

第一阶段至少使用不同集合：

```text
bridgeai_memory_v1
bridgeai_knowledge_dense_v1
bridgeai_knowledge_sparse_v1
```

两类索引的来源、发布状态、权限、有效期和删除语义不同，不能通过一个混合集合共享别名。Memory 检索结果也不得伪装成 RAG EvidenceItem。

### 7.11.5 MinIO Artifact

建议对象键由系统生成：

```text
memory-context/
  organization/{organization_id}/
  project/{project_id_or_global}/
  memory/{memory_id}/
  version/{artifact_version}/
  {artifact_id}.json.zst
```

PostgreSQL 保存 artifact_id、bucket、object_key、object_version_id、sha256、size、content_type、encryption_profile 和 retention_policy。对象键不得直接拼接用户输入和原始文件名。

### 7.11.6 Outbox 与索引一致性

```text
Memory Service
   │ PostgreSQL Transaction
   ├── memory_records
   ├── memory_events
   └── memory_outbox
             │
             ▼
       Index Worker
       ├── upsert / delete vector
       ├── invalidate cache
       └── report result
```

Worker 使用 outbox_id 作为幂等键。处理成功后记录 index_version、point_id 和完成时间。连续失败进入死信并告警。

### 7.11.7 召回一致性规则

语义候选返回后，Memory Service 必须回到 PostgreSQL 重新确认：

1. status 仍为 active；
2. 当前时间位于有效期；
3. 来源未撤回；
4. 当前 ACL 版本允许调用者读取；
5. 项目未归档或调用显式允许归档查询；
6. deletion_status 为 none；
7. 索引 memory_version 与权威版本一致。

任一条件失败即丢弃候选并产生索引修复事件。

### 7.11.8 索引重建与回滚

索引可以根据 PostgreSQL active 记录和受控 Artifact 重建。重建采用版本化集合和别名切换：

1. 创建新集合并登记 index_version；
2. 读取权威记录，按权限和状态批量写入；
3. 比对记录数、哈希和抽样查询；
4. 在控制面批准后切换生产别名；
5. 保留旧集合到回滚窗口结束；
6. 删除旧集合前记录审计。

索引重建不得改变 memory_id、确认状态和有效期。

### 7.11.9 删除顺序

删除或撤权时按以下顺序处理：

1. PostgreSQL 将记录变为不可召回状态；
2. 提交缓存失效和索引删除事件；
3. 删除或按策略保留 MinIO 对象版本；
4. 删除派生摘要和 Context 缓存；
5. 完成一致性核对；
6. 将删除任务标记为 complete，或保留 blocked 原因和最小墓碑。

不得先删除原始来源或 Artifact，再留下无法解释的 active 记忆。

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
