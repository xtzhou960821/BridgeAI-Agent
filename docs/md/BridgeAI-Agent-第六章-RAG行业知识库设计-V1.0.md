# BridgeAI-Agent Architecture White Paper

# 第六章 RAG 行业知识库设计

| 项目 | 内容 |
|---|---|
| 文档名称 | BridgeAI-Agent Architecture White Paper |
| 章节 | 第六章 RAG 行业知识库设计 |
| 版本 | V1.0 |
| 状态 | 正式版 |
| 适用范围 | 桥梁与道路巡检 AI Agent |
| 默认开发环境 | Mac Studio / Apple M3 Ultra / 512GB 统一内存 |
| 元数据与审计 | PostgreSQL（本地部署） |
| 向量检索 | Qdrant（本地部署） |
| 对象存储 | MinIO 或兼容 S3 的受控对象存储 |
| 编制日期 | 2026-07-29 |

---

## 6.1 本章目标

本章定义 BridgeAI-Agent 的 RAG（Retrieval-Augmented Generation，检索增强生成）行业知识库架构，包括知识分类、来源准入、文档解析、结构化切分、索引构建、检索重排、证据引用、权限隔离、评测治理和工程落地要求。

RAG 的目标不是让大语言模型“记住更多内容”，而是让 Agent 在执行桥梁与道路巡检任务时，能够取得来源明确、版本有效、权限允许、可以复核的工程依据。

本章重点解决以下问题：

1. 规范、标准、项目资料、历史案例和病害知识如何统一接入；
2. 扫描 PDF、表格、图片和复杂版式如何恢复为可检索结构；
3. 如何保留页码、章节、条款、表格和图号，使答案可以定位原文；
4. 如何通过关键词与向量混合检索提高专业术语和语义问题的召回能力；
5. 如何处理规范失效、版本替代、来源冲突和适用范围差异；
6. RAG Tool 如何与 Agent、Workflow、报告生成及人工复核集成；
7. 如何防止越权检索、间接提示注入和无证据生成；
8. 如何建立可量化、可回归、可审计的 RAG 评测体系。

本章的最终产出是 BridgeAI-Agent 第一阶段知识服务的工程设计基线，而不是某个具体 RAG 框架的使用说明。

---

## 6.2 RAG 在 BridgeAI-Agent 中的定位

BridgeAI-Agent 中的 RAG 是一个受权限、版本和证据规则约束的行业知识服务。

其正式定位为：

> 从已发布且调用者有权访问的工程知识中检索适用依据，形成可引用的证据包，并为 Agent 的解释、建议草案和报告编制提供受约束输入。

RAG 不直接替代检测算法，也不直接替代工程人员判断。视觉病害识别、裂缝测量、构件定位和统计计算仍由专业 Tool 执行；RAG 负责回答“依据是什么”“规范如何规定”“相似案例如何处理”“当前结论还缺少哪些证据”。

### 6.2.1 RAG、Memory、业务数据与模型参数的区别

| 能力 | 保存或处理的对象 | 典型问题 | 权威来源 | 本章边界 |
|---|---|---|---|---|
| RAG | 规范、项目资料、案例、病害知识及可引用片段 | “该类裂缝应查阅哪些条款？” | 已发布知识版本 | 本章详细设计 |
| Memory | 用户偏好、任务摘要、项目上下文、跨步骤事实 | “这个项目上次采用了哪套复核规则？” | 项目记忆和任务记忆 | 第七章详细设计 |
| 业务数据 | 桥梁、道路、构件、病害、任务、报告、复核记录 | “某桥本次发现多少处裂缝？” | PostgreSQL 业务表 | 第八章详细设计 |
| Workflow State | 当前执行步骤、结果标识、恢复信息 | “任务中断后从哪个节点继续？” | LangGraph Checkpoint 与业务状态 | 第五章已定义 |
| 模型参数 | 模型训练形成的统计能力 | “如何组织自然语言回答？” | 模型版本 | 第十二章详细设计 |

知识库可以收录项目文件和历史案例，但它保存的是经过治理、可检索、可引用的知识版本；项目实时状态、个人偏好和临时对话不得因此混入知识索引。

### 6.2.2 RAG 的输出形态

RAG 服务不只返回一段自然语言。标准输出至少包括：

- 检索结果 ID；
- 规范化问题；
- 命中的知识版本；
- 证据条目及原文定位；
- 来源有效性和适用性；
- 检索与重排信息；
- 来源冲突和缺失信息；
- 可供 Agent 使用的答案草案；
- 是否必须人工复核；
- 完整审计标识。

这种设计使 Agent 可以组织结果，但不能隐藏证据边界。

---

## 6.3 职责边界

RAG 系统涉及多个组件。各组件必须保持单一职责，避免把检索、生成、权限和业务决策集中在一个不可审计的链路中。

| 组件 | 负责 | 不负责 |
|---|---|---|
| Agent | 判断是否需要知识、构造检索意图、解释 RAG 结果、决定是否追问或送审 | 直接读取向量库、绕过权限、把检索分数解释为工程置信度 |
| Workflow | 安排 RAG 节点、保存结果标识、处理重试和人工复核 | 维护完整知识正文、执行底层检索算法 |
| RAG Tool | 校验结构化输入、调用知识服务、统一错误和审计语义 | 自行改变 Workflow、直接签发报告 |
| RAG Service | 查询理解、过滤、召回、重排、证据组织和引用校验 | 决定正式病害等级或处治方案 |
| Ingestion Service | 文档注册、解析、切分、索引、发布和版本迁移 | 将未审核内容直接发布到生产集合 |
| PostgreSQL | 保存权威元数据、版本、权限、状态、处理记录和审计记录 | 保存大体积原始文件或替代 Qdrant 的向量检索职责 |
| Qdrant | 保存稠密与稀疏向量、检索载荷和过滤索引 | 充当知识版本和权限关系的唯一权威数据源 |
| MinIO | 保存原始文件、OCR、版面分析及其他 Artifact | 保存业务状态机和检索决策逻辑 |
| 人工复核者 | 复核规范适用性、工程结论、处治建议和正式成果 | 人工串联每一次普通知识查询 |

### 6.3.1 四条强制边界

1. **权限边界：** 权限必须在检索前生效，不得先召回越权内容再在答案阶段删除。
2. **证据边界：** 无法定位来源的模型知识不得作为规范条款或工程事实引用。
3. **责任边界：** RAG 可以生成处治建议草案，但不得代替有资质人员确认正式结论。
4. **状态边界：** Workflow State 只保存 `knowledge_result_ids`、必要摘要和复核标志，完整证据结果单独持久化。

### 6.3.2 与后续章节的关系

- 第七章定义项目记忆、任务记忆和上下文压缩；
- 第八章展开知识实体、权限实体、索引映射和审计表的完整数据库设计；
- 第十章定义通用 Prompt、引用格式和结构化输出规范；
- 第十一章定义知识管理后台、检索 API 和用户交互；
- 第十二章定义 Embedding、Reranker 和生成模型的统一评测与生命周期；
- 第十三章定义生产部署、备份、监控、密钥和网络安全。

本章只给出上述章节必须遵守的知识服务契约。

---

## 6.4 典型应用场景

### 6.4.1 病害解释与检查要点

现场人员或 Agent 可以围绕裂缝、剥落、露筋、渗水、坑槽、车辙、沉陷等病害发起查询。

RAG 应返回：

- 术语定义和常见表现；
- 可能成因，但明确区分“来源陈述”和“模型归纳”；
- 建议补充采集的信息；
- 适用的检查、检测或评定依据；
- 原文条款和页码；
- 不确定性与人工复核提示。

RAG 不得仅凭一张图片和一段通用知识确定结构安全等级。

### 6.4.2 标准与规范条款检索

典型问题包括：

- 某类桥梁检查应采用哪种检查类型；
- 道路技术状况评定涉及哪些指标；
- 某病害记录需要哪些字段；
- 某规范版本是否仍在项目适用期内；
- 项目专用技术要求是否比通用标准更严格。

系统必须同时检查标准编号、版本、实施日期、替代关系、项目约定和适用范围。只命中关键词而未验证适用性，不能视为有效回答。

### 6.4.3 处治建议辅助

Agent 可以综合病害检测结果、构件类型、环境条件、历史处治案例和有效规范，生成处治建议草案。

输出必须分为：

1. 已知检测事实；
2. 直接引用的工程依据；
3. 模型综合形成的建议；
4. 仍需补充的检测信息；
5. 必须由专业人员确认的事项。

处治建议草案不得直接形成施工指令、预算批准或正式技术结论。

### 6.4.4 历史案例与既往效果检索

历史案例检索应同时考虑：

- 资产类型和结构形式；
- 构件类型；
- 病害类型、尺度和发展趋势；
- 环境与交通条件；
- 检测方法；
- 处治措施；
- 实施时间和后续效果；
- 案例质量和复核状态。

相似度只表示检索相关性，不表示案例可以直接复制。RAG 必须说明相似项、差异项和适用限制。

### 6.4.5 巡检报告引用支持

报告生成节点可以调用 RAG Tool，为病害说明、评定依据、检查方法和建议草案附加引用。

每条报告引用必须能够回溯到：

```text
report_id
  → knowledge_result_id
  → evidence_id
  → document_version_id
  → page / section / clause
  → source_artifact_id
```

当知识版本在报告生成后更新时，历史报告仍应能够恢复当时使用的证据版本。

---

## 6.5 设计原则

### 6.5.1 Evidence First

系统先取得证据，再组织答案。无法取得可引用证据时，应明确返回证据不足，而不是利用模型参数生成看似合理的条款。

### 6.5.2 Authority First

同一主题存在多个来源时，优先级不是由向量相似度单独决定，而应综合发布机构、文件类型、版本有效性、项目约束和人工审核状态。

### 6.5.3 Permission Before Retrieval

组织、项目、角色、知识域和敏感级别过滤必须进入召回条件。生成模型只接触调用者有权访问的证据。

### 6.5.4 Structure Aware

规范条款、表格、图注和项目记录具有明确结构。系统必须优先保留文档结构和定位信息，不能只按固定字符数机械切分。

### 6.5.5 Immutable Version

已发布知识版本不得原地覆盖。修订、替代和纠错通过新版本及版本关系表达，从而支持历史任务复现。

### 6.5.6 Hybrid Retrieval

工程查询同时包含编号、构件名、病害术语和自然语言意图。系统采用稀疏检索处理精确词项，采用稠密检索处理语义相关性，再通过融合与重排形成候选结果。

### 6.5.7 Abstention by Design

拒答、追问和转人工不是失败，而是工程系统的正常输出。系统应定义确定性的证据不足、版本冲突和适用性不明条件。

### 6.5.8 Model Agnostic

Embedding、Reranker 和生成模型通过 Model Gateway 接入。索引记录模型版本和向量维度，模型替换通过新索引版本完成，不破坏已发布知识。

### 6.5.9 Local First

涉及工程资料、检测报告和内部案例时，解析、向量化、检索和生成优先在本地或私有环境运行。外部服务必须经过数据分级和授权评估。

### 6.5.10 Traceable by Default

每次入库、发布、检索、引用和人工复核都必须产生可关联的审计记录。只记录最终答案而不记录证据版本，不符合本系统要求。

---

## 6.6 总体架构

BridgeAI-Agent RAG 由离线知识处理链和在线检索链组成。

```text
┌─────────────────────────────────────────────────────────────┐
│                       Knowledge Sources                      │
│  标准规范  项目资料  历史案例  病害知识  设备与模型文档       │
└───────────────────────────┬─────────────────────────────────┘
                            │ 注册、校验、授权
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ingestion Service                        │
│  Parser / OCR / Layout / Chunker / Metadata / Quality Gate │
└───────────────┬────────────────┬────────────────┬───────────┘
                │                │                │
                ▼                ▼                ▼
       ┌────────────────┐ ┌──────────────┐ ┌──────────────┐
       │ PostgreSQL     │ │ Qdrant       │ │ MinIO        │
       │ 元数据/版本/ACL│ │ Dense/Sparse │ │ 原文/解析产物 │
       │ 状态/审计      │ │ Payload Index│ │ OCR/版面结果  │
       └────────┬───────┘ └──────┬───────┘ └──────┬───────┘
                └────────────────┼────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                     Retrieval Service                       │
│ Query Understanding → ACL Filter → Hybrid Recall → Rerank  │
│ → Deduplicate → Evidence Pack → Citation Validation         │
└───────────────────────────┬─────────────────────────────────┘
                            ▼
                     ┌──────────────┐
                     │ RAG Tool     │
                     │ Tool SDK 契约│
                     └──────┬───────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Agent / LangGraph Workflow / Report Tool / Human Review     │
└─────────────────────────────────────────────────────────────┘
```

### 6.6.1 离线知识处理链

离线链负责把文件转化为可发布知识：

```text
来源登记
  ↓
文件哈希与安全检查
  ↓
解析、OCR 与版面恢复
  ↓
元数据补全与结构化切分
  ↓
解析质量和权限检查
  ↓
Embedding 与稀疏表示
  ↓
写入候选索引
  ↓
人工或规则审核
  ↓
发布知识版本和索引别名
```

入库成功不等于发布成功。只有通过质量门和权限门的版本才能进入生产检索。

### 6.6.2 在线检索链

在线链负责从一次结构化查询生成证据结果：

```text
RAGQueryInput
  ↓
身份、项目和权限校验
  ↓
查询理解与过滤条件构造
  ↓
稀疏召回 + 稠密召回
  ↓
融合、重排、去重和邻接扩展
  ↓
版本、适用性和证据覆盖检查
  ↓
Evidence Pack
  ↓
受约束生成与引用校验
  ↓
RAGQueryOutput
```

在线链的每个阶段都必须记录耗时和版本，以便定位问题发生在权限、召回、重排、生成还是引用校验环节。

### 6.6.3 控制面与数据面

控制面负责知识源、版本、权限、发布、索引别名和审计策略；数据面负责文件解析、向量写入和在线检索。生产发布权限不得由普通查询服务持有。

---

## 6.7 知识分类体系

BridgeAI-Agent 第一阶段采用“知识域 + 来源类型 + 资产范围 + 权威等级 + 生命周期状态”的多维分类方式。

### 6.7.1 知识域

| 知识域 | 主要内容 | 桥梁示例 | 道路示例 |
|---|---|---|---|
| 标准规范 | 行业标准、技术规范、指南、公告 | 桥涵养护、桥梁技术状况评定 | 公路技术状况评定、路面检测 |
| 项目要求 | 合同、技术要求、检测方案、监理指令 | 某桥定期检查方案 | 某路段路况检测方案 |
| 资产知识 | 结构、构件、材料和环境知识 | 梁、墩台、支座、伸缩缝 | 路基、路面、边坡、沿线设施 |
| 病害知识 | 病害定义、表现、成因和检查要点 | 裂缝、剥落、露筋、渗水 | 坑槽、车辙、沉陷、裂缝 |
| 历史案例 | 已复核的检测、处治和效果记录 | 同类桥型处治案例 | 同类路面病害处治案例 |
| 设备与模型 | 采集设备、算法和模型使用边界 | 无人机、测量设备、视觉模型 | 检测车、路况仪、视觉模型 |
| 报告模板 | 已审核的章节结构、术语和引用规则 | 桥梁定检报告模板 | 道路技术状况报告模板 |

### 6.7.2 来源类型

来源类型至少包括：

- `official_standard`：正式发布的标准或规范；
- `official_notice`：主管部门公告、解释和实施通知；
- `project_contract`：合同及项目专用技术要求；
- `project_plan`：经审批的检测方案或实施方案；
- `inspection_report`：已签发的检测或巡检报告；
- `review_record`：专家复核、监理审核或内部质量记录；
- `case_record`：结构化历史案例；
- `domain_manual`：内部病害手册和作业指导书；
- `equipment_manual`：设备和传感器文档；
- `model_card`：模型能力、数据范围和限制说明。

### 6.7.3 权威等级

| 等级 | 定义 | 使用规则 |
|---|---|---|
| A | 法规、主管部门正式公告、现行标准规范 | 可作为规范性核心证据，但仍需检查版本和适用范围 |
| B | 经审批的项目文件、签发报告、正式复核记录 | 可作为项目事实和项目约束证据 |
| C | 经内部审核的知识手册、结构化案例、模型卡 | 可用于解释和辅助建议，不得覆盖 A、B 级来源 |
| D | 未审核草稿、外部网页摘录、自动生成摘要 | 只进入隔离区，不得用于正式回答 |

权威等级不直接等同于检索排名。一个 A 级来源如果已失效或不适用于当前资产，也不能优先于有效且适用的来源。

### 6.7.4 规范类知识示例

第一阶段至少验证以下公开来源的入库与版本治理能力：

- 《公路技术状况评定标准》（JTG 5210-2018），主管部门公告明确自 2019 年 5 月 1 日起施行，并同时废止 JTG H20-2007；
- 《公路桥涵养护规范》（JTG 5120-2021），主管部门公告明确自 2021 年 11 月 1 日起施行，并同时废止 JTG H11-2004；
- 《公路桥梁技术状况评定标准》（JTG/T H21-2011），主管部门公告明确自 2011 年 9 月 1 日起施行。

上述条目用于验证版本字段和替代关系，不表示三个文件可以覆盖所有桥梁与道路巡检问题。每次正式入库仍须通过交通运输标准化信息系统或主管部门最新目录核验状态。

---

## 6.8 知识来源与准入治理

### 6.8.1 来源登记

任何文件进入解析流程前，必须先创建知识源和文档版本记录。最小登记信息包括：

- 组织和项目；
- 知识域与来源类型；
- 文档名称、编号和语言；
- 发布机构或责任单位；
- 发布、实施和失效日期；
- 适用资产、区域、专业和项目阶段；
- 来源 URL 或 Artifact ID；
- 文件哈希、MIME 类型和大小；
- 敏感级别与访问范围；
- 登记人、登记时间和审核责任人。

无法确认来源责任主体的材料，默认进入 D 级隔离区。

### 6.8.2 准入检查

知识发布前必须完成以下检查：

1. **来源真实性：** 文件来源、发布机构和传递链可以验证；
2. **完整性：** 文件没有缺页、截断、损坏或异常加密；
3. **版本性：** 标准编号、版本、实施日期和替代关系明确；
4. **适用性：** 适用资产、区域、项目和时间范围可表达；
5. **解析质量：** 标题、条款、页码、表格及图注达到发布门槛；
6. **权限：** 组织、项目、角色和敏感级别已经配置；
7. **安全性：** 文件类型、宏、嵌入对象和可疑内容经过检查；
8. **重复性：** 内容哈希和逻辑版本未造成无意义重复；
9. **审核性：** 达到来源等级要求的人工或规则审核已经完成。

### 6.8.3 发布状态

| 状态 | 含义 | 是否可检索 |
|---|---|---|
| `registered` | 已登记，尚未解析 | 否 |
| `parsing` | 正在解析或 OCR | 否 |
| `validating` | 正在执行质量、版本和权限检查 | 否 |
| `indexing` | 正在写入候选索引 | 否 |
| `review_pending` | 等待审核发布 | 否 |
| `published` | 已发布到生产检索别名 | 是 |
| `rejected` | 未通过准入 | 否 |
| `failed` | 处理失败，可按策略重试 | 否 |
| `superseded` | 已被新版本替代 | 仅历史复现或显式查询 |
| `archived` | 已归档 | 默认否 |

### 6.8.4 拒绝准入条件

出现以下任一情况时不得发布：

- 规范版本无法确认；
- 关键页、条款或表格缺失；
- OCR 质量低于项目门槛且未完成人工校正；
- 文件包含未授权的个人信息或敏感工程数据；
- 项目草稿被错误标记为正式文件；
- 权限范围无法确定；
- 文件内容哈希与登记版本不一致；
- 内容包含可疑指令，且未完成不可信内容隔离；
- 责任审核人拒绝发布。

### 6.8.5 发布与查询分权

知识管理员可以登记和维护元数据；解析服务可以生成候选片段；审核者可以批准发布；查询服务只能读取已发布版本。普通 Agent、RAG Tool 和最终用户不得取得生产发布或索引别名切换权限。

---

## 6.9 知识入库流水线

知识入库是一个可恢复、可审计、可重复执行的长任务，不应由一次同步 API 请求串行完成。

### 6.9.1 状态流转

```text
registered
  ↓
parsing
  ↓
validating
  ↓
indexing
  ↓
review_pending
  ↓
published
```

异常和退出状态包括：

```text
rejected     准入或审核未通过
failed       技术处理失败，可按策略恢复
superseded   已被新版本替代
archived     已退出常规检索
```

状态迁移必须由应用服务执行，并写入 PostgreSQL 事件记录。解析器、Embedding Worker 和 Qdrant 客户端只能报告步骤结果，不得自行把知识版本标记为 `published`。

### 6.9.2 处理步骤

1. **登记：** 创建 `document_id` 和 `document_version_id`，保存来源、权限和文件哈希；
2. **安全预检：** 校验文件类型、大小、加密、宏、嵌入对象和恶意内容风险；
3. **原件固化：** 将原始文件写入带版本的 MinIO Bucket，记录 `object_version_id`；
4. **解析：** 生成文本、版面块、表格、图片、页码和结构树；
5. **质量校验：** 计算解析覆盖率、OCR 置信度、乱码率、标题恢复率和定位完整率；
6. **切分：** 按文档结构生成 Chunk，并建立父子和邻接关系；
7. **表示生成：** 批量生成稠密向量和稀疏表示；
8. **候选索引：** 写入非生产集合或未激活索引版本；
9. **一致性检查：** 对比 PostgreSQL Chunk 数、Qdrant Point 数和 MinIO Artifact；
10. **审核：** 由规则或人工确认来源、版本、权限和解析质量；
11. **发布：** 原子切换知识版本状态与生产索引别名；
12. **审计：** 记录处理版本、审核人、发布时间和发布结果。

### 6.9.3 幂等键

一次入库执行的幂等性由以下字段共同确定：

```text
content_sha256
parser_name
parser_version
chunking_policy_version
embedding_model_id
embedding_model_version
sparse_encoder_version
index_schema_version
```

相同幂等键已成功完成时，重复请求返回既有处理结果，不重复创建 Chunk 或 Point。任何影响正文、定位、权限或向量空间的字段变化，都必须产生新的处理版本。

### 6.9.4 事务与补偿

PostgreSQL 事务不能覆盖 MinIO 和 Qdrant，因此入库采用业务事务加 Outbox 事件和幂等 Worker：

```text
PostgreSQL 写入处理意图与 Outbox
  ↓
Worker 写 MinIO / Qdrant
  ↓
Worker 回写外部资源 ID 与校验结果
  ↓
发布服务确认三方一致
```

当外部写入成功但 PostgreSQL 回写失败时，Worker 使用幂等键查询并恢复；当审核拒绝发布时，候选向量保留到规定期限后清理，不立即删除审计信息。

### 6.9.5 重试边界

可自动重试：

- 对象存储短暂不可用；
- Qdrant 短暂连接失败；
- Embedding Worker 超时；
- 单页 OCR 临时失败；
- 数据库可恢复事务冲突。

不得自动重试：

- 文件哈希与登记值不一致；
- 规范版本或来源无法确认；
- 权限配置缺失；
- 解析质量低于发布门槛；
- 人工审核拒绝；
- 向量维度与目标集合不一致。

---

## 6.10 文档解析、OCR 与结构恢复

工程知识文档通常包含复杂表格、扫描页、图号、公式、页眉页脚和多级条款。解析目标不是只提取连续文本，而是恢复能够支持引用和检索的文档结构。

### 6.10.1 支持格式

第一阶段支持：

| 格式 | 处理重点 | 原件保留 |
|---|---|---|
| PDF | 文本层、扫描页、目录、页码、表格、双栏和图注 | 必须 |
| DOCX | 标题样式、段落、表格、列表、批注和分页定位 | 必须 |
| XLSX | Sheet、区域、表头、单元格坐标、合并单元格和公式结果 | 必须 |
| HTML | 标题层级、正文、表格、链接和来源 URL | 必须保存快照 |
| PNG/JPEG/TIFF | OCR、方向校正、区域识别和图像坐标 | 必须 |
| TXT/Markdown | 编码、标题、列表、代码和引用关系 | 必须 |

压缩包、可执行文件和含宏文档不得直接进入解析队列。需要支持时，应先在隔离环境解包和安全检查，再逐个登记内部文件。

### 6.10.2 解析产物

每个文档版本至少产生：

- `raw_text`：按页面保存的原始提取文本；
- `layout_blocks`：带页码和坐标的标题、正文、表格、图片及页眉页脚；
- `document_tree`：章节、条款和父子关系；
- `tables`：表格结构、表头、单元格和跨页关系；
- `figures`：图号、图注、页码和原图引用；
- `ocr_result`：OCR 文本、区域、置信度和识别引擎版本；
- `quality_report`：解析质量指标和阻断原因；
- `normalized_text`：供切分使用但不替代原文的规范化文本。

所有解析产物均以 Artifact 方式写入 MinIO，PostgreSQL 保存 Artifact ID、版本、哈希和处理状态。

### 6.10.3 OCR 策略

OCR 处理步骤为：

```text
页面图像化
  ↓
方向与倾斜校正
  ↓
版面区域检测
  ↓
中文、英文、数字与符号识别
  ↓
阅读顺序恢复
  ↓
页码、条款号和表格结构校验
  ↓
低置信度区域复核
```

不得用整页平均置信度掩盖关键条款编号的错误。标准编号、数值、单位、等级、条款号和表头属于高风险字段，应单独设置质量门。

### 6.10.4 表格和图像

表格应保留：

- 文档、页码和表号；
- 表题；
- 行列标题；
- 合并单元格关系；
- 单元格坐标；
- 跨页续表关系；
- 脚注和单位；
- 原始页面截图引用。

图像不能只保存 OCR 文本。病害示意图、构件编号图和检测流程图应保留图号、图注、页面坐标和原图 Artifact。第一阶段可以只检索图注和邻近正文，但数据结构必须允许后续接入多模态 Embedding。

### 6.10.5 解析质量指标

| 指标 | 定义 | 发布要求 |
|---|---|---|
| 页面覆盖率 | 成功解析页数 / 应解析页数 | 必须达到项目门槛 |
| 字符异常率 | 乱码和不可识别字符占比 | 不得超过项目门槛 |
| 标题恢复率 | 正确恢复标题数 / 抽检标题数 | 规范类文档从严 |
| 条款定位率 | 可定位条款数 / 抽检条款数 | 规范类文档从严 |
| 表格结构准确率 | 正确单元格关系 / 抽检关系 | 含关键数值表时从严 |
| OCR 关键字段准确率 | 正确编号、数值、单位 / 抽检项 | 未达标必须人工校正 |

具体数值阈值由真实样本评测确定并版本化，不在设计阶段凭经验固定。发布记录必须保存当时使用的阈值版本。

---

## 6.11 结构化切分与元数据设计

### 6.11.1 切分原则

BridgeAI-Agent 采用“结构优先、长度约束、语义完整、定位可回溯”的切分策略。

切分优先级为：

```text
文档
  → 篇 / 章
  → 节
  → 条款
  → 自然段 / 列表
  → 表格 / 图注
  → 长度二次切分
```

固定 Token 长度只作为最后一道限制，不能跨越不同条款、不同表格或不同权限范围合并内容。

### 6.11.2 Chunk 类型

| 类型 | 用途 | 特殊要求 |
|---|---|---|
| `clause` | 标准条款和项目要求 | 保留完整条款号和父级标题 |
| `paragraph` | 说明性正文 | 保留上下文路径和邻接关系 |
| `list` | 检查项、条件和步骤 | 不拆散编号语义 |
| `table` | 指标、等级、检查频率和参数 | 保留表题、表头、单位和单元格坐标 |
| `figure_caption` | 病害图、构件图和流程图 | 关联原图 Artifact |
| `case_summary` | 历史案例的结构化摘要 | 关联原始报告与复核状态 |
| `model_card` | 模型能力和限制 | 关联模型版本和数据范围 |

### 6.11.3 上下文关系

每个 Chunk 应保存：

- `parent_chunk_id`：上级章节或条款；
- `previous_chunk_id` 和 `next_chunk_id`：同一文档中的邻接关系；
- `referenced_chunk_ids`：正文引用的表格、图或附录；
- `source_span`：原文字符范围或页面坐标；
- `section_path`：从文档标题到当前节点的完整路径。

邻接扩展只能在同一文档版本、相同权限范围和相同结构分支内进行。

### 6.11.4 元数据契约

```python
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class KnowledgeChunkMetadata(BaseModel):
    chunk_id: str
    document_id: str
    document_version_id: str
    tenant_id: str
    project_id: str | None = None

    source_type: Literal[
        "official_standard",
        "official_notice",
        "project_contract",
        "project_plan",
        "inspection_report",
        "review_record",
        "case_record",
        "domain_manual",
        "equipment_manual",
        "model_card",
    ]
    knowledge_domain: str
    authority_level: Literal["A", "B", "C", "D"]
    publication_status: Literal[
        "review_pending", "published", "superseded", "archived"
    ]

    asset_types: list[str] = Field(default_factory=list)
    component_types: list[str] = Field(default_factory=list)
    disease_types: list[str] = Field(default_factory=list)
    region_codes: list[str] = Field(default_factory=list)

    effective_from: date | None = None
    effective_to: date | None = None
    supersedes_version_id: str | None = None
    superseded_by_version_id: str | None = None

    page_number: int | None = None
    section_path: list[str] = Field(default_factory=list)
    clause_number: str | None = None
    table_number: str | None = None
    figure_number: str | None = None

    acl_scope: list[str] = Field(default_factory=list)
    sensitivity_level: str
    content_sha256: str
    parser_version: str
    chunking_policy_version: str
    embedding_model_version: str
    sparse_encoder_version: str
    index_schema_version: str
```

该契约用于说明跨组件必须一致的字段，不替代第八章的数据库表和约束设计。

### 6.11.5 切分版本

切分策略必须版本化。以下变化需要创建新的 `chunking_policy_version`：

- 最大 Token 数变化；
- 重叠窗口变化；
- 标题或条款识别规则变化；
- 表格序列化方式变化；
- 邻接扩展规则变化；
- 权限边界或脱敏规则变化。

历史检索结果必须能够恢复当时使用的切分版本。

---

## 6.12 Embedding 与索引策略

### 6.12.1 双路表示

第一阶段为每个可检索 Chunk 生成两类表示：

- **稠密向量：** 捕捉自然语言语义、同义表达和上下文相关性；
- **稀疏表示：** 保留标准编号、构件名称、病害术语、数值和精确词项。

工程查询经常同时包含“JTG/T H21-2011”“支座脱空”和“这种现象如何处理”等内容。只使用稠密向量容易削弱编号和专业词项，只使用关键词又难以处理同义表达，因此两路表示必须独立生成、独立评测、在线融合。

### 6.12.2 模型选择要求

Embedding 模型不得只依据公开榜单选型。候选模型必须在 BridgeAI 自有桥梁与道路评测集上验证：

- 中文工程术语；
- 中英混合标准编号；
- 构件与病害同义词；
- 长条款和短查询；
- 数值、单位和等级；
- 否定条件与适用范围；
- 本地推理吞吐和内存占用。

在完成项目评测前，本章不锁定具体模型名称。模型通过 Model Gateway 统一调用，本地部署优先。

### 6.12.3 向量空间隔离

以下任一变化不得直接向原集合写入：

- Embedding 模型或权重变化；
- 向量维度变化；
- 归一化策略变化；
- 距离度量变化；
- 稀疏编码器变化；
- Chunk 正文规范化方式变化。

推荐集合命名：

```text
bridgeai_knowledge_dense_sparse_v1
bridgeai_knowledge_dense_sparse_v2
```

生产查询使用逻辑别名，例如：

```text
bridgeai_knowledge_active
```

发布新索引时，先完成全量构建和离线评测，再原子切换别名。旧索引按回滚期限保留。

### 6.12.4 Qdrant Point 载荷

Qdrant Point 保存：

- `chunk_id`；
- `document_version_id`；
- 稠密与稀疏向量；
- 用于过滤的租户、项目、来源、状态、有效期、资产和权限载荷；
- 用于结果展示的最小标题与定位字段。

完整正文可以按性能和安全要求选择存放在 Qdrant Payload 或通过 `chunk_id` 回读 PostgreSQL/MinIO，但 PostgreSQL 始终是版本与权限元数据的权威来源。

### 6.12.5 Payload Index

以下字段应建立适合类型的 Payload Index：

- `tenant_id`；
- `project_id`；
- `publication_status`；
- `authority_level`；
- `source_type`；
- `asset_types`；
- `component_types`；
- `disease_types`；
- `effective_from` 和 `effective_to`；
- `acl_scope`；
- `document_version_id`。

字段是否建索引以真实过滤频率和集合规模为依据，避免为低选择性字段无条件建立索引。

### 6.12.6 重建与回滚

重建过程不得修改正在服务的集合。完整流程为：

```text
创建新集合
  ↓
批量生成并写入向量
  ↓
校验 Point 数和抽样内容
  ↓
执行离线评测与权限测试
  ↓
切换生产别名
  ↓
观察运行指标
  ↓
确认或回滚
```

---

## 6.13 PostgreSQL、Qdrant 与 MinIO 分工

### 6.13.1 存储职责矩阵

| 存储 | 权威数据 | 主要用途 | 不应存放 |
|---|---|---|---|
| PostgreSQL | 知识源、文档版本、状态、权限、处理任务、引用和审计 | 事务、关联查询、版本治理、发布控制 | 原始 PDF、大体积 OCR 页面和模型文件 |
| Qdrant | 不作为业务权威源 | 稠密/稀疏召回、过滤和检索载荷 | 唯一权限关系、唯一发布状态、业务审批记录 |
| MinIO | 原始文件和 Artifact 的不可变版本 | 原件、OCR、版面、表格、图片和解析报告 | 任务状态机、关系权限、检索排序逻辑 |
| Redis | 无权威数据 | 短期缓存、限流和轻量队列 | 长期知识、审计和唯一状态 |
| Workflow State | 当前执行快照 | 保存结果标识、必要摘要和恢复信息 | 完整文档、完整 Evidence Pack、向量 |

### 6.13.2 PostgreSQL 代表性实体

本章只定义实体边界，完整字段、外键、索引和迁移留到第八章：

```text
knowledge_sources
knowledge_documents
knowledge_document_versions
knowledge_processing_runs
knowledge_chunks
knowledge_index_versions
knowledge_publications
knowledge_acl_bindings
knowledge_query_runs
knowledge_results
knowledge_evidence_items
knowledge_review_records
knowledge_audit_events
```

`knowledge_document_versions` 是版本治理中心，`knowledge_chunks` 保存可查询元数据和文本引用，`knowledge_results` 与 `knowledge_evidence_items` 保存每次检索及其证据快照。

### 6.13.3 MinIO Bucket 建议

```text
bridgeai-knowledge-source      原始文件
bridgeai-knowledge-parsed      解析、OCR 和版面产物
bridgeai-knowledge-review      审核快照和质量报告
bridgeai-knowledge-export      经授权导出的知识包
```

Bucket 和对象键不得直接使用用户输入拼接。对象键由系统生成，并在 PostgreSQL 中建立 `artifact_id → bucket / object_key / version_id / sha256` 映射。

### 6.13.4 一致性规则

生产知识版本必须同时满足：

1. PostgreSQL 状态为 `published`；
2. 生产索引别名指向包含该版本的已验证集合；
3. 原始文件和必需解析 Artifact 可读取且哈希一致；
4. 权限绑定存在且已经同步为 Qdrant 过滤载荷；
5. 发布事件和审核记录完整。

任一条件不满足时，查询服务应排除该版本并产生一致性告警。

### 6.13.5 删除与保留

业务删除先在 PostgreSQL 标记不可检索，再更新索引，最后按保留策略处理对象版本。不得先物理删除原件，再留下无法验证的引用记录。

因合规要求必须删除文件时，应保留不含正文的最小审计记录，包括删除对象、依据、执行人、时间、原哈希和受影响的知识结果 ID。

---

## 6.14 混合检索与查询理解

在线检索不是把用户原句直接发送给向量数据库。系统必须先把自然语言问题转换为受权限和适用性约束的检索计划。

### 6.14.1 查询理解

查询理解输出至少包括：

- 规范化问题；
- 查询意图；
- 资产类型；
- 构件类型；
- 病害类型；
- 标准编号或项目文件编号；
- 地区和项目范围；
- 查询基准日期；
- 期望证据类型；
- 是否要求现行有效版本；
- 需要追问的缺失条件。

典型意图包括：

```text
define_disease          病害解释
retrieve_clause         条款检索
compare_versions        版本比较
find_case               案例检索
support_treatment       处治建议辅助
support_report          报告引用支持
check_applicability     适用性检查
```

标准编号、构件编号、数值、单位和否定条件应通过确定性规则提取；大语言模型可以辅助意图识别和同义词扩展，但不得自行扩大项目权限或知识范围。

### 6.14.2 查询规范化

查询规范化可以执行：

- 全角和半角统一；
- 常见标准编号格式统一；
- 构件和病害别名映射；
- 中英文术语映射；
- 错别字候选提示；
- 单位规范化；
- 项目内部编码映射。

原始查询必须保留。规范化查询和扩展词作为独立字段进入审计记录，避免无法解释召回原因。

### 6.14.3 权限与适用性过滤

召回前由服务端根据 `ToolContext` 和业务权限生成过滤条件。过滤范围至少包含：

```text
tenant_id
project_id
publication_status
source_type
authority_level
asset_types
component_types
disease_types
region_codes
effective_from / effective_to
acl_scope
```

用户输入只能缩小检索范围，不能声明自己拥有额外 `acl_scope`。查询现行规范时，默认排除 `superseded` 和 `archived`；历史复现任务必须显式指定任务发生日期和知识版本。

### 6.14.4 混合召回

Qdrant Query API 支持将稠密和稀疏查询作为预取结果，再通过融合生成统一排名。BridgeAI-Agent 第一阶段采用：

```text
稀疏召回 Top-Ns
        +
稠密召回 Top-Nd
        ↓
Reciprocal Rank Fusion
        ↓
融合候选 Top-Nf
        ↓
Reranker Top-K
```

推荐初始配置仅作为可评测基线：

| 参数 | 初始值 | 说明 |
|---|---:|---|
| `sparse_candidate_k` | 40 | 精确术语和编号候选数 |
| `dense_candidate_k` | 40 | 语义候选数 |
| `fusion_candidate_k` | 30 | 融合后进入重排的候选数 |
| `final_top_k` | 8 | 最终证据候选数 |

这些参数必须存入 `retrieval_config_version`，并通过评测集调优。不得把初始值写死在 Tool 代码中。

### 6.14.5 精确命中通道

对于标准编号、条款号、构件编码和报告编号，系统应先执行精确或前缀匹配。精确命中与混合召回并行，最终由融合与重排统一处理。

例如查询“JTG 5210-2018 第 5 章”时，编号和章节过滤应比语义相似片段更先进入候选集。

### 6.14.6 查询追问

以下情况应在检索前追问或返回结构化缺失项：

- 未提供桥梁或道路资产类型，但不同标准适用范围可能冲突；
- 未提供查询基准日期，却要求判断规范是否现行；
- 处治建议缺少病害尺度、构件、材料或环境条件；
- 项目要求与通用规范可能存在优先级关系，但未指定项目；
- 查询请求超出调用者可访问的知识域。

---

## 6.15 重排、去重与上下文组织

### 6.15.1 重排目标

混合召回解决“找到候选”，Reranker 解决“候选是否真正回答当前问题”。重排输入由规范化问题、必要的工程上下文和候选片段组成。

重排模型必须在本地工程评测集上验证，并记录：

- `reranker_model_id`；
- `reranker_model_version`；
- 输入模板版本；
- 候选数；
- 推理设备；
- 耗时；
- 原始分数。

检索分数和重排分数都是排序信号，不是病害识别置信度，也不是工程结论正确概率。

### 6.15.2 规则校正

重排后还需执行确定性规则校正：

1. 已失效且非历史查询的来源降级或排除；
2. 不适用当前资产、地区或日期的来源排除；
3. 项目专用要求在本项目范围内可高于通用内部手册；
4. A、B 级来源优先于仅有语义相似的 C 级来源；
5. D 级来源不得进入正式 Evidence Pack；
6. 同一条款的重复切片只保留定位最完整的版本；
7. 包含关键表格时，表题、表头、单位和必要脚注必须一起进入上下文。

规则校正不得默默修改结果。每一次升降级都应记录 `ranking_reason`。

### 6.15.3 去重策略

去重分为四层：

- **内容哈希去重：** 排除完全相同的文本；
- **文档版本去重：** 默认保留当前有效版本，历史任务保留指定版本；
- **条款去重：** 同一条款被不同长度 Chunk 命中时合并证据；
- **近重复去重：** 对重复转载或报告引用内容保留权威原始来源。

不同来源对同一问题给出不同结论时，不得作为重复内容删除，应进入冲突检测。

### 6.15.4 邻接扩展

当命中片段依赖上文定义、列表前置条件、表格脚注或下一条例外条件时，可以扩展父级、前后邻接或引用 Chunk。

扩展必须满足：

- 同一 `document_version_id`；
- 调用者拥有相同或更高访问权限；
- 扩展内容与命中条款存在结构关系；
- 扩展后仍在上下文预算内；
- 所有扩展片段拥有独立定位和引用 ID。

### 6.15.5 上下文预算

上下文组织按以下优先顺序分配 Token：

1. 直接回答问题的有效规范条款；
2. 条款适用条件、定义和例外；
3. 项目专用要求；
4. 高质量历史案例；
5. 解释性病害知识；
6. 辅助设备或模型文档。

不得为了增加来源数量而截断关键条件，也不得让单个长文档占满全部上下文。上下文包应设置单文档上限、单来源类型上限和最小来源多样性要求。

### 6.15.6 证据覆盖检查

进入生成前，系统检查：

- 是否存在直接支持核心结论的证据；
- 是否包含必要定义和适用条件；
- 是否遗漏明确的例外或限制；
- 是否存在相互冲突的有效来源；
- 是否只有低权威来源；
- 是否存在必须由项目资料补充的事实。

覆盖不完整时，系统降低回答范围或返回缺失项，不通过增加生成长度弥补证据缺口。

---

## 6.16 引用、证据链与冲突处理

### 6.16.1 Evidence Item

每个进入答案或报告的引用都必须对应一个不可混淆的证据条目。

```python
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    evidence_id: str
    chunk_id: str
    document_id: str
    document_version_id: str

    document_title: str
    document_number: str | None = None
    issuing_organization: str | None = None
    source_type: str
    authority_level: Literal["A", "B", "C"]

    page_number: int | None = None
    section_path: list[str] = Field(default_factory=list)
    clause_number: str | None = None
    table_number: str | None = None
    figure_number: str | None = None
    source_artifact_id: str

    excerpt: str
    effective_from: date | None = None
    effective_to: date | None = None
    applicability: Literal[
        "applicable", "partially_applicable", "not_confirmed", "not_applicable"
    ]
    applicability_reason: str

    retrieval_methods: list[Literal["exact", "sparse", "dense"]]
    retrieval_score: float | None = None
    rerank_score: float | None = None
    ranking_reason: str
    acl_scope: list[str] = Field(default_factory=list)
```

`excerpt` 用于复核，不得因追求简短而删除否定词、适用条件、单位或例外条款。

### 6.16.2 引用定位

引用优先级为：

1. 条款号；
2. 表号或图号；
3. 章节路径加页码；
4. 页码加段落定位；
5. 仅页码。

如果原文件没有稳定页码，系统应使用章节路径、段落序号和原文哈希组合定位。解析后的内部行号不得伪装成原文条款号。

### 6.16.3 答案与证据的关联

生成结果应采用事实单元与证据 ID 的显式关联：

```text
claim_01 → evidence_02, evidence_05
claim_02 → evidence_07
claim_03 → unsupported
```

`unsupported` 的事实单元不得进入正式回答；如果它是模型推测，应改写为不确定性说明或需要人工确认的问题。

### 6.16.4 版本状态处理

| 情况 | 处理方式 |
|---|---|
| 当前有效版本 | 正常参与检索和引用 |
| 已被替代版本 | 默认排除；历史复现时允许并明确标识 |
| 尚未实施版本 | 仅在明确查询未来适用规则时返回 |
| 实施日期不明 | 标记 `not_confirmed`，不得作为确定性规范依据 |
| 项目继续约定旧版本 | 同时展示项目约定和标准替代关系，进入人工复核 |

### 6.16.5 来源冲突

冲突检测至少覆盖：

- 同一标准不同版本；
- 通用规范与项目专用要求；
- 正式标准与内部手册；
- 两份已签发项目文件；
- 规范条款与历史案例做法；
- 来源正文与自动摘要。

处理顺序为：

```text
确认来源身份
  ↓
确认版本和生效时间
  ↓
确认适用范围与项目约定
  ↓
标记冲突点
  ↓
输出双方证据
  ↓
请求人工裁决
```

生成模型不得通过语言流畅度自动选择一方。

### 6.16.6 证据快照

每个 `knowledge_result_id` 必须固化当次使用的 Evidence Item、知识版本、检索配置和模型版本。后续知识库更新不修改历史证据快照。

---

## 6.17 RAG Tool 协议

RAG Tool 遵循第四章 Tool SDK 的 `ToolContext`、`ToolResult`、Manifest、超时、审计和版本规则。Tool 只暴露稳定的结构化契约，不向 Agent 暴露 Qdrant 查询细节。

### 6.17.1 输入模型

`tenant_id`、`user_id`、角色和服务端权限来自 `ToolContext`，不得由自然语言参数覆盖。

```python
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class RAGQueryInput(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    project_id: str | None = None
    asset_id: str | None = None

    intent: Literal[
        "define_disease",
        "retrieve_clause",
        "compare_versions",
        "find_case",
        "support_treatment",
        "support_report",
        "check_applicability",
    ] | None = None

    asset_types: list[str] = Field(default_factory=list)
    component_types: list[str] = Field(default_factory=list)
    disease_types: list[str] = Field(default_factory=list)
    source_types: list[str] = Field(default_factory=list)
    document_numbers: list[str] = Field(default_factory=list)

    as_of_date: date | None = None
    require_current: bool = True
    include_superseded: bool = False
    answer_mode: Literal["evidence_only", "answer_with_evidence"] = (
        "answer_with_evidence"
    )
    final_top_k: int = Field(default=8, ge=1, le=20)
```

当 `include_superseded=True` 时，Tool 必须要求调用方提供历史复现理由或由策略层授权。

### 6.17.2 输出模型

```python
from typing import Literal

from pydantic import BaseModel, Field


class RetrievalTiming(BaseModel):
    authorization_ms: int
    query_understanding_ms: int
    sparse_retrieval_ms: int
    dense_retrieval_ms: int
    rerank_ms: int
    generation_ms: int
    citation_validation_ms: int
    total_ms: int


class KnowledgeConflict(BaseModel):
    conflict_id: str
    topic: str
    evidence_ids: list[str]
    description: str
    resolution: Literal["resolved_by_rule", "requires_human_review"]


class RAGQueryOutput(BaseModel):
    knowledge_result_id: str
    normalized_query: str
    intent: str
    status: Literal[
        "answered",
        "evidence_only",
        "needs_clarification",
        "insufficient_evidence",
        "conflict",
    ]

    answer: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    claim_evidence_map: dict[str, list[str]] = Field(default_factory=dict)
    conflicts: list[KnowledgeConflict] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    review_required: bool
    knowledge_index_version: str
    retrieval_config_version: str
    embedding_model_version: str
    reranker_model_version: str
    generation_model_version: str | None = None
    timings: RetrievalTiming
    trace_id: str
```

### 6.17.3 Tool Manifest 建议

```yaml
name: retrieve_engineering_knowledge
version: 1.0.0
category: knowledge
description: 检索桥梁与道路巡检工程知识并返回可引用证据
input_schema: RAGQueryInput
output_schema: RAGQueryOutput
side_effects: read_only
timeout_seconds: 45
retry:
  enabled: true
  max_attempts: 2
permissions:
  knowledge_read: true
  project_scope_required: false
audit:
  enabled: true
  retain_query_text: controlled
```

当查询包含敏感内容时，`retain_query_text` 应按数据分级改为哈希、脱敏摘要或受控加密保存，而不是无条件记录原文。

### 6.17.4 错误码

| 错误码 | 含义 | 是否自动重试 | 上层处理 |
|---|---|---:|---|
| `RAG_PERMISSION_DENIED` | 无知识域或项目权限 | 否 | 返回拒绝，不暴露存在性 |
| `RAG_NO_EVIDENCE` | 没有满足条件的证据 | 否 | 追问、扩大已授权范围或转人工 |
| `RAG_VERSION_CONFLICT` | 存在无法规则化解决的版本冲突 | 否 | 展示冲突并创建复核项 |
| `RAG_PARSE_QUALITY_BLOCKED` | 命中文档未通过解析质量门 | 否 | 阻断引用并通知知识管理员 |
| `RAG_INDEX_UNAVAILABLE` | 检索索引不可用 | 是 | 重试或降级到受控精确检索 |
| `RAG_TIMEOUT` | 调用超时 | 是 | 按幂等键重试，不重复写结果 |
| `RAG_CITATION_VALIDATION_FAILED` | 答案引用无法支持事实单元 | 否 | 删除不支持内容或返回证据模式 |
| `RAG_INPUT_INVALID` | 输入缺少必要条件或格式错误 | 否 | 返回结构化字段错误 |

权限拒绝响应不得返回无权访问的文档标题、数量、摘要或版本信息。

### 6.17.5 幂等与审计

只读检索可以重复执行，但结果持久化应使用：

```text
tool_execution_id
  + normalized_query_hash
  + effective_acl_version
  + knowledge_index_version
  + retrieval_config_version
```

同一次 Tool 执行重试不得产生多份不可关联的 `knowledge_result_id`。

---

## 6.18 与 Agent 和 Workflow 的集成

### 6.18.1 调用时序

```text
User / Upstream Node
        ↓
Agent 判断是否需要工程依据
        ↓
Policy Engine 检查权限与高风险意图
        ↓
RAG Tool 校验 RAGQueryInput
        ↓
Retrieval Service 返回 RAGQueryOutput
        ↓
Workflow 保存 knowledge_result_id
        ↓
Agent 组织解释、追问或复核请求
        ↓
Report Tool / Human Review
```

Agent 可以决定“是否调用”和“如何使用结果”，但不能修改证据正文、来源版本或引用定位。

### 6.18.2 Workflow State 增量

知识节点只返回必要状态增量：

```python
from typing import Any


def build_knowledge_state_update(
    knowledge_result_id: str,
    review_required: bool,
    summary: str,
) -> dict[str, Any]:
    return {
        "knowledge_result_ids": [knowledge_result_id],
        "review_required": review_required,
        "final_summary": {
            "knowledge_summary": summary,
        },
    }
```

如果 State 使用 Reducer 合并 `knowledge_result_ids`，节点返回列表增量；如果未配置 Reducer，则节点必须先读取并显式合并既有 ID。具体规则由第五章定义的 State 实现决定。

### 6.18.3 节点路由

| RAG 状态 | Workflow 路由 |
|---|---|
| `answered` | 进入结果组织或报告节点 |
| `evidence_only` | 由 Agent 基于证据组织受限回答 |
| `needs_clarification` | 返回用户补充条件节点 |
| `insufficient_evidence` | 进入补充检测、知识管理员或人工复核节点 |
| `conflict` | 强制进入人工复核节点 |
| 权限拒绝 | 终止知识分支并记录安全事件 |
| 索引短暂不可用 | 按 Workflow 重试策略恢复 |

### 6.18.4 与检测结果结合

病害检测结果和知识证据属于不同事实域：

```text
detection_result_id  → 图像、模型、病害和测量证据
knowledge_result_id  → 规范、项目文件和案例证据
review_item_id       → 人工确认和修正记录
report_artifact_id   → 最终成果版本
```

报告节点通过这些 ID 组装完整证据链，不把 RAG 摘要写回病害检测原始结果。

### 6.18.5 人工复核触发条件

以下情况强制复核：

- 正式技术状况等级评定；
- 处治方案和优先级建议；
- 规范版本冲突或适用性不明；
- 只有 C 级证据支持关键结论；
- RAG 结果与检测数据明显矛盾；
- 报告签发；
- 涉及设备控制、飞行安全或现场作业指令。

---

## 6.19 受约束生成与拒答机制

### 6.19.1 生成输入

生成模型只接收：

- 规范化问题；
- 已授权的 Evidence Pack；
- 允许使用的检测事实摘要；
- 输出模式和结构化约束；
- 证据不足与高风险处理规则。

原始文档中的指令性文本被视为数据，不得改变系统规则、Tool 权限或输出约束。

### 6.19.2 答案结构

回答应明确分为：

1. **结论范围：** 当前证据能够支持到什么程度；
2. **依据：** 对应 Evidence ID 的来源事实；
3. **综合说明：** 模型对多条证据的归纳；
4. **冲突与不确定性：** 版本、适用性和证据缺口；
5. **建议动作：** 补充检测、查询或人工复核；
6. **引用清单：** 标题、编号、版本和原文定位。

不得把“模型综合说明”伪装为规范原文。

### 6.19.3 引用校验

生成后执行：

```text
提取事实单元
  ↓
检查 claim_evidence_map
  ↓
验证证据是否包含直接支持
  ↓
检查引用版本和定位
  ↓
删除或降级无支持事实
  ↓
生成最终答案
```

引用校验失败时，系统优先返回 `evidence_only`，不得悄悄保留未支持结论。

### 6.19.4 确定性拒答条件

出现以下任一情况时，状态不得为 `answered`：

- 没有可用 Evidence Item；
- 核心证据已失效且查询不是历史复现；
- 有效来源对关键结论存在未解决冲突；
- 所有候选均不适用于当前资产、地区、项目或日期；
- 用户请求正式评定或签发，但没有人工复核；
- 查询要求超出权限；
- 引用校验失败；
- 关键检测事实缺失，无法判断适用条件。

### 6.19.5 安全表达

拒答必须说明可公开的原因和下一步动作，但权限拒绝不得确认受限文档是否存在。

推荐表达结构：

```text
状态：证据不足 / 需要澄清 / 存在冲突 / 无访问权限
当前可确认：基于已授权证据可以确认的事实
缺失信息：需要补充的项目、日期、构件或检测数据
下一步：补充条件、发起复核或联系知识管理员
```

---

## 6.20 知识版本与生命周期

## 6.21 权限、安全与提示注入防护

## 6.22 缓存、性能与资源控制

## 6.23 评测体系

## 6.24 可观测性、审计与异常恢复

## 6.25 第一阶段实施范围

## 6.26 架构决策记录

## 6.27 本章结论

## 参考资料

## 修订记录
