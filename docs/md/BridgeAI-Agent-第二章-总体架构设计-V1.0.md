# BridgeAI-Agent 总体架构设计说明书

# 第二章 总体架构设计（V1.0）

## 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | BridgeAI-Agent 总体架构设计说明书 |
| 章节 | 第二章 总体架构设计 |
| 版本 | V1.0 |
| 日期 | 2026-07-13 |

---

# 2.1 设计目标

本章定义 BridgeAI-Agent 的总体软件架构。

总体目标不是重新开发病害识别模型，而是在已有能力基础上构建一个能够完成完整巡检任务的 AI Agent 平台。

平台需要满足以下要求：

- Agent 负责任务理解与受策略约束的调度；
- Tool 负责专业能力执行；
- Workflow Runtime 负责流程控制、状态迁移和恢复；
- Memory 负责上下文记忆；
- RAG 负责行业知识；
- 数据资产可持续沉淀；
- 全流程可追溯。

---

# 2.2 总体架构

| 架构层（自上而下） | 关键组件 | 核心职责 |
|---|---|---|
| 表现层 | Web / Desktop / Mobile | 上传资料、创建任务、查看结果、人工复核和下载报告。 |
| 应用服务层 | FastAPI / 权限 / 任务 API / 人工复核 | 承接请求，执行身份与项目权限校验，管理任务生命周期和业务审计。 |
| Agent 与 Workflow 编排层 | LangGraph StateGraph | 在策略、确定性关口和人工复核约束下，组织任务规划、状态迁移、Tool 调用和恢复执行。 |
| Tool 与领域服务层 | YOLO Tool / RAG Tool / GIS Tool / Report Tool | 提供可独立测试的专业能力及受控副作用。 |
| 数据与基础设施层 | PostgreSQL / Vector DB / Object Storage / MLX · YOLO26 · FastAPI · Redis | 提供业务数据、向量检索、文件存储、模型推理、队列、日志和运行支撑。 |

---

# 2.3 五层架构

## 第一层：表现层（Presentation）

负责人与系统交互。

包括：

- Web（Vue）；
- 桌面客户端；
- 移动端；
- 管理后台。

职责：

- 上传图片；
- 创建任务；
- 查看结果；
- 人工复核；
- 下载报告。

---

## 第二层：应用服务层（Application Service）

负责把表现层请求转换为受权限、任务和审计约束的业务操作。

包括：

- FastAPI 任务 API；
- 身份、组织、项目和角色权限校验；
- 任务创建、查询、暂停、恢复与取消；
- 人工复核界面和回调；
- 向现有业务系统提供 REST / WebSocket 接口；
- 可选的 Dify 接入：仅作为知识问答、轻量流程或运营入口，通过 API / MCP 调用 BridgeAI 服务。

应用服务层不直接编排病害巡检节点，也不保存框架私有的执行状态。

---

## 第三层：Agent 与 Workflow 编排层

第一阶段采用 LangGraph StateGraph，承担受策略约束的 Agent 决策和可恢复 Workflow 执行。

职责：

- 理解用户目标；
- 制定执行计划；
- 管理状态；
- 调用 Tool；
- 处理中断；
- 请求人工审核；
- 汇总结果；
- 在确定性关口、权限策略和人工复核要求内组织已有专业能力。

---

## 第四层：Tool 与领域服务层

所有成熟能力全部封装为 Tool 或领域服务。

第一阶段建议包括：

- YOLO Detection Tool；
- Crack Measure Tool；
- GIS Tool；
- RAG Tool；
- PDF Report Tool；
- Word Report Tool；
- Statistics Tool；
- Image Preprocess Tool。

统一接口：

输入 → 执行 → 输出。

任何 Tool 都可以独立测试。Tool 负责确定性专业能力和受控副作用，不改变业务 Workflow 的状态机语义。

---

## 第五层：基础设施层

推荐技术栈：

- FastAPI；
- PostgreSQL；
- Redis；
- MinIO（对象存储）；
- Qdrant（向量数据库）；
- MLX；
- YOLO26。

基础设施负责：

- 数据存储；
- 模型管理；
- 日志；
- 权限；
- 队列；
- 版本控制。

---

# 2.4 数据流

用户上传图片

↓

应用服务创建任务并登记输入

↓

LangGraph 初始化或恢复 Workflow

↓

按策略调用 YOLO / GIS / RAG / Report Tool

↓

写入业务事件、Artifact 与 Checkpoint

↓

人工复核或条件路由

↓

输出 Word/PDF 并归档

---

# 2.5 为什么选择 LangGraph

当前阶段特点：

- 工作流固定；
- Tool 明确；
- 需要状态管理；
- 需要人工审核节点；
- 需要失败恢复；
- 需要在本地 Python 服务中直接协调 YOLO、GIS、RAG 和报告能力。

LangGraph 非常适合作为第一阶段架构：它提供细粒度状态图、持久化、中断恢复和人工复核能力，且可直接承载本地 Python Tool。

Google ADK 不是 LangGraph 的线性升级版，而是覆盖 Agent、Workflow、Session、Tool、Memory、评测和部署的另一套完整开发框架。未来若出现跨服务多 Agent、A2A 协作或 Google Cloud Agent Runtime 部署需求，可先以独立服务或试点 Workflow 验证 ADK。只要领域状态、业务事件、Tool SDK 和 Artifact 协议保持框架无关，就能降低共存或迁移成本；但仍必须进行 State、Session、持久化和权限模型的兼容性验证。

Dify 适合快速构建知识问答、轻量业务流程和人工运营入口。它不应与 LangGraph 同时管理同一桥梁巡检任务的状态、重试和恢复；核心长任务仍以 BridgeAI 的应用服务和 LangGraph 为唯一编排中心。

---

# 2.6 设计原则

1. Agent 负责受策略约束的判断、计划和解释。
2. Workflow Runtime 负责状态迁移、恢复、重试和执行语义。
3. Tool 负责确定性专业能力和受控副作用。
4. Checkpointer 负责线程级执行快照，业务表负责可查询任务状态。
5. Memory 负责跨步骤或跨任务上下文，RAG 负责可引用的外部工程依据。
6. 数据形成长期资产。
7. 人工负责关键结论与正式成果确认。

---

# 2.7 本章结论

BridgeAI-Agent 的总体架构采用“应用服务 + Agent 与 Workflow 编排 + Tool 与领域服务”的模式。

LangGraph 是第一阶段的核心编排运行时，不直接承担专业检测；所有已有能力均以 Tool 形式接入，并由 PostgreSQL、对象存储和可观测事件提供持久化支撑。

通过统一状态管理、知识检索和数据沉淀，系统为后续 MCP Tool 互操作、A2A Agent 协作和经验证的 Google ADK 架构试点奠定基础。Dify 保持为可选低代码应用入口，不成为核心巡检长任务的第二编排中心。
