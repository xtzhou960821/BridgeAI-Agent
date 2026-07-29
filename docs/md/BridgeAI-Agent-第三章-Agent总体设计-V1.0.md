# BridgeAI-Agent Architecture White Paper

# 第三章 Agent 总体设计

| 项目 | 内容 |
|---|---|
| 文档名称 | BridgeAI-Agent Architecture White Paper |
| 章节 | 第三章 Agent 总体设计 |
| 版本 | V1.0 |
| 状态 | 正式版 |
| 默认开发环境 | Mac Studio / Apple M3 Ultra / 512GB 统一内存 |
| 数据库 | PostgreSQL（本地部署） |
| 本地模型运行 | Apple MLX 优先 |
| 编制日期 | 2026-07-14 |

---

## 3.1 本章目标

本章定义 BridgeAI-Agent 的核心智能体架构，包括职责边界、状态模型、执行机制、规划策略、上下文管理、人工复核、异常恢复、日志追踪和后续多 Agent 演进路线。

BridgeAI-Agent 中的 Agent 不是病害识别模型，也不是普通聊天机器人。它是位于业务入口、工作流和专业工具之间的智能调度中枢。

其核心职责可以概括为：

> 理解任务、规划步骤、调用工具、维护状态、处理异常、组织证据、请求复核并输出成果。

Agent 不直接替代 YOLO、MLX 推理、GIS 计算、裂缝测量、数据库事务或 PDF 渲染。所有具备确定性输入输出的专业能力，应由 Tool 执行；Agent 负责决定“何时调用、调用什么、使用什么参数、是否需要复核、失败后如何处理”。

---

## 3.2 设计背景

现有 BridgeAI 工作流已经能够完成以下链路：

1. 现场采集影像；
2. 数据标注；
3. YOLO 模型训练；
4. Apple MLX 本地训练与推理；
5. 病害识别；
6. 结果统计；
7. 规范查询；
8. 处置建议生成；
9. Word/PDF 报告输出。

当前瓶颈不是“流程是否跑通”，而是：

- 不同任务需要人工判断下一步；
- 流程分支难以动态调整；
- 多个专业模块缺少统一调度；
- 中间状态和错误恢复不够标准化；
- 低置信度结果需要更明确的人工复核；
- 项目上下文、历史病害和报告内容尚未形成统一记忆体系；
- 后续道路、隧道、智慧工地扩展时，固定工作流会快速复杂化。

因此，Agent 化的目标不是推翻现有系统，而是把已经验证有效的能力升级为可被智能调度的标准工具，并通过状态图管理完整任务生命周期。

---

## 3.3 总体设计原则

### 3.3.1 Agent 负责决策，Tool 负责执行

Agent 可以决定调用 `detect_damage`，但不能在大模型内部直接输出病害框坐标。

Agent 可以决定调用 `generate_report`，但不能绕过报告模板、数据校验和正式文档渲染引擎。

### 3.3.2 确定性优先

对可规则化、可计算、可验证的环节，优先使用确定性代码和固定 Workflow。

适合确定性执行的场景包括：

- 文件格式检查；
- 图像尺寸检查；
- 模型推理；
- 坐标转换；
- 面积、长度和数量统计；
- 数据库写入；
- 报告模板渲染；
- 权限校验；
- 哈希计算；
- 版本记录。

适合 Agent 判断的场景包括：

- 任务意图识别；
- 工具选择；
- 任务拆分；
- 异常分支判断；
- 是否需要人工复核；
- 规范检索查询改写；
- 多结果汇总；
- 处置建议初稿组织；
- 报告叙述结构生成。

### 3.3.3 人在回路

BridgeAI-Agent 属于工程辅助系统，而不是无责任主体的自动决策系统。关键结论必须支持人工审核、修订、驳回和签发。

### 3.3.4 可追溯

每次 Agent 决策至少记录：

- task_id；
- 当前状态；
- 输入摘要；
- 使用的模型；
- Prompt 版本；
- 调用的 Tool；
- Tool 参数；
- Tool 返回值摘要；
- 决策结果；
- 时间戳；
- 人工复核记录。

### 3.3.5 本地优先

考虑到工程数据保密、模型体积和本地硬件条件，第一阶段默认：

- Agent 编排服务在 Mac Studio 本地运行；
- PostgreSQL 在本机运行；
- 本地模型优先通过 MLX 执行；
- 视觉模型本地推理；
- 项目文件存储在本地对象存储或受控目录；
- 云端大模型仅作为可选适配器，不作为强依赖。

---

## 3.4 Agent 职责边界

### 3.4.1 Agent 负责的工作

- 识别用户任务类型；
- 提取项目、桥梁、构件、时间范围等关键信息；
- 验证任务前置条件；
- 生成或选择执行计划；
- 调用 Tool；
- 读取 Tool 返回结果；
- 根据结果决定下一步；
- 更新任务状态；
- 生成复核清单；
- 触发人工审核；
- 查询行业知识库；
- 组织结论、建议和报告叙述；
- 处理失败重试或降级；
- 维护任务级上下文；
- 生成可追溯执行记录。

### 3.4.2 Agent 不负责的工作

- 直接执行 YOLO 推理；
- 直接完成裂缝像素测量；
- 直接进行摄影测量或 GIS 坐标转换；
- 绕过数据库访问层写表；
- 直接修改原始影像；
- 无依据地判定病害等级；
- 无人工审核签发正式检测结论；
- 直接渲染 Word/PDF；
- 直接控制无人机飞行；
- 直接替代有资质的检测工程师。

---

## 3.5 Agent 内部逻辑架构

```text
┌──────────────────────────────────────────────┐
│               BridgeAI Agent                 │
├──────────────────────────────────────────────┤
│ 1. Intent Parser      意图解析                │
│ 2. Context Builder    上下文构建              │
│ 3. Planner            任务规划                │
│ 4. Policy Engine      规则与权限判断          │
│ 5. Tool Router        工具选择                │
│ 6. Executor           调用执行                │
│ 7. State Manager      状态管理                │
│ 8. Memory Manager     记忆管理                │
│ 9. RAG Manager        知识检索                │
│10. Review Manager     人工复核                │
│11. Result Composer    结果汇总                │
│12. Audit Logger       审计日志                │
└──────────────────────────────────────────────┘
```

---

## 3.6 核心模块设计

### 3.6.1 Intent Parser

职责：

- 识别任务类型；
- 提取项目标识；
- 提取数据来源；
- 提取期望输出；
- 判断是否缺少必要信息。

建议首批支持任务类型：

- `bridge_inspection`
- `damage_detection`
- `damage_review`
- `historical_comparison`
- `knowledge_query`
- `report_generation`
- `dataset_analysis`
- `model_evaluation`

输出示例：

```json
{
  "intent": "bridge_inspection",
  "project_id": "P2026-001",
  "asset_type": "bridge",
  "input_source": "image_batch",
  "expected_outputs": [
    "damage_list",
    "statistics",
    "repair_advice",
    "pdf_report"
  ],
  "missing_fields": []
}
```

### 3.6.2 Context Builder

上下文构建器负责将当前任务真正需要的信息组织成紧凑上下文，避免一次性把全部项目数据塞给大模型。

上下文来源：

- 当前用户输入；
- PostgreSQL 中的项目记录；
- 历史任务状态；
- 模型版本；
- Tool 执行结果；
- RAG 检索片段；
- 人工复核记录；
- 报告模板配置。

上下文必须分层加载：

1. 必要字段；
2. 当前节点需要的数据；
3. 必要时追加历史上下文；
4. 不相关内容不得进入 Prompt。

### 3.6.3 Planner

Planner 负责生成任务执行计划。

第一阶段不建议完全自由规划，而应采用“模板计划 + Agent 参数化”的方式。

示例模板：

```yaml
plan_id: bridge_inspection_v1
steps:
  - validate_input
  - preprocess_images
  - detect_damage
  - calculate_statistics
  - retrieve_standards
  - generate_advice
  - request_review
  - generate_report
  - archive_task
```

Agent 可以根据任务情况：

- 跳过某些步骤；
- 增加复核节点；
- 调整 Tool 参数；
- 选择不同模型版本；
- 在失败时执行替代分支。

### 3.6.4 Policy Engine

Policy Engine 是 Agent 的安全边界。

规则示例：

- 正式报告必须人工签发；
- 置信度低于阈值必须进入复核；
- 未知规范版本不得生成确定性结论；
- 没有 project_id 不得写入正式项目表；
- Tool 未注册不得调用；
- 数据越权不得访问；
- 处治建议必须关联病害类型和证据；
- 生产任务不得默认使用实验模型。

### 3.6.5 Tool Router

Tool Router 根据任务节点、输入类型、模型能力和策略规则选择 Tool。

选择依据：

- Tool 名称与描述；
- 输入 Schema；
- Tool 版本；
- 是否启用；
- 支持的模型；
- 当前运行环境；
- 资源占用；
- 历史成功率；
- 超时配置；
- 是否允许生产调用。

### 3.6.6 Executor

Executor 负责：

- 参数校验；
- Tool 调用；
- 超时控制；
- 重试；
- 幂等控制；
- 结果解析；
- 错误映射；
- 生成调用日志。

Agent 不应直接调用内部 Python 函数，而应通过统一 Tool Executor 执行，以便日志、权限和版本控制保持一致。

### 3.6.7 State Manager

State Manager 是 LangGraph 架构的核心。

建议 Agent State：

```python
from typing import TypedDict, Any

class BridgeAgentState(TypedDict, total=False):
    task_id: str
    project_id: str
    user_id: str
    intent: str
    current_node: str
    status: str
    plan: list[dict[str, Any]]
    input_files: list[str]
    tool_results: dict[str, Any]
    review_items: list[dict[str, Any]]
    retrieved_knowledge: list[dict[str, Any]]
    final_output: dict[str, Any]
    error: dict[str, Any] | None
    retry_count: int
```

状态持久化分为三层：LangGraph Checkpointer 保存 `thread_id` 范围内的执行快照；`bridgeai_workflow` 业务表保存可查询的任务、事件和复核状态；项目和领域记忆保存于独立的项目表、知识库或 Store。不得在业务表中再复制一份完整框架 State 作为恢复依据。

### 3.6.8 Memory Manager

记忆分为三类：

#### 任务记忆

仅服务当前任务：

- 当前节点；
- Tool 输出；
- 用户修订；
- 复核状态；
- 临时摘要。

#### 项目记忆

服务同一桥梁或项目：

- 历史检测记录；
- 既往病害；
- 构件信息；
- 业主偏好；
- 报告模板；
- 项目术语；
- 常用模型。

#### 领域记忆

服务整个系统：

- 行业规范；
- 病害知识；
- 处治案例；
- 模型经验；
- 错误模式；
- 标注规则。

### 3.6.9 RAG Manager

RAG Manager 不等于 Memory。

RAG 负责从知识库检索外部依据，Memory 负责保存任务和项目上下文。

RAG 返回内容必须包含：

- 文档标识；
- 文档版本；
- 章节；
- 原文片段；
- 生效状态；
- 检索分数；
- 引用信息。

### 3.6.10 Review Manager

Review Manager 负责人工复核任务。

复核类型：

- 低置信度病害；
- 关键病害；
- 模型冲突；
- 规范适用性；
- 病害等级；
- 处治建议；
- 报告签发。

每条复核项应包含：

```json
{
  "review_id": "R-001",
  "task_id": "T-001",
  "type": "damage_confirmation",
  "priority": "high",
  "evidence_ids": ["IMG-1001", "DET-923"],
  "suggested_value": "裂缝",
  "review_status": "pending"
}
```

### 3.6.11 Result Composer

Result Composer 负责将多个 Tool 输出组合为结构化成果。

它不能篡改原始 Tool 结果，只能：

- 组织；
- 汇总；
- 解释；
- 生成叙述；
- 添加引用；
- 生成报告输入数据。

### 3.6.12 Audit Logger

Audit Logger 记录完整决策链。

建议日志级别：

- INFO：节点开始、结束；
- TOOL：工具调用；
- DECISION：Agent 决策；
- REVIEW：人工复核；
- WARNING：可恢复异常；
- ERROR：任务失败；
- SECURITY：权限与访问异常。

---

## 3.7 Agent 生命周期

```text
Created
  ↓
Validating
  ↓
Planning
  ↓
Running
  ↓
WaitingReview
  ↓
Resuming
  ↓
Reporting
  ↓
Completed
```

异常状态：

```text
Running → Retrying → Running
Running → Degraded → WaitingReview
Running → Failed
Reporting → Failed
```

### 生命周期要求

- 每次状态变化写入 PostgreSQL；
- 状态变化必须带时间戳；
- 失败必须记录失败节点；
- 可恢复任务必须保存恢复点；
- 完成任务必须冻结关键版本信息；
- 报告签发后不得静默覆盖历史版本。

---

## 3.8 LangGraph 状态图建议

```text
START
  │
  ▼
parse_intent
  │
  ▼
validate_request ──失败──> request_user_input
  │
  ▼
load_project_context
  │
  ▼
build_plan
  │
  ▼
preprocess_images
  │
  ▼
detect_damage
  │
  ├──低置信度──> human_review
  │                   │
  │                   ▼
  └──────────────> calculate_statistics
                      │
                      ▼
               retrieve_standards
                      │
                      ▼
                generate_advice
                      │
                      ▼
                  final_review
                      │
                      ▼
                generate_report
                      │
                      ▼
                 archive_task
                      │
                      ▼
                     END
```

---

## 3.9 Agent 与 Workflow 的状态持久化边界

第三章不再单独定义 `agent_tasks`、`agent_events`、`agent_reviews` 等平行表，统一以第五章的 `bridgeai_workflow` Schema 为准：

| 信息类别 | 权威存储 | 主要用途 |
|---|---|---|
| 图执行快照 | LangGraph Checkpointer | `thread_id` 恢复、Interrupt、故障恢复和历史调试 |
| 业务任务 | `workflow_tasks`、`workflow_runs` | 任务查询、进度、权限、版本与统计 |
| 业务事件 | `workflow_events`、`workflow_node_executions` | 审计、观测、重试与幂等控制 |
| 人工复核 | `workflow_reviews` | 待办、审批、前后值与签发记录 |
| 项目与领域记忆 | 项目表、知识库或 Store | 跨线程项目上下文、历史病害和可引用知识 |

业务表只保存必要的检索字段、摘要、版本和关联 ID；不复制完整框架 State，也不得直接修改 Checkpointer 内部表结构。详细 Schema、`task_id` / `thread_id` / `run_id` 语义及恢复流程以第五章 5.10 至 5.18 为准。

---

## 3.10 Prompt 架构

建议 Prompt 分层：

1. System Prompt：角色、责任、安全边界；
2. Task Prompt：当前任务目标；
3. Context：项目和节点上下文；
4. Tool Definitions：可调用工具；
5. Policy：必须遵守的工程规则；
6. Output Schema：结构化输出格式。

禁止在一个超长 Prompt 中混合全部规范、全部项目历史和全部 Tool 文档。

### 结构化输出示例

```json
{
  "decision": "call_tool",
  "tool_name": "yolo_damage_detection",
  "reason": "输入为已完成预处理的桥梁图像批次",
  "arguments": {
    "task_id": "T-001",
    "model_version": "bridge-yolo26-v3.2",
    "confidence_threshold": 0.35
  },
  "next_state": "detecting"
}
```

---

## 3.11 本地模型策略

基于 M3 Ultra 和 512GB 统一内存，建议：

- 视觉模型优先本地推理；
- 文本大模型优先 MLX；
- 大模型与视觉模型避免同时无上限占用内存；
- 通过模型服务层统一加载和卸载；
- 对长上下文任务采用摘要与检索，不依赖单纯扩大上下文；
- 建立模型预热和常驻策略；
- 训练任务与生产 Agent 任务隔离；
- 对高负载任务设置队列和并发限制。

### 模型服务接口

```text
Agent
  ↓
Model Gateway
  ├── MLX Local LLM
  ├── YOLO26
  ├── Embedding Model
  └── Optional Cloud LLM
```

Agent 不直接绑定某一个模型 SDK。

---

## 3.12 异常恢复策略

异常分为：

- 输入异常；
- Tool 参数异常；
- Tool 执行异常；
- 模型异常；
- 数据库异常；
- 文件异常；
- 权限异常；
- Agent 决策异常；
- 人工复核超时。

恢复策略：

1. 参数错误：不重试，返回校验失败；
2. 短暂超时：指数退避重试；
3. 模型不可用：切换备用模型；
4. 低置信度：进入人工复核；
5. 数据库连接失败：任务暂停并保留状态；
6. 报告生成失败：从 Reporting 节点恢复；
7. Agent 输出不符合 Schema：自动修复一次，仍失败则中止；
8. 未知异常：记录事件并进入 Failed。

---

## 3.13 幂等设计

每个 Agent 节点都应支持重复执行而不产生重复业务数据。

建议使用：

```text
idempotency_key = task_id + node_name + input_hash + tool_version
```

示例：

- 同一批图像重复检测时，可复用已完成结果；
- 报告生成失败重试时，不重复创建多个正式版本；
- 人工复核提交不得重复写入；
- Agent 重启后可以从最后稳定节点继续。

---

## 3.14 可观测性

必须监控：

- 任务成功率；
- 平均任务时长；
- 每节点耗时；
- Tool 调用次数；
- Tool 失败率；
- 重试次数；
- 人工复核比例；
- 低置信度比例；
- Token 消耗；
- 本地内存占用；
- 模型加载时间；
- PostgreSQL 查询耗时。

建议所有事件附带：

- trace_id；
- task_id；
- project_id；
- node_name；
- tool_name；
- model_version。

---

## 3.15 安全设计

- Agent 不能直接执行任意 Shell 命令；
- Tool 必须白名单注册；
- 文件路径必须经过沙箱校验；
- 数据库访问必须通过 Repository 层；
- Prompt 中不得暴露数据库密码；
- 项目之间必须进行权限隔离；
- Tool 输出进入 Agent 前应进行清洗；
- 正式报告必须经过签发流程；
- 外部模型调用必须可配置脱敏策略。

---

## 3.16 测试策略

### 单元测试

- Intent Parser；
- Planner；
- Policy Engine；
- Router；
- State Manager；
- Result Composer。

### 集成测试

- Agent + PostgreSQL；
- Agent + YOLO Tool；
- Agent + RAG；
- Agent + Report Tool；
- 人工复核恢复流程。

### 场景测试

- 正常桥梁巡检；
- 图像缺失；
- 模型低置信度；
- Tool 超时；
- PostgreSQL 短暂断连；
- 报告生成失败；
- 人工驳回结果；
- 历史任务恢复。

---

## 3.17 第一阶段实现范围

第一阶段只实现一个总控 Agent：

```text
BridgeInspectionAgent
```

它负责：

- 接收巡检任务；
- 调度现有 Tool；
- 管理任务状态；
- 触发人工复核；
- 组织报告输入。

暂不拆分为多个自治 Agent。

这是因为当前最重要的是建立：

- 标准 Tool；
- 稳定 State；
- 可恢复 Workflow；
- PostgreSQL 持久化；
- 人工复核；
- 审计日志。

---

## 3.18 后续多 Agent 演进

当系统稳定后，可拆分：

- Detection Agent；
- Measurement Agent；
- Knowledge Agent；
- Review Agent；
- Report Agent；
- Project Agent。

多 Agent 不是简单地“多放几个大模型”，而是不同职责、状态、权限和可观测边界的独立执行单元。第一步可优先使用 LangGraph 子图或明确的服务边界；只有确需独立生命周期或跨进程协作时，才拆分为独立 Agent 服务。

MCP 用于将专业 Tool 暴露给不同 Agent 客户端；A2A 用于独立 Agent 服务之间的协作。两者均不替代 `workflow_tasks`、业务事件和人工复核记录。

Google ADK 可在以下条件满足后开展架构验证，而非作为默认替换目标：

- Tool 接口稳定；
- 状态模型稳定；
- 单 Agent 运行可靠；
- 业务确实需要多个独立角色协作；
- 多 Agent 带来的收益大于复杂度。
- 已验证所选语言版本具备所需的本地部署、持久化、人工介入和 Tool 接入能力；
- 已完成 State、Session、事件、权限和 Artifact 协议的兼容性评估。

Dify 可作为面向业务人员的低代码知识问答或轻量流程入口，通过 REST / MCP 调用 BridgeAI 服务；不得与 LangGraph 共同承担同一巡检任务的恢复和状态主控。

---

## 3.19 本章结论

BridgeAI-Agent 的 Agent 是任务级调度中枢。

第一阶段应采用：

> 单总控 Agent + LangGraph 状态图 + PostgreSQL 持久化 + 标准 Tool + 人工复核。

Mac Studio 的 M3 Ultra 和 512GB 统一内存，使本地模型、本地视觉推理和本地数据处理具备很强的工程可行性。系统应充分利用本地算力，但仍需通过模型网关、队列、状态持久化和资源限制保证稳定性。

Agent 的成功标准不是“能聊天”，而是：

- 能正确理解任务；
- 能可靠调用工具；
- 能处理中断；
- 能恢复状态；
- 能请求复核；
- 能组织证据；
- 能输出可追溯成果。
